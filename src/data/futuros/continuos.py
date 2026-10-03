"""
Precio del futuro continuo (primer vencimiento) via yfinance.

Aporta el contexto de precio que el COT no tiene: el posicionamiento dice hacia
donde apuestan los especuladores, el precio dice si les esta saliendo bien. Se
publica en el informe y NO entra en el sesgo: el sesgo macro sale del z-score de
posicionamiento, que es la metrica que la literatura sistematica respalda.

Cache por dia natural, como el resto de datos "de hoy".
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from src.data.futuros import cache as macro_cache

NOMBRE = "futuro_continuo"


def _resumen(df) -> Dict[str, Any]:
    cierres = df["Close"].dropna()
    if cierres.empty:
        return {"disponible": False, "motivo": "sin cierres en el historico"}

    def variacion(sesiones: int) -> Optional[float]:
        if len(cierres) <= sesiones:
            return None
        base = float(cierres.iloc[-1 - sesiones])
        if not base:
            return None
        return round(float(cierres.iloc[-1]) / base - 1.0, 4)

    return {
        "disponible": True,
        "close": round(float(cierres.iloc[-1]), 4),
        "change_1m_pct": variacion(21),
        "change_3m_pct": variacion(63),
        "sesiones": int(len(cierres)),
    }


def precio_continuo(contrato: str, dia: Optional[str] = None, offline: bool = False,
                    directorio: Optional[Any] = None) -> Dict[str, Any]:
    """
    Ultimo cierre y variaciones a 1 y 3 meses del futuro continuo.

    Un fallo devuelve `{"disponible": False, "motivo": ...}` y nunca lanza: la
    ausencia del precio del contrato degrada el informe macro, no lo detiene.
    """
    dia = dia or date.today().isoformat()
    cacheado = macro_cache.leer_contrato(contrato, dia, directorio)
    if cacheado is not None:
        return cacheado

    if offline:
        return {"disponible": False, "contrato": contrato,
                "motivo": f"modo offline y sin cache de {contrato} para {dia}"}

    try:
        import yfinance as yf
        df = yf.Ticker(contrato).history(period="6mo")
    except Exception as exc:  # pragma: no cover - depende de la red
        return {"disponible": False, "contrato": contrato,
                "motivo": f"{type(exc).__name__}: {exc}"}

    if df is None or df.empty:
        return {"disponible": False, "contrato": contrato,
                "motivo": f"yfinance no devolvio precios para {contrato}"}

    payload = {"contrato": contrato, **_resumen(df)}
    macro_cache.escribir_contrato(contrato, payload, dia, directorio)
    return payload
