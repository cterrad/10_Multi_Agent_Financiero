"""
Caches del dosier macro: futuros continuos e informes COT.

Dos claves distintas porque son dos datos distintos, y la diferencia importa:

- **Futuro continuo** -> `data/cache/futuros/{CONTRATO}_{YYYY-MM-DD}.json`.
  Clave por dia natural, igual que la cache de noticias
  (`src/data/news/cache.py`): es un dato "de hoy" y el de ayer no es
  reutilizable.

- **Informe COT** -> `data/cache/cot/{SLUG}_{ANIO}.json`.
  La clave NO lleva el dia de la ejecucion. Lleva el ano del informe, y cada
  fila del fichero lleva su propia fecha de informe y su fecha de publicacion.
  Un informe publicado es inmutable, asi que:

    1. entre viernes y viernes toda la ejecucion es acierto de cache;
    2. los ficheros de anos cerrados no se vuelven a descargar nunca;
    3. la cache queda ordenada POINT-IN-TIME por construccion, que es lo que
       permite que el backtest la reutilice sin reimplementar la seleccion
       historica.

El punto 3 es el motivo real de esta forma de clave. Con una clave por dia de
ejecucion —la de noticias— el backtest tendria que descargar y parsear el
archivo entero de la CFTC por su cuenta, y habria dos implementaciones de la
misma seleccion.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import COT_CACHE_DIR, MACRO_CACHE_DIR, MACRO_CACHE_ENABLED


def slug(nombre: str) -> str:
    """Nombre de mercado de la CFTC a un identificador utilizable como fichero."""
    return re.sub(r"[^A-Z0-9]+", "_", (nombre or "").upper()).strip("_") or "DESCONOCIDO"


# --------------------------------------------------------------------------- #
# Futuro continuo (clave por dia)
# --------------------------------------------------------------------------- #
def _ruta_contrato(contrato: str, dia: str, directorio: Optional[Path] = None) -> Path:
    base = Path(directorio) if directorio else Path(MACRO_CACHE_DIR)
    return base / f"{slug(contrato)}_{dia}.json"


def leer_contrato(contrato: str, dia: Optional[str] = None,
                  directorio: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    if not MACRO_CACHE_ENABLED and directorio is None:
        return None
    ruta = _ruta_contrato(contrato, dia or date.today().isoformat(), directorio)
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        # Un fichero corrupto no debe tumbar el analisis: se ignora y se vuelve
        # a descargar, sobrescribiendolo.
        return None


def escribir_contrato(contrato: str, payload: Dict[str, Any], dia: Optional[str] = None,
                      directorio: Optional[Path] = None) -> None:
    if not MACRO_CACHE_ENABLED and directorio is None:
        return
    ruta = _ruta_contrato(contrato, dia or date.today().isoformat(), directorio)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[MacroCache] No se pudo escribir la cache de {contrato}: {exc}")


# --------------------------------------------------------------------------- #
# Informes COT (clave por ano del INFORME, no por dia de ejecucion)
# --------------------------------------------------------------------------- #
def _ruta_cot(mercado: str, anio: int, directorio: Optional[Path] = None) -> Path:
    base = Path(directorio) if directorio else Path(COT_CACHE_DIR)
    return base / f"{slug(mercado)}_{anio}.json"


def leer_cot(mercado: str, anio: int,
             directorio: Optional[Path] = None) -> Optional[List[Dict[str, Any]]]:
    """Filas cacheadas del ano, o None si no hay o el fichero esta corrupto."""
    ruta = _ruta_cot(mercado, anio, directorio)
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, list) else None
    except Exception:
        return None


def escribir_cot(mercado: str, anio: int, filas: List[Dict[str, Any]],
                 directorio: Optional[Path] = None) -> None:
    ruta = _ruta_cot(mercado, anio, directorio)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(filas, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[CotCache] No se pudo escribir la cache de {mercado} {anio}: {exc}")


def anio_esta_cerrado(anio: int, hoy: Optional[date] = None) -> bool:
    """
    Un ano anterior al corriente ya no puede recibir informes nuevos, asi que su
    fichero es definitivo y no se vuelve a descargar. El ano corriente si se
    refresca.
    """
    return anio < (hoy or date.today()).year
