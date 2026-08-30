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
# Análisis en vivo. Escribe TRES documentos más el JSON:
#   output/resumen_ejecutivo.md   la decisión agregada (punto de entrada)
#   output/daily_selection.md     el informe completo
#   output/detalle/{TICKER}.md    ficha por valor + traza de herramientas
<python> cli.py --tickers NVDA,AAPL,TSLA
<python> cli.py --tickers NVDA,AAPL --sin-cartera        # omite correlaciones y límites
<python> cli.py --tickers NVDA,AAPL --sin-benchmark      # momentum absoluto, no relativo
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
<python> backtest_cli.py --offline --quiet          # sin red, solo caché

# Tests
<python> -m pytest tests/                            # suite completa
<python> -m pytest tests/test_backtest.py            # suite sin red
<python> -m pytest tests/test_news_analyst.py        # suite sin red (Analista de Noticias)
<python> -m pytest tests/test_llm_texto.py           # suite sin red (contrato de texto del LLM)
<python> -m pytest tests/test_integridad_datos.py    # suite sin red (ausencia ≠ cero)
<python> -m pytest tests/test_momentum.py            # suite sin red (clasificador técnico)
<python> -m pytest tests/test_calidad.py             # suite sin red (Piotroski/Altman/Graham/estilo)
<python> -m pytest tests/test_cartera.py             # suite sin red (correlación y riesgo)
<python> -m pytest tests/test_tools.py               # suite sin red (registro de tools y frontera JSON)
<python> -m pytest tests/test_mensajes.py            # suite sin red (traza tipada de los agentes)
<python> -m pytest tests/test_investigador.py        # suite sin red (el ReAct no toca la decisión)
<python> -m pytest tests/test_backtest.py::test_no_lookahead_future_prices_do_not_change_past_signal -v
<python> -m pytest tests/test_news_analyst.py -k ruido -v          # filtrar por nombre

# Docker
docker-compose up --build
```

`tests/test_backtest.py`, `tests/test_reconciler.py`, `tests/test_news_analyst.py`, `tests/test_llm_texto.py`, `tests/test_integridad_datos.py`, `tests/test_momentum.py`, `tests/test_calidad.py`, `tests/test_cartera.py`, `tests/test_tools.py`, `tests/test_mensajes.py` y `tests/test_investigador.py` son offline y deterministas (los que tocan al LLM usan dobles). `tests/test_fetcher.py` y `tests/test_workflow.py` **golpean yfinance en vivo** y fallan sin red o si yfinance cambia el esquema de `info` — no son fiables en CI.

La primera ejecución de `backtest_cli.py` descarga precios y `companyfacts` de la SEC a `data/cache/` (~250 MB, ignorado por git). A partir de ahí `--offline` reproduce el estudio bit a bit.

## Arquitectura

### Grafo de producción (`src/graph/workflow.py`)

Máquina de estados LangGraph sobre `FinancialAnalysisState` (`src/state.py`, un `TypedDict` que cada nodo actualiza parcialmente):

```
                              ┌─ gatekeeper ────┐
ingest → quality_analysis ────┤                 ├─ join_analisis → [route_after_gatekeeper] ─┬─ aprobado → technical → debate → fund_manager → END
                              └─ news_analysis ─┘                                           └─ rechazado ─────────────────────→ fund_manager → END
```

`quality_analysis` va **secuencial y antes del fan-out**, no en paralelo, por dos motivos: es cálculo puro sobre datos ya ingeridos (paralelizarlo no ahorra latencia y solo añadiría un tercer escritor al mismo superstep), y colocarlo antes del gatekeeper deja sus puntuaciones y banderas rojas disponibles **también para los valores rechazados** — un Altman en zona de insolvencia es justo lo que se quiere leer sobre una empresa que no pasa el filtro.

El corte del gatekeeper es la razón de ser del diseño: un valor rechazado salta el análisis técnico y el debate, y el `fund_manager` le asigna VENTA / VENTA FUERTE directamente.

`gatekeeper` y `news_analysis` corren en paralelo (fan-out desde `quality_analysis`) y convergen en `join_analisis` **antes** del enrutado condicional.

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
  noticias.py       puntuación por ítem y agregación por OR ruidoso
  debate.py         tesis alcista, tesis bajista, condiciones de invalidación
  decision.py       rating compuesto, vetos, niveles de riesgo, tamaño, perfil R:R
  cartera.py        construcción de cartera y matriz de correlaciones
```

