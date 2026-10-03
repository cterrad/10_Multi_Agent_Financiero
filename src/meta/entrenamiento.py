"""
Entrenamiento walk-forward del meta-modelo, con CV purgado y pesos por unicidad.

NO SE CONGELA UN ARTEFACTO ÚNICO, Y ÉSA ES LA DECISIÓN CENTRAL
----------------------------------------------------------------
El encargo permite dos caminos: reentrenamiento walk-forward, o un artefacto
congelado cuya ventana de entrenamiento termine antes de que empiece el estudio.
El segundo es más simple y aquí sería inservible: dejaría el estudio con los
años de entrenamiento fuera y una muestra ya pequeña reducida a la mitad.

Así que **se reentrena**, con un calendario explícito: un modelo nuevo cada
`META_REENTRENAR_CADA_DIAS`, y cada uno solo puede haber visto etiquetas cuya
barrera se resolvió **antes** de su corte.

POR QUÉ UN LINEAL REGULARIZADO Y NO UN GBM
-------------------------------------------
No es una preferencia estética: es la muestra la que decide.

    señales de compra del estudio ............... 944
    tras el corte por desenlace y el walk-forward   ~200 en los primeros modelos
    tamaño EFECTIVO tras ponderar por unicidad ... menor todavía

Con eso, `HistGradientBoosting` con sus valores por defecto memoriza. Una
regresión logística con L2 fuerte tiene pocos parámetros, coeficientes
auditables y una probabilidad razonablemente calibrada de fábrica — que es
exactamente lo que un factor de tamaño necesita. Es un caso en el que la
restricción de datos determina la arquitectura, no al revés.

`sklearn` se importa DENTRO de las funciones a propósito: la suite determinista
del proyecto corre en segundos y no debe pagar el arranque de scikit-learn por
importar un módulo que en la mayoría de los tests no se usa.

TRES REGLAS QUE NO CONVIENE DESHACER
-------------------------------------
1. **El corte del conjunto de entrenamiento es la fecha de DESENLACE.** Está en
   `BancoDeEtiquetas.conjunto()`; aquí solo se consume. Si se relajara, el
   backtest dejaría de medir nada y ninguna cifra lo delataría.
2. **La CV es purgada y con embargo.** Un k-fold corriente sobre etiquetas que
   se solapan no es validación: es una fuga con un número al lado.
3. **Si el modelo no supera a la tasa base en CV, no se entrega artefacto.** Se
   devuelve `None` con su motivo, y la capa degrada a factor 1.0. Entregar un
   modelo que no bate a «apostar siempre» sería añadir ruido con la apariencia
   de una predicción.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.config import (
    META_CV_PARTICIONES,
    META_EMBARGO_DIAS,
    META_MUESTRA_MINIMA,
    META_REGULARIZACION_C,
    META_VENTAJA_MINIMA_AUC,
)
from src.meta.artefacto import MetaArtefacto
from src.meta.banco import Etiqueta
from src.tools.validacion import ParticionPurgadaPorGrupos, pesos_de_muestra


def _matriz(etiquetas: List[Etiqueta],
            variables: List[str]) -> Tuple[np.ndarray, np.ndarray, List[Any], List[Any], np.ndarray]:
    """
    `(X, y, t0, t1, retornos)` de las etiquetas que tienen TODAS las variables.

    Las filas con alguna variable ausente se descartan enteras. No se imputa:
    rellenar con la media convertiría una ausencia en una observación, que es el
    defecto que `src/data/magnitudes.py` corrige en el resto del sistema.
    """
    filas, ys, t0, t1, rets = [], [], [], [], []
    for e in etiquetas:
        vals = [e.variables.get(v) for v in variables]
        if any(v is None or not np.isfinite(float(v)) for v in vals):
            continue
        filas.append([float(v) for v in vals])
        ys.append(int(e.etiqueta))
        t0.append(e.fecha)
        t1.append(e.fecha_desenlace)
        rets.append(float(e.retorno or 0.0))
    if not filas:
        return np.zeros((0, len(variables))), np.zeros(0), [], [], np.zeros(0)
    return (np.asarray(filas, dtype=float), np.asarray(ys, dtype=int),
            t0, t1, np.asarray(rets, dtype=float))


def _auc(y: np.ndarray, p: np.ndarray) -> float:
    """
    Área bajo la curva ROC, sin sklearn: es un Mann-Whitney normalizado.

    Se calcula a mano para que `evaluar_cv` no dependa de más superficie de
    scikit-learn de la estrictamente necesaria, y porque la fórmula por rangos
    es exacta y trivial de auditar.
    """
    pos, neg = y == 1, y == 0
    n1, n0 = int(pos.sum()), int(neg.sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    rangos = pd.Series(p).rank().to_numpy()
    return float((rangos[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def evaluar_cv(X: np.ndarray, y: np.ndarray, t0: List[Any], t1: List[Any],
               pesos: np.ndarray, n_particiones: int = META_CV_PARTICIONES,
               embargo_dias: int = META_EMBARGO_DIAS) -> Dict[str, Any]:
    """
    AUC media sobre particiones purgadas y con embargo.

    La partición agrupa por fecha de señal, así que todas las señales de un
    rebalanceo caen del mismo lado: partirlas metería en el mismo fold dos
    observaciones que el sistema emitió a la vez con la misma información.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    particion = ParticionPurgadaPorGrupos(n_particiones, embargo_dias)
    aucs, tamanos = [], []
    for tr, te in particion.split(t0):
        if len(np.unique(y[tr])) < 2 or len(np.unique(y[te])) < 2:
            continue
        esc = StandardScaler().fit(X[tr])
        clf = LogisticRegression(C=META_REGULARIZACION_C, max_iter=2000)
        clf.fit(esc.transform(X[tr]), y[tr], sample_weight=pesos[tr])
        p = clf.predict_proba(esc.transform(X[te]))[:, 1]
        a = _auc(y[te], p)
        if np.isfinite(a):
            aucs.append(a)
            tamanos.append(len(te))
    if not aucs:
        return {"auc_media": None, "n_particiones_validas": 0,
                "motivo": "ninguna partición tenía las dos clases en ambos lados"}
    return {"auc_media": round(float(np.mean(aucs)), 4),
            "auc_por_particion": [round(a, 4) for a in aucs],
            "n_particiones_validas": len(aucs),
            "muestras_test": tamanos, "motivo": None}


