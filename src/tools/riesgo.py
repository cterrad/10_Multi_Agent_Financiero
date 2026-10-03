"""
Freno por drawdown de la cartera: `drawdown_guard` traducido a este sistema.

QUÉ CUBRE Y POR QUÉ NO EXISTÍA
-------------------------------
`src/risk/sizing.py` del repositorio 03 lanza `RiskCheckError` cuando el
patrimonio cae más de un porcentaje desde su máximo. El anfitrión **no tiene
equivalente**: su presupuesto de riesgo es *por posición* (`riesgo asumible /
distancia al stop`) y *agregado en un instante* (`RIESGO_TOTAL_CARTERA_PCT`),
pero **nada mira la trayectoria**. Una cartera puede estar dentro de todos sus
límites instantáneos mientras acumula el cuarto mes consecutivo de pérdidas.

LANZAR EXCEPCIÓN NO ENCAJA, Y LA TRADUCCIÓN NO ES LIBRE
--------------------------------------------------------
Un `raise` detendría el análisis, y en este sistema un fallo de riesgo no puede
impedir que se emita un dictamen ya calculado — es el mismo criterio por el que
un 503 del proveedor de LLM degrada al texto heurístico en lugar de tumbar al
agente.

La traducción correcta es la familia que ya existe cuatro veces en el proyecto:
**un factor que solo recorta**. Ni veto ni excepción: menos exposición.

EL BLOQUEANTE, QUE ES DE FONDO Y NO DE IMPLEMENTACIÓN
------------------------------------------------------
**Producción no tiene curva de capital.** `cli.py` emite recomendaciones; no
gestiona una cartera, no conoce su patrimonio y no sabe si está en drawdown. El
backtest sí (`engine.equity`).

Cablearlo solo en el backtest sería **inaceptable**: una variable de decisión
medida en el estudio y ausente en producción es la imagen especular exacta de la
limitación nº 5 —el ajuste de entrada que producción aplicaba y el estudio no— y
por el mismo motivo igual de mala.

Por eso el parámetro es **opcional y neutro por defecto**: sin `drawdown`, el
constructor se comporta exactamente igual que hoy, en producción y en el
backtest. La capa queda declarada INERTE en producción en `build_limitations()`
hasta que exista una cartera real que seguir, y eso está en `NEXT_STEPS`.
"""

from typing import Any, Dict, Optional

from langchain_core.tools import tool

from src.config import (
    DRAWDOWN_ESCALA,
    DRAWDOWN_FACTOR_MINIMO,
    DRAWDOWN_UMBRAL,
)

NEUTRO = 1.0


def _freno(drawdown: Optional[float]) -> Dict[str, Any]:
    """
    Drawdown actual -> factor de exposición, acotado en [mínimo, 1.0].

        exceso = max(0, |drawdown| − UMBRAL)
        factor = clip(1 − exceso / ESCALA, MÍNIMO, 1.0)

    El `max(0, ...)` hace **estructuralmente imposible** que el factor supere
    1.0: por debajo del umbral el exceso es cero y el factor es exactamente el
    neutro. Un drawdown de cero —una cartera en máximos— no amplía nada, y ésa
    es la asimetría deliberada: el freno frena, no acelera.

    `drawdown` llega como número negativo o cero (−0.12 = −12%). Un valor
    positivo se trata como cero, no como un drawdown al revés: una cartera por
    encima de su máximo no es una cartera con drawdown negativo, es una cartera
    sin drawdown.
    """
    if drawdown is None:
        return {"factor_drawdown": NEUTRO, "drawdown": None, "evaluable": False,
                "motivo": ("sin curva de capital: producción no gestiona una cartera y "
                           "no puede conocer su drawdown")}
    dd = min(0.0, float(drawdown))
    exceso = max(0.0, abs(dd) - DRAWDOWN_UMBRAL)
    factor = 1.0 - (exceso / DRAWDOWN_ESCALA if DRAWDOWN_ESCALA > 0 else 0.0)
    factor = max(DRAWDOWN_FACTOR_MINIMO, min(NEUTRO, factor))
    return {
        "factor_drawdown": round(factor, 4),
        "drawdown": round(dd, 4),
        "umbral": DRAWDOWN_UMBRAL,
        "exceso": round(exceso, 4),
        "evaluable": True,
        "motivo": None,
    }


@tool("calcular_freno_por_drawdown")
def calcular_freno_por_drawdown(drawdown: Optional[float] = None) -> Dict[str, Any]:
    """Reduce la exposición cuando la cartera acumula pérdidas desde su máximo.

    Es `drawdown_guard` traducido a la familia de factores que solo recortan: en
    lugar de lanzar una excepción que detendría el análisis, devuelve un
    multiplicador en `[mínimo, 1.0]`.

    Por debajo del umbral el factor es exactamente 1.0 y **nunca lo supera**: una
    cartera en máximos no amplía posiciones. El freno frena, no acelera.

    Sin `drawdown` devuelve el neutro con `evaluable=False` y el motivo, que es
    el estado permanente en producción: el sistema emite recomendaciones y no
    gestiona una cartera, así que no conoce su patrimonio. Declarado en
    `build_limitations()`.

    VARIABLE DE DECISIÓN: multiplica el peso en `PortfolioConstructor`. Queda
    FUERA de `TOOLS_LECTURA`.
    """
    return _freno(drawdown)


TOOLS_RIESGO = [calcular_freno_por_drawdown]
