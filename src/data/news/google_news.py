"""
Buscador 1/3: Google News RSS.

Feed público, sin clave de API. Adaptado del prototipo
`src/notebooks/agent_search_web.ipynb`, del que se conserva el parseo del RSS y
la construcción de la consulta orientada a salas de prensa.

Límite conocido y heredado del feed: Google News enlaza a través de una URL de
redirección (`news.google.com/rss/articles/...`), no a la del medio final. Por
eso la credibilidad se clasifica con el atributo `url` de la etiqueta `<source>`,
que sí trae el dominio real; si se usara el `<link>` todos los ítems caerían en
el cubo AGREGADOR.
"""

from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

from src.config import NEWS_HTTP_TIMEOUT, NEWS_LOCALE, NEWS_USER_AGENT, NEWS_WINDOW_DAYS
from src.data.news.schema import clasificar_tipo_fuente, limpiar_texto, normalizar_item

NOMBRE = "google_news_rss"
URL_BASE = "https://news.google.com/rss/search"


def construir_consulta(empresa: str, ventana_dias: int = NEWS_WINDOW_DAYS) -> str:
    """Consulta orientada a anuncios corporativos, no a artículos de opinión."""
    return (
        f'"{empresa}" ("press release" OR "nota de prensa" OR "announces" OR "anuncia" '
        f'OR "reports" OR "results") when:{ventana_dias}d'
    )


def _peticion(consulta: str, max_items: int, empresa: str = "") -> List[Dict[str, Any]]:
    url = f"{URL_BASE}?" + urllib.parse.urlencode({"q": consulta, **NEWS_LOCALE})
    respuesta = requests.get(url, headers={"User-Agent": NEWS_USER_AGENT},
                             timeout=NEWS_HTTP_TIMEOUT)
    respuesta.raise_for_status()

    items: List[Dict[str, Any]] = []
    for nodo in ET.fromstring(respuesta.content).findall(".//item")[:max_items]:
        origen = nodo.find("source")
        url_medio = origen.get("url") if origen is not None else None
        item = normalizar_item(
            titulo=nodo.findtext("title"),
            url=(nodo.findtext("link") or "").strip(),
            fuente=limpiar_texto(origen.text if origen is not None else None) or "Google News",
            fecha=nodo.findtext("pubDate"),
            extracto=nodo.findtext("description"),
            buscador=NOMBRE,
            # El dominio real vive en <source url>, no en <link>.
            tipo_fuente=(clasificar_tipo_fuente(url_medio, empresa=empresa)
                         if url_medio else "AGREGADOR"),
        )
        if item:
            items.append(item)
    return items


def buscar(empresa: str, ticker: str, max_items: int,
           ventana_dias: int = NEWS_WINDOW_DAYS) -> List[Dict[str, Any]]:
    """
    Notas de prensa recientes de `empresa`. Lanza excepción si la red falla; el
    agregador es quien la captura para que la caída de esta fuente no tumbe el
    nodo.
    """
    items = _peticion(construir_consulta(empresa, ventana_dias), max_items, empresa)
    if not items:
        # La consulta estricta puede quedarse vacía en empresas poco cubiertas:
        # se relaja a solo el nombre antes de darla por fallida.
        items = _peticion(f'"{empresa}" when:{ventana_dias}d', max_items, empresa)
    return items
