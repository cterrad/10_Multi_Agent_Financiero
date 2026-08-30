"""
Grafo de producción: máquina de estados LangGraph sobre `FinancialAnalysisState`.

FORMA DEL GRAFO

                              ┌─ gatekeeper ────┐
ingest → quality_analysis ────┤                 ├─ join_analisis → [route] ─┬─ aprobado → technical → debate → fund_manager → END
                              └─ news_analysis ─┘                          └─ rechazado ─────────────────────→ fund_manager → END

CONTRATO DE ESCRITURA DE LOS NODOS
----------------------------------
`logs` y `messages` declaran reductor en `src/state.py` (`operator.add` y
`add_messages`), así que cada nodo devuelve SOLO lo que él produce, nunca el
acumulado. Devolver la lista entera —que es lo que hacía la versión anterior,
cuando no había reductores— la duplicaría en silencio: no rompe nada, solo
ensucia el informe con cada línea repetida tantas veces como nodos hayan pasado.

Los reductores además resolvieron una limitación real. Antes `news_analysis`
tenía PROHIBIDO escribir `logs`, porque coincidía en superstep con el gatekeeper
y `FinancialAnalysisState` no declaraba ninguno: LangGraph abortaba con
`InvalidUpdateError: can receive only one value per step`. Sus trazas las tenía
que volcar `join_analisis` en su nombre. Ahora escribe las suyas.

`workflow_status` sigue SIN reductor a propósito —es un escalar, y dos nodos
paralelos escribiéndolo no tendrían un valor correcto que fusionar—, así que
`news_analysis` sigue sin tocarlo. Esa parte de la restricción no ha cambiado.

POR QUÉ `quality_analysis` VA ANTES DEL FAN-OUT
-----------------------------------------------
Es cálculo puro sobre datos ya ingeridos, así que paralelizarlo no ahorraría
latencia. Y colocarlo antes del gatekeeper deja sus puntuaciones y banderas
rojas disponibles TAMBIÉN para los valores rechazados: un Altman en zona de
insolvencia es justo lo que se quiere leer sobre una empresa que no pasa el
filtro.

POR QUÉ SIGUE EXISTIENDO `join_analisis`
-----------------------------------------
Su segunda razón de ser es independiente de los reductores y sigue vigente:
colgar el enrutado condicional del gatekeeper y llevar `news_analysis`
directamente a `debate_unit` haría que las dos ramas tuvieran longitudes
distintas y que `debate_unit` coincidiera con `fund_manager` en un superstep.
Unir antes de ramificar lo resuelve y además deja `news_report` disponible en
las dos ramas, incluida la de rechazo.

Este módulo instancia los agentes y compila el grafo A NIVEL DE MÓDULO
(`financial_app`), así que importarlo tiene efectos secundarios.
"""

from typing import Any, Dict, List

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph

from src.agents.base import Traza, usar_tool
from src.agents.debate import DebateUnitAgent
from src.agents.fund_manager import FundManagerAgent
from src.agents.fundamental import FundamentalAnalystAgent
from src.agents.news import NewsAnalystAgent
from src.agents.quality import QualityAnalystAgent
from src.agents.technical import TechnicalAnalystAgent
from src.state import FinancialAnalysisState

# Instancias de los agentes. Las clases de datos (fetchers, reconciliador) ya no
# se instancian aquí: viven detrás de las tools de `src/tools/extraccion.py`,
# que son las únicas del sistema que salen a la red.
fundamental_agent = FundamentalAnalystAgent()
quality_agent = QualityAnalystAgent()
technical_agent = TechnicalAnalystAgent()
news_agent = NewsAnalystAgent()
debate_agent = DebateUnitAgent()
fund_manager_agent = FundManagerAgent()


def _salida(informe: Dict[str, Any], clave: str, logs: List[str],
            **extra: Any) -> Dict[str, Any]:
    """
    Actualización de estado de un nodo de agente.

    Extrae los mensajes de la traza al canal `messages` y deja el informe sin
    ellos: los objetos de mensaje no son JSON-serializables y `daily_selection.json`
    los rompería. La forma serializada sigue en `informe["_traza"]`.
    """
    mensajes: List[BaseMessage] = informe.pop("_mensajes", [])
    return {clave: informe, "logs": logs, "messages": mensajes, **extra}


