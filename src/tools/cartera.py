"""
Tools de construcción de cartera.

POR QUÉ AQUÍ HAY UNA TOOL Y NO SEIS
-----------------------------------
Las seis restricciones de `PortfolioConstructor` —peso del Fund Manager,
penalización por correlación, tope sectorial, tope de número de posiciones,
presupuesto de riesgo agregado y exposición bruta— se aplican EN ESE ORDEN, y el
orden cambia el resultado. Además cada paso muta las posiciones en curso en vez
de devolver una copia.

Exponer cada paso como una tool independiente invitaría a invocarlas sueltas o
en otro orden, y produciría una cartera distinta sin que nada fallara. Así que
la construcción se expone como una sola tool que ejecuta la secuencia completa,
que es la unidad con sentido. `calcular_correlaciones` sí va aparte porque es
genuinamente independiente: es una consulta sobre las series de precios que no
depende de ninguna decisión previa.
"""

from typing import Any, Dict, List, Optional

import pandas as pd
from langchain_core.tools import tool

from src.config import CAPITAL_BASE, CORRELACION_VENTANA_DIAS
from src.portfolio import PortfolioConstructor


@tool("construir_cartera")
def construir_cartera(dictamenes: List[Dict[str, Any]],
                      series_precios: Optional[Dict[str, List[float]]] = None,
                      posiciones_existentes: Optional[List[Dict[str, Any]]] = None,
                      capital: float = CAPITAL_BASE) -> Dict[str, Any]:
    """Agrega dictámenes individuales en una cartera con presupuesto de riesgo.

    Aplica seis restricciones en orden estricto: peso del Fund Manager,
    penalización por correlación media con el resto de candidatas, tope por
    sector, tope de número de posiciones conservando las de mayor convicción,
    presupuesto de riesgo agregado (suma de peso por distancia al stop) y tope
    de exposición bruta. Cada paso deja constancia de lo que recortó.

    Sin matriz de correlaciones NO se corrige nada y se declara la limitación:
    es preferible no corregir a corregir con una matriz inventada.

    `posiciones_existentes` entran con peso FIJO —reajustar la cartera entera en
    cada rebalanceo generaría rotación cuyo coste se comería el ajuste— pero
    consumen presupuesto sectorial, de riesgo y de exposición. Sin eso, cada
    rebalanceo respetaría el tope por sector y la cartera acabaría igualmente
    concentrada tras tres rebalanceos.
    """
    series = None
    if series_precios:
        series = {t: pd.Series(v) for t, v in series_precios.items() if v}
    cartera = PortfolioConstructor(capital=capital).construir(
        dictamenes, series, posiciones_existentes)
    return cartera.a_dict()


@tool("calcular_correlaciones")
def calcular_correlaciones(series_precios: Dict[str, List[float]]) -> Dict[str, Any]:
    """Matriz de correlación de rentabilidades diarias entre varios valores.

    Responde a la pregunta que ninguna ficha individual contesta: si cuatro
    posiciones son cuatro apuestas o una repetida. Usa la ventana de
    `CORRELACION_VENTANA_DIAS` sesiones más recientes.

    Devuelve `{"matriz": None, "motivo": ...}` cuando no hay series suficientes
    —menos de dos valores, menos de 30 observaciones comunes o menos de 20
    rentabilidades tras la ventana—. Ese None es un resultado, no un fallo: la
    capa de cartera lo interpreta como «no penalizar por correlación» y lo
    declara en el informe.
    """
    series = {t: pd.Series(v) for t, v in (series_precios or {}).items() if v}
    if len(series) < 2:
        return {"matriz": None, "motivo": "se necesitan al menos dos series de precios"}

    df = pd.DataFrame(series).dropna()
    if len(df) < 30:
        return {"matriz": None,
                "motivo": f"solo {len(df)} observaciones comunes; se exigen 30"}
    rets = df.pct_change().dropna().tail(CORRELACION_VENTANA_DIAS)
    if len(rets) < 20:
        return {"matriz": None,
                "motivo": f"solo {len(rets)} rentabilidades en la ventana; se exigen 20"}

    matriz = rets.corr()
    return {
        "matriz": {a: {b: round(float(matriz.loc[a, b]), 3) for b in matriz.columns}
                   for a in matriz.index},
        "n_observaciones": int(len(rets)),
        "ventana_dias": CORRELACION_VENTANA_DIAS,
        "motivo": None,
    }


TOOLS_CARTERA = [construir_cartera, calcular_correlaciones]
