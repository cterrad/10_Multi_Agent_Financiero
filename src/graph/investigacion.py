"""
Grafo del agente investigador: bucle ReAct canónico.

    investigador ──(hay tool_calls)──> tools ──> investigador
         │
         └──(sin tool_calls)──> END

Es literalmente la forma de `ReAct.py` del curso: un nodo que llama al modelo,
un `ToolNode` que ejecuta lo que el modelo pidió, una arista condicional que
mira si el último mensaje trae `tool_calls`, y el retorno de tools al agente.

SEPARADO DE `financial_app` A PROPÓSITO
---------------------------------------
No comparte grafo con el pipeline de decisión y no comparte estado más allá de
lo que se le pase. Si estuviera dentro, una vuelta del bucle podría escribir en
canales que los agentes deterministas leen, y la frontera entre «el modelo
explica» y «el modelo decide» dejaría de ser comprobable de un vistazo.

TOPE DE RECURSIÓN
-----------------
`recursion_limit` acota el bucle en el propio grafo, además del tope de vueltas
del agente. Un ReAct que no converge encadena llamadas al proveedor hasta agotar
la cuota, y el ejemplo del curso no lo contempla porque allí no hay factura.
"""

from typing import Annotated, Any, Dict, List, Optional, Sequence, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.agents.investigador import (
    LIMITE_VUELTAS,
    SYSTEM_INVESTIGADOR,
    modelo_con_tools,
    resumen_de_traza,
)
from src.config import texto_de_respuesta_llm
from src.tools import TOOLS_LECTURA
from src.utils.logging_agentes import logger_de_agente


class EstadoInvestigacion(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]


def _nodo_investigador(state: EstadoInvestigacion) -> Dict[str, Any]:
    """Llama al modelo con la conversación completa. Él decide si usa tools."""
    modelo = modelo_con_tools()
    respuesta = modelo.invoke(list(state["messages"]))
    return {"messages": [respuesta]}


# Turnos vacíos que se toleran antes de rendirse. Ver `_debe_continuar`.
MAX_TURNOS_VACIOS = 2

PETICION_DE_CIERRE = (
    "Ya tienes los datos que pediste. Escribe ahora tu respuesta final en texto, "
    "citando los valores concretos que has obtenido. No llames a más herramientas."
)


def _debe_continuar(state: EstadoInvestigacion) -> str:
    """
    Decide si el bucle sigue, insiste o termina.

    El caso obvio: si el modelo pidió tools, se ejecutan y se vuelve a él.

    El caso que `ReAct.py` no contempla: Gemini cierra a veces un turno con
    `content` compuesto solo por un bloque de PENSAMIENTO —texto vacío más una
    firma— sin `tool_calls`. Con la condición del curso («¿hay tool_calls? si no,
    fin») ese turno se tomaba por respuesta final y `investigar()` devolvía una
    cadena vacía habiendo consultado cuatro tools. Se observó analizando DOCN:
    el modelo había calculado el Altman correctamente y la respuesta se perdía
    en el último paso.

    Un turno sin tools y sin texto no es una respuesta: es un modelo que aún no
    ha terminado. Se le devuelve el control. El reintento está acotado por
    `MAX_TURNOS_VACIOS` y, por encima, por el `recursion_limit` del grafo: sin
    tope, un modelo que no converge encadenaría llamadas hasta agotar la cuota.
    """
    ultimo = state["messages"][-1]
    if getattr(ultimo, "tool_calls", None):
        return "continuar"

    if texto_de_respuesta_llm(ultimo):
        return "fin"

    # El tope se cuenta sobre las peticiones de cierre ya enviadas y no sobre
    # turnos consecutivos: `_nodo_reencauzar` intercala un HumanMessage, así que
    # los turnos vacíos nunca quedan seguidos y contarlos así daría siempre 1 —
    # un bucle infinito hasta el `recursion_limit`.
    insistencias = sum(1 for m in state["messages"]
                       if isinstance(m, HumanMessage) and m.content == PETICION_DE_CIERRE)
    return "reintentar" if insistencias < MAX_TURNOS_VACIOS else "fin"


