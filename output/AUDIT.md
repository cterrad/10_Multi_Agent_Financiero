# AUDIT.md — Auditoría de la lógica de decisión (Fase 1 del backtest)

Auditoría completa de `src/` previa a la construcción de la capa de backtest.
Documenta **cómo se produce realmente la decisión**, **qué datos la alimentan y
cuáles son conocibles en el pasado**, y **qué defectos aparecieron por el camino**.

Todo lo que sigue se refiere al código tal y como está hoy. No se ha modificado
ni un agente: la capa de backtest es estrictamente de solo lectura.

---

## 1. La función de decisión, como árbol determinista

El grafo compilado (`src/graph/workflow.py:114-146`) es:

```
ingest → gatekeeper → ¿passed? ──sí──→ technical → debate → fund_manager → END
                          └────no──────────────────────────→ fund_manager → END
```

`route_after_gatekeeper` (`workflow.py:66-70`) es la única bifurcación. El
rechazo fundamental cortocircuita el análisis técnico y el debate, lo que ahorra
cómputo pero también significa que **un valor rechazado nunca llega a tener
momentum, ni stop, ni objetivo**.

### 1.1 Gatekeeper fundamental — `src/agents/fundamental.py:29-42`

Tres reglas booleanas en AND sobre `reconciliation_data.reconciled_metrics`:

| Condición de rechazo | Umbral | Origen |
|---|---|---|
| `net_margin < MIN_NET_MARGIN` | 0.03 | `config.py:9` |
| `revenue_growth < MIN_REVENUE_GROWTH` | 0.05 | `config.py:8` |
| `debt_to_equity > MAX_DEBT_TO_EQUITY` | 3.5 | `config.py:10` |

`confidence_score < 0.5` **añade un motivo pero no rechaza** (`fundamental.py:41-42`).

### 1.2 Clasificación de momentum — `src/agents/technical.py:30-75`

Sistema de puntos, sin ponderaciones ni ajustes:

| Señal | Condición | Alcista | Bajista |
|---|---|:---:|:---:|
| RSI | `> 70` | — | +1 |
| RSI | `50 ≤ rsi ≤ 70` | +2 | — |
| RSI | `< 30` | +1 | — |
| MACD | `macd > signal and hist > 0` | +2 | — |
| MACD | `macd < signal` | — | +2 |
| SMA | `close > sma50 > sma200` | +2 | — |
| SMA | `sma50 < sma200` | — | +2 |
| Bollinger | `close ≥ bb_upper` | +1 | — |
| Bollinger | `close ≤ bb_lower` | — | +1 |

Clasificación final (`technical.py:68-75`), evaluada en orden:

```
alcistas ≥ 5                        → ALCISTA_FUERTE
alcistas ≥ 3 y bajistas ≤ 2         → ALCISTA
bajistas ≥ 4                        → BAJISTA
resto                               → NEUTRAL
```

### 1.3 Dictamen final — `src/agents/fund_manager.py:31-65`

```
si NO passed_gatekeeper:
    rating = "VENTA FUERTE"  si net_margin < -0.10
    rating = "VENTA"         en caso contrario
    tamaño = 0.0%  ·  stop = None  ·  objetivo = None
si SÍ passed_gatekeeper:
    momentum == ALCISTA_FUERTE  y  rsi <  70   → COMPRA FUERTE   8.0% – 10.0%
    momentum ∈ {ALCISTA_FUERTE, ALCISTA}       → COMPRA          4.0% –  7.0%
    momentum == NEUTRAL                        → MANTENER        2.0% –  3.0%
    momentum == BAJISTA  y  rsi >  50          → VENTA           0.0%
    resto                                      → VENTA FUERTE    0.0%

    stop_loss   = round(close - 2.0 * ATR, 2)
    take_profit = round(close + 3.5 * ATR, 2)
```

**Ratio riesgo/beneficio implícito: 3.5 / 2.0 = 1.75.** La tasa de acierto de
equilibrio es `1 / (1 + 1.75) = 36.36%`. Es el listón mínimo contra el que hay
que leer cualquier hit rate del informe.