def entrenar(etiquetas: List[Etiqueta], variables: List[str],
             corte: Any) -> Tuple[Optional[MetaArtefacto], Dict[str, Any]]:
    """
    Entrena un artefacto con las etiquetas dadas, o devuelve `None` con su motivo.

    Las tres puertas por las que NO se entrega modelo, en orden:

      1. Menos de `META_MUESTRA_MINIMA` etiquetas utilizables.
      2. Una sola clase presente: no hay nada que discriminar.
      3. **La AUC en CV purgada no supera 0.5 por al menos
         `META_VENTAJA_MINIMA_AUC`.** Un modelo que no bate a «apostar siempre»
         no es un filtro, es ruido con apariencia de predicción, y entregarlo
         sería peor que no tener modelo.

    Devolver `None` no es un fallo: es el estado normal de una instalación
    reciente, exactamente como la memoria de reflexión no penaliza a nadie
    durante su primer año.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    X, y, t0, t1, rets = _matriz(etiquetas, variables)
    diag: Dict[str, Any] = {"n_utilizables": int(len(y)), "corte": str(corte)}

    if len(y) < META_MUESTRA_MINIMA:
        diag["motivo"] = (f"{len(y)} etiquetas resueltas frente a las "
                          f"{META_MUESTRA_MINIMA} mínimas")
        return None, diag
    if len(np.unique(y)) < 2:
        diag["motivo"] = "todas las etiquetas son de la misma clase"
        return None, diag

    pesos = pesos_de_muestra(t0, t1, rets)
    diag["tamano_efectivo"] = round(float(pesos.sum() / max(pesos.max(), 1e-9)), 1)

    cv = evaluar_cv(X, y, t0, t1, pesos)
    diag["cv"] = cv
    auc = cv.get("auc_media")
    if auc is None or auc < 0.5 + META_VENTAJA_MINIMA_AUC:
        diag["motivo"] = (
            f"AUC en CV purgada {auc if auc is not None else 'no evaluable'} frente al "
            f"{0.5 + META_VENTAJA_MINIMA_AUC:.2f} exigido: el modelo no bate a apostar "
            f"siempre, así que no se entrega")
        return None, diag

    esc = StandardScaler().fit(X)
    clf = LogisticRegression(C=META_REGULARIZACION_C, max_iter=2000)
    clf.fit(esc.transform(X), y, sample_weight=pesos)

    art = MetaArtefacto(
        variables=list(variables),
        coeficientes=[float(c) for c in clf.coef_[0]],
        intercepto=float(clf.intercept_[0]),
        media=[float(m) for m in esc.mean_],
        escala=[float(s) if s > 0 else 1.0 for s in esc.scale_],
        entrenado_hasta=max(str(e.fecha_desenlace) for e in etiquetas if e.resuelta),
        entrenado_desde=min(str(e.fecha) for e in etiquetas),
        n_muestras=int(len(y)),
        tasa_base=float(y.mean()),
        metricas_cv=cv)
    diag["motivo"] = None
    diag["tasa_base"] = art.tasa_base
    return art, diag
