"""
Capa de construcción de cartera.

Convierte una lista de dictámenes por valor en una cartera con pesos
numéricos, límites de concentración y presupuesto de riesgo. Es la etapa que
el sistema no tenía: `cli.py` recorría los tickers de forma independiente y
nadie miraba nunca el conjunto.
"""

from src.portfolio.construccion import (  # noqa: F401
    CarteraPropuesta,
    PortfolioConstructor,
    PosicionPropuesta,
)
