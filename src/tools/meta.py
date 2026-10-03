"""
Tool de meta-etiquetado: convierte una probabilidad en un factor de tamaño.

QUÉ PRODUCE Y POR QUÉ ESTÁ AQUÍ Y NO EN `src/meta/`
----------------------------------------------------
`src/meta/` almacena, respeta el point-in-time y entrena; este módulo hace el
cálculo puro que traduce una probabilidad en la única variable de decisión que
el meta-modelo toca:

  · `factor_meta` ∈ [`META_FACTOR_MINIMO`, 1.0] — multiplica el peso.

Es exactamente el mismo reparto que hay entre `src/memoria/` y
`src/tools/reflexion.py`, y por el mismo motivo: la disciplina temporal en un
sitio, la regla de decisión en otro.

Es variable de decisión, así que esta tool queda **FUERA de `TOOLS_LECTURA`**,
igual que `consultar_reflexion`, `aplicar_vetos` y `ajustar_precio_entrada`.

LAS TRES REGLAS QUE NO CONVIENEN DESHACER
------------------------------------------
1. **EL FACTOR SOLO RECORTA.** 1.0 es a la vez el valor neutro y el máximo. Una
   señal que el modelo considera excelente **no amplía** el peso.

   No es simetría por elegancia: ampliar el peso de lo que el modelo cree bueno
   convierte una capa de filtrado en una **apuesta apalancada sobre el propio
   modelo**, y con 944 muestras de entrenamiento eso es exactamente lo que no se
   puede permitir. Es la misma regla que gobierna `factor_reflexion`,
   `aplicar_vetos` y `ajustar_precio_entrada`, y ya van cuatro.

2. **Sin modelo no hay ajuste, y se dice.** Factor 1.0 con `evaluable=False` y
   un motivo. Una instalación reciente no penaliza a nadie, igual que los
   percentiles de opciones no se inventan un percentil 50 mientras acumulan
   histórico.

3. **La referencia es la TASA BASE del entrenamiento, no 0.5.** Si el sistema
   acierta el 47% de sus compras, exigirle a una señal un 50% para no recortarla
   penalizaría a la mayoría por una constante arbitraria. El punto neutro es «tan
   buena como la señal media que este sistema emite».

DÓNDE SE APLICA, Y POR QUÉ NO EN EL FUND MANAGER
-------------------------------------------------
En `PortfolioConstructor`, junto a `factor_reflexion`. El Fund Manager lo
publica **sin aplicar**, porque solo la capa de cartera ve el rebalanceo entero
y puede **reasignar** a los demás candidatos el presupuesto que el recorte
libera. Aplicarlo valor a valor solo sabría restar, y este sistema ya opera con
una exposición bruta media del 30%.
"""

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from src.config import META_ESCALA_DEFICIT, META_FACTOR_MINIMO

NEUTRO = 1.0


def _neutro(motivo: str) -> Dict[str, Any]:
    return {"factor_meta": NEUTRO, "probabilidad": None, "tasa_base": None,
            "evaluable": False, "motivo": motivo}


def _consultar(probabilidad: Optional[float],
               tasa_base: Optional[float]) -> Dict[str, Any]:
    """
    Probabilidad de acierto -> factor de tamaño, acotado en [mínimo, 1.0].

        déficit = max(0, tasa_base − p)
        factor  = clip(1 − déficit / ESCALA, MÍNIMO, 1.0)

    El `max(0, ...)` es lo que hace **estructuralmente imposible** que el factor
    supere 1.0: por encima de la tasa base el déficit es cero y el factor es
    exactamente el neutro. No hay ninguna combinación de argumentos que amplíe
    un peso, y `test_el_factor_meta_nunca_sube_el_peso` lo recorre sobre el
    producto cartesiano.
    """
    if probabilidad is None:
        return _neutro("el modelo no emitió probabilidad: faltan variables o no hay artefacto")
    if tasa_base is None or not (0.0 < tasa_base < 1.0):
        return _neutro("tasa base del entrenamiento no disponible o degenerada")

    p = max(0.0, min(1.0, float(probabilidad)))
    deficit = max(0.0, float(tasa_base) - p)
    factor = 1.0 - (deficit / META_ESCALA_DEFICIT if META_ESCALA_DEFICIT > 0 else 0.0)
    factor = max(META_FACTOR_MINIMO, min(NEUTRO, factor))
    return {
        "factor_meta": round(factor, 4),
        "probabilidad": round(p, 4),
        "tasa_base": round(float(tasa_base), 4),
        "deficit": round(deficit, 4),
        "evaluable": True,
        "motivo": None,
    }


@tool("consultar_meta_etiqueta")
def consultar_meta_etiqueta(probabilidad: Optional[float],
                            tasa_base: Optional[float]) -> Dict[str, Any]:
    """Convierte la probabilidad del meta-modelo en un factor de tamaño que SOLO RECORTA.

    El punto neutro es la TASA BASE del conjunto de entrenamiento, no 0.5: si el
    sistema acierta el 47% de sus compras, exigirle a una señal un 50% para no
    recortarla la penalizaría por una constante arbitraria.

    Por encima de la tasa base el factor es exactamente 1.0. **Nunca lo supera**,
    y no por convención: ampliar el peso de lo que el modelo cree bueno
    convertiría una capa de filtrado en una apuesta apalancada sobre el propio
    modelo, con 944 muestras de entrenamiento detrás.

    Sin probabilidad —sin artefacto, o con variables ausentes— devuelve el
    neutro con `evaluable=False` y el motivo. Nunca una probabilidad inventada.

    VARIABLE DE DECISIÓN: su salida multiplica el peso en `PortfolioConstructor`.
    Queda FUERA de `TOOLS_LECTURA`.
    """
    return _consultar(probabilidad, tasa_base)


TOOLS_META = [consultar_meta_etiqueta]