Interacción no evidente que merece registro: se puede alcanzar `ALCISTA_FUERTE`
con RSI > 70 (MACD +2, estructura SMA +2, ruptura de Bollinger +1 = 5 alcistas).
En ese caso la guarda `rsi < 70` degrada la recomendación de COMPRA FUERTE a
COMPRA. Es decir, **una ruptura potente con RSI sobrecomprado recibe menos peso
de cartera que la misma ruptura sin sobrecompra.** Es intencionado y coherente,
pero no está documentado en el código.

---

## 2. Verificación crítica: ¿contamina el LLM la decisión?

**Hipótesis:** la salida del LLM solo sobrescribe campos de texto (`summary`,
`synthesis`) y no influye en `passed_gatekeeper`, `momentum_classification`,
`rating`, `position_size_pct`, `stop_loss_atr` ni `take_profit_atr`.

### 2.1 Evidencia por lectura de código

En los cuatro agentes la invocación del LLM ocurre **después** de que todas las
variables de decisión estén calculadas, y su único efecto es una reasignación:

| Agente | Línea | Efecto del LLM | Variables de decisión, ya fijadas antes |
|---|---|---|---|
| `fundamental.py` | 64-65 | `summary = llm_res.content` | `passed` (l. 29-39) |
| `technical.py` | 94-95 | `summary = llm_res.content` | `momentum` (l. 68-75) |
| `debate.py` | 66-67 | `synthesis = llm_res.content` | ninguna (capa puramente narrativa) |
| `fund_manager.py` | 93-94 | `summary = llm_res.content` | `rating`, `position_size_pct`, `stop_loss`, `take_profit` (l. 31-65) |

El `debate_report` se consume una sola vez, en `fund_manager.py:69`, dentro de un
f-string que construye `rationale` — un campo de texto. No hay ninguna ruta por
la que la síntesis del debate alcance el dictamen.

### 2.2 Evidencia empírica

La lectura de código no basta, así que se comprueba en ejecución. La función
`assert_llm_is_decision_neutral()` (`src/backtest/replay.py`) ejecuta el pipeline
completo dos veces sobre el mismo estado sintético: una con `get_llm() → None` y
otra con un LLM falso que devuelve texto constante. Resultado:

```
NEUTRAL: True
heurístico: {"passed_gatekeeper": true, "momentum_classification": "ALCISTA_FUERTE",
             "rating": "COMPRA FUERTE", "position_size_pct": "8.0% - 10.0%",
             "stop_loss_atr": 96.0, "take_profit_atr": 107.0}
con LLM   : {"passed_gatekeeper": true, "momentum_classification": "ALCISTA_FUERTE",
             "rating": "COMPRA FUERTE", "position_size_pct": "8.0% - 10.0%",
             "stop_loss_atr": 96.0, "take_profit_atr": 107.0}
divergencias: {}
```

**HIPÓTESIS CONFIRMADA.** La comprobación se ejecuta en cada arranque de
`backtest_cli.py` y aborta el estudio si alguna vez deja de cumplirse, y está
fijada como test de regresión (`tests/test_backtest.py::test_llm_is_decision_neutral`).

### 2.3 Consecuencia

El backtest puede correr con el motor heurístico determinista y seguir siendo
una **réplica fiel** de producción: mismos ratings, mismos niveles, sin coste de
API, sin temperatura, sin variabilidad entre ejecuciones. Es lo que hace viable
todo el estudio.

Corolario incómodo para el diseño del sistema: **el LLM es hoy una capa de
redacción, no de análisis.** Los cuatro agentes son motores de reglas y el
modelo solo pone la prosa encima. No es necesariamente malo, pero la
arquitectura se presenta como "análisis multi-agente" cuando la inteligencia
reside íntegramente en umbrales fijos escritos a mano.

---

## 3. Inventario de fuentes: point-in-time vs. as-of-today

