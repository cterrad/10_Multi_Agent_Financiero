"""
Generador del informe de inversión.

QUÉ CAMBIÓ EN ESTA VERSIÓN Y POR QUÉ
------------------------------------
La versión anterior imprimía cada valor como SEIS secciones de prosa —filtro,
calidad, técnico, noticias, debate y dictamen—, cada una con su párrafo
explicativo. El resultado era correcto y casi ilegible: para saber qué se
recomendaba sobre un valor había que recorrer pantalla y media, y el mismo
párrafo sobre cómo interpretar una métrica se repetía en cada ficha.

Ahora cada valor cabe en UNA TABLA de seis filas —un bloque por fila, con su
veredicto y sus cifras clave— y todo el pormenor vive detrás de bloques
`<details>` plegados. No se ha eliminado ni un dato: se ha dejado de imprimir
seis veces lo que se lee una.

Los textos explicativos que describían el método (cómo se calcula un peso, por
qué las noticias no mueven el dictamen, qué significa cada estilo) estaban
repetidos por ficha y ahora aparecen UNA vez, en el anexo.

Estructura, separada por AUDIENCIA y no por tamaño:

  · `resumen_ejecutivo.md`  la decisión agregada. Es el punto de entrada.
  · `daily_selection.md`    el informe completo, con las fichas.
  · `detalle/{TICKER}.md`   ficha del valor más la traza de herramientas.

Todo lo que aquí se imprime procede del estado; este módulo no calcula ninguna
variable de decisión.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config import (
    CAPITAL_BASE,
    EXPOSICION_BRUTA_MAXIMA,
    LIMITE_POR_SECTOR,
    MAX_DEBT_TO_EQUITY,
    MIN_NET_MARGIN,
    MIN_REVENUE_GROWTH,
    OUTPUT_DIR,
    PESO_MAXIMO_POSICION,
    RIESGO_POR_POSICION_PCT,
    RIESGO_TOTAL_CARTERA_PCT,
    VOLATILIDAD_OBJETIVO,
)
from src.state import FinancialAnalysisState

SIN_DATO = "n/d"

# Glosario de las etiquetas de estilo. Se imprime UNA vez en el anexo, no en
# cada ficha: una definición repetida seis veces no informa seis veces.
GLOSARIO_ESTILOS = {
    "CALIDAD_COMPUESTA": "Reinvierte por encima de su coste de capital de forma sostenida (Buffett).",
    "CALIDAD_DETERIORADA": "Rentable pero con varios defectos estructurales a la vez; la tesis exige que se corrijan.",
    "VALOR": "Descuento sobre su valor intrínseco conservador manteniendo calidad (Graham).",
    "GARP": "Crecimiento a precio razonable; el PEG confirma que el múltiplo no se adelantó (Lynch).",
    "CRECIMIENTO": "La tesis depende de que el crecimiento se mantenga. El múltiplo no deja margen de error.",
    "CICLICA": "El múltiplo depende de la fase del ciclo. Un P/E bajo en máximos de beneficio señala techo.",
    "TRAMPA_DE_VALOR": "Barato con calidad deteriorada: el descuento parece justificado.",
    "ESPECULATIVA": "El riesgo domina cualquier lectura de valor o crecimiento.",
    "MIXTA": "Sin dominancia clara de ninguna dimensión.",
    "DATOS_INSUFICIENTES": "Cobertura por debajo del mínimo para clasificar. Es un juicio sobre los datos, no sobre la empresa.",
}

# Glosario de las decisiones de entrada del Analista de Posicionamiento.
GLOSARIO_ENTRADA = {
    "PERSEGUIR": "Macro, opciones y momentum confirman y nada está sobreextendido: se entra a mercado.",
    "ESCALONAR": "Acuerdo parcial, o acuerdo total con algo sobreextendido: se entra a medio camino del nivel.",
    "ESPERAR_RETROCESO": "Las señales divergen: se exige el retroceso completo hasta el nivel de la cadena.",
    "NO_APLICABLE": "Sin dos señales disponibles o sin nivel por debajo del precio: entrada al precio de mercado.",
}


def _p(valor: Optional[float], fmt: str = "{:.1%}") -> str:
    """Formatea o devuelve el marcador de ausencia. Nunca imprime un cero falso."""
    if valor is None:
        return SIN_DATO
    try:
        return fmt.format(valor)
    except (TypeError, ValueError):
        return str(valor)


def _texto(valor: Any) -> str:
    """
    Blindaje del informe frente a valores no textuales.

    Los proveedores de LLM devuelven `content` como lista de bloques y, si un
    agente nuevo olvidara pasar por `texto_de_respuesta_llm`, esa lista
    terminaría impresa como `[{'type': 'text', ...}]` — que es exactamente lo
    que ocurría antes de existir el helper. Aquí se corta esa vía de escape.
    """
    if valor is None:
        return SIN_DATO
    if isinstance(valor, str):
        return valor
    if isinstance(valor, list):
        partes = []
        for b in valor:
            if isinstance(b, dict):
                if b.get("type", "text") == "text" and b.get("text"):
                    partes.append(str(b["text"]))
            else:
                partes.append(str(b))
        return "\n".join(partes) if partes else SIN_DATO
    return str(valor)


def _si_no(valor: Optional[bool]) -> str:
    if valor is None:
        return "—"
    return "✅" if valor else "❌"


def _detalles(titulo: str, cuerpo: List[str]) -> List[str]:
    """Bloque plegable. Es lo que permite que la ficha quepa en una pantalla."""
    if not cuerpo:
        return []
    return [f"<details><summary>{titulo}</summary>", ""] + cuerpo + ["", "</details>", ""]


def _estado_serializable(estado: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara el estado para `daily_selection.json`.

    El canal `messages` contiene objetos `BaseMessage`, que `json.dump` solo
    puede volcar a través de `default=str` — es decir, como el `repr` de una
    lista de objetos de LangChain: ilegible y sin estructura sobre la que
    consultar nada. Se sustituyen por su forma tipada, que es la misma que ya
    guarda cada informe en `_traza`.
    """
    salida = dict(estado)
    mensajes = salida.get("messages")
    if mensajes:
        salida["messages"] = [
            {
                "tipo": type(m).__name__,
                "id": getattr(m, "id", None),
                "contenido": _texto(getattr(m, "content", "")),
                "tool_calls": [{"name": tc.get("name"), "id": tc.get("id")}
                               for tc in (getattr(m, "tool_calls", None) or [])],
                "tool_call_id": getattr(m, "tool_call_id", None),
                "name": getattr(m, "name", None),
            }
            for m in mensajes
        ]
    return salida


