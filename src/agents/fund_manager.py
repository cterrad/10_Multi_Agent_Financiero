"""
Agente Director del Fondo (Fund Manager).

QUÉ CAMBIA RESPECTO DE LA VERSIÓN ANTERIOR
------------------------------------------
La versión anterior decidía con dos variables —`momentum_classification` y
`rsi`— y emitía el tamaño de posición como una CADENA literal:

    elif momentum == "NEUTRAL":
        rating = "MANTENER"
        position_size_pct = "2.0% - 3.0%"

Eso producía tres defectos encadenados, todos visibles en el informe del
2026-08-21, donde cuatro valores aprobados con perfiles radicalmente distintos
—GOOGL con P/E 17 y margen del 55%, BE con P/E 270 y margen del 8%— recibieron
exactamente el mismo dictamen y el mismo «2.0% - 3.0%»:

  1. Los fundamentales no entraban en la decisión más allá del sí/no del
     gatekeeper. Aprobar por los pelos y aprobar con holgura pesaban igual.
  2. Al ser una cadena, el tamaño no se podía sumar, ni escalar por
     volatilidad, ni presupuestar. Una posición del 3% en un valor con 80% de
     volatilidad aporta cuatro veces más riesgo que otra del 3% con 20%, y el
     sistema no podía ni expresar esa diferencia.
  3. Stop y objetivo usaban los mismos múltiplos de ATR para todo y sin declarar
     horizonte, así que el ratio riesgo/recompensa de 1.75 era ininterpretable:
     no se sabía a cuántas sesiones aplicaba.

Ahora la decisión combina CONVICCIÓN FUNDAMENTAL (del Analista de Calidad) con
MOMENTUM (puntuación continua del Analista Técnico), el tamaño sale de un
presupuesto de riesgo explícito y los múltiplos de ATR dependen del estilo.

CADA PASO ES UNA TOOL
---------------------
Rating compuesto, vetos, niveles de riesgo, dimensionamiento y perfil de riesgo
están en `src/tools/decision.py`, invocables por separado. Son las cuatro
variables más sensibles del sistema —`rating`, `peso_objetivo`,
`stop_loss_atr`, `take_profit_atr`— y separarlas hace que la traza responda a la
pregunta que siempre se hace ante un dictamen sorprendente: qué puntuación lo
produjo y qué veto lo recortó después.

Esas tools quedan FUERA de `TOOLS_LECTURA`, así que el agente investigador ReAct
no las alcanza. El modelo no emite dictámenes en este sistema.

REGLA DE RIESGO
---------------
    peso = (riesgo_asumible / distancia_al_stop) · factor_volatilidad

Es la regla de dimensionamiento por volatilidad estándar: se fija cuánto
patrimonio se está dispuesto a perder si salta el stop, y el tamaño se deduce.
No al revés.

PRECIO DE ENTRADA
-----------------
Desde que existe el Analista de Posicionamiento, los niveles NO se miden desde
el último cierre sino desde `precio_entrada_objetivo` cuando este existe. Un
stop medido sobre un precio que no se ha pagado describe una operación que nadie
hizo, y el ratio riesgo/recompensa que sale de ahí es ininterpretable.

Cuando ese agente no puede emitir ajuste —sin cadena de opciones no hay nivel de
precio, y es lo que ocurre en todo el backtest— el precio de entrada ES el de
mercado y el comportamiento es exactamente el anterior.

INVARIANTE: el LLM solo sobrescribe `summary`, y siempre después de que
`rating`, `peso_objetivo`, `stop_loss_atr` y `take_profit_atr` estén fijados.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.agents.base import AgenteBase, Traza
from src.config import (
    get_llm,  # noqa: F401  — resuelto por módulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_FUND_MANAGER, prompt_fund_manager
from src.state import FinancialAnalysisState
from src.tools.decision import (  # noqa: F401  — contrato público del agente
    CONVICCION_NEUTRA,
    CORTES_RATING,
    ESCALERA,
    PESO_FUNDAMENTAL,
    PESO_TECNICO,
    _bajar,
    _decision_rechazada,
    _justificacion,
    _tope,
)

__all__ = ["FundManagerAgent", "CORTES_RATING", "ESCALERA",
           "PESO_FUNDAMENTAL", "PESO_TECNICO", "CONVICCION_NEUTRA"]


class FundManagerAgent(AgenteBase):
    """
    Decisión final de inversión y parámetros de gestión de riesgo.

    Cinco categorías: COMPRA FUERTE, COMPRA, MANTENER, VENTA, VENTA FUERTE.
    Más SIN OPINION cuando los datos no permiten evaluar, que es distinto de
    VENTA y no debe colapsarse en ella.
    """

    nombre = "fund_manager"
    rol = "Director de Inversiones"
    system_prompt = SYSTEM_FUND_MANAGER

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        passed_gatekeeper = state.get("passed_fundamental_gatekeeper", False)
        fund_report = state.get("fundamental_report", {}) or {}
        tech_report = state.get("technical_report", {}) or {}
        quality_report = state.get("quality_report", {}) or {}
        debate_report = state.get("debate_report", {}) or {}
        pos_report = state.get("positioning_report", {}) or {}
        regimen_report = state.get("regimen_report", {}) or {}
        rec = state.get("reconciliation_data", {}) or {}
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}

        current_price = raw_tech.get("close", 0.0) or 0.0
        atr = raw_tech.get("atr") or (current_price * 0.02 if current_price else 0.0)
        volatilidad = (tech_report.get("volatilidad_anual")
                       or raw_tech.get("volatilidad_anual") or 0.0)

        estilo = quality_report.get("style_classification", "MIXTA")
        conviccion_obj = quality_report.get("conviccion_fundamental", {}) or {}
        conviccion = conviccion_obj.get("valor")
        banderas = quality_report.get("banderas_rojas", []) or []
        confianza_datos = rec.get("confidence_score", 1.0)
        momentum_score = tech_report.get("momentum_score")
        momentum = tech_report.get("momentum_classification", "NEUTRAL")
        sobreextendido = bool(tech_report.get("sobreextendido"))

        # --- Precio de referencia para los niveles -------------------------
        # El stop y el objetivo se miden desde el precio que se espera PAGAR, no
        # desde el último cruce del mercado: medirlos desde un precio al que no
        # se ha entrado produce un ratio riesgo/recompensa que describe una
        # operación que nadie hizo.
        #
        # La comprobación es `is None` y NO `or`: un `precio_entrada_objetivo`
        # de 0.0 es un dato corrupto, no una ausencia, y `or` lo enmascararía
        # sustituyéndolo en silencio. Es la misma distinción que separa un
        # ajuste de 0.0 —«entrar a mercado por confluencia»— de uno ausente.
        precio_entrada = pos_report.get("precio_entrada_objetivo")
        if precio_entrada is None:
            precio_entrada = current_price
        sesgo_macro_cls = pos_report.get("sesgo_macro_clasificacion")
        # El régimen se lee del informe del Analista de Régimen y NO del de
        # posicionamiento, aunque este último lo republique: el propietario del
        # dato es quien lo calcula, y leerlo de su fuente evita que una
        # reordenación del grafo lo deje en `None` sin que nada lo declare.
        regimen_cls = regimen_report.get("regimen_clasificacion")

        # ---------------- Rama de rechazo del gatekeeper -------------------
        # Se decide ANTES de cualquier otra tool: un valor rechazado no tiene
        # análisis técnico ni debate, y calcular su rating compuesto sería
        # inventar una puntuación sobre informes que no existen.
        if not passed_gatekeeper:
            return _decision_rechazada(
                ticker, fund_report, quality_report, current_price, estilo, banderas
            )

        # ---------------- Puntuación compuesta -----------------------------
        compuesto = self.usar_tool("calcular_rating_compuesto", {
            "conviccion_fundamental": conviccion,
            "momentum_score": momentum_score}, traza)

        # ---------------- Memoria de reflexión -----------------------------
        # Qué hizo el precio DESPUÉS de las señales con este mismo perfil, con
        # el dosier point-in-time que viaja en el estado. Va ANTES de los vetos
        # porque habilita uno de ellos, y su factor se publica para que la capa
        # de cartera lo aplique con la vista puesta en el conjunto: recortar
        # aquí, valor a valor, dejaría el presupuesto liberado sin reasignar.
        reflexion = self.usar_tool("consultar_reflexion", {
            "dosier": state.get("reflexion_data") or {},
            "estilo": estilo,
            "momentum": momentum}, traza)

        # ---------------- Meta-modelo --------------------------------------
        # Probabilidad de que ESTA operación acabe en beneficio, según el modelo
        # entrenado sobre las señales de compra ya desenlazadas. Llega ya
        # calculada en el estado —el agente no entrena ni carga artefactos— y se
        # traduce aquí al factor que la capa de cartera aplicará.
        #
        # Se publica SIN APLICAR, por el mismo motivo que `factor_reflexion`:
        # solo `PortfolioConstructor` ve el rebalanceo entero y puede reasignar
        # el presupuesto que el recorte libera. Aplicarlo aquí solo sabría restar.
        meta_estado = state.get("meta_data", {}) or {}
        meta = self.usar_tool("consultar_meta_etiqueta", {
            "probabilidad": meta_estado.get("probabilidad"),
            "tasa_base": meta_estado.get("tasa_base")}, traza)

        # ---------------- Vetos y topes ------------------------------------
        vetado = self.usar_tool("aplicar_vetos", {
            "rating_bruto": compuesto["rating_bruto"],
            "estilo": estilo,
            "banderas_rojas": banderas,
            "sobreextendido": sobreextendido,
            "confianza_datos": confianza_datos,
            "conviccion_evaluable": compuesto["conviccion_evaluable"],
            "sesgo_macro_clasificacion": sesgo_macro_cls,
            "reflexion_desfavorable": bool(reflexion.get("desfavorable")),
            "regimen_clasificacion": regimen_cls}, traza)
        rating = vetado["rating"]
        vetos = vetado["vetos"]

        # ---------------- Riesgo, tamaño y horizonte -----------------------
        niveles = self.usar_tool("calcular_niveles_riesgo", {
            "precio": precio_entrada, "atr": atr, "estilo": estilo}, traza)
        stop_loss = niveles["stop_loss"]
        take_profit = niveles["take_profit"]
        mult_stop = niveles["multiplo_stop"]
        mult_objetivo = niveles["multiplo_objetivo"]
        horizonte_dias = niveles["horizonte_dias"]

        dimensionado = self.usar_tool("dimensionar_posicion", {
            "rating": rating,
            "conviccion": compuesto["conviccion_usada"],
            "distancia_stop_pct": niveles["distancia_stop_pct"],
            "volatilidad": volatilidad,
            "confianza_datos": confianza_datos,
            "n_banderas": len(banderas),
            "sobreextendido": sobreextendido}, traza)

        riesgo = self.usar_tool("calcular_perfil_riesgo", {
            "precio": precio_entrada, "stop": stop_loss, "objetivo": take_profit,
            "atr": atr, "horizonte_dias": horizonte_dias,
            "mult_stop": mult_stop, "mult_objetivo": mult_objetivo}, traza)

        desglose = {
            "conviccion_fundamental": conviccion,
            "conviccion_usada": compuesto["conviccion_usada"],
            "momentum_score": momentum_score,
            "momentum_normalizado": compuesto["momentum_normalizado"],
            "peso_fundamental": PESO_FUNDAMENTAL,
            "peso_tecnico": PESO_TECNICO,
            "puntuacion_compuesta": compuesto["puntuacion_compuesta"],
            "rating_antes_de_vetos": compuesto["rating_bruto"],
            "rating_final": rating,
            "cortes": compuesto["cortes"],
            "reflexion": reflexion,
        }

        rationale = _justificacion(ticker, rating, estilo, conviccion, momentum,
                                   momentum_score, vetos, banderas, debate_report)

        summary = (
            f"Dictamen Final ({ticker}): {rating} · estilo {estilo}. "
            f"Asignación objetivo {dimensionado['peso_objetivo_pct']:.2f}% de la cartera "
            f"({dimensionado['motivo']}). "
            f"Precio de mercado ${current_price:.2f}"
            + ("" if precio_entrada == current_price
               else f", entrada objetivo ${precio_entrada:.2f} "
                    f"({pos_report.get('entrada_clasificacion')})")
            + f"; stop ${stop_loss} ({mult_stop}·ATR) y objetivo "
            f"${take_profit} ({mult_objetivo}·ATR) sobre un horizonte de {horizonte_dias} sesiones "
            f"(~{horizonte_dias / 21:.0f} meses). "
            f"Ratio riesgo/recompensa {riesgo['ratio_riesgo_recompensa']}, que exige acertar el "
            f"{riesgo['tasa_acierto_equilibrio']:.0%} de las veces para no perder dinero."
            # `riesgo` puede venir vacío si no se pudieron fijar stop y objetivo.
            # La condición mira las dos cosas y no solo el precio: `bool(nan)` es
            # True, así que comprobar únicamente `current_price` dejaba pasar un
            # precio inexistente a la rama que cita el ratio riesgo/recompensa.
            if current_price and riesgo
            else f"Dictamen Final ({ticker}): {rating}. Sin precio ni niveles de riesgo disponibles."
        )

        return {
            "rating": rating,
            # Número, no cadena. `position_size_pct` conserva el nombre por
            # compatibilidad con el backtest y el informe, pero ahora es un
            # porcentaje sumable.
            "position_size_pct": dimensionado["peso_objetivo_pct"],
            "position_size_display": dimensionado["display"],
            "peso_objetivo": dimensionado["peso_objetivo"],
            "dimensionado": dimensionado,
            # Factor de la memoria de reflexión. Se publica SIN aplicar: quien
            # lo aplica es `PortfolioConstructor`, que ve la cartera entera y
            # puede reasignar a los demás candidatos el presupuesto que este
            # recorte libera. Aplicarlo aquí reduciría la exposición en lugar de
            # redistribuirla, que es justo lo que no se quiere.
            "factor_reflexion": reflexion.get("factor", 1.0),
            "reflexion": reflexion,
            # Igual que el anterior: se publica SIN aplicar. Quien lo aplica y
            # reasigna es `PortfolioConstructor`.
            "factor_meta": meta.get("factor_meta", 1.0),
            "meta": meta,
            "current_price": current_price,
            # Los dos precios se publican por separado: sin ambos, el lector del
            # informe no puede saber si el stop está donde está por el ATR o por
            # el ajuste de entrada.
            "precio_entrada": round(precio_entrada, 2) if precio_entrada else None,
            "ajuste_entrada_pct": pos_report.get("ajuste_entrada_pct"),
            "entrada_clasificacion": pos_report.get("entrada_clasificacion"),
            "nivel_origen": pos_report.get("nivel_origen"),
            "sesgo_macro_clasificacion": sesgo_macro_cls,
            "regimen_clasificacion": regimen_cls,
            "stop_loss_atr": stop_loss,
            "take_profit_atr": take_profit,
            "multiplo_stop": mult_stop,
            "multiplo_objetivo": mult_objetivo,
            "horizonte_dias": horizonte_dias,
            "perfil_riesgo": riesgo,
            "estilo": estilo,
            "desglose_decision": desglose,
            "vetos_aplicados": vetos,
            "banderas_rojas": banderas,
            "rationale": rationale,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        quality = state.get("quality_report", {}) or {}
        tech = state.get("technical_report", {}) or {}
        return prompt_fund_manager(
            state.get("ticker", "UNKNOWN"), informe,
            (quality.get("conviccion_fundamental") or {}).get("valor"),
            tech.get("momentum_score"),
        )

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        return (f"DICTAMEN {informe.get('rating')} · "
                f"peso {informe.get('peso_objetivo', 0.0):.2%} · "
                f"vetos {len(informe.get('vetos_aplicados', []))}")
