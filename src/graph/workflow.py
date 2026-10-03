"""
Grafo de producción: máquina de estados LangGraph sobre `FinancialAnalysisState`.

FORMA DEL GRAFO

                              ┌─ gatekeeper ────┐
ingest → quality_analysis ────┼─ news_analysis ─┼─ join_analisis → [route] ─┬─ aprobado → technical → estructura → posicionamiento → debate → fund_manager → END
                              └─ regimen ───────┘                          └─ rechazado ────────────────────────────────────────────────────→ fund_manager → END

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

POR QUÉ `posicionamiento` VA DESPUÉS DE `technical` Y NO EN PARALELO
--------------------------------------------------------------------
Porque consume lo que `technical` escribe: `momentum_score` es la tercera pata
de su comparación de tres vías, `sobreextendido` es lo que le prohíbe perseguir
el precio, y `atr` es lo que acota su ajuste. Es una dependencia de datos real,
del mismo tipo que obliga a ordenar —y no paralelizar— los pasos dentro de
`quality.py`. Paralelizarlo no rompería el grafo: produciría otro dictamen.

Y sería paralelismo sin ganancia, por el mismo motivo que `quality_analysis` va
secuencial: el nodo no toca la red. La recolección la hacen las tools de
ingesta. Además, colgado del mismo superstep que `technical` no podría escribir
`workflow_status`, que es un escalar sin reductor.

POR QUÉ `estructura` SE INTERCALA ENTRE `technical` Y `posicionamiento`
-----------------------------------------------------------------------
Misma cadena de dependencias de datos y por eso mismo mismo lugar del grafo:
consume `close` y `atr` del informe técnico —la distancia al soporte solo es
comparable entre valores expresada en unidades de volatilidad— y a su vez
`posicionamiento` consume su `soporte` como candidato de nivel y su
`soporte_lejano` como bandera de sobreextensión.

Su razón de ser es que, hasta ahora, los TRES candidatos de nivel del ajuste de
entrada salían de la cadena de opciones, cuyo histórico es de pago. En el
backtest la cadena está siempre ausente, así que el ajuste era `None` en el 100%
de las señales y la lógica quedaba sin medir. `soporte` es el cuarto candidato y
el único reconstruible point-in-time.

POR QUÉ `regimen` VA EN EL FAN-OUT Y NO EN LA RAMA APROBADA
------------------------------------------------------------
Al contrario que los dos anteriores, no hay ninguna dependencia de datos que lo
fuerce a ir después de nada: consume `regimen_data`, que viaja en el estado
inicial, y `volatilidad_anual`, que produce la ingesta. Se cuelga por tanto del
fan-out, y allí escribe `regimen_report` (clave propia, un solo escritor),
`logs` (`operator.add`) y `messages` (`add_messages`) — los dos últimos con
reductor, que es lo que hace legal el superstep compartido. **No escribe
`workflow_status`**, por el mismo motivo que no lo escribe `news_analysis`.

Colocarlo antes del enrutado condicional deja además su lectura disponible para
los valores RECHAZADOS, que es el mismo argumento por el que `quality_analysis`
va antes del gatekeeper: el régimen de mercado es justo lo que se quiere leer
sobre una empresa que no pasa el filtro.

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
from src.agents.estructura import StructureAnalystAgent
from src.agents.fund_manager import FundManagerAgent
from src.agents.fundamental import FundamentalAnalystAgent
from src.agents.news import NewsAnalystAgent
from src.agents.posicionamiento import PositioningAnalystAgent
from src.agents.quality import QualityAnalystAgent
from src.agents.regimen import RegimeAnalystAgent
from src.agents.technical import TechnicalAnalystAgent
from src.state import FinancialAnalysisState

# Instancias de los agentes. Las clases de datos (fetchers, reconciliador) ya no
# se instancian aquí: viven detrás de las tools de `src/tools/extraccion.py`,
# que son las únicas del sistema que salen a la red.
fundamental_agent = FundamentalAnalystAgent()
quality_agent = QualityAnalystAgent()
technical_agent = TechnicalAnalystAgent()
estructura_agent = StructureAnalystAgent()
posicionamiento_agent = PositioningAnalystAgent()
regimen_agent = RegimeAnalystAgent()
news_agent = NewsAnalystAgent()
debate_agent = DebateUnitAgent()
fund_manager_agent = FundManagerAgent()

# Artefacto del meta-modelo vigente para el LOTE en curso. Vive a nivel de módulo
# y no en el estado porque no es serializable —rompería `daily_selection.json`— y
# porque es común a todos los tickers: meterlo en el estado sería copiarlo una
# vez por valor. Lo fija `run_stock_analysis` y lo limpia al terminar.
_META_ARTEFACTO = None


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

    # Cadena de opciones del propio ticker. Es la ÚNICA fuente del sistema capaz
    # de producir un nivel de precio concreto para la entrada. Su fallo degrada
    # el Analista de Posicionamiento a NO_APLICABLE —entrada al precio de
    # mercado— pero no detiene el análisis, igual que un fallo de la SEC.
    try:
        opt_data = usar_tool("obtener_cadena_opciones", {"ticker": ticker}, traza)
    except Exception as e:
        opt_data = {"disponible": False, "ticker": ticker.upper(),
                    "motivo": f"{type(e).__name__}: {e}", "contratos": [],
                    "agregados": {}, "historico": [], "n_dias_historico": 0}

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
        "options_data": opt_data,
        "workflow_status": "INGESTED",
        "messages": traza.mensajes,
        "logs": [
            f"[Ingesta] Recolectando datos multi-fuente para {ticker}...",
            f"[Reconciliación] Puntuación de confianza: {rec_data['confidence_score']}, "
            f"Fuentes: {rec_data['sources_consulted']}",
            f"[Ingesta] Cadena de opciones: "
            + (f"{len(opt_data.get('contratos', []))} contrato(s), "
               f"{opt_data.get('n_dias_historico', 0)} día(s) de histórico"
               if opt_data.get("disponible")
               else f"no disponible ({opt_data.get('motivo')})"),
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


def node_regimen(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Régimen de Volatilidad. Corre EN PARALELO al gatekeeper y al
    analista de noticias (fan-out desde `quality_analysis`).

    Capa de DECISIÓN por dos vías que solo cierran: `regimen_clasificacion`
    habilita un veto en `aplicar_vetos` —PANICO topa en MANTENER, TENSION en
    COMPRA— y `puerta_regimen` cerrada prohíbe perseguir el precio.

    Como `news_analysis`, escribe sus propias trazas (`logs` y `messages` tienen
    reductor) pero **no** `workflow_status`, que es un escalar sin reductor y lo
    escribe el gatekeeper en este mismo superstep.

    Su dosier NO se descarga aquí: viaja en el estado inicial como
    `regimen_data`, resuelto una sola vez por quien orquesta el lote. El nivel
    del VIX de una fecha es idéntico para las cincuenta empresas de la ejecución.
    """
    ticker = state["ticker"]
    informe = regimen_agent.analyze(state)
    logs = [
        f"[Régimen] Evaluando el régimen de volatilidad del mercado para {ticker}...",
        f"[Régimen] {informe.get('regimen_clasificacion')} | "
        f"{informe.get('serie_volatilidad')} {informe.get('nivel_volatilidad')} | "
        f"z {informe.get('zscore_volatilidad')} | "
        f"curva {informe.get('ratio_curva')} | "
        f"puerta {'abierta' if informe.get('puerta_regimen') else 'CERRADA'}",
    ]
    mensajes = informe.pop("_mensajes", [])
    return {"regimen_report": informe, "logs": logs, "messages": mensajes}


