# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Pipeline multi-agente (LangGraph) que selecciona acciones: ingiere y reconcilia datos de yfinance/SEC EDGAR/Finnhub, filtra con un gatekeeper fundamental, puntúa calidad y valoración con siete escuelas clásicas (Piotroski, Altman, Graham, Buffett, Lynch, Greenblatt, Sloan), cruza momentum técnico, sitúa el precio frente a sus soportes estructurales, lee el régimen de volatilidad del mercado, fija el precio de entrada con el posicionamiento en futuros (COT) y en la cadena de opciones, incorpora una capa de noticias asesora, y emite un rating en 5 categorías con tamaño de posición y niveles de stop/objetivo — todo por reglas deterministas (ver «La invariante que sostiene todo el proyecto» más abajo). `src/backtest/` reejecuta esos mismos agentes sobre datos históricos point-in-time para medir si la selección aporta sobre el índice o el azar.

El código, los comentarios y la documentación de este proyecto están en español. Mantén ese idioma al escribir código nuevo, docstrings o informes.

## Entorno

El proyecto **no** corre con el `python` del PATH. Usa siempre el intérprete conda por ruta absoluta (`conda activate` no persiste entre llamadas de herramienta):

```powershell
C:\Users\cterr\anaconda3\envs\venv-multi_gent_finantial\python.exe   # Python 3.10
```

Los imports son de la forma `from src...`, así que todo se ejecuta **desde la raíz del repositorio** (no hay `pyproject.toml` ni instalación en modo editable).

## Comandos

```powershell
# Análisis en vivo. Escribe TRES documentos más el JSON:
#   output/resumen_ejecutivo.md   la decisión agregada (punto de entrada)
#   output/daily_selection.md     el informe completo
#   output/detalle/{TICKER}.md    ficha por valor + traza de herramientas
<python> cli.py --tickers NVDA,AAPL,TSLA
<python> cli.py --tickers NVDA,AAPL --sin-cartera        # omite correlaciones y límites
<python> cli.py --tickers NVDA,AAPL --sin-benchmark      # momentum absoluto, no relativo
<python> cli.py --tickers NVDA,AAPL --sin-macro          # sin COT: no hay ajuste de entrada
<python> cli.py --tickers NVDA --benchmark QQQ --capital 250000
<python> cli.py --detalle NVDA                           # vuelca la ficha pormenorizada
<python> cli.py --log INFO --tickers NVDA                # detalle en consola; el JSONL va completo siempre

# Agente investigador (ReAct asesor). Requiere LLM y NO altera ningún dictamen.
<python> cli.py --investigar DOCN "Por que el Altman es 0.04 con flujo de caja libre positivo?"

# Dashboard FastAPI en http://localhost:8000
<python> -m src.web.app

# Backtest histórico (regímenes: pit | technical_only | biased)
<python> backtest_cli.py --start 2015-01-01 --end 2025-12-31 --regime pit
<python> backtest_cli.py --regime technical_only --out output/regimes/technical_only
<python> backtest_cli.py --con-reflexion             # activa la capa REFUTADA (ver su sección)
<python> backtest_cli.py --con-entrada-limitada     # ejecuta la entrada como orden LIMITADA (REFUTADA, ver su sección)
<python> backtest_cli.py --sin-estructura           # ablación: sin soportes de precio → sin nivel de entrada
<python> backtest_cli.py --sin-regimen              # ablación: sin veto de volatilidad
<python> backtest_cli.py --con-meta                 # meta-etiquetado walk-forward (REFUTADO, ver su sección)
<python> backtest_cli.py --con-meta                 # meta-etiquetado walk-forward (REFUTADO, ver su sección)
<python> backtest_cli.py --offline --quiet          # sin red, solo caché

# Recarga del archivo de FRED/ALFRED. Reejecutable sin riesgo: un vintage
# cacheado NUNCA se sobrescribe y una redescarga divergente levanta excepción.
<python> -m src.data.fred.backfill --desde 2013 --hasta 2026

# Tests
# Todo lo determinista de una vez (466 pruebas, ~5 s). Es el comando por defecto:
# `pytest tests/` a secas arrastra las dos suites que salen a la red (ver abajo).
<python> -m pytest tests/ --ignore=tests/test_fetcher.py --ignore=tests/test_workflow.py -q
<python> -m pytest tests/                            # incluye las dos suites en vivo
<python> -m pytest tests/test_backtest.py            # suite sin red
<python> -m pytest tests/test_news_analyst.py        # suite sin red (Analista de Noticias)
<python> -m pytest tests/test_llm_texto.py           # suite sin red (contrato de texto del LLM)
<python> -m pytest tests/test_integridad_datos.py    # suite sin red (ausencia ≠ cero)
<python> -m pytest tests/test_momentum.py            # suite sin red (clasificador técnico)
<python> -m pytest tests/test_calidad.py             # suite sin red (Piotroski/Altman/Graham/estilo)
<python> -m pytest tests/test_cartera.py             # suite sin red (correlación y riesgo)
<python> -m pytest tests/test_futuros.py             # suite sin red (COT point-in-time y sesgo macro)
<python> -m pytest tests/test_opciones.py            # suite sin red (Griegas, max pain, percentiles)
<python> -m pytest tests/test_entrada.py             # suite sin red (el ajuste de entrada solo baja)
<python> -m pytest tests/test_reflexion.py           # suite sin red (memoria point-in-time, el factor solo baja)
<python> -m pytest tests/test_estructura.py          # suite sin red (soportes causales, el soporte solo baja la entrada)
<python> -m pytest tests/test_regimen.py             # suite sin red (ALFRED point-in-time, el veto solo baja, vintage inmutable)
<python> -m pytest tests/test_fuentes_pit.py         # suite sin red (clasificación PIT de las fuentes de decisión)
<python> -m pytest tests/test_entrada_limitada.py     # suite sin red (ejecución de orden limitada: relleno, expiración, sustitución)
<python> -m pytest tests/test_meta.py                # suite sin red (artefacto anacrónico, corte por desenlace, el factor solo recorta)
<python> -m pytest tests/test_meta.py                # suite sin red (artefacto anacrónico, corte por desenlace, el factor solo recorta)
<python> -m pytest tests/test_tools.py               # suite sin red (registro de tools y frontera JSON)
<python> -m pytest tests/test_mensajes.py            # suite sin red (traza tipada de los agentes)
<python> -m pytest tests/test_investigador.py        # suite sin red (el ReAct no toca la decisión)
<python> -m pytest tests/test_backtest.py::test_no_lookahead_future_prices_do_not_change_past_signal -v
<python> -m pytest tests/test_news_analyst.py -k ruido -v          # filtrar por nombre

# Docker
docker-compose up --build
```

`tests/test_backtest.py`, `tests/test_reconciler.py`, `tests/test_news_analyst.py`, `tests/test_llm_texto.py`, `tests/test_integridad_datos.py`, `tests/test_momentum.py`, `tests/test_calidad.py`, `tests/test_cartera.py`, `tests/test_tools.py`, `tests/test_mensajes.py`, `tests/test_futuros.py`, `tests/test_opciones.py`, `tests/test_entrada.py`, `tests/test_reflexion.py`, `tests/test_estructura.py`, `tests/test_regimen.py`, `tests/test_fuentes_pit.py`, `tests/test_entrada_limitada.py`, `tests/test_meta.py` y `tests/test_investigador.py` son offline y deterministas (los que tocan al LLM usan dobles). `tests/test_fetcher.py` y `tests/test_workflow.py` **golpean yfinance en vivo** y fallan sin red o si yfinance cambia el esquema de `info` — no son fiables en CI.

La primera ejecución de `backtest_cli.py` descarga precios y `companyfacts` de la SEC a `data/cache/` (~250 MB, ignorado por git). Las series de volatilidad se recargan aparte con `python -m src.data.fred.backfill` (~850 KB) y **requieren `FRED_API_KEY`**, gratuita. A partir de ahí `--offline` reproduce el estudio bit a bit.

## Arquitectura

### Los tres puntos de entrada NO son equivalentes

`financial_app.invoke()` analiza **un** ticker. Todo lo que es «de lote» —benchmark, dosier macro COT, memoria de reflexión, construcción de cartera— vive **fuera** del grafo, en quien orquesta el bucle, porque son datos comunes a todos los valores y descargarlos dentro sería pedir el mismo fichero una vez por ticker (ver el docstring de `run_stock_analysis`).

La consecuencia es que **el dashboard produce un dictamen distinto del de la CLI sobre el mismo valor**, y no está roto: es que solo la CLI orquesta el lote.

| | `cli.py` | `src/web/app.py` (`POST /api/analyze`) | `backtest_cli.py` |
|---|---|---|---|
| `benchmark_data` | sí (`cargar_benchmark`) | **no** → momentum absoluto | sí |
| `macro_data` (COT) | sí (`cargar_contexto_macro`, una vez) | **no** → sin sesgo macro ni veto macro | sí (`COTStore`) |
| `regimen_data` (VIX) | sí (`cargar_regimen`, una vez) | **sí** (`cargar_regimen`, una vez por petición) | sí (`FREDStore`) |
| `reflexion_data` | archiva siempre; decide con `--con-reflexion` | **no** | opcional |
| `meta_data` (meta-modelo) | carga el artefacto si `META_HABILITADO` | **no** | opcional (`--con-meta`) |
| `PortfolioConstructor` | sí | **no** — pesos individuales sin tope sectorial ni de correlación | sí |
| Informe | los tres documentos + JSON | `generate_daily_selection(results)` a secas | `output/backtest_report.md` |

`src/web/app.py` cablea **únicamente** `regimen_data`; los otros tres argumentos de lote siguen con su valor por defecto. La asimetría es deliberada y tiene un motivo concreto: el veto de régimen puede TOPAR un dictamen en MANTENER, y un dashboard que emitiera COMPRA FUERTE en mitad de un episodio de pánico mientras la CLI emite MANTENER sobre el mismo valor sería una divergencia difícil de defender. Las otras tres capas modulan; esta corta.

**Si añades una capa de lote nueva, `cli.py` no es el único llamante**: o la cableas también en el dashboard o el `README` deja de describir lo que el dashboard hace.

### Grafo de producción (`src/graph/workflow.py`)

Máquina de estados LangGraph sobre `FinancialAnalysisState` (`src/state.py`, un `TypedDict` que cada nodo actualiza parcialmente):

```
                              ┌─ gatekeeper ────┐
ingest → quality_analysis ────┼─ news_analysis ─┼─ join → [route] ─┬─ aprobado → technical → estructura → posicionamiento → debate → meta → fund_manager → END
                              └─ regimen ───────┘                  └─ rechazado ──────────────────────────────────────────────────────────→ fund_manager → END
```

El nodo `meta` va **entre el debate y el Fund Manager** por una dependencia de datos estricta en las dos direcciones: consume TODOS los informes anteriores —calidad, técnico, estructura, régimen, posicionamiento— para armar su vector de 23 variables, y el Fund Manager consume su probabilidad para producir `factor_meta`. Antes daría un vector incompleto; después llegaría tarde. Solo corre en la rama aprobada, por el mismo motivo que el posicionamiento: la probabilidad de que acierte una compra que no se va a hacer no significa nada. El artefacto viaja a **nivel de módulo** (`_META_ARTEFACTO`) y no dentro del estado, porque no es serializable —`daily_selection.json` lo rompería— y porque es común a todo el lote; es el mismo patrón que `HistoricalReplayer.meta_artefacto`.

`estructura` y `posicionamiento` van **secuenciales después de `technical`**, en ese orden, y el motivo es una cadena de dependencias de datos real: `estructura` consume `close` y `atr` para expresar la distancia al soporte en unidades de volatilidad, y `posicionamiento` consume el `soporte` que aquella produce —como cuarto candidato de nivel— más `momentum_score` (tercera pata de su comparación de tres vías), `sobreextendido` (lo que le prohíbe perseguir el precio) y `atr` (lo que acota su ajuste). Paralelizarlo no rompería el grafo — produciría otro dictamen, exactamente igual que reordenar los pasos dentro de `quality.py`. Y sería paralelismo sin ganancia, porque el nodo no toca la red: la recolección la hacen `obtener_contexto_macro` y `obtener_cadena_opciones` desde la ingesta. Colgado del mismo superstep que `technical` tampoco podría escribir `workflow_status`, que sigue siendo un escalar sin reductor.

`quality_analysis` va **secuencial y antes del fan-out**, no en paralelo, por dos motivos: es cálculo puro sobre datos ya ingeridos (paralelizarlo no ahorra latencia y solo añadiría un tercer escritor al mismo superstep), y colocarlo antes del gatekeeper deja sus puntuaciones y banderas rojas disponibles **también para los valores rechazados** — un Altman en zona de insolvencia es justo lo que se quiere leer sobre una empresa que no pasa el filtro.

