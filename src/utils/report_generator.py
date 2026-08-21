"""
Generador del informe de inversión.

El informe anterior era una lista de fichas independientes: cada valor tenía su
gatekeeper, su momentum y su dictamen, y nada más. Faltaba todo lo que
convierte un conjunto de opiniones en una recomendación defendible — el punto
de comparación de cada múltiplo, el horizonte de los niveles de riesgo, la
correlación entre las posiciones, la exposición total, el historial de la
estrategia y las condiciones que invalidarían cada tesis.

Estructura actual:

  1. Resumen ejecutivo y cartera propuesta (la decisión agregada primero).
  2. Reparto por estilo de inversión.
  3. Ficha completa por compañía, con la trazabilidad de cada número.
  4. Calidad de los datos, limitaciones y track record.
  5. Anexo metodológico con los umbrales aplicados.

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

# Glosario de las etiquetas de estilo. Se imprime en el informe porque una
# etiqueta sin definición es una etiqueta que cada lector interpreta a su modo.
GLOSARIO_ESTILOS = {
    "CALIDAD_COMPUESTA": (
        "Negocio capaz de reinvertir beneficios por encima de su coste de capital durante años. "
        "Es la categoría que persigue Buffett: se paga un múltiplo razonable por una tasa de "
        "retorno sostenible, no un múltiplo bajo por un activo estancado."),
    "CALIDAD_DETERIORADA": (
        "Negocio rentable con varios defectos estructurales a la vez (caja, devengos, dilución "
        "o balance). La calidad operativa no compensa por sí sola un balance deteriorado: la "
        "tesis depende de que esos defectos se corrijan, y eso exige revisarla antes."),
    "VALOR": (
        "Cotiza con descuento sobre su valor intrínseco conservador manteniendo calidad "
        "suficiente. La escuela de Graham: el margen de seguridad está en el precio pagado."),
    "GARP": (
        "Crecimiento a precio razonable. La categoría de Lynch: el PEG confirma que el múltiplo "
        "no se ha adelantado al crecimiento que lo justifica."),
    "CRECIMIENTO": (
        "La tesis depende de que el crecimiento se mantenga. El múltiplo no ofrece margen de "
        "error: una decepción en la ejecución se paga con una recalificación completa."),
    "CICLICA": (
        "El múltiplo depende de la fase del ciclo, no del negocio. Cuidado con el P/E bajo en "
        "máximos de beneficio: en cíclicas suele señalar techo, no ganga."),
    "TRAMPA_DE_VALOR": (
        "Barato con calidad deteriorada. El descuento parece justificado por el deterioro del "
        "negocio y no una oportunidad; es el error clásico del inversor en valor."),
    "ESPECULATIVA": (
        "El perfil de riesgo domina cualquier lectura de valor o crecimiento. Solvencia "
        "comprometida o varias banderas rojas simultáneas."),
    "MIXTA": "Sin dominancia clara de ninguna de las dimensiones.",
    "DATOS_INSUFICIENTES": (
        "Cobertura de datos por debajo del mínimo exigido para clasificar. No es un juicio "
        "sobre la empresa, sino sobre la información disponible."),
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


def _barra(valor: Optional[float], ancho: int = 20) -> str:
    """Barra de progreso ASCII para las puntuaciones de 0 a 100."""
    if valor is None:
        return "░" * ancho + f" {SIN_DATO}"
    llenos = int(round(ancho * max(0.0, min(100.0, valor)) / 100.0))
    return "█" * llenos + "░" * (ancho - llenos) + f" {valor:.0f}/100"


def _si_no(valor: Optional[bool]) -> str:
    if valor is None:
        return "—"
    return "✅" if valor else "❌"


class ReportGenerator:
    """Genera el informe de inversión en Markdown y su equivalente en JSON."""

    def generate_daily_selection(self, results: List[FinancialAnalysisState],
                                 cartera: Optional[Any] = None,
                                 benchmark: Optional[Dict[str, Any]] = None,
                                 filename: str = "daily_selection.md") -> str:
        filepath = os.path.join(OUTPUT_DIR, filename)
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cartera_dict = cartera.a_dict() if cartera is not None and hasattr(cartera, "a_dict") else None

        lineas: List[str] = []
        lineas += self._cabecera(ahora, results, benchmark)
        lineas += self._resumen_ejecutivo(results)
        lineas += self._cartera(cartera_dict)
        lineas += self._reparto_por_estilo(results)

        lineas += ["## 4. Fichas por compañía", ""]
        for res in results:
            lineas += self._ficha(res)

        lineas += self._calidad_de_datos(results)
        lineas += self._limitaciones()
        lineas += self._anexo_metodologico()

        contenido = "\n".join(lineas)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(contenido)

        json_path = os.path.join(OUTPUT_DIR, "daily_selection.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "generado": ahora,
                "benchmark": benchmark or {},
                "cartera": cartera_dict,
                "analisis": results,
            }, f, indent=2, ensure_ascii=False, default=str)

        print(f"[ReportGenerator] Informe generado en: {filepath}")
        return filepath

    # ================================================================== #
    def _cabecera(self, ahora: str, results: List[Dict[str, Any]],
                  benchmark: Optional[Dict[str, Any]]) -> List[str]:
        tickers = ", ".join(r.get("ticker", "?") for r in results)
        b = benchmark or {}
        ref = (f"{b.get('ticker')} · 12m {_p(b.get('change_12m_pct'))} · "
               f"3m {_p(b.get('change_3m_pct'))}") if b.get("ticker") else \
            "no disponible — el momentum se reporta en términos absolutos"
        return [
            "# Informe de Inversión — Selección Multi-Agente",
            "",
            f"**Fecha de análisis:** `{ahora}`  ",
            f"**Universo analizado:** {tickers} ({len(results)} valores)  ",
            f"**Referencia de mercado:** {ref}  ",
            f"**Capital de referencia:** ${CAPITAL_BASE:,.0f}",
            "",
            "> Este informe es el resultado de un sistema automatizado de análisis. Las "
            "recomendaciones se derivan de reglas deterministas y auditables; el modelo de "
            "lenguaje interviene únicamente en la redacción de los resúmenes, nunca en el "
            "cálculo de ratings, tamaños de posición ni niveles de riesgo. "
            "**No constituye asesoramiento de inversión.**",
            "",
            "---",
            "",
        ]

    # ================================================================== #
    def _resumen_ejecutivo(self, results: List[Dict[str, Any]]) -> List[str]:
        lineas = [
            "## 1. Resumen ejecutivo",
            "",
            "| Ticker | Empresa | Sector | Estilo | Convicción | Filtro | Momentum | Dictamen | Peso | Stop | Objetivo | R:R | Horizonte |",
            "| :--- | :--- | :--- | :--- | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for res in results:
            q = res.get("quality_report", {}) or {}
            t = res.get("technical_report", {}) or {}
            d = res.get("final_decision", {}) or {}
            f = res.get("fundamental_report", {}) or {}
            riesgo = d.get("perfil_riesgo", {}) or {}
            conv = (q.get("conviccion_fundamental") or {}).get("valor")

            estado = f.get("status", "N/A")
            filtro = {"APROBADO": "✅", "RECHAZADO": "❌",
                      "DATOS_INSUFICIENTES": "⚠️"}.get(estado, "?")
            mom = t.get("momentum_score")
            horizonte = d.get("horizonte_dias")

            lineas.append(
                f"| **{res.get('ticker', '?')}** "
                f"| {res.get('company_name', '')[:28]} "
                f"| {res.get('sector', SIN_DATO)} "
                f"| `{q.get('style_classification', SIN_DATO)}` "
                f"| {_p(conv, '{:.0f}') if conv is not None else SIN_DATO} "
                f"| {filtro} "
                f"| {f'{mom:+.0f}' if mom is not None else SIN_DATO} "
                f"| **{d.get('rating', SIN_DATO)}** "
                f"| {_p(d.get('peso_objetivo'), '{:.2%}')} "
                f"| {_p(d.get('stop_loss_atr'), '${:,.2f}')} "
                f"| {_p(d.get('take_profit_atr'), '${:,.2f}')} "
                f"| {_p(riesgo.get('ratio_riesgo_recompensa'), '{:.2f}')} "
                f"| {f'{horizonte}d' if horizonte else SIN_DATO} |"
            )

        lineas += [
            "",
            "**Cómo leer esta tabla.** La *convicción* (0-100) resume calidad, valoración, "
            "crecimiento y solvencia, ya descontada por la cobertura de datos. El *momentum* "
            "(−100 a +100) es la puntuación técnica continua. El *dictamen* sale de cruzar ambas "
            "y aplicar los vetos de riesgo. El *peso* es el resultado del presupuesto de riesgo, "
            "no un rango fijo: dos valores con el mismo dictamen pueden tener pesos muy distintos "
            "si su volatilidad o su distancia al stop difieren. *R:R* es el ratio "
            "riesgo/recompensa y el *horizonte* es el plazo al que aplican stop y objetivo.",
            "",
            "---",
            "",
        ]
        return lineas

    # ================================================================== #
    def _cartera(self, cartera: Optional[Dict[str, Any]]) -> List[str]:
        lineas = ["## 2. Cartera propuesta", ""]
        if not cartera:
            lineas += [
                "_No se construyó cartera agregada en esta ejecución._",
                "", "---", "",
            ]
            return lineas

        diag = cartera.get("diagnostico", {})
        lineas += [
            f"**Exposición bruta:** {cartera['exposicion_bruta_pct']:.2f}% · "
            f"**Liquidez:** {cartera['liquidez_pct']:.2f}% · "
            f"**Riesgo agregado si todos los stops saltan:** {cartera['riesgo_total_pct']:.2f}% "
            f"del patrimonio (presupuesto: {RIESGO_TOTAL_CARTERA_PCT:.1%})",
            "",
        ]

        if cartera.get("posiciones"):
            lineas += [
                "| Ticker | Sector | Estilo | Convicción | Peso solicitado | Peso final | Riesgo aportado | Correlación media |",
                "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |",
            ]
            for p in cartera["posiciones"]:
                lineas.append(
                    f"| **{p['ticker']}** | {p['sector']} | `{p['estilo']}` "
                    f"| {p['conviccion'] if p['conviccion'] is not None else SIN_DATO} "
                    f"| {p['peso_solicitado_pct']:.2f}% | **{p['peso_final_pct']:.2f}%** "
                    f"| {p['riesgo_aportado_pct']:.2f}% "
                    f"| {p['correlacion_media'] if p['correlacion_media'] is not None else SIN_DATO} |"
                )
            lineas.append("")

            ajustes = [(p["ticker"], a) for p in cartera["posiciones"] for a in p.get("ajustes", [])]
            if ajustes:
                lineas += ["**Ajustes aplicados a los pesos individuales:**", ""]
                lineas += [f"- `{t}` — {a}" for t, a in ajustes]
                lineas.append("")
        else:
            lineas += ["_Ninguna posición supera los filtros. La cartera permanece en liquidez._", ""]

        if cartera.get("por_sector_pct"):
            lineas += ["**Concentración por sector** "
                       f"(límite: {LIMITE_POR_SECTOR:.0%})", ""]
            for sector, peso in sorted(cartera["por_sector_pct"].items(),
                                       key=lambda x: x[1], reverse=True):
                alerta = " ⚠️" if peso >= LIMITE_POR_SECTOR * 100 * 0.95 else ""
                lineas.append(f"- {sector}: {peso:.2f}%{alerta}")
            lineas.append("")

        lineas += ["**Diagnóstico de diversificación**", ""]
        for etiqueta, clave, fmt in (
            ("Posiciones", "n_posiciones", "{}"),
            ("Posiciones efectivas (inverso de Herfindahl)", "posiciones_efectivas", "{}"),
            ("Volatilidad estimada de la cartera", "volatilidad_cartera_anual_pct", "{}%"),
            ("Suma ponderada de volatilidades", "volatilidad_suma_ponderada_pct", "{}%"),
            ("Ratio de diversificación", "ratio_diversificacion", "{}"),
        ):
            if diag.get(clave) is not None:
                lineas.append(f"- {etiqueta}: **{fmt.format(diag[clave])}**")
        if diag.get("nota_diversificacion"):
            lineas += ["", f"> {diag['nota_diversificacion']}"]
        if diag.get("pares_muy_correlacionados"):
            lineas += ["", "**Pares muy correlacionados** (no son apuestas independientes):", ""]
            for par in diag["pares_muy_correlacionados"]:
                lineas.append(f"- `{par['par']}`: ρ = {par['correlacion']}")
        lineas.append("")

        if diag.get("liquidez_pct", 0) > 0:
            lineas += [
                f"> **Sobre la liquidez.** El {diag['liquidez_pct']:.1f}% no invertido rinde un "
                f"{diag.get('rendimiento_liquidez_supuesto_pct', 0):.1f}% anual supuesto, lo que "
                f"aporta {diag.get('aportacion_liquidez_anual_pct', 0):.2f} puntos al resultado. "
                f"El backtest histórico documenta que ignorar este detalle —dejar el efectivo al "
                f"0%— hacía la comparación contra el índice más pesimista de lo debido.",
                "",
            ]

        if cartera.get("restricciones_activadas"):
            lineas += ["**Restricciones de cartera activadas:**", ""]
            lineas += [f"- {r}" for r in cartera["restricciones_activadas"]]
            lineas.append("")

        if cartera.get("excluidas"):
            lineas += ["**Candidatos sin asignación** (y por qué):", ""]
            for e in cartera["excluidas"]:
                lineas.append(f"- `{e['ticker']}` ({e.get('rating', 'N/A')}) — {e['motivo']}")
            lineas.append("")

        lineas += ["---", ""]
        return lineas

    # ================================================================== #
    def _reparto_por_estilo(self, results: List[Dict[str, Any]]) -> List[str]:
        conteo: Dict[str, List[str]] = {}
        for res in results:
            estilo = (res.get("quality_report", {}) or {}).get("style_classification", "n/d")
            conteo.setdefault(estilo, []).append(res.get("ticker", "?"))

        lineas = [
            "## 3. Reparto por estilo de inversión",
            "",
            "El estilo no es una etiqueta descriptiva: determina los múltiplos de ATR del stop y "
            "del objetivo, el horizonte de la posición y los vetos que puede aplicar el Fund "
            "Manager. Un valor clasificado como TRAMPA_DE_VALOR o ESPECULATIVA no puede recibir "
            "un dictamen superior a MANTENER por muy atractivos que sean sus múltiplos.",
            "",
            "| Estilo | Valores | Qué significa |",
            "| :--- | :--- | :--- |",
        ]
        for estilo, tickers in sorted(conteo.items()):
            lineas.append(f"| `{estilo}` | {', '.join(tickers)} | "
                          f"{GLOSARIO_ESTILOS.get(estilo, '—')} |")
        lineas += ["", "---", ""]
        return lineas

    # ================================================================== #
    def _ficha(self, res: Dict[str, Any]) -> List[str]:
        ticker = res.get("ticker", "?")
        q = res.get("quality_report", {}) or {}
        f = res.get("fundamental_report", {}) or {}
        t = res.get("technical_report", {}) or {}
        n = res.get("news_report", {}) or {}
        d = res.get("debate_report", {}) or {}
        fd = res.get("final_decision", {}) or {}
        rec = res.get("reconciliation_data", {}) or {}

        lineas = [
            f"### {ticker} — {res.get('company_name', ticker)}",
            "",
            f"**Sector / Industria:** {res.get('sector', SIN_DATO)} / {res.get('industry', SIN_DATO)}  ",
            f"**Estilo:** `{q.get('style_classification', SIN_DATO)}`"
            + (f" (secundarias: {', '.join(q.get('etiquetas_secundarias', []))})"
               if q.get("etiquetas_secundarias") else "") + "  ",
            f"**Confianza en los datos:** {_p(rec.get('confidence_score'), '{:.0%}')} · "
            f"Fuentes: {', '.join(rec.get('sources_consulted', [])) or SIN_DATO}"
            + (f" · Sin respuesta: {', '.join(x['fuente'] for x in rec.get('sources_failed', []))}"
               if rec.get("sources_failed") else ""),
            "",
        ]

        # La numeración se lleva con un contador porque no todas las secciones
        # aparecen siempre: un valor rechazado no tiene análisis técnico ni
        # debate, y sin `TAVILY_API_KEY` puede no haber noticias. Numerarlas de
        # forma fija dejaba huecos («3» seguido de «5») en el informe.
        n_seccion = iter(range(1, 99))
        lineas += self._ficha_gatekeeper(f, next(n_seccion))
        lineas += self._ficha_calidad(q, next(n_seccion))
        if res.get("passed_fundamental_gatekeeper") and t:
            lineas += self._ficha_tecnico(t, next(n_seccion))
        if n:
            lineas += self._ficha_noticias(n, next(n_seccion))
        if d:
            lineas += self._ficha_debate(d, next(n_seccion))
        lineas += self._ficha_dictamen(fd, next(n_seccion))

        lineas += ["---", ""]
        return lineas

    def _ficha_gatekeeper(self, f: Dict[str, Any], num: int) -> List[str]:
        lineas = [f"#### {num}. Filtro fundamental — {f.get('status', SIN_DATO)}", ""]
        if f.get("criterios"):
            lineas += ["| Criterio | Valor | Umbral | Cumple |", "| :--- | ---: | ---: | :---: |"]
            for c in f["criterios"]:
                if c.get("exento"):
                    lineas.append(f"| {c['criterio']} | {_p(c.get('valor'))} | — | exento |")
                    continue
                fmt = "{:.2f}x" if "Deuda" in c["criterio"] else "{:.1%}"
                lineas.append(f"| {c['criterio']} | {_p(c.get('valor'), fmt)} "
                              f"| {_p(c.get('umbral'), fmt)} | {_si_no(c.get('cumple'))} |")
            lineas.append("")
        if f.get("magnitudes_ausentes"):
            lineas += [f"⚠️ **Magnitudes no disponibles:** {', '.join(f['magnitudes_ausentes'])}. "
                       "El veredicto es NO EVALUABLE, no un suspenso: la ausencia de dato no es "
                       "evidencia de deterioro.", ""]
        if f.get("reasons"):
            lineas += ["**Motivos:** " + "; ".join(f["reasons"]), ""]
        if f.get("avisos"):
            lineas += [f"- ℹ️ {a}" for a in f["avisos"]] + [""]
        lineas += [f"**Lectura:** {_texto(f.get('summary'))}", ""]
        return lineas

    def _ficha_calidad(self, q: Dict[str, Any], num: int) -> List[str]:
        if not q:
            return []
        p = q.get("puntuaciones", {}) or {}
        conv = q.get("conviccion_fundamental", {}) or {}

        lineas = [
            f"#### {num}. Calidad y valoración",
            "",
            "```",
            f"Calidad      {_barra(p.get('calidad'))}",
            f"Valoración   {_barra(p.get('valoracion'))}",
            f"Crecimiento  {_barra(p.get('crecimiento'))}",
            f"Solvencia    {_barra(p.get('solvencia'))}",
            "─" * 40,
            f"CONVICCIÓN   {_barra(conv.get('valor'))}",
            "```",
            "",
            f"**Estilo `{q.get('style_classification')}`** — {q.get('style_rationale', '')}",
            "",
        ]

        if conv.get("valor") is not None:
            lineas += [
                f"_Convicción bruta {conv.get('bruta')} × cobertura de datos "
                f"{conv.get('factor_cobertura')} × confianza en fuentes {conv.get('factor_confianza')} "
                f"− {conv.get('descuento_banderas')} por banderas rojas = **{conv.get('valor')}**._",
                "",
            ]

        # --- escuelas ----------------------------------------------------
        pio = q.get("piotroski", {}) or {}
        alt = q.get("altman", {}) or {}
        gra = q.get("graham", {}) or {}
        gre = q.get("greenblatt", {}) or {}
        buf = q.get("buffett", {}) or {}
        lyn = q.get("lynch", {}) or {}
        dev = q.get("devengos", {}) or {}

        lineas += [
            "| Escuela | Métrica | Valor | Lectura |",
            "| :--- | :--- | ---: | :--- |",
            f"| Piotroski | F-Score | {pio.get('score', SIN_DATO)}/{pio.get('criterios_evaluables', 9)} "
            f"| {pio.get('lectura', SIN_DATO)} |",
            f"| Altman | {alt.get('variante', 'Z-Score')} | {alt.get('z', SIN_DATO)} "
            f"| zona {alt.get('zona', SIN_DATO)} (seguro > {alt.get('umbral_seguro')}, "
            f"insolvencia < {alt.get('umbral_distress')}) |",
            f"| Graham | Nº de Graham | {_p(gra.get('numero_graham'), '${:,.2f}')} "
            f"| margen de seguridad {_p(gra.get('margen_seguridad'))} "
            f"({gra.get('criterios_cumplidos', 0)}/{gra.get('criterios_evaluables', 0)} criterios defensivos) |",
            f"| Greenblatt | EBIT/EV | {_p(gre.get('earnings_yield'))} "
            f"| {'atractivo' if gre.get('ey_atractivo') else 'por debajo del umbral' if gre.get('ey_atractivo') is not None else SIN_DATO} |",
            f"| Buffett | ROIC | {_p(buf.get('roic'))} "
            f"| {_p(buf.get('roic_menos_wacc'), '{:+.1%}')} sobre el coste de capital de referencia |",
            f"| Buffett | Margen bruto | {_p(buf.get('margen_bruto'))} "
            f"| {'indicio de foso competitivo' if buf.get('indicio_de_foso') else 'sin indicio de foso' if buf.get('indicio_de_foso') is not None else SIN_DATO} |",
            f"| Buffett | Rendimiento FCF | {_p(buf.get('fcf_yield'))} "
            f"| dilución anual {_p(buf.get('dilucion_anual'), '{:+.2%}')} |",
            f"| Lynch | PEG | {lyn.get('peg', SIN_DATO)} "
            f"| {lyn.get('lectura_peg', SIN_DATO)} · categoría {lyn.get('categoria_lynch', SIN_DATO)} "
            f"(sobre crecimiento de {lyn.get('base_del_crecimiento', SIN_DATO)}) |",
            f"| Sloan | Devengos | {_p(dev.get('ratio_devengos'))} | {dev.get('lectura', SIN_DATO)} |",
            "",
        ]

        # --- detalle Piotroski -------------------------------------------
        if pio.get("detalle"):
            lineas += ["<details><summary>Desglose del F-Score de Piotroski</summary>", ""]
            lineas += ["| Criterio | Cumple | Detalle |", "| :--- | :---: | :--- |"]
            for c in pio["detalle"]:
                lineas.append(f"| {c['criterio']} | {_si_no(c.get('cumple'))} | {c.get('detalle', '')} |")
            lineas += ["", "</details>", ""]

        # --- contexto sectorial ------------------------------------------
        ctx = q.get("contexto_sectorial", {}) or {}
        comparaciones = ctx.get("comparaciones", {})
        if comparaciones:
            lineas += [
                f"**Contexto sectorial ({ctx.get('sector')})** — el punto de comparación que "
                "convierte «P/E elevado» en una afirmación verificable:",
                "",
                "| Métrica | Valor | Mediana del sector | Ratio | Lectura |",
                "| :--- | ---: | ---: | ---: | :--- |",
            ]
            nombres = {"pe": "P/E", "margen_neto": "Margen neto",
                       "deuda_patrimonio": "Deuda/Patrimonio",
                       "crecimiento_ingresos": "Crecimiento de ingresos"}
            for clave, comp in comparaciones.items():
                fmt = "{:.1f}x" if clave in ("pe", "deuda_patrimonio") else "{:.1%}"
                ref_fmt = "{:.1f}x" if clave in ("pe", "deuda_patrimonio") else "{:.0%}"
                lineas.append(
                    f"| {nombres.get(clave, clave)} | {_p(comp.get('valor'), fmt)} "
                    f"| {_p(comp.get('referencia_sector'), ref_fmt)} "
                    f"| {comp.get('ratio', SIN_DATO)} | {comp.get('lectura')} |")
            lineas += ["", f"> {ctx.get('advertencia', '')}", ""]

        if q.get("banderas_rojas"):
            lineas += ["**🚩 Banderas rojas:**", ""]
            lineas += [f"- {b}" for b in q["banderas_rojas"]] + [""]

        lineas += [
            f"_Cobertura de datos: {_p(q.get('cobertura_global'), '{:.0%}')} "
            f"({q.get('status')})._",
            "",
            f"**Lectura:** {_texto(q.get('summary'))}",
            "",
        ]
        return lineas

    def _ficha_tecnico(self, t: Dict[str, Any], num: int) -> List[str]:
        if not t:
            return []
        lineas = [
            f"#### {num}. Análisis técnico",
            "",
            f"**Momentum:** `{t.get('momentum_classification')}` "
            f"(puntuación {t.get('momentum_score', 0):+.1f}/100) · "
            f"**Tendencia:** {t.get('estado_tendencia')} · "
            f"**RSI:** {t.get('rsi')} ({t.get('rsi_estado')})",
            "",
        ]
        if t.get("contribuciones"):
            lineas += ["| Componente | Aporte a la puntuación |", "| :--- | ---: |"]
            for k, v in t["contribuciones"].items():
                lineas.append(f"| {k.replace('_', ' ').capitalize()} | {v:+.2f} |")
            lineas += [f"| **Total** | **{t.get('momentum_score', 0):+.2f}** |", ""]

        lineas += [
            f"- Precio frente a medias: SMA50 {_p(t.get('dist_sma_50_pct'), '{:+.1%}')} · "
            f"SMA200 {_p(t.get('dist_sma_200_pct'), '{:+.1%}')}",
            f"- Posición en el rango de 52 semanas: {_p(t.get('posicion_rango_52w'), '{:.0%}')}",
            f"- ATR: {_p(t.get('atr'), '${:,.2f}')} ({_p(t.get('atr_pct'))} del precio) · "
            f"Volatilidad anualizada: {_p(t.get('volatilidad_anual'))}",
        ]
        if t.get("momentum_relativo_12m") is not None:
            lineas.append(f"- Momentum relativo a 12 meses frente al índice: "
                          f"{_p(t['momentum_relativo_12m'], '{:+.1%}')}")
        if t.get("sobreextendido"):
            lineas.append("- ⚠️ **Valor técnicamente sobreextendido:** la entrada en este nivel "
                          "asume riesgo de reversión. Afecta al tamaño de la posición, no a la tesis.")
        lineas += ["", "**Señales:**", ""]
        lineas += [f"- {s}" for s in t.get("signals", [])]
        lineas += ["", f"**Lectura:** {_texto(t.get('summary'))}", ""]
        return lineas

    def _ficha_noticias(self, n: Dict[str, Any], num: int) -> List[str]:
        if not n:
            return []
        fallidas = ", ".join(f["buscador"] for f in n.get("sources_failed", [])) or "ninguna"
        lineas = [
            f"#### {num}. Analista de noticias — **capa asesora, no altera el dictamen**",
            "",
            f"**Probabilidad de impacto:** `{n.get('impact_classification')}` "
            f"({_p(n.get('impact_probability'), '{:.2f}')}) · "
            f"**Dirección probable:** `{n.get('direction_classification')}`",
            "",
            f"Cobertura: {n.get('n_items', 0)} nota(s) en {n.get('window_days', 0)} días · "
            f"fuentes con respuesta: {', '.join(n.get('sources_ok', [])) or 'ninguna'} · "
            f"sin respuesta: {fallidas}",
            "",
        ]
        if n.get("catalysts"):
            lineas += ["**Catalizadores principales:**", ""]
            for c in n["catalysts"]:
                titular = f"[{c['titular']}]({c['url']})" if c.get("url") else c["titular"]
                lineas.append(
                    f"- `{c.get('fecha') or 's/f'}` · **{c['categoria']}** · {c['direccion']} · "
                    f"p={c['probabilidad_impacto']:.2f} · _{c.get('fuente', '')}_ "
                    f"({c.get('n_corroboraciones', 1)} fuente/s) — {titular}")
            lineas.append("")
        lineas += [
            f"**Lectura:** {_texto(n.get('summary'))}",
            "",
            "> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son "
            "buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una "
            "fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un "
            "almacén de noticias point-in-time. Un litigio o una investigación regulatoria "
            "relevante debe activar una **revisión manual**, no un recálculo automático del peso.",
            "",
        ]
        return lineas

    def _ficha_debate(self, d: Dict[str, Any], num: int) -> List[str]:
        lineas = [f"#### {num}. Debate y mitigación de sesgos", ""]
        n_alc = d.get("n_alcistas", 0)
        n_baj = d.get("n_bajistas", 0)
        lineas += [f"**🐂 Tesis alcista** ({n_alc} argumento{'s' if n_alc != 1 else ''})", ""]
        lineas += [f"- {a}" for a in d.get("argumentos_alcistas", [])] or ["- —"]
        lineas += ["", f"**🐻 Tesis bajista** ({n_baj} argumento{'s' if n_baj != 1 else ''})", ""]
        lineas += [f"- {a}" for a in d.get("argumentos_bajistas", [])] or ["- —"]
        lineas += ["", f"**⚖️ Síntesis:** {_texto(d.get('synthesis'))}", ""]
        if d.get("invalidacion"):
            lineas += [
                "**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, "
                "no una tesis:", "",
            ]
            lineas += [f"- {c}" for c in d["invalidacion"]] + [""]
        return lineas

    def _ficha_dictamen(self, fd: Dict[str, Any], num: int) -> List[str]:
        if not fd:
            return []
        des = fd.get("desglose_decision", {}) or {}
        dim = fd.get("dimensionado", {}) or {}
        riesgo = fd.get("perfil_riesgo", {}) or {}

        lineas = [
            f"#### {num}. Dictamen del Fund Manager",
            "",
            f"### 🎯 `{fd.get('rating')}` — asignación objetivo "
            f"**{_p(fd.get('peso_objetivo'), '{:.2%}')}** de la cartera",
            "",
        ]

        if des.get("puntuacion_compuesta") is not None:
            lineas += [
                "**Cómo se llegó al dictamen**",
                "",
                f"- Convicción fundamental **{des.get('conviccion_usada')}**/100 × peso "
                f"{des.get('peso_fundamental')} + momentum normalizado "
                f"**{des.get('momentum_normalizado')}**/100 × peso {des.get('peso_tecnico')} "
                f"= **{des.get('puntuacion_compuesta')}**/100",
                f"- Corte alcanzado: **{des.get('rating_antes_de_vetos')}**"
                + (f" → tras los vetos: **{des.get('rating_final')}**"
                   if des.get("rating_antes_de_vetos") != des.get("rating_final") else ""),
                "",
            ]

        if fd.get("vetos_aplicados"):
            lineas += ["**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):", ""]
            lineas += [f"- {v}" for v in fd["vetos_aplicados"]] + [""]

        if dim.get("factores"):
            fac = dim["factores"]
            lineas += [
                "**Cómo se calculó el tamaño**",
                "",
                f"> `peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`",
                "",
                "| Factor | Valor |",
                "| :--- | ---: |",
                f"| Escala de convicción | ×{fac.get('escala_conviccion', SIN_DATO)} |",
                f"| Riesgo asumible por posición | {fac.get('riesgo_asumible_pct', SIN_DATO)}% del patrimonio |",
                f"| Distancia al stop | {_p(fac.get('distancia_stop_pct'))} |",
                f"| Peso por presupuesto de riesgo | {_p(fac.get('peso_por_riesgo'), '{:.2%}')} |",
                f"| Factor de volatilidad | ×{fac.get('factor_volatilidad', SIN_DATO)} |",
                f"| Factor de confianza en datos | ×{fac.get('factor_confianza_datos', SIN_DATO)} |",
                f"| Factor de banderas rojas | ×{fac.get('factor_banderas_rojas', SIN_DATO)} |",
                f"| Factor de sobreextensión técnica | ×{fac.get('factor_sobreextension', SIN_DATO)} |",
                f"| **Peso final** | **{dim.get('display', SIN_DATO)}** |",
                "",
                f"_{dim.get('motivo', '')}_",
                "",
            ]
        elif dim.get("motivo"):
            lineas += [f"_Sin asignación: {dim['motivo']}._", ""]

        if riesgo:
            lineas += [
                "**Gestión del riesgo**",
                "",
                f"| Nivel | Precio | Distancia | Múltiplo ATR |",
                f"| :--- | ---: | ---: | ---: |",
                f"| Entrada (referencia) | {_p(fd.get('current_price'), '${:,.2f}')} | — | — |",
                f"| Stop-loss | {_p(fd.get('stop_loss_atr'), '${:,.2f}')} "
                f"| {_p(riesgo.get('riesgo_pct'), '−{:.1%}')} | {fd.get('multiplo_stop')}× |",
                f"| Objetivo | {_p(fd.get('take_profit_atr'), '${:,.2f}')} "
                f"| {_p(riesgo.get('recompensa_pct'), '+{:.1%}')} | {fd.get('multiplo_objetivo')}× |",
                "",
                f"- **Ratio riesgo/recompensa:** {riesgo.get('ratio_riesgo_recompensa')} → exige "
                f"acertar el **{_p(riesgo.get('tasa_acierto_equilibrio'), '{:.1%}')}** de las veces "
                f"solo para no perder dinero.",
                f"- **Horizonte:** {riesgo.get('horizonte_dias')} sesiones "
                f"(~{riesgo.get('horizonte_meses')} meses). "
                f"A su ATR actual, el precio necesitaría al menos "
                f"{riesgo.get('sesiones_minimas_al_objetivo')} sesiones de avance direccional "
                f"puro para alcanzar el objetivo.",
                "",
                f"> {riesgo.get('nota_horizonte', '')}",
                "",
            ]

        lineas += [f"**Orden ejecutiva:** {_texto(fd.get('summary'))}", ""]
        return lineas

    # ================================================================== #
    def _calidad_de_datos(self, results: List[Dict[str, Any]]) -> List[str]:
        lineas = [
            "## 5. Calidad de los datos",
            "",
            "Ningún dictamen es mejor que los datos que lo sostienen. Esta sección declara qué "
            "se sabe y qué no de cada valor, porque la ausencia de un dato se propaga a la "
            "convicción y, por esa vía, al tamaño de la posición.",
            "",
            "| Ticker | Confianza | Fuentes | Cobertura fundamental | Campos ausentes | Discrepancias |",
            "| :--- | ---: | :--- | ---: | :--- | ---: |",
        ]
        for res in results:
            rec = res.get("reconciliation_data", {}) or {}
            q = res.get("quality_report", {}) or {}
            cob = rec.get("cobertura", {}) or {}
            ausentes = cob.get("campos_ausentes", [])
            lineas.append(
                f"| **{res.get('ticker')}** | {_p(rec.get('confidence_score'), '{:.0%}')} "
                f"| {', '.join(rec.get('sources_consulted', []))} "
                f"| {_p(q.get('cobertura_global'), '{:.0%}')} "
                f"| {', '.join(ausentes) if ausentes else '—'} "
                f"| {len(rec.get('discrepancies', []))} |")
        lineas.append("")

        detalles = []
        for res in results:
            rec = res.get("reconciliation_data", {}) or {}
            for disc in rec.get("discrepancies", []):
                detalles.append(f"- `{res.get('ticker')}` — {disc.get('texto')}")
        if detalles:
            lineas += ["**Discrepancias entre proveedores:**", ""] + detalles + [""]

        procedencias = []
        for res in results:
            proc = (res.get("reconciliation_data", {}) or {}).get("procedencia", {})
            if not proc:
                continue
            fuentes = {k: v.get("fuente_elegida") for k, v in proc.items() if v.get("fuente_elegida")}
            if fuentes:
                procedencias.append(f"- `{res.get('ticker')}`: " + ", ".join(
                    f"{k} ← {v}" for k, v in fuentes.items()))
        if procedencias:
            lineas += [
                "<details><summary>Procedencia de cada magnitud reconciliada</summary>", "",
            ] + procedencias + ["", "</details>", ""]

        lineas += ["---", ""]
        return lineas

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
            return [
                "**No hay backtest disponible.** No existe `output/backtest_results.json`, así "
                "que este informe no puede declarar ningún historial. Ejecuta "
                "`backtest_cli.py --regime pit` antes de dar peso a las recomendaciones: un "
                "sistema de selección sin track record es una hipótesis, no una estrategia.",
                "",
            ]
        try:
            with open(ruta, encoding="utf-8") as f:
                bt = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            return [f"**Backtest ilegible** (`{ruta}`): {e}.", ""]

        est = bt.get("strategy", {}) or {}
        spy = bt.get("spy", {}) or {}
        aleatorio = bt.get("random_test", {}) or {}
        regimen = bt.get("regime", "?")
        generado = (bt.get("generated_at") or "")[:16]

        exceso = (est.get("cagr", 0.0) - spy.get("cagr", 0.0))
        bate = exceso > 0
        veredicto = ("**El sistema bate a comprar y mantener el índice en el histórico "
                     "simulado.**" if bate else
                     "**El sistema NO bate a comprar y mantener el índice.**")

        lineas = [
            f"{veredicto} Backtest en régimen `{regimen}` sobre "
            f"{est.get('start', '?')} → {est.get('end', '?')} "
            f"(generado el {generado}, ver `output/backtest_report.md`):",
            "",
            "| Métrica | Estrategia | SPY |",
            "| :--- | ---: | ---: |",
            f"| CAGR | {_p(est.get('cagr'))} | {_p(spy.get('cagr'))} |",
            f"| Volatilidad anualizada | {_p(est.get('volatility'))} | {_p(spy.get('volatility'))} |",
            f"| Sharpe | {_p(est.get('sharpe'), '{:.2f}')} | {_p(spy.get('sharpe'), '{:.2f}')} |",
            f"| Sortino | {_p(est.get('sortino'), '{:.2f}')} | {_p(spy.get('sortino'), '{:.2f}')} |",
            f"| Máximo drawdown | {_p(est.get('max_drawdown'))} | {_p(spy.get('max_drawdown'))} |",
            "",
        ]

        pct = aleatorio.get("percentil_vs_aleatorio")
        if pct is not None:
            lectura = ("por encima de la mediana de carteras aleatorias con el mismo perfil de "
                       "exposición" if pct >= 50 else
                       "**por debajo** de la mediana de carteras aleatorias con el mismo perfil "
                       "de exposición, lo que significa que la selección de valores no aporta")
            lineas += [
                f"Frente a la selección aleatoria, la estrategia queda en el **percentil "
                f"{pct:.1f}** — {lectura}.",
                "",
            ]

        if est.get("volatility") and spy.get("volatility") and \
                est["volatility"] < spy["volatility"] * 0.6:
            lineas += [
                f"> **Cuidado al comparar el CAGR.** La estrategia opera con una volatilidad del "
                f"{est['volatility']:.1%} frente al {spy['volatility']:.1%} del índice, porque el "
                f"presupuesto de riesgo la mantiene estructuralmente poco invertida. Comparar "
                f"rentabilidades absolutas entre carteras con perfiles de riesgo tan distintos "
                f"favorece mecánicamente a la más expuesta; el Sharpe y el Sortino son la "
                f"comparación pertinente.",
                "",
            ]

        return lineas

    def _limitaciones(self) -> List[str]:
        return [
            "## 6. Limitaciones y track record",
            "",
        ] + self._track_record() + [
            "**Limitaciones metodológicas vigentes:**",
            "",
            "- **Universo con sesgo de supervivencia.** Solo se analizan valores que existen hoy.",
            "- **Normas sectoriales estáticas.** Las medianas de comparación son de largo plazo, "
            "no la mediana viva del sector. Ordenan y contextualizan; no valoran.",
            "- **Coste de capital constante.** Se usa un WACC de referencia común en lugar de "
            "estimarlo por empresa: la dispersión de un WACC estimado con beta y estructura de "
            "capital sería mayor que la señal que aporta.",
            "- **Sin datos intradía.** La ejecución se modela al cierre y la apertura siguiente.",
            "- **Riesgo legal y regulatorio fuera de la decisión.** Un litigio por fraude de "
            "valores aparece en la capa de noticias pero no toca el tamaño de la posición, porque "
            "esa capa no es reconstruible point-in-time. Debe activar revisión manual.",
            "- **Sin Finnhub histórico** en el backtest, y contrastes múltiples sin corregir.",
            "",
            "---",
            "",
        ]

    def _anexo_metodologico(self) -> List[str]:
        return [
            "## 7. Anexo metodológico",
            "",
            "**Umbrales del filtro fundamental**",
            "",
            f"- Margen neto mínimo: {MIN_NET_MARGIN:.1%}",
            f"- Crecimiento de ingresos mínimo: {MIN_REVENUE_GROWTH:.1%}",
            f"- Deuda/Patrimonio máxima: {MAX_DEBT_TO_EQUITY:.2f}x "
            "(ajustada al alza en servicios financieros, inmobiliario y utilities, donde el "
            "apalancamiento alto es estructural)",
            "",
            "**Política de riesgo y cartera**",
            "",
            f"- Riesgo por posición: {RIESGO_POR_POSICION_PCT:.2%} del patrimonio al stop",
            f"- Riesgo agregado máximo: {RIESGO_TOTAL_CARTERA_PCT:.1%}",
            f"- Peso máximo por posición: {PESO_MAXIMO_POSICION:.0%}",
            f"- Límite por sector: {LIMITE_POR_SECTOR:.0%}",
            f"- Exposición bruta máxima: {EXPOSICION_BRUTA_MAXIMA:.0%}",
            f"- Volatilidad objetivo por posición: {VOLATILIDAD_OBJETIVO:.0%} anualizada",
            "",
            "**Origen de las reglas de calidad y valoración**",
            "",
            "- *Piotroski (2000)* — F-Score de 9 puntos sobre rentabilidad, apalancamiento y "
            "eficiencia, medidos como variación interanual.",
            "- *Altman (1968)* — Z-Score de solvencia; variante Z'' para no manufactureras.",
            "- *Graham (1949)* — Número de Graham y criterios del inversor defensivo.",
            "- *Buffett* — ROIC sostenido sobre el coste del capital, margen bruto como "
            "aproximación al foso, beneficio del propietario.",
            "- *Lynch (1989)* — PEG y taxonomía por perfil de crecimiento.",
            "- *Greenblatt (2005)* — rendimiento del beneficio sobre valor de empresa y "
            "rentabilidad del capital tangible.",
            "- *Sloan (1996)* — ratio de devengos: el beneficio que no es caja revierte.",
            "",
            "**Papel del modelo de lenguaje**",
            "",
            "Ninguna variable de decisión depende del LLM. Los agentes calculan rating, tamaño, "
            "stop, objetivo y etiqueta de estilo con reglas deterministas; el modelo solo puede "
            "sobrescribir los campos de texto, y siempre después de que todo esté fijado. Sin "
            "clave de API el sistema produce exactamente los mismos dictámenes. Esta propiedad se "
            "verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()`.",
            "",
        ]
