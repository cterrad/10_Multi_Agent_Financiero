from typing import TypedDict, Dict, Any, Optional, List

class FinancialAnalysisState(TypedDict, total=False):
    ticker: str
    company_name: str
    sector: str
    industry: str
    
    # Ingestion & Reconciled Raw Data
    raw_data: Dict[str, Any]
    sec_edgar_data: Dict[str, Any]
    finnhub_data: Dict[str, Any]
    yfinance_data: Dict[str, Any]
    reconciliation_data: Dict[str, Any]
    
    # Noticias (capa asesora): `news_data` es el dosier bruto ya deduplicado
    # por src/data/news/aggregator.py; `news_report` es el dictamen determinista
    # del NewsAnalystAgent. No intervienen en el rating ni en el sizing (v1) y
    # están ausentes en el backtest — ver src/backtest/replay.py.
    news_data: Dict[str, Any]

    # Stage Reports
    fundamental_report: Dict[str, Any]
    technical_report: Dict[str, Any]
    news_report: Dict[str, Any]
    debate_report: Dict[str, Any]
    
    # Final Manager Decision
    # Rating categories: "COMPRA FUERTE", "COMPRA", "MANTENER", "VENTA", "VENTA FUERTE"
    final_decision: Dict[str, Any]
    
    # State Control
    passed_fundamental_gatekeeper: bool
    workflow_status: str
    logs: List[str]
    error_message: Optional[str]