El corte del gatekeeper es la razón de ser del diseño: un valor rechazado salta el análisis técnico y el debate, y el `fund_manager` le asigna VENTA / VENTA FUERTE directamente.

`gatekeeper`, `news_analysis` y `regimen` corren en paralelo (fan-out de tres ramas desde `quality_analysis`) y convergen en `join_analisis` **antes** del enrutado condicional. `regimen` está ahí y no en la rama aprobada porque no tiene ninguna dependencia de datos que lo fuerce a ir después —consume `regimen_data`, que viaja en el estado inicial— y porque colocarlo antes del enrutado deja su lectura disponible **también para los valores rechazados**, exactamente el mismo argumento que sitúa a `quality_analysis` antes del gatekeeper. Como `news_analysis`, escribe `logs` y `messages` (ambos con reductor) pero **no** `workflow_status`.

**`FinancialAnalysisState` ahora SÍ declara reductores** en dos canales: `messages` con `add_messages` y `logs` con `operator.add`. Eso cambia una de las dos restricciones históricas y deja la otra intacta:

- **Resuelta.** `news_analysis` ya puede escribir sus propias trazas. Antes chocaba con el gatekeeper en el mismo superstep y LangGraph abortaba con `InvalidUpdateError: can receive only one value per step`, así que `node_join_analisis` las volcaba en su nombre. Ese apaño se ha eliminado. Lo que `news_analysis` sigue **sin** escribir es `workflow_status`: es un escalar sin reductor y dos nodos paralelos no tendrían un valor correcto que fusionar.
- **Vigente.** Colgar el enrutado condicional del `gatekeeper` y llevar `news_analysis` directamente a `debate_unit` **sigue sin funcionar**: las ramas tendrían longitudes distintas y `debate_unit` coincidiría con `fund_manager` en un superstep. Por eso `join_analisis` se conserva.

**Con reductor, cada nodo devuelve SOLO sus líneas nuevas, nunca el acumulado.** Los nodos hacían `logs = state.get("logs", []); logs.append(...); return {"logs": logs}`; con `operator.add` eso duplicaría el log en silencio — no rompe nada, solo ensucia el informe.

`workflow.py` instancia los agentes y compila el grafo **a nivel de módulo** (`financial_app`), así que importar el módulo tiene efectos secundarios.

### Tools (`src/tools/`) — donde viven ahora las reglas de cálculo

Todas las reglas de cálculo del sistema son **tools de LangChain invocables por nombre**. Antes eran métodos privados dentro de los agentes: `QualityAnalystAgent` tenía las siete escuelas clásicas encerradas en una clase de 1 200 líneas, sin forma de calcular una sola por separado ni de exponerla.

```
src/tools/
  __init__.py       REGISTRO_TOOLS (nombre → tool) · TOOLS_LECTURA · obtener_tool()
  extraccion.py     yfinance, SEC EDGAR, Finnhub, reconciliación, noticias, benchmark
  fundamentales.py  criterios del gatekeeper, umbral de deuda sectorial
  calidad.py        las siete escuelas + puntuaciones, convicción, banderas, estilo
  tecnico.py        los cinco bloques de momentum + la etiqueta
  futuros.py        z-score del posicionamiento COT, mapeo sector→contrato, sesgo macro
  opciones.py       put/call, niveles de OI, max pain, Griegas, exposición gamma, skew
  niveles.py        soportes estructurales del OHLCV, distancia en ATR, sobreextensión
  regimen.py        z-score y curva de la volatilidad implícita, régimen y puerta
  covarianza.py     denoising Marchenko-Pastur de la matriz de correlaciones
  meta.py           probabilidad del meta-modelo → factor de tamaño que solo recorta
  riesgo.py         freno por drawdown de la cartera (inerte en producción)
  etiquetado.py     triple barrera sobre los niveles que el propio sistema emitió
  validacion.py     CV purgada con embargo, unicidad y pesos de muestra
  noticias.py       puntuación por ítem y agregación por OR ruidoso
  reflexion.py      factor de tamaño y veto a partir de la memoria de resultados
  debate.py         tesis alcista, tesis bajista, condiciones de invalidación
  decision.py       rating compuesto, vetos, niveles de riesgo, tamaño, perfil R:R
  cartera.py        construcción de cartera y matriz de correlaciones
```

**Los cuerpos son los de siempre.** El traslado fue mecánico —los scorers nunca usaban `self`— y el `golden` del backtest se verificó idéntico tras cada agente migrado. **Una segunda copia de una regla de decisión es un bug**, exactamente igual que si apareciera en `src/backtest/`.

Dos capas por tool, y el motivo no es estético: los scorers operan sobre `Dict[str, Magnitud]`, que no es serializable y por tanto **no cabe en un `ToolMessage`**. La implementación (`_altman`, `_graham`, …) conserva esa firma; la fachada `@tool` (`calcular_altman`, …) convierte en el borde con `detalle_magnitudes` / `magnitudes_desde_detalle` (`src/data/magnitudes.py`). Los docstrings de las fachadas son la descripción que lee el LLM en la rama ReAct: se redactan como documentación de API.

`src/tools/extraccion.py` es el **único** módulo que sale a la red. Mirando los imports de un agente se sabe si puede hacer una petición; `tests/test_tools.py` fija esa separación en las dos direcciones.

`TOOLS_LECTURA` es el subconjunto que se enlaza al agente investigador. **Excluye deliberadamente** `calcular_rating_compuesto`, `aplicar_vetos`, `calcular_niveles_riesgo`, `dimensionar_posicion`, `calcular_perfil_riesgo`, `ajustar_precio_entrada`, `consultar_reflexion`, `construir_cartera`, `denoise_correlaciones` y `reconciliar_fuentes`. `TOOLS_FUTUROS`, `TOOLS_OPCIONES`, `TOOLS_NIVELES` y `TOOLS_REGIMEN` entran **enteras**: explican, no deciden. El soporte que devuelve `identificar_soportes` es un CANDIDATO, exactamente como el que devuelve `identificar_niveles_oi`; quien lo convierte en precio de entrada es `ajustar_precio_entrada`, que vive en `src/tools/decision.py`. Y el régimen que etiqueta `clasificar_regimen_volatilidad` solo llega al dictamen a través de `aplicar_vetos`, que tampoco se expone. La única tool de posicionamiento que produce una variable de decisión es `ajustar_precio_entrada`, y vive en `src/tools/decision.py` — la exclusión es estructural (por módulo), no una lista negra que haya que recordar actualizar. Es la barrera que impide que el modelo emita un dictamen, y `test_el_react_no_alcanza_ninguna_tool_de_decision` la protege. **Si añades una tool que produzca una variable de decisión, mantenla fuera de esa lista.**

### Clase base de los agentes (`src/agents/base.py`)

Los **nueve** agentes deterministas —gatekeeper, calidad, técnico, régimen, estructura, noticias, posicionamiento, debate y fund manager— heredan de `AgenteBase` e implementan dos métodos: `decidir(state, traza)` —todo el análisis determinista— y `prompt_usuario(state, informe)`. `analyze(state) -> dict` se conserva como firma pública porque es el contrato que consumen `src/graph/workflow.py` y `src/backtest/replay.py`.

El orden de `analyze()` es la invariante hecha código: `decidir()` va **siempre** antes que `_redactar()`, de modo que cuando el LLM interviene todas las variables de decisión ya están fijadas y lo único que se le asigna es la clave que declara `campo_texto` (`summary` en ocho agentes, `synthesis` en el debate).

`usar_tool(nombre, args, traza)` es el `take_action` de `RAG_Agent.py` del curso, con una diferencia que lo es todo: **allí los `tool_calls` los emitía el modelo, aquí los emite el código.** La traza resultante tiene la misma forma —`AIMessage` con `tool_calls`, `ToolMessage` con el resultado y su `tool_call_id`— pero el plan de llamadas es determinista. Esa es la razón de que el sistema pueda tener tools sin romper su invariante: la forma de un agente ReAct, la sustancia de una función pura. Está también a nivel de módulo porque el nodo de ingesta invoca tools y deja traza sin ser un agente.

Dos detalles que no conviene deshacer:

- **`_obtener_llm()` resuelve `get_llm` en el módulo de la SUBCLASE**, no en el de la base. `from src.config import get_llm` fija el nombre en el espacio del importador, y todo el sistema se apoya en poder sustituirlo módulo a módulo: `disable_llm()` hace `mod.get_llm = lambda: None` sobre cada módulo de agente, y `tests/test_llm_texto.py` inyecta sus dobles igual. Si la base llamara a su propio `get_llm`, esos parches no surtirían efecto y el backtest abriría llamadas de red y de coste en mitad de una ejecución offline.
- **Los identificadores de la traza son secuenciales, no UUID.** Con UUID, dos ejecuciones del mismo análisis producían informes distintos —lo detectó `test_el_agente_es_reproducible`— y `daily_selection.json` cambiaba entero en cada pasada, volviendo inútil cualquier diff. Por lo mismo, `Traza.a_dict()` **no publica duraciones**: los milisegundos son irrepetibles por naturaleza y viven en el JSONL.

### Prompts (`src/prompts.py`)

Todos los system prompts y los constructores de prompt de usuario están aquí. Antes cada agente llevaba el suyo incrustado como f-string en mitad de `analyze()` y se invocaba con `llm.invoke(prompt)` — una cadena pelada, **sin `SystemMessage`**. Ahora la llamada es `llm.invoke([SystemMessage(...), HumanMessage(...)])`.

Los nueve system prompts comparten tres bloques porque describen invariantes del sistema y no del agente: la **cláusula anti-decisión** (el modelo redacta, no decide), la **cláusula de ausencia** (una magnitud «no disponible» se dice, no se rellena con cero) y el **contrato de salida** (número de frases, español, prosa continua, sin markdown ni preámbulos). La cláusula de ausencia es la regla nº 1 del proyecto y antes solo aparecía en el prompt del gatekeeper, aunque aplica a los nueve.

Los constructores del prompt de usuario formatean **toda** cifra con `_v()`, que imprime «no disponible» en vez de un cero: de nada sirve la cláusula del system prompt si el prompt de usuario le presenta al modelo un `0.0` indistinguible de un valor real.

### Agente Investigador (`src/agents/investigador.py` + `src/graph/investigacion.py`) — capa ASESORA

El **único ReAct real** del sistema: `bind_tools` + `ToolNode` + bucle condicional, el patrón de `ReAct.py` sin adulterar. Aquí el LLM sí elige qué tools invocar, con qué argumentos y cuándo parar.

Puede serlo sin romper nada por tres barreras, todas comprobables:

1. **Alcance.** Solo ve `TOOLS_LECTURA`. Las tools que emiten dictámenes no están en su mesa.
2. **Salida.** Escribe un único campo, `research_report`, y solo texto. `test_research_report_does_not_alter_decision` comprueba que añadirlo al estado no mueve `rating`, `position_size_pct`, `peso_objetivo` ni los niveles. **Si algún día ese test falla, el ReAct ha entrado en la ruta de decisión y el backtest deja de ser válido.**
3. **Topología.** Vive en un grafo aparte que no está conectado a `financial_app`. Se pide a mano con `cli.py --investigar`; la ejecución diaria no lo invoca porque cuesta dinero y exige clave.

Queda **excluido del backtest** y `disable_llm()` lo cubre, de modo que `modelo_con_tools()` levanta `LLMNoConfigurado` en lugar de abrir una factura en mitad de una ejecución offline. Es el único agente sin motor heurístico al que degradar: su trabajo *es* el razonamiento del modelo, y fallar de forma explícita es más honesto que devolver un informe vacío que parezca una respuesta.

Dos comportamientos del proveedor que costó descubrir y que el ejemplo del curso no contempla:

- **Gemini cierra a veces un turno con un bloque de solo pensamiento**: texto vacío más una firma, sin `tool_calls`. Con la condición del curso («¿hay `tool_calls`? si no, fin») ese turno se tomaba por respuesta final y el agente devolvía cadena vacía habiendo consultado cuatro tools. Ahora un turno sin tools y sin texto se trata como «el modelo aún no ha terminado» y se le devuelve el control, acotado por `MAX_TURNOS_VACIOS` y por el `recursion_limit` del grafo.
- **No se puede reintentar sin más**: Gemini rechaza una petición cuyo último turno sea del propio modelo (*«does not support model prefilling»*). `_nodo_reencauzar` intercala un `HumanMessage` que además pide explícitamente el cierre.

### Logging estructurado (`src/utils/logging_agentes.py`)

Dos canales con propósitos distintos y deliberadamente separados:

- **`logging` estándar → consola y `output/logs/{fecha}_{ticker}.jsonl`.** Un registro por evento (`inicio`, `tool_call`, `tool_result`, `llm`, `dictamen`) con `duracion_ms`, argumentos y resultado resumido. Es la traza de auditoría, y es JSONL porque se consulta con herramientas, no leyéndola.
- **La lista `logs` del estado** sigue existiendo, pero solo como resumen legible que el informe imprime. Ya no es la fuente de verdad.