**Los cuerpos son los de siempre.** El traslado fue mecánico —los scorers nunca usaban `self`— y el `golden` del backtest se verificó idéntico tras cada agente migrado. **Una segunda copia de una regla de decisión es un bug**, exactamente igual que si apareciera en `src/backtest/`.

Dos capas por tool, y el motivo no es estético: los scorers operan sobre `Dict[str, Magnitud]`, que no es serializable y por tanto **no cabe en un `ToolMessage`**. La implementación (`_altman`, `_graham`, …) conserva esa firma; la fachada `@tool` (`calcular_altman`, …) convierte en el borde con `detalle_magnitudes` / `magnitudes_desde_detalle` (`src/data/magnitudes.py`). Los docstrings de las fachadas son la descripción que lee el LLM en la rama ReAct: se redactan como documentación de API.

`src/tools/extraccion.py` es el **único** módulo que sale a la red. Mirando los imports de un agente se sabe si puede hacer una petición; `tests/test_tools.py` fija esa separación en las dos direcciones.

`TOOLS_LECTURA` es el subconjunto que se enlaza al agente investigador. **Excluye deliberadamente** `calcular_rating_compuesto`, `aplicar_vetos`, `calcular_niveles_riesgo`, `dimensionar_posicion`, `calcular_perfil_riesgo`, `construir_cartera` y `reconciliar_fuentes`. Es la barrera que impide que el modelo emita un dictamen, y `test_el_react_no_alcanza_ninguna_tool_de_decision` la protege. **Si añades una tool que produzca una variable de decisión, mantenla fuera de esa lista.**

### Clase base de los agentes (`src/agents/base.py`)

Los seis agentes heredan de `AgenteBase` e implementan dos métodos: `decidir(state, traza)` —todo el análisis determinista— y `prompt_usuario(state, informe)`. `analyze(state) -> dict` se conserva como firma pública porque es el contrato que consumen `src/graph/workflow.py` y `src/backtest/replay.py`.

El orden de `analyze()` es la invariante hecha código: `decidir()` va **siempre** antes que `_redactar()`, de modo que cuando el LLM interviene todas las variables de decisión ya están fijadas y lo único que se le asigna es la clave que declara `campo_texto` (`summary` en cinco agentes, `synthesis` en el debate).

`usar_tool(nombre, args, traza)` es el `take_action` de `RAG_Agent.py` del curso, con una diferencia que lo es todo: **allí los `tool_calls` los emitía el modelo, aquí los emite el código.** La traza resultante tiene la misma forma —`AIMessage` con `tool_calls`, `ToolMessage` con el resultado y su `tool_call_id`— pero el plan de llamadas es determinista. Esa es la razón de que el sistema pueda tener tools sin romper su invariante: la forma de un agente ReAct, la sustancia de una función pura. Está también a nivel de módulo porque el nodo de ingesta invoca tools y deja traza sin ser un agente.

Dos detalles que no conviene deshacer:

- **`_obtener_llm()` resuelve `get_llm` en el módulo de la SUBCLASE**, no en el de la base. `from src.config import get_llm` fija el nombre en el espacio del importador, y todo el sistema se apoya en poder sustituirlo módulo a módulo: `disable_llm()` hace `mod.get_llm = lambda: None` sobre cada módulo de agente, y `tests/test_llm_texto.py` inyecta sus dobles igual. Si la base llamara a su propio `get_llm`, esos parches no surtirían efecto y el backtest abriría llamadas de red y de coste en mitad de una ejecución offline.
- **Los identificadores de la traza son secuenciales, no UUID.** Con UUID, dos ejecuciones del mismo análisis producían informes distintos —lo detectó `test_el_agente_es_reproducible`— y `daily_selection.json` cambiaba entero en cada pasada, volviendo inútil cualquier diff. Por lo mismo, `Traza.a_dict()` **no publica duraciones**: los milisegundos son irrepetibles por naturaleza y viven en el JSONL.

### Prompts (`src/prompts.py`)

Todos los system prompts y los constructores de prompt de usuario están aquí. Antes cada agente llevaba el suyo incrustado como f-string en mitad de `analyze()` y se invocaba con `llm.invoke(prompt)` — una cadena pelada, **sin `SystemMessage`**. Ahora la llamada es `llm.invoke([SystemMessage(...), HumanMessage(...)])`.