class ReportGenerator:
    """Genera el informe de inversión en Markdown y su equivalente en JSON."""

    # ================================================================== #
    def generate_daily_selection(self, results: List[FinancialAnalysisState],
                                 cartera: Optional[Any] = None,
                                 benchmark: Optional[Dict[str, Any]] = None,
                                 filename: str = "daily_selection.md") -> str:
        """
        Escribe los tres documentos y el JSON. Devuelve la ruta del resumen
        ejecutivo, que es el punto de entrada.
        """
        filepath = os.path.join(OUTPUT_DIR, filename)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
        cartera_dict = (cartera.a_dict() if cartera is not None
                        and hasattr(cartera, "a_dict") else None)

        # --- 1. Informe completo -----------------------------------------
        lineas: List[str] = self._cabecera("Informe de inversión", ahora, results, benchmark)
        lineas += self._tabla_decision(results)
        lineas += self._cartera(cartera_dict)
        lineas += ["## Fichas por compañía", ""]
        for res in results:
            lineas += self._ficha(res)
        lineas += self._calidad_de_datos(results)
        lineas += self._limitaciones()
        lineas += self._anexo(results)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas))

        # --- 2. Resumen ejecutivo ----------------------------------------
        ruta_resumen = os.path.join(OUTPUT_DIR, "resumen_ejecutivo.md")
        with open(ruta_resumen, "w", encoding="utf-8") as f:
            f.write("\n".join(self.documento_ejecutivo(results, cartera_dict,
                                                       benchmark, ahora)))

        # --- 3. Detalle por compañía --------------------------------------
        dir_detalle = os.path.join(OUTPUT_DIR, "detalle")
        os.makedirs(dir_detalle, exist_ok=True)
        for res in results:
            ticker = res.get("ticker", "?")
            with open(os.path.join(dir_detalle, f"{ticker}.md"), "w", encoding="utf-8") as f:
                f.write("\n".join(self.documento_detalle(res, ahora)))

        # --- 4. JSON ------------------------------------------------------
        json_path = os.path.join(OUTPUT_DIR, "daily_selection.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "generado": ahora,
                "benchmark": benchmark or {},
                "cartera": cartera_dict,
                "analisis": [_estado_serializable(r) for r in results],
            }, f, indent=2, ensure_ascii=False, default=str)

        print(f"[ReportGenerator] Resumen ejecutivo: {ruta_resumen}")
        print(f"[ReportGenerator] Informe completo:  {filepath}")
        print(f"[ReportGenerator] Detalle por valor: {dir_detalle}")
        return ruta_resumen

    # ================================================================== #
    # Documento 1: resumen ejecutivo
    # ================================================================== #
    def documento_ejecutivo(self, results: List[Dict[str, Any]],
                            cartera: Optional[Dict[str, Any]] = None,
                            benchmark: Optional[Dict[str, Any]] = None,
                            ahora: Optional[str] = None) -> List[str]:
        """La decisión agregada y nada más, con enlaces a lo demás."""
        ahora = ahora or datetime.now().strftime("%Y-%m-%d %H:%M")
        lineas = self._cabecera("Resumen ejecutivo", ahora, results, benchmark)
        lineas += self._tabla_decision(results)
        lineas += self._cartera(cartera)
        lineas += self._track_record()

        lineas += ["## Dónde seguir leyendo", "",
                   "| Documento | Contenido |", "| :--- | :--- |",
                   "| [Informe completo](daily_selection.md) | Fichas, calidad de datos, "
                   "limitaciones y anexo. |"]
        for res in results:
            ticker = res.get("ticker", "?")
            fd = res.get("final_decision", {}) or {}
            lineas.append(f"| [{ticker}](detalle/{ticker}.md) | "
                          f"**{fd.get('rating', SIN_DATO)}** — ficha y traza de herramientas. |")
        lineas += [""]
        return lineas

    # ================================================================== #
    # Documento 2: detalle por compañía
    # ================================================================== #
    def documento_detalle(self, res: Dict[str, Any],
                          ahora: Optional[str] = None) -> List[str]:
        """Ficha del valor más la traza de su análisis."""
        ticker = res.get("ticker", "?")
        ahora = ahora or datetime.now().strftime("%Y-%m-%d %H:%M")
        lineas = [
            f"# {ticker} — {res.get('company_name', ticker)}",
            "",
            f"`{ahora}` · {res.get('workflow_status', SIN_DATO)} · "
            f"[← resumen ejecutivo](../resumen_ejecutivo.md)",
            "",
        ]
        lineas += self._ficha(res, con_titulo=False)
        lineas += self._traza_de_agentes(res)
        lineas += self._registro_de_ejecucion(res)
        return lineas

    # ================================================================== #
    # Cabecera y tabla de decisión
    # ================================================================== #
    def _cabecera(self, titulo: str, ahora: str, results: List[Dict[str, Any]],
                  benchmark: Optional[Dict[str, Any]]) -> List[str]:
        b = benchmark or {}
        ref = (f"{b.get('ticker')} 12m {_p(b.get('change_12m_pct'))}"
               if b.get("ticker") else "sin índice (momentum absoluto)")
        tickers = ", ".join(r.get("ticker", "?") for r in results)
        # El régimen de volatilidad es un dato DE LOTE: el mismo número para los
        # cincuenta valores de la ejecución. Va en la cabecera y no en una
        # columna de la tabla precisamente por eso — repetirlo por fila sería
        # imprimir cincuenta veces lo que se lee una. Pero tiene que aparecer,
        # porque puede TOPAR el dictamen de todos ellos a la vez.
        g = next((r.get("regimen_report") for r in results if r.get("regimen_report")), None)
        reg = ""
        if g and g.get("regimen_clasificacion") not in (None, "NO_APLICABLE"):
            reg = (f" · régimen de mercado **{g['regimen_clasificacion']}** "
                   f"({g.get('serie_volatilidad', 'VIX')} "
                   f"{_p(g.get('nivel_volatilidad'), '{:.2f}')}, "
                   f"z {_p(g.get('zscore_volatilidad'), '{:+.2f}')})")
            if not g.get("puerta_regimen", True):
                reg += " — prohíbe perseguir el precio"
        return [
            f"# {titulo} — Selección Multi-Agente",
            "",
            f"`{ahora}` · {len(results)} valor(es): {tickers} · referencia {ref} · "
            f"capital ${CAPITAL_BASE:,.0f}{reg}",
            "",
            "> Sistema automatizado. Ratings, pesos y niveles salen de reglas deterministas; "
            "el modelo de lenguaje solo redacta los resúmenes. **No es asesoramiento de "
            "inversión.**",
            "",
        ]

    def _tabla_decision(self, results: List[Dict[str, Any]]) -> List[str]:
        """
        La decisión completa en una tabla.

        Incluye el precio de ENTRADA además del de mercado: desde que existe el
        Analista de Posicionamiento, el stop y el objetivo se miden desde el
        precio que se espera pagar, y sin las dos columnas no se puede saber si
        un stop está donde está por el ATR o por el ajuste de entrada.
        """
        lineas = [
            "## Decisión",
            "",
            "| Ticker | Estilo | Conv | Mom | Macro | Entrada | Dictamen | Peso | "
            "Mercado | Objetivo entrada | Stop | Take-profit | R:R | Horiz. |",
            "| :--- | :--- | ---: | ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for res in results:
            q = res.get("quality_report", {}) or {}
            t = res.get("technical_report", {}) or {}
            d = res.get("final_decision", {}) or {}
            p = res.get("positioning_report", {}) or {}
            riesgo = d.get("perfil_riesgo", {}) or {}
            conv = (q.get("conviccion_fundamental") or {}).get("valor")
            mom = t.get("momentum_score")
            horizonte = d.get("horizonte_dias")
            ajuste = p.get("ajuste_entrada_pct")

            entrada = p.get("entrada_clasificacion") or SIN_DATO
            if ajuste is not None:
                entrada = f"{entrada} {ajuste:+.1%}"

            lineas.append(
                f"| **{res.get('ticker', '?')}** "
                f"| `{(q.get('style_classification') or SIN_DATO)}` "
                f"| {_p(conv, '{:.0f}')} "
                f"| {f'{mom:+.0f}' if mom is not None else SIN_DATO} "
                f"| {self._macro_corto(p)} "
                f"| {entrada} "
                f"| **{d.get('rating', SIN_DATO)}** "
                f"| {_p(d.get('peso_objetivo'), '{:.2%}')} "
                f"| {_p(d.get('current_price'), '${:,.2f}')} "
                f"| {_p(d.get('precio_entrada'), '${:,.2f}')} "
                f"| {_p(d.get('stop_loss_atr'), '${:,.2f}')} "
                f"| {_p(d.get('take_profit_atr'), '${:,.2f}')} "
                f"| {_p(riesgo.get('ratio_riesgo_recompensa'), '{:.2f}')} "
                f"| {f'{horizonte}d' if horizonte else SIN_DATO} |")

        lineas += [
            "",
            "_Convicción 0-100 (calidad, valoración, crecimiento y solvencia, descontada por "
            "cobertura de datos) · Momentum −100 a +100 · Macro: posicionamiento de "
            "especuladores en futuros · Entrada: si se persigue el precio o se exige retroceso "
            "· Peso: resultado del presupuesto de riesgo, no un rango fijo. Definiciones en el "
            "anexo._",
            "",
        ]
        return lineas

    @staticmethod
    def _macro_corto(p: Dict[str, Any]) -> str:
        """Etiqueta macro abreviada para que la tabla no se desborde."""
        cls = p.get("sesgo_macro_clasificacion")
        if not cls or cls == "NO_APLICABLE":
            return SIN_DATO
        corto = {"VIENTO_A_FAVOR_FUERTE": "favor++", "VIENTO_A_FAVOR": "favor",
                 "NEUTRO": "neutro", "VIENTO_EN_CONTRA": "contra",
                 "VIENTO_EN_CONTRA_FUERTE": "contra−−"}.get(cls, cls)
        sesgo = p.get("sesgo_macro")
        return f"{corto} {sesgo:+.2f}" if sesgo is not None else corto

    # ================================================================== #
    # Cartera
    # ================================================================== #
    def _cartera(self, cartera: Optional[Dict[str, Any]]) -> List[str]:
        lineas = ["## Cartera propuesta", ""]
        if not cartera:
            return lineas + ["_No se construyó cartera agregada en esta ejecución._", ""]

        diag = cartera.get("diagnostico", {}) or {}
        lineas += [
            f"Exposición bruta **{cartera['exposicion_bruta_pct']:.2f}%** · "
            f"liquidez {cartera['liquidez_pct']:.2f}% · "
            f"riesgo agregado {cartera['riesgo_total_pct']:.2f}% "
            f"(presupuesto {RIESGO_TOTAL_CARTERA_PCT:.1%}) · "
            f"{diag.get('n_posiciones', 0)} posición(es), "
            f"{diag.get('posiciones_efectivas', SIN_DATO)} efectivas",
            "",
        ]

        if cartera.get("posiciones"):
            lineas += [
                "| Ticker | Sector | Estilo | Conv | Solicitado | Final | Riesgo | ρ media |",
                "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
            ]
            for p in cartera["posiciones"]:
                lineas.append(
                    f"| **{p['ticker']}** | {p['sector']} | `{p['estilo']}` "
                    f"| {p['conviccion'] if p['conviccion'] is not None else SIN_DATO} "
                    f"| {p['peso_solicitado_pct']:.2f}% | **{p['peso_final_pct']:.2f}%** "
                    f"| {p['riesgo_aportado_pct']:.2f}% "
                    f"| {p['correlacion_media'] if p['correlacion_media'] is not None else SIN_DATO} |")
            lineas.append("")
        else:
            lineas += ["_Ninguna posición supera los filtros; la cartera queda en liquidez._", ""]

        cuerpo: List[str] = []
        if cartera.get("por_sector_pct"):
            reparto = " · ".join(
                f"{s} {w:.1f}%" + ("⚠️" if w >= LIMITE_POR_SECTOR * 95 else "")
                for s, w in sorted(cartera["por_sector_pct"].items(),
                                   key=lambda x: -x[1]))
            cuerpo += [f"**Por sector** (límite {LIMITE_POR_SECTOR:.0%}): {reparto}", ""]
        if diag.get("nota_diversificacion"):
            cuerpo += [f"**Diversificación:** {diag['nota_diversificacion']}", ""]
        if diag.get("pares_muy_correlacionados"):
            cuerpo += ["**Pares muy correlacionados:** " + " · ".join(
                f"`{par['par']}` ρ={par['correlacion']}"
                for par in diag["pares_muy_correlacionados"]), ""]
        if cartera.get("restricciones_activadas"):
            cuerpo += ["**Restricciones activadas:**", ""] + \
                      [f"- {r}" for r in cartera["restricciones_activadas"]] + [""]
        ajustes = [(p["ticker"], a) for p in cartera.get("posiciones", [])
                   for a in p.get("ajustes", [])]
        if ajustes:
            cuerpo += ["**Ajustes a los pesos:**", ""] + \
                      [f"- `{t}` — {a}" for t, a in ajustes] + [""]
        if cartera.get("excluidas"):
            cuerpo += ["**Candidatos sin asignación:**", ""] + [
                f"- `{e['ticker']}` ({e.get('rating', 'N/A')}) — {e['motivo']}"
                for e in cartera["excluidas"]] + [""]

        lineas += _detalles("Restricciones, ajustes y diversificación", cuerpo)
        return lineas

    # ================================================================== #
    # Ficha por compañía
    # ================================================================== #
    def _ficha(self, res: Dict[str, Any], con_titulo: bool = True) -> List[str]:
        """
        Un valor entero en una tabla de bloques, con el pormenor plegado.

        La versión anterior imprimía seis secciones de prosa por valor. Aquí cada
        bloque es UNA fila con su veredicto y sus cifras; lo que antes era el
        cuerpo de la sección vive en los `<details>` de más abajo.
        """
        ticker = res.get("ticker", "?")
        q = res.get("quality_report", {}) or {}
        f = res.get("fundamental_report", {}) or {}
        t = res.get("technical_report", {}) or {}
        e = res.get("estructura_report", {}) or {}
        p = res.get("positioning_report", {}) or {}
        g = res.get("regimen_report", {}) or {}
        n = res.get("news_report", {}) or {}
        d = res.get("debate_report", {}) or {}
        fd = res.get("final_decision", {}) or {}
        rec = res.get("reconciliation_data", {}) or {}

        lineas: List[str] = []
        if con_titulo:
            lineas += [f"### {ticker} — {res.get('company_name', ticker)}", ""]

        lineas += [
            f"{res.get('sector', SIN_DATO)} / {res.get('industry', SIN_DATO)} · "
            f"confianza en datos {_p(rec.get('confidence_score'), '{:.0%}')} · "
            f"fuentes: {', '.join(rec.get('sources_consulted', [])) or SIN_DATO}",
            "",
            self._linea_dictamen(fd, p),
            "",
            "| Bloque | Veredicto | Claves |",
            "| :--- | :--- | :--- |",
        ]
        lineas.append(self._fila_gatekeeper(f))
        lineas.append(self._fila_calidad(q))
        if g:
            lineas.append(self._fila_regimen(g))
        if t:
            lineas.append(self._fila_tecnico(t))
        if e:
            lineas.append(self._fila_estructura(e))
        if p:
            lineas.append(self._fila_posicionamiento(p))
        if n:
            lineas.append(self._fila_noticias(n))
        if d:
            lineas.append(self._fila_debate(d))
        lineas.append("")

        if q.get("banderas_rojas"):
            lineas += ["🚩 " + " · ".join(q["banderas_rojas"]), ""]

        lineas += _detalles("Calidad y valoración — las siete escuelas",
                            self._detalle_calidad(q))
        if t:
            lineas += _detalles("Análisis técnico", self._detalle_tecnico(t))
        if e:
            lineas += _detalles("Estructura de precio y soportes",
                                self._detalle_estructura(e))
        if g:
            lineas += _detalles("Régimen de volatilidad del mercado",
                                self._detalle_regimen(g))
        if p:
            lineas += _detalles("Posicionamiento en derivados y precio de entrada",
                                self._detalle_posicionamiento(p))
        if n:
            lineas += _detalles("Noticias (capa asesora)", self._detalle_noticias(n))
        if d:
            lineas += _detalles("Debate y condiciones de invalidación",
                                self._detalle_debate(d))
        lineas += _detalles("Cómo se llegó al dictamen y al tamaño",
                            self._detalle_dictamen(fd))

        lineas += [f"**Lectura:** {_texto(fd.get('summary'))}", "", "---", ""]
        return lineas

    # ---------------------------------------------------------------- #
    @staticmethod
    def _linea_dictamen(fd: Dict[str, Any], p: Dict[str, Any]) -> str:
        """Titular del valor: la decisión y los cuatro números que la ejecutan."""
        if not fd:
            return "_Sin dictamen._"
        riesgo = fd.get("perfil_riesgo", {}) or {}
        partes = [f"### 🎯 `{fd.get('rating', SIN_DATO)}` · "
                  f"peso {_p(fd.get('peso_objetivo'), '{:.2%}')}"]
        if fd.get("stop_loss_atr") is not None:
            entrada = fd.get("precio_entrada")
            mercado = fd.get("current_price")
            texto_entrada = _p(mercado, "${:,.2f}")
            if entrada is not None and mercado is not None and entrada != mercado:
                texto_entrada = (f"{_p(entrada, '${:,.2f}')} "
                                 f"({_p(p.get('ajuste_entrada_pct'), '{:+.2%}')} "
                                 f"sobre {_p(mercado, '${:,.2f}')})")
            partes.append(
                f"entrada {texto_entrada} · stop {_p(fd.get('stop_loss_atr'), '${:,.2f}')} "
                f"({fd.get('multiplo_stop')}·ATR) · objetivo "
                f"{_p(fd.get('take_profit_atr'), '${:,.2f}')} ({fd.get('multiplo_objetivo')}·ATR) "
                f"· R:R {riesgo.get('ratio_riesgo_recompensa', SIN_DATO)} "
                f"· {fd.get('horizonte_dias', SIN_DATO)} sesiones")
        return "\n".join(partes)

    @staticmethod
    def _fila_gatekeeper(f: Dict[str, Any]) -> str:
        estado = f.get("status", SIN_DATO)
        icono = {"APROBADO": "✅", "RECHAZADO": "❌",
                 "DATOS_INSUFICIENTES": "⚠️"}.get(estado, "?")
        claves = "; ".join(
            f"{c['criterio']} {_p(c.get('valor'), '{:.2f}x' if 'Deuda' in c['criterio'] else '{:.1%}')}"
            f"{'' if c.get('exento') else ' vs ' + _p(c.get('umbral'), '{:.2f}x' if 'Deuda' in c['criterio'] else '{:.1%}')}"
            f" {_si_no(None if c.get('exento') else c.get('cumple'))}"
            for c in f.get("criterios", [])[:3]) or "; ".join(f.get("reasons", [])[:2])
        if f.get("magnitudes_ausentes"):
            claves += f" · ausentes: {', '.join(f['magnitudes_ausentes'])}"
        return f"| Filtro fundamental | {icono} {estado} | {claves or '—'} |"

    @staticmethod
    def _fila_calidad(q: Dict[str, Any]) -> str:
        if not q:
            return "| Calidad y valoración | — | — |"
        pt = q.get("puntuaciones", {}) or {}
        conv = (q.get("conviccion_fundamental") or {}).get("valor")
        pio = q.get("piotroski", {}) or {}
        alt = q.get("altman", {}) or {}
        return (f"| Calidad y valoración | `{q.get('style_classification', SIN_DATO)}` · "
                f"convicción **{_p(conv, '{:.0f}')}**/100 "
                f"| calidad {_p(pt.get('calidad'), '{:.0f}')} · "
                f"valoración {_p(pt.get('valoracion'), '{:.0f}')} · "
                f"crecimiento {_p(pt.get('crecimiento'), '{:.0f}')} · "
                f"solvencia {_p(pt.get('solvencia'), '{:.0f}')} · "
                f"F-Score {pio.get('score', SIN_DATO)}/{pio.get('criterios_evaluables', 9)} · "
                f"Altman {alt.get('z', SIN_DATO)} ({alt.get('zona', SIN_DATO)}) · "
                f"cobertura {_p(q.get('cobertura_global'), '{:.0%}')} |")

    @staticmethod
    def _fila_tecnico(t: Dict[str, Any]) -> str:
        aviso = " · ⚠️ sobreextendido" if t.get("sobreextendido") else ""
        return (f"| Técnico | `{t.get('momentum_classification', SIN_DATO)}` "
                f"{_p(t.get('momentum_score'), '{:+.1f}')}/100 "
                f"| RSI {_p(t.get('rsi'), '{:.1f}')} ({t.get('rsi_estado')}) · "
                f"tendencia {t.get('estado_tendencia')} · "
                f"ATR {_p(t.get('atr'), '${:,.2f}')} ({_p(t.get('atr_pct'))}) · "
                f"SMA200 {_p(t.get('dist_sma_200_pct'), '{:+.1%}')}{aviso} |")

    @staticmethod
    def _fila_posicionamiento(p: Dict[str, Any]) -> str:
        ajuste = p.get("ajuste_entrada_pct")
        veredicto = f"`{p.get('entrada_clasificacion', SIN_DATO)}`"
        if ajuste is not None:
            veredicto += f" {ajuste:+.2%}"
        claves = (f"macro {p.get('sesgo_macro_clasificacion')} "
                  f"({_p(p.get('sesgo_macro'), '{:+.2f}')}) · "
                  f"opciones {p.get('sesgo_opciones_clasificacion')} "
                  f"({_p(p.get('sesgo_opciones'), '{:+.2f}')}) · "
                  f"gamma {p.get('regimen_gamma')}")
        if p.get("nivel_referencia") is not None:
            claves += (f" · nivel {p.get('nivel_origen')} "
                       f"{_p(p.get('nivel_referencia'), '${:,.2f}')}")
        elif p.get("motivo_entrada"):
            claves += f" · {p['motivo_entrada']}"
        return f"| Posicionamiento | {veredicto} | {claves} |"

    @staticmethod
    def _fila_estructura(e: Dict[str, Any]) -> str:
        veredicto = f"`{e.get('estructura', SIN_DATO)}`"
        if e.get("soporte_lejano"):
            veredicto += " 🚫"
        claves = (f"soporte {e.get('soporte_origen', SIN_DATO)} "
                  f"{_p(e.get('soporte'), '${:,.2f}')} · "
                  f"a {_p(e.get('distancia_pct'))} "
                  f"({_p(e.get('distancia_atr'), '{:.2f}')} ATR)")
        if e.get("resistencia") is not None:
            claves += f" · primera referencia arriba {_p(e['resistencia'], '${:,.2f}')}"
        if e.get("soporte") is None and e.get("motivo"):
            claves = e["motivo"]
        return f"| Estructura | {veredicto} | {claves} |"

    @staticmethod
    def _fila_regimen(g: Dict[str, Any]) -> str:
        veredicto = f"`{g.get('regimen_clasificacion', SIN_DATO)}`"
        if not g.get("puerta_regimen", True):
            veredicto += " 🚫"
        claves = (f"{g.get('serie_volatilidad', 'VIX')} "
                  f"{_p(g.get('nivel_volatilidad'), '{:.2f}')} · "
                  f"z {_p(g.get('zscore_volatilidad'), '{:+.2f}')} · "
                  f"curva {_p(g.get('ratio_curva'), '{:.3f}')}")
        if g.get("curva_invertida"):
            claves += " (INVERTIDA)"
        if g.get("volatilidad_relativa") is not None:
            claves += f" · el valor se mueve {g['volatilidad_relativa']:.2f}x el mercado"
        if g.get("nivel_volatilidad") is None and g.get("motivo"):
            claves = g["motivo"]
        return f"| Régimen | {veredicto} | {claves} |"

    @staticmethod
    def _detalle_estructura(e: Dict[str, Any]) -> List[str]:
        filas = ["| Candidato | Nivel |", "| :--- | ---: |"]
        for c in (e.get("candidatos_por_debajo") or [])[:6]:
            filas.append(f"| {c.get('origen')} | {_p(c.get('nivel'), '${:,.2f}')} |")
        if len(filas) == 2:
            filas = ["_Ningún soporte estructural por debajo del precio._"]
        return (filas + ["", *[f"- {s}" for s in (e.get("signals") or [])], "",
                         f"**Lectura:** {_texto(e.get('summary'))}"])

    @staticmethod
    def _detalle_regimen(g: Dict[str, Any]) -> List[str]:
        return ([f"- {s}" for s in (g.get("signals") or [])]
                + ["",
                   f"Ventana del z-score: {g.get('ventana_zscore')} sesiones sobre "
                   f"{g.get('n_observaciones')} observación(es) publicadas"
                   + (f" hasta {g['as_of']}" if g.get("as_of") else "") + ".",
                   "",
                   "El régimen describe el MERCADO, no la empresa, y solo puede "
                   "RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en "
                   "COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún "
                   "régimen mejora un dictamen.",
                   "",
                   f"**Lectura:** {_texto(g.get('summary'))}"])

    @staticmethod
    def _fila_noticias(n: Dict[str, Any]) -> str:
        return (f"| Noticias _(asesora)_ | `{n.get('impact_classification', SIN_DATO)}` "
                f"{_p(n.get('impact_probability'), '{:.2f}')} · "
                f"{n.get('direction_classification', SIN_DATO)} "
                f"| {n.get('n_items', 0)} nota(s) en {n.get('window_days', 0)} días · "
                f"fuentes: {', '.join(n.get('sources_ok', [])) or 'ninguna'} |")

    @staticmethod
    def _fila_debate(d: Dict[str, Any]) -> str:
        return (f"| Debate | 🐂 {d.get('n_alcistas', 0)} vs 🐻 {d.get('n_bajistas', 0)} "
                f"| {_texto(d.get('synthesis'))[:220]} |")

    # ---------------------------------------------------------------- #
    # Bloques plegados
    # ---------------------------------------------------------------- #
    def _detalle_calidad(self, q: Dict[str, Any]) -> List[str]:
        if not q:
            return []
        pio = q.get("piotroski", {}) or {}
        alt = q.get("altman", {}) or {}
        gra = q.get("graham", {}) or {}
        gre = q.get("greenblatt", {}) or {}
        buf = q.get("buffett", {}) or {}
        lyn = q.get("lynch", {}) or {}
        dev = q.get("devengos", {}) or {}
        conv = q.get("conviccion_fundamental", {}) or {}

        lineas = [
            "| Escuela | Métrica | Valor | Lectura |",
            "| :--- | :--- | ---: | :--- |",
            f"| Piotroski | F-Score | {pio.get('score', SIN_DATO)}/{pio.get('criterios_evaluables', 9)} "
            f"| {pio.get('lectura', SIN_DATO)} |",
            f"| Altman | {alt.get('variante', 'Z')} | {alt.get('z', SIN_DATO)} "
            f"| {alt.get('zona', SIN_DATO)} (seguro > {alt.get('umbral_seguro')}, "
            f"insolvencia < {alt.get('umbral_distress')}) |",
            f"| Graham | Nº de Graham | {_p(gra.get('numero_graham'), '${:,.2f}')} "
            f"| margen {_p(gra.get('margen_seguridad'))} · "
            f"{gra.get('criterios_cumplidos', 0)}/{gra.get('criterios_evaluables', 0)} defensivos |",
            f"| Greenblatt | EBIT/EV | {_p(gre.get('earnings_yield'))} "
            f"| {'atractivo' if gre.get('ey_atractivo') else 'bajo umbral' if gre.get('ey_atractivo') is not None else SIN_DATO} |",
            f"| Buffett | ROIC | {_p(buf.get('roic'))} "
            f"| {_p(buf.get('roic_menos_wacc'), '{:+.1%}')} sobre el coste de capital |",
            f"| Buffett | Margen bruto | {_p(buf.get('margen_bruto'))} "
            f"| {'indicio de foso' if buf.get('indicio_de_foso') else 'sin foso' if buf.get('indicio_de_foso') is not None else SIN_DATO} · "
            f"FCF yield {_p(buf.get('fcf_yield'))} · dilución {_p(buf.get('dilucion_anual'), '{:+.2%}')} |",
            f"| Lynch | PEG | {lyn.get('peg', SIN_DATO)} "
            f"| {lyn.get('lectura_peg', SIN_DATO)} · {lyn.get('categoria_lynch', SIN_DATO)} "
            f"(sobre {lyn.get('base_del_crecimiento', SIN_DATO)}) |",
            f"| Sloan | Devengos | {_p(dev.get('ratio_devengos'))} | {dev.get('lectura', SIN_DATO)} |",
            "",
            f"**Estilo `{q.get('style_classification')}`** — {q.get('style_rationale', '')}",
            "",
        ]
        if conv.get("valor") is not None:
            lineas += [
                f"_Convicción: bruta {conv.get('bruta')} × cobertura {conv.get('factor_cobertura')} "
                f"× confianza {conv.get('factor_confianza')} − {conv.get('descuento_banderas')} "
                f"por banderas = **{conv.get('valor')}**._", ""]

        ctx = q.get("contexto_sectorial", {}) or {}
        if ctx.get("comparaciones"):
            nombres = {"pe": "P/E", "margen_neto": "Margen neto",
                       "deuda_patrimonio": "Deuda/Patrimonio",
                       "crecimiento_ingresos": "Crecimiento"}
            lineas += [f"**Contexto sectorial ({ctx.get('sector')})**", "",
                       "| Métrica | Valor | Mediana sector | Ratio | Lectura |",
                       "| :--- | ---: | ---: | ---: | :--- |"]
            for clave, comp in ctx["comparaciones"].items():
                fmt = "{:.1f}x" if clave in ("pe", "deuda_patrimonio") else "{:.1%}"
                lineas.append(
                    f"| {nombres.get(clave, clave)} | {_p(comp.get('valor'), fmt)} "
                    f"| {_p(comp.get('referencia_sector'), fmt)} | {comp.get('ratio', SIN_DATO)} "
                    f"| {comp.get('lectura')} |")
            lineas += ["", f"> {ctx.get('advertencia', '')}", ""]

        if pio.get("detalle"):
            lineas += ["**Desglose del F-Score**", "",
                       "| Criterio | Cumple | Detalle |", "| :--- | :---: | :--- |"]
            lineas += [f"| {c['criterio']} | {_si_no(c.get('cumple'))} | {c.get('detalle', '')} |"
                       for c in pio["detalle"]]
            lineas.append("")
        return lineas

    @staticmethod
    def _detalle_tecnico(t: Dict[str, Any]) -> List[str]:
        lineas = []
        if t.get("contribuciones"):
            aportes = " · ".join(f"{k.replace('_', ' ')} {v:+.1f}"
                                 for k, v in t["contribuciones"].items())
            lineas += [f"**Aportes a la puntuación:** {aportes} → "
                       f"**{_p(t.get('momentum_score'), '{:+.2f}')}**", ""]
        lineas += [
            f"SMA50 {_p(t.get('dist_sma_50_pct'), '{:+.1%}')} · "
            f"SMA200 {_p(t.get('dist_sma_200_pct'), '{:+.1%}')} · "
            f"rango 52s {_p(t.get('posicion_rango_52w'), '{:.0%}')} · "
            f"volatilidad anual {_p(t.get('volatilidad_anual'))}"
            + (f" · momentum relativo 12m {_p(t.get('momentum_relativo_12m'), '{:+.1%}')}"
               if t.get("momentum_relativo_12m") is not None else ""),
            "",
        ]
        if t.get("signals"):
            lineas += [f"- {s}" for s in t["signals"]] + [""]
        lineas += [f"**Lectura:** {_texto(t.get('summary'))}", ""]
        return lineas

    @staticmethod
    def _detalle_posicionamiento(p: Dict[str, Any]) -> List[str]:
        """
        Pormenor del bloque de derivados.

        Se imprimen las dos fechas del COT —informe y publicación— porque la
        distinción es la que hace honesta la señal: el informe del martes no es
        público hasta el viernes, y usar la primera fecha en un estudio
        histórico es la misma fuga que leer un cierre contable antes de su 10-K.
        """
        lineas: List[str] = []
        cot = p.get("cot", []) or []
        if cot:
            lineas += ["**Posicionamiento en futuros (COT de la CFTC, no comerciales)**", "",
                       "| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |",
                       "| :--- | :--- | ---: | ---: | :--- | :--- | :---: |"]
            for c in cot:
                lineas.append(
                    f"| `{c.get('contrato')}` | {c.get('papel')} "
                    f"| {_p(c.get('z'), '{:+.2f}')} | {c.get('n_semanas', 0)} "
                    f"| {c.get('ultima_fecha_informe') or SIN_DATO} "
                    f"| {c.get('ultima_fecha_publicacion') or SIN_DATO} "
                    f"| {'⚠️' if c.get('extremo') else '—'} |")
            lineas.append("")

        opc = p.get("opciones", {}) or {}
        if opc.get("disponible"):
            pcr = opc.get("put_call", {}) or {}
            skew = opc.get("skew", {}) or {}
            gam = opc.get("gamma", {}) or {}
            lineas += [
                "**Cadena de opciones**", "",
                f"Open interest agregado {opc.get('oi_total', 0):,} · "
                f"histórico acumulado {opc.get('n_dias_historico', 0)}/"
                f"{opc.get('minimo_dias_historico')} días",
                "",
                "| Métrica | Valor | Percentil | Estado |",
                "| :--- | ---: | ---: | :--- |",
                f"| Put/call (open interest) | {pcr.get('pcr_oi', SIN_DATO)} "
                f"| {_p(pcr.get('percentil_pcr'), '{:.0%}')} | {pcr.get('status', SIN_DATO)} |",
                f"| Put/call (volumen) | {pcr.get('pcr_volumen', SIN_DATO)} | — | — |",
                f"| Skew (IV put OTM − call OTM) | {skew.get('skew', SIN_DATO)} "
                f"| {_p(skew.get('percentil_skew'), '{:.0%}')} | {skew.get('status', SIN_DATO)} |",
                f"| Skew ÷ volatilidad ATM | {skew.get('skew_normalizado', SIN_DATO)} "
                f"| — | comparable sin histórico |",
                "",
                f"**Posición en el canal de open interest: "
                f"{_p(p.get('posicion_en_canal'), '{:.0%}')}** "
                + ("⚠️ en el techo: se compraría contra la oferta pendiente"
                   if p.get("en_techo_del_canal") else
                   "(0% = sobre el soporte, 100% = contra la resistencia)"),
                "",
                f"Niveles: soporte OI {_p(p.get('soporte_oi'), '${:,.2f}')} · "
                f"resistencia OI {_p(p.get('resistencia_oi'), '${:,.2f}')} · "
                f"max pain {_p(p.get('max_pain'), '${:,.2f}')} · "
                f"punto de inflexión de gamma {_p(p.get('gamma_flip'), '${:,.2f}')}",
                "",
                f"Régimen de gamma **{p.get('regimen_gamma')}** "
                f"(exposición {_p(p.get('gex_total'), '{:,.0f}')} $ por 1%). "
                f"_{gam.get('convencion', '')}_",
                "",
            ]
        else:
            lineas += [f"**Cadena de opciones no utilizable:** "
                       f"{opc.get('motivo', SIN_DATO)}", ""]

        sesgo_comp = ((opc.get("sesgo", {}) or {}).get("componentes")
                      if opc.get("disponible") else None)
        if sesgo_comp:
            lineas += ["**De dónde sale el sesgo de la cadena**", "",
                       "| Componente | Valor | Peso | Lectura |",
                       "| :--- | ---: | ---: | :--- |"]
            lineas += [f"| {c['componente']} | {c['valor']:+.2f} | {c['peso']} "
                       f"| {c.get('lectura', '')} |" for c in sesgo_comp]
            lineas += ["", "_Se promedian solo los componentes disponibles, con sus pesos "
                       "renormalizados. Todos se leen en clave contraria: este bloque puntúa "
                       "si el precio es un buen sitio para comprar, no si la tendencia sube._",
                       ""]

        det = p.get("detalle_entrada", {}) or {}
        comp = det.get("componentes", {}) or {}
        lineas += [
            "**Confluencia de tres vías**", "",
            f"macro {_p(comp.get('macro'), '{:+.2f}')} · "
            f"opciones {_p(comp.get('opciones'), '{:+.2f}')} · "
            f"técnico {_p(comp.get('tecnico'), '{:+.2f}')} → "
            f"media {_p(det.get('sesgo_medio'), '{:+.2f}')}, "
            f"confluencia {_p(p.get('confluencia'), '{:.0%}')} sobre "
            f"{len(p.get('componentes_disponibles', []))} componente(s) → "
            f"**{p.get('entrada_clasificacion')}**",
            "",
        ]
        if p.get("ajuste_entrada_pct") is not None:
            lineas += [
                f"Ajuste bruto hasta el nivel {_p(det.get('ajuste_bruto_pct'), '{:+.2%}')} × "
                f"factor {det.get('factor')} = **{_p(p.get('ajuste_entrada_pct'), '{:+.2%}')}**"
                + (", limitado por el tope de 1·ATR" if det.get("limitado_por_atr") else "")
                + f" → entrada objetivo {_p(p.get('precio_entrada_objetivo'), '${:,.2f}')}",
                "",
            ]
        else:
            lineas += [f"_Sin ajuste de entrada: {p.get('motivo_entrada')}. "
                       f"La entrada se toma al precio de mercado._", ""]
        lineas += [f"**Lectura:** {_texto(p.get('summary'))}", ""]
        return lineas

    @staticmethod
    def _detalle_noticias(n: Dict[str, Any]) -> List[str]:
        lineas = []
        if n.get("catalysts"):
            for c in n["catalysts"]:
                titular = f"[{c['titular']}]({c['url']})" if c.get("url") else c["titular"]
                lineas.append(f"- `{c.get('fecha') or 's/f'}` **{c['categoria']}** · "
                              f"{c['direccion']} · p={c['probabilidad_impacto']:.2f} · "
                              f"_{c.get('fuente', '')}_ — {titular}")
            lineas.append("")
        fallidas = ", ".join(f["buscador"] for f in n.get("sources_failed", []))
        if fallidas:
            lineas += [f"_Fuentes sin respuesta: {fallidas}._", ""]
        lineas += [f"**Lectura:** {_texto(n.get('summary'))}", ""]
        return lineas

    @staticmethod
    def _detalle_debate(d: Dict[str, Any]) -> List[str]:
        lineas = ["**🐂 Alcista**", ""]
        lineas += [f"- {a}" for a in d.get("argumentos_alcistas", [])] or ["- —"]
        lineas += ["", "**🐻 Bajista**", ""]
        lineas += [f"- {a}" for a in d.get("argumentos_bajistas", [])] or ["- —"]
        if d.get("invalidacion"):
            lineas += ["", "**Invalidarían la tesis:**", ""]
            lineas += [f"- {c}" for c in d["invalidacion"]]
        lineas += ["", f"**Síntesis:** {_texto(d.get('synthesis'))}", ""]
        return lineas

    @staticmethod
    def _detalle_dictamen(fd: Dict[str, Any]) -> List[str]:
        if not fd:
            return []
        des = fd.get("desglose_decision", {}) or {}
        dim = fd.get("dimensionado", {}) or {}
        riesgo = fd.get("perfil_riesgo", {}) or {}
        lineas: List[str] = []

        if des.get("puntuacion_compuesta") is not None:
            lineas += [
                f"Convicción **{des.get('conviccion_usada')}** × {des.get('peso_fundamental')} + "
                f"momentum normalizado **{des.get('momentum_normalizado')}** × "
                f"{des.get('peso_tecnico')} = **{des.get('puntuacion_compuesta')}**/100 → "
                f"**{des.get('rating_antes_de_vetos')}**"
                + (f" → tras vetos **{des.get('rating_final')}**"
                   if des.get("rating_antes_de_vetos") != des.get("rating_final") else ""),
                "",
            ]
        if fd.get("vetos_aplicados"):
            lineas += ["**Ajustes a la baja** (ninguna condición puede subir un rating):", ""]
            lineas += [f"- {v}" for v in fd["vetos_aplicados"]] + [""]

        # Memoria de reflexión. Se imprime aunque no recorte, porque «no había
        # muestra» y «la había y no penalizó» son dos lecturas distintas y el
        # lector no puede deducir cuál es a partir de un peso sin anotar.
        refl = fd.get("reflexion") or {}
        if refl.get("motivo"):
            estado = (f"factor ×{refl.get('factor'):.2f}" if refl.get("factor", 1.0) < 1.0
                      else "sin recorte")
            lineas += [f"**Memoria de reflexión** ({estado}): {refl['motivo']}", ""]

        if dim.get("factores"):
            fac = dim["factores"]
            lineas += [
                "`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`",
                "",
                f"convicción ×{fac.get('escala_conviccion', SIN_DATO)} · "
                f"riesgo {fac.get('riesgo_asumible_pct', SIN_DATO)}% · "
                f"stop a {_p(fac.get('distancia_stop_pct'))} → "
                f"{_p(fac.get('peso_por_riesgo'), '{:.2%}')} · "
                f"volatilidad ×{fac.get('factor_volatilidad', SIN_DATO)} · "
                f"datos ×{fac.get('factor_confianza_datos', SIN_DATO)} · "
                f"banderas ×{fac.get('factor_banderas_rojas', SIN_DATO)} · "
                f"extensión ×{fac.get('factor_sobreextension', SIN_DATO)} → "
                f"**{dim.get('display', SIN_DATO)}**",
                "",
                f"_{dim.get('motivo', '')}_", "",
            ]
        elif dim.get("motivo"):
            lineas += [f"_Sin asignación: {dim['motivo']}._", ""]

        if riesgo:
            lineas += [
                f"R:R {riesgo.get('ratio_riesgo_recompensa')} → exige acertar el "
                f"**{_p(riesgo.get('tasa_acierto_equilibrio'))}** de las veces para no perder "
                f"dinero. Horizonte {riesgo.get('horizonte_dias')} sesiones "
                f"(~{riesgo.get('horizonte_meses')} meses); a su ATR actual el precio "
                f"necesita al menos {riesgo.get('sesiones_minimas_al_objetivo')} sesiones de "
                f"avance direccional puro para alcanzar el objetivo.",
                "",
            ]
        if fd.get("rationale"):
            lineas += [f"_{_texto(fd['rationale'])}_", ""]
        return lineas

    # ================================================================== #
    # Traza y registro
    # ================================================================== #
    def _traza_de_agentes(self, res: Dict[str, Any]) -> List[str]:
        """Qué herramienta se invocó, con qué argumentos y qué devolvió."""
        bloques = [
            ("Calidad", res.get("quality_report")),
            ("Gatekeeper", res.get("fundamental_report")),
            ("Noticias", res.get("news_report")),
            ("Régimen", res.get("regimen_report")),
            ("Técnico", res.get("technical_report")),
            ("Estructura", res.get("estructura_report")),
            ("Posicionamiento", res.get("positioning_report")),
            ("Debate", res.get("debate_report")),
            ("Fund Manager", res.get("final_decision")),
        ]
        con_traza = [(nombre, inf) for nombre, inf in bloques
                     if isinstance(inf, dict) and inf.get("_traza")]
        if not con_traza:
            return []

        filas: List[str] = []
        for nombre, informe in con_traza:
            traza = informe["_traza"]
            for i, t in enumerate(traza["tools"], 1):
                args = ", ".join(f"{k}={v}" for k, v in
                                 list(t.get("argumentos", {}).items())[:3]) or "—"
                if t.get("error"):
                    resultado = f"⚠️ {t['error']}"
                else:
                    r = t.get("resultado")
                    resultado = (f"{r['n_claves']} campos" if isinstance(r, dict) and "n_claves" in r
                                 else f"{r['n_elementos']} elementos"
                                 if isinstance(r, dict) and "n_elementos" in r else _texto(r))
                filas.append(f"| {nombre} | {i} | `{t['tool']}` | {args[:90]} | {resultado} |")

        return ["## Traza de herramientas", "",
                "Cada fila es una llamada real al registro de `src/tools/`. En el Analista de "
                "Calidad, en el de Posicionamiento y en el Fund Manager el orden no es "
                "intercambiable: cada paso consume la salida del anterior.", "",
                "| Agente | # | Herramienta | Argumentos | Resultado |",
                "| :--- | ---: | :--- | :--- | :--- |"] + filas + [""]

    @staticmethod
    def _registro_de_ejecucion(res: Dict[str, Any]) -> List[str]:
        logs = res.get("logs") or []
        if not logs:
            return []
        return (["## Registro de ejecución", "",
                 "_La traza completa con tiempos por herramienta está en `output/logs/`._",
                 "", "```"] + list(logs) + ["```", ""])

    # ================================================================== #
    # Calidad de datos, limitaciones y anexo
    # ================================================================== #
    def _calidad_de_datos(self, results: List[Dict[str, Any]]) -> List[str]:
        lineas = [
            "## Calidad de los datos", "",
            "La ausencia de un dato se propaga a la convicción y, por esa vía, al tamaño de "
            "la posición. Por eso se declara.", "",
            "| Ticker | Confianza | Fuentes | Cobertura | Ausentes | Discrep. | Opciones |",
            "| :--- | ---: | :--- | ---: | :--- | ---: | :--- |",
        ]
        for res in results:
            rec = res.get("reconciliation_data", {}) or {}
            q = res.get("quality_report", {}) or {}
            opt = res.get("options_data", {}) or {}
            ausentes = (rec.get("cobertura", {}) or {}).get("campos_ausentes", [])
            estado_opc = (f"{opt.get('n_dias_historico', 0)}d hist." if opt.get("disponible")
                          else "no disponible")
            lineas.append(
                f"| **{res.get('ticker')}** | {_p(rec.get('confidence_score'), '{:.0%}')} "
                f"| {', '.join(rec.get('sources_consulted', []))} "
                f"| {_p(q.get('cobertura_global'), '{:.0%}')} "
                f"| {', '.join(ausentes) if ausentes else '—'} "
                f"| {len(rec.get('discrepancies', []))} | {estado_opc} |")
        lineas.append("")

        cuerpo = []
        for res in results:
            rec = res.get("reconciliation_data", {}) or {}
            for disc in rec.get("discrepancies", []):
                cuerpo.append(f"- `{res.get('ticker')}` — {disc.get('texto')}")
            proc = rec.get("procedencia", {}) or {}
            fuentes = {k: v.get("fuente_elegida") for k, v in proc.items()
                       if v.get("fuente_elegida")}
            if fuentes:
                cuerpo.append(f"- `{res.get('ticker')}` procedencia: " +
                              ", ".join(f"{k} ← {v}" for k, v in fuentes.items()))
        lineas += _detalles("Discrepancias y procedencia de cada magnitud", cuerpo)
        return lineas

    def _limitaciones(self) -> List[str]:
        return ["## Track record y limitaciones", ""] + self._track_record() + [
            "**Limitaciones vigentes**", "",
            "- **Universo con sesgo de supervivencia:** solo se analizan valores que existen hoy.",
            "- **El ajuste de precio de entrada no está backtesteado.** Su nivel sale solo de la "
            "cadena de opciones, y el histórico de open interest y volatilidad implícita es de "
            "pago. El backtest mide el sistema *sin* ajuste de entrada, mientras producción sí "
            "lo aplica. Del bloque de posicionamiento solo se mide el veto macro, que sí es "
            "point-in-time.",
            "- **El signo de la exposición gamma es una convención**, no una medición: la cadena "
            "publica open interest, no quién está en cada lado de cada contrato.",
            "- **Percentiles de put/call y skew** necesitan histórico acumulado propio; hasta "
            "reunirlo se declaran DATOS_INSUFICIENTES en vez de asumir el percentil 50.",
            "- **Normas sectoriales estáticas y coste de capital constante:** ordenan y "
            "contextualizan, no valoran.",
            "- **Sin datos intradía:** la ejecución se modela al cierre y la apertura siguiente.",
            "- **Riesgo legal y regulatorio fuera de la decisión:** aparece en la capa de "
            "noticias pero no toca el tamaño. Debe activar revisión manual.",
            "",
        ]

    @staticmethod
    def _track_record() -> List[str]:
        """
        Track record leído de `output/backtest_results.json`.

        Se lee del fichero en lugar de escribirlo a mano por un motivo concreto:
        la versión anterior lo tenía embebido en el código y quedó obsoleta en
        cuanto el backtest se volvió a ejecutar. Un informe que declara un
        historial desactualizado es peor que uno que no lo declara, porque
        parece verificado.
        """
        ruta = os.path.join(OUTPUT_DIR, "backtest_results.json")
        if not os.path.exists(ruta):
            return ["**Sin backtest disponible.** No existe `output/backtest_results.json`. "
                    "Ejecuta `backtest_cli.py --regime pit` antes de dar peso a las "
                    "recomendaciones: un sistema de selección sin track record es una "
                    "hipótesis, no una estrategia.", ""]
        try:
            with open(ruta, encoding="utf-8") as f:
                bt = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return [f"**Backtest ilegible** (`{ruta}`): {e}.", ""]

        est = bt.get("strategy", {}) or {}
        spy = bt.get("spy", {}) or {}
        aleatorio = bt.get("random_test", {}) or {}
        bate = (est.get("cagr", 0.0) - spy.get("cagr", 0.0)) > 0

        lineas = [
            ("**El sistema bate a comprar y mantener el índice** en el histórico simulado."
             if bate else "**El sistema NO bate a comprar y mantener el índice.**")
            + f" Régimen `{bt.get('regime', '?')}`, {est.get('start', '?')} → "
              f"{est.get('end', '?')} (`output/backtest_report.md`).",
            "",
            "| | CAGR | Volatilidad | Sharpe | Sortino | Máx. drawdown |",
            "| :--- | ---: | ---: | ---: | ---: | ---: |",
            f"| Estrategia | {_p(est.get('cagr'))} | {_p(est.get('volatility'))} "
            f"| {_p(est.get('sharpe'), '{:.2f}')} | {_p(est.get('sortino'), '{:.2f}')} "
            f"| {_p(est.get('max_drawdown'))} |",
            f"| SPY | {_p(spy.get('cagr'))} | {_p(spy.get('volatility'))} "
            f"| {_p(spy.get('sharpe'), '{:.2f}')} | {_p(spy.get('sortino'), '{:.2f}')} "
            f"| {_p(spy.get('max_drawdown'))} |",
            "",
        ]

        pct = aleatorio.get("percentil_vs_aleatorio")
        if pct is not None:
            lineas += [
                f"Frente a selección aleatoria con el mismo perfil de exposición: **percentil "
                f"{pct:.1f}**"
                + (", por encima de la mediana." if pct >= 50 else
                   ", **por debajo** de la mediana — la selección de valores todavía no aporta."),
                "",
            ]
        if est.get("volatility") and spy.get("volatility") and \
                est["volatility"] < spy["volatility"] * 0.6:
            lineas += [
                f"> El CAGR no es comparable directamente: la estrategia opera al "
                f"{est['volatility']:.1%} de volatilidad frente al {spy['volatility']:.1%} del "
                f"índice, porque el presupuesto de riesgo la mantiene poco invertida. Sharpe y "
                f"Sortino son la comparación pertinente.",
                "",
            ]
        return lineas

    def _anexo(self, results: List[Dict[str, Any]]) -> List[str]:
        """
        Definiciones y umbrales, UNA sola vez.

        Antes cada ficha repetía la explicación de su bloque. Con veinte valores
        analizados eso son veinte copias del mismo párrafo, que es ruido: lo que
        cambia entre valores son las cifras, no el método.
        """
        estilos = sorted({(r.get("quality_report", {}) or {}).get("style_classification")
                          for r in results} - {None})
        entradas = sorted({(r.get("positioning_report", {}) or {}).get("entrada_clasificacion")
                           for r in results} - {None})

        lineas = ["## Anexo metodológico", "", "**Umbrales y política de riesgo**", "",
                  f"- Filtro fundamental: margen neto ≥ {MIN_NET_MARGIN:.1%} · crecimiento ≥ "
                  f"{MIN_REVENUE_GROWTH:.1%} · deuda/patrimonio ≤ {MAX_DEBT_TO_EQUITY:.2f}x "
                  f"(al alza en financieras, inmobiliario y utilities, donde el apalancamiento "
                  f"es estructural).",
                  f"- Riesgo por posición {RIESGO_POR_POSICION_PCT:.2%} al stop · agregado "
                  f"{RIESGO_TOTAL_CARTERA_PCT:.1%} · peso máximo {PESO_MAXIMO_POSICION:.0%} · "
                  f"límite sectorial {LIMITE_POR_SECTOR:.0%} · exposición bruta máxima "
                  f"{EXPOSICION_BRUTA_MAXIMA:.0%} · volatilidad objetivo "
                  f"{VOLATILIDAD_OBJETIVO:.0%}.",
                  ""]

        if estilos:
            lineas += ["**Estilos presentes en este informe**", ""]
            lineas += [f"- `{e}` — {GLOSARIO_ESTILOS.get(e, '—')}" for e in estilos]
            lineas += ["", "El estilo no es descriptivo: fija los múltiplos de ATR del stop y "
                       "del objetivo, el horizonte, y habilita vetos. TRAMPA_DE_VALOR y "
                       "ESPECULATIVA no pueden superar MANTENER.", ""]

        if entradas:
            lineas += ["**Decisiones de entrada presentes**", ""]
            lineas += [f"- `{e}` — {GLOSARIO_ENTRADA.get(e, '—')}" for e in entradas]
            lineas += ["", ""]

        lineas += [
            "**Cómo se decide el precio de entrada**", "",
            "El Analista de Posicionamiento cruza tres señales: el posicionamiento de los "
            "especuladores en futuros (informes COT de la CFTC, en z-score frente a su propio "
            "histórico y normalizado por interés abierto), el de la cadena de opciones del "
            "propio valor (put/call ratio y skew en percentil histórico, más el punto de "
            "inflexión de la exposición gamma) y el momentum del Analista Técnico. El bloque "
            "macro da dirección; solo la cadena de opciones da un nivel de precio concreto. Si "
            "las tres confirman, se entra a mercado; si divergen, se exige el retroceso. El "
            "ajuste **solo puede bajar** el precio de entrada, nunca subirlo, y está acotado a "
            "un ATR para que la entrada objetivo nunca quede por debajo del propio stop.",
            "",
            "**Origen de las reglas de calidad y valoración**", "",
            "Piotroski (1998, F-Score) · Altman (1968, Z-Score, variante Z'' para no "
            "manufactureras) · Graham (1949, número de Graham y criterios defensivos) · Buffett "
            "(ROIC sobre coste de capital, margen bruto como foso, beneficio del propietario) · "
            "Lynch (1989, PEG y taxonomía) · Greenblatt (2005, EBIT/EV y rentabilidad del "
            "capital tangible) · Sloan (1996, ratio de devengos).",
            "",
            "**Papel del modelo de lenguaje**", "",
            "Ninguna variable de decisión depende del LLM. Rating, tamaño, stop, objetivo, "
            "estilo y precio de entrada salen de reglas deterministas; el modelo solo puede "
            "sobrescribir los campos de texto, y siempre después de que todo esté fijado. Sin "
            "clave de API el sistema produce exactamente los mismos dictámenes, y esa propiedad "
            "se verifica en ejecución con `assert_llm_is_decision_neutral()`.",
            "",
        ]
        return lineas
