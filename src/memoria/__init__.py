"""
Memoria del sistema: qué observó, qué decidió y cómo terminó.

Un solo módulo por ahora, `reflexion`, que es la capa de calibración por
resultados realizados. Vive fuera de `src/tools/` porque es un ALMACÉN con
estado y disciplina point-in-time, no un cálculo puro; las tools que la
consultan están en `src/tools/reflexion.py`.
"""

from src.memoria.reflexion import (
    MemoriaReflexion,
    Observacion,
    resolver_desde_precios,
)

__all__ = ["MemoriaReflexion", "Observacion", "resolver_desde_precios"]