| Métrica | Fuente en producción | Régimen temporal | ¿Utilizable en backtest? |
|---|---|---|---|
| OHLCV | `yfinance.history(period="1y")` | Point-in-time (ajustado) | ✅ Sí |
| RSI, MACD, Bollinger, SMA, ATR, Volumen rel. | Derivados del OHLCV | Point-in-time | ✅ Sí, recalculando la ventana |
| `revenue_growth` | `info["revenueGrowth"]` | **AS-OF-TODAY (TTM)** | ❌ No — look-ahead |
| `net_margin` | `info["profitMargins"]` | **AS-OF-TODAY (TTM)** | ❌ No — look-ahead |
| `debt_to_equity` | `info["debtToEquity"]` | **AS-OF-TODAY** | ❌ No — look-ahead |
| `roe`, `pe_ratio` | `info[...]` | **AS-OF-TODAY** | ❌ No (irrelevantes para la decisión) |
| `sector`, `industry` | `info[...]` | As-of-today (casi estático) | ⚠️ Aceptable, solo descriptivo |
| Revenues / NetIncome / Assets / Liabilities | SEC EDGAR companyfacts | Point-in-time **si se filtra por `filed`** | ✅ Sí, con la corrección de §4.3 |
| `net_margin_ttm` de Finnhub | API Finnhub | As-of-today, sin histórico gratuito | ❌ No disponible |

**Este es el hallazgo que determina el diseño del backtest.** Las tres métricas
que gobiernan el gatekeeper son as-of-today. Replicar producción literalmente
significaría filtrar el año 2016 sabiendo qué empresas serían rentables en 2026,
lo que produce un resultado espectacular y completamente falso.

Solución adoptada: reconstruir `revenue_growth`, `net_margin` y `debt_to_equity`
desde SEC EDGAR filtrando por `filed <= t` (`src/backtest/data.py::FundamentalStore`),
y ejecutar además los regímenes `technical_only` (gatekeeper neutralizado) y
`biased` (fundamentales de hoy, etiquetado como look-ahead) para acotar el
tamaño del sesgo.

---

## 4. Defectos encontrados

Ninguno se ha corregido: la capa de backtest es de solo lectura y arreglarlos
habría cambiado el sistema que se pretende medir. Se documentan aquí para que la
decisión de corregirlos sea explícita.

### 4.1 🔴 `summary` y `rationale` guardan el *repr* de la respuesta del LLM

**Dónde:** `fundamental.py:64-65`, `technical.py:94-95`, `debate.py:66-67`,
`fund_manager.py:93-94` — el patrón `summary = llm_res.content`.

**Qué pasa:** con los modelos actuales `.content` no es una cadena, sino una
lista de bloques de contenido. Se asigna la lista entera a un campo que el
generador de informes interpola con un f-string (`report_generator.py:66,89`),
así que el markdown acaba mostrando la estructura interna en crudo, bloque
`signature` incluido. Se puede ver en `output/daily_selection.md:23` y `:29`:

```
- **Resumen:** [{'type': 'text', 'text': 'Como Analista Fundamental...',
  'extras': {'signature': 'El4KXAERTTIPHaHf2ZSwS9kCaRu9m15Oah+irHS168aB...'}}]
```

**Impacto:** el informe que ve el usuario final es ilegible en sus campos
narrativos. No afecta a las decisiones (§2), pero sí a todo el valor
comunicativo del producto.

**Corrección sugerida:** normalizar en un único punto, por ejemplo un helper
compartido:

```python
def llm_text(res) -> str:
    content = getattr(res, "content", res)
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content
                       if isinstance(b, dict) and b.get("type") == "text").strip()
    return str(content).strip()
```

### 4.2 🔴 Los ETF siempre se rechazan y salen como VENTA

**Dónde:** interacción entre `fetcher.py:35-43` y `fundamental.py:29-39`.

