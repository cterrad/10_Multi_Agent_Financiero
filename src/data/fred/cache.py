"""
Caché de series de FRED/ALFRED y manifiesto de recuperaciones.

LA CLAVE ES EL AÑO DE LA OBSERVACIÓN, NO EL DÍA DE LA EJECUCIÓN
---------------------------------------------------------------
`data/cache/fred/{SERIE}_{AÑO}.json`. Es la misma forma de clave que
`data/cache/cot/{MERCADO}_{AÑO}.json` y por el mismo motivo, que no es de
almacenamiento sino de disciplina:

  1. Cada fila lleva su `fecha` (la observación) y su `fecha_publicacion` (el
     `realtime_start` de la primera publicación que devuelve ALFRED con
     `output_type=4`). Es el par `end`/`filed` del XBRL.
  2. Un año cerrado no puede recibir observaciones nuevas, así que su fichero es
     definitivo y no se vuelve a descargar.
  3. **La caché queda ordenada point-in-time por construcción**, que es lo que
     permite que el backtest la reutilice sin reimplementar la selección
     histórica. Con una clave por día de ejecución —la de las noticias— habría
     dos implementaciones de la misma selección.

UN VINTAGE CACHEADO NO SE SOBRESCRIBE JAMÁS
--------------------------------------------
`escribir_serie` compara con lo que ya hay y **levanta `VintageDivergente`** si
los bytes difieren. Que el proveedor reescriba la historia es un evento que
registrar e investigar, no algo que absorber en silencio: es exactamente la
propiedad que hace que un estudio del año pasado siga siendo reproducible hoy.

EL MANIFIESTO NO LLEVA RELOJ DE PARED
--------------------------------------
Anota fuente, serie, año, vintage, filas y suma de verificación. **No anota la
hora de descarga**, porque `daily_selection.json` y el informe del backtest
deben poder compararse byte a byte entre dos ejecuciones `--offline`, y este
proyecto ya tuvo ese defecto una vez: lo corrigió haciendo secuenciales los
identificadores de traza y dejando las duraciones fuera de `Traza.a_dict()`.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import FRED_CACHE_DIR, FRED_CACHE_ENABLED, FRED_MANIFIESTO


class VintageDivergente(RuntimeError):
    """
    Una redescarga devolvió contenido distinto para un vintage ya cacheado.

    No se traga: significa que el proveedor revisó historia que ya se había
    consumido, y cualquier estudio ejecutado con la versión anterior deja de ser
    reproducible en silencio. Se levanta para que quede constancia.
    """


def slug(nombre: str) -> str:
    """Identificador de serie utilizable como nombre de fichero."""
    return re.sub(r"[^A-Z0-9]+", "_", (nombre or "").upper()).strip("_") or "DESCONOCIDA"


def _ruta(serie: str, anio: int, directorio: Optional[Path] = None) -> Path:
    base = Path(directorio) if directorio else Path(FRED_CACHE_DIR)
    return base / f"{slug(serie)}_{anio}.json"


def _huella(filas: List[Dict[str, Any]]) -> str:
    """
    Suma de verificación del contenido, estable entre ejecuciones.

    `sort_keys=True` es lo que la hace estable: sin él, el orden de las claves
    de un dict podría variar y dos descargas idénticas producirían huellas
    distintas.
    """
    crudo = json.dumps(filas, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(crudo).hexdigest()[:16]


def leer_serie(serie: str, anio: int,
               directorio: Optional[Path] = None) -> Optional[List[Dict[str, Any]]]:
    """Filas cacheadas del año, o `None` si no hay o el fichero está corrupto."""
    ruta = _ruta(serie, anio, directorio)
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return datos if isinstance(datos, list) else None
    except Exception:
        return None


def escribir_serie(serie: str, anio: int, filas: List[Dict[str, Any]],
                   directorio: Optional[Path] = None) -> Dict[str, Any]:
    """
    Persiste el año y anota la recuperación en el manifiesto.

    Si ya existe un fichero para ese vintage con contenido DISTINTO, levanta
    `VintageDivergente` en lugar de sobrescribirlo. Un vintage es inmutable por
    definición; si dejó de serlo, hay que enterarse.
    """
    ruta = _ruta(serie, anio, directorio)
    huella = _huella(filas)

    previas = leer_serie(serie, anio, directorio)
    if previas is not None:
        huella_previa = _huella(previas)
        if huella_previa != huella:
            raise VintageDivergente(
                f"{serie} {anio}: la redescarga devuelve un contenido distinto del "
                f"cacheado ({huella_previa} -> {huella}). El proveedor ha revisado "
                f"historia ya consumida. No se sobrescribe: revísalo antes de "
                f"reejecutar el estudio.")
        return {"serie": serie, "anio": anio, "filas": len(filas),
                "huella": huella, "escrito": False}

    if not FRED_CACHE_ENABLED and directorio is None:
        return {"serie": serie, "anio": anio, "filas": len(filas),
                "huella": huella, "escrito": False}

    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(filas, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    except Exception as exc:
        print(f"[FredCache] No se pudo escribir {serie} {anio}: {exc}")
        return {"serie": serie, "anio": anio, "filas": len(filas),
                "huella": huella, "escrito": False}

    anotar_manifiesto({"fuente": "fred_alfred", "serie": serie, "anio": anio,
                       "vintage": f"{anio}-inicial", "filas": len(filas),
                       "huella": huella})
    return {"serie": serie, "anio": anio, "filas": len(filas),
            "huella": huella, "escrito": True}


def anotar_manifiesto(registro: Dict[str, Any],
                      ruta: Optional[Path] = None) -> None:
    """
    Añade una línea al manifiesto append-only. Nunca falla hacia arriba.

    El manifiesto es un medio de auditoría, no el motivo por el que un análisis
    deja de emitirse — el mismo criterio que gobierna el logger estructurado.
    """
    destino = Path(ruta) if ruta else Path(FRED_MANIFIESTO)
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, sort_keys=True, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover
        print(f"[FredCache] No se pudo anotar el manifiesto: {exc}")


def anio_esta_cerrado(anio: int, hoy: Optional[date] = None) -> bool:
    """
    Un año anterior al corriente ya no recibe observaciones nuevas, así que su
    fichero es definitivo. El año en curso sí se refresca.
    """
    return anio < (hoy or date.today()).year
