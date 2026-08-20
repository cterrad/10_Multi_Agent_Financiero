"""
Capa de backtesting de solo lectura sobre el sistema multi-agente.

Principio de diseño innegociable: este paquete NO reimplementa la lógica de
decisión. Importa y ejecuta los agentes reales de `src/agents/` sobre estados
reconstruidos históricamente. Si el backtest y producción divergen, es un bug
del backtest, no una licencia para editar los agentes.
"""