Tres detalles con cicatriz:

- **El nivel se aplica a los HANDLERS, no al logger.** Ponerlo en el logger silenciaba también el fichero: pedir una consola tranquila dejaba el JSONL vacío.
- **`_AdaptadorQueFusiona`.** El `LoggerAdapter` de la biblioteca estándar hace `kwargs["extra"] = self.extra`, es decir **sustituye**. Con él, `log.info("tool_result", extra={"tool": ..., "duracion_ms": ...})` llegaba al fichero sin la tool ni el tiempo — justo lo que la traza existe para conservar.
- **Claves reservadas.** `logging` revienta con `KeyError` si `extra` trae una clave que ya existe en `LogRecord` (`args`, `name`, `module`…). El adaptador las renombra en vez de fallar: la traza es un medio, nunca el motivo por el que un dictamen deja de emitirse.

**Por defecto no se configura en el backtest.** Un estudio de 2015 a 2025 recorre ~50 valores en ~130 rebalanceos con ~30 tools por análisis: cientos de miles de registros que no aportan nada al estudio. Sin `configurar_logging()`, el logger no escribe fichero.

### Ingesta y reconciliación (`src/data/`)

`node_ingest_and_reconcile` consulta tres proveedores para el mismo ticker — `DataFetcher` (yfinance: precios + `info`), `SECEdgarClient` (`companyfacts` XBRL) y `FinnhubClient` (opcional, requiere `FINNHUB_API_KEY`) — y los pasa por `DataReconciler.reconcile()`, que cruza las magnitudes coincidentes y penaliza las discrepancias hasta un `confidence_score` acotado en `[0.4, 1.0]`. Los agentes consumen el estado **ya reconciliado**: ninguno vuelve a la red.

Ninguna fuente es obligatoria salvo yfinance. La ausencia de Finnhub o un fallo de la SEC baja la confianza y se declara en `sources_consulted`, pero no detiene el flujo.

### Ausencia de dato ≠ cero (`src/data/magnitudes.py`)

La regla más importante después de la invariante del LLM. El sistema colapsaba las dos cosas en el mismo `0.0` (`info.get("revenueGrowth", 0.0)`, `metrics.get("net_margin", 0.0)`), y el resultado observado era que **una empresa sin cobertura de datos y otra realmente sin ingresos producían el mismo veredicto y los mismos motivos**: «Margen Neto (0.0%) por debajo del umbral mínimo».

Ahora toda magnitud ausente viaja como `None` y se declara. Las consecuencias recorren el sistema entero:

- `DataFetcher` devuelve `None` y publica `campos_ausentes`.
- `DataReconciler` penaliza la ausencia en `confidence_score` (antes solo penalizaba el *desacuerdo*: con SEC caída y Finnhub sin configurar, el estado decía `SINGLE_VENDOR_FALLBACK` y la puntuación decía 1.0).
- El gatekeeper tiene **tres veredictos**: `APROBADO`, `RECHAZADO` y `DATOS_INSUFICIENTES`.
- El Fund Manager traduce `DATOS_INSUFICIENTES` a `SIN OPINION`, no a `VENTA`.
- `FundamentalStore.as_of()` en el backtest propaga `None` igual que producción.

**No reintroduzcas un default numérico en ninguna de estas rutas.** `tests/test_integridad_datos.py` fija exactamente esta propiedad.

Dos correcciones de unidades del mismo bloque, ambas con test:

- `debtToEquity` de yfinance viene **siempre en porcentaje**. La regla anterior `if v > 10: v /= 100` adivinaba la unidad y fallaba justo en las empresas sanas: una compañía con un 8% de deuda se leía como 8.0x y el gatekeeper la rechazaba por apalancamiento. La conversión es incondicional.
- `trailingPE` y `forwardPE` ya no se mezclan en silencio: `pe_origen` declara cuál alimentó la decisión.

### La invariante que sostiene todo el proyecto

**Ninguna variable de decisión depende del LLM.** Los siete agentes calculan su dictamen con reglas deterministas y, si hay LLM configurado, este solo sobrescribe campos de texto (`summary` en fundamental/quality/technical/news/posicionamiento/fund_manager, `synthesis` en debate). Sin token de API, `get_llm()` devuelve `None` y el sistema produce exactamente los mismos ratings.

