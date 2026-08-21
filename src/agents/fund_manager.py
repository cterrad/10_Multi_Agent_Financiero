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

REGLA DE RIESGO
---------------
    peso = (riesgo_asumible / distancia_al_stop) · factor_volatilidad

Es la regla de dimensionamiento por volatilidad estándar: se fija cuánto
patrimonio se está dispuesto a perder si salta el stop, y el tamaño se deduce.
No al revés.

INVARIANTE: el LLM solo sobrescribe `summary`, y siempre después de que
`rating`, `peso_objetivo`, `stop_loss_atr` y `take_profit_atr` estén fijados.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    ATR_AJUSTE_POR_ESTILO,
    ATR_MULTIPLO_OBJETIVO,
    ATR_MULTIPLO_STOP,
    HORIZONTE_MINIMO_DIAS,
    PESO_MAXIMO_POSICION,
    PESO_MINIMO_OPERABLE,
    RIESGO_POR_POSICION_PCT,
    VOLATILIDAD_OBJETIVO,
    get_llm,
    texto_de_respuesta_llm,
)
from src.state import FinancialAnalysisState

# Cortes de la puntuación compuesta (0-100) sobre las cinco categorías. Son la
# tabla de decisión completa del sistema: no hay ninguna otra regla que asigne
# rating.
CORTES_RATING = (
    (72.0, "COMPRA FUERTE"),
    (58.0, "COMPRA"),
    (42.0, "MANTENER"),
    (28.0, "VENTA"),
    (0.0, "VENTA FUERTE"),
)

ESCALERA = ["VENTA FUERTE", "VENTA", "MANTENER", "COMPRA", "COMPRA FUERTE"]

# Peso relativo de fundamental y técnico en la puntuación compuesta. El
# fundamental manda porque el backtest mostró que la capa técnica por sí sola
# no ordena el rendimiento futuro; el técnico modula la entrada.
PESO_FUNDAMENTAL = 0.65
PESO_TECNICO = 0.35

# Convicción supuesta cuando el Analista de Calidad no pudo evaluar. Es
# deliberadamente el punto neutro: sin información no se premia ni se castiga
# la tesis, pero el tamaño sí se recorta por la vía del factor de datos.
CONVICCION_NEUTRA = 50.0


def _bajar(rating: str, escalones: int = 1) -> str:
    i = ESCALERA.index(rating) if rating in ESCALERA else 2
    return ESCALERA[max(0, i - escalones)]


def _tope(rating: str, maximo: str) -> str:
    i = ESCALERA.index(rating) if rating in ESCALERA else 2
    j = ESCALERA.index(maximo)
    return ESCALERA[min(i, j)]


