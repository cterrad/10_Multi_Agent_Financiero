"""
Agente Investigador: el ÚNICO ReAct real del sistema.

QUÉ LO DISTINGUE DE LOS OTROS SEIS
----------------------------------
Aquí el LLM sí elige: recibe las tools con `bind_tools`, decide cuáles invocar,
con qué argumentos y cuándo parar. Es el patrón de `ReAct.py` del curso, sin
adulterar.

Los otros seis agentes usan las mismas tools con un plan fijo escrito en código.
Esa diferencia es deliberada y define la frontera de todo el diseño.

POR QUÉ PUEDE SER UN ReAct DE VERDAD SIN ROMPER NADA
-----------------------------------------------------
Porque no toca ninguna variable de decisión. Tres barreras, todas verificables:

  1. ALCANCE. Solo ve `TOOLS_LECTURA`, que EXCLUYE `calcular_rating_compuesto`,
     `aplicar_vetos`, `dimensionar_posicion`, `calcular_niveles_riesgo`,
     `calcular_perfil_riesgo`, `construir_cartera` y `reconciliar_fuentes`. No
     hay forma de que emita un dictamen: las tools que producen dictámenes no
     están en su mesa.
  2. SALIDA. Escribe un único campo del estado, `research_report`, y solo texto.
     `test_research_report_does_not_alter_decision` comprueba que con y sin ese
     campo el rating, el peso y los niveles salen idénticos.
  3. TOPOLOGÍA. Vive en un grafo aparte (`src/graph/investigacion.py`) que no
     está conectado a `financial_app`. La ejecución diaria no lo invoca; se pide
     a mano con `cli.py --investigar`.

Queda además EXCLUIDO del backtest, igual que la capa de noticias: sus
respuestas dependen del modelo y no serían reproducibles. `disable_llm()` lo
cubre para que un backtest offline no pueda abrir una llamada de red.

COSTE
-----
Cada invocación son varias llamadas al proveedor —una por vuelta del bucle— y
por eso está fuera de la ejecución diaria. `LIMITE_VUELTAS` acota el bucle: un
ReAct sin tope puede encadenar llamadas indefinidamente si el modelo no
converge, y `ReAct.py` no lo contempla porque en un ejemplo de curso da igual.
Aquí no da igual.
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from src.config import get_llm, texto_de_respuesta_llm
from src.prompts import SYSTEM_INVESTIGADOR
from src.tools import TOOLS_LECTURA
from src.utils.logging_agentes import logger_de_agente

# Vueltas máximas del bucle agente↔tools. Cada vuelta es una llamada al
# proveedor más las tools que decida invocar.
LIMITE_VUELTAS = 8


class LLMNoConfigurado(RuntimeError):
    """
    Sin proveedor no hay agente investigador.

    Es la diferencia esencial con los otros seis: ellos degradan a su motor
    heurístico y emiten exactamente el mismo dictamen sin LLM. Este no tiene
    motor heurístico al que degradar, porque su trabajo ES el razonamiento del
    modelo. Fallar de forma explícita es más honesto que devolver un informe
    vacío que parezca una respuesta.
    """


def modelo_con_tools():
    """LLM con las tools de lectura enlazadas. Falla claro si no hay proveedor."""
    llm = get_llm()
    if llm is None:
        raise LLMNoConfigurado(
            "El agente investigador necesita un proveedor de LLM configurado "
            "(LLM_PROVIDER y su clave en .env). El resto del sistema funciona sin él "
            "y produce los mismos ratings; esta capa no."
        )
    return llm.bind_tools(TOOLS_LECTURA)


def resumen_de_traza(mensajes: List[BaseMessage]) -> Dict[str, Any]:
    """
    Qué hizo el agente, para el informe.

    Interesa especialmente `tools_invocadas`: en un ReAct, saber qué consultó el
    modelo antes de responder es la única forma de juzgar si la respuesta se
    apoya en datos o en su memoria.
    """
    tools: List[str] = []
    for m in mensajes:
        for tc in (getattr(m, "tool_calls", None) or []):
            tools.append(tc.get("name", "?"))
    # El texto se extrae con `texto_de_respuesta_llm`, no leyendo `.content`:
    # los proveedores modernos devuelven una LISTA de bloques y asignarla tal
    # cual metía `[{'type': 'text', 'text': '', 'extras': {...}}]` en el informe,
    # que es el defecto que ese helper existe para cortar. Aquí volvió a
    # aparecer en la primera prueba del agente.
    #
    # Se recorren TODOS los turnos sin tool_calls y no solo el último: cuando el
    # modelo razona en varios turnos, el texto útil puede haber quedado en uno
    # anterior y el último venir vacío.
    textos = [texto_de_respuesta_llm(m) for m in mensajes
              if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)]
    utiles = [t for t in textos if t]
    return {
        "tools_invocadas": tools,
        "n_llamadas_tool": len(tools),
        "n_mensajes": len(mensajes),
        "respuesta": "\n\n".join(utiles),
    }
