from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from src.state import FinancialAnalysisState
from src.data.fetcher import DataFetcher
from src.data.sec_edgar import SECEdgarClient
from src.data.finnhub_client import FinnhubClient
from src.data.reconciler import DataReconciler
from src.agents.fundamental import FundamentalAnalystAgent
from src.agents.technical import TechnicalAnalystAgent
from src.agents.debate import DebateUnitAgent
from src.agents.fund_manager import FundManagerAgent

# Instancias de componentes
fetcher = DataFetcher()
sec_client = SECEdgarClient()
finnhub_client = FinnhubClient()
reconciler = DataReconciler()

fundamental_agent = FundamentalAnalystAgent()
technical_agent = TechnicalAnalystAgent()
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
    workflow.add_node("gatekeeper", node_fundamental_gatekeeper)
    workflow.add_node("technical_analysis", node_technical_analysis)
    workflow.add_node("debate_unit", node_debate_unit)
    workflow.add_node("fund_manager", node_fund_manager)

    # Transiciones / Edges
    workflow.set_entry_point("ingest")
    workflow.add_edge("ingest", "gatekeeper")

    # Transición Condicional
    workflow.add_conditional_edges(
        "gatekeeper",
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

def run_stock_analysis(ticker: str) -> FinancialAnalysisState:
    """Función de alto nivel para ejecutar el pipeline de un ticker."""
    initial_state: FinancialAnalysisState = {
        "ticker": ticker.upper(),
        "logs": [],
        "passed_fundamental_gatekeeper": False,
        "workflow_status": "INITIALIZED"
    }
    result = financial_app.invoke(initial_state)
    return result
