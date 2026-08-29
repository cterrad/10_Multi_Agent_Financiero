# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pipeline multi-agente (LangGraph) que selecciona acciones: ingiere y reconcilia datos de yfinance/SEC EDGAR/Finnhub, filtra con un gatekeeper fundamental, puntúa calidad y valoración con siete escuelas clásicas (Piotroski, Altman, Graham, Buffett, Lynch, Greenblatt, Sloan), cruza momentum técnico y una capa de noticias asesora, y emite un rating en 5 categorías con tamaño de posición y niveles de stop/objetivo — todo por reglas deterministas (ver «La invariante que sostiene todo el proyecto» más abajo). `src/backtest/` reejecuta esos mismos agentes sobre datos históricos point-in-time para medir si la selección aporta sobre el índice o el azar.

El código, los comentarios y la documentación de este proyecto están en español. Mantén ese idioma al escribir código nuevo, docstrings o informes.

## Entorno

El proyecto **no** corre con el `python` del PATH. Usa siempre el intérprete conda por ruta absoluta (`conda activate` no persiste entre llamadas de herramienta):

```powershell
C:\Users\cterr\anaconda3\envs\venv-multi_gent_finantial\python.exe   # Python 3.10
```

Los imports son de la forma `from src...`, así que todo se ejecuta **desde la raíz del repositorio** (no hay `pyproject.toml` ni instalación en modo editable).

## Comandos

```powershell
# Análisis en vivo (escribe output/daily_selection.md + .json)
<python> cli.py --tickers NVDA,AAPL,TSLA

# Dashboard FastAPI en http://localhost:8000
<python> -m src.web.app

# Backtest histórico (regímenes: pit | technical_only | biased)
<python> backtest_cli.py --start 2015-01-01 --end 2025-12-31 --regime pit
<python> backtest_cli.py --regime technical_only --out output/regimes/technical_only
<python> backtest_cli.py --offline --quiet          # sin red, solo caché

# Tests
<python> -m pytest tests/                            # suite completa
<python> -m pytest tests/test_backtest.py            # única suite sin red
<python> -m pytest tests/test_backtest.py::test_no_lookahead_future_prices_do_not_change_past_signal -v

# Docker
docker-compose up --build
```

`tests/test_backtest.py` y `tests/test_reconciler.py` son offline y deterministas. `tests/test_fetcher.py` y `tests/test_workflow.py` **golpean yfinance en vivo** y fallan sin red o si yfinance cambia el esquema de `info` — no son fiables en CI.

La primera ejecución de `backtest_cli.py` descarga precios y `companyfacts` de la SEC a `data/cache/` (~250 MB, ignorado por git). A partir de ahí `--offline` reproduce el estudio bit a bit.

## Arquitectura

### Grafo de producción (`src/graph/workflow.py`)

Máquina de estados LangGraph sobre `FinancialAnalysisState` (`src/state.py`, un `TypedDict` que cada nodo actualiza parcialmente):

```
ingest → gatekeeper → [route_after_gatekeeper] ─┬─ aprobado → technical → debate → fund_manager → END
                                                └─ rechazado ─────────────────────→ fund_manager → END
```

El corte del gatekeeper es la razón de ser del diseño: un valor rechazado salta el análisis técnico y el debate, y el `fund_manager` le asigna VENTA / VENTA FUERTE directamente.

`workflow.py` instancia los agentes y compila el grafo **a nivel de módulo** (`financial_app`), así que importar el módulo tiene efectos secundarios.

### La invariante que sostiene todo el proyecto

**Ninguna variable de decisión depende del LLM.** Los cuatro agentes calculan su dictamen con reglas deterministas y, si hay LLM configurado, este solo sobrescribe campos de texto (`summary` en fundamental/technical/fund_manager, `synthesis` en debate). Sin token de API, `get_llm()` devuelve `None` y el sistema produce exactamente los mismos ratings.