**Qué pasa:** un ETF no tiene `revenueGrowth`, `profitMargins` ni
`debtToEquity`. `info.get(..., 0.0)` devuelve 0.0, las tres reglas del gatekeeper
fallan y el Fund Manager emite `VENTA` con 0% de asignación. `output/daily_selection.md:11`
muestra exactamente eso para SPY: un ETF del S&P 500 clasificado como venta por
"ausencia de crecimiento y rentabilidad".

**Impacto:** el sistema no puede evaluar ETFs ni ningún instrumento sin estados
financieros. Peor: no lo señala como *fuera de alcance*, sino que emite una
recomendación de venta con apariencia de análisis. Un usuario podría actuar
sobre ella.

**Corrección sugerida:** detectar `quoteType in {"ETF", "MUTUALFUND", "INDEX"}`
en el fetcher y enrutar a un dictamen `NO_APLICABLE`, distinto de `VENTA`.

### 4.3 🟠 `_extract_recent_fact()` ordena por `end`, no por `filed`

**Dónde:** `src/data/sec_edgar.py:79`.

```python
sorted_items = sorted(items, key=lambda x: x.get("end", ""), reverse=True)
```

**Qué pasa:** toma el hecho XBRL cuyo *periodo contable* termina más tarde, sin
mirar cuándo se presentó. En tiempo real el efecto es leve (lo más reciente
suele ser también lo último presentado), pero es un look-ahead latente: en
cualquier reproducción histórica devuelve cifras que aún no eran públicas.

**Impacto en el backtest:** bloqueante. Por eso `FundamentalStore` no reutiliza
este cliente y reimplementa la selección filtrando por `filed <= t`, con un
retardo mínimo de 45 días cuando el campo falta.

**Corrección sugerida:** ordenar por `(filed, end)` y aceptar una fecha de corte
opcional. Es un cambio de una línea que además hace el cliente reutilizable
desde el backtest.

### 4.4 🟠 La "reconciliación multi-fuente" no reconcilia nada

**Dónde:** `src/data/reconciler.py:52-58`.

```python
reconciled_metrics = {
    "revenue_growth": revenue_yf,      # yfinance
    "net_margin":     net_margin_yf,   # yfinance
    "debt_to_equity": debt_to_equity_yf,  # yfinance
    "roe":            roe_yf,          # yfinance
    "pe_ratio":       yf_fund.get("pe_ratio", 0.0),  # yfinance
}
```

**Qué pasa:** las cinco métricas que consume el gatekeeper proceden
íntegramente de yfinance. SEC EDGAR y Finnhub solo se usan para detectar
discrepancias y descontar puntos de un `confidence_score`, que a su vez no
rechaza nada (`fundamental.py:41-42`). El módulo se llama "Consistency Checker"
y el informe presenta un "Confianza en Datos Multi-Fuente: 100%", pero **la
fuente oficial y auditada de la SEC no influye en ninguna decisión**.

**Impacto:** el sistema hereda todos los errores de yfinance sin la protección
que su propia arquitectura sugiere tener. Es además la razón por la que la
ausencia de Finnhub en el backtest no altera ningún resultado.

**Corrección sugerida:** o bien usar realmente los datos de la SEC como fuente
primaria con yfinance de respaldo, o bien renombrar el módulo para que no
prometa una garantía que no da.

### 4.5 🟠 Las ventanas `min(50, len)` / `min(200, len)` redefinen los indicadores en silencio

**Dónde:** `src/data/fetcher.py:76-77`.

```python
df["SMA_50"]  = close.rolling(window=min(50,  len(close))).mean()
df["SMA_200"] = close.rolling(window=min(200, len(close))).mean()
```

**Qué pasa:** con un histórico corto —una salida a bolsa reciente, o cualquier
llamada con una ventana recortada— la "SMA de 200 sesiones" pasa a ser la media
de todo lo disponible, sin avisar. La estructura `close > sma50 > sma200`, que
vale 2 puntos alcistas, se calcula entonces sobre algo que no es lo que su
nombre dice.

