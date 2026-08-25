"""
Buscador 2/3: Tavily (`langchain-tavily`, topic="news").

Es la única de las tres fuentes que exige clave. La degradación es doble y
silenciosa a propósito:

  - sin `TAVILY_API_KEY` en el entorno  -> lista vacía, motivo declarado;
  - sin el paquete `langchain-tavily`   -> lista vacía, motivo declarado.

En ambos casos el nodo de noticias sigue funcionando con las otras dos fuentes
y el informe indica qué buscador se quedó fuera. El import es perezoso para no
convertir una dependencia opcional en un requisito de arranque del grafo.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.config import NEWS_WINDOW_DAYS, TAVILY_API_KEY
from src.data.news.schema import normalizar_item

NOMBRE = "tavily"


class TavilyNoDisponible(RuntimeError):
    """Falta la clave o el paquete. No es un error de red: es una capacidad ausente."""


def disponible() -> bool:
    """¿Hay clave y paquete? Se consulta antes de lanzar el hilo."""
    if not TAVILY_API_KEY:
        return False
    try:
        import langchain_tavily  # noqa: F401
    except ImportError:
        return False
    return True


def construir_consulta(empresa: str, ticker: str) -> str:
    return f"{empresa} ({ticker}) press release earnings announcement"


def buscar(empresa: str, ticker: str, max_items: int,
           ventana_dias: int = NEWS_WINDOW_DAYS) -> List[Dict[str, Any]]:
    """Noticias recientes vía Tavily. Lanza `TavilyNoDisponible` si falta la clave."""
    if not TAVILY_API_KEY:
        raise TavilyNoDisponible("TAVILY_API_KEY no está definida en el entorno")
    try:
        from langchain_tavily import TavilySearch
    except ImportError as exc:
        raise TavilyNoDisponible(
            "El paquete `langchain-tavily` no está instalado (pip install langchain-tavily)"
        ) from exc

    buscador = TavilySearch(
        max_results=max_items,
        topic="news",
        days=ventana_dias,
        tavily_api_key=TAVILY_API_KEY,
    )
    respuesta = buscador.invoke({"query": construir_consulta(empresa, ticker)})

    # La forma de la respuesta ha cambiado entre versiones del paquete: unas
    # devuelven {"results": [...]} y otras la lista directamente.
    resultados = respuesta.get("results", []) if isinstance(respuesta, dict) else (respuesta or [])

    items: List[Dict[str, Any]] = []
    for r in resultados[:max_items]:
        if not isinstance(r, dict):
            continue
        item = normalizar_item(
            titulo=r.get("title"),
            url=r.get("url"),
            fuente=r.get("source") or r.get("url"),
            fecha=r.get("published_date") or r.get("published_time"),
            extracto=r.get("content") or r.get("raw_content"),
            buscador=NOMBRE,
            empresa=empresa,
        )
        if item:
            items.append(item)
    return items
