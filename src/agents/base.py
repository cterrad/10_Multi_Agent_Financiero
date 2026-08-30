"""
Clase base de los agentes: tools, mensajes tipados y traza.

QUÉ CENTRALIZA
--------------
Los seis agentes repetían el mismo bloque de doce líneas: pedir el LLM,
envolver la llamada en try/except, aplanar la respuesta con
`texto_de_respuesta_llm`, conservar el resumen determinista si no había texto, e
imprimir el error por consola. Seis copias del mismo código, y cada una con su
propio matiz en el mensaje de error.

Ahora eso vive en `_redactar()` y los agentes solo declaran su system prompt y
cómo construyen el prompt de usuario.

EL PATRÓN DE EJECUCIÓN DE TOOLS
-------------------------------
`usar_tool()` es el `take_action` de `RAG_Agent.py` con una diferencia que lo es
todo: allí los `tool_calls` los emitía el modelo, aquí los emite el código. La
traza resultante es idéntica en forma —AIMessage con `tool_calls`, ToolMessage
con el resultado y su `tool_call_id`— pero el plan de llamadas es determinista,
así que el backtest sigue siendo reproducible y gratuito.

Esa es la razón de que el sistema pueda tener tools sin romper su invariante:
la forma de un agente ReAct, la sustancia de una función pura.

ORDEN DE LOS PASOS EN `analyze()`
---------------------------------
`decidir()` va SIEMPRE antes que `_redactar()`, y no es casual: cuando el LLM
interviene, todas las variables de decisión ya están fijadas y escritas en el
informe. El modelo no puede alcanzarlas ni aunque lo intentara, porque lo único
que se le asigna es la clave de texto que devuelve `campo_texto`.
"""

from __future__ import annotations

import json
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from src.config import get_llm, texto_de_respuesta_llm
from src.state import FinancialAnalysisState
from src.tools import obtener_tool
from src.utils.logging_agentes import logger_de_agente


class Traza:
    """
    Acumulador de mensajes y eventos de un agente durante una ejecución.

    Es deliberadamente un objeto y no una lista suelta: además de los mensajes
    guarda el registro de tools con sus tiempos, que es lo que el informe
    detallado imprime y lo que permite ver qué parte del análisis fue cara.
    """

    def __init__(self, agente: str, ticker: str):
        self.agente = agente
        self.ticker = (ticker or "?").upper()
        self.mensajes: List[BaseMessage] = []
        self.tools: List[Dict[str, Any]] = []
        self.log = logger_de_agente(agente, self.ticker)
        self._n = 0

    def añadir(self, mensaje: BaseMessage) -> BaseMessage:
        # `add_messages` deduplica por id, así que cada mensaje necesita el suyo:
        # sin id propio, dos mensajes idénticos se fusionarían y la traza
        # perdería pasos.
        #
        # El id es SECUENCIAL y no un UUID a propósito. Con UUID, dos ejecuciones
        # del mismo análisis producían informes distintos —lo detectó
        # `test_el_agente_es_reproducible`— y `daily_selection.json` cambiaba
        # entero en cada pasada, volviendo inútil cualquier diff. La unicidad
        # está garantizada porque cada agente corre una sola vez por invocación
        # del grafo y el prefijo lleva su nombre.
        if not getattr(mensaje, "id", None):
            self._n += 1
            mensaje.id = f"{self.agente}-{self._n:02d}"
        self.mensajes.append(mensaje)
        return mensaje

    def a_dict(self) -> Dict[str, Any]:
        """
        Forma serializable, para el informe detallado y `daily_selection.json`.

        NO incluye duraciones. La traza del informe responde a «qué se calculó y
        con qué datos», que es reproducible; el coste en milisegundos es
        irrepetible por naturaleza y vive en el JSONL de
        `src/utils/logging_agentes.py`, que es donde sirve para algo.
        """
        return {
            "agente": self.agente,
            "ticker": self.ticker,
            "n_mensajes": len(self.mensajes),
            "tools": [{k: v for k, v in t.items() if k != "duracion_ms"}
                      for t in self.tools],
            "mensajes": [
                {
                    "tipo": m.__class__.__name__,
                    "id": getattr(m, "id", None),
                    "contenido": m.content if isinstance(m.content, str) else str(m.content),
                    "tool_calls": [
                        {"name": tc.get("name"), "args": tc.get("args"), "id": tc.get("id")}
                        for tc in (getattr(m, "tool_calls", None) or [])
                    ],
                    "tool_call_id": getattr(m, "tool_call_id", None),
                    "name": getattr(m, "name", None),
                }
                for m in self.mensajes
            ],
        }