**Impacto en el backtest:** obliga a exigir ≥ 200 sesiones en cada ventana
(`replay.py::MIN_WINDOW_ROWS`) para que las medias tengan la misma definición
que en producción. Las fechas que no lo cumplen se descartan en lugar de emitir
una señal calculada de otra manera.

**Corrección sugerida:** dejar `NaN` cuando no haya historia suficiente, en vez
de degradar la definición.

### 4.6 🟡 La heurística `debtToEquity > 10 → /100` puede dividir un dato correcto

**Dónde:** `src/data/fetcher.py:38-40`. yfinance devuelve a veces el ratio en
porcentaje (150 → 1.5) y el código lo normaliza dividiendo por 100 cuando supera
10. Una empresa genuinamente apalancada 12× —posible en banca— se convierte en
0.12 y atraviesa el filtro `MAX_DEBT_TO_EQUITY = 3.5` sin resistencia. El umbral
de 10 es una conjetura sobre el formato, no una comprobación de él.

### 4.7 🟡 El aviso de baja confianza nunca llega al informe

**Dónde:** `src/agents/fundamental.py:41-48`. Si `confidence_score < 0.5` se
añade un motivo a `reasons`, pero `reasons` solo se concatena al `summary`
`if not passed`. Un valor **aprobado** con datos poco fiables se reporta sin
ninguna advertencia visible, aunque el motivo exista en el estado.

### 4.8 🟡 `VENTA` es ambiguo en un sistema solo-largo

`fund_manager.py:33` asigna `VENTA` a todo lo rechazado por el gatekeeper,
incluidos valores que nunca se han tenido en cartera. Semánticamente ahí
significa "no comprar", pero el informe lo presenta como recomendación de venta
y `daily_selection.md` no distingue ambos casos. En el backtest se ha
interpretado como "salir si se tiene, no entrar si no" — decisión que queda
documentada porque cambia el resultado.

### 4.9 🟢 Errata: "Momentum técnico classified como"

`src/agents/fund_manager.py:68`. Spanglish en un texto que llega al informe
final. Trivial, pero visible para el usuario.

---

## 5. Consecuencias para el diseño del backtest

| Hallazgo | Decisión tomada |
|---|---|
| LLM neutral en la decisión (§2) | Replay determinista con `get_llm() → None`, coste cero |
| Fundamentales as-of-today (§3) | `FundamentalStore` point-in-time por `filed`; regímenes `pit` / `technical_only` / `biased` |
| `_extract_recent_fact` por `end` (§4.3) | No se reutiliza `SECEdgarClient`; selección reimplementada solo en la capa de backtest |
| Ventanas `min(...)` (§4.5) | Mínimo de 200 sesiones por ventana; las demás fechas no generan señal |
| Reconciliación ficticia (§4.4) | La ausencia de Finnhub en el backtest se declara inocua, y está justificada |
| ETFs siempre rechazados (§4.2) | Universo restringido a acciones; SPY solo se usa como benchmark, nunca como candidato |
| `VENTA` ambiguo (§4.8) | Regla explícita: salir si se tiene, no entrar si no |

---

## 6. Lo que el backtest devolvió sobre esta arquitectura

Los tres regímenes se ejecutaron sobre el mismo universo (50 megacaps
estadounidenses), el mismo periodo (2015-2025), la misma cadencia mensual y los
mismos costes (10 bps ida y vuelta). La única diferencia es de dónde salen los
fundamentales:

| Régimen | Fundamentales | CAGR | Sharpe | Operaciones | Percentil vs aleatorio |
|---|---|---:|---:|---:|---:|
| `pit` | SEC EDGAR, `filed <= t` | 2.11% | 0.35 | 928 | 1.9 |
| `technical_only` | **Gatekeeper desactivado** | **4.97%** | **0.59** | 2734 | 0.3 |
| `biased` | yfinance de HOY (look-ahead) | 3.80% | 0.50 | 1658 | 0.1 |
| _SPY comprar y mantener_ | — | _13.51%_ | _0.80_ | _1_ | — |

