"""
Maquinaria de validación: CV purgado con embargo, unicidad y pesos de muestra.

QUÉ ES Y POR QUÉ NO ESTABA
---------------------------
Levantado de `src/validation/` del repositorio 06 (López de Prado, *Advances in
Financial Machine Learning*, caps. 4 y 7). Hasta ahora era **código muerto**: sin
ningún modelo entrenado en la ruta de decisión no tenía un solo llamante, y este
proyecto no mantiene código sin llamante. Entra con `src/meta/`, que es
precisamente cuando pasa de adorno a requisito.

Es `VALIDATE-ONLY`: **no produce ninguna variable de decisión.** Sirve para
elegir modelo y umbral, y para que esa elección sea falsificable. Por eso sus
tools no aparecen en `TOOLS_LECTURA` — no por peligro, sino porque el agente
investigador razona sobre fundamentales, no sobre validación cruzada.

POR QUÉ EL K-FOLD CORRIENTE NO SIRVE, SIN RODEOS
-------------------------------------------------
Las etiquetas de este sistema **se solapan en el tiempo**. Una señal del 1 de
junio cuyas barreras se resuelven el 15 de julio comparte información con otra
del 20 de junio: los mismos precios deciden las dos. Si la primera cae en
entrenamiento y la segunda en prueba, el modelo ya ha visto parte de la
respuesta.

Un k-fold corriente sobre etiquetas solapadas **no es validación: es una fuga
con un número al lado**, y da exactamente la clase de resultado excelente que no
sobrevive fuera de muestra. Las dos correcciones:

  · **PURGA** — el bloque de prueba es contiguo y cronológico, y su periodo
    entero sale del entrenamiento.
  · **EMBARGO** — además se retiran los días inmediatamente POSTERIORES al
    bloque de prueba, porque una etiqueta emitida justo antes del corte se
    resuelve dentro de él.

TRES REGLAS QUE NO CONVIENE DESHACER
-------------------------------------
1. **Los bloques de prueba son contiguos y cronológicos**, nunca aleatorios.
   Barajar destruye la única estructura que hace informativa la partición.
2. **El embargo va DESPUÉS del bloque de prueba, no antes.** El solapamiento va
   hacia adelante en el tiempo: una etiqueta se resuelve en el futuro, no en el
   pasado.
3. **Los pesos por unicidad no son opcionales cuando hay solapamiento.** Diez
   señales que comparten el mismo tramo de precios no son diez observaciones
   independientes, y tratarlas como tales infla la confianza en todo lo que se
   estime después.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from langchain_core.tools import tool


# --------------------------------------------------------------------------- #
# 1. Partición purgada con embargo
# --------------------------------------------------------------------------- #
class ParticionPurgadaPorGrupos:
    """
    K bloques de prueba cronológicos sobre fechas de señal, con purga y embargo.

    Es `PurgedGroupTimeSeriesSplit` del repositorio 06. Se prefiere a
    `PurgedKFold` del 03 por una razón concreta de este sistema: agrupa por
    FECHA, y aquí todas las señales de un rebalanceo comparten fecha. Partirlas
    entre entrenamiento y prueba metería en el mismo fold dos observaciones que
    el sistema emitió a la vez con la misma información.

    `split()` devuelve índices posicionales, como los splitters de sklearn, de
    modo que se puede usar en su lugar sin adaptador.
    """

    def __init__(self, n_particiones: int = 5, embargo_dias: int = 21) -> None:
        if n_particiones < 2:
            raise ValueError("se necesitan al menos dos particiones")
        self.n_particiones = n_particiones
        # El embargo por defecto es el horizonte típico de una operación de este
        # sistema (~21 sesiones): es exactamente el tiempo que una etiqueta tarda
        # en resolverse, y por tanto el tramo que puede filtrarse hacia el test.
        self.embargo_dias = embargo_dias

    def split(self, fechas: Sequence[Any]) -> Iterator[Tuple[np.ndarray, np.ndarray]]:
        """
        `fechas` es la fecha de señal de cada fila (longitud = nº de muestras).
        """
        f = pd.to_datetime(pd.Series(list(fechas)).reset_index(drop=True))
        unicas = np.sort(f.unique())
        if len(unicas) < self.n_particiones:
            raise ValueError(
                f"{len(unicas)} fechas distintas para {self.n_particiones} particiones: "
                f"no hay bloques que formar")
        bloques = np.array_split(unicas, self.n_particiones)
        embargo = pd.Timedelta(days=self.embargo_dias)

        for fechas_test in bloques:
            if len(fechas_test) == 0:
                continue
            hasta = pd.Timestamp(fechas_test.max())
            es_test = f.isin(fechas_test).to_numpy()
            # Purga: el bloque de prueba sale del entrenamiento (implícito en
            # `~es_test`). Embargo: además salen los días posteriores, porque una
            # etiqueta emitida justo antes del corte se resuelve DENTRO del test.
            embargado = ((f > hasta) & (f <= hasta + embargo)).to_numpy()
            train = np.flatnonzero(~es_test & ~embargado)
            test = np.flatnonzero(es_test)
            if len(train) == 0 or len(test) == 0:
                continue
            yield train, test

    def get_n_splits(self, *_args, **_kwargs) -> int:
        return self.n_particiones


# --------------------------------------------------------------------------- #
# 2. Concurrencia y unicidad
# --------------------------------------------------------------------------- #
def _concurrencia(t0: pd.Series, t1: pd.Series) -> Tuple[pd.DatetimeIndex, np.ndarray]:
    """
    Cuántas etiquetas están vivas en cada instante de la línea temporal.

    Se calcula con un array de diferencias y una suma acumulada: O(n log n) por
    la ordenación, en lugar del O(n²) de comparar cada etiqueta con las demás.
    """
    puntos = pd.DatetimeIndex(pd.concat([t0, t1]).dropna().unique()).sort_values()
    if len(puntos) == 0:
        return puntos, np.zeros(0)
    ini = puntos.searchsorted(pd.DatetimeIndex(t0), side="left")
    fin = puntos.searchsorted(pd.DatetimeIndex(t1), side="right")
    dif = np.zeros(len(puntos) + 1)
    np.add.at(dif, ini, 1.0)
    np.add.at(dif, fin, -1.0)
    return puntos, np.cumsum(dif[:-1])


def unicidad_media(t0: Sequence[Any], t1: Sequence[Any]) -> np.ndarray:
    """
    Unicidad media de cada etiqueta: media de `1 / concurrencia` sobre su tramo.

    Una etiqueta aislada tiende a 1.0; una que comparte su horizonte con otras
    nueve tiende a 0.1. Es la medida de cuánta información NUEVA aporta cada
    observación, y es lo que impide que diez señales del mismo mes cuenten como
    diez observaciones independientes.
    """
    s0 = pd.Series(pd.to_datetime(pd.Series(list(t0))).values)
    s1 = pd.Series(pd.to_datetime(pd.Series(list(t1))).values)
    if len(s0) == 0:
        return np.zeros(0)
    puntos, conc = _concurrencia(s0, s1)
    if len(puntos) == 0:
        return np.ones(len(s0))
    inv = np.divide(1.0, conc, out=np.zeros_like(conc), where=conc > 0)
    acum = np.concatenate([[0.0], np.cumsum(inv)])
    ini = puntos.searchsorted(pd.DatetimeIndex(s0), side="left")
    fin = puntos.searchsorted(pd.DatetimeIndex(s1), side="right")
    tramo = np.maximum(fin - ini, 1)
    return (acum[fin] - acum[ini]) / tramo


def pesos_de_muestra(t0: Sequence[Any], t1: Sequence[Any],
                     retorno: Sequence[float]) -> np.ndarray:
    """
    Peso de entrenamiento de cada etiqueta: `|retorno| × unicidad`, media 1.

    Dos correcciones a la vez, y las dos importan:

      · **Unicidad** — una observación solapada aporta menos información.
      · **Atribución por retorno** — una operación que movió el 15% dice más
        sobre si la señal funcionaba que otra que movió el 0.2%. Es la
        ponderación por atribución de retorno de AFML cap. 4.

    Se normaliza a media 1 para que el tamaño efectivo de la muestra no cambie:
    los pesos reordenan la importancia relativa, no inflan ni desinflan el
    conjunto.
    """
    u = unicidad_media(t0, t1)
    r = np.abs(np.asarray(list(retorno), dtype=float))
    w = np.nan_to_num(u * r, nan=0.0, posinf=0.0, neginf=0.0)
    media = w.mean() if len(w) else 0.0
    if media <= 0:
        # Sin retornos utilizables la ponderación no aporta nada, y unos pesos
        # todos a cero anularían el entrenamiento. Se declara devolviendo el
        # neutro en lugar de fallar.
        return np.ones(len(w))
    return w / media


# --------------------------------------------------------------------------- #
# 3. Fachadas @tool
# --------------------------------------------------------------------------- #
@tool("calcular_unicidad_media")
def calcular_unicidad_media(t0: List[str], t1: List[str]) -> Dict[str, Any]:
    """Unicidad media de cada etiqueta, dada la ventana que ocupa en el tiempo.

    Una etiqueta cuyo horizonte no se solapa con ninguna otra vale 1.0; una que
    lo comparte con otras nueve, en torno a 0.1. Mide cuánta información NUEVA
    aporta cada observación.

    Es lo que impide que diez señales emitidas el mismo mes, resueltas sobre los
    mismos precios, cuenten como diez observaciones independientes — que es la
    forma más común de inflar la confianza en un modelo financiero.

    No produce ninguna variable de decisión: sirve para entrenar y para validar.
    """
    u = unicidad_media(t0, t1)
    return {"unicidad": [round(float(x), 4) for x in u],
            "unicidad_media": round(float(u.mean()), 4) if len(u) else None,
            "n": int(len(u)),
            "tamano_efectivo": round(float(u.sum()), 2) if len(u) else 0.0}


@tool("calcular_pesos_de_muestra")
def calcular_pesos_de_muestra(t0: List[str], t1: List[str],
                              retorno: List[float]) -> Dict[str, Any]:
    """Pesos de entrenamiento por unicidad y atribución de retorno, media 1.

    Combina dos correcciones de López de Prado: una observación solapada aporta
    menos información que una aislada, y una operación que movió el 15% dice más
    sobre la señal que otra que movió el 0.2%.

    Normalizado a media 1 para no cambiar el tamaño efectivo de la muestra: los
    pesos reordenan la importancia relativa, no inflan el conjunto.
    """
    w = pesos_de_muestra(t0, t1, retorno)
    return {"pesos": [round(float(x), 4) for x in w],
            "n": int(len(w)),
            "peso_maximo": round(float(w.max()), 3) if len(w) else None}


TOOLS_VALIDACION = [calcular_unicidad_media, calcular_pesos_de_muestra]