class FundManagerAgent:
    """
    Decisión final de inversión y parámetros de gestión de riesgo.

    Cinco categorías: COMPRA FUERTE, COMPRA, MANTENER, VENTA, VENTA FUERTE.
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        passed_gatekeeper = state.get("passed_fundamental_gatekeeper", False)
        fund_report = state.get("fundamental_report", {}) or {}
        tech_report = state.get("technical_report", {}) or {}
        quality_report = state.get("quality_report", {}) or {}
        debate_report = state.get("debate_report", {}) or {}
        rec = state.get("reconciliation_data", {}) or {}
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}

        current_price = raw_tech.get("close", 0.0) or 0.0
        atr = raw_tech.get("atr") or (current_price * 0.02 if current_price else 0.0)
        volatilidad = tech_report.get("volatilidad_anual") or raw_tech.get("volatilidad_anual") or 0.0

        estilo = quality_report.get("style_classification", "MIXTA")
        conviccion_obj = quality_report.get("conviccion_fundamental", {}) or {}
        conviccion = conviccion_obj.get("valor")
        banderas = quality_report.get("banderas_rojas", []) or []
        confianza_datos = rec.get("confidence_score", 1.0)
        momentum_score = tech_report.get("momentum_score")
        momentum = tech_report.get("momentum_classification", "NEUTRAL")
        sobreextendido = bool(tech_report.get("sobreextendido"))

        vetos: List[str] = []

        # ---------------- Rama de rechazo del gatekeeper -------------------
        if not passed_gatekeeper:
            return self._decision_rechazada(
                ticker, fund_report, quality_report, current_price, estilo, banderas
            )

        # ---------------- Puntuación compuesta -----------------------------
        conviccion_efectiva = conviccion if conviccion is not None else CONVICCION_NEUTRA
        if conviccion is None:
            vetos.append("Convicción fundamental no evaluable: se asume el punto neutro (50) "
                         "y se recorta el tamaño por falta de datos")
        # El momentum llega en [-100, +100] y se lleva a [0, 100].
        momentum_norm = ((momentum_score + 100.0) / 2.0) if momentum_score is not None else 50.0

        compuesta = PESO_FUNDAMENTAL * conviccion_efectiva + PESO_TECNICO * momentum_norm
        rating = next(nombre for corte, nombre in CORTES_RATING if compuesta >= corte)
        rating_bruto = rating

        # ---------------- Vetos y topes ------------------------------------
        # Actúan SIEMPRE a la baja. Ninguna condición puede mejorar un rating:
        # el sesgo del sistema debe ser hacia no operar cuando hay dudas.
        if estilo == "ESPECULATIVA":
            rating = _tope(rating, "MANTENER")
            vetos.append("Estilo ESPECULATIVA: el dictamen no puede superar MANTENER")
        elif estilo == "TRAMPA_DE_VALOR":
            rating = _tope(rating, "MANTENER")
            vetos.append("Estilo TRAMPA_DE_VALOR: barato sin calidad; no puede superar MANTENER")
        elif estilo == "DATOS_INSUFICIENTES":
            rating = _tope(rating, "MANTENER")
            vetos.append("Calidad no evaluable por cobertura de datos: no puede superar MANTENER")

        if len(banderas) >= 2:
            rating = _bajar(rating)
            vetos.append(f"{len(banderas)} banderas rojas fundamentales: se baja un escalón")

        if sobreextendido and rating == "COMPRA FUERTE":
            rating = "COMPRA"
            vetos.append("Valor técnicamente sobreextendido: se rebaja COMPRA FUERTE a COMPRA "
                         "por calidad de la entrada, no por la tesis")

        if confianza_datos < 0.6:
            rating = _tope(rating, "MANTENER")
            vetos.append(f"Confianza en los datos de {confianza_datos:.0%}: no puede superar MANTENER")

        # ---------------- Riesgo, tamaño y horizonte -----------------------
        ajuste = ATR_AJUSTE_POR_ESTILO.get(estilo, ATR_AJUSTE_POR_ESTILO["MIXTA"])
        mult_stop = ajuste.get("stop", ATR_MULTIPLO_STOP)
        mult_objetivo = ajuste.get("objetivo", ATR_MULTIPLO_OBJETIVO)
        horizonte_dias = int(ajuste.get("horizonte_dias", 126))

        stop_loss = take_profit = None
        distancia_stop_pct = None
        if current_price > 0 and atr > 0:
            stop_loss = round(current_price - mult_stop * atr, 2)
            take_profit = round(current_price + mult_objetivo * atr, 2)
            distancia_stop_pct = (current_price - stop_loss) / current_price
        elif current_price > 0:
            stop_loss = round(current_price * 0.95, 2)
            take_profit = round(current_price * 1.10, 2)
            distancia_stop_pct = 0.05

        dimensionado = self._dimensionar(
            rating=rating,
            conviccion=conviccion_efectiva,
            distancia_stop_pct=distancia_stop_pct,
            volatilidad=volatilidad,
            confianza_datos=confianza_datos,
            n_banderas=len(banderas),
            sobreextendido=sobreextendido,
        )

        riesgo = self._perfil_riesgo(current_price, stop_loss, take_profit, atr,
                                     horizonte_dias, mult_stop, mult_objetivo)

        desglose = {
            "conviccion_fundamental": conviccion,
            "conviccion_usada": round(conviccion_efectiva, 1),
            "momentum_score": momentum_score,
            "momentum_normalizado": round(momentum_norm, 1),
            "peso_fundamental": PESO_FUNDAMENTAL,
            "peso_tecnico": PESO_TECNICO,
            "puntuacion_compuesta": round(compuesta, 1),
            "rating_antes_de_vetos": rating_bruto,
            "rating_final": rating,
            "cortes": {nombre: corte for corte, nombre in CORTES_RATING},
        }

        rationale = self._justificacion(ticker, rating, estilo, conviccion, momentum,
                                        momentum_score, vetos, banderas, debate_report)

        summary = (
            f"Dictamen Final ({ticker}): {rating} · estilo {estilo}. "
            f"Asignación objetivo {dimensionado['peso_objetivo_pct']:.2f}% de la cartera "
            f"({dimensionado['motivo']}). "
            f"Precio ${current_price:.2f}; stop ${stop_loss} ({mult_stop}·ATR) y objetivo "
            f"${take_profit} ({mult_objetivo}·ATR) sobre un horizonte de {horizonte_dias} sesiones "
            f"(~{horizonte_dias / 21:.0f} meses). "
            f"Ratio riesgo/recompensa {riesgo['ratio_riesgo_recompensa']}, que exige acertar el "
            f"{riesgo['tasa_acierto_equilibrio']:.0%} de las veces para no perder dinero."
            if current_price else f"Dictamen Final ({ticker}): {rating}. Sin precio disponible."
        )

        informe = {
            "rating": rating,
            # Número, no cadena. `position_size_pct` conserva el nombre por
            # compatibilidad con el backtest y el informe, pero ahora es un
            # porcentaje sumable.
            "position_size_pct": dimensionado["peso_objetivo_pct"],
            "position_size_display": dimensionado["display"],
            "peso_objetivo": dimensionado["peso_objetivo"],
            "dimensionado": dimensionado,
            "current_price": current_price,
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

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Como Director de Inversiones, redacta la orden ejecutiva final para {ticker}:\n"
                    f"- Dictamen: {rating} (estilo {estilo})\n"
                    f"- Convicción fundamental: {conviccion}/100 · Momentum: {momentum_score}/100\n"
                    f"- Asignación: {dimensionado['peso_objetivo_pct']:.2f}% de la cartera\n"
                    f"- Precio ${current_price:.2f} · Stop ${stop_loss} · Objetivo ${take_profit}\n"
                    f"- Horizonte: {horizonte_dias} sesiones · R:R {riesgo['ratio_riesgo_recompensa']}\n"
                    f"- Vetos aplicados: {'; '.join(vetos) or 'ninguno'}\n"
                    f"- Banderas rojas: {'; '.join(banderas) or 'ninguna'}\n"
                    f"Entrega una recomendación profesional en 3 frases. Menciona el horizonte "
                    f"y no exageres la convicción por encima de la cifra dada."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    informe["summary"] = texto
            except Exception as e:
                print(f"[FundManager] Error LLM: {e}")

        return informe

    # ------------------------------------------------------------------ #
    def _decision_rechazada(self, ticker: str, fund_report: Dict[str, Any],
                            quality_report: Dict[str, Any], precio: float,
                            estilo: str, banderas: List[str]) -> Dict[str, Any]:
        """
        Rama del gatekeeper rechazado.

        Distingue tres casos que la versión anterior colapsaba en «VENTA»:
        rechazo por deterioro real, rechazo por pérdidas severas y —el que
        faltaba— imposibilidad de evaluar por falta de datos. Emitir VENTA
        contra una empresa de la que no se sabe nada es una afirmación que los
        datos no sustentan; lo correcto es declararse sin opinión.
        """
        estado = fund_report.get("status", "RECHAZADO")
        metrics = fund_report.get("metrics", {}) or {}
        margen = metrics.get("net_margin")

        if estado == "DATOS_INSUFICIENTES":
            rating = "SIN OPINION"
            rationale = (
                f"No se emite dictamen sobre {ticker}: la cobertura de datos es insuficiente para "
                f"evaluar los fundamentales. {fund_report.get('summary', '')} "
                "Ausencia de datos no es evidencia de deterioro; emitir VENTA aquí sería afirmar "
                "algo que ninguna fuente respalda."
            )
        else:
            rating = "VENTA"
            if margen is not None and margen < -0.10:
                rating = "VENTA FUERTE"
            rationale = (f"Rechazado en el filtro fundamental. {fund_report.get('summary', '')}")

        summary = (
            f"Dictamen Final ({ticker}): {rating}. Sin asignación de cartera. "
            f"{rationale}"
        )

        return {
            "rating": rating,
            "position_size_pct": 0.0,
            "position_size_display": "0.00%",
            "peso_objetivo": 0.0,
            "dimensionado": {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0,
                             "display": "0.00%", "motivo": "no supera el filtro fundamental",
                             "factores": {}},
            "current_price": precio,
            "stop_loss_atr": None,
            "take_profit_atr": None,
            "multiplo_stop": None,
            "multiplo_objetivo": None,
            "horizonte_dias": None,
            "perfil_riesgo": {},
            "estilo": estilo,
            "desglose_decision": {"rating_final": rating, "motivo": estado},
            "vetos_aplicados": [f"Gatekeeper: {estado}"],
            "banderas_rojas": banderas,
            "rationale": rationale,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def _dimensionar(self, rating: str, conviccion: float,
                     distancia_stop_pct: Optional[float], volatilidad: float,
                     confianza_datos: float, n_banderas: int,
                     sobreextendido: bool) -> Dict[str, Any]:
        """
        Peso objetivo de la posición, en tanto por uno de la cartera.

        Cadena de cálculo, cada paso auditable:

          1. Riesgo asumible = presupuesto por posición × escala de convicción.
             Una convicción de 80/100 arriesga el doble que una de 40/100.
          2. Peso base = riesgo asumible / distancia al stop. Si el stop está a
             un 10% y se aceptan perder 75 puntos básicos, el peso es 7.5%.
          3. Factor de volatilidad = volatilidad objetivo / volatilidad real,
             acotado a 1. Iguala la contribución al riesgo entre posiciones.
          4. Descuentos por confianza en los datos, banderas rojas y
             sobreextensión técnica.
          5. Topes duros: máximo por posición y mínimo operable.

        Los ratings que no son de compra devuelven cero: el sistema es solo
        largo, y MANTENER significa no abrir posición nueva.
        """
        factores: Dict[str, Any] = {}

        if rating not in ("COMPRA", "COMPRA FUERTE"):
            return {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0, "display": "0.00%",
                    "motivo": f"{rating} no genera asignación en una cartera solo larga",
                    "factores": factores}

        # 1. Escala de convicción: lineal entre 40 y 90 de convicción.
        escala_conviccion = max(0.4, min(1.5, (conviccion - 30.0) / 40.0))
        factores["escala_conviccion"] = round(escala_conviccion, 3)
        riesgo_asumible = RIESGO_POR_POSICION_PCT * escala_conviccion
        factores["riesgo_asumible_pct"] = round(riesgo_asumible * 100, 3)

        # 2. Peso por presupuesto de riesgo.
        distancia = distancia_stop_pct if (distancia_stop_pct and distancia_stop_pct > 0.01) else 0.10
        factores["distancia_stop_pct"] = round(distancia, 4)
        peso = riesgo_asumible / distancia
        factores["peso_por_riesgo"] = round(peso, 4)

        # 3. Escalado por volatilidad.
        if volatilidad and volatilidad > 0:
            factor_vol = min(1.0, VOLATILIDAD_OBJETIVO / volatilidad)
        else:
            factor_vol = 1.0
        factores["factor_volatilidad"] = round(factor_vol, 3)
        peso *= factor_vol

        # 4. Descuentos.
        factor_datos = max(0.5, min(1.0, confianza_datos))
        factor_banderas = max(0.4, 1.0 - 0.2 * n_banderas)
        factor_extension = 0.7 if sobreextendido else 1.0
        factores.update({
            "factor_confianza_datos": round(factor_datos, 3),
            "factor_banderas_rojas": round(factor_banderas, 3),
            "factor_sobreextension": factor_extension,
        })
        peso *= factor_datos * factor_banderas * factor_extension

        # 5. Topes.
        peso_final = min(PESO_MAXIMO_POSICION, peso)
        if peso_final < PESO_MINIMO_OPERABLE:
            factores["descartado_por_minimo"] = True
            return {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0, "display": "0.00%",
                    "motivo": (f"peso calculado {peso_final:.2%} por debajo del mínimo operable "
                               f"{PESO_MINIMO_OPERABLE:.2%}: el coste de operar supera la aportación"),
                    "factores": factores}

        motivo = (f"riesgo por posición {riesgo_asumible:.2%} sobre un stop al {distancia:.1%}, "
                  f"escalado por volatilidad ×{factor_vol:.2f}")
        if peso > PESO_MAXIMO_POSICION:
            motivo += f", limitado por el tope de concentración del {PESO_MAXIMO_POSICION:.0%}"

        return {
            "peso_objetivo": round(peso_final, 4),
            "peso_objetivo_pct": round(peso_final * 100, 2),
            "display": f"{peso_final * 100:.2f}%",
            "motivo": motivo,
            "factores": factores,
        }

    # ------------------------------------------------------------------ #
    @staticmethod
    def _perfil_riesgo(precio: float, stop: Optional[float], objetivo: Optional[float],
                       atr: float, horizonte_dias: int, mult_stop: float,
                       mult_objetivo: float) -> Dict[str, Any]:
        """
        Traduce los niveles de ATR a un perfil interpretable.

        El dato que faltaba en el informe: un ratio riesgo/recompensa solo
        significa algo junto a la tasa de acierto que exige para no perder
        dinero —1/(1+R:R)— y al plazo en que se espera que ocurra. Se declara
        además cuántas sesiones necesita el precio, a su ATR actual, para
        recorrer la distancia al objetivo.
        """
        if not precio or stop is None or objetivo is None:
            return {}

        riesgo = precio - stop
        recompensa = objetivo - precio
        if riesgo <= 0:
            return {}

        rr = recompensa / riesgo
        # Recorrido esperado: el ATR es el rango medio diario, así que la
        # distancia al objetivo dividida por el ATR da las sesiones necesarias
        # en un avance direccional puro. Es un suelo optimista, no un pronóstico.
        sesiones_minimas = int(round(recompensa / atr)) if atr > 0 else None

        return {
            "riesgo_por_accion": round(riesgo, 2),
            "recompensa_por_accion": round(recompensa, 2),
            "ratio_riesgo_recompensa": round(rr, 2),
            "tasa_acierto_equilibrio": round(1.0 / (1.0 + rr), 4),
            "riesgo_pct": round(riesgo / precio, 4),
            "recompensa_pct": round(recompensa / precio, 4),
            "atr_pct": round(atr / precio, 4) if precio else None,
            "horizonte_dias": horizonte_dias,
            "horizonte_meses": round(horizonte_dias / 21.0, 1),
            "sesiones_minimas_al_objetivo": max(sesiones_minimas or 0, HORIZONTE_MINIMO_DIAS)
            if sesiones_minimas is not None else None,
            "multiplos_atr": {"stop": mult_stop, "objetivo": mult_objetivo},
            "nota_horizonte": (
                f"Stop y objetivo se evalúan sobre {horizonte_dias} sesiones "
                f"(~{horizonte_dias / 21:.0f} meses). Fuera de ese plazo la posición se revisa, "
                f"no se mantiene por inercia."),
        }

    @staticmethod
    def _justificacion(ticker: str, rating: str, estilo: str, conviccion: Optional[float],
                       momentum: str, momentum_score: Optional[float], vetos: List[str],
                       banderas: List[str], debate: Dict[str, Any]) -> str:
        partes = [
            f"{ticker}: fundamentales aprobados; estilo {estilo} con convicción "
            f"{conviccion if conviccion is not None else 'no evaluable'}/100 y momentum {momentum} "
            f"({momentum_score:+.1f}/100)." if momentum_score is not None else
            f"{ticker}: fundamentales aprobados; estilo {estilo}."
        ]
        if vetos:
            partes.append("Ajustes a la baja aplicados: " + "; ".join(vetos) + ".")
        if banderas:
            partes.append("Banderas rojas vigentes: " + "; ".join(banderas) + ".")
        sintesis = debate.get("synthesis")
        if isinstance(sintesis, str) and sintesis:
            partes.append(f"Síntesis del debate: {sintesis}")
        return " ".join(partes)
