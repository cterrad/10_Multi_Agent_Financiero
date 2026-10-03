"""
Denoising espectral de matrices de correlación (Marchenko-Pastur).

QUÉ DEFECTO CORRIGE
-------------------
`PortfolioConstructor` penaliza cada candidato por su correlación media con el
resto, y esa media se calculaba sobre la matriz de correlación **muestral en
crudo**. Con las observaciones y el número de activos que maneja un rebalanceo,
la mayor parte del espectro de esa matriz es ruido: la teoría de matrices
aleatorias de Marchenko-Pastur dice exactamente dónde está la frontera, y todos
los autovalores por debajo de ella son indistinguibles de los que produciría una
matriz de rendimientos independientes.

Consecuencia práctica: la penalización por correlación estaba respondiendo, en
parte, a estructura que no existe. Corregirlo no requiere **ningún dato nuevo**.

Es `denoise_cov` del repositorio 03 (`src/risk/portfolio.py`), levantada como
función pura. Allí opera sobre covarianza; aquí sobre correlación, que es lo que
el anfitrión maneja, y por eso la reconstrucción de la diagonal es directa.

DOS REGLAS QUE NO CONVIENE DESHACER
------------------------------------
1. **Si no hay autovalores de ruido, se devuelve la matriz TAL CUAL.** Cuando
   `q` es grande —muchas más observaciones que activos— la frontera cae por
   debajo de todo el espectro y no hay nada que sustituir. Forzar una
   sustitución en ese caso destruiría señal real.
2. **La diagonal se renormaliza a 1 después de reconstruir.** Sin ese paso la
   matriz deja de ser una correlación y la «correlación media» de una fila deja
   de ser comparable entre candidatos.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

import numpy as np
from langchain_core.tools import tool


def _denoise(matriz: Dict[str, Dict[str, float]], q: float,
             holgura: float = 0.01) -> Dict[str, Any]:
    """
    Sustituye los autovalores de ruido por su media y renormaliza la diagonal.

    `q = T / N` es el número de observaciones por activo. La frontera superior
    del ruido de Marchenko-Pastur es `(1 + sqrt(1/q))^2`, ensanchada por
    `holgura` para no dejar justo en el borde autovalores que sí son ruido.

    Devuelve la matriz original y el motivo cuando no hay nada que corregir. No
    se inventa un resultado: es preferible no corregir a corregir mal, el mismo
    criterio con el que `PortfolioConstructor` se abstiene sin matriz.
    """
    nombres = sorted(matriz or {})
    n = len(nombres)
    if n < 2:
        return {"matriz": matriz, "n_ruido": 0, "corregida": False,
                "motivo": "se necesitan al menos dos activos"}
    if q is None or q <= 1.0:
        return {"matriz": matriz, "n_ruido": 0, "corregida": False,
                "motivo": (f"q={q} no es mayor que 1: con menos observaciones que "
                           f"activos la frontera de Marchenko-Pastur no está definida")}

    m = np.array([[float(matriz[a].get(b, 0.0)) for b in nombres] for a in nombres])
    m = (m + m.T) / 2.0                      # simetriza fallos de redondeo
    try:
        vals, vecs = np.linalg.eigh(m)
    except np.linalg.LinAlgError:            # pragma: no cover
        return {"matriz": matriz, "n_ruido": 0, "corregida": False,
                "motivo": "la descomposición espectral no convergió"}

    frontera = (1.0 + math.sqrt(1.0 / q)) ** 2 * (1.0 + holgura)
    ruido = vals < frontera
    if not ruido.any():
        return {"matriz": matriz, "n_ruido": 0, "corregida": False,
                "frontera": round(frontera, 4),
                "motivo": ("ningún autovalor cae bajo la frontera de ruido: la matriz "
                           "se conserva tal cual")}

    vals_lim = vals.copy()
    vals_lim[ruido] = vals[ruido].mean()
    reconstruida = vecs @ np.diag(vals_lim) @ vecs.T

    # La diagonal se renormaliza a 1: sin esto la matriz deja de ser una
    # correlación y la media de una fila deja de ser comparable entre candidatos.
    d = np.sqrt(np.clip(np.diag(reconstruida), 1e-12, None))
    reconstruida = reconstruida / np.outer(d, d)
    np.fill_diagonal(reconstruida, 1.0)

    return {
        "matriz": {a: {b: round(float(reconstruida[i, j]), 3)
                       for j, b in enumerate(nombres)}
                   for i, a in enumerate(nombres)},
        "n_ruido": int(ruido.sum()),
        "n_activos": n,
        "q": round(float(q), 3),
        "frontera": round(frontera, 4),
        "corregida": True,
        "motivo": None,
    }


@tool("denoise_correlaciones")
def denoise_correlaciones(matriz: Dict[str, Dict[str, float]], q: float,
                          holgura: float = 0.01) -> Dict[str, Any]:
    """Limpia de ruido una matriz de correlación por el método de Marchenko-Pastur.

    Con las observaciones y el número de activos de un rebalanceo, la mayor
    parte del espectro de una matriz de correlación muestral es indistinguible
    del que produciría una matriz de rendimientos independientes. Sustituir esos
    autovalores por su media conserva la estructura real y descarta la inventada.

    `q` es el número de observaciones dividido por el de activos. Por debajo de
    1 la frontera no está definida y la matriz se devuelve intacta con su
    motivo, igual que cuando ningún autovalor cae bajo la frontera.

    La diagonal se renormaliza a 1 después de reconstruir: sin ese paso el
    resultado deja de ser una correlación y la media de cada fila deja de ser
    comparable entre candidatos.
    """
    return _denoise(matriz, q, holgura)


TOOLS_COVARIANZA = [denoise_correlaciones]