Esto no es un detalle de estilo: es lo que permite que el backtest reproduzca la lógica real de forma determinista y a coste cero. Se verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()` (`src/backtest/replay.py`), que ejecuta los agentes con y sin un LLM falso y compara `passed_gatekeeper`, `momentum_classification`, `rating`, `position_size_pct`, los niveles de stop/objetivo y el dictamen de noticias (`impact_probability`, `impact_classification`, `direction_classification`, `catalysts`) el del Analista de Calidad (`style_classification`, `conviccion_fundamental`, las cuatro puntuaciones, F-Score y Z-Score) el del Analista de Posicionamiento (`sesgo_macro`, `sesgo_opciones`, `entrada_clasificacion`, `confluencia`, `nivel_referencia`, `ajuste_entrada_pct`, `precio_entrada_objetivo`, `gamma_flip`, `max_pain`), el del Analista de Estructura (`soporte`, `soporte_origen`, `soporte_lejano`, `distancia_atr`, `estructura`), el del Analista de Régimen (`regimen_clasificacion`, `puerta_regimen`, `nivel_volatilidad`, `zscore_volatilidad`, `curva_invertida`, `volatilidad_relativa`) el `factor_reflexion` de la memoria de reflexión y el `factor_meta` del meta-modelo. En el caso del posicionamiento la independencia del modelo no es una propiedad deseable sino un **requisito**: `stop_loss_atr` y `take_profit_atr`, que ya se comparaban, cuelgan directamente de `precio_entrada_objetivo`. `backtest_cli.py` aborta si la verificación falla, y `test_llm_is_decision_neutral` la cubre en la suite.

**Si añades lógica a un agente, el resultado del LLM no puede entrar en ninguna rama ni en ningún número.** Solo en texto.

La invariante sobrevive a la introducción de tools porque **el plan de llamadas lo escribe el código, no el modelo** (ver `src/agents/base.py`). La única pieza donde el LLM sí elige es el agente investigador, que está fuera de la ruta de decisión y solo alcanza `TOOLS_LECTURA`.

Reglas de decisión concretas (documentadas exhaustivamente en `output/AUDIT.md`):
- Gatekeeper: umbrales `MIN_NET_MARGIN`, `MIN_REVENUE_GROWTH`, `MAX_DEBT_TO_EQUITY` de `src/config.py` (leídos del entorno **en tiempo de import**), con excepciones sectoriales en `GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR` — aplicar el mismo límite de deuda a un banco que a una empresa de software es un error de categoría.
- Calidad y valoración: `src/tools/calidad.py` (orquestado por `src/agents/quality.py`) → cuatro puntuaciones 0-100 (calidad, valoración, crecimiento, solvencia), `conviccion_fundamental` y `style_classification`. Ver la sección propia más abajo.
- Momentum: `src/tools/tecnico.py`, una tool por bloque. Puntuación **continua** en `[-100, +100]` como suma ponderada de cinco bloques (tendencia 30, MACD 20, RSI 20, Bollinger 10, momentum de precio 20); las etiquetas son cortes sobre ese número. Constantes `MOMENTUM_*` en `src/config.py`.
- Rating final: puntuación compuesta `0.65·convicción + 0.35·momentum_normalizado` cortada por `CORTES_RATING` en `src/tools/decision.py`, más vetos que **solo bajan** (`aplicar_vetos`; `test_los_vetos_solo_bajan_el_rating` recorre el producto cartesiano de condiciones para comprobarlo). Stop y objetivo salen de `ATR_AJUSTE_POR_ESTILO`, que varía el múltiplo y el horizonte según el estilo asignado.
- Precio de entrada: `src/tools/futuros.py` + `src/tools/opciones.py` + `src/tools/niveles.py` (orquestado por `src/agents/posicionamiento.py` y `src/agents/estructura.py`) → confluencia de tres vías entre sesgo macro (z-score COT), sesgo de la cadena de opciones y `momentum_score`. El **nivel** sale de CUATRO candidatos —soporte de open interest, max pain, punto de inflexión de la gamma y **soporte estructural del precio**—, de los cuales solo el último es reconstruible point-in-time; el macro solo da dirección. `ajuste = max(−AJUSTE_MAXIMO_ATR·ATR/precio, factor · (nivel−precio)/precio)` con `factor` ∈ {0.0 perseguir, 0.5 escalonar, 1.0 esperar}, y **nunca positivo**. `precio_entrada_objetivo` alimenta `calcular_niveles_riesgo`; `sesgo_macro_clasificacion` alimenta un veto que solo baja. Ver la sección propia más arriba.
- Tamaño de posición: **número, no cadena**. `peso = (riesgo_asumible / distancia_al_stop) × factor_volatilidad × descuentos`, acotado por `PESO_MAXIMO_POSICION` y `PESO_MINIMO_OPERABLE`.
- Régimen de volatilidad: `src/tools/regimen.py` (orquestado por `src/agents/regimen.py`) sobre las series `VIXCLS` y `VXVCLS` que recolecta `src/data/fred/`. Manda la peor de dos dimensiones —nivel y z-score sobre `REGIMEN_VENTANA_ZSCORE` sesiones—, la curva invertida agrava un escalón y nunca atenúa, y el resultado solo llega al dictamen como veto que baja (`PANICO` topa en MANTENER, `TENSION` en COMPRA) y como puerta que prohíbe perseguir.
- Noticias: `src/tools/noticias.py` sobre el dosier que recolecta `src/data/news/`. Por ítem, `p = NEWS_ITEM_PROB_MAX · peso_categoría · credibilidad_de_la_fuente · decaimiento(antigüedad) · corroboración · penalización_de_ruido`; el conjunto se agrega con OR ruidoso sobre los `NEWS_TOP_K_ITEMS` mayores → `impact_probability` y bucket ALTA/MEDIA/BAJA. Categoría y dirección salen de diccionarios cerrados, nunca del LLM. Todas las constantes están en `src/config.py`.

#### Contrato del único campo que sí toca el LLM

La respuesta del proveedor **nunca** se asigna directamente. `AgenteBase._redactar()` hace `texto = texto_de_respuesta_llm(llm.invoke([SystemMessage(...), HumanMessage(...)]))` (`src/config.py`) —una sola vez, para los siete agentes— y solo sobrescribe el campo si `texto` no es `None`:

- Los proveedores modernos devuelven `content` como **lista de bloques** (`[{"type": "text", "text": "..."}]`), no como cadena. Asignarlo tal cual metía una lista de diccionarios de Python en el informe y en `daily_selection.json` — el defecto que motivó el helper.
- Devuelve `None` (no cadena vacía) cuando no hay texto utilizable, precisamente para que el agente **conserve su resumen determinista** en lugar de perder información ya calculada.
- La llamada va siempre dentro de un `try/except`: un fallo del proveedor degrada al texto heurístico, nunca tumba al agente.

`tests/test_llm_texto.py` fija ese contrato **para los nueve**. Su lista `AGENTES` no incluía a `PositioningAnalystAgent` —un hueco de cobertura real, no una exención— y ahora lo incluye, junto con los dos agentes nuevos. `summary`/`synthesis` son `str` pase lo que pase. **Si añades un agente, añádelo a esa lista.** Los dobles de esa suite declaran `invoke(self, prompt)` con un solo posicional, así que la lista de mensajes los satisface sin cambios.

El helper hace falta también fuera de los agentes: el agente investigador volvió a caer en el mismo defecto al leer `.content` directamente, y el generador de informes conserva `_texto()` como último blindaje.

### Analista de Calidad y Valoración (`src/agents/quality.py` + `src/tools/calidad.py`) — capa de DECISIÓN

El agente fija el ORDEN de las llamadas y ensambla el informe; los cálculos son tools. El orden no es intercambiable: las puntuaciones necesitan las siete escuelas ya calculadas, las banderas rojas necesitan las puntuaciones, el estilo necesita las banderas y la convicción necesita el estilo y la cobertura. Reordenar no produce un error, produce un dictamen distinto.

Codifica siete escuelas clásicas como reglas deterministas y produce cuatro puntuaciones de 0 a 100 —**calidad, valoración, crecimiento, solvencia**—, una `conviccion_fundamental` y una etiqueta de estilo.

| Escuela | Qué aporta |
|---|---|
| Piotroski (2000) | F-Score de 9 puntos sobre **variaciones** interanuales. Por eso el agente necesita series, no una foto. |
| Altman (1968) | Z-Score de solvencia; **Z'' para no manufactureras** — el Z clásico penaliza los modelos ligeros en capital vía la rotación de activos. |
| Graham (1949) | Número de Graham y criterios defensivos. Con BPA negativo devuelve `NO_APLICABLE`, no un cero. |
| Buffett | ROIC contra `WACC_REFERENCIA`, margen bruto como proxy de foso, beneficio del propietario, dilución. |
| Lynch (1989) | PEG y taxonomía; declara siempre **sobre qué crecimiento** se calculó (beneficio o ingresos: no son lo mismo). |
| Greenblatt (2005) | EBIT/EV y rentabilidad del capital tangible. |
| Sloan (1996) | Ratio de devengos: el beneficio que no es caja revierte. |

**Estilos** (`style_classification`): `CALIDAD_COMPUESTA`, `CALIDAD_DETERIORADA`, `VALOR`, `GARP`, `CRECIMIENTO`, `CICLICA`, `TRAMPA_DE_VALOR`, `ESPECULATIVA`, `MIXTA`, `DATOS_INSUFICIENTES`. No son decorativos: eligen los múltiplos de ATR y el horizonte (`ATR_AJUSTE_POR_ESTILO`) y habilitan vetos — `ESPECULATIVA` y `TRAMPA_DE_VALOR` no pueden superar MANTENER por atractivos que sean sus múltiplos.

Dos detalles del clasificador que no son obvios y conviene no deshacer:

- **La trampa de valor se detecta con los múltiplos de titular** (P/E, P/VC, EV/EBITDA), no con la puntuación compuesta de valoración. El compuesto incluye el rendimiento del flujo de caja libre, que en una trampa de valor es malo y arrastra la media a zona neutra — se acababa promediando la señal de alarma con la señal de reclamo, y el caso quedaba sin etiquetar.
- **Por debajo de `COBERTURA_MINIMA_ESTILO` no se emite etiqueta.** Una clasificación apoyada en dos de doce métricas es peor que ninguna.
- **El veto por insolvencia de Altman exige corroboración de caja** (flujo libre negativo, cobertura de intereses < 1.5x o margen operativo negativo). Dos de los cuatro términos del Z'' —beneficios retenidos y fondos propios sobre activos— se hunden en compañías que han recomprado acciones por encima de su beneficio acumulado, lo que describe a buena parte del software rentable. Sin la corroboración, el veto sería un falso positivo sistemático de todo un sector; el caso que lo motivó fue DOCN, con Z''=0.04 y flujo de caja holgadamente positivo.
- **`CALIDAD_COMPUESTA` admite como mucho una bandera roja.** La etiqueta describe el negocio y puede convivir con una valoración exigente, pero no con dos defectos estructurales simultáneos; ese caso es `CALIDAD_DETERIORADA`.

Las cuatro puntuaciones se promedian **solo sobre los componentes disponibles**; imputar ceros convertiría una ausencia en un suspenso, que es el defecto que este proyecto arrastraba.

### Construcción de cartera (`src/portfolio/construccion.py`)

Etapa posterior al bucle por ticker, orquestada desde `cli.py`. Antes no existía: nadie sumaba la exposición ni miraba si cuatro posiciones eran cuatro apuestas o una repetida.

Restricciones **en este orden**, y el orden importa porque cambia el resultado:

1. Peso del Fund Manager (ya escalado por riesgo y volatilidad).
2. **Reflexión**: recorte por expectativa histórica y **reasignación** del presupuesto liberado a los candidatos sin evidencia en contra (`_penalizar_reflexion`). Va la segunda, no la última, porque modifica el peso BASE y todos los topes posteriores tienen que morder sobre el resultado; colocarla al final dejaría que un recorte reabriera hueco por encima del límite sectorial.
3. Penalización por correlación media con el resto de candidatos.
4. Tope por sector (`LIMITE_POR_SECTOR`).
5. Tope de número de posiciones, conservando las de mayor convicción.
6. Presupuesto de riesgo agregado (`RIESGO_TOTAL_CARTERA_PCT`): suma de `peso × distancia_al_stop`.
7. Tope de exposición bruta.

Cada paso deja constancia de lo que recortó en `restricciones_activadas` y en los `ajustes` de cada posición. Sin matriz de correlaciones **no se corrige nada** y se declara la limitación: es preferible no corregir a corregir con una matriz inventada.

`posiciones_existentes` permite usar esta misma capa desde el motor histórico, donde en cada rebalanceo ya hay posiciones abiertas. Entran con peso **fijo** —no se reescalan, porque reajustar la cartera entera en cada rebalanceo generaría rotación cuyo coste se comería el ajuste— pero **consumen presupuesto** sectorial, de riesgo y de exposición. Sin eso, cada rebalanceo respetaría el tope del 30% por sector y la cartera acabaría igualmente con el 90% en un sector tras tres rebalanceos.

### Analista de Estructura de Precio (`src/agents/estructura.py` + `src/tools/niveles.py`) — capa de DECISIÓN

Responde dónde está el suelo más cercano **sin depender de la cadena de opciones**.

**El defecto que corrige.** Los tres candidatos de nivel del ajuste de entrada —`SOPORTE_OI`, `GAMMA_FLIP`, `MAX_PAIN`— salían los tres de la cadena, así que su ausencia no degradaba el bloque: lo **anulaba**. Y como el histórico de cadenas por ticker es de pago, en el backtest la cadena está **siempre** ausente y `ajuste_entrada_pct` era `None` en el **100%** de las 5 621 señales del estudio. El informe medía un sistema sin ajuste de entrada mientras producción sí lo aplicaba.

«¿A qué precio es probable que vuelva el valor?» no es una pregunta que solo sepa responder una cadena de opciones. Es la pregunta que `add_liquidity` y `_causal_levels` del repositorio 07 (*Bear Trap*) responden con OHLCV, que el anfitrión ya tiene point-in-time, ya cacheado y ya protegido por `test_no_lookahead_future_prices_do_not_change_past_signal`.

**Dónde toca la decisión.** Dos vías, y las dos solo cierran:

1. `soporte` entra en `ajustar_precio_entrada` como **cuarto candidato**, con la misma regla de «el más alto por debajo del precio». El ajuste sigue acotado a `AJUSTE_MAXIMO_ATR` y sigue pasando por `min(0.0, ajuste)`.
2. `soporte_lejano` se une por `or` a `sobreextendido`, en la misma familia que el RSI extremo y el techo del canal de open interest: prohíbe perseguir el precio, nunca lo habilita.

**Reglas que no conviene deshacer:**

- **El mínimo EXCLUYE la barra en curso.** Es el `shift(1)` explícito de `_causal_levels`. Un mínimo que incluya la sesión de hoy no es un soporte previo: es el mínimo de hoy, y esperar a él es esperar un precio que ya se ha tocado.
- **El número redondo NO es candidato**, aunque el repo 07 lo use. Medido sobre las 132 fechas de rebalanceo del estudio, con un paso fijo el redondo ganaba la elección el **65%** de las veces —por construcción es siempre el más cercano por debajo— y dejaba la profundidad mediana del nivel en **0.95% (0.46 ATR)**, que es ruido frente a un ATR. Excluyéndolo, la mediana sube a **2.52% (1.24 ATR)** y el nivel lo aportan los mínimos previos (45%), la SMA50 (25%) y la banda inferior de Bollinger (19%). **Reintroducirlo degenera la elección.**
- **La SMA50, la SMA200 y la banda inferior NO se recalculan**: ya las publica `_add_technical_indicators` sobre la misma ventana, en producción y en el replay. Dos implementaciones del mismo indicador es el bug de clase que este proyecto prohíbe.
- **Los mínimos previos los calcula la INGESTA**, no el agente. `DataFetcher.fetch_all` y `HistoricalReplayer.build_state` llaman ambos a `minimos_previos()` sobre su propia ventana ya cortada. El agente es puro y no vuelve al DataFrame, igual que el de noticias no vuelve a la red.
- **La bandera describe, el extremo actúa.** La asociación medida entre distancia al soporte y rentabilidad futura **no es monótona**: a 21 sesiones, el tramo (0.5, 1.0] ATR rindió +2.42% frente a +1.41% del tramo pegado al soporte y +1.33% del tramo por encima de 2 ATR. Es una joroba, no una recta, así que la etiqueta contextualiza y solo el extremo superior enciende la bandera.

**Lo que este agente NO afirma.** Que esperar al soporte mejore el resultado. Ver la sección siguiente.

### La entrada limitada, MEDIDA Y REFUTADA — desactivada por defecto

> **SEGUNDO RESULTADO NEGATIVO MEDIDO Y PUBLICABLE**, hermano del de `src/memoria/`. `--con-entrada-limitada` en `backtest_cli.py` la activa; sin la bandera, el motor rellena a la apertura de t+1 como siempre.

El sistema publica un `precio_entrada_objetivo` por debajo del mercado y mide desde ahí el stop, el objetivo y el tamaño. La pregunta que nadie podía responder era si **esperar a ese precio** mejora el resultado. Ahora se puede, porque hay nivel (arriba) y porque `engine.py` sabe ejecutar una orden limitada.

Medido sobre las **936 señales de compra** del régimen `pit`, con los stops y objetivos del propio Fund Manager, la regla de salida pesimista de `process_intraday_exits` y 10 pb de costes:

| Regla de entrada | Opera | Acierto | Expectativa | PF | **Valor esperado / señal** |
|---|---|---|---|---|---|
| **A. Mercado (lo de hoy)** | 100.0% | 45.3% | +1.34% | 1.43 | **+1.34%** |
| B. Limitada al soporte (vida 10) | 46.3% | 45.5% | **+1.70%** | **1.53** | +0.78% |
| C. Recuperación confirmada (repo 07) | 39.1% | 45.9% | +1.51% | 1.49 | +0.59% |

**La orden limitada mejora la operación y empeora el sistema.** Lo que no rellena es precisamente lo que sube: esas 503 señales habrían rendido **+3.56% con un 59.6% de acierto**, frente al 45.3% de la línea base. Con la orden viva 21 sesiones el desequilibrio se agrava: lo descartado acierta el **71.1%**.

**Y traslada a nivel de cartera.** Sobre el estudio completo (2015-2025, régimen `pit`), las tres variantes de entrada limitada quedan por debajo de la entrada a mercado en los dos criterios de aceptación:

| Ejecución | Ops | Expiradas | Acierto | Expectativa | Percentil vs. aleatorio |
|---|---:|---:|---:|---:|---:|
| **A mercado (se entrega)** | 535 | — | **47.3%** | **+1.283%** | **16.6** |
| Limitada, vida 5 | 503 | 42 | 45.5% | +1.252% | 13.9 |
| Limitada, vida 10 | 511 | 33 | 45.8% | +1.271% | 13.9 |
| Limitada, vida 21 | 518 | 13 | 45.8% | +1.229% | 13.7 |
| Limitada 10, ajuste 0.5·ATR | 518 | 22 | 45.4% | +1.221% | 11.5 |

La última fila es la más instructiva y contradice lo que se predijo antes de medirla: un ajuste **más somero** rellena más órdenes (22 expiradas frente a 33) y sale **peor**. Más rellenos limitados es más selección adversa, no menos.

Y lo más llamativo, que es lo que convierte esto en un hallazgo y no en una obviedad: **la rentabilidad CONDICIONADA a operar es prácticamente idéntica en las tres reglas** (+1.71%, +1.76%, +1.71% sobre las 6 421 observaciones del universo completo). Entrar entre un 1% y un 2.5% más barato **no produce un resultado mejor**: la selección adversa cancela exactamente la mejora de precio, porque las trayectorias que vuelven a tu nivel son las débiles.

**No inviertas el signo «a ver si así funciona»**, y no compres histórico de cadenas esperando que un nivel de open interest cambie la conclusión: tendría que **invertir** el signo de la selección adversa, no solo mejorar la magnitud.

### Analista de Régimen de Volatilidad (`src/agents/regimen.py` + `src/tools/regimen.py` + `src/data/fred/`) — capa de DECISIÓN

El sistema no tenía **ninguna** medida de estrés sistémico. El dosier COT mide posicionamiento **por contrato** —cuánto están largos los especuladores del E-mini o del crudo—, que es una pregunta distinta de «en qué estado está el mercado». Un valor puede tener el posicionamiento a favor y estar en mitad de una capitulación.

Es la traducción del *anti-falling-knife gate* de `src/macro/regime.py` del repositorio 07: en un régimen de pánico, lo que parece una oportunidad suele ser una capitulación en curso. Allí es una puerta binaria (`vix_level <= 35 AND vix_z <= 2`); aquí son cuatro etiquetas —`CALMA`, `NORMAL`, `TENSION`, `PANICO`— y **dos mecanismos que solo cierran**, porque este sistema necesita distinguir «no perseguir el precio» de «no comprar».

**Es la única capa del sistema de la que el estudio mide el 100%.** `VIXCLS` y `VXVCLS` llegan por **ALFRED**, la interfaz de archivo de FRED, cuyos parámetros `realtime_start`/`realtime_end` devuelven la serie **tal y como se conocía** en una fecha, y cuyo `output_type=4` adjunta a cada observación su fecha de primera publicación. Verificado contra la API el 2026-09-06:

```
WALCL, observación del miércoles 2020-03-25
  consultado el 2020-03-25 -> 0 observaciones visibles
  consultado el 2020-03-26 -> 1 observación visible