class AgenteBase(ABC):
    """Agente determinista con traza tipada. Subclasear implementando `decidir`."""

    #: Nombre corto, usado en el logger y en la traza.
    nombre: str = "agente"
    #: Descripción del papel, para el informe.
    rol: str = ""
    #: Instrucción permanente que se envía como `SystemMessage`.
    system_prompt: str = ""
    #: Clave del informe que el LLM puede sobrescribir. La ÚNICA.
    campo_texto: str = "summary"

    # ------------------------------------------------------------------ #
    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        """
        Punto de entrada. Firma conservada: es el contrato que consumen
        `src/graph/workflow.py` y `src/backtest/replay.py`, y cambiarlo obligaría
        a tocar el motor histórico, que por diseño no debe conocer a los agentes
        más que por esta llamada.
        """
        ticker = state.get("ticker", "UNKNOWN")
        traza = Traza(self.nombre, ticker)
        traza.añadir(HumanMessage(content=self.tarea(state)))
        traza.log.info("inicio", extra={"evento": "inicio"})

        informe = self.decidir(state, traza)
        informe = self._redactar(state, informe, traza)

        traza.log.info(self.resumen_de_log(informe),
                       extra={"evento": "dictamen",
                              "n_tools": len(traza.tools),
                              "duracion_tools_ms": round(
                                  sum(t.get("duracion_ms", 0) for t in traza.tools), 1)})

        # Prefijo `_` porque no es un dato de análisis sino la traza de cómo se
        # produjo. El informe lo imprime; ningún agente lo consume.
        informe["_traza"] = traza.a_dict()
        informe["_mensajes"] = traza.mensajes
        return informe

    # ------------------------------------------------------------------ #
    def usar_tool(self, nombre: str, args: Dict[str, Any], traza: Traza) -> Any:
        """Ejecuta una tool dejando traza. Ver `usar_tool` a nivel de módulo."""
        return usar_tool(nombre, args, traza)

    # ------------------------------------------------------------------ #
    def _obtener_llm(self):
        """
        Resuelve `get_llm` en el MÓDULO DE LA SUBCLASE, no en el de esta base.

        No es rebuscamiento: `from src.config import get_llm` fija el nombre en
        el espacio del importador, y todo el sistema se apoya en poder
        sustituirlo módulo a módulo. `disable_llm()` (src/backtest/replay.py)
        hace `mod.get_llm = lambda: None` sobre cada módulo de agente para
        forzar el motor determinista en el backtest, y `tests/test_llm_texto.py`
        hace lo mismo para inyectar sus dobles.

        Si esta base llamara a su propio `get_llm` importado, esos parches no
        surtirían efecto: el backtest abriría llamadas de red y de coste en
        mitad de una ejecución offline, y los tests del contrato de texto
        pasarían sin comprobar nada. De ahí la indirección.
        """
        modulo = sys.modules.get(type(self).__module__)
        return getattr(modulo, "get_llm", get_llm)()

    # ------------------------------------------------------------------ #
    def _redactar(self, state: FinancialAnalysisState, informe: Dict[str, Any],
                  traza: Traza) -> Dict[str, Any]:
        """
        Único punto del agente donde interviene el LLM.

        Tres propiedades que hay que preservar si alguna vez se toca:

          · Se llama DESPUÉS de `decidir()`, con todas las variables ya fijadas.
          · Solo escribe `self.campo_texto`. Nada más del informe se toca.
          · Cualquier fallo del proveedor degrada al texto determinista en vez de
            propagar: un 503 de la API no puede impedir que se emita un dictamen
            que ya está calculado.

        Se invoca con una LISTA de mensajes (`SystemMessage` + `HumanMessage`),
        no con una cadena. Los dobles de test declaran `invoke(self, prompt)` con
        un solo posicional, así que la lista los satisface sin cambios.
        """
        determinista = informe.get(self.campo_texto)
        informe.setdefault("resumen_determinista", determinista)

        llm = self._obtener_llm()
        if not llm:
            traza.añadir(AIMessage(content=str(determinista or "")))
            return informe

        try:
            from langchain_core.messages import SystemMessage
            prompt = self.prompt_usuario(state, informe)
            t0 = time.perf_counter()
            texto = texto_de_respuesta_llm(llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt),
            ]))
            ms = round((time.perf_counter() - t0) * 1000, 1)
            if texto:
                informe[self.campo_texto] = texto
                traza.log.info("llm_ok", extra={"evento": "llm", "duracion_ms": ms,
                                                "caracteres": len(texto)})
            else:
                traza.log.warning("llm_sin_texto", extra={"evento": "llm", "duracion_ms": ms})
        except Exception as exc:
            err = str(exc)
            if "Expecting ',' delimiter" in err or "JSONDecodeError" in err:
                aviso = ("el proveedor devolvió una respuesta no válida (modelo "
                         "restringido, token inválido o error del servidor); se conserva "
                         "el resumen determinista")
            else:
                aviso = f"{type(exc).__name__}: {exc}"
            traza.log.warning("llm_error", extra={"evento": "llm_error", "error": aviso})

        traza.añadir(AIMessage(content=str(informe.get(self.campo_texto) or "")))
        return informe

    # ------------------------------------------------------------------ #
    # A implementar por cada agente
    # ------------------------------------------------------------------ #
    @abstractmethod
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        """
        Todo el análisis determinista. Debe dejar el informe COMPLETO, incluido
        el texto de `campo_texto` en su versión heurística.
        """

    @abstractmethod
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        """Prompt de usuario, construido desde el informe ya cerrado."""

    def tarea(self, state: FinancialAnalysisState) -> str:
        """Texto del `HumanMessage` que abre la traza del agente."""
        return f"{self.rol or self.nombre}: analiza {state.get('ticker', 'UNKNOWN')}."

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        """Línea que resume el dictamen en el log. Se sobrescribe por agente."""
        return "dictamen emitido"