Esto no es un detalle de estilo: es lo que permite que el backtest reproduzca la lógica real de forma determinista y a coste cero. Se verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()` (`src/backtest/replay.py`), que ejecuta los agentes con y sin un LLM falso y compara `passed_gatekeeper`, `momentum_classification`, `rating`, `position_size_pct` y los niveles de stop/objetivo. `backtest_cli.py` aborta si la verificación falla, y `test_llm_is_decision_neutral` la cubre en la suite.

**Si añades lógica a un agente, el resultado del LLM no puede entrar en ninguna rama ni en ningún número.** Solo en texto.

Reglas de decisión concretas (documentadas exhaustivamente en `output/AUDIT.md`):
- Gatekeeper: umbrales `MIN_NET_MARGIN`, `MIN_REVENUE_GROWTH`, `MAX_DEBT_TO_EQUITY` de `src/config.py` (leídos del entorno **en tiempo de import**).
- Momentum: sistema de puntos alcistas/bajistas sobre RSI, MACD, cruce SMA 50/200 y Bandas de Bollinger → `ALCISTA_FUERTE` / `ALCISTA` / `NEUTRAL` / `BAJISTA`.
- Rating final: tabla momentum×RSI en `src/agents/fund_manager.py`; stop = `close − 2.0·ATR`, objetivo = `close + 3.5·ATR`.

### Capa de backtest (`src/backtest/`) — solo lectura sobre los agentes

`HistoricalReplayer` **no reimplementa ninguna regla**. Importa las clases reales de `src/agents/`, reconstruye para una fecha `t` un estado indistinguible del que produciría `node_ingest_and_reconcile` ese día, y recorre el mismo camino usando el `route_after_gatekeeper` de producción.

Consecuencia práctica: **cualquier regla de decisión que aparezca en `src/backtest/` es un bug**. Si el backtest necesita comportarse distinto, el cambio va en `src/agents/`. `disable_llm()` parchea el símbolo `get_llm` importado en cada módulo de agente (no `src.config.get_llm`), porque `from src.config import get_llm` fija el nombre en el espacio del importador.

División de responsabilidades:
- `data.py` — `PriceStore` (OHLCV cacheado) y `FundamentalStore` (point-in-time desde XBRL). `TodayFundamentalStore` es el almacén deliberadamente sesgado.
- `replay.py` — reconstrucción del estado + ejecución de los agentes reales → `Signal`.
- `engine.py` — contabilidad de cartera. No conoce ni una regla de decisión.
- `metrics.py` — recibe series, devuelve números. No conoce la estrategia.
- `report.py` — markdown, JSON, CSV y PNG.

### Disciplina point-in-time

Es lo que separa un backtest de una ficción; el proyecto la aplica de forma explícita y verificada:

- **`filed` vs `end`**: los hechos XBRL se filtran por `filed <= t`, nunca por `end`. Un ejercicio cerrado el 31-dic no es público hasta el 10-K de febrero. Cuando falta `filed`, se asume un retardo de 45 días (`MIN_REPORTING_LAG_DAYS`), y un `filed` anterior a `end` se sanea. Producción **no** hace esto: `_extract_recent_fact()` en `src/data/sec_edgar.py` ordena por `end` — look-ahead latente conocido, documentado en `AUDIT.md` §4.3.
- **Ventana de precios**: `PriceStore.window()` corta en `as_of` inclusive. Ninguna barra posterior entra jamás en el cálculo de indicadores.
- **`MIN_WINDOW_ROWS = 200`**: por debajo de 200 sesiones, los `min(50, len)` / `min(200, len)` de `_add_technical_indicators` cambian silenciosamente de definición, así que esas fechas se descartan en lugar de emitir una señal distinta a la de producción.
- **Caché con metadatos de cobertura**: `PriceStore._covers()` compara contra el rango *solicitado* (`.meta.json`), no contra las filas del CSV. Sin esto, una ejecución con `--start` posterior deja un histórico truncado que las siguientes reutilizan en silencio.
- Ejecución conservadora en `engine.py`: señal al cierre de `t`, relleno en la apertura de `t+1`; si stop y objetivo se tocan en la misma barra, gana el stop; hueco más allá del stop rellena en la apertura.

Los tests `test_no_lookahead_*`, `test_fundamentals_respect_filed_not_end` y `test_price_cache_rejects_insufficient_coverage` protegen exactamente estas propiedades. **No los relajes para hacer pasar un cambio.**

### Regímenes del backtest

| `--regime` | Fundamentales | Para qué |
|---|---|---|
| `pit` | SEC EDGAR filtrado por `filed <= t` | Resultado principal, insesgado |
| `technical_only` | Gatekeeper neutralizado (`passed=True`) | Aísla la capa técnica |
| `biased` | `yfinance.info` de HOY aplicado al pasado | Mide el tamaño del look-ahead — **etiquétalo siempre como sesgado** |

Todos los outputs del régimen `biased` llevan marca de sesgo. No los presentes como resultado del sistema.

## Convenciones del informe

`backtest_cli.py` mantiene a mano las listas `build_limitations()` y `NEXT_STEPS`, que se vuelcan al informe. Si un cambio altera una limitación o corrige un defecto listado, actualiza esas listas: el informe declara sus sesgos residuales explícitamente (supervivencia del universo, ausencia de Finnhub histórico, sin datos intradía, contrastes múltiples sin corregir) y esa franqueza es intencional. El resultado publicado es que **el sistema no bate a comprar y mantener el índice** y que el rendimiento a 12 meses ordena las categorías al revés de lo que el sistema afirma; no suavices esa conclusión al editar los informes.

## Notas de plataforma

`cli.py` y `backtest_cli.py` fuerzan `sys.stdout.reconfigure(encoding="utf-8")` porque los informes y los prints llevan acentos y emoji, y la consola de Windows fallaría con cp1252. Manténlo en cualquier entrypoint nuevo.