# --------------------------------------------------------------------------- #
# Nodos
# --------------------------------------------------------------------------- #
def node_ingest_and_reconcile(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Ingesta multi-fuente y reconciliación.

    Es el ÚNICO nodo que sale a la red en la ruta de decisión. Los cuatro
    agentes posteriores consumen el estado ya reconciliado y son puros, que es
    lo que los hace testeables sin red y reproducibles en el backtest.

    No es un agente —no tiene dictamen que emitir ni texto que redactar— pero sí
    deja traza: las cuatro llamadas quedan en `messages` con sus argumentos y su
    resultado, igual que las de cualquier scorer.
    """
    ticker = state["ticker"]
    traza = Traza("ingesta", ticker)
    traza.añadir(HumanMessage(content=f"Ingesta multi-fuente de {ticker}."))

    yf_data = usar_tool("obtener_datos_yfinance", {"ticker": ticker}, traza)
    sec_data = usar_tool("obtener_hechos_sec", {"ticker": ticker}, traza)
    fh_data = usar_tool("obtener_datos_finnhub", {"ticker": ticker}, traza)
    rec_data = usar_tool("reconciliar_fuentes", {
        "ticker": ticker, "datos_yfinance": yf_data,
        "hechos_sec": sec_data, "datos_finnhub": fh_data}, traza)

    traza.log.info(
        f"confianza {rec_data['confidence_score']} · fuentes {rec_data['sources_consulted']}",
        extra={"evento": "dictamen", "confianza": rec_data["confidence_score"]})

    return {
        "company_name": yf_data.get("company_name", ticker),
        "sector": yf_data.get("sector", "Desconocido"),
        "industry": yf_data.get("industry", "Desconocido"),
        "yfinance_data": yf_data,
        "sec_edgar_data": sec_data,
        "finnhub_data": fh_data,
        "reconciliation_data": rec_data,
        "workflow_status": "INGESTED",
        "messages": traza.mensajes,
        "logs": [
            f"[Ingesta] Recolectando datos multi-fuente para {ticker}...",
            f"[Reconciliación] Puntuación de confianza: {rec_data['confidence_score']}, "
            f"Fuentes: {rec_data['sources_consulted']}",
        ],
    }


def node_quality_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Calidad y Valoración.

    A diferencia del Analista de Noticias, este dictamen SÍ es variable de
    decisión: el Fund Manager cruza `conviccion_fundamental` con el momentum.
    Por eso el backtest lo ejecuta.
    """
    ticker = state["ticker"]
    informe = quality_agent.analyze(state)
    conviccion = (informe.get("conviccion_fundamental") or {}).get("valor")

    logs = [
        f"[Analista de Calidad] Evaluando calidad, valoración y solvencia de {ticker}...",
        f"[Analista de Calidad] Estilo: {informe.get('style_classification')} | "
        f"Convicción: {conviccion} | "
        f"Piotroski: {informe.get('piotroski', {}).get('score')} | "
        f"Altman: {informe.get('altman', {}).get('zona')} | "
        f"Cobertura de datos: {informe.get('cobertura_global', 0.0):.0%}",
    ]
    if informe.get("banderas_rojas"):
        logs.append(f"[Analista de Calidad] Banderas rojas: "
                    f"{'; '.join(informe['banderas_rojas'])}")

    return _salida(informe, "quality_report", logs,
                   workflow_status="QUALITY_EVALUATED")


def node_fundamental_gatekeeper(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    informe = fundamental_agent.analyze(state)
    passed = informe["passed_gatekeeper"]

    estado = ("APROBADO -> Continuando a Análisis Técnico" if passed
              else "RECHAZADO -> Deteniendo flujo avanzado (Ahorro de Cómputo)")
    logs = [
        f"[Gatekeeper Fundamental] Evaluando salud financiera para {ticker}...",
        f"[Gatekeeper Fundamental] Resultado: {estado}",
    ]

    return _salida(informe, "fundamental_report", logs,
                   passed_fundamental_gatekeeper=passed,
                   workflow_status="FUNDAMENTAL_EVALUATED")


def node_news_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Noticias. Corre EN PARALELO al gatekeeper (fan-out desde
    `quality_analysis`), porque sus tres buscadores son de red y el gatekeeper es
    puro cálculo sobre datos ya ingeridos.

    Ahora SÍ escribe sus propias trazas: `logs` y `messages` tienen reductor. Lo
    que sigue sin escribir es `workflow_status`, que es un escalar sin reductor y
    lo escribe el gatekeeper en este mismo superstep.
    """
    ticker = state["ticker"]
    empresa = state.get("company_name") or ticker
    traza = Traza("noticias_ingesta", ticker)
    traza.añadir(HumanMessage(content=f"Recolecta la prensa reciente de {empresa} ({ticker})."))

    try:
        news_data = usar_tool("obtener_noticias",
                              {"ticker": ticker, "empresa": empresa}, traza)
    except Exception as e:
        # Red inaccesible, caché ilegible o cualquier fallo del agregador: se
        # emite un dosier vacío para que el agente produzca un informe
        # degradado. Un valor no se deja de analizar porque falle la prensa.
        news_data = {
            "status": "SIN_DATOS", "ticker": ticker.upper(), "empresa": empresa,
            "items": [], "n_items": 0, "ventana_dias": 0,
            "fuentes_ok": [], "desde_cache": False,
            "fuentes_fallidas": [{"buscador": "agregador", "motivo": f"{type(e).__name__}: {e}"}],
        }

    informe = news_agent.analyze({**state, "news_data": news_data})
    fallidas = ", ".join(f["buscador"] for f in informe.get("sources_failed", [])) or "ninguna"

    logs = [
        f"[Analista de Noticias] {informe.get('n_items', 0)} noticia(s) | "
        f"Impacto: {informe.get('impact_classification', 'N/A')} "
        f"({informe.get('impact_probability', 0.0):.2f}) | "
        f"Dirección: {informe.get('direction_classification', 'N/A')} | "
        f"Fuentes sin respuesta: {fallidas}",
        "[Analista de Noticias] Capa ASESORA: no altera el rating ni el sizing.",
    ]

    mensajes = traza.mensajes + informe.pop("_mensajes", [])
    return {"news_data": news_data, "news_report": informe,
            "logs": logs, "messages": mensajes}


def node_join_analisis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Punto de encuentro del fan-out `gatekeeper` / `news_analysis`.

    Ya no vuelca las trazas del nodo de noticias —ese nodo escribe las suyas
    desde que `logs` tiene reductor—, pero el nodo sigue siendo necesario: sin
    él, las dos ramas tendrían longitudes distintas y `debate_unit` coincidiría
    con `fund_manager` en un superstep, reventando el grafo con
    `InvalidUpdateError`. Unir ANTES del enrutado condicional lo resuelve sin
    renunciar al paralelismo.
    """
    return {"logs": []}


def route_after_gatekeeper(state: FinancialAnalysisState) -> str:
    """Condición explícita de LangGraph para ramificación condicional."""
    if state.get("passed_fundamental_gatekeeper", False):
        return "technical_analysis"
    return "fund_manager"


def node_technical_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    informe = technical_agent.analyze(state)
    logs = [
        f"[Analista Técnico] Evaluando indicadores de momentum para {ticker}...",
        f"[Analista Técnico] Momentum clasificado como: {informe['momentum_classification']}",
    ]
    return _salida(informe, "technical_report", logs,
                   workflow_status="TECHNICAL_COMPLETED")


def node_debate_unit(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    informe = debate_agent.analyze(state)
    logs = [
        f"[Capa de Debate] Ejecutando confrontación Bullish vs Bearish para {ticker}...",
        f"[Capa de Debate] Síntesis finalizada: {informe['n_alcistas']} argumento(s) "
        f"alcista(s) frente a {informe['n_bajistas']} bajista(s).",
    ]
    return _salida(informe, "debate_report", logs,
                   workflow_status="DEBATE_COMPLETED")


def node_fund_manager(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    informe = fund_manager_agent.analyze(state)
    logs = [
        f"[Fund Manager] Sintetizando informes y emitiendo recomendación final para {ticker}...",
        f"[Fund Manager] DICTAMEN FINAL: {informe['rating']}",
    ]
    return _salida(informe, "final_decision", logs, workflow_status="COMPLETED")


# --------------------------------------------------------------------------- #
# Construcción del grafo
# --------------------------------------------------------------------------- #
def build_financial_workflow():
    """Construye y compila el gráfico de estados de LangGraph."""
    workflow = StateGraph(FinancialAnalysisState)

    workflow.add_node("ingest", node_ingest_and_reconcile)
    workflow.add_node("quality_analysis", node_quality_analysis)
    workflow.add_node("gatekeeper", node_fundamental_gatekeeper)
    workflow.add_node("news_analysis", node_news_analysis)
    workflow.add_node("join_analisis", node_join_analisis)
    workflow.add_node("technical_analysis", node_technical_analysis)
    workflow.add_node("debate_unit", node_debate_unit)
    workflow.add_node("fund_manager", node_fund_manager)

    workflow.set_entry_point("ingest")

    # Fan-out: el gatekeeper (cálculo puro) y el analista de noticias (tres
    # buscadores de red) no dependen el uno del otro y corren a la vez.
    workflow.add_edge("ingest", "quality_analysis")
    workflow.add_edge("quality_analysis", "gatekeeper")
    workflow.add_edge("quality_analysis", "news_analysis")

    # Unión antes de ramificar. Ver el encabezado del módulo.
    workflow.add_edge("gatekeeper", "join_analisis")
    workflow.add_edge("news_analysis", "join_analisis")

    workflow.add_conditional_edges(
        "join_analisis",
        route_after_gatekeeper,
        {
            "technical_analysis": "technical_analysis",
            "fund_manager": "fund_manager"
        }
    )

    workflow.add_edge("technical_analysis", "debate_unit")
    workflow.add_edge("debate_unit", "fund_manager")
    workflow.add_edge("fund_manager", END)

    return workflow.compile()


# Instancia del grafo compilado
financial_app = build_financial_workflow()


def run_stock_analysis(ticker: str,
                       benchmark_data: Dict[str, Any] = None) -> FinancialAnalysisState:
    """
    Ejecuta el pipeline completo de un ticker.

    `benchmark_data` es opcional y contiene las rentabilidades del índice de
    referencia (ver `cargar_benchmark`). Cuando está, el Analista Técnico
    calcula momentum RELATIVO; sin él, momentum absoluto, y lo declara en el
    informe. No se descarga aquí dentro para no repetir la misma petición una
    vez por ticker: quien orquesta el lote la hace una sola vez.
    """
    initial_state: FinancialAnalysisState = {
        "ticker": ticker.upper(),
        "logs": [],
        "messages": [],
        "passed_fundamental_gatekeeper": False,
        "workflow_status": "INITIALIZED",
        "benchmark_data": benchmark_data or {},
    }
    return financial_app.invoke(initial_state)


def cargar_benchmark(ticker: str = "SPY") -> Dict[str, Any]:
    """
    Rentabilidades del índice de referencia, para medir momentum relativo.

    Sin esta referencia, «el valor sube un 20% a doce meses» no distingue
    habilidad de selección de simple exposición al mercado — que es
    precisamente la crítica que el contraste de Monte Carlo del backtest hace
    a la estrategia. Un fallo de red devuelve un dict vacío y el sistema
    degrada a momentum absoluto en lugar de detenerse.
    """
    from src.tools.extraccion import obtener_benchmark
    try:
        return obtener_benchmark.invoke({"ticker": ticker})
    except Exception as e:
        print(f"[Benchmark] No se pudo cargar {ticker}: {e}. "
              f"El momentum se calculará en términos absolutos.")
        return {}