Dos lecturas incómodas, y ninguna depende del sesgo de supervivencia (que afecta
por igual a las tres filas al compartir universo):

**6.1 El gatekeeper fundamental destruye valor.** Desactivarlo más que duplica
el CAGR (2.11% → 4.97%). El filtro que motiva la arquitectura jerárquica entera
—y cuya justificación declarada es "evitar el gasto computacional de análisis
técnicos innecesarios"— está eliminando más oportunidades buenas que malas.

**6.2 Ni siquiera hacer trampas lo arregla.** El régimen `biased` le entrega al
gatekeeper los fundamentales de 2026 para filtrar 2015, un look-ahead que
debería producir resultados irreales de buenos. Rinde 3.80%: mejor que el
régimen limpio, como era de esperar, pero **todavía peor que no usar el filtro
en absoluto**. El problema no es que el gatekeeper trabaje con información
tardía; es que sus tres umbrales (crecimiento ≥ 5%, margen ≥ 3%, deuda/capital
≤ 3.5) seleccionan un estilo de inversión que no fue el ganador del periodo.

**6.3 El rating no ordena el rendimiento futuro.** Rendimiento medio a 12 meses
por categoría en el régimen `pit`, sobre 5621 señales: VENTA FUERTE +35.1%,
COMPRA +23.8%, MANTENER +21.1%, COMPRA FUERTE +21.0%, VENTA +17.5%. La categoría
más bajista es la que más rinde y las dos de compra quedan por debajo de
MANTENER.

Aquí cabía una objeción legítima: VENTA FUERTE recoge sobre todo empresas con
fundamentales deteriorados, y de esas solo sobreviven en el universo las que se
recuperaron, así que el sesgo de supervivencia podría estar fabricando el
resultado. **El régimen `technical_only` desactiva esa objeción**, porque con el
gatekeeper apagado el rating lo determina exclusivamente el momentum técnico
(RSI, MACD, estructura SMA, Bollinger), y a lo largo de 11 años cada valor del
universo atraviesa las cinco categorías: el sesgo afecta a todos los cubos por
igual. El resultado, sobre 6550 señales:

| Rating | n | Rendimiento medio a 12 meses |
|---|---:|---:|
| VENTA | 177 | **+27.7%** |
| VENTA FUERTE | 660 | +24.3% |
| MANTENER | 2539 | +21.8% |
| COMPRA | 2301 | +20.7% |
| COMPRA FUERTE | 873 | **+18.9%** |

La ordenación es **perfectamente monótona, y al revés**: cuanto más alcista el
dictamen, peor el rendimiento a un año. Con t-stats de 15 a 24, no es ruido.

La interpretación más plausible no es que el código esté mal, sino que la regla
es económicamente ingenua: "RSI entre 50 y 70, cruce dorado y ruptura de la
banda superior de Bollinger" describe un valor que ya ha subido. Comprar fuerza
reciente en megacaps y mantener 12 meses captura sobre todo la reversión a la
media posterior. El sistema mide correctamente el momentum; lo que falla es la
premisa de que el momentum a corto plazo anticipa rendimiento a largo.

Nada de esto es un defecto de implementación: el código hace exactamente lo que
dice hacer. Es un resultado sobre el diseño, y por eso vive en el informe de
backtest y no en la lista de bugs de §4.

---

## 7. Qué NO cubre esta auditoría

- No se ha verificado el comportamiento del sistema bajo fallo de API real
  (timeouts, respuestas parciales de yfinance), solo la ruta feliz.
- No se han auditado `src/api/` ni la capa FastAPI, si existe: quedan fuera del
  camino de decisión.
- No se ha evaluado la calidad de los *prompts* enviados al LLM, porque su salida
  no interviene en ninguna decisión (§2).
- No se han revisado los tests existentes (`tests/test_fetcher.py`,
  `test_reconciler.py`, `test_workflow.py`) más allá de comprobar que la capa
  nueva no los rompe.
