"""
Capa de ingesta de noticias del Analista de Noticias.

Tres buscadores independientes con la MISMA forma de salida, un agregador que
los ejecuta en paralelo y deduplica, y una caché por (ticker, día).

Ninguna regla de decisión vive aquí: la clasificación por categoría, los pesos,
el léxico de dirección y la probabilidad de impacto están en
`src/agents/news.py`, que es donde el proyecto guarda las reglas.
"""

from src.data.news.aggregator import deduplicar, recolectar, resolver_nombre_empresa
from src.data.news.schema import (
    CLAVES_ITEM, clasificar_tipo_fuente, fecha_iso, limpiar_texto,
    normalizar_item, normalizar_texto, ordenar_estable, tokens_titular,
)

__all__ = [
    "recolectar", "deduplicar", "resolver_nombre_empresa",
    "normalizar_item", "normalizar_texto", "limpiar_texto", "fecha_iso",
    "clasificar_tipo_fuente", "tokens_titular", "ordenar_estable", "CLAVES_ITEM",
]
