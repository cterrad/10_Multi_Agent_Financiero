# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
<python> -m pytest tests/test_backtest.py            # suite sin red
<python> -m pytest tests/test_news_analyst.py        # suite sin red (Analista de Noticias)
<python> -m pytest tests/test_llm_texto.py           # suite sin red (contrato de texto del LLM)
<python> -m pytest tests/test_backtest.py::test_no_lookahead_future_prices_do_not_change_past_signal -v
<python> -m pytest tests/test_news_analyst.py -k ruido -v          # filtrar por nombre

# Docker
docker-compose up --build
```

`tests/test_backtest.py`, `tests/test_reconciler.py`, `tests/test_news_analyst.py` y `tests/test_llm_texto.py` son offline y deterministas (los que tocan al LLM usan dobles). `tests/test_fetcher.py` y `tests/test_workflow.py` **golpean yfinance en vivo** y fallan sin red o si yfinance cambia el esquema de `info` — no son fiables en CI.

La primera ejecución de `backtest_cli.py` descarga precios y `companyfacts` de la SEC a `data/cache/` (~250 MB, ignorado por git). A partir de ahí `--offline` reproduce el estudio bit a bit.

## Arquitectura

### Grafo de producción (`src/graph/workflow.py`)

Máquina de estados LangGraph sobre `FinancialAnalysisState` (`src/state.py`, un `TypedDict` que cada nodo actualiza parcialmente):

```
        ┌─ gatekeeper ────┐
ingest ─┤                 ├─ join_analisis → [route_after_gatekeeper] ─┬─ aprobado → technical → debate → fund_manager → END
        └─ news_analysis ─┘                                            └─ rechazado ─────────────────────→ fund_manager → END
```

El corte del gatekeeper es la razón de ser del diseño: un valor rechazado salta el análisis técnico y el debate, y el `fund_manager` le asigna VENTA / VENTA FUERTE directamente.

`gatekeeper` y `news_analysis` corren en paralelo (fan-out desde `ingest`) y convergen en `join_analisis` **antes** del enrutado condicional. Dos restricciones de LangGraph obligan a esa forma exacta, ambas verificadas empíricamente:

- `news_analysis` devuelve solo `news_data` y `news_report`. Si escribiera `logs` o `workflow_status` chocaría con el gatekeeper en el mismo superstep: `FinancialAnalysisState` no declara reductores y LangGraph aborta con `InvalidUpdateError: can receive only one value per step`. Sus trazas las vuelca `node_join_analisis`.
- Colgar el enrutado condicional del `gatekeeper` y llevar `news_analysis` directamente a `debate_unit` **no funciona**: las ramas tendrían longitudes distintas y `debate_unit` coincidiría con `fund_manager` en un superstep, con el mismo error. Unir antes de ramificar lo resuelve y además deja `news_report` disponible en las dos ramas, incluida la de rechazo.

`workflow.py` instancia los agentes y compila el grafo **a nivel de módulo** (`financial_app`), así que importar el módulo tiene efectos secundarios.

### Ingesta y reconciliación (`src/data/`)

`node_ingest_and_reconcile` consulta tres proveedores para el mismo ticker — `DataFetcher` (yfinance: precios + `info`), `SECEdgarClient` (`companyfacts` XBRL) y `FinnhubClient` (opcional, requiere `FINNHUB_API_KEY`) — y los pasa por `DataReconciler.reconcile()`, que cruza las magnitudes coincidentes y penaliza las discrepancias hasta un `confidence_score` acotado en `[0.4, 1.0]`. Los agentes consumen el estado **ya reconciliado**: ninguno vuelve a la red.

Ninguna fuente es obligatoria salvo yfinance. La ausencia de Finnhub o un fallo de la SEC baja la confianza y se declara en `sources_consulted`, pero no detiene el flujo.

### La invariante que sostiene todo el proyecto

**Ninguna variable de decisión depende del LLM.** Los cinco agentes calculan su dictamen con reglas deterministas y, si hay LLM configurado, este solo sobrescribe campos de texto (`summary` en fundamental/technical/news/fund_manager, `synthesis` en debate). Sin token de API, `get_llm()` devuelve `None` y el sistema produce exactamente los mismos ratings.

Esto no es un detalle de estilo: es lo que permite que el backtest reproduzca la lógica real de forma determinista y a coste cero. Se verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()` (`src/backtest/replay.py`), que ejecuta los agentes con y sin un LLM falso y compara `passed_gatekeeper`, `momentum_classification`, `rating`, `position_size_pct`, los niveles de stop/objetivo y el dictamen de noticias (`impact_probability`, `impact_classification`, `direction_classification`, `catalysts`). `backtest_cli.py` aborta si la verificación falla, y `test_llm_is_decision_neutral` la cubre en la suite.

**Si añades lógica a un agente, el resultado del LLM no puede entrar en ninguna rama ni en ningún número.** Solo en texto.

