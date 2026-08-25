"""
Caché de noticias por (ticker, día).

Sigue el espíritu de `PriceStore`/`FundamentalStore` de `src/backtest/data.py`:
una descarga, servida después desde disco. La diferencia es la clave, que aquí
incluye el día natural — las noticias son un dato "de hoy", así que una entrada
de ayer no es reutilizable y no se debe intentar servirla.

Objetivo práctico: no agotar la cuota de Tavily ni martillear el RSS de Google
cuando se reanaliza el mismo ticker varias veces en la misma sesión.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import NEWS_CACHE_DIR, NEWS_CACHE_ENABLED


def _ruta(ticker: str, dia: str, directorio: Optional[Path] = None) -> Path:
    base = Path(directorio) if directorio else Path(NEWS_CACHE_DIR)
    return base / f"{ticker.upper()}_{dia}.json"


def leer(ticker: str, dia: Optional[str] = None,
         directorio: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Payload cacheado de hoy para `ticker`, o None si no hay o está corrupto."""
    if not NEWS_CACHE_ENABLED and directorio is None:
        return None
    ruta = _ruta(ticker, dia or date.today().isoformat(), directorio)
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        # Un fichero corrupto no debe tumbar el análisis: se ignora y se
        # vuelve a buscar, sobrescribiéndolo.
        return None


def escribir(ticker: str, payload: Dict[str, Any], dia: Optional[str] = None,
             directorio: Optional[Path] = None) -> None:
    """Persiste el payload. Un fallo de escritura nunca interrumpe el análisis."""
    if not NEWS_CACHE_ENABLED and directorio is None:
        return
    ruta = _ruta(ticker, dia or date.today().isoformat(), directorio)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as exc:
        print(f"[NewsCache] No se pudo escribir la caché de {ticker}: {exc}")