def node_estructura(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Estructura de Precio. Va entre `technical` y `posicionamiento`.

    Capa de DECISIÓN: su `soporte` es el cuarto candidato de nivel para
    `ajustar_precio_entrada` —y el único que no depende de la cadena de
    opciones, de modo que es el único disponible en el backtest— y su
    `soporte_lejano` se une por `or` a `sobreextendido`.
    """
    ticker = state["ticker"]
    informe = estructura_agent.analyze(state)
    soporte = informe.get("soporte")
    d_atr = informe.get("distancia_atr")
    logs = [
        f"[Estructura] Localizando soportes estructurales de {ticker}...",
        f"[Estructura] {informe.get('estructura')} | soporte "
        + ("no disponible" if soporte is None
           else f"{informe.get('soporte_origen')} en ${soporte:.2f}"
                + (f" ({d_atr:.2f} ATR)" if d_atr is not None else ""))
        + (" | SOPORTE LEJANO: prohíbe perseguir el precio"
           if informe.get("soporte_lejano") else ""),
    ]
    return _salida(informe, "estructura_report", logs,
                   workflow_status="STRUCTURE_COMPLETED")


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


def node_posicionamiento(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Analista de Posicionamiento y Precio de Entrada.

    Capa de DECISIÓN, no asesora: `precio_entrada_objetivo` alimenta
    `calcular_niveles_riesgo` en el Fund Manager, y por esa vía el stop, el
    objetivo y el tamaño. `sesgo_macro_clasificacion` habilita además un veto
    que solo puede bajar el rating.

    Solo corre en la rama aprobada, por el mismo motivo que `technical`: el
    precio de entrada óptimo de un valor al que se le va a asignar VENTA no
    significa nada.
    """
    ticker = state["ticker"]
    informe = posicionamiento_agent.analyze(state)
    ajuste = informe.get("ajuste_entrada_pct")

    logs = [
        f"[Posicionamiento] Cruzando futuros, opciones y momentum de {ticker}...",
        f"[Posicionamiento] Macro: {informe.get('sesgo_macro_clasificacion')} | "
        f"Opciones: {informe.get('sesgo_opciones_clasificacion')} | "
        f"Gamma: {informe.get('regimen_gamma')} | "
        f"Entrada: {informe.get('entrada_clasificacion')}"
        + (" (sin ajuste: entrada al precio de mercado)" if ajuste is None
           else f" ({ajuste:+.2%} -> ${informe.get('precio_entrada_objetivo')})"),
    ]
    return _salida(informe, "positioning_report", logs,
                   workflow_status="POSITIONING_COMPLETED")


def node_meta(state: FinancialAnalysisState) -> Dict[str, Any]:
    """
    Probabilidad del meta-modelo para este valor.

    Va entre el debate y el Fund Manager por una dependencia de datos estricta:
    consume TODOS los informes anteriores —calidad, técnico, estructura, régimen,
    posicionamiento— para construir su vector de variables, y el Fund Manager
    consume su salida para producir `factor_meta`. Colocarlo antes daría un
    vector incompleto; colocarlo después llegaría tarde.

    Solo corre en la rama aprobada, por el mismo motivo que el posicionamiento:
    la probabilidad de que acierte una compra que no se va a hacer no significa
    nada.

    Sin artefacto escribe `{}`, y el Fund Manager lo traduce a factor 1.0 con
    `evaluable=False`. No se inventa una probabilidad.
    """
    if _META_ARTEFACTO is None:
        return {"meta_data": {}, "logs": []}
    from src.meta.variables import variables_de_senal
    p = _META_ARTEFACTO.probabilidad(variables_de_senal(state))
    if p is None:
        return {"meta_data": {},
                "logs": ["[Meta] Sin probabilidad: faltan variables en el estado."]}
    return {
        "meta_data": {"probabilidad": p, "tasa_base": _META_ARTEFACTO.tasa_base,
                      "entrenado_hasta": _META_ARTEFACTO.entrenado_hasta,
                      "n_muestras": _META_ARTEFACTO.n_muestras},
        "logs": [f"[Meta] Probabilidad de acierto {p:.1%} frente a una tasa base de "
                 f"{_META_ARTEFACTO.tasa_base:.1%} "
                 f"(modelo de {_META_ARTEFACTO.n_muestras} etiquetas hasta "
                 f"{_META_ARTEFACTO.entrenado_hasta})."],
    }


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
    workflow.add_node("regimen", node_regimen)
    workflow.add_node("join_analisis", node_join_analisis)
    workflow.add_node("technical_analysis", node_technical_analysis)
    workflow.add_node("estructura", node_estructura)
    workflow.add_node("posicionamiento", node_posicionamiento)
    workflow.add_node("meta", node_meta)
    workflow.add_node("debate_unit", node_debate_unit)
    workflow.add_node("fund_manager", node_fund_manager)

    workflow.set_entry_point("ingest")

    # Fan-out: el gatekeeper (cálculo puro) y el analista de noticias (tres
    # buscadores de red) no dependen el uno del otro y corren a la vez.
    workflow.add_edge("ingest", "quality_analysis")
    workflow.add_edge("quality_analysis", "gatekeeper")
    workflow.add_edge("quality_analysis", "news_analysis")
    # Tercera rama del fan-out: el régimen de volatilidad no depende de nada que
    # produzcan las otras dos, y colocarlo aquí lo deja disponible también en la
    # rama de rechazo.
    workflow.add_edge("quality_analysis", "regimen")

    # Unión antes de ramificar. Ver el encabezado del módulo.
    workflow.add_edge("gatekeeper", "join_analisis")
    workflow.add_edge("news_analysis", "join_analisis")
    workflow.add_edge("regimen", "join_analisis")

    workflow.add_conditional_edges(
        "join_analisis",
        route_after_gatekeeper,
        {
            "technical_analysis": "technical_analysis",
            "fund_manager": "fund_manager"
        }
    )

    # La estructura y el posicionamiento se intercalan entre el técnico y el
    # debate, en ese orden y por una cadena de dependencias de datos: la
    # estructura consume el `close` y el `atr` del técnico, y el posicionamiento
    # consume el `soporte` de la estructura como candidato de nivel. El precio de
    # entrada queda cerrado ANTES de que el debate argumente sobre él.
    workflow.add_edge("technical_analysis", "estructura")
    workflow.add_edge("estructura", "posicionamiento")
    workflow.add_edge("posicionamiento", "debate_unit")
    # El meta-modelo va entre el debate y el Fund Manager: consume todos los
    # informes anteriores y su probabilidad tiene que estar en el estado cuando
    # el Fund Manager la convierte en `factor_meta`.
    workflow.add_edge("debate_unit", "meta")
    workflow.add_edge("meta", "fund_manager")
    workflow.add_edge("fund_manager", END)

    return workflow.compile()


# Instancia del grafo compilado
financial_app = build_financial_workflow()


def run_stock_analysis(ticker: str,
                       benchmark_data: Dict[str, Any] = None,
                       macro_data: Dict[str, Any] = None,
                       reflexion_data: Dict[str, Any] = None,
                       regimen_data: Dict[str, Any] = None,
                       meta_artefacto: Any = None) -> FinancialAnalysisState:
    """
    Ejecuta el pipeline completo de un ticker.

    `benchmark_data` es opcional y contiene las rentabilidades del índice de
    referencia (ver `cargar_benchmark`). Cuando está, el Analista Técnico
    calcula momentum RELATIVO; sin él, momentum absoluto, y lo declara en el
    informe. No se descarga aquí dentro para no repetir la misma petición una
    vez por ticker: quien orquesta el lote la hace una sola vez.

    `macro_data` sigue exactamente el mismo patrón y por el mismo motivo, solo
    que más acusado: el dosier COT no es por ticker —el sesgo del futuro del
    petróleo es idéntico para todas las energéticas del lote— y se publica una
    vez por semana. Descargarlo dentro del grafo sería pedir el mismo fichero de
    la CFTC una vez por valor analizado.

    `reflexion_data` es el tercer caso del mismo patrón: la tabla de expectativa
    histórica por estilo y momentum es común a todo el lote, se consolida una
    vez y cada Fund Manager busca su celda. Sin ella la capa se declara
    inaplicable y el factor es 1.0, que es el estado de una instalación recién
    puesta en marcha y no un error.

    `regimen_data` es el cuarto, y el más acusado de todos: el nivel del VIX de
    una fecha es literalmente el mismo número para las cincuenta empresas del
    lote. Sin él el Analista de Régimen declara NO_APLICABLE, deja la puerta
    ABIERTA y no dispara ningún veto — abierta y no cerrada, porque cerrarla por
    precaución convertiría una laguna de cobertura en una restricción de
    cartera, que es la forma inversa del defecto «ausencia ≠ cero».
    """
    initial_state: FinancialAnalysisState = {
        "ticker": ticker.upper(),
        "logs": [],
        "messages": [],
        "passed_fundamental_gatekeeper": False,
        "workflow_status": "INITIALIZED",
        "benchmark_data": benchmark_data or {},
        "futures_data": macro_data or {},
        "reflexion_data": reflexion_data or {},
        "regimen_data": regimen_data or {},
    }
    # El artefacto viaja a NIVEL DE MÓDULO y no dentro del estado, por dos
    # motivos: no es serializable —`daily_selection.json` lo rompería— y es
    # común a todo el lote, así que meterlo en el estado sería copiarlo una vez
    # por ticker. Es el mismo patrón que `HistoricalReplayer.meta_artefacto`.
    #
    # Se fija ANTES de invocar el grafo porque `node_meta` lo lee, y ese nodo va
    # entre el debate y el Fund Manager: la probabilidad tiene que estar en el
    # estado cuando el Fund Manager la convierte en `factor_meta`.
    global _META_ARTEFACTO
    _META_ARTEFACTO = meta_artefacto
    try:
        return financial_app.invoke(initial_state)
    finally:
        _META_ARTEFACTO = None


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


def cargar_contexto_macro(as_of: str = None) -> Dict[str, Any]:
    """
    Dosier de posicionamiento en futuros, compartido por todo el lote.

    Hermana de `cargar_benchmark` y con la misma disciplina: se resuelve UNA vez
    por ejecución, un fallo devuelve un dict vacío y el Analista de
    Posicionamiento degrada su pata macro a NO_APLICABLE en lugar de detenerse.

    No se llama desde el grafo a propósito. El conjunto de contratos es cerrado
    y pequeño (`SECTOR_A_FUTURO` más el de índice), así que son media docena de
    descargas por ejecución en vez de una por ticker.
    """
    from src.tools.extraccion import obtener_contexto_macro
    try:
        return obtener_contexto_macro.invoke({"as_of": as_of})
    except Exception as e:
        print(f"[Macro] No se pudo cargar el posicionamiento en futuros: {e}. "
              f"El sesgo macro se declarará no aplicable.")
        return {}


def cargar_regimen(as_of: str = None) -> Dict[str, Any]:
    """
    Dosier de régimen de volatilidad, compartido por todo el lote.

    Hermana de `cargar_benchmark` y `cargar_contexto_macro`, con la misma
    disciplina: se resuelve UNA vez por ejecución, un fallo devuelve un dict
    vacío y el Analista de Régimen degrada a NO_APLICABLE con la puerta abierta
    en lugar de detenerse.

    No se llama desde el grafo a propósito. El nivel del VIX de una fecha es
    idéntico para todos los valores analizados, así que descargarlo dentro sería
    pedir la misma serie de FRED una vez por ticker.
    """
    from src.tools.extraccion import obtener_contexto_regimen
    try:
        return obtener_contexto_regimen.invoke({"as_of": as_of})
    except Exception as e:
        print(f"[Régimen] No se pudo cargar la serie de volatilidad: {e}. "
              f"El régimen se declarará no aplicable y no se aplicará ningún veto.")
        return {}
