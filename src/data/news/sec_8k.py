"""
Buscador 3/3: resultados de la compañía anclados en fuente primaria (SEC 8-K).

Envuelve `SECEdgarClient.get_recent_8k_earnings()` y traduce cada 8-K con Ítem
2.02 a la forma normalizada común. No hace ninguna llamada extra: el título del
ítem se construye a partir de metadatos de EDGAR (formulario, ítem, fecha del
periodo), sin descargar ni interpretar el documento.

Es la fuente más fiable del trío y la única con fecha de publicación exacta
(`filed`), de ahí `tipo_fuente="SEC_8K"` y credibilidad 1.0.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.config import NEWS_WINDOW_DAYS
from src.data.news.schema import normalizar_item
from src.data.sec_edgar import SECEdgarClient

NOMBRE = "sec_8k"

# Cliente compartido: reutiliza la caché de CIK entre tickers dentro del proceso.
_cliente = SECEdgarClient()


class SinCoberturaSEC(RuntimeError):
    """El ticker no está en EDGAR (ADR, valor no estadounidense, símbolo erróneo)."""


def buscar(empresa: str, ticker: str, max_items: int,
           ventana_dias: int = NEWS_WINDOW_DAYS) -> List[Dict[str, Any]]:
    """8-K con Ítem 2.02 presentados en los últimos `ventana_dias` días."""
    respuesta = _cliente.get_recent_8k_earnings(ticker, dias=ventana_dias, max_items=max_items)

    if respuesta.get("status") == "NOT_FOUND":
        raise SinCoberturaSEC(f"{ticker} no tiene CIK en EDGAR")
    if respuesta.get("status") != "SUCCESS":
        raise RuntimeError(f"EDGAR devolvió {respuesta.get('status')} para {ticker}")

    items: List[Dict[str, Any]] = []
    for f in respuesta.get("filings", []):
        periodo = f.get("report_date")
        titulo = (
            f"{empresa} presenta el formulario 8-K (Ítem 2.02: Results of Operations "
            f"and Financial Condition)"
        )
        extracto = (
            f"Presentación oficial ante la SEC el {f.get('filed')}"
            + (f", periodo de referencia {periodo}" if periodo else "")
            + (f". {f.get('description')}" if f.get("description") else "")
            + f" Ítems declarados: {f.get('items')}."
        )
        item = normalizar_item(
            titulo=titulo,
            url=f.get("url"),
            fuente="SEC EDGAR (8-K)",
            fecha=f.get("filed"),
            extracto=extracto,
            buscador=NOMBRE,
            tipo_fuente="SEC_8K",
            # `filed` es la fecha de publicación real; se conserva aparte de
            # `fecha` para que el informe pueda declarar su procedencia exacta.
            extra={"filed": f.get("filed"), "accession_number": f.get("accession_number"),
                   "categoria_forzada": "RESULTADOS"},
        )
        if item:
            items.append(item)
    return items