# --------------------------------------------------------------------------- #
# Serialización de la traza
# --------------------------------------------------------------------------- #
# Un `ToolMessage` solo transporta texto, y algunos resultados (el mapa de
# magnitudes, la matriz de correlaciones) son grandes. Se serializan enteros en
# el mensaje —es la traza fiel— pero en el LOG se guarda solo un resumen: el
# JSONL debe poder abrirse, y volcar cien magnitudes por llamada lo haría
# inmanejable.

_LIMITE_TEXTO_TOOL = 4000


def _a_texto(resultado: Any) -> str:
    if isinstance(resultado, str):
        return resultado
    try:
        texto = json.dumps(resultado, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        texto = str(resultado)
    if len(texto) > _LIMITE_TEXTO_TOOL:
        return texto[:_LIMITE_TEXTO_TOOL] + f"... [truncado, {len(texto)} caracteres]"
    return texto


def _resumir(resultado: Any) -> Any:
    """Forma compacta del resultado para el log estructurado."""
    if isinstance(resultado, dict):
        claves = list(resultado)
        return {"claves": claves[:12], "n_claves": len(claves)}
    if isinstance(resultado, list):
        return {"n_elementos": len(resultado)}
    return resultado


def _resumir_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Argumentos sin los diccionarios grandes, que solo estorban en el log."""
    salida: Dict[str, Any] = {}
    for k, v in (args or {}).items():
        if isinstance(v, dict):
            salida[k] = f"<{len(v)} claves>"
        elif isinstance(v, list) and len(v) > 8:
            salida[k] = f"<{len(v)} elementos>"
        else:
            salida[k] = v
    return salida


# --------------------------------------------------------------------------- #
# Ejecución de tools con traza
# --------------------------------------------------------------------------- #
def usar_tool(nombre: str, args: Dict[str, Any], traza: Traza) -> Any:
    """
    Ejecuta una tool por nombre y deja constancia tipada de la llamada.

    Emite el mismo par de mensajes que produciría un agente ReAct —AIMessage con
    `tool_calls`, ToolMessage con el resultado— pero es el CÓDIGO quien elige la
    tool y los argumentos. Ver el encabezado del módulo.

    Está a nivel de módulo y no solo como método porque el nodo de ingesta de
    `src/graph/workflow.py` también invoca tools y también debe dejar traza, y no
    es un agente: no tiene dictamen que redactar ni prompt que construir.
    `AgenteBase.usar_tool` delega aquí, de modo que hay una sola implementación.

    Una excepción de la tool NO se traga: se registra, se refleja en la traza
    como resultado de error y se relanza. Un scorer que falla en silencio
    produciría un informe al que le falta un bloque sin que nada lo diga, y eso
    es peor que un análisis que se detiene.
    """
    tool = obtener_tool(nombre)
# ------------------------------------------------------------------ #
    # Secuencial por el mismo motivo que los ids de mensaje: la traza que se
    # publica en el informe tiene que ser idéntica entre dos ejecuciones del
    # mismo análisis.
    call_id = f"{traza.agente}-call-{len(traza.tools) + 1:02d}"
    traza.añadir(AIMessage(content="", tool_calls=[
        {"name": nombre, "args": args, "id": call_id},
    ]))
    traza.log.debug("tool_call", extra={"evento": "tool_call", "tool": nombre,
                                        "argumentos": _resumir_args(args)})

    t0 = time.perf_counter()
    try:
        resultado = tool.invoke(args)
    except Exception as exc:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        traza.añadir(ToolMessage(tool_call_id=call_id, name=nombre,
                                 status="error",
                                 content=f"{type(exc).__name__}: {exc}"))
        traza.tools.append({"tool": nombre, "argumentos": _resumir_args(args),
                            "duracion_ms": ms, "error": f"{type(exc).__name__}: {exc}"})
        traza.log.error("tool_error", extra={"evento": "tool_error", "tool": nombre,
                                             "duracion_ms": ms,
                                             "error": f"{type(exc).__name__}: {exc}"})
        raise

    ms = round((time.perf_counter() - t0) * 1000, 1)
    traza.añadir(ToolMessage(tool_call_id=call_id, name=nombre,
                             content=_a_texto(resultado)))
    traza.tools.append({"tool": nombre, "argumentos": _resumir_args(args),
                        "duracion_ms": ms, "resultado": _resumir(resultado)})
    traza.log.info("tool_result", extra={"evento": "tool_result", "tool": nombre,
                                         "duracion_ms": ms,
                                         "resultado": _resumir(resultado)})
    return resultado
