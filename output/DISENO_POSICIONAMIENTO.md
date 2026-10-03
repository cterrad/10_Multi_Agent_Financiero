# Diseño — Analista de Posicionamiento y Precio de Entrada

Documento de diseño, no de implementación. Firmas, docstrings de fachada y
pseudocódigo donde el contrato lo exige; ningún archivo nuevo escrito.

**Qué se propone.** Un agente que estima *a qué precio conviene entrar* en un
valor que el sistema ya ha decidido comprar, cruzando tres cosas: el sesgo
macro/sectorial que se lee en el posicionamiento de futuros (COT), el
posicionamiento en la cadena de opciones del propio ticker (put/call, open
interest por strike, exposición gamma de los creadores de mercado, skew) y el
momentum propio del valor que ya calcula `technical`. De los dos primeros sale
un **nivel de precio concreto**; del cruce de los tres sale si se persigue el
precio o se exige un retroceso hasta ese nivel.

> **ESTADO: IMPLEMENTADO.** Este documento se escribió como diseño previo y se
> conserva como registro de las decisiones y su justificación. El sistema
> construido sigue el diseño con **una desviación deliberada, decidida por el
> autor del proyecto**: la §7 recomendaba desplegar la v1 con el bloque de
> opciones como capa ASESORA, y lo que se ha construido es la **capa de decisión
> completa** — `precio_entrada_objetivo` alimenta `calcular_niveles_riesgo` en
> producción. Las consecuencias de esa elección están asumidas y declaradas: ver
> la §7 revisada al final del documento y `build_limitations()` en
> `backtest_cli.py`.
>
> Otras dos desviaciones menores, ambas por verificación contra las fuentes
> reales: los patrones de mercado de la CFTC se corrigieron tras descargar
> `deacot2025.zip` (§9.1 resultó ser un hueco real: «NATURAL GAS» y «10 YEAR
> NOTE» no casan con nada), y el skew se define por *moneyness* fijo en lugar de
> por delta de 25, para que el agregado que alimenta el percentil siga siendo
> aritmética y no requiera Griegas en la capa de datos.

Un aviso que conviene leer antes de la sección 1, porque condiciona todo lo
demás: **la mitad de opciones de este diseño no es reconstruible point-in-time
con fuentes gratuitas**, y por tanto no es backtesteable. Eso no impide
construirla, pero sí determina qué puede tocar en v1. Está resuelto en la
sección 7.

---

## 1. Ubicación en el grafo

### Decisión: **(C) — nodo nuevo secuencial después de `technical_analysis`, antes de `debate_unit`, solo en la rama aprobada.**

```
                              ┌─ gatekeeper ────┐
ingest → quality_analysis ────┤                 ├─ join_analisis → [route] ─┬─ aprobado → technical → posicionamiento → debate → fund_manager → END
                              └─ news_analysis ─┘                          └─ rechazado ───────────────────────────────────────→ fund_manager → END
```

