from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import FinancialAnalysisState
from src.data.fetcher import DataFetcher
from src.data.sec_edgar import SECEdgarClient
from src.data.finnhub_client import FinnhubClient
from src.data.reconciler import DataReconciler
from src.data.news import recolectar as recolectar_noticias
from src.agents.fundamental import FundamentalAnalystAgent
from src.agents.quality import QualityAnalystAgent
from src.agents.technical import TechnicalAnalystAgent
from src.agents.news import NewsAnalystAgent
from src.agents.debate import DebateUnitAgent
from src.agents.fund_manager import FundManagerAgent

# Instancias de componentes
fetcher = DataFetcher()
sec_client = SECEdgarClient()
finnhub_client = FinnhubClient()
reconciler = DataReconciler()

fundamental_agent = FundamentalAnalystAgent()
quality_agent = QualityAnalystAgent()
technical_agent = TechnicalAnalystAgent()
news_agent = NewsAnalystAgent()
debate_agent = DebateUnitAgent()
fund_manager_agent = FundManagerAgent()

def node_ingest_and_reconcile(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Ingesta] Recolectando datos multi-fuente para {ticker}...")

    yf_data = fetcher.fetch_all(ticker)
    sec_data = sec_client.get_fundamental_facts(ticker)
    fh_data = finnhub_client.get_basic_financials(ticker)

    rec_data = reconciler.reconcile(ticker, yf_data, sec_data, fh_data)
    logs.append(f"[Reconciliación] Puntuación de confianza: {rec_data['confidence_score']}, Fuentes: {rec_data['sources_consulted']}")

    return {
        "company_name": yf_data.get("company_name", ticker),
        "sector": yf_data.get("sector", "Desconocido"),
        "industry": yf_data.get("industry", "Desconocido"),
        "yfinance_data": yf_data,
        "sec_edgar_data": sec_data,
        "finnhub_data": fh_data,
        "reconciliation_data": rec_data,
        "workflow_status": "INGESTED",
        "logs": logs
    }

def node_quality_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Calidad y Valoración.

    Corre SECUENCIALMENTE entre `ingest` y el fan-out, no en paralelo, por dos
    motivos:

      1. Es cálculo puro sobre datos ya ingeridos —no toca la red—, así que
         paralelizarlo no ahorra latencia; solo añadiría un tercer escritor al
         mismo superstep, y `FinancialAnalysisState` no declara reductores.
      2. Situarlo ANTES del gatekeeper hace que sus puntuaciones y banderas
         rojas estén disponibles para TODOS los valores, incluidos los que el
         gatekeeper rechace. Un Altman en zona de insolvencia es justamente la
         información que se quiere leer sobre una empresa rechazada, y con el
         orden inverso se habría perdido.

    A diferencia del Analista de Noticias, este dictamen SÍ es variable de
    decisión: el Fund Manager cruza `conviccion_fundamental` con el momentum.
    Por eso el backtest lo ejecuta.
    """
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Analista de Calidad] Evaluando calidad, valoración y solvencia de {ticker}...")

    report = quality_agent.analyze(state)
    conviccion = (report.get("conviccion_fundamental") or {}).get("valor")
    logs.append(
        f"[Analista de Calidad] Estilo: {report.get('style_classification')} | "
        f"Convicción: {conviccion} | "
        f"Piotroski: {report.get('piotroski', {}).get('score')} | "
        f"Altman: {report.get('altman', {}).get('zona')} | "
        f"Cobertura de datos: {report.get('cobertura_global', 0.0):.0%}"
    )
    if report.get("banderas_rojas"):
        logs.append(f"[Analista de Calidad] Banderas rojas: {'; '.join(report['banderas_rojas'])}")

    return {
        "quality_report": report,
        "workflow_status": "QUALITY_EVALUATED",
        "logs": logs
    }

def node_fundamental_gatekeeper(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Gatekeeper Fundamental] Evaluando salud financiera para {ticker}...")

    report = fundamental_agent.analyze(state)
    passed = report["passed_gatekeeper"]

    status_log = "APROBADO -> Continuando a Análisis Técnico" if passed else "RECHAZADO -> Deteniendo flujo avanzado (Ahorro de Cómputo)"
    logs.append(f"[Gatekeeper Fundamental] Resultado: {status_log}")

    return {
        "fundamental_report": report,
        "passed_fundamental_gatekeeper": passed,
        "workflow_status": "FUNDAMENTAL_EVALUATED",
        "logs": logs
    }

def node_news_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Noticias. Corre EN PARALELO al gatekeeper (fan-out desde
    `ingest`), porque sus tres buscadores son de red y el gatekeeper es puro
    cálculo sobre datos ya ingeridos.

    Devuelve deliberadamente SOLO `news_data` y `news_report`: `logs` y
    `workflow_status` los escribe el gatekeeper en este mismo superstep y
    `FinancialAnalysisState` no declara reductores, así que escribirlos aquí
    provocaría `InvalidUpdateError: can receive only one value per step`. Las
    trazas de este nodo se vuelcan a `logs` en `node_join_analisis`.
    """
    ticker = state["ticker"]
    empresa = state.get("company_name") or ticker

    try:
        news_data = recolectar_noticias(ticker, empresa=empresa)
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

    report = news_agent.analyze({**state, "news_data": news_data})

    return {
        "news_data": news_data,
        "news_report": report
    }

