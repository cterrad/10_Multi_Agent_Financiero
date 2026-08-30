"""
Registro central de tools.

Réplica del patrón `tools_dict = {t.name: t for t in tools}` de `RAG_Agent.py`,
que es la pieza que permite ejecutar una tool por NOMBRE sin que el LLM decida
cuál. El agente determinista consulta este registro con un plan fijo; el agente
investigador recibe la lista y deja que el modelo elija. Misma colección de
tools, dos formas de recorrerla.

DOS COLECCIONES, DOS PROPÓSITOS
-------------------------------
`REGISTRO_TOOLS` es todo lo invocable, indexado por nombre. Lo usa
`AgenteBase.usar_tool()`.

`TOOLS_LECTURA` es el subconjunto que se expone al agente investigador ReAct.
Deja fuera:

  · `construir_cartera` — produce una asignación de capital. Es una decisión,
    y las decisiones no las toma el modelo en este sistema.
  · `reconciliar_fuentes` — su salida alimenta al gatekeeper; exponerla
    invitaría a que el investigador fabricara un estado alternativo.
  · `obtener_noticias` — la fuente más lenta y la que más cuota consume, y el
    investigador razona sobre fundamentales.

La distinción no es cosmética: `TOOLS_LECTURA` es la superficie exacta que el
LLM puede alcanzar, y mantenerla estrecha es lo que hace que el agente
investigador sea auditable de un vistazo.
"""

from typing import Dict, List

from langchain_core.tools import BaseTool

from src.tools.calidad import TOOLS_CALIDAD
from src.tools.cartera import TOOLS_CARTERA
from src.tools.debate import TOOLS_DEBATE
from src.tools.decision import TOOLS_DECISION
from src.tools.extraccion import TOOLS_EXTRACCION, TOOLS_EXTRACCION_LECTURA
from src.tools.fundamentales import TOOLS_FUNDAMENTALES
from src.tools.noticias import TOOLS_NOTICIAS
from src.tools.tecnico import TOOLS_TECNICO

TODAS_LAS_TOOLS: List[BaseTool] = (
    TOOLS_EXTRACCION + TOOLS_FUNDAMENTALES + TOOLS_CALIDAD
    + TOOLS_TECNICO + TOOLS_NOTICIAS + TOOLS_DEBATE
    + TOOLS_DECISION + TOOLS_CARTERA
)

REGISTRO_TOOLS: Dict[str, BaseTool] = {t.name: t for t in TODAS_LAS_TOOLS}

if len(REGISTRO_TOOLS) != len(TODAS_LAS_TOOLS):
    # Dos tools con el mismo nombre harían que una eclipsara a la otra en
    # silencio, y el agente ejecutaría un cálculo distinto del que cree.
    vistos, duplicados = set(), set()
    for t in TODAS_LAS_TOOLS:
        if t.name in vistos:
            duplicados.add(t.name)
        vistos.add(t.name)
    raise RuntimeError(f"Nombres de tool duplicados en el registro: {sorted(duplicados)}")

TOOLS_LECTURA: List[BaseTool] = (
    TOOLS_EXTRACCION_LECTURA + TOOLS_FUNDAMENTALES + TOOLS_CALIDAD
    + TOOLS_TECNICO + TOOLS_NOTICIAS + TOOLS_DEBATE
    + [t for t in TOOLS_CARTERA if t.name == "calcular_correlaciones"]
)


def obtener_tool(nombre: str) -> BaseTool:
    """
    Devuelve la tool por nombre, o falla con la lista de nombres válidos.

    El fallo es explícito a propósito: un nombre mal escrito en el plan de un
    agente debe romper en el acto, no producir un informe al que le falte
    silenciosamente un bloque de análisis.
    """
    try:
        return REGISTRO_TOOLS[nombre]
    except KeyError:
        raise KeyError(
            f"Tool desconocida: {nombre!r}. Disponibles: {sorted(REGISTRO_TOOLS)}"
        ) from None


__all__ = [
    "REGISTRO_TOOLS",
    "TODAS_LAS_TOOLS",
    "TOOLS_LECTURA",
    "obtener_tool",
]
