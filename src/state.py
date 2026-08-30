import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class FinancialAnalysisState(TypedDict, total=False):
    ticker: str
    company_name: str
    sector: str
    industry: str

    # ------------------------------------------------------------------ #
    # Canales con reductor
    # ------------------------------------------------------------------ #
    # `messages` es la traza tipada de la ejecución: HumanMessage con la tarea
    # que recibe cada agente, AIMessage con las tool_calls que emite,
    # ToolMessage con lo que cada tool devolvió, y el AIMessage final con el
    # texto redactado. Es lo que permite responder «de dónde salió esta cifra»
    # sin releer el código.
    #
    # El reductor `add_messages` NO es decorativo. Antes este TypedDict no
    # declaraba ninguno, y por eso dos nodos en el mismo superstep —el
    # gatekeeper y el analista de noticias, que corren en paralelo— no podían
    # escribir el mismo canal sin reventar con `InvalidUpdateError: can receive
    # only one value per step`. Con reductor, ambos anexan y LangGraph fusiona.
    #
    # `add_messages` deduplica por `id`: los mensajes construidos a mano en
    # `AgenteBase.usar_tool()` llevan uno único. Reutilizar un id hace
    # DESAPARECER mensajes de la traza sin error visible.
    messages: Annotated[List[BaseMessage], add_messages]

    # Resumen legible para el informe. `operator.add` concatena, así que cada
    # nodo debe devolver SOLO sus líneas nuevas, nunca la lista entera: devolver
    # el acumulado la duplicaría en silencio.
    logs: Annotated[List[str], operator.add]

    # ------------------------------------------------------------------ #
    # Ingesta y datos reconciliados
    # ------------------------------------------------------------------ #
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

    # Referencia de mercado (SPY por defecto). La usa el Analista Técnico para
    # calcular momentum RELATIVO en lugar de absoluto: sin benchmark, «el valor
    # sube un 20%» no dice si eso es habilidad o simplemente mercado. Es
    # opcional; si falta, el técnico degrada a momentum absoluto y lo declara.
    benchmark_data: Dict[str, Any]

    # ------------------------------------------------------------------ #
    # Informes por etapa
    # ------------------------------------------------------------------ #
    fundamental_report: Dict[str, Any]
    # Dictamen del Analista de Calidad y Valoración: puntuaciones de calidad,
    # valoración, crecimiento y solvencia, etiqueta de estilo (VALOR /
    # CRECIMIENTO / GARP / CALIDAD_COMPUESTA / ...) y convicción fundamental.
    # A DIFERENCIA de `news_report`, SÍ es variable de decisión: el Fund
    # Manager cruza `conviccion_fundamental` con el momentum para el rating y
    # el tamaño de posición. Por eso el backtest debe ejecutarlo.
    quality_report: Dict[str, Any]
    technical_report: Dict[str, Any]
    news_report: Dict[str, Any]
    debate_report: Dict[str, Any]

    # Dictamen del agente investigador ReAct. Capa ASESORA, igual que las
    # noticias: es texto y solo texto, no entra en ninguna decisión, y el grafo
    # de producción no lo produce — se pide bajo demanda desde `cli.py
    # --investigar`. `test_research_report_does_not_alter_decision` fija esa
    # premisa: si alguna vez alimenta al rating, ese test debe fallar.
    research_report: Dict[str, Any]

    # ------------------------------------------------------------------ #
    # Decisión final
    # ------------------------------------------------------------------ #
    # Rating categories: "COMPRA FUERTE", "COMPRA", "MANTENER", "VENTA",
    # "VENTA FUERTE", más "SIN OPINION" cuando los datos no permiten evaluar.
    final_decision: Dict[str, Any]

    # ------------------------------------------------------------------ #
    # Control de flujo
    # ------------------------------------------------------------------ #
    passed_fundamental_gatekeeper: bool
    workflow_status: str
    error_message: Optional[str]