Reglas de decisión concretas (documentadas exhaustivamente en `output/AUDIT.md`):
- Gatekeeper: umbrales `MIN_NET_MARGIN`, `MIN_REVENUE_GROWTH`, `MAX_DEBT_TO_EQUITY` de `src/config.py` (leídos del entorno **en tiempo de import**).
- Momentum: sistema de puntos alcistas/bajistas sobre RSI, MACD, cruce SMA 50/200 y Bandas de Bollinger → `ALCISTA_FUERTE` / `ALCISTA` / `NEUTRAL` / `BAJISTA`.
- Rating final: tabla momentum×RSI en `src/agents/fund_manager.py`; stop = `close − 2.0·ATR`, objetivo = `close + 3.5·ATR`.
- Noticias: `src/agents/news.py` sobre el dosier que recolecta `src/data/news/`. Por ítem, `p = NEWS_ITEM_PROB_MAX · peso_categoría · credibilidad_de_la_fuente · decaimiento(antigüedad) · corroboración · penalización_de_ruido`; el conjunto se agrega con OR ruidoso sobre los `NEWS_TOP_K_ITEMS` mayores → `impact_probability` y bucket ALTA/MEDIA/BAJA. Categoría y dirección salen de diccionarios cerrados, nunca del LLM. Todas las constantes están en `src/config.py`.

#### Contrato del único campo que sí toca el LLM

La respuesta del proveedor **nunca** se asigna directamente. Los cinco agentes hacen `texto = texto_de_respuesta_llm(llm.invoke(prompt))` (`src/config.py`) y solo sobrescriben el campo si `texto` no es `None`:

- Los proveedores modernos devuelven `content` como **lista de bloques** (`[{"type": "text", "text": "..."}]`), no como cadena. Asignarlo tal cual metía una lista de diccionarios de Python en el informe y en `daily_selection.json` — el defecto que motivó el helper.
- Devuelve `None` (no cadena vacía) cuando no hay texto utilizable, precisamente para que el agente **conserve su resumen determinista** en lugar de perder información ya calculada.
- La llamada va siempre dentro de un `try/except`: un fallo del proveedor degrada al texto heurístico, nunca tumba al agente.

`tests/test_llm_texto.py` fija ese contrato para los cinco agentes: `summary`/`synthesis` son `str` pase lo que pase.

### Analista de Noticias (`src/agents/news.py` + `src/data/news/`) — capa ASESORA

Estima la probabilidad de que la actualidad de una empresa mueva su cotización. Reparto de responsabilidades idéntico al del resto del sistema: `src/data/news/` ingiere y normaliza, `src/agents/news.py` decide.

- Tres buscadores en paralelo (`ThreadPoolExecutor`), cada uno con su propio try/except: `sec_8k` (8-K con Ítem 2.02, vía `SECEdgarClient.get_recent_8k_earnings`), `google_news` (RSS público) y `tavily` (requiere `TAVILY_API_KEY` **y** el paquete `langchain-tavily`; sin cualquiera de los dos degrada a esa fuente y lo declara en el informe). Ninguna caída tumba el nodo: el peor caso es `status="SIN_DATOS"` con los motivos.
- El agregador deduplica por URL y por índice de Jaccard entre titulares normalizados. La corroboración se cuenta en **dominios distintos**, no en buscadores distintos.
- Caché en `data/cache/news/{TICKER}_{YYYY-MM-DD}.json`. La clave incluye el día porque las noticias son un dato "de hoy".
- El agente es **puro**: consume `state["news_data"]` y no toca la red, igual que el gatekeeper consume los fundamentales ya reconciliados.

**Es una capa asesora, no un input de decisión.** Aparece en el informe y aporta un argumento al `debate_unit`, pero no toca `rating` ni `position_size_pct`. El motivo es el backtest: dos de sus tres fuentes son buscadores "de hoy" y no hay forma asequible de reconstruir qué era visible en una fecha pasada, así que el nodo **se excluye del `HistoricalReplayer`** (documentado en el encabezado de `src/backtest/replay.py` y en `build_limitations()`). Mientras siga siendo asesora, su ausencia en el replay no altera ni una señal. `test_news_report_does_not_alter_decision` protege exactamente esa premisa: **si conectas las noticias a la decisión, ese test debe fallar y el backtest deja de ser válido hasta que exista un `NewsStore` point-in-time.**

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

## Configuración del proveedor de LLM

`LLM_PROVIDER` solo tiene rama implementada para `huggingface`, `openai` y `gemini` en `get_llm()`. `ollama` y `heuristic` —anunciados en `README.md` y `.env.example`— caen por el final y devuelven `None`, que es exactamente el motor heurístico determinista. **No es un bug pendiente**: sin LLM el sistema produce los mismos ratings, así que `None` es un modo de operación de primera clase, no un fallback degradado.

Cualquier error al instanciar el proveedor se captura y también devuelve `None`. Por eso "el sistema funciona" nunca prueba que el LLM esté conectado; para eso hay que mirar los `summary` del informe.

Los umbrales del gatekeeper de `.env.example` (`MIN_NET_MARGIN=0.05`, `MAX_DEBT_TO_EQUITY=3.0`) **no coinciden** con los valores por defecto de `src/config.py` (`0.03` y `3.5`). Si comparas resultados entre máquinas, comprueba primero cuál de los dos está activo.

## Notas de plataforma

`src/notebooks/` contiene prototipos, no código del pipeline: `agent_search_web.ipynb` es el borrador del que salió el Analista de Noticias (pedía criterio al LLM, algo que la versión de producción sustituye por diccionarios cerrados) y `plotter_graph.ipynb` dibuja el grafo. Nada de `src/` los importa.

`cli.py` y `backtest_cli.py` fuerzan `sys.stdout.reconfigure(encoding="utf-8")` porque los informes y los prints llevan acentos y emoji, y la consola de Windows fallaría con cp1252. Manténlo en cualquier entrypoint nuevo.
