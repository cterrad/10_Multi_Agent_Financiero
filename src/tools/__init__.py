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
  · `obtener_contexto_macro` — descarga el fichero anual de la CFTC. Mismo
    criterio de coste que las noticias.
  · `ajustar_precio_entrada` — produce el precio de entrada objetivo, que
    alimenta `calcular_niveles_riesgo` y por esa vía el stop, el objetivo y el
    tamaño. Es una variable de decisión y vive en `src/tools/decision.py`, de
    modo que la exclusión es estructural y no una lista negra.
  · `consultar_reflexion` — produce el factor que recorta el peso y la señal
    que habilita un veto. Dos variables de decisión, así que el módulo entero
    queda fuera por el mismo criterio estructural.

`TOOLS_NIVELES` y `TOOLS_REGIMEN` entran ENTERAS, por el mismo criterio que
`TOOLS_FUTUROS` y `TOOLS_OPCIONES`: explican dónde está el soporte y en qué
régimen cotiza el mercado, pero ninguna emite un dictamen. El soporte que
`identificar_soportes` devuelve es un CANDIDATO, exactamente como el que
devuelve `identificar_niveles_oi`; quien lo convierte en precio de entrada es
`ajustar_precio_entrada`, que vive en `src/tools/decision.py` y no se expone. Y
el régimen que `clasificar_regimen_volatilidad` etiqueta solo llega al dictamen
a través de `aplicar_vetos`, que tampoco se expone. La exclusión sigue siendo
estructural —por el módulo donde vive la tool— y no una lista negra.

`consultar_meta_etiqueta` y `calcular_freno_por_drawdown` quedan FUERA por el
criterio estructural de siempre: las dos producen un factor que multiplica el
peso en `PortfolioConstructor`, es decir variables de decisión, igual que
`consultar_reflexion`.

`etiquetar_por_triple_barrera` y las de `src/tools/validacion.py` también quedan
fuera, pero por un motivo distinto y que conviene no confundir: **no producen
variables de decisión** —son maquinaria de entrenamiento y de validación— y
exponerlas al investigador solo añadiría superficie sin responder ninguna
pregunta sobre un valor concreto.

`denoise_correlaciones` queda FUERA aunque su hermana `calcular_correlaciones`
esté dentro. El criterio es el mismo que con `construir_cartera`: su salida
alimenta la penalización por correlación de `PortfolioConstructor` y por esa vía
el peso de cada posición. Ser más estrecho de lo estrictamente necesario es la
dirección segura de este error.

La distinción no es cosmética: `TOOLS_LECTURA` es la superficie exacta que el
LLM puede alcanzar, y mantenerla estrecha es lo que hace que el agente
investigador sea auditable de un vistazo.
"""

from typing import Dict, List

from langchain_core.tools import BaseTool

from src.tools.calidad import TOOLS_CALIDAD
from src.tools.cartera import TOOLS_CARTERA
from src.tools.covarianza import TOOLS_COVARIANZA
from src.tools.debate import TOOLS_DEBATE
from src.tools.decision import TOOLS_DECISION
from src.tools.etiquetado import TOOLS_ETIQUETADO
from src.tools.extraccion import TOOLS_EXTRACCION, TOOLS_EXTRACCION_LECTURA
from src.tools.fundamentales import TOOLS_FUNDAMENTALES
from src.tools.futuros import TOOLS_FUTUROS
from src.tools.meta import TOOLS_META
from src.tools.niveles import TOOLS_NIVELES
from src.tools.noticias import TOOLS_NOTICIAS
from src.tools.opciones import TOOLS_OPCIONES
from src.tools.reflexion import TOOLS_REFLEXION
from src.tools.regimen import TOOLS_REGIMEN
from src.tools.riesgo import TOOLS_RIESGO
from src.tools.tecnico import TOOLS_TECNICO
from src.tools.validacion import TOOLS_VALIDACION

TODAS_LAS_TOOLS: List[BaseTool] = (
    TOOLS_EXTRACCION + TOOLS_FUNDAMENTALES + TOOLS_CALIDAD
    + TOOLS_TECNICO + TOOLS_NOTICIAS + TOOLS_FUTUROS + TOOLS_OPCIONES
    + TOOLS_DEBATE + TOOLS_DECISION + TOOLS_CARTERA + TOOLS_REFLEXION
    + TOOLS_NIVELES + TOOLS_REGIMEN + TOOLS_COVARIANZA
    + TOOLS_META + TOOLS_RIESGO + TOOLS_ETIQUETADO + TOOLS_VALIDACION
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

# `TOOLS_FUTUROS` y `TOOLS_OPCIONES` entran ENTERAS: explican, no deciden. La
# unica tool de posicionamiento que produce una variable de decision es
# `ajustar_precio_entrada`, y vive en `TOOLS_DECISION`, que no se expone. Que la
# exclusion sea estructural —por el modulo donde vive la tool— y no una lista
# negra que haya que recordar actualizar es deliberado. `TOOLS_REFLEXION` queda
# fuera por el mismo motivo: su unica tool emite factor y veto.
TOOLS_LECTURA: List[BaseTool] = (
    TOOLS_EXTRACCION_LECTURA + TOOLS_FUNDAMENTALES + TOOLS_CALIDAD
    + TOOLS_TECNICO + TOOLS_NOTICIAS + TOOLS_FUTUROS + TOOLS_OPCIONES
    + TOOLS_DEBATE + TOOLS_NIVELES + TOOLS_REGIMEN
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