def _nodo_reencauzar(state: EstadoInvestigacion) -> Dict[str, Any]:
    """
    Pide explícitamente el cierre tras un turno de solo pensamiento.

    No se puede volver al modelo sin más: Gemini rechaza una petición cuyo último
    turno sea del propio modelo —«does not support model prefilling. The final
    request turn must be a user message or a function response»—, que es
    exactamente con lo que reventó el primer intento de reintento. Hay que
    intercalar un turno de usuario, y ya que hace falta, se aprovecha para
    decirle qué se espera de él.
    """
    return {"messages": [HumanMessage(content=PETICION_DE_CIERRE)]}


def construir_grafo_investigacion():
    grafo = StateGraph(EstadoInvestigacion)
    grafo.add_node("investigador", _nodo_investigador)
    grafo.add_node("tools", ToolNode(TOOLS_LECTURA))
    grafo.add_node("reencauzar", _nodo_reencauzar)
    grafo.set_entry_point("investigador")
    grafo.add_conditional_edges("investigador", _debe_continuar,
                                {"continuar": "tools",
                                 "reintentar": "reencauzar",
                                 "fin": END})
    grafo.add_edge("tools", "investigador")
    grafo.add_edge("reencauzar", "investigador")
    return grafo.compile()


def investigar(ticker: str, pregunta: str) -> Dict[str, Any]:
    """
    Responde una pregunta sobre una compañía consultando las tools reales.

    Devuelve `research_report`: texto, la lista de tools que el modelo invocó y
    la traza de mensajes. NO altera ninguna variable de decisión — ver el
    encabezado de `src/agents/investigador.py`.
    """
    log = logger_de_agente("investigador", ticker)
    log.info("inicio", extra={"evento": "inicio", "pregunta": pregunta})

    app = construir_grafo_investigacion()
    entrada = {
        "messages": [
            SystemMessage(content=SYSTEM_INVESTIGADOR),
            HumanMessage(content=f"Compañía: {ticker.upper()}.\n\nPregunta: {pregunta}"),
        ]
    }
    # Cada vuelta del bucle son dos supersteps (investigador + tools), más el
    # turno final sin tools: de ahí el 2n+1.
    resultado = app.invoke(entrada, {"recursion_limit": 2 * LIMITE_VUELTAS + 1})

    resumen = resumen_de_traza(list(resultado["messages"]))
    if not resumen["respuesta"]:
        # Se declara en vez de devolver una cadena vacía que el informe
        # imprimiría como si el agente no tuviera nada que decir.
        resumen["respuesta"] = (
            f"El modelo consultó {resumen['n_llamadas_tool']} herramienta(s) pero no "
            f"produjo texto final. Vuelve a preguntar, preferiblemente acotando más la "
            f"pregunta; los datos consultados están en la traza de mensajes."
        )
        log.warning("sin_texto_final", extra={"evento": "llm_sin_texto",
                                              "tools": resumen["tools_invocadas"]})
    log.info(f"respondido tras {resumen['n_llamadas_tool']} llamada(s) a tools",
             extra={"evento": "dictamen",
                    "tools": resumen["tools_invocadas"],
                    "n_mensajes": resumen["n_mensajes"]})

    return {
        "ticker": ticker.upper(),
        "pregunta": pregunta,
        "respuesta": resumen["respuesta"],
        "tools_invocadas": resumen["tools_invocadas"],
        "n_llamadas_tool": resumen["n_llamadas_tool"],
        # Marca explícita, igual que en el informe de noticias.
        "advisory_only": True,
        # El contenido pasa por `texto_de_respuesta_llm` y no por `str()`: los
        # turnos del modelo llegan como lista de bloques, y volcarlos con `str()`
        # imprimiría `[{'type': 'text', ...}]` en el informe — el mismo defecto
        # que ese helper existe para cortar en los otros agentes.
        "mensajes": [
            {"tipo": type(m).__name__,
             "contenido": (m.content if isinstance(m.content, str)
                           else (texto_de_respuesta_llm(m) or "")),
             "tool_calls": [tc.get("name") for tc in (getattr(m, "tool_calls", None) or [])]}
            for m in resultado["messages"]
        ],
    }
