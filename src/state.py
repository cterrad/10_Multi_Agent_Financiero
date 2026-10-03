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

    # Posicionamiento en derivados. `futures_data` es el dosier macro COMPARTIDO
    # por todos los tickers de la ejecucion: el sesgo del futuro del petroleo es
    # el mismo para todas las energeticas del lote y el COT se publica una vez
    # por semana, asi que lo resuelve el orquestador UNA vez y viaja en el estado
    # inicial, igual que `benchmark_data`. `options_data` si es por ticker y la
    # escribe el nodo de ingesta.
    futures_data: Dict[str, Any]
    options_data: Dict[str, Any]

    # Dosier de régimen de volatilidad (VIX y VIX a 3 meses, vía ALFRED). Tercer
    # caso del mismo patrón que `futures_data` y `benchmark_data`: el nivel del
    # VIX de una fecha es idéntico para las cincuenta empresas del lote, así que
    # lo resuelve el orquestador UNA vez y viaja en el estado inicial.
    #
    # A diferencia de `options_data`, SÍ es reconstruible point-in-time: ALFRED
    # devuelve la serie tal y como se conocía en una fecha y cada observación
    # trae su fecha de publicación. De este bloque el backtest mide el 100% de
    # la lógica, no la mitad.
    regimen_data: Dict[str, Any]

    # Dosier de la memoria de reflexión: la rentabilidad en exceso sobre el
    # índice que siguió históricamente a cada configuración de señal, contando
    # SOLO las observaciones ya desenlazadas en la fecha de análisis. NO es por
    # ticker —la tabla completa son unas decenas de entradas y cada agente busca
    # su celda—, así que lo resuelve el orquestador una vez por ejecución y
    # viaja en el estado inicial, igual que `futures_data` y `benchmark_data`.
    #
    # SÍ es variable de decisión: el Fund Manager lo convierte en
    # `factor_reflexion` (recorta el peso) y en un veto que solo baja el rating.
    reflexion_data: Dict[str, Any]

    # Probabilidad que el meta-modelo asigna a ESTA señal, más la tasa base con
    # la que se entrenó. NO es por lote —cada valor tiene la suya— pero tampoco
    # la calcula ningún agente: la inyecta quien orquesta, porque cargar el
    # artefacto y evaluarlo es responsabilidad de `src/meta/`, no del grafo.
    #
    # SÍ es variable de decisión: el Fund Manager la convierte en `factor_meta`,
    # que recorta el peso en la capa de cartera. Vacío = capa inactiva y factor
    # 1.0, que es el estado de una instalación sin artefacto entrenado.
    meta_data: Dict[str, Any]

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

    # Dictamen del Analista de Posicionamiento y Precio de Entrada. A DIFERENCIA
    # de `news_report`, SI es variable de decision: `precio_entrada_objetivo`
    # alimenta `calcular_niveles_riesgo` en el Fund Manager, y por esa via el
    # stop, el objetivo, el ratio riesgo/recompensa y el tamano de la posicion;
    # `sesgo_macro_clasificacion` habilita ademas un veto que solo baja.
    #
    # El NIVEL de precio tiene ahora DOS proveedores: la cadena de opciones
    # (soporte de open interest, max pain, gamma flip) y el soporte estructural
    # que aporta `estructura_report`. Solo el segundo es reconstruible
    # point-in-time, así que en el backtest el ajuste de entrada se apoya en
    # soportes de PRECIO y no en open interest. La diferencia se declara en
    # `build_limitations()` en vez de promediarse.
    positioning_report: Dict[str, Any]

    # Dictamen del Analista de Estructura de Precio. SÍ es variable de decisión
    # por dos vías, ambas de las que solo cierran: `soporte` entra como
    # candidato de nivel en `ajustar_precio_entrada`, y `soporte_lejano` se une
    # por `or` a `sobreextendido` y prohíbe perseguir el precio.
    estructura_report: Dict[str, Any]

    # Dictamen del Analista de Régimen de Volatilidad. SÍ es variable de
    # decisión por dos vías: `regimen_clasificacion` habilita un veto en
    # `aplicar_vetos` (PANICO topa en MANTENER, TENSION en COMPRA) y
    # `puerta_regimen` cerrada prohíbe perseguir el precio. Ambas solo bajan.
    regimen_report: Dict[str, Any]

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
