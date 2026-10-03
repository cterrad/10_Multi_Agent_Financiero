"""
Series de FRED/ALFRED con fecha de publicación por observación.

QUÉ SE DESCARGA Y POR QUÉ ASÍ
------------------------------
ALFRED es la interfaz de archivo de FRED. Dos parámetros la hacen point-in-time:

    realtime_start / realtime_end   la serie tal y como se conocía en esa fecha
    output_type=4                   SOLO la primera publicación de cada observación

Con `output_type=4` cada fila vuelve con su propio `realtime_start`, que es **la
fecha en que ese dato se hizo público**. Es exactamente el par `end`/`filed` de
los hechos XBRL y el par `fecha_informe`/`fecha_publicacion` del COT, solo que
aquí lo aporta el proveedor en lugar de tener que modelarlo.

Verificado el 2026-09-06 contra la API:

    WALCL, observacion del miercoles 2020-03-25
      consultado el 2020-03-25 -> 0 observaciones visibles
      consultado el 2020-03-26 -> 1 observacion visible

    VIXCLS, misma observacion
      consultado el 2020-03-25 -> visible, 63.95   (cierre del dia, sin retardo)

Es decir: **el retardo de publicación no hay que modelarlo, hay que no
estorbarlo.** Toda selección de este módulo usa `fecha_publicacion`.

POR QUÉ SE PIDE AÑO A AÑO
--------------------------
La API rechaza un rango de tiempo real con más de 2000 fechas de vintage, y
`VIXCLS` acumula 3926 desde 1990:

    {"error_code":400,"error_message":"Bad Request. There are 3926 vintage dates
     in the specified real-time period ... exceeds the maximum ... (2000)."}

Un año son unos 250 vintages, holgadamente dentro del límite, y coincide con la
granularidad de la caché. El `realtime_end` se extiende
`FRED_MARGEN_PUBLICACION_DIAS` más allá del cierre del año para capturar la
publicación tardía de las últimas observaciones.

ROBUSTEZ
--------
Una serie que no responde se declara con su motivo y devuelve una serie vacía.
Nunca ceros: una volatilidad implícita de 0.0 no es «sin miedo», es un fichero
que no se supo leer, y confundirlos es el defecto que `src/data/magnitudes.py`
existe para impedir.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    FRED_API_KEY,
    FRED_HTTP_TIMEOUT,
    FRED_MARGEN_PUBLICACION_DIAS,
    FRED_URL_OBSERVACIONES,
)
from src.data.fred import cache as fred_cache

NOMBRE = "fred_alfred"


class FredNoConfigurado(RuntimeError):
    """Falta `FRED_API_KEY`. Se declara; no se sustituye por datos inventados."""


def _fecha(valor: str) -> Optional[str]:
    try:
        return datetime.strptime((valor or "").strip(), "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _numero(valor: str) -> Optional[float]:
    """
    FRED marca el dato ausente con un punto. Devuelve `None`, nunca 0.0.
    """
    v = (valor or "").strip()
    if not v or v == ".":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _descargar_anio(serie: str, anio: int) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Primeras publicaciones de `serie` con observación dentro de `anio`.

    Devuelve `(filas, motivo_de_fallo)`. Nunca lanza salvo por falta de clave,
    que sí es un error de configuración y no una indisponibilidad del proveedor.
    """
    if not FRED_API_KEY:
        raise FredNoConfigurado(
            "FRED_API_KEY no está configurada. La serie de régimen no se puede "
            "reconstruir point-in-time sin ella, y no se sustituye por un valor "
            "por defecto.")

    fin_obs = date(anio, 12, 31)
    # `realtime_end` NO puede ser posterior a hoy: la API lo rechaza con
    #   "Variable realtime_end can not be after today's date"
    # Se recorta, y eso no introduce ningún sesgo: pedir el archivo hasta hoy es
    # justamente lo máximo que se puede saber.
    fin_rt = min(fin_obs + timedelta(days=FRED_MARGEN_PUBLICACION_DIAS), date.today())
    params = {
        "series_id": serie,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "output_type": "4",                       # solo primera publicación
        "realtime_start": date(anio, 1, 1).isoformat(),
        "realtime_end": fin_rt.isoformat(),
        "observation_start": date(anio, 1, 1).isoformat(),
        "observation_end": fin_obs.isoformat(),
    }
    url = f"{FRED_URL_OBSERVACIONES}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=FRED_HTTP_TIMEOUT) as r:
            datos = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # El cuerpo de un 400 de FRED lleva el motivo REAL, y distinguirlos
        # importa: «la serie no existe en ALFRED» es una frontera de cobertura
        # del archivo —VXVCLS observa desde 2007 pero solo se archiva desde
        # 2014— mientras que un límite de vintages o un parámetro inválido son
        # defectos de esta llamada. Tragarse el cuerpo los confundiría.
        try:
            cuerpo = json.loads(exc.read().decode("utf-8"))
            return [], f"FRED {cuerpo.get('error_code')}: {cuerpo.get('error_message', '')[:180]}"
        except Exception:
            return [], f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        return [], f"{type(exc).__name__}: {exc}"

    if "error_message" in datos:
        return [], f"FRED {datos.get('error_code')}: {datos['error_message'][:160]}"

    filas: List[Dict[str, Any]] = []
    for o in datos.get("observations", []):
        f_obs = _fecha(o.get("date", ""))
        f_pub = _fecha(o.get("realtime_start", ""))
        if not f_obs or not f_pub:
            continue
        filas.append({
            "serie": serie,
            "fecha": f_obs,
            "fecha_publicacion": f_pub,
            "valor": _numero(o.get("value", "")),
        })
    filas.sort(key=lambda f: f["fecha"])
    return filas, None