Cambio topológico exacto: se sustituye la arista única de
[workflow.py:317](src/graph/workflow.py#L317)

```python
workflow.add_edge("technical_analysis", "debate_unit")
```

por dos aristas encadenadas, más `workflow.add_node("posicionamiento", node_posicionamiento)`.
**No se toca nada más.** `route_after_gatekeeper`
([workflow.py:240-244](src/graph/workflow.py#L240-L244)) sigue devolviendo
`"technical_analysis"` o `"fund_manager"`, así que la rama de rechazo salta el
nodo nuevo sin una sola línea de enrutado adicional. Y el bloque de
`add_conditional_edges` ([workflow.py:308-315](src/graph/workflow.py#L308-L315))
queda intacto.

### Por qué (C) y no (B)

El criterio de desempate que la propia petición fija es correcto: (B) solo vale
si el agente es funcionalmente independiente de `technical`. **No lo es**, y no
por un detalle: la comparación de tres vías es el producto del agente, no un
adorno. Consume dos campos que escribe `technical`:

- `momentum_score` — [technical.py:133-134](src/agents/technical.py#L133-L134),
  publicado en el informe en [technical.py:152-153](src/agents/technical.py#L152-L153).
  Es la tercera pata de la confluencia (§4.3).
- `sobreextendido` — [technical.py:140](src/agents/technical.py#L140). Es la
  condición que prohíbe «perseguir el precio», y su comentario en el propio
  código ya anticipa este uso: *«no altera la etiqueta […] pero el Fund Manager
  lo usa para recortar tamaño, que es donde debe actuar la prudencia sobre un
  valor extendido»*. El precio de entrada es exactamente el otro sitio donde
  debe actuar.

También consume `atr` ([technical.py:163](src/agents/technical.py#L163)) para
acotar el ajuste en unidades de volatilidad (§4.3), y `bb_lower` / `sma_50`
([technical.py:167-169](src/agents/technical.py#L167-L169)) como nivel de
repliegue declarado.

Esa es una dependencia de datos real, del mismo tipo que la que el proyecto ya
usa para ordenar y no paralelizar dentro de `quality.py`. `CLAUDE.md` lo dice
sin ambigüedad: *«las puntuaciones necesitan las siete escuelas ya calculadas,
las banderas rojas necesitan las puntuaciones, el estilo necesita las banderas
[…] Reordenar no produce un error, produce un dictamen distinto.»* Aquí ocurre
lo mismo un nivel más arriba: paralelizar no rompería el grafo, produciría un
dictamen distinto — uno sin comparación de tres vías.

Tres razones adicionales, todas verificables en el código:

1. **(B) no ahorraría latencia, que es la única cosa que el paralelismo compra
   en este grafo.** El nodo nuevo es cálculo puro: la recolección de red vive en
   la ingesta (§3), igual que la de noticias. Y el encabezado de
   [workflow.py:28-34](src/graph/workflow.py#L28-L34) ya resolvió este mismo
   caso para `quality_analysis`: *«Es cálculo puro sobre datos ya ingeridos, así
   que paralelizarlo no ahorraría latencia»*. El fan-out
   `gatekeeper` / `news_analysis` ([workflow.py:300-306](src/graph/workflow.py#L300-L306))
   existe porque uno de los dos hace tres peticiones HTTP
   ([workflow.py:180-189](src/graph/workflow.py#L180-L189)). Aquí no hay ninguna.

2. **(B) heredaría la restricción de `workflow_status`.** Es un escalar sin
   reductor ([state.py:93](src/state.py#L93)), y por eso `news_analysis` no
   puede escribirlo ([workflow.py:24-26](src/graph/workflow.py#L24-L26)). Un
   nodo en paralelo con `technical` tampoco podría, y perderíamos la marca de
   etapa. En (C) el nodo está solo en su superstep y escribe
   `workflow_status="POSITIONING_COMPLETED"` sin problema.

3. **(B) exigiría un `join_tecnico` nuevo.** El motivo por el que
   `join_analisis` sigue existiendo ([workflow.py:36-43](src/graph/workflow.py#L36-L43))
   —ramas de longitud distinta que hacen coincidir dos nodos en un superstep—
   se reproduce idéntico. Añadir un nodo vacío para resolver un paralelismo que
   no ahorra nada es coste sin contrapartida.

### Por qué antes de `debate_unit` y no después

Porque el patrón del proyecto es que todo lo determinista se cierra antes del
debate. `DebateUnitAgent.decidir()` construye sus tesis a partir de informes ya
cerrados ([debate.py:74-89](src/agents/debate.py#L74-L89)) y el Fund Manager
consume su síntesis ([fund_manager.py:180-181](src/agents/fund_manager.py#L180-L181)).
Colocar el nodo después del debate dejaría al debate argumentando sobre un
precio de entrada que aún no existe.

Además, así el debate **gana un argumento nuevo**: la divergencia entre el
momentum propio del valor y el sesgo macro es exactamente el tipo de tensión
que la tesis bajista debería recoger, y entra por la misma vía por la que hoy
entran las noticias ([debate.py:91-97](src/agents/debate.py#L91-L97)) — como
una frase más, sin tocar ninguna cifra.

### Por qué solo en la rama aprobada

Por el mismo motivo que `technical` no corre para los rechazados: el precio de
entrada óptimo de un valor al que se le va a asignar VENTA no significa nada.
`_decision_rechazada` ([decision.py:76-133](src/tools/decision.py#L76-L133))
devuelve `stop_loss_atr=None` y `peso_objetivo=0.0`; un `precio_entrada_objetivo`
ahí sería ruido.

---

## 2. Contrato de datos

### Campos nuevos en `FinancialAnalysisState`

```python
# --- Ingesta (escritos por node_ingest_and_reconcile / el orquestador) ---

# Dosier macro COMPARTIDO por todos los tickers de la ejecución: futuros
# continuos e informes COT de la CFTC. No es por ticker (el sesgo del futuro
# del petróleo es el mismo para todas las energéticas del lote), así que lo
# resuelve el orquestador UNA vez y viaja en el estado inicial, exactamente
# igual que `benchmark_data`. Ver §3.
futures_data: Dict[str, Any]

# Cadena de opciones del PROPIO ticker. Sí es por ticker, y la escribe el nodo
# de ingesta como cualquier otra fuente. Ver §3.
options_data: Dict[str, Any]

# --- Informe (escrito por node_posicionamiento) ---

# Dictamen del Analista de Posicionamiento: sesgo macro vía COT, sesgo de
# posicionamiento en opciones, nivel de precio de referencia y ajuste de
# entrada. En v1 es capa ASESORA — ver §7, que es donde se explica por qué.
positioning_report: Dict[str, Any]
```

Los tres van en inglés como el resto de claves de estado (`yfinance_data`,
`news_data`, `quality_report`), y los módulos y tools en español como el resto
de `src/tools/`.

### Semántica de ausencia — la regla nº 1 del proyecto aplicada aquí

Este agente tiene un modo de fallo que los demás no tienen, y hay que nombrarlo:
**`ajuste_entrada_pct = 0.0` es una lectura real y frecuente** («las tres
señales confirman: entra a mercado»). No es lo mismo que «no se pudo calcular».
Confundirlos aquí sería reproducir exactamente el defecto que
`src/data/magnitudes.py` existe para corregir, con el agravante de que el 0.0
sería *plausible* y por tanto invisible en el informe.

| Campo | Tipo | Ausencia | Qué significa el valor |
|---|---|---|---|
| `status` | `str` | — | `SUCCESS` · `DEGRADADO` · `DATOS_INSUFICIENTES` |
| `sesgo_macro` | `Optional[float]` en `[-1,+1]` | `None` | Viento a favor (+) / en contra (−) del sector |
| `sesgo_macro_clasificacion` | `str` | `NO_APLICABLE` | `VIENTO_A_FAVOR_FUERTE` · `VIENTO_A_FAVOR` · `NEUTRO` · `VIENTO_EN_CONTRA` · `VIENTO_EN_CONTRA_FUERTE` · `NO_APLICABLE` |
| `cot` | `Dict` | `{}` | z-score, contrato, categoría de trader, semanas de muestra, fecha de publicación |
| `sesgo_opciones` | `Optional[float]` en `[-1,+1]` | `None` | Sesgo de posicionamiento en la cadena |
| `sesgo_opciones_clasificacion` | `str` | `NO_APLICABLE` | `DATOS_INSUFICIENTES` cuando hay cadena pero no histórico para percentiles |
| `opciones` | `Dict` | `{}` | `pcr_oi`, `pcr_volumen`, percentiles, `skew_25d`, `gex_total`, OI agregado |
| `soporte_oi` | `Optional[float]` | `None` | Strike con mayor OI de puts por debajo del precio |
| `resistencia_oi` | `Optional[float]` | `None` | Strike con mayor OI de calls por encima del precio |
| `max_pain` | `Optional[float]` | `None` | Strike que minimiza el valor intrínseco agregado |
| `gamma_flip` | `Optional[float]` | `None` | Precio donde la GEX agregada cambia de signo |
| `nivel_referencia` | `Optional[float]` | `None` | El nivel elegido entre los candidatos (§4.3) |
| `nivel_origen` | `str` | `NO_APLICABLE` | `SOPORTE_OI` · `MAX_PAIN` · `GAMMA_FLIP` · `REPLIEGUE_TECNICO` · `NO_APLICABLE` |
| `entrada_clasificacion` | `str` | `NO_APLICABLE` | `PERSEGUIR` · `ESCALONAR` · `ESPERAR_RETROCESO` · `NO_APLICABLE` |
| `ajuste_entrada_pct` | `Optional[float]` ≤ 0 | `None` | **`0.0` = entrar a mercado por confluencia. `None` = no calculable.** |
| `precio_entrada_objetivo` | `Optional[float]` | `None` | `precio · (1 + ajuste_entrada_pct)` |
| `confluencia` | `Optional[float]` en `[0,1]` | `None` | Fracción de componentes disponibles que coinciden en signo |
| `componentes_disponibles` | `List[str]` | `[]` | Cuáles de los tres entraron en el promedio |
| `advisory_only` | `bool` | — | `True` en v1, como `news_report` ([news.py:174](src/agents/news.py#L174)) |
| `signals` | `List[str]` | `[]` | Líneas legibles para el informe, patrón de `technical` |
| `summary` / `resumen_determinista` | `str` | — | El único campo que el LLM puede sobrescribir |

Dos ausencias explícitamente prohibidas de rellenar, que es lo que la petición
exige y lo que `tests/test_integridad_datos.py` debe fijar:

- **Sector sin futuro correlato claro → `sesgo_macro = None` y
  `sesgo_macro_clasificacion = "NO_APLICABLE"`.** Nunca un proxy forzado. El
  mapa sector→contrato es un diccionario cerrado y un sector que no está en él
  no está por decisión, no por olvido (§4.1).
- **Cadena inexistente, ilíquida o con OI agregado por debajo del mínimo →
  `sesgo_opciones = None`, niveles `None`, `NO_APLICABLE`.** Un `0.0` ahí se
  leería como «sin sesgo de posicionamiento», que es una afirmación fuerte
  sobre una empresa cuya cadena nadie negocia.

---

## 3. Recolección

### La conclusión primero: no hace falta ninguna excepción nueva

La petición asume que `src/data/news/` es «la única excepción documentada» a
«un solo módulo toca la red». Leyendo el código, **no es una excepción en
absoluto**: la tool de red `obtener_noticias` vive en
[extraccion.py:107-124](src/tools/extraccion.py#L107-L124) y lo único que hace
es delegar (`from src.data.news import recolectar`). La regla se sostiene
exactamente donde el proyecto la comprueba —
`test_las_tools_de_red_estan_donde_deben`
([test_tools.py:220-229](tests/test_tools.py#L220-L229)) verifica que
`tool.func.__module__ == "src.tools.extraccion"` — y `src/data/news/` es la capa
de *recolección* detrás de la tool, no otra puerta a la red.

Por tanto ambos bloques nuevos siguen ese mismo patrón, sin multiplicar nada:

| Qué | Recolector | Tool (en `extraccion.py`) | Quién la invoca |
|---|---|---|---|
| Cadena de opciones | `src/data/fetcher.py` (`DataFetcher`) | `obtener_cadena_opciones` | `node_ingest_and_reconcile` |
| Futuros continuos + COT | `src/data/futuros/` (nuevo) | `obtener_contexto_macro` | El orquestador, **una vez por ejecución** |

### 3.1 Cadena de opciones → dentro de `DataFetcher`, sin módulo nuevo

`DataFetcher.fetch_all()` ya instancia `stock = yf.Ticker(symbol)` en
[fetcher.py:154](src/data/fetcher.py#L154) y le pide `info`, `history` y los
tres estados financieros. `Ticker.options` y `Ticker.option_chain(fecha)`
cuelgan de ese mismo objeto. Meter la cadena en otro sitio significaría
instanciar un segundo `yf.Ticker` para el mismo símbolo en la misma ejecución.

Se añade un método hermano de `_fetch_estados_financieros`
([fetcher.py:246](src/data/fetcher.py#L246)) con la misma disciplina —bloque
opcional, fallo aislado, degradación declarada— y el mismo interruptor de
construcción que ya existe (`DataFetcher(con_estados_financieros=False)`,
[fetcher.py:144-149](src/data/fetcher.py#L144-L149)):

```python
def __init__(self, con_estados_financieros: bool = True,
             con_cadena_opciones: bool = True): ...

def _fetch_cadena_opciones(self, stock: "yf.Ticker") -> Dict[str, Any]:
    """
    Cadena de opciones de los vencimientos dentro de `OPCIONES_VENTANA_DIAS`.

    Devuelve por contrato: strike, tipo, openInterest, volume,
    impliedVolatility, lastPrice, dias_a_vencimiento. Sin cadena, sin
    volatilidad implícita publicada o con OI agregado por debajo de
    `OPCIONES_OI_MINIMO`, devuelve `{"disponible": False, "motivo": ...}` — no
    un diccionario de ceros.
    """
```

La tool de red, en `extraccion.py`, junto a las otras cinco:

```python
@tool("obtener_cadena_opciones")
def obtener_cadena_opciones(ticker: str, ventana_dias: int = 45) -> Dict[str, Any]:
    """Cadena de opciones cotizadas del ticker, por vencimiento y strike.

    Devuelve para cada contrato dentro de la ventana: strike, tipo (call/put),
    open interest, volumen, volatilidad implícita y días a vencimiento. Es el
    insumo del put/call ratio, de los niveles de open interest, del max pain y
    de la exposición gamma agregada.

    Una cadena ausente, sin volatilidad implícita o con open interest agregado
    por debajo del mínimo se declara NO disponible con su motivo. Nunca se
    rellena con ceros: un cero se leería como «sin posicionamiento», que es una
    afirmación fuerte sobre una empresa cuya cadena nadie negocia.

    HACE UNA PETICIÓN DE RED. La caché es diaria: la cadena es un dato de hoy.
    """
```

Caché: `data/cache/opciones/{TICKER}_{YYYY-MM-DD}.json`, clave idéntica a la de
noticias ([news/cache.py:23-25](src/data/news/cache.py#L23-L25)) y por el mismo
motivo. **Con una diferencia que importa mucho y que se explota en §4.2: esta
caché es ACUMULATIVA.** Los ficheros de días anteriores no se borran, porque el
percentil histórico del put/call ratio y del skew se calcula sobre ellos. Es lo
más parecido a un `OpcionesStore` point-in-time que se puede construir sin
pagar, y crece un fichero por ticker y día.

### 3.2 Futuros y COT → `src/data/futuros/`, resuelto una vez por ejecución

Aquí sí hay proveedores nuevos, y sí merecen módulo propio:

```
src/data/futuros/
  __init__.py    recolectar_macro() → dosier compartido
  cot.py         descarga y parseo del Commitments of Traders (CFTC)
  continuos.py   precios del futuro continuo (yfinance: CL=F, ES=F, HG=F, ZN=F...)
  cache.py       dos cachés con claves distintas, ver abajo
```

Y una sola tool de red en `extraccion.py`:

```python
@tool("obtener_contexto_macro")
def obtener_contexto_macro(contratos: Optional[List[str]] = None) -> Dict[str, Any]:
    """Posicionamiento de futuros e informes COT de la CFTC.

    Devuelve, por contrato: la serie semanal de posición neta no comercial
    (especuladores) normalizada por interés abierto, su z-score frente a las
    últimas `COT_VENTANA_SEMANAS` semanas, la fecha del informe (martes) y la
    fecha de publicación (viernes), más el precio del futuro continuo.

    NO es un dato por ticker: el sesgo del futuro del petróleo es el mismo para
    todas las energéticas de una misma ejecución. Se resuelve una vez y se
    reparte. Sin contratos indicados descarga el conjunto cerrado de
    `SECTOR_A_FUTURO` más el contrato de índice.

    HACE PETICIONES DE RED.
    """
```

**El matiz de dato compartido, y qué obliga a mover.** Sí obliga a mover algo
fuera del bucle por ticker de `cli.py`, y el proyecto ya tiene el patrón exacto
resuelto para el benchmark. `cargar_benchmark` se llama una vez antes del bucle
([cli.py:145-155](cli.py#L145-L155)) y el resultado se inyecta por parámetro en
[cli.py:161](cli.py#L161); el comentario de `run_stock_analysis`
([workflow.py:334-337](src/graph/workflow.py#L334-L337)) explica por qué: *«No
se descarga aquí dentro para no repetir la misma petición una vez por ticker:
quien orquesta el lote la hace una sola vez.»* Palabra por palabra el problema
del COT.

Cambios concretos:

- `src/graph/workflow.py`: `cargar_contexto_macro()` hermana de
  `cargar_benchmark` ([workflow.py:350-366](src/graph/workflow.py#L350-L366)),
  con el mismo `try/except` que degrada a `{}` en vez de detenerse; y
  `run_stock_analysis(ticker, benchmark_data=None, macro_data=None)` que lo
  siembra en el estado inicial junto a `benchmark_data`
  ([workflow.py:339-347](src/graph/workflow.py#L339-L347)).
- `cli.py`: una llamada antes del bucle, junto a la del benchmark, y un flag
  `--sin-macro` calcado de `--sin-benchmark`
  ([cli.py:114-117](cli.py#L114-L117)).
- `node_ingest_and_reconcile` **no** toca `futures_data`: lo recibe ya en el
  estado, igual que `benchmark_data`, y solo añade `options_data` a su bloque de
  retorno ([workflow.py:117-132](src/graph/workflow.py#L117-L132)).

Coste: el mapa `SECTOR_A_FUTURO` tiene un puñado de contratos (§4.1), así que
son ~6 descargas por ejecución completa, no por ticker. Hoy el sistema hace 3-4
peticiones *por ticker* en la ingesta.

**Caché, con dos claves distintas porque son dos datos distintos:**

```
data/cache/futuros/{CONTRATO}_{YYYY-MM-DD}.json     # precio del continuo, diario
data/cache/cot/{CODIGO_CFTC}_{YYYY-MM-DD}.json      # UN FICHERO POR INFORME
```

La clave del COT **no es el día de la ejecución, es la fecha del informe** (el
martes al que se refieren los datos). Tres consecuencias, y la tercera es la
que justifica la decisión:

1. Se publica los viernes; entre viernes y viernes toda la ejecución es acierto
   de caché sin trucos.
2. No se reescribe: cada informe es inmutable una vez publicado.
3. **La caché queda, por construcción, ordenada point-in-time.** Ese es el
   activo real: es lo que permite que el backtest reconstruya el bloque macro
   (§7) sin una segunda implementación de la selección histórica.

---

## 4. Reglas de cálculo

Dos módulos de tools nuevos. **Por qué dos y no uno**, con la misma vara con la
que el proyecto decide: `src/tools/` se divide por familia de análisis, no por
tamaño (`fundamentales.py` tiene dos tools, `debate.py` tres). El criterio que
decide aquí es que las dos familias tienen **entradas disjuntas, modos de fallo
disjuntos y — sobre todo — backtestabilidad disjunta**: el bloque macro es
reconstruible point-in-time y el de opciones no (§7). Esa asimetría tiene que
verse en el grafo de imports, que es exactamente la propiedad que
`extraccion.py` defiende en su encabezado
([extraccion.py:1-15](src/tools/extraccion.py#L1-L15)): *«mirando los imports de
un agente se sabe si puede o no hacer una petición»*. Fundirlas en
`posicionamiento.py` escondería la única distinción que el diseño necesita
mantener visible.

```
src/tools/futuros.py    z-score COT, sesgo macro, mapeo sector→contrato
src/tools/opciones.py   put/call, niveles de OI, max pain, gamma, skew
```

Ambos con el patrón de dos capas de todo `src/tools/`: implementación interna
(`_zscore_cot`, `_gex`, …) y fachada `@tool` con docstring de API, como
`calcular_altman` / `_altman` ([calidad.py:1074-1087](src/tools/calidad.py#L1074-L1087)).
La conversión en el borde solo hace falta en `opciones.py`: la cadena entra como
lista de diccionarios serializables, pero el cálculo de gamma opera sobre arrays
de NumPy y el resultado debe volver a JSON para caber en un `ToolMessage`.

### 4.1 Bloque macro / futuros

#### Mapeo sector → contrato

Diccionario cerrado en `src/config.py`, modelado sobre
`GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR`
([config.py:450-454](src/config.py#L450-L454)) y con las mismas claves de sector
que `SECTOR_NORMAS` ([config.py:427-440](src/config.py#L427-L440)), que son los
nombres que devuelve yfinance:

```python
# Contrato de futuros cuyo posicionamiento informa sobre cada sector, con el
# SIGNO de la relación. +1: el precio del subyacente al alza es viento a favor
# (una petrolera con el crudo caro). -1: es viento en contra (una aerolínea).
#
# Un sector que NO está aquí no está por decisión, no por olvido: forzar un
# proxy para «Technology» produciría un número donde no hay relación, que es
# peor que declarar NO_APLICABLE. La misma lógica que hace que
# `GATEKEEPER_INDUSTRIAS_SIN_MARGEN` sea una lista corta y explícita.
SECTOR_A_FUTURO = {
    "Energy":             {"contrato": "CL=F", "cot": "CRUDE OIL, LIGHT SWEET", "signo": +1},
    "Basic Materials":    {"contrato": "HG=F", "cot": "COPPER-GRADE #1",        "signo": +1},
    "Utilities":          {"contrato": "NG=F", "cot": "NATURAL GAS",            "signo": +1},
    "Financial Services": {"contrato": "ZN=F", "cot": "10-YEAR NOTE",           "signo": -1},
    "Real Estate":        {"contrato": "ZN=F", "cot": "10-YEAR NOTE",           "signo": -1},
}

# Contrato de índice, aplicable a TODOS los sectores: mide apetito de riesgo
# agregado, no exposición sectorial. Es la única pata del bloque macro que
# nunca es NO_APLICABLE.
FUTURO_INDICE = {"contrato": "ES=F", "cot": "E-MINI S&P 500", "signo": +1}
```

Nota sobre el signo de tipos: para financieras e inmobiliario el contrato es el
bono a 10 años y el signo es **−1** porque el precio del bono se mueve al revés
que el tipo; una posición especulativa larga en bonos (tipos a la baja) es
viento a favor para el inmobiliario y, con matices, viento en contra para el
margen de intereses de un banco. **Aplicar el mismo signo a bancos y REITs es
una simplificación consciente**, del mismo tipo que la ya declarada para
`SECTOR_NORMAS`, y está en §9.

`Technology`, `Communication Services`, `Healthcare`, `Consumer Cyclical`,
`Consumer Defensive` e `Industrials` **no están en el mapa**: no hay un contrato
único cuyo posicionamiento informe sobre el sector entero. Reciben solo la pata
de índice, y su `sesgo_macro` se promedia sobre el único componente disponible
— la misma regla que ya rige las cuatro puntuaciones de calidad (*«se promedian
solo sobre los componentes disponibles; imputar ceros convertiría una ausencia
en un suspenso»*, `CLAUDE.md`).

#### z-score del posicionamiento COT

**Categoría de trader: no comercial (especulador).** Es la elección que Carver
justifica y la que tiene sentido causal: los comerciales cubren producción o
inventario, así que su posición la dicta el negocio, no una opinión; los no
comerciales son el flujo direccional marginal y su posicionamiento revierte a
la media. Se reporta la posición comercial en el informe, pero no entra en el
número.

```
neta_t   = (largos_no_comerciales_t − cortos_no_comerciales_t) / interes_abierto_total_t
z_t      = (neta_t − media(neta, N)) / desviacion_tipica(neta, N)          N = COT_VENTANA_SEMANAS (156)
```

**La normalización por interés abierto no es cosmética.** El número bruto de
contratos crece secularmente con el tamaño del mercado; un z-score sobre la
serie sin normalizar mide, en parte, el crecimiento del mercado de futuros. Es
el mismo error de categoría que leer un histograma MACD sin normalizar por ATR,
que `evaluar_macd` ya corrige ([tecnico.py:244-264](src/tools/tecnico.py#L244-L264)).

Con menos de `COT_MINIMO_SEMANAS` (52) observaciones, `z = None`. Una desviación
típica calculada sobre veinte semanas no es una medida de extremo.

#### De z-score a sesgo direccional

El z-score tiene dos lecturas que se contradicen y hay que separarlas
explícitamente, porque fundirlas es el error clásico:

- **Moderado** → confirmación de tendencia. Los especuladores acompañan el
  movimiento.
- **Extremo** → posicionamiento hacinado. Sinclair y Carver coinciden en que lo
  que importa es la desviación respecto al propio histórico, y en que un
  extremo es una advertencia contraria.

La resolución no invierte el signo (invertirlo con |z|>2 produce un
clasificador no monótono, que es la patología nº 2 que el propio proyecto
documenta en [technical.py:23-27](src/agents/technical.py#L23-L27)). En su
lugar:

```python
sesgo_bruto = signo_sector * tanh(z / COT_ESCALA)          # COT_ESCALA = 1.5 → sesgo ∈ (-1, +1), monótono en z
extremo     = abs(z) >= COT_Z_EXTREMO                      # COT_Z_EXTREMO = 2.0
```

`extremo` **no cambia el signo**: prohíbe `PERSEGUIR` y recorta la confianza
(§4.3). Direccionalidad y sobreextensión son dos cosas distintas, exactamente
como en el bloque RSI, que puntúa dirección y penaliza el exceso de forma
proporcional y separada ([tecnico.py:102-149](src/tools/tecnico.py#L102-L149)).

Agregación de las patas disponibles (índice, y sector si existe):

```python
sesgo_macro = media([s for s in (sesgo_indice, sesgo_sector) if s is not None])   # None si la lista está vacía
```

Clasificación, con cortes en `config.py` al estilo de `MOMENTUM_*`
([config.py:551-555](src/config.py#L551-L555)) y por el mismo mecanismo que
`_etiqueta` ([tecnico.py:198-214](src/tools/tecnico.py#L198-L214)) — cortes
sobre un número continuo, monótonos por construcción, nunca una escalera de
condicionales:

| `sesgo_macro` | Etiqueta |
|---|---|
| ≥ +0.45 | `VIENTO_A_FAVOR_FUERTE` |
| ≥ +0.15 | `VIENTO_A_FAVOR` |
| ≤ −0.45 | `VIENTO_EN_CONTRA_FUERTE` |
| ≤ −0.15 | `VIENTO_EN_CONTRA` |
| resto | `NEUTRO` |
| `None` | `NO_APLICABLE` |

#### Tools de `src/tools/futuros.py`

```python
@tool("resolver_contrato_sectorial")   # sector → contrato + signo, o NO_APLICABLE
@tool("calcular_zscore_cot")           # serie semanal → z, media, sigma, n_semanas, extremo
@tool("clasificar_sesgo_macro")        # z's disponibles + signos → sesgo_macro + etiqueta
```

### 4.2 Bloque de opciones sobre el propio ticker

Todo lo de esta sección se calcula sobre `options_data`; el agente no toca la
red, igual que `NewsAnalystAgent` ([news.py:33-38](src/agents/news.py#L33-L38)).

#### Put/Call ratio y su percentil

```
pcr_oi  = Σ OI_puts / Σ OI_calls          (vencimientos ≤ OPCIONES_VENTANA_DIAS)
pcr_vol = Σ vol_puts / Σ vol_calls
```

El **nivel absoluto no dice nada** — un PCR de 0.8 es alto en un valor y bajo
en otro. Lo que se usa es el percentil frente a su propio histórico, el mismo
criterio de Sinclair que rige el z-score del COT:

```
pct_pcr = percentil(pcr_oi_hoy, [pcr_oi de los días en caché])
```

Lectura contraria: percentil alto (mucha put respecto a call frente a lo
habitual) = miedo = apoyo contrario alcista; percentil bajo = complacencia.

**Y aquí está el hueco honesto de este bloque.** yfinance publica la cadena de
*hoy*, no su historia. El percentil se calcula sobre la caché acumulativa de
§3.1, así que **una instalación nueva no puede calcularlo durante meses**. Por
debajo de `OPCIONES_MINIMO_DIAS_HISTORICO` (60 observaciones):
`pct_pcr = None` y el subbloque se declara `DATOS_INSUFICIENTES`, **no 0.5**.
Un 0.5 sería exactamente el defecto que `COBERTURA_MINIMA_ESTILO`
([config.py:411](src/config.py#L411)) evita en el clasificador de estilo: *«una
clasificación apoyada en dos de doce métricas es peor que ninguna»*. Está en §9.

#### Niveles de open interest y max pain

```
soporte_oi     = argmax_{K < S}  OI_put(K)
resistencia_oi = argmin... → argmax_{K > S} OI_call(K)
```

Restringidos a strikes con `OI ≥ OPCIONES_OI_MINIMO_STRIKE` para no elegir un
strike con doce contratos.

Max pain (McMillan), el strike que minimiza el valor intrínseco agregado de lo
que está vivo al vencimiento:

```
dolor(K) = Σ_calls OI_c · max(0, K − K_c) · mult  +  Σ_puts OI_p · max(0, K_p − K) · mult
max_pain = argmin_K dolor(K)
```

Sobre el vencimiento más cercano con OI suficiente. **Su fuerza gravitatoria es
función de la proximidad al vencimiento**, así que el peso con que entra en la
elección de nivel decae linealmente hasta cero en
`OPCIONES_MAXPAIN_DIAS_MAXIMO` (21 sesiones). Un max pain a noventa días es
aritmética, no una fuerza.

#### Exposición gamma agregada y punto de inflexión

Gamma de Black-Scholes en forma cerrada (Hull), no aproximada:

```
d1 = [ ln(S/K) + (r − q + σ²/2)·T ] / (σ·√T)
Γ  = φ(d1) / (S · σ · √T)                       φ = densidad normal estándar
Δ_call = e^(−qT)·N(d1)          Δ_put = −e^(−qT)·N(−d1)
```

`σ` es la volatilidad implícita publicada por contrato; sin ella no hay Γ y el
subbloque es `NO_APLICABLE`. `r` de `TIPO_LIBRE_RIESGO` en `config.py`, `q = 0`
declarado.

Exposición gamma agregada de los creadores de mercado, en dólares de delta por
cada 1% de movimiento del subyacente:

```
GEX(S) = Σ_calls Γ_c(S)·OI_c·mult·S²·0.01  −  Σ_puts Γ_p(S)·OI_p·mult·S²·0.01
```

**El signo de esta expresión es una CONVENCIÓN, no una medición**, y es el
eslabón más débil del diseño. Asume que los creadores de mercado están largos
gamma en las calls y cortos en las puts (el cliente compra protección y vende
calls cubiertas). Es la convención estándar del sector, pero no es observable
con datos públicos: la cadena da OI, no quién está en cada lado. Se declara en
el informe con esas palabras y está en §9.

Punto de inflexión (*gamma flip*): el nivel `S*` donde `GEX(S*) = 0`.

```python
def _gamma_flip(cadena, S0, r, rango=0.20, pasos=201):
    """
    Barrido de GEX(S) sobre [S0·(1−rango), S0·(1+rango)] y bisección sobre el
    cambio de signo MÁS CERCANO a S0.

    Devuelve None si no hay cambio de signo en el rango — que es una respuesta
    legítima y frecuente, no un fallo: significa que los creadores de mercado
    están del mismo lado en todo el rango relevante.
    """
```

Interpretación, que es lo que hace que este bloque valga la pena y no sea otro
indicador más:

- **GEX > 0** (dealers largos gamma) → sus coberturas amortiguan el movimiento,
  el precio tiende a clavarse cerca de los strikes de mayor OI. Un retroceso
  hacia `soporte_oi` / `max_pain` es *probable que se rellene*. → **exigir el
  retroceso está justificado**.
- **GEX < 0** (dealers cortos gamma) → sus coberturas aceleran el movimiento en
  la dirección de la tendencia. Un retroceso puede no llegar nunca, y el riesgo
  de un movimiento violento es mayor. → **esperar es caro; se favorece
  `ESCALONAR` en vez de `ESPERAR_RETROCESO`**.

Eso es lo que los futuros solos no dan: el COT dice hacia dónde sopla el viento,
la GEX dice si el precio va a volver a pasar por donde quieres comprarlo.

#### Percentil del skew

Risk reversal de 25 deltas (Natenberg), con el delta calculado por la fórmula
cerrada de arriba y no por moneyness:

```
skew_25d = IV(put con Δ ≈ −0.25) − IV(call con Δ ≈ +0.25)
pct_skew = percentil(skew_25d, histórico en caché)
```

Percentil alto = demanda de cobertura inusualmente cara = miedo. **Una lectura
aislada no basta**: entra solo como filtro de sobreextensión y corroboración,
con la misma disciplina que el veto de insolvencia de Altman, que exige
corroboración de caja antes de disparar (`CLAUDE.md`, y el caso DOCN que lo
motivó). Mismo problema de histórico que el PCR, misma respuesta: `None` por
debajo del mínimo.

#### Agregación del sesgo de opciones

```python
componentes = []
if pct_pcr  is not None: componentes.append(+(2*pct_pcr  − 1) * PESO_PCR)    # contrario: miedo → alcista
if pct_skew is not None: componentes.append(+(2*pct_skew − 1) * PESO_SKEW)   # contrario, mismo signo
if gex_total is not None: componentes.append(signo(gex_total) * PESO_GEX * ... )
sesgo_opciones = sum(componentes) / sum(pesos_disponibles)  if componentes else None
```

Pesos en `config.py` sumando 1 sobre los componentes disponibles, misma
mecánica que `PESOS_CONVICCION` ([config.py:393-398](src/config.py#L393-L398))
y que los cinco bloques de momentum ([tecnico.py:33-37](src/tools/tecnico.py#L33-L37)).

#### Tools de `src/tools/opciones.py`

```python
@tool("calcular_put_call_ratio")     # cadena + histórico → pcr_oi, pcr_vol, percentiles (o None)
@tool("identificar_niveles_oi")      # cadena + precio → soporte_oi, resistencia_oi, OI por strike
@tool("calcular_max_pain")           # cadena → max_pain, dolor(K), días a vencimiento, peso
@tool("calcular_gamma_exposure")     # cadena + precio + r → GEX total, por strike, convención declarada
@tool("localizar_gamma_flip")        # cadena + precio → S* o None
@tool("calcular_skew_percentil")     # cadena + histórico → skew_25d, percentil (o None)
@tool("clasificar_sesgo_opciones")   # los anteriores → sesgo_opciones + etiqueta
```

### 4.3 Combinación final — de dos sesgos y un nivel a un precio de entrada

Esta es la pieza que hay que fijar con precisión, porque es donde el diseño se
gana o se pierde.

#### Paso 1 — Confluencia de tres vías

```python
componentes = {
    "macro":    sesgo_macro,                       # de §4.1, o None
    "opciones": sesgo_opciones,                    # de §4.2, o None
    "tecnico":  momentum_score / 100.0,            # technical_report["momentum_score"] ∈ [-100, +100]
}
disponibles = {k: v for k, v in componentes.items() if v is not None}
```

`tecnico` está siempre disponible en esta rama del grafo (§1). Si `disponibles`
tiene un solo elemento, no hay confluencia que medir y el resultado es
`NO_APLICABLE` con `ajuste_entrada_pct = None`: **una sola señal no es una
comparación de tres vías, y fingir que lo es sería el defecto que este diseño
existe para evitar.**

```python
s_medio     = mean(disponibles.values())
concordes   = [v for v in disponibles.values()
               if signo(v) == signo(s_medio) and abs(v) >= UMBRAL_SENAL]     # UMBRAL_SENAL = 0.15
confluencia = len(concordes) / len(disponibles)
```

#### Paso 2 — Banderas de sobreextensión

Ninguna cambia el signo; todas prohíben perseguir el precio. Es el mismo
principio que rige `aplicar_vetos`, cuyo encabezado lo dice literalmente: *«Los
vetos SOLO bajan»* ([decision.py:18-22](src/tools/decision.py#L18-L22)).

```python
sobreextendido = (technical_report["sobreextendido"]        # RSI extremo o >35% sobre SMA200
                  or cot["extremo"]                          # |z| ≥ 2: posicionamiento hacinado
                  or (pct_pcr is not None and pct_pcr <= OPCIONES_PCT_COMPLACENCIA))   # 0.10
```

#### Paso 3 — Clasificación de la entrada

```python
if len(disponibles) < 2 or s_medio <= 0:
    clasificacion = "NO_APLICABLE"          # sin comparación, o sin sesgo alcista que perseguir
elif confluencia == 1.0 and not sobreextendido:
    clasificacion = "PERSEGUIR"             # las tres confirman y nada está estirado
elif confluencia >= 0.5:
    clasificacion = "ESCALONAR"             # acuerdo parcial, o acuerdo total con sobreextensión
else:
    clasificacion = "ESPERAR_RETROCESO"     # divergencia
```

Cobertura explícita de los dos casos de divergencia que la petición pide
resolver:

- **Divergencia con `momentum_classification`.** El momentum es uno de los tres
  componentes, así que su discrepancia baja `confluencia` por el mismo
  mecanismo que cualquier otra. Ejemplo: momentum `ALCISTA_FUERTE` (+0.6) con
  `sesgo_macro` `VIENTO_EN_CONTRA` (−0.3) y `sesgo_opciones` neutro (+0.05) →
  `s_medio ≈ +0.12`, un solo componente concorde de tres → `confluencia = 0.33`
  → `ESPERAR_RETROCESO`. El sistema no renuncia a la compra: exige un mejor
  precio para una tesis en la que solo el precio propio confirma.
- **Divergencia entre los dos bloques nuevos.** Idéntico tratamiento, sin regla
  especial. Que macro y opciones se contradigan no es un caso patológico, es la
  situación normal cuando el sector va bien y la cadena del valor está
  complaciente, y merece exactamente la misma respuesta: entrar más abajo.

#### Paso 4 — Elección del nivel

```python
candidatos = []
if soporte_oi is not None and soporte_oi < precio:  candidatos.append(("SOPORTE_OI", soporte_oi))
if gamma_flip is not None and gamma_flip < precio:  candidatos.append(("GAMMA_FLIP", gamma_flip))
if max_pain is not None and max_pain < precio and dias_venc <= OPCIONES_MAXPAIN_DIAS_MAXIMO:
    candidatos.append(("MAX_PAIN", max_pain))

nivel_origen, nivel_referencia = max(candidatos, key=lambda c: c[1]) if candidatos else ("NO_APLICABLE", None)
```

**Se elige el más ALTO de los candidatos por debajo del precio**: es el
retroceso más cercano y por tanto el más probable de que se rellene. Tomar el
más bajo sería esperar un desplome, no un retroceso. Y **exigir que esté por
debajo del precio es lo que hace estructuralmente imposible que este agente
suba el precio de entrada** (paso 5).

Si no hay ningún candidato de opciones —el caso del backtest, y de cualquier
valor sin cadena líquida— cabe un repliegue técnico declarado
(`REPLIEGUE_TECNICO`: `bb_lower` o `sma_50`, ya presentes en el informe del
técnico). **Ese repliegue es la pieza que decide si el backtest puede medir
algo, y por eso se discute en §7, no aquí.** En v1 queda apagado.

#### Paso 5 — El ajuste

```python
factor = {"PERSEGUIR": 0.0, "ESCALONAR": 0.5, "ESPERAR_RETROCESO": 1.0}[clasificacion]

if nivel_referencia is None or clasificacion == "NO_APLICABLE":
    ajuste_entrada_pct     = None
    precio_entrada_objetivo = None
else:
    bruto  = (nivel_referencia - precio) / precio                    # ≤ 0 por construcción (paso 4)
    tope   = -AJUSTE_MAXIMO_ATR * (atr / precio)                     # AJUSTE_MAXIMO_ATR = 1.0
    ajuste_entrada_pct      = max(tope, factor * bruto)              # más negativo de los dos ⇒ el tope manda
    precio_entrada_objetivo = round(precio * (1 + ajuste_entrada_pct), 2)
```

Dos propiedades que quiero destacar porque son las que hacen esto seguro:

1. **`ajuste_entrada_pct ≤ 0` siempre.** Aunque las tres señales sean
   eufóricamente alcistas, el sistema no paga por encima del mercado: entra a
   mercado y punto. Es el análogo exacto de *«ninguna condición puede mejorar un
   rating»*, protegido por el producto cartesiano de
   `test_los_vetos_solo_bajan_el_rating`
   ([test_tools.py:195-214](tests/test_tools.py#L195-L214)), y merece un test
   con la misma forma (§8).
2. **El tope está en unidades de ATR, no en un porcentaje fijo.** Un ajuste más
   profundo que el stop produciría una entrada objetivo por debajo del propio
   stop, que es incoherente. El stop se fija en `mult_stop · ATR` según estilo
   ([config.py:514-527](src/config.py#L514-L527), aplicado en
   [decision.py:395](src/tools/decision.py#L395)), con `mult_stop ∈ [1.5, 2.5]`;
   acotar el ajuste en 1·ATR lo deja siempre estrictamente por encima. El agente
   no puede leer `distancia_stop_pct` porque la calcula el Fund Manager
   *después* ([fund_manager.py:145-151](src/agents/fund_manager.py#L145-L151)),
   pero sí tiene el ATR, y con él la cota es dimensionalmente correcta y
   neutral respecto al estilo.

#### Tool de combinación

```python
@tool("ajustar_precio_entrada")
def ajustar_precio_entrada(precio: float, atr: float,
                           sesgo_macro: Optional[float],
                           sesgo_opciones: Optional[float],
                           momentum_score: Optional[float],
                           soporte_oi: Optional[float],
                           max_pain: Optional[float],
                           gamma_flip: Optional[float],
                           dias_a_vencimiento: Optional[int],
                           sobreextendido: bool) -> Dict[str, Any]:
    """Precio de entrada objetivo a partir de la confluencia de tres señales.

    Cruza el sesgo macro de posicionamiento en futuros, el sesgo de
    posicionamiento en la cadena de opciones y el momentum propio del valor. Si
    los tres confirman y nada está sobreextendido, se entra a mercado
    (`ajuste = 0.0`). Si divergen, se exige un retroceso hasta el nivel de
    referencia que marque el open interest, el max pain o el punto de inflexión
    de la exposición gamma.

    El ajuste SOLO puede bajar el precio de entrada, nunca subirlo, y está
    acotado a un ATR: un ajuste más profundo dejaría la entrada objetivo por
    debajo del propio stop.

    Devuelve `ajuste_entrada_pct = None` —no 0.0— cuando no hay dos componentes
    disponibles o no hay ningún nivel por debajo del precio. `0.0` significa
    «entrar a mercado por confluencia», que es una lectura distinta.

    VARIABLE DE DECISIÓN: candidata a EXCLUIR de `TOOLS_LECTURA`. Ver §6.
    """
```

---

## 5. Punto de integración con `decision.py` / `fund_manager.py`

### Dónde entra hoy `current_price` sin ajuste

En [fund_manager.py:105](src/agents/fund_manager.py#L105) se lee del bloque
técnico bruto y de ahí alimenta, sin ninguna modificación, las tres tools que
producen los niveles y el tamaño:

```python
current_price = raw_tech.get("close", 0.0) or 0.0                     # :105
...
niveles = self.usar_tool("calcular_niveles_riesgo", {                  # :145-147
    "precio": current_price, "atr": atr, "estilo": estilo}, traza)
...
riesgo = self.usar_tool("calcular_perfil_riesgo", {                    # :162-165
    "precio": current_price, "stop": stop_loss, "objetivo": take_profit, ...}, traza)
```

Y dentro de la tool, `calcular_niveles_riesgo` deriva stop, objetivo y distancia
al stop de ese precio ([decision.py:394-403](src/tools/decision.py#L394-L403)),
que a su vez es lo que dimensiona la posición
([decision.py:172-175](src/tools/decision.py#L172-L175)).

### El cambio

**`calcular_niveles_riesgo` no cambia de firma.** Ya recibe `precio`; lo que
cambia es *qué precio se le pasa*. Esa es toda la integración:

```python
# --- Precio de referencia para los niveles ---------------------------------
# El stop y el objetivo se miden desde el precio que se espera PAGAR, no desde
# el último cruce del mercado. Medirlos desde un precio al que no se ha entrado
# produce un ratio riesgo/recompensa que describe una operación que nadie hizo.
pos = state.get("positioning_report", {}) or {}
precio_entrada = pos.get("precio_entrada_objetivo")
if precio_entrada is None:                      # `is None`, NO `or`: 0.0 es un
    precio_entrada = current_price              # precio inválido, no una ausencia

niveles = self.usar_tool("calcular_niveles_riesgo", {
    "precio": precio_entrada, "atr": atr, "estilo": estilo}, traza)
...
riesgo = self.usar_tool("calcular_perfil_riesgo", {
    "precio": precio_entrada, "stop": stop_loss, "objetivo": take_profit, ...}, traza)
```

El `is None` explícito no es pedantería: `pos.get(...) or current_price` con un
`ajuste_entrada_pct` de `0.0` funcionaría por accidente, pero con
`precio_entrada_objetivo = 0.0` (dato corrupto) enmascararía el error. Es la
misma clase de defecto que el proyecto ya corrigió en
[fund_manager.py:192-197](src/agents/fund_manager.py#L192-L197), donde
comprobar solo `current_price` dejaba pasar un `nan`.

Efecto colateral que hay que declarar, no esconder: al bajar el precio de
referencia, `distancia_stop_pct = mult_stop·ATR / precio_entrada` **sube
ligeramente**, y por tanto `peso_objetivo` baja
([decision.py:174](src/tools/decision.py#L174)). Es correcto —una entrada más
baja con el mismo ATR arriesga una fracción mayor del capital comprometido— pero
significa que **este agente mueve `position_size_pct`**, y eso es lo que lo
convierte en capa de decisión y no en capa asesora. §7 se ocupa de las
consecuencias.

El informe conserva **los dos** precios: `current_price` (el de mercado, como
hoy) y `precio_entrada_objetivo`. Sin ambos, el lector del informe no puede
saber si el stop está donde está por el ATR o por el ajuste.

### Veto macro en `aplicar_vetos` — el añadido que sí es backtesteable

Un viento macro fuertemente en contra debe poder recortar el dictamen, no solo
el precio. Encaja sin fricción en la tool que ya existe, respetando su regla:

```python
@tool("aplicar_vetos")
def aplicar_vetos(rating_bruto: str, estilo: str, banderas_rojas: List[str],
                  sobreextendido: bool, confianza_datos: float,
                  conviccion_evaluable: bool = True,
                  sesgo_macro_clasificacion: Optional[str] = None) -> Dict[str, Any]:
    ...
    if sesgo_macro_clasificacion == "VIENTO_EN_CONTRA_FUERTE":
        rating = _tope(rating, "COMPRA")
        vetos.append("Posicionamiento de futuros fuertemente en contra del sector: "
                     "el dictamen no puede superar COMPRA")
```

**El parámetro va al final y con valor por defecto `None`.** Es obligatorio:
`test_los_vetos_solo_bajan_el_rating`
([test_tools.py:208-211](tests/test_tools.py#L208-L211)) invoca la tool sin él,
y un parámetro requerido rompería la suite. Con el defecto, la tool sigue
comportándose exactamente igual cuando no hay dato macro — que es el caso del
estado sintético y de cualquier sector fuera del mapa.

---

## 6. Invariante LLM-neutral

### Lo que ya se cumple por construcción

El agente hereda de `AgenteBase`, así que el orden lo impone la clase, no el
agente: `analyze()` llama a `decidir()` y solo después a `_redactar()`
([base.py:141-142](src/agents/base.py#L141-L142)), y `_redactar()` únicamente
escribe `self.campo_texto` ([base.py:182-233](src/agents/base.py#L182-L233)).
`campo_texto = "summary"`, como en cinco de los seis agentes.

El plan de llamadas lo escribe el código: el agente invoca sus ~9 tools por
nombre con `usar_tool()` ([base.py:309-362](src/agents/base.py#L309-L362)) en un
orden fijo. La forma es la de un ReAct, la sustancia la de una función pura.

Y `_obtener_llm()` resuelve `get_llm` en el módulo de la subclase
([base.py:162-179](src/agents/base.py#L162-L179)), así que el agente nuevo debe
importar `get_llm` en su propio módulo con el `# noqa: F401` de rigor, como
[technical.py:41](src/agents/technical.py#L41). Sin ese import, `disable_llm()`
no lo alcanza y el backtest abriría llamadas de red.

### `TOOLS_LECTURA` — qué se excluye y por qué

En [tools/__init__.py:61-65](src/tools/__init__.py#L61-L65):

```python
TOOLS_LECTURA: List[BaseTool] = (
    TOOLS_EXTRACCION_LECTURA + TOOLS_FUNDAMENTALES + TOOLS_CALIDAD
    + TOOLS_TECNICO + TOOLS_NOTICIAS + TOOLS_DEBATE
    + [t for t in TOOLS_CARTERA if t.name == "calcular_correlaciones"]
    + [t for t in TOOLS_FUTUROS + TOOLS_OPCIONES
       if t.name != "ajustar_precio_entrada"]          # ← la única exclusión
)
```

| Tool | ¿En `TOOLS_LECTURA`? | Motivo |
|---|---|---|
| `ajustar_precio_entrada` | **NO** | Produce `precio_entrada_objetivo`, que alimenta `calcular_niveles_riesgo`. Es variable de decisión. |
| `calcular_zscore_cot`, `clasificar_sesgo_macro`, `resolver_contrato_sectorial` | Sí | Explican, no deciden. El veto macro vive dentro de `aplicar_vetos`, que ya está excluida. |
| `calcular_put_call_ratio`, `identificar_niveles_oi`, `calcular_max_pain`, `calcular_gamma_exposure`, `localizar_gamma_flip`, `calcular_skew_percentil`, `clasificar_sesgo_opciones` | Sí | Mismo estatus que `calcular_altman`: son el material con el que el investigador explica un dictamen sorprendente. |
| `obtener_cadena_opciones` | Sí | Barata, yfinance, y es justo lo que el investigador necesita para responder «¿por qué la entrada objetivo está un 3% por debajo?». |
| `obtener_contexto_macro` | **NO** | Descarga el fichero de la CFTC, que es grande y lento. Mismo criterio que excluye `obtener_noticias` ([tools/__init__.py:22-23](src/tools/__init__.py#L22-L23)): *«la fuente más lenta y la que más cuota consume»*. |

En `tests/test_tools.py`, `TOOLS_DE_DECISION`
([test_tools.py:32-40](tests/test_tools.py#L32-L40)) suma
`"ajustar_precio_entrada"`, y `TOOLS_DE_RED`
([test_tools.py:43-46](tests/test_tools.py#L43-L46)) suma
`"obtener_cadena_opciones"` y `"obtener_contexto_macro"`. Con eso,
`test_el_react_no_alcanza_ninguna_tool_de_decision` y
`test_las_tools_de_red_estan_donde_deben` cubren lo nuevo sin escribir un test
adicional.

### `assert_llm_is_decision_neutral()`

Tres cambios en [replay.py](src/backtest/replay.py):

1. **`disable_llm()`** ([replay.py:131-132](src/backtest/replay.py#L131-L132)):
   añadir `posicionamiento_mod` a la tupla. Por el mismo motivo por el que
   `news_mod` está ahí aunque el replay no lo ejecute.
2. **`modulos`** ([replay.py:171](src/backtest/replay.py#L171)): añadirlo, para
   que el doble de LLM lo alcance.
3. **`_run()`** ([replay.py:194-223](src/backtest/replay.py#L194-L223)):
   ejecutar el agente entre técnico y debate, y añadir al diccionario comparado:

```python
"posicionamiento_sesgo_macro":        pr.get("sesgo_macro"),
"posicionamiento_sesgo_opciones":     pr.get("sesgo_opciones"),
"posicionamiento_clasificacion":      pr.get("entrada_clasificacion"),
"posicionamiento_nivel":              pr.get("nivel_referencia"),
"posicionamiento_nivel_origen":       pr.get("nivel_origen"),
"posicionamiento_ajuste_pct":         pr.get("ajuste_entrada_pct"),
"posicionamiento_precio_entrada":     pr.get("precio_entrada_objetivo"),
"posicionamiento_confluencia":        pr.get("confluencia"),
```

`stop_loss_atr`, `take_profit_atr`, `position_size_pct` y `peso_objetivo` ya
están en la comparación, así que en cuanto el precio de entrada los mueva, los
cubre sin tocar nada.

4. **`_synthetic_state()`** ([replay.py:242-331](src/backtest/replay.py#L242-L331)):
   añadir `futures_data` y `options_data` sintéticos **con fechas fijas**, por
   la misma razón que el dosier de noticias las lleva fijas
   ([replay.py:309-313](src/backtest/replay.py#L309-L313)): si la antigüedad o
   el percentil dependieran del día de ejecución, la verificación dejaría de ser
   reproducible.

---

## 7. Viabilidad point-in-time y backtest

### Respuesta: **PARCIAL, y con una asimetría que decide el alcance de la v1.**

| Bloque | ¿Reconstruible point-in-time? | Por qué |
|---|---|---|
| Macro / COT | **Sí** | La CFTC publica el archivo histórico completo (ficheros anuales, desde 1986) con la fecha del informe **y** la fecha de publicación. |
| Futuro continuo | **Sí** | yfinance sirve el histórico de `CL=F`, `ES=F`, etc. Mismo `PriceStore` que ya existe. |
| Cadena de opciones | **No** | yfinance publica la cadena de *hoy*. El histórico de OI y volatilidad implícita es de pago (OptionMetrics/IvyDB, CBOE DataShop, ORATS). Sin él no hay PCR histórico, ni max pain, ni GEX, ni skew a fecha `t`. |

### El COT tiene el mismo problema `filed` vs `end` que el XBRL

Y es exactamente el mismo, no uno parecido. El informe COT del martes
2024-03-05 **no es público hasta el viernes 2024-03-08 a las 15:30 ET**.
Filtrar por la fecha del informe en un backtest permite operar el miércoles con
datos que nadie tenía, que es palabra por palabra la fuga que
[data.py:13-21](src/backtest/data.py#L13-L21) documenta para los hechos XBRL:
*«El periodo fiscal que termina el 31-dic-2023 no es público hasta que se
presenta el 10-K, típicamente en feb-2024. Usar `end` en un backtest permite
operar en enero con cifras que nadie conocía.»*

Correspondencia exacta:

| XBRL | COT |
|---|---|
| `end` (cierre del periodo) | fecha del informe (martes) |
| `filed` (presentación) | fecha de publicación (viernes 15:30 ET) |
| `MIN_REPORTING_LAG_DAYS = 45` ([data.py:45](src/backtest/data.py#L45)) | retardo de 3 días naturales, conocido y fijo |
| `_annual(facts, as_of)` filtra `f.filed <= as_of` ([data.py:398-402](src/backtest/data.py#L398-L402)) | `COTStore._serie(codigo, as_of)` filtra `publicado <= as_of` |

Un `COTStore` en `src/backtest/data.py`, hermano de `FundamentalStore`, con
caché en `data/cache/cot/` — la misma que usa producción (§3.2), porque la clave
es la fecha del informe y por tanto es point-in-time por construcción. **Una
sola implementación de la selección histórica**, que es la propiedad que
`CLAUDE.md` defiende al justificar el parámetro `as_of` de `_serie_de_hechos()`.

### La consecuencia incómoda, que es la que decide el diseño

**El bloque macro solo produce dirección. El nivel de precio sale únicamente de
las opciones.** (§4.3, paso 4.) Por tanto, en un backtest sin cadena de
opciones:

```
soporte_oi = max_pain = gamma_flip = None  →  candidatos = []  →  nivel_referencia = None
→ ajuste_entrada_pct = None  →  precio_entrada = current_price  →  decisión idéntica a la de hoy
```

Es decir: **con el bloque de opciones ausente, el backtest no mide absolutamente
nada de esta capa.** No es que la mida mal; es que reproduce exactamente el
comportamiento actual. Y como el bloque *sí* mueve `position_size_pct` en
producción (§5), tendríamos una variable de decisión viva en directo e
inmedible en el estudio. Eso es precisamente lo que `CLAUDE.md` prohíbe para las
noticias: *«si conectas las noticias a la decisión, ese test debe fallar y el
backtest deja de ser válido hasta que exista un `NewsStore` point-in-time.»*

### Lo que se decidió y lo que implica

**Se construyó la capa de decisión completa.** `precio_entrada_objetivo`
sustituye a `current_price` en `calcular_niveles_riesgo` y en
`calcular_perfil_riesgo`, y `sesgo_macro_clasificacion` habilita un veto que
solo baja. La recomendación de la versión previa de esta sección —dejar el
bloque de opciones como capa asesora hasta disponer de un almacén
point-in-time— **no se siguió**, y esa es una decisión legítima del autor del
proyecto que este documento registra sin suavizar.

Lo que hay que tener presente a partir de ahora:

- **El backtest publicado ya no mide la lógica completa que decide en vivo.** En
  el estudio no hay cadena de opciones, luego no hay nivel, luego el ajuste es
  `None` y las entradas se toman al precio de mercado. Lo que el backtest sí
  mide de esta capa es el veto macro, que es point-in-time.
- **Ninguna cifra de rendimiento del informe puede atribuirse al ajuste de
  entrada**, ni a favor ni en contra. No hay evidencia de que mejore el
  resultado; el argumento que lo sostiene es de coherencia (un stop medido desde
  un precio que no se ha pagado describe una operación que nadie hizo), no
  empírico.
- **La vía para cerrar la brecha** sigue siendo la de abajo: un almacén de
  cadenas point-in-time, o aceptar el repliegue técnico declarado como
  definición backtesteable del nivel.
- `test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado` fija que
  la rama sin datos —la del backtest— reproduce exactamente el comportamiento
  anterior. Mientras ese test pase, el estudio sigue siendo interpretable como
  «el sistema sin ajuste de entrada».

### La recomendación original, conservada como registro

Es la única parte del entregable donde propongo algo más estrecho de lo que la
petición sugiere, y quiero ser explícito sobre por qué: no es cautela genérica,
es que la alternativa invalida el resultado publicado del backtest, que
`backtest_cli.py` aborta si la verificación falla y que `CLAUDE.md` declara
tres veces como propiedad que sostiene el proyecto.

**v1 — se construye entero, se reporta entero, y solo entra en la decisión la
mitad medible:**

- **Bloque macro → capa de DECISIÓN.** Vía el veto de §5 (`VIENTO_EN_CONTRA_FUERTE`
  topa en COMPRA). Solo baja, es reconstruible point-in-time con `COTStore`, y
  el replay lo ejecuta. **Medible.**
- **Bloque de opciones → capa ASESORA.** Se calcula, se publica en el informe
  con su nivel y su entrada sugerida, y aporta un argumento al debate. Lleva
  `advisory_only: True` como `news_report`
  ([news.py:173-174](src/agents/news.py#L173-L174)).
  `precio_entrada_objetivo` se emite pero **no** se pasa a
  `calcular_niveles_riesgo`. El cambio de §5 se documenta y se deja preparado,
  sin activar.
- **Test-guardián:** `test_positioning_report_does_not_alter_decision`, copia
  estructural del de noticias
  ([test_news_analyst.py:127-156](tests/test_news_analyst.py#L127-L156)).

**v2 — se activa el ajuste de entrada cuando se cumpla UNA de estas dos:**

1. Existe un `OpcionesStore` point-in-time (datos de pago), o
2. Se acepta el **repliegue técnico declarado** de §4.3 paso 4 como definición
   de `nivel_referencia` para el backtest — `bb_lower` o `sma_50`, ambos ya en
   `technical_report` y ambos reconstruibles. Nótese que esto **no** duplicaría
   una regla de decisión: el repliegue lo define el propio agente y la misma
   rama corre en producción y en replay. Lo que introduce es una *divergencia de
   definición* entre ambos —producción usaría el nivel de OI, el backtest el
   técnico— exactamente del mismo tipo que la divergencia TTM/anual ya declarada
   en `build_limitations()`
   ([backtest_cli.py:131-137](backtest_cli.py#L131-L137)). Precedente hay; lo que
   hace falta es declararla igual de claro.

Cuando se active, `test_positioning_report_does_not_alter_decision` **debe
borrarse, no relajarse**, y el informe debe reejecutarse entero.

### Segundo problema, independiente del anterior: la ejecución del límite

Aunque se resolviera el dato, un precio de entrada objetivo es una **orden
limitada**, y el motor no sabe rellenarlas. Hoy `engine.py` ejecuta al estilo
señal-al-cierre-de-`t`, relleno-en-la-apertura-de-`t+1`. Una entrada limitada
exige una regla nueva: cuántas sesiones se deja viva la orden, qué pasa si el
precio no la toca (no se abre la posición, y eso cambia la exposición agregada)
y si se rellena a la apertura cuando abre por debajo del límite. Es una regla de
*ejecución*, no de decisión, así que sí puede vivir en `engine.py` — pero no
existe y hay que escribirla. Va a `NEXT_STEPS`.

### Qué entra en `build_limitations()`

Añadir a la función de [backtest_cli.py:103](backtest_cli.py#L103):

```python
lims.append(
    "**La capa de posicionamiento en opciones no está en el backtest.** Su bloque macro "
    "(COT de la CFTC) sí se reconstruye point-in-time filtrando por fecha de PUBLICACIÓN "
    "—no por la del informe, que es el mismo error que usar `end` en vez de `filed` en el "
    "XBRL—, pero la cadena de opciones no: yfinance solo publica la de hoy y el histórico "
    "de open interest y volatilidad implícita es de pago. Como el nivel de precio de "
    "entrada sale ÚNICAMENTE de la cadena, en el backtest el ajuste de entrada es siempre "
    "nulo y las operaciones se rellenan al precio de mercado. **El estudio mide por tanto "
    "el sistema SIN ajuste de entrada.** Mientras esa capa siga siendo asesora, esa "
    "ausencia no altera ni una señal; si se conecta a la decisión, este backtest deja de "
    "ser válido hasta que exista un almacén de cadenas point-in-time.")

lims.append(
    "**El percentil del put/call ratio y del skew necesita histórico propio.** Se calculan "
    "sobre la caché acumulativa de cadenas diarias, así que una instalación nueva no puede "
    "emitirlos hasta acumular `OPCIONES_MINIMO_DIAS_HISTORICO` observaciones. Hasta "
    "entonces se declaran DATOS_INSUFICIENTES en vez de asumir el percentil 50.")

lims.append(
    "**El signo de la exposición gamma es una convención, no una medición.** Se asume que "
    "los creadores de mercado están largos gamma en las calls y cortos en las puts. Es la "
    "convención estándar, pero la cadena publica open interest, no quién está en cada lado "
    "de cada contrato. Si esa convención falla en un valor concreto, el punto de inflexión "
    "calculado apunta al lado contrario.")
```

Y a `NEXT_STEPS` ([backtest_cli.py:222](backtest_cli.py#L222)): la regla de
ejecución de órdenes limitadas, y la evaluación de si comprar histórico de
cadenas está justificado por el tamaño del efecto medido en directo.

---

## 8. Tests a añadir

Todos offline y deterministas, con dobles donde toque LLM, siguiendo el estilo
de `tests/test_momentum.py` y `tests/test_news_analyst.py`.

### `tests/test_futuros.py` — bloque macro

| Test | Qué protege |
|---|---|
| `test_el_zscore_normaliza_por_interes_abierto` | Duplicar todos los contratos (largos, cortos y OI) no mueve el z-score. Sin normalizar, el crecimiento secular del mercado se colaría como señal. |
| `test_sin_semanas_suficientes_el_zscore_es_none` | Con menos de `COT_MINIMO_SEMANAS`, `z is None` y no un 0.0 que se leería como «posicionamiento neutro». |
| `test_un_sector_fuera_del_mapa_es_no_aplicable` | `Technology` → `sesgo_macro` solo con la pata de índice; un sector desconocido sin índice → `NO_APLICABLE`, nunca un proxy forzado. |
| `test_el_signo_sectorial_se_aplica` | Mismo z-score del bono con signo −1 produce sesgo de signo opuesto al de un contrato con +1. |
| `test_el_extremo_no_invierte_el_signo` | Con `|z| ≥ COT_Z_EXTREMO` el sesgo conserva su signo y solo se marca `extremo`. Invertirlo produciría un clasificador no monótono — la patología nº 2 de `technical.py`. |
| `test_la_clasificacion_de_sesgo_es_monotona` | Barrido de `sesgo_macro` en `[-1, 1]`: la etiqueta nunca empeora cuando el número sube. Mismo contrato que `test_la_etiqueta_es_monotona_en_la_puntuacion` ([test_momentum.py:89](tests/test_momentum.py#L89)). |

### `tests/test_opciones.py` — bloque de la cadena

| Test | Qué protege |
|---|---|
| `test_gamma_coincide_con_la_forma_cerrada` | Γ calculada por la tool contra el valor de Black-Scholes en un caso con solución conocida. La instrucción es no aproximar donde hay fórmula cerrada. |
| `test_max_pain_sobre_una_cadena_construida_a_mano` | Cadena de tres strikes con OI conocido: el mínimo de `dolor(K)` está donde la aritmética dice. |
| `test_el_gamma_flip_es_none_si_no_hay_cambio_de_signo` | No encontrar el nivel es una respuesta legítima, no un fallo. |
| `test_el_gamma_flip_encuentra_el_cruce_mas_cercano` | Con dos cruces en el rango, se devuelve el más próximo al precio. |
| `test_sin_volatilidad_implicita_no_hay_gex` | Sin `σ` no hay Γ: `NO_APLICABLE`, nunca `gex_total = 0.0`. |
| `test_percentil_sin_historico_suficiente_es_none` | Con menos de `OPCIONES_MINIMO_DIAS_HISTORICO`, `pct_pcr is None` y el subbloque es `DATOS_INSUFICIENTES`. **No 0.5.** |
| `test_los_niveles_de_oi_ignoran_strikes_ilíquidos` | Un strike con OI por debajo del mínimo no puede ser el soporte. |
| `test_el_max_pain_no_entra_lejos_del_vencimiento` | Más allá de `OPCIONES_MAXPAIN_DIAS_MAXIMO` no es candidato a nivel. |

### `tests/test_entrada.py` — la combinación y la integración

| Test | Qué protege |
|---|---|
| `test_el_ajuste_de_entrada_solo_baja_el_precio` | **El test central.** Producto cartesiano de sesgos, niveles, momentum y banderas: `ajuste_entrada_pct <= 0` **siempre**. Misma forma que `test_los_vetos_solo_bajan_el_rating`. |
| `test_el_ajuste_esta_acotado_a_un_atr` | `abs(ajuste) <= AJUSTE_MAXIMO_ATR * atr / precio`, para que la entrada objetivo nunca quede por debajo del stop. |
| `test_confluencia_total_entra_a_mercado` | Tres señales alcistas concordes y nada sobreextendido → `PERSEGUIR` y `ajuste == 0.0`. |
| `test_divergencia_con_el_momentum_exige_retroceso` | Momentum alcista contra macro en contra → `ESPERAR_RETROCESO`. |
| `test_sobreextension_prohibe_perseguir` | Con `sobreextendido=True`, la confluencia total no llega a `PERSEGUIR`. |
| `test_ausencia_total_devuelve_none_no_cero` | Sin macro ni opciones: `ajuste_entrada_pct is None`, `entrada_clasificacion == "NO_APLICABLE"`. **La distinción `None` ≠ `0.0` es la regla nº 1 del proyecto.** |
| `test_un_solo_componente_no_es_confluencia` | Con solo el momentum disponible → `NO_APLICABLE`. |
| `test_positioning_report_does_not_alter_decision` | **Guardián de la v1** (§7). Copia estructural del de noticias. **Debe borrarse, no relajarse, cuando la v2 active el ajuste.** |
| `test_el_veto_macro_solo_baja` | El nuevo parámetro de `aplicar_vetos` no puede subir ningún rating, sobre el mismo producto cartesiano. |
| `test_aplicar_vetos_sin_sesgo_macro_se_comporta_igual` | Compatibilidad: la tool invocada sin el parámetro nuevo da el mismo resultado que antes. |

### Añadidos a suites existentes

| Archivo | Añadido |
|---|---|
| `tests/test_tools.py` | `"ajustar_precio_entrada"` en `TOOLS_DE_DECISION`; `"obtener_cadena_opciones"` y `"obtener_contexto_macro"` en `TOOLS_DE_RED`. Con eso los dos tests de barrera cubren lo nuevo sin escribir ninguno. |
| `tests/test_llm_texto.py` | El agente nuevo en la parametrización: `summary` es `str` con LLM que devuelve bloques, cadena vacía, `None` o excepción. |
| `tests/test_integridad_datos.py` | Cadena ausente → `NO_APLICABLE` en todos los niveles y `None` en todos los números; sector fuera del mapa → `NO_APLICABLE`. Nunca un cero. |
| `tests/test_mensajes.py` | La traza del agente nuevo es reproducible entre dos ejecuciones (ids secuenciales, sin duraciones). |
| `tests/test_backtest.py` | `test_cot_respects_release_date_not_report_date`: un informe del martes no es visible el miércoles. Es el análogo exacto de `test_fundamentals_respect_filed_not_end` y **no debe relajarse para hacer pasar un cambio**. |
| `tests/test_workflow.py` | El nodo aparece entre `technical_analysis` y `debate_unit`, y **no** se ejecuta en la rama de rechazo. (Esta suite golpea la red y no es fiable en CI; el test topológico se puede escribir sobre el grafo compilado sin invocarlo.) |

---

## 9. Supuestos y huecos que requieren validación humana

Ordenados por cuánto pueden invalidar el diseño.

1. **El formato del fichero COT de la CFTC no lo he verificado.** No he
   descargado ninguno. Lo que doy por supuesto: que los ficheros anuales
   (`Legacy Futures Only`) traen la fecha del informe y que la fecha de
   publicación es derivable (viernes siguiente al martes del informe, 15:30 ET),
   y que las columnas de largos/cortos no comerciales e interés abierto están
   ahí con nombres estables entre años. **Los nombres de columna de la CFTC han
   cambiado históricamente entre formatos** (Legacy / Disaggregated / TFF).
   Antes de implementar `cot.py`, descargar dos ficheros de años lejanos y
   comprobar el esquema. Si el retardo de publicación no fuera derivable con
   certeza, aplicar un retardo mínimo declarado como
   `MIN_REPORTING_LAG_DAYS` — el precedente existe
   ([data.py:45](src/backtest/data.py#L45)).

2. **Los códigos de contrato de la tabla `SECTOR_A_FUTURO` son propuestas, no
   verificaciones.** Los símbolos de yfinance (`CL=F`, `ES=F`, `HG=F`, `NG=F`,
   `ZN=F`) y los nombres de mercado de la CFTC no los he comprobado contra las
   fuentes. El emparejamiento símbolo↔código CFTC es manual y hay que hacerlo a
   mano una vez.

3. **El signo para `Financial Services` mezcla dos cosas.** Bancos (margen de
   intereses, se beneficia de tipos altos) y REITs (coste de financiación, se
   beneficia de tipos bajos) no responden igual al mismo contrato. La
   granularidad correcta es la industria, no el sector, igual que ya ocurre con
   `GATEKEEPER_INDUSTRIAS_SIN_MARGEN`. **Decisión humana**: aceptar el sesgo
   declarado, o abrir un `INDUSTRIA_A_FUTURO` que tenga precedencia sobre el
   mapa sectorial.

4. **`Basic Materials` es heterogéneo.** El cobre informa sobre mineras de
   metales industriales y no sobre químicas ni sobre mineras de oro. Misma
   disyuntiva y misma decisión pendiente que el punto anterior.

5. **La convención de signo de la GEX no es verificable con datos públicos**
   (§4.2). Es el supuesto más frágil del bloque de opciones y el que más
   directamente puede invertir una conclusión. Va declarado en el informe y en
   `build_limitations()`, pero conviene una validación empírica: contrastar
   `gamma_flip` contra el comportamiento observado del precio en una muestra de
   valores antes de darle peso en la elección de nivel.

6. **El percentil de PCR y de skew no está disponible al arrancar.** Necesita
   ~60 días de caché acumulada. Durante ese periodo el bloque de opciones
   funciona a medias (niveles de OI, max pain y GEX sí; PCR y skew no).
   **Decisión humana**: arrancar la caché ya, aunque el agente no esté
   implementado, para que el histórico exista cuando lo esté.

7. **`Ticker.option_chain()` de yfinance: cobertura y estabilidad sin
   comprobar.** No sé qué proporción del universo tiene cadena utilizable, ni
   si `impliedVolatility` viene poblada de forma fiable, ni cuántas peticiones
   cuesta (una por vencimiento). Con 5 vencimientos por ticker y 50 tickers son
   250 peticiones extra por ejecución; hay que medir si eso choca con el
   límite de yfinance antes de fijar `OPCIONES_VENTANA_DIAS`.

8. **No hay clave de API nueva en el camino recomendado.** COT es público y
   yfinance ya se usa. Si se decide comprar histórico de cadenas (§7 v2), eso sí
   introduce credencial y coste recurrente, y es una decisión de presupuesto.

9. **Estructura temporal de futuros (contango/backwardation) — descartada de la
   v1 por falta de dato.** El *cost-of-carry* de Hull sería un tercer componente
   macro con contenido real —la backwardation señala escasez física, que es
   viento a favor para un productor con independencia del posicionamiento
   especulativo—, pero exige dos vencimientos consecutivos y yfinance sirve el
   continuo del primer mes. Trabajo futuro, no hueco a validar.

10. **Actividad inusual de opciones (Nations, Cohen) — declarada como trabajo
    futuro, tal y como la petición permite.** El proxy determinista razonable es
    `volumen / open_interest > 1` en strikes OTM, que distingue apertura de
    posición direccional agresiva de actividad de rolado o cobertura. **No entra
    en ningún número en la v1**; a lo sumo se emite como
    `flag_actividad_inusual` en el informe. El motivo de no incluirlo: sin
    distinguir compra agresiva de calls de venta de calls cubiertas, el volumen
    de calls no es una señal alcista, y el proxy por sí solo no hace esa
    distinción — solo indica que *algo* se abrió.

11. **La regla de ejecución de órdenes limitadas no existe** (§7). Es
    prerrequisito de la v2 y es trabajo de `engine.py`, no de los agentes.