def node_join_analisis(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Punto de encuentro del fan-out `gatekeeper` / `news_analysis`.

    Existe por una razón concreta y verificada: si `news_analysis` desembocara
    directamente en `debate_unit`, las dos ramas tendrían longitudes distintas y
    `debate_unit` y `fund_manager` coincidirían en el mismo superstep,
    reventando el grafo con `InvalidUpdateError`. Unir ANTES del enrutado
    condicional resuelve el problema sin renunciar al paralelismo y deja
    `news_report` disponible en las dos ramas, también en la de rechazo.

    Aquí se consolidan además las trazas del nodo de noticias, que no puede
    escribirlas por su cuenta.
    """
    logs = state.get("logs", [])
    news = state.get("news_report", {})

    if news:
        fallidas = ", ".join(f["buscador"] for f in news.get("sources_failed", [])) or "ninguna"
        logs.append(
            f"[Analista de Noticias] {news.get('n_items', 0)} noticia(s) | "
            f"Impacto: {news.get('impact_classification', 'N/A')} "
            f"({news.get('impact_probability', 0.0):.2f}) | "
            f"Dirección: {news.get('direction_classification', 'N/A')} | "
            f"Fuentes sin respuesta: {fallidas}"
        )
        logs.append("[Analista de Noticias] Capa ASESORA: no altera el rating ni el sizing.")

    return {"logs": logs}

def route_after_gatekeeper(state: FinancialAnalysisState) -> str:
    """Condición explícita de LangGraph para ramificación condicional."""
    if state.get("passed_fundamental_gatekeeper", False):
        return "technical_analysis"
    return "fund_manager"

def node_technical_analysis(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Analista Técnico] Evaluando indicadores de momentum para {ticker}...")

    report = technical_agent.analyze(state)
    logs.append(f"[Analista Técnico] Momentum clasificado como: {report['momentum_classification']}")

    return {
        "technical_report": report,
        "workflow_status": "TECHNICAL_COMPLETED",
        "logs": logs
    }

def node_debate_unit(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Capa de Debate] Ejecutando confrontación Bullish vs Bearish para {ticker}...")

    report = debate_agent.analyze(state)
    logs.append(f"[Capa de Debate] Síntesis finalizada.")

    return {
        "debate_report": report,
        "workflow_status": "DEBATE_COMPLETED",
        "logs": logs
    }

def node_fund_manager(state: FinancialAnalysisState) -> Dict[str, Any]:
    ticker = state["ticker"]
    logs = state.get("logs", [])
    logs.append(f"[Fund Manager] Sintetizando informes y emitiendo recomendación final para {ticker}...")

    report = fund_manager_agent.analyze(state)
    logs.append(f"[Fund Manager] DICTAMEN FINAL: {report['rating']}")

    return {
        "final_decision": report,
        "workflow_status": "COMPLETED",
        "logs": logs
    }

def build_financial_workflow():
    """Construye y compila el gráfico de estados de LangGraph."""
    workflow = StateGraph(FinancialAnalysisState)

    # Agregar Nodos
    workflow.add_node("ingest", node_ingest_and_reconcile)
    workflow.add_node("quality_analysis", node_quality_analysis)
    workflow.add_node("gatekeeper", node_fundamental_gatekeeper)
    workflow.add_node("news_analysis", node_news_analysis)
    workflow.add_node("join_analisis", node_join_analisis)
    workflow.add_node("technical_analysis", node_technical_analysis)
    workflow.add_node("debate_unit", node_debate_unit)
    workflow.add_node("fund_manager", node_fund_manager)

    # Transiciones / Edges
    workflow.set_entry_point("ingest")

    # Fan-out: el gatekeeper (cálculo puro) y el analista de noticias (tres
    # buscadores de red) no dependen el uno del otro y corren a la vez.
    workflow.add_edge("ingest", "quality_analysis")
    workflow.add_edge("quality_analysis", "gatekeeper")
    workflow.add_edge("quality_analysis", "news_analysis")

    # Unión antes de ramificar. El enrutado condicional cuelga del nodo de
    # unión, no del gatekeeper: así las dos ramas del fan-out han terminado
    # cuando se decide el camino, y `news_report` está disponible tanto en la
    # rama aprobada como en la de rechazo.
    workflow.add_edge("gatekeeper", "join_analisis")
    workflow.add_edge("news_analysis", "join_analisis")

    # Transición Condicional
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
        "passed_fundamental_gatekeeper": False,
        "workflow_status": "INITIALIZED",
        "benchmark_data": benchmark_data or {},
    }
    result = financial_app.invoke(initial_state)
    return result


def cargar_benchmark(ticker: str = "SPY") -> Dict[str, Any]:
    """
    Rentabilidades del índice de referencia, para medir momentum relativo.

    Sin esta referencia, «el valor sube un 20% a doce meses» no distingue
    habilidad de selección de simple exposición al mercado — que es
    precisamente la crítica que el contraste de Monte Carlo del backtest hace
    a la estrategia. Un fallo de red devuelve un dict vacío y el sistema
    degrada a momentum absoluto en lugar de detenerse.
    """
    try:
        datos = fetcher.fetch_all(ticker)
        if datos.get("status") != "SUCCESS":
            return {}
        resumen = datos.get("price_history_summary", {})
        return {
            "ticker": ticker.upper(),
            "change_1m_pct": resumen.get("change_1m_pct"),
            "change_3m_pct": resumen.get("change_3m_pct"),
            "change_6m_pct": resumen.get("change_6m_pct"),
            "change_12m_pct": resumen.get("change_12m_pct"),
            "volatilidad_anual": datos.get("technical", {}).get("volatilidad_anual"),
        }
    except Exception as e:
        print(f"[Benchmark] No se pudo cargar {ticker}: {e}. "
              f"El momentum se calculará en términos absolutos.")
        return {}