def serie_diaria(serie: str, as_of: Optional[str] = None,
                 dias: int = 400, offline: bool = False,
                 directorio: Optional[Any] = None) -> Dict[str, Any]:
    """
    Serie con las observaciones YA PUBLICADAS en `as_of`.

    `as_of` (YYYY-MM-DD) filtra por **fecha de publicación**, nunca por la de la
    observación. En producción se omite —la pregunta es qué se sabe hoy— y
    existe para que el backtest no reintroduzca la fuga por descuido. Es la misma
    firma y la misma disciplina que `src.data.futuros.cot.serie_semanal`, y
    `FREDStore` la invoca con `as_of` en lugar de reimplementarla: una segunda
    implementación de la selección point-in-time sería un bug de la misma clase
    que una regla de decisión duplicada.

    Devuelve `{"serie", "as_of", "n_observaciones", "observaciones", "fallos"}`.
    Una serie que no se pudo reconstruir viaja con `observaciones` vacía y el
    motivo en `fallos`. **Nunca con ceros.**
    """
    tope = date.fromisoformat(as_of) if as_of else date.today()
    anio_final = tope.year
    anio_inicial = anio_final - max(1, (dias // 365) + 1)

    filas: List[Dict[str, Any]] = []
    fallos: List[str] = []
    for anio in range(anio_inicial, anio_final + 1):
        cacheado = fred_cache.leer_serie(serie, anio, directorio)
        if cacheado is not None and (fred_cache.anio_esta_cerrado(anio, tope) or offline):
            filas.extend(cacheado)
            continue
        if offline:
            if cacheado is not None:
                filas.extend(cacheado)
            else:
                fallos.append(f"{anio}: modo offline y sin caché para {serie}")
            continue
        del_anio, motivo = _descargar_anio(serie, anio)
        if motivo:
            if cacheado is not None:
                filas.extend(cacheado)
            else:
                fallos.append(f"{anio}: {motivo}")
            continue
        fred_cache.escribir_serie(serie, anio, del_anio, directorio)
        filas.extend(del_anio)

    visibles = [f for f in filas
                if f["fecha_publicacion"] <= tope.isoformat() and f["valor"] is not None]
    # Deduplica por fecha de observación conservando la última aparición, por si
    # un año se solapa entre la caché y una descarga nueva.
    unicas: Dict[str, Dict[str, Any]] = {f["fecha"]: f for f in
                                         sorted(visibles, key=lambda f: f["fecha"])}
    obs = sorted(unicas.values(), key=lambda f: f["fecha"])[-dias:]

    return {
        "serie": serie,
        "as_of": tope.isoformat(),
        "n_observaciones": len(obs),
        "observaciones": obs,
        "fallos": fallos,
    }