VIXCLS, misma observación
  consultado el 2020-03-25 -> visible, 63.95   (cierre del día, sin retardo)
```

Es el par `filed`/`end` de los hechos XBRL y el par `fecha_informe`/`fecha_publicacion` del COT, **impuesto por el proveedor**. El retardo no hay que modelarlo: hay que no estorbarlo.

**Dónde toca la decisión.** Dos vías, y las dos solo bajan:

1. `regimen_clasificacion` entra en `aplicar_vetos`: **PANICO topa en MANTENER**, **TENSION topa en COMPRA**.
2. `puerta_regimen` cerrada se une a `sobreextendido` en el posicionamiento y prohíbe perseguir el precio.

**Reglas que no conviene deshacer:**

- **Manda la PEOR de las dos dimensiones, no su promedio.** Un VIX de 20 con un z-score de +3 describe un salto brusco desde la calma, y promediarlo con el nivel lo disolvería. Es el mismo criterio que gobierna la memoria de reflexión.
- **La curva invertida AGRAVA, nunca atenúa.** `VIX > VIX3M` significa que el estrés es inmediato y no de fondo, y solo puede empeorar la clasificación un escalón. Una curva en contango durante un pánico no convierte el pánico en calma. `test_la_curva_invertida_solo_agrava_nunca_atenua` recorre el producto cartesiano.
- **Sin dosier, la puerta queda ABIERTA.** Cerrarla por precaución ante la ausencia de dato convertiría una laguna de cobertura en una restricción de cartera, que es la **forma inversa** del defecto «ausencia ≠ cero». Sin `regimen_data` el sistema se comporta exactamente como antes de que este agente existiera, y `test_sin_regimen_el_rating_no_cambia` lo fija.
- **El z-score no se emite por debajo de `REGIMEN_MINIMO_OBSERVACIONES`.** Un z de 0.0 afirmaría que la volatilidad está exactamente en su media, que es una afirmación fuerte sobre una serie que no se ha podido reconstruir. Misma regla que los percentiles de opciones.
- **`VXVCLS` no existe en ALFRED antes de 2014.** Observa desde 2007, pero su *archivo de vintages* empieza en 2014: pedir 2013 devuelve «the series does not exist in ALFRED». Es una **frontera de cobertura declarada**, no un fallo, y `test_la_serie_a_tres_meses_declara_su_frontera_de_archivo` la fija para que nadie asuma lo contrario. Cuando falta, `ratio_curva` es `None` y el agravamiento no se aplica.
- **El dictamen es POR TICKER aunque el dosier sea de lote.** `volatilidad_relativa = volatilidad_anual / (VIX/100)` distingue, dentro del mismo régimen, un valor que se mueve el doble que el mercado de otro que se mueve la mitad. Sin eso el agente publicaría el mismo párrafo cincuenta veces.
- **La caché va indexada por AÑO DE LA OBSERVACIÓN**, nunca por día de ejecución — el patrón de `data/cache/cot/` y por el mismo motivo. Y **un vintage cacheado NUNCA se sobrescribe**: una redescarga con contenido distinto levanta `VintageDivergente` en lugar de reemplazarlo en silencio, porque que el proveedor reescriba historia ya consumida es un evento que investigar, no algo que absorber.

**Recolección: ninguna excepción nueva al «un solo módulo toca la red».** `src/data/fred/` es la capa de ingesta y su tool de red, `obtener_contexto_regimen`, vive en `src/tools/extraccion.py` como todas las demás. Es el patrón de `obtener_noticias` → `src/data/news/`.

**Es de LOTE**, así que está cableado en los tres puntos de entrada: `cli.py` (`cargar_regimen`), `src/web/app.py` (una vez por petición) y `backtest_cli.py` (`FREDStore`). El dashboard cablea **este y solo este** de los cuatro argumentos de lote, y el motivo está en la tabla de «Los tres puntos de entrada NO son equivalentes».

### Analista de Posicionamiento y Precio de Entrada (`src/agents/posicionamiento.py` + `src/tools/futuros.py` + `src/tools/opciones.py`) — capa de DECISIÓN

Responde la pregunta que el sistema no se hacía: **a qué precio entrar**. Antes el Fund Manager tomaba el último cierre y medía desde ahí el stop, el objetivo y el tamaño; un stop medido desde un precio que no se ha pagado describe una operación que nadie hizo.

Cruza tres señales y de ahí sale un precio de entrada objetivo:

| Señal | Origen | Qué aporta |
|---|---|---|
| Sesgo macro | Informes COT de la CFTC, por contrato de índice y sectorial | **Dirección.** Nunca un nivel. |
| Sesgo de opciones | Cadena del propio ticker | **Calidad del precio y NIVEL**: soporte de OI, max pain, punto de inflexión de la gamma |
| Momentum | `momentum_score` del Analista Técnico | La señal propia del valor |

Si las tres confirman y nada está sobreextendido, se entra a mercado (`PERSEGUIR`, ajuste `0.0`). Si divergen, se exige un retroceso hasta el nivel (`ESPERAR_RETROCESO`); en acuerdo parcial, medio camino (`ESCALONAR`).

**El sesgo de opciones mide CALIDAD DEL PRECIO, no dirección.** De la dirección ya se encarga el Analista Técnico, y confundirlas fue el defecto de la primera versión. Sus cuatro componentes se leen todos en clave contraria y se promedian solo sobre los disponibles:

| Componente | Peso | Disponible desde |
|---|---|---|
| Posición del precio en el canal de open interest (invertida) | 0.35 | **el primer día** |
| Skew — percentil histórico si lo hay, si no dividido por la IV at-the-money | 0.25 | **el primer día** (normalizado) |
| Put/call ratio en percentil histórico | 0.20 | tras ~60 sesiones |
| Punto de inflexión de la gamma, **asimétrico** | 0.20 | el primer día |

**El defecto que esto corrige, y que no debe reintroducirse.** En la primera versión los dos componentes con más peso —put/call y skew— exigían 60 días de caché acumulada, así que durante los primeros tres meses de vida del sistema **no votaban**. El único componente vivo era `tanh((precio − gamma_flip) / (0.05·precio))`, que crece cuanto más ha subido el valor: el sesgo de opciones era un **proxy de momentum que duplicaba la pata técnica**, la confluencia llegaba a 1.0 sin esfuerzo y el ajuste de entrada salía 0.0 casi siempre. Verificado sobre datos reales el 2026-08-30: AAPL cotizaba en el **percentil 98 de su canal de open interest** —pegado a la resistencia— con sesgo de opciones +0.89 y recibió `PERSEGUIR` con entrada a mercado, que es el peor precio posible para una compra en largo. NEM, el caso de sobrecompra extrema que el propio proyecto documenta, salía con +0.99 saturado.

Las dos reglas que lo evitan:

1. **Todo componente direccional debe estar disponible SIN histórico siempre que se pueda.** La posición en el canal de open interest y el skew dividido por la volatilidad at-the-money lo están; los percentiles son la refinación que llega después, no el cimiento. Un bloque cuyos componentes principales tardan tres meses en activarse es un bloque que no funciona cuando se estrena.
2. **El componente de gamma es asimétrico** (`GEX_ASIMETRIA_POSITIVA`). Por debajo del punto de inflexión la advertencia es real —las coberturas de los creadores de mercado aceleran el movimiento en contra— y usa el rango completo; por encima solo dice que el colchón de amortiguación queda lejos, así que el lado positivo se escala a una fracción. Sin esa asimetría el término vuelve a ser un proxy de momentum.

Tras la corrección, sobre las mismas cadenas: AAPL pasa de +0.89 a −0.14 (`ESCALONAR −1.95%`), NEM de +0.99 a −0.45, y GOOGL —que cotizaba en el 31% de su canal, cerca del soporte— sube a +0.17 y conserva `PERSEGUIR`. El bloque discrimina en vez de refrendar la tendencia.

**Reglas que no conviene deshacer:**

- **El z-score COT usa la categoría NO COMERCIAL y se normaliza por interés abierto.** Los comerciales cubren producción o inventario: su posición la dicta el negocio, no una opinión. Y sin normalizar por interés abierto, una serie de tres años mide en parte el crecimiento del mercado de futuros — el mismo error de categoría que leer un histograma MACD sin normalizar por ATR.
- **Un z-score extremo NO invierte el signo.** Señala posicionamiento hacinado y lo único que hace es prohibir perseguir el precio. Invertirlo produciría un clasificador no monótono, que es la patología nº 2 documentada del momentum por puntos enteros.
- **`SECTOR_A_FUTURO` es un diccionario cerrado y un sector que no está en él no recibe pata sectorial.** Forzar un contrato para «Technology» produce un número donde no hay relación. El contrato de índice sí aplica a todos, porque mide apetito de riesgo agregado. Los patrones de mercado están **verificados contra el fichero real de la CFTC** (`deacot2025.zip`, 2026-08-30): «NATURAL GAS» y «10 YEAR NOTE» no casan con nada — los mercados se llaman `NAT GAS NYME` y `UST 10Y NOTE`.
- **Las Griegas salen de la forma cerrada de Black-Scholes, no de una aproximación.** `test_gamma_es_la_derivada_de_delta` lo verifica contra la derivada numérica de la delta, que es una comprobación independiente de la fórmula.
- **El signo de la exposición gamma es una CONVENCIÓN, no una medición.** Se asume creadores de mercado largos gamma en calls y cortos en puts; la cadena publica open interest, no quién está en cada lado. Va declarado en el informe y en `build_limitations()`. Es el eslabón más débil del bloque.
- **`ajuste_entrada_pct = 0.0` y `None` NO son lo mismo.** `0.0` es «entrar a mercado por confluencia»; `None` es «no calculable». Colapsarlos sería reintroducir el defecto que `src/data/magnitudes.py` corrige, agravado porque aquí el cero es plausible y por tanto invisible.
- **El ajuste SOLO puede bajar el precio de entrada**, nunca subirlo, y está acotado a `AJUSTE_MAXIMO_ATR` veces el ATR. El tope está en unidades de volatilidad y no en un porcentaje fijo porque uno más profundo dejaría la entrada objetivo por debajo del propio stop. `test_el_ajuste_de_entrada_solo_baja_el_precio` recorre el producto cartesiano, igual que `test_los_vetos_solo_bajan_el_rating`.
- **El nivel se elige como el candidato MÁS ALTO por debajo del precio**: es el retroceso más cercano y por tanto el más probable de que se rellene. Tomar el más bajo sería esperar un desplome. Exigir que esté por debajo del precio es lo que hace estructuralmente imposible subir la entrada.
- **Los percentiles de put/call y skew se calculan sobre la caché ACUMULATIVA** de `data/cache/opciones/`. Los ficheros de días anteriores **no se borran**: son el histórico. Una instalación nueva no puede emitirlos hasta acumular `OPCIONES_MINIMO_DIAS_HISTORICO` observaciones, y hasta entonces se declara `DATOS_INSUFICIENTES`, nunca el percentil 50. Que su ausencia ya no deje al bloque sin voto es justo lo que resuelven el canal de open interest y el skew normalizado.
- **Comprar en el techo del canal de open interest cuenta como SOBREEXTENSIÓN** (`OPCIONES_CANAL_SOBREEXTENDIDO`), en la misma familia que el RSI extremo: no cambia la dirección, prohíbe perseguir el precio. Es la barrera directa contra el caso AAPL.

**Dónde toca la decisión.** Dos vías, y solo dos:

1. `precio_entrada_objetivo` sustituye a `current_price` en la llamada a `calcular_niveles_riesgo` y a `calcular_perfil_riesgo` del Fund Manager (`src/agents/fund_manager.py`). La comprobación es `is None` y **no** `or`: un `precio_entrada_objetivo` de `0.0` es un dato corrupto, no una ausencia, y `or` lo enmascararía.
2. `sesgo_macro_clasificacion` entra en `aplicar_vetos` como un veto que **solo baja**: `VIENTO_EN_CONTRA_FUERTE` topa el dictamen en COMPRA. El parámetro va al final y con defecto `None` para no romper a los llamantes existentes.

**Recolección: ninguna excepción nueva al «un solo módulo toca la red».** `src/data/futuros/` y `src/data/opciones.py` son capas de ingesta, y sus tools de red —`obtener_contexto_macro` y `obtener_cadena_opciones`— viven en `src/tools/extraccion.py` como todas las demás. Es exactamente el patrón de `obtener_noticias`, que también delega en `src/data/news/`.

**El dosier macro NO es por ticker** y por eso se resuelve **una vez por ejecución** en `cli.py`, junto a `cargar_benchmark`, y viaja en el estado inicial como `benchmark_data`. El sesgo del futuro del petróleo es idéntico para todas las energéticas del lote y el COT se publica semanalmente: descargarlo dentro del grafo sería pedir el mismo fichero de la CFTC una vez por valor. La cadena de opciones sí es por ticker y la escribe el nodo de ingesta.

**Cachés, con claves distintas a propósito:**

| Dato | Clave | Por qué |
|---|---|---|
| Futuro continuo | `data/cache/futuros/{CONTRATO}_{YYYY-MM-DD}.json` | Dato «de hoy», como las noticias |
| Informe COT | `data/cache/cot/{MERCADO}_{AÑO}.json` | Clave por **año del informe**, no por día de ejecución: cada informe es inmutable, así la caché queda ordenada point-in-time y **el backtest la reutiliza sin reimplementar la selección histórica** |
| Cadena de opciones | `data/cache/opciones/{TICKER}_{YYYY-MM-DD}.json` | Diaria y **acumulativa**: los días anteriores son el histórico de los percentiles |

### Meta-etiquetado (`src/meta/` + `src/tools/meta.py`) — REFUTADO, desactivado por defecto

> **TERCER RESULTADO NEGATIVO MEDIDO Y PUBLICABLE**, hermano del de `src/memoria/` y del de la entrada limitada. `--con-meta` en `backtest_cli.py` lo activa; sin la bandera, `factor_meta` es 1.0 y la capa no decide nada. El motivo no es una duda de diseño: es una medición en ocho ventanas walk-forward independientes.

El modelo primario —las reglas deterministas de este sistema— da el **lado**. El meta-etiquetado de López de Prado (AFML cap. 3) responde a la pregunta siguiente: *dado que el sistema dice comprar, ¿acierta?*, y su salida es un **tamaño**, nunca un rating.

**Por qué encajaba mejor que ningún otro candidato de los cuatro repositorios:** no toca `rating`; el mecanismo de aplicación ya existía (`factor_reflexion` es su gemelo exacto); y el patrón de capa con estado point-in-time ya existía (`src/memoria/`).

**Qué salió.** Reentrenamiento anual, CV purgada de 5 particiones con 21 días de embargo, pesos por unicidad y atribución de retorno:

| Corte | AUC en CV purgada | ¿Artefacto? |
|---|---:|:--|
| 2018 · 2019 · 2020 · 2021 | 0.420 · 0.403 · 0.452 · 0.447 | **no** |
| 2022 · 2023 · 2024 · 2025 | 0.472 · 0.468 · 0.438 · 0.470 | **no** |

**En las ocho ventanas con muestra suficiente la AUC quedó por DEBAJO de 0.5.** No es que no supere al azar: queda sistemáticamente por debajo. La lectura no es «el modelo es malo» sino algo más fuerte:

> Las 23 variables que el sistema conoce al emitir una señal **no contienen información utilizable sobre si esa compra concreta acabará en beneficio**.

Encaja con lo que el informe lleva publicando dos revalidaciones: **el rating no ordena el rendimiento futuro**. Si la puntuación compuesta no lo ordena, es coherente que un modelo entrenado sobre sus mismos insumos tampoco. Un AUC persistentemente bajo 0.5 —y no oscilando alrededor— es además la firma de un sobreajuste leve cuyo signo se invierte fuera de muestra: exactamente lo que la CV purgada existe para revelar y lo que un k-fold corriente habría ocultado.

**La barrera funcionó.** `META_VENTAJA_MINIMA_AUC` impidió entregar artefacto y el factor se quedó en 1.0. Ejecutar con y sin `--con-meta` produce cifras **idénticas dígito a dígito**.

**Reglas que no conviene deshacer:**

- **El corte del conjunto de entrenamiento es la fecha de DESENLACE, no la de emisión.** `BancoDeEtiquetas.conjunto()` filtra por `fecha_desenlace < corte`. Es el par `filed`/`end` del XBRL aplicado por cuarta vez, y relajarlo convierte el estudio en un examen de memoria. Con un horizonte medio de 33 sesiones, el modelo de enero de 2019 no puede usar señales posteriores a noviembre de 2018.
- **`cargar_para()` LEVANTA EXCEPCIÓN si el artefacto vio el futuro.** No degrada, no avisa, no devuelve `None`. Es la única defensa contra un peligro que **ningún otro test de este repositorio detectaría**: `test_no_lookahead_*` mira precios, `test_fundamentals_respect_filed_not_end` mira `filed`, ninguno mira de qué años salieron los coeficientes. La comparación es `>=` y no `>`: un artefacto entrenado con etiquetas resueltas el mismo día ya conoce el desenlace de operaciones que seguían abiertas.
- **Las etiquetas usan las barreras DEL PROPIO SISTEMA** —`stop_loss_atr`, `take_profit_atr`, `horizonte_dias`— y la misma regla pesimista que `process_intraday_exits`: si stop y objetivo se tocan en la misma sesión, gana el stop. Si divergiera, el modelo se entrenaría con un desenlace distinto del que el backtest simula.
- **El factor SOLO recorta.** Por encima de la tasa base es exactamente 1.0. Ampliar el peso de lo que el modelo cree bueno convertiría una capa de filtrado en una apuesta apalancada sobre el propio modelo, con 944 muestras detrás. Van cinco mecanismos con esta misma regla.
- **La referencia es la TASA BASE del entrenamiento, no 0.5.** Si el sistema acierta el 47% de sus compras, exigirle a una señal un 50% la penalizaría por una constante arbitraria.
- **Una regresión logística con L2 fuerte, no un GBM.** No es preferencia estética: 944 señales de compra, ~200 en los primeros modelos walk-forward, y menos aún tras ponderar por unicidad. Con eso un GBM memoriza. Es un caso donde la restricción de datos determina la arquitectura.
- **El artefacto es JSON legible, no `pickle`.** Un pickle es código ejecutable, no se revisa en un diff y no sobrevive a un cambio de versión de scikit-learn.

**Una cicatriz que dejó la calibración.** Con `FFD_UMBRAL=1e-4` la diferenciación fraccional necesita **282 rezagos** y la ventana del replay tiene ~250 sesiones, así que la variable era `None` en todas las filas y el modelo se negaba a entrenar con «0 etiquetas utilizables». **El síntoma fue el correcto** —descartar la fila en vez de imputar la media— pero el umbral estaba mal. `test_los_pesos_ffd_caben_en_la_ventana_del_replay` lo fija.

### Maquinaria de validación (`src/tools/validacion.py`) — VALIDATE-ONLY

CV purgada con embargo, unicidad media y pesos de muestra, levantados del repositorio 06. **No producen ninguna variable de decisión.**

Hasta esta revalidación eran código muerto: sin ningún modelo entrenado no tenían un solo llamante, y este proyecto no mantiene código sin llamante. Entran con `src/meta/`, que es cuando pasan de adorno a requisito.

**Por qué el k-fold corriente no sirve, dicho sin rodeos.** Una señal del 1 de junio cuyas barreras se resuelven el 15 de julio comparte información con otra del 20 de junio: los mismos precios deciden las dos. Si la primera cae en entrenamiento y la segunda en prueba, el modelo ya ha visto parte de la respuesta. **Un k-fold sobre etiquetas solapadas no es validación: es una fuga con un número al lado**, y da exactamente la clase de resultado excelente que no sobrevive fuera de muestra.

Dos detalles que no conviene deshacer: **el embargo va DESPUÉS del bloque de prueba** (el solapamiento va hacia adelante en el tiempo), y **la partición agrupa por fecha de señal**, porque todas las señales de un rebalanceo comparten fecha y partirlas metería en el mismo fold dos observaciones que el sistema emitió a la vez con la misma información.

### Freno por drawdown (`src/tools/riesgo.py`) — implementado e INERTE en producción

`drawdown_guard` del repositorio 03, traducido de excepción a **factor que solo recorta** la exposición: un `raise` detendría el análisis, y en este sistema un fallo de riesgo no puede impedir que se emita un dictamen ya calculado.

**El bloqueante es de fondo, no de implementación: producción no tiene curva de capital.** `cli.py` emite recomendaciones; no gestiona una cartera, no conoce su patrimonio y no sabe si está en drawdown. El backtest sí.

Cablearlo solo en el backtest sería **inaceptable**: una variable de decisión medida en el estudio y ausente en producción es la imagen especular exacta de la vieja limitación del ajuste de entrada. Por eso el parámetro de `PortfolioConstructor.construir()` es **opcional y neutro por defecto** — sin `drawdown` el comportamiento es idéntico al de antes, en los dos entornos— y la capa queda declarada inerte en `build_limitations()` hasta que exista una cartera real que seguir.

### Memoria de reflexión (`src/memoria/reflexion.py` + `src/tools/reflexion.py`) — REFUTADA, desactivada por defecto

> **RESULTADO NEGATIVO, MEDIDO Y PUBLICABLE.** Esta capa está implementada, probada y documentada, y **no decide nada**: `--con-reflexion` en `backtest_cli.py` y en `cli.py` la activan; sin la bandera, `factor_reflexion` es 1.0 y el veto nunca se dispara. El motivo no es una duda de diseño, es una medición.
>
> Contraste sobre el régimen `pit`, 2015-2025, 50 valores, contra su contrafactual exacto (mismas señales, mismos costes, misma capa de cartera):
>
> | | Sin reflexión | Con reflexión | |
> |---|---|---|---|
> | **Percentil vs. selección aleatoria** | **7.4** | **3.1** | ↓ |
> | **Expectativa por operación** | **+1.23%** | **+0.95%** | ↓ |
> | CAGR | 3.95% | 2.90% | ↓ |
> | Sharpe | 0.68 | 0.54 | ↓ |
> | Máx. drawdown | −13.8% | **−18.0%** | ↓ |
> | Alfa anual (t) | 0.91% (0.67) | 0.34% (0.25) | ↓ |
> | Operaciones · acierto · PF | 563 · 44.6% · 1.38 | 530 · 43.2% · 1.28 | ↓ |
>
> La capa **sí actuó**: recortó 1.031 de 5.621 señales (18.3%) con factor medio ×0.93. Empeoró las dos métricas de selección que se habían fijado como criterio de aceptación, y además todas las demás.
>
> **La lectura más probable**, y la que explica el drawdown: el rendimiento relativo de un perfil (estilo, momentum) a un mes **revierte**, no persiste. Evitar los perfiles que acaban de rendir peor que sus pares es, en este universo y a este horizonte, comprar caro y vender barato — y la reasignación concentra la cartera en menos nombres, que es lo que sube el drawdown de −13.8% a −18.0%.
>
> **No inviertas el signo «a ver si así funciona».** Buscar en el espacio de variantes hasta que una dé positivo sobre el mismo histórico es exactamente el defecto metodológico que se documentó en FinVision y FinAgent. Cualquier reevaluación de esta capa exige validación walk-forward declarada de antemano.

Qué hizo el precio **después** de cada señal que este sistema emitió, y qué se deduce de ello para las señales de hoy.

Es la traducción determinista de la *low-level reflection* de **FinAgent** (Zhang et al., 2024, arXiv:2402.18485), el único componente de los dos papers de trading multiagente analizados que (a) tiene evidencia de ablación en ambos, (b) es implementable sin LLM y (c) es medible en este backtest. En FinAgent el vínculo «qué observé → qué pasó después» lo redacta un modelo mirando un gráfico de velas; aquí es una media condicionada sobre observaciones ya desenlazadas. La forma es la misma; la sustancia es una función pura, así que **la invariante del proyecto no se toca**.

**Por qué el bajo nivel y no el alto.** La reflexión de alto nivel mira las decisiones ejecutadas; la de bajo nivel, todo lo observado. Aquí la diferencia es de un orden de magnitud: cada rebalanceo evalúa ~50 valores y compra 4 o 5, así que medir sobre las 563 operaciones cerradas daría celdas de veinte observaciones y medir sobre las ~6.600 señales emitidas da celdas con las que se puede decir algo. Es el mismo motivo por el que la ablación de FinAgent premia a L sobre H.

**La medida es TRANSVERSAL, y ese es el punto entero.** El desenlace se calcula en dos pasos: retorno del valor menos retorno del índice, y después **menos la media de las demás señales del mismo rebalanceo**. La primera versión se quedó en el paso uno y, sobre el histórico real, la capa recortó **62 de 5.621 señales con factor medio ×0.99** — o sea, nada: este universo de grandes capitalizaciones bate al SPY, el exceso medio de todas las señales era **+0.46%** a 21 sesiones y casi ninguna celda llegaba a caer por debajo de cero. Contra el índice la memoria mide *universo menos índice*, que es **exposición**; contra la cohorte mide *este perfil menos los demás perfiles que el sistema tenía delante ese día*, que es **selección** — la única pregunta que esta capa puede responder y justo la que juzga el percentil frente a selección aleatoria. **No lo revientas volviendo a medir contra el SPY.**

Restar la media de la cohorte no introduce look-ahead: una cohorte madura entera y a la vez, porque el desplazamiento del calendario es constante. Y el valor centrado se guarda en `retorno_relativo`, **aparte** de `retorno_exceso`, para que consolidar dos veces no reste la media dos veces (`test_consolidar_dos_veces_no_resta_la_media_dos_veces`).

**Dos vías hacia la decisión, y solo dos** (ambas inertes mientras la capa esté desactivada)**:**

1. `factor_reflexion` ∈ `[REFLEXION_FACTOR_MINIMO, 1.0]` multiplica el peso en `PortfolioConstructor`. **El Fund Manager lo publica SIN aplicar** —ver `_penalizar_reflexion`—: quien lo aplica es la capa de cartera, porque es la única que ve el rebalanceo entero y puede **reasignar** a los demás candidatos el presupuesto que el recorte libera. Aplicarlo valor a valor solo sabría restar, y el sistema ya opera con una exposición bruta media del 30%.
2. `reflexion_desfavorable` entra en `aplicar_vetos` como un veto que **solo baja**: topa el dictamen en MANTENER.

**Reglas que no conviene deshacer:**

- **El punto de corte es la fecha de DESENLACE, no la de emisión.** Una señal del 1 de junio con horizonte de 21 sesiones no se sabe cómo terminó hasta julio. Es el mismo par `filed`/`end` del XBRL y el mismo `fecha_publicacion` del COT. `test_la_memoria_respeta_la_fecha_de_desenlace` es el análogo de `test_fundamentals_respect_filed_not_end`: **si se relaja, el backtest deja de medir nada.**
- **El orden del bucle es la propiedad, no una convención:** `consolidar(t) → dosier(t) → decidir(t) → anotar(t)`. Anotar antes de decidir metería la señal de hoy en el dosier de hoy.
- **El factor solo baja.** 1.0 es a la vez el valor neutro y el máximo. Una celda con expectativa excelente **no** amplía el peso: premiar con tamaño lo que ya funcionó es la definición operativa de perseguir el rendimiento pasado. `test_el_factor_de_reflexion_nunca_sube_el_peso` recorre el producto cartesiano, igual que `test_los_vetos_solo_bajan_el_rating`.
- **Manda la peor dimensión, no el producto.** Estilo y momentum están correlacionados; multiplicar sus factores castigaría dos veces el mismo defecto.
- **El déficit se mide contra CERO; la contracción, contra la media global.** Medir el déficit contra la media obligaría a penalizar siempre a alguien —siempre hay una mitad por debajo— incluso en un sistema donde todas las celdas funcionan. La contracción sí va a la media, que es la mejor estimación de una celda sin datos.
- **Una dimensión cada vez, jamás cruzadas.** Cruzar estilo × momentum × sector produce celdas de tres observaciones, que es ruido con formato de tabla.
- **Sin muestra no hay ajuste, y se declara.** Por debajo de `REFLEXION_MUESTRA_MINIMA`, factor 1.0 con `evaluable=False` y motivo — nunca una expectativa inventada, igual que los percentiles de opciones no se inventan un 50 mientras acumulan histórico. Una instalación nueva no penaliza a nadie durante su primer año, y eso es correcto.
- **Con un solo candidato penalizado no hay a quién reasignar** y el presupuesto se queda sin usar; el freno efectivo en ese caso es el veto, no el factor. Está fijado en `test_sin_receptores_el_presupuesto_no_se_reparte` para que nadie lo «arregle».

**Recolección: ninguna excepción nueva al «un solo módulo toca la red».** El desenlace en producción se resuelve con `obtener_cierres_historicos`, en `src/tools/extraccion.py`. `src/memoria/` no importa nada de red: recibe un `resolver` inyectado.

| Entorno | Quién alimenta la memoria | Persistencia |
|---|---|---|
| Backtest | El bucle de `backtest_cli.py`, en el mismo recorrido temporal del replay | En memoria; sin `--con-reflexion` no se construye |
| Producción | `cli.py`, tras decidir, con **todos** los valores analizados y no solo las compras | `data/memoria/reflexion.jsonl` |

**En producción se sigue archivando aunque la capa no decida.** Cuesta un fichero de texto y es lo único que permitirá reevaluarla algún día con datos que no sean los mismos con los que se refutó. El dosier viaja vacío salvo con `--con-reflexion`.

### Analista de Noticias (`src/agents/news.py` + `src/tools/noticias.py` + `src/data/news/`) — capa ASESORA

Estima la probabilidad de que la actualidad de una empresa mueva su cotización. Reparto de responsabilidades idéntico al del resto del sistema: `src/data/news/` ingiere y normaliza, `src/agents/news.py` decide.

- Tres buscadores en paralelo (`ThreadPoolExecutor`), cada uno con su propio try/except: `sec_8k` (8-K con Ítem 2.02, vía `SECEdgarClient.get_recent_8k_earnings`), `google_news` (RSS público) y `tavily` (requiere `TAVILY_API_KEY` **y** el paquete `langchain-tavily`; sin cualquiera de los dos degrada a esa fuente y lo declara en el informe). Ninguna caída tumba el nodo: el peor caso es `status="SIN_DATOS"` con los motivos.
- El agregador deduplica por URL y por índice de Jaccard entre titulares normalizados. La corroboración se cuenta en **dominios distintos**, no en buscadores distintos.
- Caché en `data/cache/news/{TICKER}_{YYYY-MM-DD}.json`. La clave incluye el día porque las noticias son un dato "de hoy".
- El agente es **puro**: consume `state["news_data"]` y no toca la red, igual que el gatekeeper consume los fundamentales ya reconciliados. Sus dos tools —`puntuar_noticias` y `agregar_impacto_noticias`— tampoco salen a la red; la recolección la hace `obtener_noticias`, que pertenece al nodo de ingesta. Las funciones del scorer se reexportan desde `src.agents.news` porque son su contrato público y los tests las importan por ese nombre.

**Es una capa asesora, no un input de decisión.** Aparece en el informe y aporta un argumento al `debate_unit`, pero no toca `rating` ni `position_size_pct`. El motivo es el backtest: dos de sus tres fuentes son buscadores "de hoy" y no hay forma asequible de reconstruir qué era visible en una fecha pasada, así que el nodo **se excluye del `HistoricalReplayer`** (documentado en el encabezado de `src/backtest/replay.py` y en `build_limitations()`). Mientras siga siendo asesora, su ausencia en el replay no altera ni una señal. `test_news_report_does_not_alter_decision` protege exactamente esa premisa: **si conectas las noticias a la decisión, ese test debe fallar y el backtest deja de ser válido hasta que exista un `NewsStore` point-in-time.**

### Capa de backtest (`src/backtest/`) — solo lectura sobre los agentes

`HistoricalReplayer` **no reimplementa ninguna regla**. Importa las clases reales de `src/agents/`, reconstruye para una fecha `t` un estado indistinguible del que produciría `node_ingest_and_reconcile` ese día, y recorre el mismo camino usando el `route_after_gatekeeper` de producción.

Consecuencia práctica: **cualquier regla de decisión que aparezca en `src/backtest/` es un bug**. Si el backtest necesita comportarse distinto, el cambio va en `src/agents/`. `disable_llm()` parchea el símbolo `get_llm` importado en cada módulo de agente (no `src.config.get_llm`), porque `from src.config import get_llm` fija el nombre en el espacio del importador.

**El replay ejecuta el `QualityAnalystAgent`.** Desde que la convicción fundamental entra en el rating es una variable de decisión, y omitirla mediría una lógica distinta de la que decide en vivo. Sus insumos —estados financieros completos— se reconstruyen point-in-time en `FundamentalStore.estados_financieros()`, con el mismo filtro `filed <= t`. Cuando no hay estados reconstruibles el agente devuelve `DATOS_INSUFICIENTES` y el Fund Manager limita el dictamen a MANTENER: la degradación va siempre hacia la prudencia, nunca hacia una compra por defecto.

El `TodayFundamentalStore` (régimen `biased`) **no** devuelve estados financieros a propósito. Ese almacén existe para medir el look-ahead de los *ratios* de `yfinance.info`; añadir además Piotroski y Altman calculados con memorias que en la fecha simulada no existían mezclaría dos mediciones distintas.

`WEIGHT_BY_RATING` ya no manda: el Fund Manager emite `peso_objetivo` numérico y el replay lo consume directamente. La tabla queda solo como respaldo para estados antiguos — una regla de decisión duplicada fuera de `src/agents/` era justo lo que la arquitectura prohíbe.

**El motor histórico dimensiona con `PortfolioConstructor`**, la misma capa que corre en vivo (`build_orders(..., constructor)` en `engine.py`). Antes escalaba los pesos proporcionalmente hasta llenar la exposición bruta y nada más: sin límite sectorial, sin penalización por correlación y sin presupuesto de riesgo agregado. La cartera simulada podía por tanto concentrar todo el capital en un sector o en cinco valores que se movían al unísono, y las métricas describían una estrategia distinta de la que el sistema recomienda. Dos detalles:

- Las correlaciones se calculan con `_series_hasta()`, que **corta en `t` inclusive**. Una matriz calculada con datos posteriores sería look-ahead del más difícil de detectar: no cambia ninguna señal, solo los pesos.
- El régimen `technical_only` pasa `constructor=None` y conserva el reparto proporcional. Allí no hay Analista de Calidad, todas las convicciones son nulas y la capa de cartera no tendría nada que ordenar.

`Signal` transporta además `precio_entrada_objetivo`, `ajuste_entrada_pct` y `nivel_origen` — sin ellos el motor no tenía a dónde llevar el precio de entrada, y esa era la razón REAL de que el ajuste fuera inmedible. `Signal`, `Position` y `Trade` arrastran `estilo` y `conviccion` hasta el registro de operaciones, lo que habilita la **atribución por estilo** (`attr_estilo`) del informe: responde si el sistema pierde dinero en valor, en crecimiento o de forma transversal — la hipótesis que `NEXT_STEPS` planteaba sin poder medir.

División de responsabilidades:
- `data.py` — `PriceStore` (OHLCV cacheado), `FundamentalStore` (point-in-time desde XBRL, ratios **y** estados financieros), `COTStore` (posicionamiento en futuros filtrado por fecha de **publicación**) y `FREDStore` (volatilidad implícita filtrada por fecha de publicación, vía ALFRED). `TodayFundamentalStore` es el almacén deliberadamente sesgado.
- `replay.py` — reconstrucción del estado + ejecución de los agentes reales → `Signal`.
- `engine.py` — contabilidad de cartera. No conoce ni una regla de decisión.
- `metrics.py` — recibe series, devuelve números. No conoce la estrategia. Incluye PSR y **Sharpe deflactado** (López de Prado 2012/2014), levantados del repositorio 06: un Sharpe a secas ignora la longitud del registro, las colas y —sobre todo— que el mejor de MUCHAS variantes probadas está sesgado al alza por selección. `deflated_sharpe_ratio(rets, n_trials=...)` exige el recuento REAL de configuraciones evaluadas.
- `report.py` — markdown, JSON, CSV y PNG.

**Qué mide el estudio de cada capa de entrada, y qué no.** Las tres son de decisión y el replay ejecuta las tres, pero su reconstruibilidad es muy distinta y la diferencia se nombra en vez de promediarse:

| Bloque | ¿Point-in-time? | Qué mide el estudio |
|---|---|---|
| **Régimen de volatilidad** (`FREDStore` → `serie_diaria` con `as_of`) | **Sí, íntegro.** ALFRED devuelve la serie tal y como se conocía y adjunta la fecha de publicación por observación | **El 100% de la lógica.** Es la única capa de la que puede decirse. |
| **Macro COT** (`COTStore` → `serie_semanal` con `as_of`) | Sí. Filtra por `fecha_publicacion`, el mismo par `filed`/`end` del XBRL | Solo el veto que topa en COMPRA. La dirección macro por sí sola no elige nivel. |
| **Estructura de precio** (`minimos_previos` sobre `PriceStore.window`) | Sí. La misma función pura que usa producción, sobre la ventana ya cortada en `t` inclusive | El nivel de entrada y la bandera de soporte lejano. |
| **Cadena de opciones** | **No.** El histórico de open interest y volatilidad implícita es de pago | Nada. Se declara ausente **con su motivo**. |

Ninguno de los tres almacenes reimplementa la selección point-in-time: los tres invocan la MISMA función de producción con `as_of`. Una segunda implementación dentro de `src/backtest/` sería un bug igual que lo sería una segunda copia de una regla de decisión.

**La consecuencia, que hay que decir con precisión.** Desde que existe el Analista de Estructura, el estudio SÍ mide un ajuste de entrada —antes era `None` en el 100% de las señales— pero lo mide **con soportes de PRECIO, no con open interest**. Son dos niveles distintos: la versión que corre en vivo, con cadena disponible, elegirá a veces otro. Eso está en `build_limitations()`, y `test_sin_estructura_el_ajuste_de_entrada_no_cambia` fija que sin estructura la degradación reproduce el comportamiento anterior exacto, igual que `test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado`.

**El motor ya sabe ejecutar una orden limitada** (`--con-entrada-limitada`), que era `NEXT_STEPS` #1: límite en `precio_entrada_objetivo`, vida de `vida_orden_sesiones`, relleno a la apertura si esta abre por debajo, al límite si el mínimo lo toca, y **cancelación sin abrir posición** si expira. Está DESACTIVADO por defecto porque la medición lo desaconseja —ver «La entrada limitada, MEDIDA Y REFUTADA»—, no porque falte código.

Los regímenes `technical_only` y `biased` pasan `cot_store=None` y `fred_store=None`: allí la capa fundamental está neutralizada y añadir vetos macro o de régimen mezclaría dos mediciones distintas, por el mismo motivo por el que `TodayFundamentalStore` no devuelve estados financieros.

**`--sin-estructura` y `--sin-regimen` son interruptores de ABLACIÓN, no opciones de producción.** Existen para poder atribuir el efecto de cada capa por separado, que es la única forma de saber si aporta, y para fijar en un test que sin ellas el sistema se comporta exactamente como antes. Con las tres ablaciones activas el estudio reproduce la línea base **al decimal**: CAGR 3.947%, Sharpe 0.6808, drawdown −13.803%, 563 operaciones, acierto 44.58%, PF 1.381, expectativa +1.229%, percentil 7.4.

### Disciplina point-in-time

Es lo que separa un backtest de una ficción; el proyecto la aplica de forma explícita y verificada:

- **`filed` vs `end`**: los hechos XBRL se filtran por `filed <= t`, nunca por `end`. Un ejercicio cerrado el 31-dic no es público hasta el 10-K de febrero. Cuando falta `filed`, se asume un retardo de 45 días (`MIN_REPORTING_LAG_DAYS`), y un `filed` anterior a `end` se sanea. `_serie_de_hechos()` en `src/data/sec_edgar.py` acepta ahora un parámetro `as_of` opcional que aplica el mismo filtro `filed <= as_of`, y deduplica reexpresiones quedándose con la presentación más reciente de cada cierre. Producción no lo pasa —pregunta «qué se sabe hoy», y `companyfacts` solo contiene hechos ya presentados, así que ahí no hay look-ahead posible—, pero el parámetro elimina el riesgo que registraba `AUDIT.md` §4.3: que alguien reutilizara este cliente para una consulta histórica y reintrodujera la fuga. **No lo quites por «no usarse»: es exactamente lo que evita reimplementar la selección point-in-time una tercera vez.**
- **Informe COT vs publicación**: el informe del martes no es público hasta el viernes a las 15:30 ET. Es el MISMO par `filed`/`end` del XBRL, y filtrar por la fecha del informe permitiría operar el miércoles con datos que nadie tenía. `COT_RETARDO_PUBLICACION_DIAS` fija el desplazamiento y todo filtro usa `fecha_publicacion`. `test_serie_semanal_filtra_por_publicacion` es el análogo de `test_fundamentals_respect_filed_not_end`.
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

Revalidación tras incorporar el Analista de Calidad a la decisión (régimen `pit`, 2015-2025): el perfil de riesgo mejora de forma clara —Sharpe 0.35 → 0.68, drawdown máximo −22.6% → −13.8%, operaciones 928 → 563— pero **las dos conclusiones incómodas siguen en pie**: el CAGR (3.95%) no alcanza al del índice (13.51%) y el percentil frente a selección aleatoria (7.4) sigue por debajo de la mediana.

Revalidación tras incorporar el Analista de Estructura y el de Régimen (misma ventana, mismo régimen, contra su ablación exacta):

| | Antes | Después | |
|---|---|---|---|
| **Percentil vs. selección aleatoria** | 7.4 | **17.7** | ↑ |
| **Expectativa por operación** | +1.229% | **+1.291%** | ↑ |
| Tasa de acierto | 44.6% | **49.8%** | ↑ |
| Factor de beneficio | 1.38 | **1.45** | ↑ |
| Sharpe | 0.68 | **0.74** | ↑ |
| CAGR | 3.95% | 3.97% | ↑ |
| Máx. drawdown | −13.80% | **−16.15%** | ↓ |
| Operaciones | 563 | 532 | |

**Parte de esa mejora NO es de los agentes nuevos.** La caché del COT solo cubría 2022-2026, así que el veto macro llevaba **siete de los once años del estudio inerte**. Recargada de 2013 en adelante, el veto actúa y aporta por sí solo +2.5 puntos de acierto. Aislado: con la caché antigua el resultado era 47.3% de acierto y 16.6 de percentil; con la completa, 49.8% y 17.7.

**Y una advertencia sobre el percentil.** La misma estrategia da 20.3 con 300 muestras de Monte Carlo y 17.7 con 1000. Son ~2.6 puntos de ruido de muestreo: las cifras publicadas usan siempre las 1000 por defecto, y **una diferencia por debajo de uno o dos puntos entre configuraciones no es interpretable.**

Los dos criterios de aceptación mejoran y el percentil se dobla con creces. **El drawdown empeora 1.8 puntos**, y el mecanismo es el mismo que llevó a rechazar la memoria de reflexión: el veto concentra la cartera en menos nombres. Allí el intercambio salió en contra; aquí a favor.

**Las dos conclusiones incómodas siguen intactas y no deben suavizarse.** El CAGR (3.97%) no alcanza al del índice (13.51%) —la diferencia se ha ampliado, no reducido— y el percentil frente a selección aleatoria (17.7 sobre 100) sigue muy por debajo de la mediana: elegir al azar con el mismo perfil de exposición sigue batiendo a este sistema cinco veces de cada seis.

Lo que sí resolvió la revalidación: la atribución por estilo (`attr_estilo`) **descarta** la hipótesis que figuraba en `NEXT_STEPS` de que el gatekeeper penalizaba al *value*. Las operaciones etiquetadas VALOR son las de mejor rentabilidad media; el lastre está en CRECIMIENTO, con rentabilidad media negativa.

**El informe diario ya no lleva estas cifras escritas a mano.** `ReportGenerator._track_record()` las lee de `output/backtest_results.json`, precisamente porque la versión anterior las tenía embebidas en el código y quedó obsoleta en cuanto el backtest volvió a ejecutarse. Si el fichero no existe, el informe lo dice en vez de callar. **No vuelvas a incrustar cifras de rendimiento en el generador.**

El informe diario (`src/utils/report_generator.py`) numera las secciones de cada ficha con un **contador**, no con literales: un valor rechazado no tiene análisis técnico ni debate, y sin `TAVILY_API_KEY` puede no haber noticias. Numerarlas a mano dejaba huecos («3» seguido de «5»).

**El informe se reparte en tres documentos, separados por AUDIENCIA y no por tamaño**, y cada valor cabe ahora en UNA TABLA de hasta ocho filas —filtro, calidad, régimen, técnico, estructura, posicionamiento, noticias y debate— en lugar de otras tantas secciones de prosa. La versión anterior imprimía filtro, calidad, técnico, noticias, debate y dictamen como bloques narrativos independientes, cada uno con su párrafo explicativo del método; con veinte valores analizados eso son veinte copias del mismo párrafo. Cada bloque nuevo entra como UNA FILA más, no como una sección: es la razón de que añadir dos agentes no haya alargado el informe. Ahora el pormenor vive detrás de bloques `<details>` plegados y las explicaciones del método aparecen **una sola vez, en el anexo**. No se ha eliminado ni un dato: se ha dejado de imprimir seis veces lo que se lee una.

| Documento | Qué contiene |
|---|---|
| `output/resumen_ejecutivo.md` | La decisión y nada más: tabla por valor, cartera propuesta, reparto por estilo, track record y enlaces al resto. El **régimen de volatilidad va en la cabecera y no en una columna**, porque es un dato de lote: repetirlo por fila sería imprimir cincuenta veces lo que se lee una. Es el punto de entrada y lo que devuelve `generate_daily_selection()`. |
| `output/daily_selection.md` | El informe completo, sin recortes respecto de la versión anterior. |
| `output/detalle/{TICKER}.md` | Ficha del valor **más la traza**: qué herramienta se invocó, con qué argumentos y qué devolvió. Es lo que se consulta cuando un dictamen sorprende. |

`daily_selection.json` pasa por `_estado_serializable()`, que convierte el canal `messages` a su forma tipada. Sin eso, `json.dump(..., default=str)` volcaba el `repr` de una lista de objetos de LangChain: ilegible y sin estructura sobre la que consultar nada.

## Configuración del proveedor de LLM

`LLM_PROVIDER` solo tiene rama implementada para `huggingface`, `openai` y `gemini` en `get_llm()`. `ollama` y `heuristic` —anunciados en `README.md` y `.env.example`— caen por el final y devuelven `None`, que es exactamente el motor heurístico determinista. **No es un bug pendiente**: sin LLM el sistema produce los mismos ratings, así que `None` es un modo de operación de primera clase, no un fallback degradado.

Cualquier error al instanciar el proveedor se captura y también devuelve `None`. Por eso "el sistema funciona" nunca prueba que el LLM esté conectado; para eso hay que mirar los `summary` del informe.

Los umbrales del gatekeeper de `.env.example` (`MIN_NET_MARGIN=0.05`, `MAX_DEBT_TO_EQUITY=3.0`) **no coinciden** con los valores por defecto de `src/config.py` (`0.03` y `3.5`). Si comparas resultados entre máquinas, comprueba primero cuál de los dos está activo.

## Estado de la documentación del repositorio

No todo el markdown versionado describe el sistema actual. Antes de citar uno de estos documentos como contrato, comprueba de qué época es:

| Documento | Estado |
|---|---|
| `CLAUDE.md`, `README.md` | Al día. Son el contrato. |
| `output/AUDIT.md` | **Anterior a la capa de tools.** Sin tocar desde el primer commit: describe la decisión cuando las siete escuelas vivían dentro de `QualityAnalystAgent` y no existían ni el Analista de Posicionamiento ni la memoria de reflexión. Sus árboles de decisión del gatekeeper y del Fund Manager siguen siendo válidos; su mapa de módulos, no. |
| `implementation_plan.md` y `implementation_plan_multiAgentFinanciero.md` | Plan original, **byte a byte idénticos entre sí**. Histórico. |
| `walkthrough.md` | Recorrido de la primera versión. Histórico. |
| `prompts/backtest_prompt.md` | El prompt con el que se encargó la capa de backtest. Histórico. |
| `output/DISENO_POSICIONAMIENTO.md` | Documento de diseño del Analista de Posicionamiento, previo a implementarlo. Útil para el **porqué** de cada regla; la implementación manda. |
| `output/FUENTES_DATOS.md` | **Al día. Es el contrato de las fuentes.** Catálogo point-in-time: qué fuente es PIT-NATIVE, cuál PIT-ARCHIVABLE y cuál no tiene historia, con la recuperación concreta que lo acredita en cada caso. Incluye la lista de demandas de datos que **ninguna fuente gratuita cualificada puede cubrir**, que es la frontera permanente de lo que este sistema podrá validar. `tests/test_fuentes_pit.py` afirma en código la parte que no puede quedarse en prosa. |
| `output/INCORPORACION_AGENTES.md` | **Al día.** Inventario verificado de los cuatro repositorios hermanos, diseño de los agentes nuevos, y los dos ledgers medidos (Loop A sobre el grafo, Loop B sobre las configuraciones) con el Sharpe deflactado al recuento real de ensayos. |
| `prompts/entry_precision_agents_prompt.md` | El encargo con el que se incorporaron el Analista de Estructura y el de Régimen. Histórico. |

## Notas de plataforma

`src/data/fred/` **requiere `FRED_API_KEY`** (registro gratuito e instantáneo en fredaccount.stlouisfed.org/apikeys). Sin ella, `recolectar_regimen` declara el fallo y el Analista de Régimen degrada a `NO_APLICABLE` con la puerta abierta: el sistema funciona igual, simplemente sin veto de régimen. **Lo que NO hace, y no debe hacer nunca, es rellenar con datos plausibles** — el repositorio 02 del que viene la idea cae a un "stub" inventado cuando falta la clave, y eso en este proyecto es la violación de «ausencia ≠ cero» en su forma más pura.

`src/notebooks/` contiene prototipos, no código del pipeline: `agent_search_web.ipynb` es el borrador del que salió el Analista de Noticias (pedía criterio al LLM, algo que la versión de producción sustituye por diccionarios cerrados) y `plotter_graph.ipynb` dibuja el grafo. Nada de `src/` los importa.

`cli.py` y `backtest_cli.py` fuerzan `sys.stdout.reconfigure(encoding="utf-8")` porque los informes y los prints llevan acentos y emoji, y la consola de Windows fallaría con cp1252. Manténlo en cualquier entrypoint nuevo.