Los seis system prompts comparten tres bloques porque describen invariantes del sistema y no del agente: la **cláusula anti-decisión** (el modelo redacta, no decide), la **cláusula de ausencia** (una magnitud «no disponible» se dice, no se rellena con cero) y el **contrato de salida** (número de frases, español, prosa continua, sin markdown ni preámbulos). La cláusula de ausencia es la regla nº 1 del proyecto y antes solo aparecía en el prompt del gatekeeper, aunque aplica a los seis.

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

**Ninguna variable de decisión depende del LLM.** Los seis agentes calculan su dictamen con reglas deterministas y, si hay LLM configurado, este solo sobrescribe campos de texto (`summary` en fundamental/quality/technical/news/fund_manager, `synthesis` en debate). Sin token de API, `get_llm()` devuelve `None` y el sistema produce exactamente los mismos ratings.

Esto no es un detalle de estilo: es lo que permite que el backtest reproduzca la lógica real de forma determinista y a coste cero. Se verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()` (`src/backtest/replay.py`), que ejecuta los agentes con y sin un LLM falso y compara `passed_gatekeeper`, `momentum_classification`, `rating`, `position_size_pct`, los niveles de stop/objetivo y el dictamen de noticias (`impact_probability`, `impact_classification`, `direction_classification`, `catalysts`) y el del Analista de Calidad (`style_classification`, `conviccion_fundamental`, las cuatro puntuaciones, F-Score y Z-Score). `backtest_cli.py` aborta si la verificación falla, y `test_llm_is_decision_neutral` la cubre en la suite.

**Si añades lógica a un agente, el resultado del LLM no puede entrar en ninguna rama ni en ningún número.** Solo en texto.

La invariante sobrevive a la introducción de tools porque **el plan de llamadas lo escribe el código, no el modelo** (ver `src/agents/base.py`). La única pieza donde el LLM sí elige es el agente investigador, que está fuera de la ruta de decisión y solo alcanza `TOOLS_LECTURA`.

Reglas de decisión concretas (documentadas exhaustivamente en `output/AUDIT.md`):
- Gatekeeper: umbrales `MIN_NET_MARGIN`, `MIN_REVENUE_GROWTH`, `MAX_DEBT_TO_EQUITY` de `src/config.py` (leídos del entorno **en tiempo de import**), con excepciones sectoriales en `GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR` — aplicar el mismo límite de deuda a un banco que a una empresa de software es un error de categoría.
- Calidad y valoración: `src/tools/calidad.py` (orquestado por `src/agents/quality.py`) → cuatro puntuaciones 0-100 (calidad, valoración, crecimiento, solvencia), `conviccion_fundamental` y `style_classification`. Ver la sección propia más abajo.
- Momentum: `src/tools/tecnico.py`, una tool por bloque. Puntuación **continua** en `[-100, +100]` como suma ponderada de cinco bloques (tendencia 30, MACD 20, RSI 20, Bollinger 10, momentum de precio 20); las etiquetas son cortes sobre ese número. Constantes `MOMENTUM_*` en `src/config.py`.
- Rating final: puntuación compuesta `0.65·convicción + 0.35·momentum_normalizado` cortada por `CORTES_RATING` en `src/tools/decision.py`, más vetos que **solo bajan** (`aplicar_vetos`; `test_los_vetos_solo_bajan_el_rating` recorre el producto cartesiano de condiciones para comprobarlo). Stop y objetivo salen de `ATR_AJUSTE_POR_ESTILO`, que varía el múltiplo y el horizonte según el estilo asignado.
- Tamaño de posición: **número, no cadena**. `peso = (riesgo_asumible / distancia_al_stop) × factor_volatilidad × descuentos`, acotado por `PESO_MAXIMO_POSICION` y `PESO_MINIMO_OPERABLE`.
- Noticias: `src/tools/noticias.py` sobre el dosier que recolecta `src/data/news/`. Por ítem, `p = NEWS_ITEM_PROB_MAX · peso_categoría · credibilidad_de_la_fuente · decaimiento(antigüedad) · corroboración · penalización_de_ruido`; el conjunto se agrega con OR ruidoso sobre los `NEWS_TOP_K_ITEMS` mayores → `impact_probability` y bucket ALTA/MEDIA/BAJA. Categoría y dirección salen de diccionarios cerrados, nunca del LLM. Todas las constantes están en `src/config.py`.

#### Contrato del único campo que sí toca el LLM

La respuesta del proveedor **nunca** se asigna directamente. `AgenteBase._redactar()` hace `texto = texto_de_respuesta_llm(llm.invoke([SystemMessage(...), HumanMessage(...)]))` (`src/config.py`) —una sola vez, para los seis agentes— y solo sobrescribe el campo si `texto` no es `None`:

- Los proveedores modernos devuelven `content` como **lista de bloques** (`[{"type": "text", "text": "..."}]`), no como cadena. Asignarlo tal cual metía una lista de diccionarios de Python en el informe y en `daily_selection.json` — el defecto que motivó el helper.
- Devuelve `None` (no cadena vacía) cuando no hay texto utilizable, precisamente para que el agente **conserve su resumen determinista** en lugar de perder información ya calculada.
- La llamada va siempre dentro de un `try/except`: un fallo del proveedor degrada al texto heurístico, nunca tumba al agente.

`tests/test_llm_texto.py` fija ese contrato para los seis agentes: `summary`/`synthesis` son `str` pase lo que pase. Los dobles de esa suite declaran `invoke(self, prompt)` con un solo posicional, así que la lista de mensajes los satisface sin cambios.

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
2. Penalización por correlación media con el resto de candidatos.
3. Tope por sector (`LIMITE_POR_SECTOR`).
4. Tope de número de posiciones, conservando las de mayor convicción.
5. Presupuesto de riesgo agregado (`RIESGO_TOTAL_CARTERA_PCT`): suma de `peso × distancia_al_stop`.
6. Tope de exposición bruta.

Cada paso deja constancia de lo que recortó en `restricciones_activadas` y en los `ajustes` de cada posición. Sin matriz de correlaciones **no se corrige nada** y se declara la limitación: es preferible no corregir a corregir con una matriz inventada.

`posiciones_existentes` permite usar esta misma capa desde el motor histórico, donde en cada rebalanceo ya hay posiciones abiertas. Entran con peso **fijo** —no se reescalan, porque reajustar la cartera entera en cada rebalanceo generaría rotación cuyo coste se comería el ajuste— pero **consumen presupuesto** sectorial, de riesgo y de exposición. Sin eso, cada rebalanceo respetaría el tope del 30% por sector y la cartera acabaría igualmente con el 90% en un sector tras tres rebalanceos.

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

`Signal`, `Position` y `Trade` arrastran `estilo` y `conviccion` hasta el registro de operaciones, lo que habilita la **atribución por estilo** (`attr_estilo`) del informe: responde si el sistema pierde dinero en valor, en crecimiento o de forma transversal — la hipótesis que `NEXT_STEPS` planteaba sin poder medir.

División de responsabilidades:
- `data.py` — `PriceStore` (OHLCV cacheado) y `FundamentalStore` (point-in-time desde XBRL, ratios **y** estados financieros). `TodayFundamentalStore` es el almacén deliberadamente sesgado.
- `replay.py` — reconstrucción del estado + ejecución de los agentes reales → `Signal`.
- `engine.py` — contabilidad de cartera. No conoce ni una regla de decisión.
- `metrics.py` — recibe series, devuelve números. No conoce la estrategia.
- `report.py` — markdown, JSON, CSV y PNG.

### Disciplina point-in-time

Es lo que separa un backtest de una ficción; el proyecto la aplica de forma explícita y verificada:

- **`filed` vs `end`**: los hechos XBRL se filtran por `filed <= t`, nunca por `end`. Un ejercicio cerrado el 31-dic no es público hasta el 10-K de febrero. Cuando falta `filed`, se asume un retardo de 45 días (`MIN_REPORTING_LAG_DAYS`), y un `filed` anterior a `end` se sanea. `_serie_de_hechos()` en `src/data/sec_edgar.py` acepta ahora un parámetro `as_of` opcional que aplica el mismo filtro `filed <= as_of`, y deduplica reexpresiones quedándose con la presentación más reciente de cada cierre. Producción no lo pasa —pregunta «qué se sabe hoy», y `companyfacts` solo contiene hechos ya presentados, así que ahí no hay look-ahead posible—, pero el parámetro elimina el riesgo que registraba `AUDIT.md` §4.3: que alguien reutilizara este cliente para una consulta histórica y reintrodujera la fuga. **No lo quites por «no usarse»: es exactamente lo que evita reimplementar la selección point-in-time una tercera vez.**
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

Revalidación tras incorporar el Analista de Calidad a la decisión (régimen `pit`, 2015-2025): el perfil de riesgo mejora de forma clara —Sharpe 0.35 → 0.68, drawdown máximo −22.6% → −13.8%, operaciones 928 → 563— pero **las dos conclusiones incómodas siguen en pie**: el CAGR (3.95%) no alcanza al del índice (13.51%) y el percentil frente a selección aleatoria (7.4) sigue por debajo de la mediana. Es decir, la selección de valores todavía no aporta sobre elegir al azar con el mismo perfil de exposición.

Lo que sí resolvió la revalidación: la atribución por estilo (`attr_estilo`) **descarta** la hipótesis que figuraba en `NEXT_STEPS` de que el gatekeeper penalizaba al *value*. Las operaciones etiquetadas VALOR son las de mejor rentabilidad media; el lastre está en CRECIMIENTO, con rentabilidad media negativa.

**El informe diario ya no lleva estas cifras escritas a mano.** `ReportGenerator._track_record()` las lee de `output/backtest_results.json`, precisamente porque la versión anterior las tenía embebidas en el código y quedó obsoleta en cuanto el backtest volvió a ejecutarse. Si el fichero no existe, el informe lo dice en vez de callar. **No vuelvas a incrustar cifras de rendimiento en el generador.**

El informe diario (`src/utils/report_generator.py`) numera las secciones de cada ficha con un **contador**, no con literales: un valor rechazado no tiene análisis técnico ni debate, y sin `TAVILY_API_KEY` puede no haber noticias. Numerarlas a mano dejaba huecos («3» seguido de «5»).

**El informe se reparte ahora en tres documentos, separados por AUDIENCIA y no por tamaño.** La versión anterior era un único fichero de 75 KB en el que la decisión agregada —lo primero que hay que leer— quedaba enterrada bajo las fichas:

| Documento | Qué contiene |
|---|---|
| `output/resumen_ejecutivo.md` | La decisión y nada más: tabla por valor, cartera propuesta, reparto por estilo, track record y enlaces al resto. Es el punto de entrada y lo que devuelve `generate_daily_selection()`. |
| `output/daily_selection.md` | El informe completo, sin recortes respecto de la versión anterior. |
| `output/detalle/{TICKER}.md` | Ficha del valor **más la traza**: qué herramienta se invocó, con qué argumentos y qué devolvió. Es lo que se consulta cuando un dictamen sorprende. |

`daily_selection.json` pasa por `_estado_serializable()`, que convierte el canal `messages` a su forma tipada. Sin eso, `json.dump(..., default=str)` volcaba el `repr` de una lista de objetos de LangChain: ilegible y sin estructura sobre la que consultar nada.

## Configuración del proveedor de LLM

`LLM_PROVIDER` solo tiene rama implementada para `huggingface`, `openai` y `gemini` en `get_llm()`. `ollama` y `heuristic` —anunciados en `README.md` y `.env.example`— caen por el final y devuelven `None`, que es exactamente el motor heurístico determinista. **No es un bug pendiente**: sin LLM el sistema produce los mismos ratings, así que `None` es un modo de operación de primera clase, no un fallback degradado.

Cualquier error al instanciar el proveedor se captura y también devuelve `None`. Por eso "el sistema funciona" nunca prueba que el LLM esté conectado; para eso hay que mirar los `summary` del informe.

Los umbrales del gatekeeper de `.env.example` (`MIN_NET_MARGIN=0.05`, `MAX_DEBT_TO_EQUITY=3.0`) **no coinciden** con los valores por defecto de `src/config.py` (`0.03` y `3.5`). Si comparas resultados entre máquinas, comprueba primero cuál de los dos está activo.

## Notas de plataforma

`src/notebooks/` contiene prototipos, no código del pipeline: `agent_search_web.ipynb` es el borrador del que salió el Analista de Noticias (pedía criterio al LLM, algo que la versión de producción sustituye por diccionarios cerrados) y `plotter_graph.ipynb` dibuja el grafo. Nada de `src/` los importa.

`cli.py` y `backtest_cli.py` fuerzan `sys.stdout.reconfigure(encoding="utf-8")` porque los informes y los prints llevan acentos y emoji, y la consola de Windows fallaría con cp1252. Manténlo en cualquier entrypoint nuevo.
