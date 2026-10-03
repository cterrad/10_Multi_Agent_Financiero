# Informe de inversión — Selección Multi-Agente

`2026-09-10 20:05` · 6 valor(es): TSM, NVDA, GOOGL, MSFT, MU, CEG · referencia SPY 12m 17.7% · capital $1,500

> Sistema automatizado. Ratings, pesos y niveles salen de reglas deterministas; el modelo de lenguaje solo redacta los resúmenes. **No es asesoramiento de inversión.**

## Decisión

| Ticker | Estilo | Conv | Mom | Macro | Entrada | Dictamen | Peso | Mercado | Objetivo entrada | Stop | Take-profit | R:R | Horiz. |
| :--- | :--- | ---: | ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **TSM** | `CALIDAD_COMPUESTA` | 83 | +78 | neutro +0.10 | ESPERAR_RETROCESO -2.1% | **COMPRA FUERTE** | 9.11% | $432.07 | $423.16 | $398.04 | $473.41 | 2.00 | 252d |
| **NVDA** | `CALIDAD_COMPUESTA` | 60 | +43 | neutro +0.10 | ESCALONAR -0.5% | **COMPRA** | 3.42% | $218.89 | $217.86 | $198.56 | $256.46 | 2.00 | 252d |
| **GOOGL** | `CALIDAD_COMPUESTA` | 67 | -16 | neutro +0.10 | ESPERAR_RETROCESO -0.3% | **COMPRA** | 8.40% | $329.89 | $328.83 | $311.63 | $363.23 | 2.00 | 252d |
| **MSFT** | `CALIDAD_COMPUESTA` | 65 | +12 | neutro +0.10 | ESPERAR_RETROCESO -0.9% | **COMPRA** | 6.87% | $491.50 | $487.31 | $462.13 | $537.66 | 2.00 | 252d |
| **MU** | `CALIDAD_COMPUESTA` | 62 | +68 | neutro +0.10 | ESPERAR_RETROCESO -0.4% | **COMPRA** | 0.00% | $983.02 | $978.68 | $868.60 | $1,198.83 | 2.00 | 252d |
| **CEG** | `MIXTA` | 42 | -24 | contra -0.34 | NO_APLICABLE | **VENTA** | 0.00% | $289.36 | $289.36 | $271.04 | $321.42 | 1.75 | 126d |

_Convicción 0-100 (calidad, valoración, crecimiento y solvencia, descontada por cobertura de datos) · Momentum −100 a +100 · Macro: posicionamiento de especuladores en futuros · Entrada: si se persigue el precio o se exige retroceso · Peso: resultado del presupuesto de riesgo, no un rango fijo. Definiciones en el anexo._

## Cartera propuesta

Exposición bruta **27.80%** · liquidez 72.20% · riesgo agregado 1.91% (presupuesto 5.0%) · 4 posición(es), 3.64 efectivas

| Ticker | Sector | Estilo | Conv | Solicitado | Final | Riesgo | ρ media |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **TSM** | Technology | `CALIDAD_COMPUESTA` | 82.7 | 9.11% | **9.11%** | 0.72% | 0.359 |
| **GOOGL** | Communication Services | `CALIDAD_COMPUESTA` | 67.4 | 8.40% | **8.40%** | 0.47% | 0.235 |
| **MSFT** | Technology | `CALIDAD_COMPUESTA` | 65.1 | 6.87% | **6.87%** | 0.41% | 0.191 |
| **NVDA** | Technology | `CALIDAD_COMPUESTA` | 60.5 | 3.42% | **3.42%** | 0.32% | 0.363 |

<details><summary>Restricciones, ajustes y diversificación</summary>

**Por sector** (límite 30%): Technology 19.4% · Communication Services 8.4%

**Diversificación:** Ratio de diversificación 1.0 significa que las posiciones se mueven como una sola; por encima de 1.3 la cartera aporta diversificación real.

**Candidatos sin asignación:**

- `MU` (COMPRA) — peso calculado 0.86% por debajo del mínimo operable 1.00%: el coste de operar supera la aportación
- `CEG` (VENTA) — VENTA no genera asignación en una cartera solo larga


</details>

## Fichas por compañía

### TSM — Taiwan Semiconductor Manufactur

Technology / Semiconductors · confianza en datos 98% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `COMPRA FUERTE` · peso 9.11%
entrada $423.16 (-2.06% sobre $432.07) · stop $398.04 (2.5·ATR) · objetivo $473.41 (5.0·ATR) · R:R 2.0 · 252 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 49.9% vs 5.0% ✅; Crecimiento de ingresos 36.0% vs 5.0% ✅; Deuda / Patrimonio 0.17x vs 3.00x ✅ |
| Calidad y valoración | `CALIDAD_COMPUESTA` · convicción **83**/100 | calidad 86 · valoración 61 · crecimiento 100 · solvencia 96 · F-Score 9/9 · Altman 7.76 (SEGURA) · cobertura 100% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `ALCISTA_FUERTE` +78.4/100 | RSI 60.8 (ALCISTA_SALUDABLE) · tendencia ALCISTA_CONFIRMADA · ATR $10.05 (2.3%) · SMA200 +15.5% |
| Estructura | `APOYADO` | soporte sma_50 $419.24 · a 3.0% (1.28 ATR) |
| Posicionamiento | `ESPERAR_RETROCESO` -2.06% | macro NEUTRO (+0.10) · opciones NEUTRO (+0.08) · gamma AMORTIGUADO · nivel GAMMA_FLIP $423.16 |
| Noticias _(asesora)_ | `BAJA` 0.12 · MIXTA | 9 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 9 vs 🐻 2 | La tesis alcista de TSM destaca por unos fundamentos operativos y financieros sobresalientes, reflejados en un crecimiento de ingresos del 36.0% que duplica la mediana del sector, un margen neto del 49.9% y un ROIC del 4 |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 9/9 | FUERTE |
| Altman | Z'' (no manufactureras) | 7.76 | SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $38.58 | margen -1019.9% · 2/5 defensivos |
| Greenblatt | EBIT/EV | 13.1% | atractivo |
| Buffett | ROIC | 46.7% | +37.7% sobre el coste de capital |
| Buffett | Margen bruto | 64.2% | indicio de foso · FCF yield 44.3% · dilución -0.00% |
| Lynch | PEG | 0.41 | MUY_ATRACTIVO · CRECIMIENTO_RAPIDO (sobre beneficio) |
| Sloan | Devengos | -7.3% | beneficio respaldado por caja |

**Estilo `CALIDAD_COMPUESTA`** — Calidad 85.5/100 y solvencia 96.1/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción: bruta 84.4 × cobertura 1.0 × confianza 0.979 − 0.0 por banderas = **82.7**._

**Contexto sectorial (Technology)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 31.9x | 26.0x | 1.23 | por encima del sector |
| Margen neto | 49.9% | 15.0% | 3.33 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.6x | 0.28 | por debajo del sector |
| Crecimiento | 36.0% | 12.0% | 3.0 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=21.40% |
| Flujo de caja operativo positivo | ✅ | FCO=2,274,975,600,000 |
| ROA en mejora | ✅ | 17.31% → 21.40% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 14.32% → 11.30% |
| Ratio corriente en mejora | ✅ | 2.36 → 2.51 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ✅ | 56.12% → 59.89% |
| Rotación de activos en mejora | ✅ | 0.43x → 0.48x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia +30.0 · macd +7.9 · rsi +14.5 · bollinger +6.0 · momentum precio +20.0 → **+78.40**

SMA50 +3.1% · SMA200 +15.5% · rango 52s 79% · volatilidad anual 44.7% · momentum relativo 12m +48.9%

- Tendencia alcista confirmada: precio 432.07 > SMA50 419.24 > SMA200 374.21
- MACD alcista (histograma +1.993, 0.20 ATR)
- RSI en zona alcista saludable (60.8, entre 50 y 70)
- Precio en el 80% del canal de Bollinger
- Momentum 12m (excl. último mes) +66.6% frente al +17.7% de SPY: exceso +48.9%

**Lectura:** El activo presenta una estructura de tendencia alcista confirmada con el precio cotizando por encima tanto de su media móvil de cincuenta sesiones como de la de doscientos, apoyado por un RSI de sesenta con ocho que refleja un impulso alcista saludable sin mostrar sobrextensión. Con una puntuación de setenta y ocho con cuatro sobre cien que califica el momentum como alcista fuerte y un histograma MACD positivo de uno con novecientos noventa y tres, la sostenibilidad del movimiento se mantiene firme mientras el valor opera en el setenta y nueve por ciento de su rango anual.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| sma_50 | $419.24 |
| minimo_10 | $407.82 |
| minimo_21 | $405.15 |
| bb_inferior | $404.55 |
| sma_200 | $374.21 |
| minimo_63 | $372.72 |

- Soporte más cercano sma_50 en $419.24, a 2.97% (1.28 ATR)
- Otros soportes por debajo: minimo_10 $407.82, minimo_21 $405.15, bb_inferior $404.55
- Estructura: APOYADO

**Lectura:** El precio actual de TSM se sitúa en $432.07 encontrando su soporte estructural más cercano en el origen sma_50 en $419.24, lo que representa una distancia del 3.0% o 1.28 ATR. Por debajo de esta referencia se encuentran adicionales niveles como el minimo_10 en $407.82, el minimo_21 en $405.15 y la banda inferior de volatilidad en $404.55, mientras que la primera referencia por encima figura como no disponible.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado se encuentra en un estado no aplicable debido a una divergencia en la serie histórica del proveedor que exige revisar los datos antes de reejecutar el estudio. Para TSM, la volatilidad realizada del valor se sitúa en 44.7% mientras que la volatilidad implícita a un mes y a tres meses figura como no disponible, y la puerta de régimen se mantiene abierta sin que esto último suponga por sí solo un argumento operativo.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 669,486 · histórico acumulado 0/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 1.5359 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 1.7743 | — | — |
| Skew (IV put OTM − call OTM) | 0.029053 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | 0.096 | — | comparable sin histórico |

**Posición en el canal de open interest: 64%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $400.00 · resistencia OI $450.00 · max pain $410.00 · punto de inflexión de gamma $423.16

Régimen de gamma **AMORTIGUADO** (exposición 119,289,202 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | -0.28 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | +0.56 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.10 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro +0.10 · opciones +0.08 · técnico +0.78 → media +0.32, confluencia 33% sobre 3 componente(s) → **ESPERAR_RETROCESO**

Ajuste bruto hasta el nivel -2.06% × factor 1.0 = **-2.06%** → entrada objetivo $423.16

**Lectura:** El sesgo macro neutro y el posicionamiento moderado en futuros se alinean con un régimen de gamma amortiguado de 119,289,202 dólares de delta por cada 1% de movimiento del subyacente, lo que sugiere un entorno sin fuertes presiones direccionales imperiosas. Ante esta estructura y bajo la decisión de esperar un retroceso, el ajuste de entrada sitúa el precio objetivo en $423.16, exactamente un -2.06% por debajo del mercado actual, apoyado en el punto de inflexion de gamma.


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-09-10` **OTROS** · ALCISTA · p=0.03 · _finance.biggo.com_ — [Barclays Raises S&P 500 Year-End Target to 7,950, But Prediction Markets Remain More Cautious - finance.biggo.com](https://news.google.com/rss/articles/CBMidkFVX3lxTFA3VW50cUxkbWpFQ3VzblF0aFgzV2tOYnFuaXV3VTJnc0c4aW5LMHRLSjFWaGxNYlhwYmE3TmpjOThrdmJKZGo1WHJnYkZlQ1J6R2xjQV9GNzZVTlptRXJzcFo1Vm1QZENPcTRMNE5leU4xY1FvUVE?oc=5)
- `2026-09-08` **OTROS** · BAJISTA · p=0.03 · _finance.biggo.com_ — [US-Iran Conflict Drives Oil Prices Higher; Dow Plunges 628 Points in Biggest Drop in Nearly Three Weeks - finance.biggo.com](https://news.google.com/rss/articles/CBMidkFVX3lxTFBVU3BHQnNzVTBfQ250djhWSWl4QmNMSk1YRGRCWDB1QXFHRWdOWFpEYUJzRS1wNktSdDUzN2kzSWlmYlpvSEd0bExoYUhSMVlMdlNidUpVZE5MX09JQl9URVlHTy1SdFRCOWJZWDlsMXhsejQ5MFE?oc=5)
- `2026-09-05` **OTROS** · NEUTRA · p=0.02 · _finance.biggo.com_ — [Three Stocks to Buy First If the Market Crashes Tomorrow: TSMC, Alphabet, Amazon - finance.biggo.com](https://news.google.com/rss/articles/CBMidkFVX3lxTE5tbkVLRVAxZXVHN1JkaEpreGZtZTFuY3RwdTB0VXh4a0xBYzl4eEplOThjMFNJcjdOWUowQUJReG5vczNkSDFpZThUSkYxaklRSnpQYk5Obk8zS3dBeG5WZ1JCTkdOZ0p2b05SLUNPMkp5TGZWSkE?oc=5)

_Fuentes sin respuesta: tavily._

**Lectura:** El análisis de nueve noticias en treinta días, elaborado con un informe degradado por la falta de respuesta de la fuente tavily, muestra que la compañía figura entre las opciones recomendadas en caso de una caída del mercado, mientras el contexto macroeconómico refleja la volatilidad de Wall Street y el encarecimiento del petróleo por el conflicto entre Estados Unidos e Irán. Esta configuración noticiosa genera una probabilidad de impacto en el precio baja de 0.12 con una dirección probable mixta y un desequilibrio de -0.14, lo que sugiere que los catalizadores externos contrarrestan el atractivo fundamental de la empresa sin alterar de forma determinante su cotización a corto plazo.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos excepcional del 36.0%, muy por encima del sector (mediana de Technology: 12%).
- Margen neto muy alto del 49.9%, muy por encima del sector.
- ROIC del 46.7%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 64%, indicio de poder de fijación de precios.
- F-Score de Piotroski 9/9: la calidad contable mejora en rentabilidad, apalancamiento y eficiencia a la vez.
- PEG de 0.41 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Rendimiento del flujo de caja libre del 44.3%.
- Estructura técnica alcista confirmada con puntuación de momentum +78.4/100 y RSI de 60.8 (alcista saludable).
- Solvencia 96.1/100: el balance aguanta un escenario adverso sin comprometer la tesis.

**🐻 Bajista**

- P/E de 31.9x, por encima del sector (mediana de Technology: 26x).
- 1 discrepancia(s) entre proveedores de datos; confianza del 98%.

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 18% en dos trimestres consecutivos.
- Que el margen neto baje del 30.0%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($374.21) con volumen creciente.

**Síntesis:** La tesis alcista de TSM destaca por unos fundamentos operativos y financieros sobresalientes, reflejados en un crecimiento de ingresos del 36.0% que duplica la mediana del sector, un margen neto del 49.9% y un ROIC del 46.7% que demuestra una creación de valor excepcional respaldada por un F-Score perfecto de Piotroski de 9/9 y un atractivo PEG de 0.41. Frente a esta solidez, la postura bajista se limita a señalar un ratio P/E de 31.9x superior a la mediana del sector de 26x y una discrepancia menor entre proveedores con una confianza del 98%, mientras que el flujo de noticias mixtas de impacto bajo y las condiciones específicas de invalidación no alteran el dictamen. En conclusión, el peso de los datos cuantitativos y técnicos favorables inclina claramente la balanza hacia la tesis alcista, evidenciando que la compañía justifica con creces sus múltiplos mediante una rentabilidad y una salud de balance incuestionables.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **82.7** × 0.65 + momentum normalizado **89.2** × 0.35 = **85.0**/100 → **COMPRA FUERTE**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

convicción ×1.318 · riesgo 0.988% · stop a 5.9% → 16.65% · volatilidad ×0.559 · datos ×0.979 · banderas ×1.0 · extensión ×1.0 → **9.11%**

_riesgo por posición 0.99% sobre un stop al 5.9%, escalado por volatilidad ×0.56_

R:R 2.0 → exige acertar el **33.3%** de las veces para no perder dinero. Horizonte 252 sesiones (~12.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_TSM: fundamentales aprobados; estilo CALIDAD_COMPUESTA con convicción 82.7/100 y momentum ALCISTA_FUERTE (+78.4/100). Síntesis del debate: La tesis alcista de TSM destaca por unos fundamentos operativos y financieros sobresalientes, reflejados en un crecimiento de ingresos del 36.0% que duplica la mediana del sector, un margen neto del 49.9% y un ROIC del 46.7% que demuestra una creación de valor excepcional respaldada por un F-Score perfecto de Piotroski de 9/9 y un atractivo PEG de 0.41. Frente a esta solidez, la postura bajista se limita a señalar un ratio P/E de 31.9x superior a la mediana del sector de 26x y una discrepancia menor entre proveedores con una confianza del 98%, mientras que el flujo de noticias mixtas de impacto bajo y las condiciones específicas de invalidación no alteran el dictamen. En conclusión, el peso de los datos cuantitativos y técnicos favorables inclina claramente la balanza hacia la tesis alcista, evidenciando que la compañía justifica con creces sus múltiplos mediante una rentabilidad y una salud de balance incuestionables._


</details>

**Lectura:** Se emite una orden de compra fuerte sobre TSM con una asignación del 9.11% de la cartera, respaldada por una convicción fundamental de 83 sobre 100 y un momentum positivo de más 78 sobre 100 sin que consten vetos ni banderas rojas que limiten la operativa. La ejecución se establece al precio de $432.07 por acción, fijando estrictamente un nivel de stop en $398.04 y un objetivo en $473.41, lo que arroja una relación de riesgo beneficio de 2.00. Todo este despliegue táctico debe desarrollarse y evaluarse estrictamente dentro del horizonte temporal fijado de 252 sesiones.

---

### NVDA — NVIDIA Corporation

Technology / Semiconductors · confianza en datos 86% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `COMPRA` · peso 3.42%
entrada $217.86 (-0.47% sobre $218.89) · stop $198.56 (2.5·ATR) · objetivo $256.46 (5.0·ATR) · R:R 2.0 · 252 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 63.7% vs 5.0% ✅; Crecimiento de ingresos 105.9% vs 5.0% ✅; Deuda / Patrimonio 0.17x vs 3.00x ✅ |
| Calidad y valoración | `CALIDAD_COMPUESTA` · convicción **60**/100 | calidad 72 · valoración 27 · crecimiento 100 · solvencia 91 · F-Score 4/9 · Altman 13.22 (SEGURA) · cobertura 100% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `ALCISTA` +42.8/100 | RSI 51.3 (ALCISTA_SALUDABLE) · tendencia ALCISTA_CONFIRMADA · ATR $7.72 (3.5%) · SMA200 +11.0% |
| Estructura | `APOYADO` | soporte sma_50 $212.18 · a 3.1% (0.87 ATR) |
| Posicionamiento | `ESCALONAR` -0.47% | macro NEUTRO (+0.10) · opciones PRECIO_FAVORABLE (+0.40) · gamma AMORTIGUADO · nivel GAMMA_FLIP $216.83 |
| Noticias _(asesora)_ | `MEDIA` 0.53 · INCIERTA | 13 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 7 vs 🐻 1 | La tesis alcista de Nvidia se sustenta en datos sólidos que reflejan un crecimiento de ingresos del 105.9%, un margen neto del 63.7%, un ROIC del 76.3% y un PEG de 0.22, respaldados además por una estructura técnica salu |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 4/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 13.22 | SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $41.11 | margen -432.4% · 2/5 defensivos |
| Greenblatt | EBIT/EV | 2.6% | bajo umbral |
| Buffett | ROIC | 76.3% | +67.3% sobre el coste de capital |
| Buffett | Margen bruto | 74.7% | indicio de foso · FCF yield 1.8% · dilución -0.71% |
| Lynch | PEG | 0.22 | MUY_ATRACTIVO · CRECIMIENTO_RAPIDO (sobre beneficio) |
| Sloan | Devengos | 8.4% | beneficio con componente de devengo |

**Estilo `CALIDAD_COMPUESTA`** — Calidad 72.3/100 y solvencia 91.4/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción: bruta 70.3 × cobertura 1.0 × confianza 0.861 − 0.0 por banderas = **60.5**._

**Contexto sectorial (Technology)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 27.6x | 26.0x | 1.06 | en línea con el sector |
| Margen neto | 63.7% | 15.0% | 4.24 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.6x | 0.28 | por debajo del sector |
| Crecimiento | 105.9% | 12.0% | 8.82 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=58.06% |
| Flujo de caja operativo positivo | ✅ | FCO=102,718,000,000 |
| ROA en mejora | ❌ | 65.30% → 58.06% |
| Flujo operativo > beneficio neto | ❌ | sin datos o devengos altos |
| Apalancamiento a largo plazo a la baja | ✅ | 7.58% → 3.61% |
| Ratio corriente en mejora | ❌ | 4.44 → 3.91 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ❌ | 74.99% → 71.07% |
| Rotación de activos en mejora | ❌ | 1.17x → 1.04x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia +30.0 · macd -0.6 · rsi +8.8 · bollinger -1.3 · momentum precio +5.9 → **+42.78**

SMA50 +3.2% · SMA200 +11.0% · rango 52s 76% · volatilidad anual 40.6% · momentum relativo 12m +8.9%

- Tendencia alcista confirmada: precio 218.89 > SMA50 212.18 > SMA200 197.13
- MACD bajista (histograma -0.116, 0.02 ATR)
- RSI en zona alcista saludable (51.3, entre 50 y 70)
- Precio en el 43% del canal de Bollinger
- Momentum 12m (excl. último mes) +26.5% frente al +17.7% de SPY: exceso +8.9%

**Lectura:** La estructura de tendencia alcista confirmada y la posición del precio por encima de sus medias móviles respaldan un impulso alcista saludable, respaldado por un RSI neutral en 51.3 que aleja cualquier lectura de sobreextensión. Aunque el histograma del MACD se sitúa levemente en negativo en -0.116, la puntuación de momentum de +42.8/100 y la ubicación del precio al 76% del rango de cincuenta y dos semanas permiten un despliegue de posición sostenible sin señales de agotamiento inmediato.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| sma_50 | $212.18 |
| minimo_10 | $209.23 |
| bb_inferior | $208.16 |
| minimo_21 | $207.25 |
| sma_200 | $197.13 |
| minimo_63 | $189.80 |

- Soporte más cercano sma_50 en $212.18, a 3.07% (0.87 ATR)
- Otros soportes por debajo: minimo_10 $209.23, bb_inferior $208.16, minimo_21 $207.25
- Estructura: APOYADO

**Lectura:** El precio actual de NVDA se sitúa en $218.89, apoyado sobre el nivel más cercano por debajo ubicado en $212.18, que coincide con el origen sma_50 y dista un 3.1% o 0.87 ATR. Los demás soportes estructurales se disponen de manera sucesiva en $209.23 para el minimo_10, $208.16 en la banda inferior de volatilidad y $207.25 para el minimo_21, mientras que la primera referencia por encima figura como no disponible.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado figura como no aplicable debido a una divergencia detectada en la serie histórica del proveedor que impide validar las métricas de volatilidad implícita y su curva, mientras que la volatilidad realizada de la compañía se sitúa en el 40.6 por ciento con una lectura relativa no disponible. Pese a esta incidencia técnica que invalida la clasificación del entorno, la puerta de régimen se mantiene abierta para la operativa sin que ello suponga una recomendación de compra.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 5,121,422 · histórico acumulado 1/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 0.808 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 0.5831 | — | — |
| Skew (IV put OTM − call OTM) | 0.073241 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | 0.2269 | — | comparable sin histórico |

**Posición en el canal de open interest: 38%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $200.00 · resistencia OI $250.00 · max pain $200.00 · punto de inflexión de gamma $216.83

Régimen de gamma **AMORTIGUADO** (exposición 136,225,225 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | +0.24 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | +0.91 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.05 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro +0.10 · opciones +0.40 · técnico +0.43 → media +0.31, confluencia 67% sobre 3 componente(s) → **ESCALONAR**

Ajuste bruto hasta el nivel -0.94% × factor 0.5 = **-0.47%** → entrada objetivo $217.86

**Lectura:** El posicionamiento neutral en futuros junto a un sesgo macro del valor de +0.10 y un régimen de gamma amortiguado de 136,225,225 DOLARES de delta por cada 1% de movimiento del subyacente indican que no existe una presión direccional dominante, lo que permite aprovechar el sesgo favorable en la cadena de opciones para planificar la compra. Dado que la decisión de entrada es escalonar con un ajuste del -0.47% apoyado en el punto de inflexion de gamma de $216.83, conviene fijar el precio objetivo en $217.86 en lugar de perseguir el precio de mercado de $218.89.


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-09-10` **REGULATORIO** · NEUTRA · p=0.25 · _Reuters_ — [DOJ probes Nvidia's licensing deal with AI startup Groq, NYT reports - Reuters](https://news.google.com/rss/articles/CBMivwFBVV95cUxOM04tamJVM0lINldJeEdvdDNHbTMxM2NMY0FzZjlGbWQzRVRjWGMweU9WM1NFeXU2U0NwdDdxZ1JOSVVUM0tjZVlkQTZvbE41VGlOT2FVbVJrRjN4Wk1ldW1od2tBcUR2T1ZKR244TjQwdWtHTm5qVFRyOFdzSGVGWVNtbFUwdHVZdl9Fak9SR1JlUWN0VUNXdFZPajZuTGVMRVJ0QUFCNzlRajdUWjVGVGNJQkotdlhFQjFoREQ1WQ?oc=5)
- `2026-09-07` **GUIDANCE** · NEUTRA · p=0.14 · _Yahoo Finance_ — [Nvidia’s (NVDA) Strong Results Reinforce Long Term Outlook - Yahoo Finance](https://news.google.com/rss/articles/CBMiowFBVV95cUxPeUtJRWdCR0V2dXFIZEF2alBBY1hFMUVyc1kwT1JRRm9NRVF0TGFBQW8tUFVWaUlvZC15SFR6ZExCaUVUVlhYSjJkYm00VF9lZ0dvTWZueDFXazVTTExvX21NaXJZZzZCWGZleF9SLXJZd2plcXo0NU42cjA3d0x0ei1ad2xuN0lrcWJsZS16XzRYU0hrbVdIMThwMjBJeEF5T25N?oc=5)
- `2026-08-26` **RESULTADOS** · NEUTRA · p=0.10 · _SEC EDGAR (8-K)_ — [NVIDIA Corporation presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1045810/000104581026000073/nvda-20260826.htm)

_Fuentes sin respuesta: tavily._

**Lectura:** La actividad reciente sobre NVIDIA Corporation comprende trece noticias en treinta días e incluye un informe regulatorio en el formulario ocho acá sobre resultados y condición financiera, además de la investigación de la fiscalía general sobre un acuerdo de licencias y análisis favorables sobre sus perspectivas a largo plazo, todo ello bajo el contexto de que la fuente tavily no respondió. Con una probabilidad de impacto en el precio media de cero coma cincuenta y tres y una dirección probable incierta con un desequilibrio de más cero coma cero cero, el informe se encuentra degradado por la falta de respuesta de esa fuente y los datos indican que el flujo informativo combina indagaciones regulatorias con presentaciones oficiales y valoraciones de mercado.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos excepcional del 105.9%, muy por encima del sector (mediana de Technology: 12%).
- Margen neto muy alto del 63.7%, muy por encima del sector.
- ROIC del 76.3%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 75%, indicio de poder de fijación de precios.
- PEG de 0.22 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Estructura técnica alcista confirmada con puntuación de momentum +42.8/100 y RSI de 51.3 (alcista saludable).
- Solvencia 91.4/100: el balance aguanta un escenario adverso sin comprometer la tesis.

**🐻 Bajista**

- 4 discrepancia(s) entre proveedores de datos; confianza del 86%.

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 53% en dos trimestres consecutivos.
- Que el margen neto baje del 38.2%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($197.13) con volumen creciente.

**Síntesis:** La tesis alcista de Nvidia se sustenta en datos sólidos que reflejan un crecimiento de ingresos del 105.9%, un margen neto del 63.7%, un ROIC del 76.3% y un PEG de 0.22, respaldados además por una estructura técnica saludable y alta solvencia. Por el contrario, la postura bajista carece de argumentos fundamentados en los datos y se limita a señalar cuatro discrepancias entre proveedores con una confianza del 86%, mientras que el flujo de noticias inciertas sobre una investigación del DOJ no altera el dictamen actual. En consecuencia, la solidez fundamental y momentum de la compañía validan la tesis de calidad compuesta, quedando condicionada su vigencia al cumplimiento de los estrictos umbrales de invalidación establecidos en cuanto a crecimiento, márgenes, rentabilidad y niveles técnicos.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **60.5** × 0.65 + momentum normalizado **71.4** × 0.35 = **64.3**/100 → **COMPRA**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

convicción ×0.762 · riesgo 0.572% · stop a 8.9% → 6.46% · volatilidad ×0.616 · datos ×0.861 · banderas ×1.0 · extensión ×1.0 → **3.42%**

_riesgo por posición 0.57% sobre un stop al 8.9%, escalado por volatilidad ×0.62_

R:R 2.0 → exige acertar el **33.3%** de las veces para no perder dinero. Horizonte 252 sesiones (~12.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_NVDA: fundamentales aprobados; estilo CALIDAD_COMPUESTA con convicción 60.5/100 y momentum ALCISTA (+42.8/100). Síntesis del debate: La tesis alcista de Nvidia se sustenta en datos sólidos que reflejan un crecimiento de ingresos del 105.9%, un margen neto del 63.7%, un ROIC del 76.3% y un PEG de 0.22, respaldados además por una estructura técnica saludable y alta solvencia. Por el contrario, la postura bajista carece de argumentos fundamentados en los datos y se limita a señalar cuatro discrepancias entre proveedores con una confianza del 86%, mientras que el flujo de noticias inciertas sobre una investigación del DOJ no altera el dictamen actual. En consecuencia, la solidez fundamental y momentum de la compañía validan la tesis de calidad compuesta, quedando condicionada su vigencia al cumplimiento de los estrictos umbrales de invalidación establecidos en cuanto a crecimiento, márgenes, rentabilidad y niveles técnicos._


</details>

**Lectura:** La mesa ejecutará una orden de compra sobre NVDA asignando el 3.42 por ciento de la cartera al precio de 218.89 dólares, respaldada por una convicción fundamental de 60 sobre 100 y un momentum positivo de más 43 sobre 100, operando sin vetos aplicados ni banderas rojas que limiten la directriz. La gestión del riesgo establece un nivel de stop en 198.56 dólares y un objetivo de salida en 256.46 dólares, lo que resulta en una relación de riesgo beneficio de 2.00. Todo este plan táctico se desarrollará estrictamente dentro de un horizonte temporal de 252 sesiones.

---

### GOOGL — Alphabet Inc.

Communication Services / Internet Content & Information · confianza en datos 91% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `COMPRA` · peso 8.40%
entrada $328.83 (-0.32% sobre $329.89) · stop $311.63 (2.5·ATR) · objetivo $363.23 (5.0·ATR) · R:R 2.0 · 252 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 54.8% vs 5.0% ✅; Crecimiento de ingresos 24.2% vs 5.0% ✅; Deuda / Patrimonio 0.19x vs 3.00x ✅ |
| Calidad y valoración | `CALIDAD_COMPUESTA` · convicción **67**/100 | calidad 80 · valoración 38 · crecimiento 91 · solvencia 92 · F-Score 6/9 · Altman 7.14 (SEGURA) · cobertura 100% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `BAJISTA` -16.2/100 | RSI 39.9 (NEUTRAL) · tendencia DETERIORO · ATR $6.88 (2.1%) · SMA200 -1.9% |
| Estructura | `PEGADO_AL_SOPORTE` | soporte minimo_10 $327.90 · a 0.6% (0.29 ATR) · primera referencia arriba $330.84 |
| Posicionamiento | `ESPERAR_RETROCESO` -0.32% | macro NEUTRO (+0.10) · opciones PRECIO_MUY_FAVORABLE (+0.47) · gamma AMORTIGUADO · nivel GAMMA_FLIP $328.83 |
| Noticias _(asesora)_ | `BAJA` 0.27 · ALCISTA | 12 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 7 vs 🐻 2 | La tesis alcista de GOOGL se sustenta en datos sólidos que demuestran una creación superior de valor, destacando un crecimiento de ingresos del 24.2% frente al 8% del sector, un margen neto del 54.8%, un ROIC del 29.9% q |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 6/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 7.14 | SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $151.11 | margen -118.3% · 2/5 defensivos |
| Greenblatt | EBIT/EV | 4.0% | bajo umbral |
| Buffett | ROIC | 29.9% | +20.9% sobre el coste de capital |
| Buffett | Margen bruto | 60.9% | indicio de foso · FCF yield 1.8% · dilución -1.01% |
| Lynch | PEG | 0.06 | MUY_ATRACTIVO · CRECIMIENTO_RAPIDO (sobre beneficio) |
| Sloan | Devengos | -5.5% | beneficio respaldado por caja |

**Estilo `CALIDAD_COMPUESTA`** — Calidad 80.4/100 y solvencia 91.9/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción: bruta 74.1 × cobertura 1.0 × confianza 0.909 − 0.0 por banderas = **67.4**._

**Contexto sectorial (Communication Services)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 16.5x | 19.0x | 0.87 | por debajo del sector |
| Margen neto | 54.8% | 12.0% | 4.56 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.8x | 0.24 | por debajo del sector |
| Crecimiento | 24.2% | 8.0% | 3.02 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=22.20% |
| Flujo de caja operativo positivo | ✅ | FCO=164,713,000,000 |
| ROA en mejora | ❌ | 22.24% → 22.20% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ❌ | 2.42% → 7.82% |
| Ratio corriente en mejora | ✅ | 1.84 → 2.01 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ✅ | 58.20% → 59.65% |
| Rotación de activos en mejora | ❌ | 0.78x → 0.68x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia -15.0 · macd -5.7 · rsi -3.0 · bollinger -10.0 · momentum precio +17.5 → **-16.21**

SMA50 -5.0% · SMA200 -1.9% · rango 52s 55% · volatilidad anual 36.2% · momentum relativo 12m +26.2%

- Precio por debajo de la SMA200 (336.17) con cruce aún alcista: tendencia en deterioro
- MACD bajista (histograma -0.976, 0.14 ATR)
- RSI neutral con sesgo débil (39.9, entre 30 y 50)
- Precio en la banda inferior de Bollinger (percentil -5% del canal)
- Momentum 12m (excl. último mes) +43.9% frente al +17.7% de SPY: exceso +26.2%

**Lectura:** La estructura de GOOGL muestra un deterioro con una puntuación de momentum de -16.2/100 que define un sesgo bajista, operando el precio a 329.89 dólares por debajo de su SMA50 en 347.37 y de su SMA200 en 336.17 sin estar sobreextendido, mientras el RSI se sitúa en un nivel neutral de 39.9 y el histograma del MACD en -0.976 confirman la presión vendedora. Aunque las medias móviles reflejan la inercia bajista de este proceso y la posición se encuentra al 55% del rango de 52 semanas, la aportación positiva del momentum de precio en 17.5 contrasta con el lastre acumulado de la tendencia y las bandas de Bollinger.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| minimo_10 | $327.90 |
| minimo_21 | $327.90 |
| minimo_63 | $314.70 |

- Soporte más cercano minimo_10 en $327.90, a 0.60% (0.29 ATR)
- Otros soportes por debajo: minimo_21 $327.90, minimo_63 $314.70
- Primera referencia por encima: $330.84
- Estructura: PEGADO_AL_SOPORTE

**Lectura:** El precio actual de GOOGL se sitúa en $329.89, encontrándose pegado al soporte estructural más cercano en $327.90, que proviene del origen del minimo_10. Esta referencia se localiza a una distancia del 0.6% o 0.29 ATR, con otros soportes adicionales situados en el minimo_21 en $327.90 y el minimo_63 en $314.70.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado para GOOGL no resulta aplicable debido a una divergencia en la serie histórica del índice que impide verificar la volatilidad implícita a un mes y a tres meses, mientras que la volatilidad realizada del valor se sitúa en el 36.2% con la puerta de régimen abierta. La ausencia de los datos de volatilidad implícita y de su cociente de curva impide determinar el estado de tensión o calma del mercado, reflejando una incidencia en la fuente que debe revisarse antes de reejecutar el análisis.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 1,322,445 · histórico acumulado 1/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 0.5527 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 0.3058 | — | — |
| Skew (IV put OTM − call OTM) | 0.030273 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | 0.1024 | — | comparable sin histórico |

**Posición en el canal de open interest: 18%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $320.00 · resistencia OI $375.00 · max pain $335.00 · punto de inflexión de gamma $328.83

Régimen de gamma **AMORTIGUADO** (exposición 49,482,596 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | +0.64 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | +0.59 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.02 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro +0.10 · opciones +0.47 · técnico -0.16 → media +0.14, confluencia 33% sobre 3 componente(s) → **ESPERAR_RETROCESO**

Ajuste bruto hasta el nivel -0.32% × factor 1.0 = **-0.32%** → entrada objetivo $328.83

**Lectura:** El posicionamiento levemente alcista en futuros y la baja confluencia técnica sugieren cautela, pero el régimen de gamma amortiguado y el sesgo favorable de la cadena de opciones permiten buscar una mejor ejecución. Por ello, la decisión de entrada indica esperar un retroceso aplicando un ajuste de menos cero con treinta y dos por ciento para fijar el precio objetivo en trescientos veintiocho con ochenta y tres dólares, apoyado en el punto de inflexion de gamma.


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-09-08` **GUIDANCE** · NEUTRA · p=0.11 · _cnn.com_ — [GOOGL Stock Quote Price and Forecast - cnn.com](https://news.google.com/rss/articles/CBMiUkFVX3lxTE5UbkhMMngyaG5RbUxmS1ZGOGtMZGpWMi1GZWM4TGdVUV9kT0wwRjhITEVWVERVZnY4ekZhU0lFbWtMNWhjZGpJdm1iek5wS0lrZUE?oc=5)
- `2026-09-08` **OTROS** · NEUTRA · p=0.06 · _Reuters_ — [EXCLUSIVE: Google warns of lower quality as it revamps Europe search results to avoid EU fines - Reuters](https://news.google.com/rss/articles/CBMitwFBVV95cUxNcUx1SUpiY29kQzBaZ0I0UmVKN0J1UkFoRlRmN0I1c0xwUjZackt2T3BVNHBvSFYwTzg3YUd6VUZlV3JrZ1FYUXVVUVpJWlRqZGN1VTNxUTZVNndVWXNJTkZ5Ui1YVjkyUDZuSW9ZWmNiR1NQYmtfOEhaVVhFWUE0dDROaVBOckhYZ3pvcnFwNXR4M3lkdmpxdUZ5eFRBT01jOGpzR0oyX2t1UHNValpzRmZJOWhnWGc?oc=5)
- `2026-09-09` **OTROS** · ALCISTA · p=0.05 · _Yahoo Finance_ — [Alphabet (GOOG) Surges Over 20% Revenue Growth, Cloud Strength - Yahoo Finance](https://news.google.com/rss/articles/CBMimAFBVV95cUxOM1MzSk82Y2JYMFF6dzFWeGlJSVRNUl9Md2R3TFhvTFY0TXlHWGxoYWRKWGNTSDgzWjVwOHhNeWRnY2VvU2JoeVByRkM1SFNmWHN3aXViVzRBZnpJMFdmbU9jeHk0dzljTnJTdUFqb0dXZGFtZGUtdllSQ3RRelZtWFdwNnJub0VweGRjZDNWTVNmUkRpYUthUQ?oc=5)

_Fuentes sin respuesta: tavily._

**Lectura:** Alphabet registra una probabilidad de impacto en el precio baja de 0.27 y una dirección probable alcista con un desequilibrio de +1.00 tras analizar 12 noticias en 30 días, destacando el optimismo en Yahoo Finance por el crecimiento de ingresos y la fortaleza de la nube frente al aviso de Reuters sobre una menor calidad en los resultados de búsqueda en Europa para evitar multas de la Unión Europea. El informe se encuentra degradado debido a que la fuente tavily no respondió, y las referencias proceden de agregadores y medios como cnn.com en lugar de comunicados regulatorios confirmados.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos sólido del 24.2%, muy por encima del sector (mediana de Communication Services: 8%).
- Margen neto muy alto del 54.8%, muy por encima del sector.
- ROIC del 29.9%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 61%, indicio de poder de fijación de precios.
- PEG de 0.06 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Solvencia 91.9/100: el balance aguanta un escenario adverso sin comprometer la tesis.
- Flujo de noticias con probabilidad de impacto BAJA (0.27) y sesgo ALCISTA sobre 12 nota(s); principal catalizador: "GOOGL Stock Quote Price and Forecast - cnn.com" (capa asesora: no altera el dictamen).

**🐻 Bajista**

- Estructura técnica en deterioro: el precio cotiza por debajo de su media de 200 sesiones.
- 4 discrepancia(s) entre proveedores de datos; confianza del 91%.

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 12% en dos trimestres consecutivos.
- Que el margen neto baje del 32.9%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($336.17) con volumen creciente.

**Síntesis:** La tesis alcista de GOOGL se sustenta en datos sólidos que demuestran una creación superior de valor, destacando un crecimiento de ingresos del 24.2% frente al 8% del sector, un margen neto del 54.8%, un ROIC del 29.9% que supera el coste de capital de referencia del 9%, un margen bruto del 61%, un PEG de 0.06 y una solvencia de 91.9 sobre 100, todo ello acompañado por un flujo de noticias con probabilidad de impacto baja de 0.27 y sesgo alcista sobre 12 notas cuyo principal catalizador es GOOGL Stock Quote Price and Forecast - cnn.com en la capa asesora que no altera el dictamen. En contraste, la postura bajista se limita a señalar una estructura técnica deteriorada donde el precio cotiza por debajo de su media de 200 sesiones, junto a 4 discrepancias entre proveedores de datos y una confianza del 91%. Dado que la tesis alcista aporta métricas financieras contundentes y la bajista se restringe a riesgos técnicos y discrepancias metodológicas, la conclusión imparcial es que los fundamentos operativos dominan el escenario actual, quedando condicionados únicamente a la vigilancia de los niveles de invalidación establecidos.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **67.4** × 0.65 + momentum normalizado **41.9** × 0.35 = **58.5**/100 → **COMPRA**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

convicción ×0.935 · riesgo 0.701% · stop a 5.2% → 13.41% · volatilidad ×0.69 · datos ×0.909 · banderas ×1.0 · extensión ×1.0 → **8.40%**

_riesgo por posición 0.70% sobre un stop al 5.2%, escalado por volatilidad ×0.69_

R:R 2.0 → exige acertar el **33.3%** de las veces para no perder dinero. Horizonte 252 sesiones (~12.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_GOOGL: fundamentales aprobados; estilo CALIDAD_COMPUESTA con convicción 67.4/100 y momentum BAJISTA (-16.2/100). Síntesis del debate: La tesis alcista de GOOGL se sustenta en datos sólidos que demuestran una creación superior de valor, destacando un crecimiento de ingresos del 24.2% frente al 8% del sector, un margen neto del 54.8%, un ROIC del 29.9% que supera el coste de capital de referencia del 9%, un margen bruto del 61%, un PEG de 0.06 y una solvencia de 91.9 sobre 100, todo ello acompañado por un flujo de noticias con probabilidad de impacto baja de 0.27 y sesgo alcista sobre 12 notas cuyo principal catalizador es GOOGL Stock Quote Price and Forecast - cnn.com en la capa asesora que no altera el dictamen. En contraste, la postura bajista se limita a señalar una estructura técnica deteriorada donde el precio cotiza por debajo de su media de 200 sesiones, junto a 4 discrepancias entre proveedores de datos y una confianza del 91%. Dado que la tesis alcista aporta métricas financieras contundentes y la bajista se restringe a riesgos técnicos y discrepancias metodológicas, la conclusión imparcial es que los fundamentos operativos dominan el escenario actual, quedando condicionados únicamente a la vigilancia de los niveles de invalidación establecidos._


</details>

**Lectura:** Ejecutaremos una posición de compra en GOOGL bajo el estilo calidad compuesta asignando el 8.40% de la cartera al precio actual de $329.89, respaldados por una convicción fundamental de 67 sobre 100 a pesar de un momentum desfavorable de menos 16 sobre 100 y sin que se registren vetos ni banderas rojas. La mesa mantendrá la operación durante un horizonte de 252 sesiones, operando estrictamente bajo un nivel de stop en $311.63 y un objetivo de $363.23 que configuran una relación de riesgo beneficio de 2.00. Esta orden obliga a la ejecución inmediata según los parámetros cuantitativos definidos, sin alterar ningún umbral y manteniendo la disciplina operativa hasta agotar el plazo establecido.

---

### MSFT — Microsoft Corporation

Technology / Software - Infrastructure · confianza en datos 95% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `COMPRA` · peso 6.87%
entrada $487.31 (-0.85% sobre $491.50) · stop $462.13 (2.5·ATR) · objetivo $537.66 (5.0·ATR) · R:R 2.0 · 252 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 40.3% vs 5.0% ✅; Crecimiento de ingresos 17.7% vs 5.0% ✅; Deuda / Patrimonio 0.29x vs 3.00x ✅ |
| Calidad y valoración | `CALIDAD_COMPUESTA` · convicción **65**/100 | calidad 80 · valoración 33 · crecimiento 83 · solvencia 79 · F-Score 6/9 · Altman 4.71 (SEGURA) · cobertura 100% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `NEUTRAL` +12.1/100 | RSI 56.4 (ALCISTA_SALUDABLE) · tendencia ALCISTA_CONFIRMADA · ATR $10.07 (2.1%) · SMA200 +14.4% |
| Estructura | `PEGADO_AL_SOPORTE` | soporte minimo_10 $487.31 · a 0.9% (0.42 ATR) |
| Posicionamiento | `ESPERAR_RETROCESO` -0.85% | macro NEUTRO (+0.10) · opciones PRECIO_MUY_FAVORABLE (+0.64) · gamma AMORTIGUADO · nivel SOPORTE_ESTRUCTURAL $487.31 |
| Noticias _(asesora)_ | `BAJA` 0.14 · BAJISTA | 12 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 7 vs 🐻 2 | La tesis alcista para MSFT destaca fundamentales sólidos, subrayados por un crecimiento de ingresos del 17.7% que supera al sector, un margen neto del 40.3% y un ROIC del 28.5% que confirma la creación de valor sobre el  |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 6/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 4.71 | SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $155.10 | margen -216.9% · 1/5 defensivos |
| Greenblatt | EBIT/EV | 4.6% | bajo umbral |
| Buffett | ROIC | 28.5% | +19.5% sobre el coste de capital |
| Buffett | Margen bruto | 67.9% | indicio de foso · FCF yield 1.8% · dilución -0.10% |
| Lynch | PEG | 0.86 | ATRACTIVO · CRECIMIENTO_RAPIDO (sobre beneficio) |
| Sloan | Devengos | -6.5% | beneficio respaldado por caja |

**Estilo `CALIDAD_COMPUESTA`** — Calidad 80.2/100 y solvencia 78.8/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción: bruta 68.7 × cobertura 1.0 × confianza 0.948 − 0.0 por banderas = **65.1**._

**Contexto sectorial (Technology)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 27.4x | 26.0x | 1.05 | en línea con el sector |
| Margen neto | 40.3% | 15.0% | 2.69 | muy por encima del sector |
| Deuda/Patrimonio | 0.3x | 0.6x | 0.49 | por debajo del sector |
| Crecimiento | 17.7% | 12.0% | 1.47 | por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=17.64% |
| Flujo de caja operativo positivo | ✅ | FCO=182,935,000,000 |
| ROA en mejora | ✅ | 16.45% → 17.64% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 6.49% → 4.10% |
| Ratio corriente en mejora | ❌ | 1.35 → 1.23 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ❌ | 68.82% → 67.94% |
| Rotación de activos en mejora | ❌ | 0.46x → 0.44x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia +30.0 · macd -15.9 · rsi +11.8 · bollinger -1.4 · momentum precio -12.4 → **+12.14**

SMA50 +9.0% · SMA200 +14.4% · rango 52s 71% · volatilidad anual 43.9% · momentum relativo 12m -18.6%

- Tendencia alcista confirmada: precio 491.50 > SMA50 450.85 > SMA200 429.52
- MACD bajista (histograma -4.004, 0.40 ATR)
- RSI en zona alcista saludable (56.4, entre 50 y 70)
- Precio en el 43% del canal de Bollinger
- Momentum 12m (excl. último mes) -1.0% frente al +17.7% de SPY: exceso -18.6%

**Lectura:** La cotización de MSFT en $491.50 mantiene una estructura de tendencia alcista confirmada con el precio por encima de sus medias móviles y un RSI neutral de 56.4, lo que indica que no presenta sobreextensión a pesar de la divergencia del histograma MACD en -4.004 y una puntuación de momentum de +12.1/100 que refleja un impulso moderado. La aportación de los bloques muestra un soporte positivo de la tendencia de 30.0 y del RSI en 11.83, mientras que el momentum de precio aporta -12.42 y el MACD -15.9, configurando un escenario donde el gestor debe valorar una sostenibilidad contenida para el dimensionamiento de su posición.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| minimo_10 | $487.31 |
| minimo_21 | $476.25 |
| bb_inferior | $474.32 |
| sma_50 | $450.85 |
| sma_200 | $429.52 |
| minimo_63 | $348.54 |

- Soporte más cercano minimo_10 en $487.31, a 0.85% (0.42 ATR)
- Otros soportes por debajo: minimo_21 $476.25, bb_inferior $474.32, sma_50 $450.85
- Estructura: PEGADO_AL_SOPORTE

**Lectura:** La cotización de MSFT se encuentra actualmente pegada al soporte estructural más cercano situado en cuatrocientos ochenta y siete dólares con treinta y uno centavos, nivel que dista un cero coma nueve por ciento o cero coma cuarenta y dos veces el ATR por debajo del precio actual de cuatrocientos noventa y uno dólares con cincuenta centavos. Por debajo de esta referencia inmediata se encuentran sucesivamente el mínimo de veintiún sesiones en cuatrocientos setenta y seis dólares con veinticinco centavos, la banda inferior de volatilidad en cuatrocientos setenta-cuatro dólares con treinta y dos centavos y la media móvil simple de cincuenta sesiones en cuatrocientos cincuenta dólares con ochenta y cinco centavos, mientras que no se dispone de ninguna referencia técnica por encima.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado no resulta aplicable debido a una divergencia en la serie histórica del proveedor que impide evaluar con fiabilidad la volatilidad implícita y la curva. En cuanto al valor, la volatilidad realizada de MSFT se sitúa en el 43.9% mientras que la volatilidad relativa al mercado figura como no disponible, manteniéndose la puerta de régimen abierta.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 1,340,368 · histórico acumulado 0/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 0.5356 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 0.6851 | — | — |
| Skew (IV put OTM − call OTM) | 0.0625 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | 0.2409 | — | comparable sin histórico |

**Posición en el canal de open interest: 16%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $480.00 · resistencia OI $550.00 · max pain $445.00 · punto de inflexión de gamma $448.42

Régimen de gamma **AMORTIGUADO** (exposición 623,336,828 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | +0.67 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | +0.92 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.24 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro +0.10 · opciones +0.64 · técnico +0.12 → media +0.29, confluencia 33% sobre 3 componente(s) → **ESPERAR_RETROCESO**

Ajuste bruto hasta el nivel -0.85% × factor 1.0 = **-0.85%** → entrada objetivo $487.31

**Lectura:** El posicionamiento moderado en futuros y el régimen gamma amortiguado de 623,336,828 dólares de delta por cada uno por ciento de movimiento del subyacente coinciden con un sesgo de opciones muy favorable que permite buscar una mejor cotización. Dado que la decisión exige esperar un retroceso con un ajuste del menos cero coma ochenta y cinco por ciento, la entrada se programa al precio objetivo de 487 dólares con 31 centavos apoyado en soporte estructural, situándose por debajo de los 491 dólares con 50 centavos de mercado y respetando los niveles de soporte en 480 dólares, max pain en 445 dólares y el punto de inflexión de gamma en 448 dólares con 42 centavos.


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-08-28` **RESULTADOS** · NEUTRA · p=0.06 · _Yahoo Finance_ — [Why Is Microsoft (MSFT) Up 12% Since Last Earnings Report? - Yahoo Finance](https://news.google.com/rss/articles/CBMilwFBVV95cUxObVp5azE0RFpsQkFwRXkyenRjTXYzWWI1QXdSc19LUldtNy1ybUNYYU4zYWEzak8ycmhRV29qSjZ0Rm16WUFDM2xJaVJaQ3p1X3lCVzUxNUNZaWQwYzUxOE10ZzFZMHFLUUdUNUZrTU5Na2Q0aFFkQi1BeEZJdlh5aVdnR0xsTFpMdHQtZ1kwSHFIWHlzV19v?oc=5)
- `2026-09-03` **OTROS** · NEUTRA · p=0.03 · _Yahoo Finance_ — [Microsoft Corporation (MSFT) Generates Revenues and Profits Beyond AI Theme - Yahoo Finance](https://news.google.com/rss/articles/CBMirwFBVV95cUxNencwUUFlUkw5TkE5UXlqNmFXQkU1RVNZcTRwVENtTVNIc2YyWUVrZGQ1UWRPUXpWQjdTSnZ2eG91dThjeDd1OEJ3aGxUU2drS3pGblZpNUl1SnJLbEh1WmF3RV9LZ2x0SWw0RS1oSnNWSFA0ak5EU2oxM0dzT21XMEFSdkxnektMSFhHT2tERUhMUS1lQk5KZnFqNjM3OU9Wb0pHZG5uQnFyNUwyUlhB?oc=5)
- `2026-09-02` **OTROS** · NEUTRA · p=0.02 · _Seeking Alpha_ — [Microsoft modifies business segment structure ahead of Q1 results - Seeking Alpha](https://news.google.com/rss/articles/CBMipgFBVV95cUxOU2Uxa1F5NkU3OEwyM3JHdl9oYjhheTJDNXJHcnZvangtUWYwY3dnVHBxUG9aVkxrVENOYnh5NFUyNC14NXBReE9aTTFpbFdPNndXWEJWWS00T0hpQkRVeUd2bGxXSFhjeVNaUDNMa2dzR0NZajdTMk5KenR0NTQ4NVNzRGJxNzZwbVdJOW5GSm5lbUw5SHkxV3FmMEFtMDBvTk9mNFBn?oc=5)

_Fuentes sin respuesta: tavily._

**Lectura:** El informe sobre Microsoft Corporation presenta una probabilidad de impacto en el precio BAJA de 0.14 con dirección probable BAJISTA y un desequilibrio de -1.00, basándose en doce noticias analizadas en treinta días que incluyen modificaciones en su estructura de segmentos de negocio y análisis de beneficios más allá de la inteligencia artificial según Yahoo Finance y Seeking Alpha. Cabe destacar que el informe se encuentra degradado debido a que la fuente tavily no respondió, lo que refleja que el silencio del buscador no constituye una ausencia de noticias.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos sólido del 17.7%, por encima del sector (mediana de Technology: 12%).
- Margen neto muy alto del 40.3%, muy por encima del sector.
- ROIC del 28.5%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 68%, indicio de poder de fijación de precios.
- PEG de 0.86 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Estructura técnica alcista confirmada con puntuación de momentum +12.1/100 y RSI de 56.4 (alcista saludable).
- Solvencia 78.8/100: el balance aguanta un escenario adverso sin comprometer la tesis.

**🐻 Bajista**

- 2 discrepancia(s) entre proveedores de datos; confianza del 95%.
- Flujo de noticias con probabilidad de impacto BAJA (0.14) y sesgo BAJISTA sobre 12 nota(s); principal catalizador: "Why Is Microsoft (MSFT) Up 12% Since Last Earnings Report? - Yahoo Finance" (capa asesora: no altera el dictamen).

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 9% en dos trimestres consecutivos.
- Que el margen neto baje del 24.2%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($429.52) con volumen creciente.

**Síntesis:** La tesis alcista para MSFT destaca fundamentales sólidos, subrayados por un crecimiento de ingresos del 17.7% que supera al sector, un margen neto del 40.3% y un ROIC del 28.5% que confirma la creación de valor sobre el coste de capital de referencia del 9%. En contraste, la tesis bajista no aporta argumentos cuantitativos propios basados en los datos, limitándose a señalar una confianza del 95% con dos discrepancias entre proveedores y un flujo de noticias con probabilidad de impacto baja de 0.14 y sesgo bajista sobre 12 notas. Por tanto, la conclusión del debate queda sostenida por la robustez de los métricos operativos y de solvencia de 78.8/100 frente a un entorno informativo adverso pero de bajo impacto estimado.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **65.1** × 0.65 + momentum normalizado **56.1** × 0.35 = **61.9**/100 → **COMPRA**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

convicción ×0.877 · riesgo 0.658% · stop a 5.2% → 12.74% · volatilidad ×0.569 · datos ×0.948 · banderas ×1.0 · extensión ×1.0 → **6.87%**

_riesgo por posición 0.66% sobre un stop al 5.2%, escalado por volatilidad ×0.57_

R:R 2.0 → exige acertar el **33.3%** de las veces para no perder dinero. Horizonte 252 sesiones (~12.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_MSFT: fundamentales aprobados; estilo CALIDAD_COMPUESTA con convicción 65.1/100 y momentum NEUTRAL (+12.1/100). Síntesis del debate: La tesis alcista para MSFT destaca fundamentales sólidos, subrayados por un crecimiento de ingresos del 17.7% que supera al sector, un margen neto del 40.3% y un ROIC del 28.5% que confirma la creación de valor sobre el coste de capital de referencia del 9%. En contraste, la tesis bajista no aporta argumentos cuantitativos propios basados en los datos, limitándose a señalar una confianza del 95% con dos discrepancias entre proveedores y un flujo de noticias con probabilidad de impacto baja de 0.14 y sesgo bajista sobre 12 notas. Por tanto, la conclusión del debate queda sostenida por la robustez de los métricos operativos y de solvencia de 78.8/100 frente a un entorno informativo adverso pero de bajo impacto estimado._


</details>

**Lectura:** Ordenamos ejecutar una compra de MSFT asignando el 6.87 por ciento de la cartera al precio actual de 491.50 dólares, respaldada por una convicción fundamental de 65 sobre 100 y un momentum de 12 sobre 100, sin que se hayan registrado vetos ni banderas rojas que condicionen la operación. La gestión del riesgo queda estrictamente limitada por un nivel de stop en 462.13 dólares y un objetivo de precio situado en 537.66 dólares, lo que configura una relación de riesgo recompensa de 2.00 en un horizonte temporal de 252 sesiones. La mesa ejecutará esta orden bajo los parámetros descritos de estilo calidad compuesta, vigilando el cumplimiento estricto de las fronteras operativas establecidas para este activo.

---

### MU — Micron Technology, Inc.

Technology / Semiconductors · confianza en datos 86% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `COMPRA` · peso 0.00%
entrada $978.68 (-0.44% sobre $983.02) · stop $868.60 (2.5·ATR) · objetivo $1,198.83 (5.0·ATR) · R:R 2.0 · 252 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 55.9% vs 5.0% ✅; Crecimiento de ingresos 345.7% vs 5.0% ✅; Deuda / Patrimonio 0.06x vs 3.00x ✅ |
| Calidad y valoración | `CALIDAD_COMPUESTA` · convicción **62**/100 | calidad 83 · valoración 31 · crecimiento 90 · solvencia 86 · F-Score 8/9 · Altman 6.1 (SEGURA) · cobertura 100% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `ALCISTA_FUERTE` +68.0/100 | RSI 51.4 (ALCISTA_SALUDABLE) · tendencia ALCISTA_CONFIRMADA · ATR $44.03 (4.5%) · SMA200 +59.0% · ⚠️ sobreextendido |
| Estructura | `APOYADO` | soporte sma_50 $929.86 · a 5.4% (1.21 ATR) |
| Posicionamiento | `ESPERAR_RETROCESO` -0.44% | macro NEUTRO (+0.10) · opciones PRECIO_ADVERSO (-0.25) · gamma AMORTIGUADO · nivel GAMMA_FLIP $978.68 |
| Noticias _(asesora)_ | `BAJA` 0.15 · ALCISTA | 12 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 8 vs 🐻 1 | La tesis alcista para Micron Technology destaca un crecimiento de ingresos excepcional del 345.7% frente al 12% de la mediana del sector, acompañado de un margen neto muy alto del 55.9% y un margen bruto del 73% que refl |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 8/9 | FUERTE |
| Altman | Z'' (no manufactureras) | 6.1 | SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $297.83 | margen -230.1% · 2/5 defensivos |
| Greenblatt | EBIT/EV | 0.9% | bajo umbral |
| Buffett | ROIC | 15.0% | +6.0% sobre el coste de capital |
| Buffett | Margen bruto | 72.6% | indicio de foso · FCF yield 0.1% · dilución +1.19% |
| Lynch | PEG | 0.02 | MUY_ATRACTIVO · CRECIMIENTO_RAPIDO (sobre beneficio) |
| Sloan | Devengos | -10.8% | beneficio respaldado por caja |

**Estilo `CALIDAD_COMPUESTA`** — Calidad 83.1/100 y solvencia 85.5/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción: bruta 72.1 × cobertura 1.0 × confianza 0.86 − 0.0 por banderas = **62.0**._

**Contexto sectorial (Technology)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 22.3x | 26.0x | 0.86 | por debajo del sector |
| Margen neto | 55.9% | 15.0% | 3.73 | muy por encima del sector |
| Deuda/Patrimonio | 0.1x | 0.6x | 0.11 | por debajo del sector |
| Crecimiento | 345.7% | 12.0% | 28.81 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=10.31% |
| Flujo de caja operativo positivo | ✅ | FCO=17,525,000,000 |
| ROA en mejora | ✅ | 1.12% → 10.31% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 16.19% → 13.93% |
| Ratio corriente en mejora | ❌ | 2.64 → 2.52 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ✅ | 22.35% → 39.79% |
| Rotación de activos en mejora | ✅ | 0.36x → 0.45x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia +30.0 · macd +5.9 · rsi +8.8 · bollinger +3.3 · momentum precio +20.0 → **+67.98**

SMA50 +5.7% · SMA200 +59.0% · rango 52s 76% · volatilidad anual 93.6% · momentum relativo 12m +534.3%

- Tendencia alcista confirmada: precio 983.02 > SMA50 929.86 > SMA200 618.12
- MACD alcista (histograma +6.445, 0.15 ATR)
- RSI en zona alcista saludable (51.4, entre 50 y 70)
- Precio en el 66% del canal de Bollinger
- Momentum 12m (excl. último mes) +552.0% frente al +17.7% de SPY: exceso +534.3%

**Lectura:** La estructura de MU presenta un momentum de ALCISTA_FUERTE con una puntuación de +68.0/100, respaldada por una tendencia alcista confirmada donde el precio de $983.02 cotiza holgadamente por encima de su SMA50 de $929.86 y su SMA200 de $618.12, aunque el RSI se sitúa en un nivel neutral de 51.4 y el valor está sobreextendido, lo que sugiere moderar el tamaño de la posición ante el potencial agotamiento del impulso.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| sma_50 | $929.86 |
| minimo_10 | $906.89 |
| bb_inferior | $897.47 |
| minimo_21 | $844.62 |
| minimo_63 | $737.88 |
| sma_200 | $618.12 |

- Soporte más cercano sma_50 en $929.86, a 5.41% (1.21 ATR)
- Otros soportes por debajo: minimo_10 $906.89, bb_inferior $897.47, minimo_21 $844.62
- Estructura: APOYADO

**Lectura:** Con un precio actual de $983.02 y un ATR de $44.03, la cotización de MU se encuentra apoyada sobre el nivel más cercano por debajo situado en $929.86, correspondiente al origen sma_50 y ubicado a una distancia del 5.4% que equivale a 1.21 ATR. Por debajo de esta referencia estructural inicial, la serie temporal cuenta con otros soportes adicionales como el minimo_10 en $906.89, la banda inferior de volatilidad en $897.47 y el minimo_21 en $844.62, mientras que la primera referencia por encima figura como no disponible.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado para MU resulta no aplicable debido a una divergencia vintage en la serie VIXCLS que impide la lectura de la volatilidad implícita y de la pendiente de su curva. La volatilidad realizada del valor se sitúa en 93.6%, con la volatilidad implícita y relativa al mercado no disponibles, mientras la puerta de régimen se mantiene abierta.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 1,235,794 · histórico acumulado 0/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 1.2965 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 0.7734 | — | — |
| Skew (IV put OTM − call OTM) | -0.007141 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | -0.0131 | — | comparable sin histórico |

**Posición en el canal de open interest: 77%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $600.00 · resistencia OI $1,100.00 · max pain $810.00 · punto de inflexión de gamma $978.68

Régimen de gamma **AMORTIGUADO** (exposición 20,878,240 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | -0.53 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | -0.09 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.02 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro +0.10 · opciones -0.25 · técnico +0.68 → media +0.18, confluencia 33% sobre 3 componente(s) → **ESPERAR_RETROCESO**

Ajuste bruto hasta el nivel -0.44% × factor 1.0 = **-0.44%** → entrada objetivo $978.68

**Lectura:** El sesgo neutral del posicionamiento en futuros junto con el régimen de gamma amortiguado de veintumillonesochocientossetentayochochocientoscuarenta dólares de delta por cada uno por ciento de movimiento del subyacente marca únicamente la dirección del viento, mientras que el precio adverso en la cadena exige esperar al retroceso indicado. La entrada se realiza aplicando un ajuste de menos cero coma cuarenta y cuatro por ciento que fija el precio objetivo en novecientos setenta y ocho con sesenta y ocho dólares apoyado en el punto de inflexión de gamma, ya que perseguir el mercado actual resulta costoso debido a la posición bajista de la cadena.


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-08-26` **RESULTADOS** · NEUTRA · p=0.05 · _Yahoo Finance_ — [Micron Technology to Report Fiscal Fourth Quarter Results on September 30, 2026 - Yahoo Finance](https://news.google.com/rss/articles/CBMioAFBVV95cUxPQTYwSjVPX3l0aEUtdmkxZzJ1cUxzeUxOckxBZXk4aDBvb2RxSVhjUE9QWDlTSWhOMlA0N3hrVnpXTlp2emc0NHdBZDlfYXRLQWNudWw4ckU0WHBpb1ZzaVpFSU5wWDhVVVh1eXBUMFZydXZJYTVnRDdiamlxSm1fVWd1T0tYSkszbFNGZzhaelc5a1VacDFKX21JODE5dzU2?oc=5)
- `2026-09-09` **OTROS** · NEUTRA · p=0.05 · _Stocktwits_ — [Top After-Hours Gainers Today Beyond Micron: QCOM, AMAT, LRCX Surge - Stocktwits](https://news.google.com/rss/articles/CBMixwFBVV95cUxPOGFLWk5MLTNnZnZhU0l6TWtOdTdvT0RVU0JwcFlfdXd0UnpaVnUwSk1oX2FvcGFZUml2Wkl5Q0VCMGt6WU1HUnBrMjhFMVcxc1FfcnhyZXZzU3RwemJJTUVDRDIycUJBLUk2MktRU1FYV3pxa1c3M0lIVjQ1SWR6bjEtUk90bWdNeGJoMmRiNlhEWmpFRVg0RUd0TlRCcENuR1Zmd1V3eVdncXh2RFE0SzNrNmh1cXQzN2lBcWw2ZWVzYlJHVmdB?oc=5)
- `2026-09-03` **OTROS** · NEUTRA · p=0.03 · _Seeking Alpha_ — [Micron: The Q4 Report Has Impossible Expectations (NASDAQ:MU) - Seeking Alpha](https://news.google.com/rss/articles/CBMikwFBVV95cUxOZ1BuYjZpRVBtYVpqSmtWaTJkRlFsenJ1ZERyUDk0Wk1qYkZOX21pWHB3VTRhdHhNUDlqVTM0WkhXUENrSTV3U2U4Tndqd1JwcWFPengweExYNHhabmpnSnBMRWpnTUZ2MEtRQmlGMUJiYnh4WXo0UFRsVTRoNlZfeUtjNGxiVUJITlBmc3NHUFc5TTA?oc=5)

_Fuentes sin respuesta: tavily._

**Lectura:** Micron Technology registra una probabilidad de impacto en el precio baja de cero coma quince con dirección alcista basada en doce noticias analizadas en treinta días, aunque el informe está degradado debido a que la fuente tavily no respondió. Los catalizadores incluyen el anuncio de resultados del cuarto trimestre fiscal para el treinta de septiembre de dos mil veintiséis en Yahoo Finance, movimientos bursátiles tras el cierre en Stocktwits y análisis de expectativas imposibles en Seeking Alpha.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos excepcional del 345.7%, muy por encima del sector (mediana de Technology: 12%).
- Margen neto muy alto del 55.9%, muy por encima del sector.
- Margen bruto del 73%, indicio de poder de fijación de precios.
- F-Score de Piotroski 8/9: la calidad contable mejora en rentabilidad, apalancamiento y eficiencia a la vez.
- PEG de 0.02 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Estructura técnica alcista confirmada con puntuación de momentum +68.0/100 y RSI de 51.4 (alcista saludable).
- Solvencia 85.5/100: el balance aguanta un escenario adverso sin comprometer la tesis.
- Flujo de noticias con probabilidad de impacto BAJA (0.15) y sesgo ALCISTA sobre 12 nota(s); principal catalizador: "Micron Technology to Report Fiscal Fourth Quarter Results on September 30, 2026 - Yahoo Finance" (capa asesora: no altera el dictamen).

**🐻 Bajista**

- 3 discrepancia(s) entre proveedores de datos; confianza del 86%.

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 173% en dos trimestres consecutivos.
- Que el margen neto baje del 33.5%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($618.12) con volumen creciente.

**Síntesis:** La tesis alcista para Micron Technology destaca un crecimiento de ingresos excepcional del 345.7% frente al 12% de la mediana del sector, acompañado de un margen neto muy alto del 55.9% y un margen bruto del 73% que refleja poder de fijación de precios. Estos fundamentales se ven respaldados por un F-Score de Piotroski de 8 sobre 9, un PEG de 0.02, una solvencia de 85.5 sobre 100 y una estructura técnica alcista con un momentum de +68.0 sobre 100 y un RSI de 51.4, mientras que la tesis bajista se limita a señalar tres discrepancias entre proveedores de datos con una confianza del 86% y un flujo de noticias con probabilidad de impacto baja de 0.15 y sesgo alcista sobre 12 notas. El dictamen queda condicionado a vigilar que el crecimiento de ingresos no caiga por debajo del 173% en dos trimestres consecutivos, que el margen neto no baje del 33.5%, que el ROIC no caiga por debajo del coste de capital de referencia del 9%, que no aparezca deterioro en el F-Score o en los devengos, y que el precio no pierda la media de 200 sesiones situada en 618.12 dólares con volumen creciente.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **62.0** × 0.65 + momentum normalizado **84.0** × 0.35 = **69.7**/100 → **COMPRA**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

`peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

convicción ×0.8 · riesgo 0.6% · stop a 11.2% → 5.33% · volatilidad ×0.267 · datos ×0.86 · banderas ×1.0 · extensión ×0.7 → **0.00%**

_peso calculado 0.86% por debajo del mínimo operable 1.00%: el coste de operar supera la aportación_

R:R 2.0 → exige acertar el **33.3%** de las veces para no perder dinero. Horizonte 252 sesiones (~12.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_MU: fundamentales aprobados; estilo CALIDAD_COMPUESTA con convicción 62.0/100 y momentum ALCISTA_FUERTE (+68.0/100). Síntesis del debate: La tesis alcista para Micron Technology destaca un crecimiento de ingresos excepcional del 345.7% frente al 12% de la mediana del sector, acompañado de un margen neto muy alto del 55.9% y un margen bruto del 73% que refleja poder de fijación de precios. Estos fundamentales se ven respaldados por un F-Score de Piotroski de 8 sobre 9, un PEG de 0.02, una solvencia de 85.5 sobre 100 y una estructura técnica alcista con un momentum de +68.0 sobre 100 y un RSI de 51.4, mientras que la tesis bajista se limita a señalar tres discrepancias entre proveedores de datos con una confianza del 86% y un flujo de noticias con probabilidad de impacto baja de 0.15 y sesgo alcista sobre 12 notas. El dictamen queda condicionado a vigilar que el crecimiento de ingresos no caiga por debajo del 173% en dos trimestres consecutivos, que el margen neto no baje del 33.5%, que el ROIC no caiga por debajo del coste de capital de referencia del 9%, que no aparezca deterioro en el F-Score o en los devengos, y que el precio no pierda la media de 200 sesiones situada en 618.12 dólares con volumen creciente._


</details>

**Lectura:** La mesa ejecutará una postura de compra bajo el estilo de calidad compuesta en MU, operando con una asignación de 0.00% de la cartera a partir de un precio de 983.02 dólares por acción, sin que medie ningún veto ni bandera roja en esta decisión. Se establece un nivel de stop en 868.60 dólares y un objetivo técnico en 1198.83 dólares, lo que configura una relación de riesgo y recompensa de 2.00 respaldada por una convicción fundamental de 62 sobre 100 y un momentum de más 68 sobre 100. Esta directriz operativa se desarrollará estrictamente dentro de un horizonte temporal de 252 sesiones.

---

### CEG — Constellation Energy Corporatio

Utilities / Utilities - Independent Power Producers · confianza en datos 94% · fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

### 🎯 `VENTA` · peso 0.00%
entrada $289.36 (n/d sobre $289.36) · stop $271.04 (2.0·ATR) · objetivo $321.42 (3.5·ATR) · R:R 1.75 · 126 sesiones

| Bloque | Veredicto | Claves |
| :--- | :--- | :--- |
| Filtro fundamental | ✅ APROBADO | Margen neto 11.1% vs 5.0% ✅; Crecimiento de ingresos 23.0% vs 5.0% ✅; Deuda / Patrimonio 0.76x vs 5.00x ✅ |
| Calidad y valoración | `MIXTA` · convicción **42**/100 | calidad 44 · valoración 34 · crecimiento 45 · solvencia 61 · F-Score 6/9 · Altman 1.65 (GRIS) · cobertura 96% |
| Régimen | `NO_APLICABLE` | VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio. |
| Técnico | `BAJISTA` -24.4/100 | RSI 63.5 (ALCISTA_SALUDABLE) · tendencia BAJISTA_CONFIRMADA · ATR $9.16 (3.2%) · SMA200 -1.8% |
| Estructura | `HOLGADO` 🚫 | soporte sma_50 $268.37 · a 7.3% (2.29 ATR) · primera referencia arriba $294.70 |
| Posicionamiento | `NO_APLICABLE` | macro VIENTO_EN_CONTRA (-0.34) · opciones NEUTRO (-0.09) · gamma AMORTIGUADO · el sesgo agregado no es alcista: no hay entrada que optimizar |
| Noticias _(asesora)_ | `BAJA` 0.03 · ALCISTA | 2 nota(s) en 30 días · fuentes: sec_8k, google_news_rss |
| Debate | 🐂 3 vs 🐻 4 | El análisis de Constellation Energy Corporation muestra un dinamismo operativo sobresaliente, respaldado por un crecimiento de ingresos del 23.0% que supera con amplitud la mediana sectorial del 4% y un margen neto acept |

<details><summary>Calidad y valoración — las siete escuelas</summary>

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 6/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 1.65 | GRIS (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $143.93 | margen -101.0% · 1/5 defensivos |
| Greenblatt | EBIT/EV | 3.1% | bajo umbral |
| Buffett | ROIC | 13.4% | +4.4% sobre el coste de capital |
| Buffett | Margen bruto | 22.1% | sin foso · FCF yield 1.3% · dilución -0.18% |
| Lynch | PEG | None | NO_EVALUABLE · EN_CONTRACCION (sobre beneficio) |
| Sloan | Devengos | -3.4% | beneficio respaldado por caja |

**Estilo `MIXTA`** — Perfil sin dominancia clara (calidad 43.7, valoración 33.5, crecimiento 44.6, solvencia 61.0).

_Convicción: bruta 44.8 × cobertura 1.0 × confianza 0.94 − 0.0 por banderas = **42.1**._

**Contexto sectorial (Utilities)**

| Métrica | Valor | Mediana sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 28.3x | 18.0x | 1.57 | muy por encima del sector |
| Margen neto | 11.1% | 11.0% | 1.01 | en línea con el sector |
| Deuda/Patrimonio | 0.8x | 1.5x | 0.51 | por debajo del sector |
| Crecimiento | 23.0% | 4.0% | 5.75 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**Desglose del F-Score**

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=4.05% |
| Flujo de caja operativo positivo | ✅ | FCO=4,237,000,000 |
| ROA en mejora | ❌ | 7.08% → 4.05% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 13.95% → 12.66% |
| Ratio corriente en mejora | ❌ | 1.57 → 1.53 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ❌ | 25.42% → 18.38% |
| Rotación de activos en mejora | ✅ | 0.45x → 0.45x |


</details>

<details><summary>Análisis técnico</summary>

**Aportes a la puntuación:** tendencia -30.0 · macd +5.0 · rsi +16.1 · bollinger +4.5 · momentum precio -20.0 → **-24.38**

SMA50 +7.8% · SMA200 -1.8% · rango 52s 34% · volatilidad anual 35.1% · momentum relativo 12m -30.2%

- Tendencia bajista confirmada: precio 289.36 < SMA200 294.70 y SMA50 268.37 por debajo de la SMA200
- MACD alcista (histograma +1.154, 0.13 ATR)
- RSI en zona alcista saludable (63.5, entre 50 y 70)
- Precio en el 73% del canal de Bollinger
- Momentum 12m (excl. último mes) -12.6% frente al +17.7% de SPY: exceso -30.2%

**Lectura:** La estructura de tendencia bajista confirmada y la puntuación de momentum de -24.4/100 reflejan la inercia del precio cotizando por debajo de su SMA200 de $294.70, a pesar de que el RSI se sitúa en un nivel neutral de 63.5 y el MACD muestra un histograma positivo de +1.154. Con el precio en $289.36 y sin estar sobreextendido, el activo se encuentra en el 34% de su rango de 52 semanas, apoyado por una SMA50 en $268.37 que evidencia una recuperación en curso tras caídas previas.


</details>

<details><summary>Estructura de precio y soportes</summary>

| Candidato | Nivel |
| :--- | ---: |
| sma_50 | $268.37 |
| minimo_10 | $268.00 |
| minimo_21 | $264.82 |
| bb_inferior | $263.55 |
| minimo_63 | $228.28 |

- Soporte más cercano sma_50 en $268.37, a 7.26% (2.29 ATR)
- Otros soportes por debajo: minimo_10 $268.00, minimo_21 $264.82, bb_inferior $263.55
- Primera referencia por encima: $294.70
- Estructura: HOLGADO — SOPORTE LEJANO: prohíbe perseguir el precio

**Lectura:** El precio actual de CEG se sitúa en doscientos ochenta y nueve con treinta y seis dólares, quedando el soporte estructural más cercano en el origen sma_50 a doscientos sesenta y ocho con treinta y siete dólares, lo que representa una distancia del siete con tres por ciento o dos con veintinueve ATR. Esta configuración de soporte lejano prohíbe perseguir el precio al cotizar el valor sin una referencia estructural inmediata por debajo, encontrándose la primera referencia por encima en doscientos noventa y cuatro con setenta dólares.

</details>

<details><summary>Régimen de volatilidad del mercado</summary>

- Régimen no evaluable: VIXCLS: VintageDivergente: VIXCLS 2026: la redescarga devuelve un contenido distinto del cacheado (bf5ea5cf6e5eaaaa -> 511e87d51816d5b1). El proveedor ha revisado historia ya consumida. No se sobrescribe: revísalo antes de reejecutar el estudio.

Ventana del z-score: 60 sesiones sobre 0 observación(es) publicadas.

El régimen describe el MERCADO, no la empresa, y solo puede RECORTAR: PANICO topa el dictamen en MANTENER y TENSION en COMPRA; la puerta cerrada prohíbe perseguir el precio. Ningún régimen mejora un dictamen.

**Lectura:** El régimen de mercado no es aplicable debido a una divergencia en la serie histórica del proveedor que impide evaluar con fiabilidad la volatilidad implícita y la pendiente de su curva. Para CEG, que registra una volatilidad realizada del 35.1% con la volatilidad relativa al mercado no disponible y puerta de régimen abierta, esta falta de datos impide validar las condiciones de estrés inmediato.

</details>

<details><summary>Posicionamiento en derivados y precio de entrada</summary>

**Posicionamiento en futuros (COT de la CFTC, no comerciales)**

| Contrato | Papel | z-score | Semanas | Informe | Publicado | Extremo |
| :--- | :--- | ---: | ---: | :--- | :--- | :---: |
| `ES=F` | indice | +0.15 | 156 | 2026-09-01 | 2026-09-04 | — |
| `NG=F` | sectorial | -1.57 | 156 | 2026-09-01 | 2026-09-04 | — |

**Cadena de opciones**

Open interest agregado 70,717 · histórico acumulado 0/60 días

| Métrica | Valor | Percentil | Estado |
| :--- | ---: | ---: | :--- |
| Put/call (open interest) | 0.9963 | n/d | DATOS_INSUFICIENTES |
| Put/call (volumen) | 0.675 | — | — |
| Skew (IV put OTM − call OTM) | -0.030518 | n/d | SIN_HISTORICO |
| Skew ÷ volatilidad ATM | -0.0621 | — | comparable sin histórico |

**Posición en el canal de open interest: 49%** (0% = sobre el soporte, 100% = contra la resistencia)

Niveles: soporte OI $260.00 · resistencia OI $320.00 · max pain $280.00 · punto de inflexión de gamma $284.26

Régimen de gamma **AMORTIGUADO** (exposición 5,636,621 $ por 1%). _creadores de mercado largos gamma en calls y cortos en puts; es la convencion estandar, no una medicion_

**De dónde sale el sesgo de la cadena**

| Componente | Valor | Peso | Lectura |
| :--- | ---: | ---: | :--- |
| canal_oi | +0.02 | 0.35 | posicion del precio entre el soporte y la resistencia de open interest |
| skew_normalizado | -0.39 | 0.25 | skew dividido por la volatilidad at-the-money |
| gamma_flip | +0.08 | 0.2 | por encima del punto de inflexion (lectura atenuada) |

_Se promedian solo los componentes disponibles, con sus pesos renormalizados. Todos se leen en clave contraria: este bloque puntúa si el precio es un buen sitio para comprar, no si la tendencia sube._

**Confluencia de tres vías**

macro -0.34 · opciones -0.09 · técnico -0.24 → media -0.23, confluencia n/d sobre 3 componente(s) → **NO_APLICABLE**

_Sin ajuste de entrada: el sesgo agregado no es alcista: no hay entrada que optimizar. La entrada se toma al precio de mercado._

**Lectura:** Posicionamiento de CEG: sesgo macro VIENTO_EN_CONTRA (-0.34) y cadena de opciones NEUTRO. No se emite ajuste de entrada: el sesgo agregado no es alcista: no hay entrada que optimizar. La entrada se toma al precio de mercado ($289.36).


</details>

<details><summary>Noticias (capa asesora)</summary>

- `2026-09-09` **OTROS** · NEUTRA · p=0.03 · _finance.biggo.com_ — [US Finalizes $1.9 Billion Loan to Restart Iowa Nuclear Plant for Google - finance.biggo.com](https://news.google.com/rss/articles/CBMidkFVX3lxTE9XR3NrajFUbkY4X1VubWpMNzVZSjVnd19TMjlrTnJhX2VySElyaW5JNVJyeGQxbUJ5UU50WGZFRUI3QlBIOHFSbS1KVDI0NWI5N2M4ajNGS2dOUHBpYUM0RkRDZi1XRnFJUmdtTDRZdWV1VHJUcWc?oc=5)
- `2026-08-16` **OTROS** · ALCISTA · p=0.00 · _finance.biggo.com_ — [Nuclear Power Operators Emerge as Prime AI Infrastructure Bets as Hyperscaler Demand Surges - finance.biggo.com](https://news.google.com/rss/articles/CBMidkFVX3lxTE5oODNYNHRZaUFFTnNBNFNFLUtlcE5hUE53YjN5Q3oxNmZPQUdfYjlMdy1hS0tzNGtKc0xfNWc1SWZHQnhYcGV0UUQ1cEsteHJacXRTOEMxbC1BbW94SE9SYXFuMWY4bHo4MjZwSXNWS1Y0Mm9ocXc?oc=5)

_Fuentes sin respuesta: tavily._

**Lectura:** Constellation Energy Corporation registra dos noticias recientes en un entorno informativo degradado por la falta de respuesta de tavily, destacando el préstamo federal para reiniciar la planta nuclear de Iowa con el fin de abastecer a Google y el posicionamiento del sector ante la demanda de los hiperescaladores. Estos acontecimientos generan una probabilidad de impacto en el precio baja de 0.03 y una dirección probable alcista con un desequilibrio de 1.00, reflejando el atractivo de los operadores nucleares como infraestructura clave para la inteligencia artificial.


</details>

<details><summary>Debate y condiciones de invalidación</summary>

**🐂 Alcista**

- Crecimiento de ingresos sólido del 23.0%, muy por encima del sector (mediana de Utilities: 4%).
- Margen neto aceptable del 11.1%, en línea con el sector.
- Flujo de noticias con probabilidad de impacto BAJA (0.03) y sesgo ALCISTA sobre 2 nota(s); principal catalizador: "US Finalizes $1.9 Billion Loan to Restart Iowa Nuclear Plant for Google - finance.biggo.com" (capa asesora: no altera el dictamen).

**🐻 Bajista**

- P/E de 28.3x frente a una mediana sectorial de 18x (1.6 veces la norma de Utilities): la valoración descuenta una ejecución impecable.
- Altman Z'' (no manufactureras) en zona gris (1.65): solvencia sin margen cómodo.
- Estructura técnica en bajista confirmada: el precio cotiza por debajo de su media de 200 sesiones.
- 2 discrepancia(s) entre proveedores de datos; confianza del 94%.

**Invalidarían la tesis:**

- Que el crecimiento de ingresos caiga por debajo del 12% en dos trimestres consecutivos.
- Que el margen neto baje del 6.6%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que el precio pierda la media de 200 sesiones ($294.7) con volumen creciente.

**Síntesis:** El análisis de Constellation Energy Corporation muestra un dinamismo operativo sobresaliente, respaldado por un crecimiento de ingresos del 23.0% que supera con amplitud la mediana sectorial del 4% y un margen neto aceptable del 11.1% en línea con el sector, impulsado además por un flujo de noticias de sesgo alcista y baja probabilidad de impacto. Sin embargo, este desempeño convive con vulnerabilidades significativas reflejadas en un ratio P/E de 28.3x que duplica ampliamente la mediana sectorial de 18x, una puntuación Altman Z de insolvencia situada en la zona gris de 1.65 y una estructura técnica bajista confirmada por la cotización por debajo de su media de 200 sesiones. La combinación de estos factores sitúa a la compañía en un escenario de valoración exigente y riesgos de solvencia latentes, condicionado por un nivel de confianza del 94% y dos discrepancias entre proveedores de datos.


</details>

<details><summary>Cómo se llegó al dictamen y al tamaño</summary>

Convicción **42.1** × 0.65 + momentum normalizado **37.8** × 0.35 = **40.6**/100 → **VENTA**

**Memoria de reflexión** (sin recorte): Sin memoria de reflexión disponible: no se aplica ajuste.

_Sin asignación: VENTA no genera asignación en una cartera solo larga._

R:R 1.75 → exige acertar el **36.4%** de las veces para no perder dinero. Horizonte 126 sesiones (~6.0 meses); a su ATR actual el precio necesita al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

_CEG: fundamentales aprobados; estilo MIXTA con convicción 42.1/100 y momentum BAJISTA (-24.4/100). Síntesis del debate: El análisis de Constellation Energy Corporation muestra un dinamismo operativo sobresaliente, respaldado por un crecimiento de ingresos del 23.0% que supera con amplitud la mediana sectorial del 4% y un margen neto aceptable del 11.1% en línea con el sector, impulsado además por un flujo de noticias de sesgo alcista y baja probabilidad de impacto. Sin embargo, este desempeño convive con vulnerabilidades significativas reflejadas en un ratio P/E de 28.3x que duplica ampliamente la mediana sectorial de 18x, una puntuación Altman Z de insolvencia situada en la zona gris de 1.65 y una estructura técnica bajista confirmada por la cotización por debajo de su media de 200 sesiones. La combinación de estos factores sitúa a la compañía en un escenario de valoración exigente y riesgos de solvencia latentes, condicionado por un nivel de confianza del 94% y dos discrepancias entre proveedores de datos._


</details>

**Lectura:** Emitimos una orden de venta de estilo mixta sobre CEG a un precio de 289.36 dólares, respaldada por una débil convicción fundamental de 42 sobre 100 y un momentum negativo de 24 sobre 100, sin vetos aplicados ni banderas rojas que alteren la ejecución. La estrategia asigna un 0.00% de la cartera y fija un nivel de stop en 271.04 dólares y un objetivo en 321.42 dólares, con una relación de riesgo beneficio de 1.75. Esta operación se ejecutará estrictamente dentro del horizonte temporal de 126 sesiones previsto por nuestros modelos deterministas.

---

## Calidad de los datos

La ausencia de un dato se propaga a la convicción y, por esa vía, al tamaño de la posición. Por eso se declara.

| Ticker | Confianza | Fuentes | Cobertura | Ausentes | Discrep. | Opciones |
| :--- | ---: | :--- | ---: | :--- | ---: | :--- |
| **TSM** | 98% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 1 | 0d hist. |
| **NVDA** | 86% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 4 | 1d hist. |
| **GOOGL** | 91% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 4 | 1d hist. |
| **MSFT** | 95% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 2 | 0d hist. |
| **MU** | 86% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 3 | 0d hist. |
| **CEG** | 94% | yfinance, SEC EDGAR (Oficial), Finnhub | 96% | — | 2 | 0d hist. |

<details><summary>Discrepancias y procedencia de cada magnitud</summary>

- `TSM` — revenue_growth: dispersión del 35% entre yfinance (0.36) vs Finnhub (0.2325)
- `TSM` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `NVDA` — revenue_growth: dispersión del 42% entre yfinance (1.059) vs Finnhub (0.669) vs SEC EDGAR (derivado) (0.614)
- `NVDA` — net_margin: dispersión del 86% entre yfinance (0.6366) vs Finnhub (0.6366) vs SEC EDGAR (derivado) (4.461)
- `NVDA` — debt_to_equity: dispersión del 68% entre yfinance (0.1697) vs SEC EDGAR (derivado) (0.05384)
- `NVDA` — roe: dispersión del 35% entre yfinance (1.172) vs Finnhub (1.101) vs SEC EDGAR (derivado) (0.7633)
- `NVDA` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `GOOGL` — revenue_growth: dispersión del 43% entre yfinance (0.242) vs Finnhub (0.1715) vs SEC EDGAR (derivado) (0.1387)
- `GOOGL` — net_margin: dispersión del 31% entre yfinance (0.5477) vs Finnhub (0.5477) vs SEC EDGAR (derivado) (0.3776)
- `GOOGL` — debt_to_equity: dispersión del 41% entre yfinance (0.1886) vs SEC EDGAR (derivado) (0.1121)
- `GOOGL` — roe: dispersión del 37% entre yfinance (0.4868) vs Finnhub (0.5084) vs SEC EDGAR (derivado) (0.3183)
- `GOOGL` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `MSFT` — revenue_growth: dispersión del 18% entre yfinance (0.177) vs Finnhub (0.1457) vs SEC EDGAR (derivado) (0.1779)
- `MSFT` — debt_to_equity: dispersión del 69% entre yfinance (0.2912) vs SEC EDGAR (derivado) (0.09108)
- `MSFT` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `MU` — revenue_growth: dispersión del 97% entre yfinance (3.457) vs Finnhub (0.1176) vs SEC EDGAR (derivado) (0.4885)
- `MU` — net_margin: dispersión del 59% entre yfinance (0.5591) vs Finnhub (0.5591) vs SEC EDGAR (derivado) (0.2284)
- `MU` — roe: dispersión del 78% entre yfinance (0.6664) vs Finnhub (0.7055) vs SEC EDGAR (derivado) (0.1576)
- `MU` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `CEG` — revenue_growth: dispersión del 66% entre yfinance (0.23) vs Finnhub (0.0772) vs SEC EDGAR (derivado) (0.1951)
- `CEG` — debt_to_equity: dispersión del 34% entre yfinance (0.7642) vs SEC EDGAR (derivado) (0.5058)
- `CEG` procedencia: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance

</details>

## Track record y limitaciones

**El sistema NO bate a comprar y mantener el índice.** Régimen `pit`, 2015-01-02 → 2025-12-30 (`output/backtest_report.md`).

| | CAGR | Volatilidad | Sharpe | Sortino | Máx. drawdown |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Estrategia | 4.0% | 5.4% | 0.74 | 0.92 | -16.2% |
| SPY | 13.5% | 17.8% | 0.80 | 0.98 | -33.7% |

Frente a selección aleatoria con el mismo perfil de exposición: **percentil 17.7**, **por debajo** de la mediana — la selección de valores todavía no aporta.

> El CAGR no es comparable directamente: la estrategia opera al 5.4% de volatilidad frente al 17.8% del índice, porque el presupuesto de riesgo la mantiene poco invertida. Sharpe y Sortino son la comparación pertinente.

**Limitaciones vigentes**

- **Universo con sesgo de supervivencia:** solo se analizan valores que existen hoy.
- **El ajuste de precio de entrada no está backtesteado.** Su nivel sale solo de la cadena de opciones, y el histórico de open interest y volatilidad implícita es de pago. El backtest mide el sistema *sin* ajuste de entrada, mientras producción sí lo aplica. Del bloque de posicionamiento solo se mide el veto macro, que sí es point-in-time.
- **El signo de la exposición gamma es una convención**, no una medición: la cadena publica open interest, no quién está en cada lado de cada contrato.
- **Percentiles de put/call y skew** necesitan histórico acumulado propio; hasta reunirlo se declaran DATOS_INSUFICIENTES en vez de asumir el percentil 50.
- **Normas sectoriales estáticas y coste de capital constante:** ordenan y contextualizan, no valoran.
- **Sin datos intradía:** la ejecución se modela al cierre y la apertura siguiente.
- **Riesgo legal y regulatorio fuera de la decisión:** aparece en la capa de noticias pero no toca el tamaño. Debe activar revisión manual.

## Anexo metodológico

**Umbrales y política de riesgo**

- Filtro fundamental: margen neto ≥ 5.0% · crecimiento ≥ 5.0% · deuda/patrimonio ≤ 3.00x (al alza en financieras, inmobiliario y utilities, donde el apalancamiento es estructural).
- Riesgo por posición 0.75% al stop · agregado 5.0% · peso máximo 10% · límite sectorial 30% · exposición bruta máxima 95% · volatilidad objetivo 25%.

**Estilos presentes en este informe**

- `CALIDAD_COMPUESTA` — Reinvierte por encima de su coste de capital de forma sostenida (Buffett).
- `MIXTA` — Sin dominancia clara de ninguna dimensión.

El estilo no es descriptivo: fija los múltiplos de ATR del stop y del objetivo, el horizonte, y habilita vetos. TRAMPA_DE_VALOR y ESPECULATIVA no pueden superar MANTENER.

**Decisiones de entrada presentes**

- `ESCALONAR` — Acuerdo parcial, o acuerdo total con algo sobreextendido: se entra a medio camino del nivel.
- `ESPERAR_RETROCESO` — Las señales divergen: se exige el retroceso completo hasta el nivel de la cadena.
- `NO_APLICABLE` — Sin dos señales disponibles o sin nivel por debajo del precio: entrada al precio de mercado.


**Cómo se decide el precio de entrada**

El Analista de Posicionamiento cruza tres señales: el posicionamiento de los especuladores en futuros (informes COT de la CFTC, en z-score frente a su propio histórico y normalizado por interés abierto), el de la cadena de opciones del propio valor (put/call ratio y skew en percentil histórico, más el punto de inflexión de la exposición gamma) y el momentum del Analista Técnico. El bloque macro da dirección; solo la cadena de opciones da un nivel de precio concreto. Si las tres confirman, se entra a mercado; si divergen, se exige el retroceso. El ajuste **solo puede bajar** el precio de entrada, nunca subirlo, y está acotado a un ATR para que la entrada objetivo nunca quede por debajo del propio stop.

**Origen de las reglas de calidad y valoración**

Piotroski (1998, F-Score) · Altman (1968, Z-Score, variante Z'' para no manufactureras) · Graham (1949, número de Graham y criterios defensivos) · Buffett (ROIC sobre coste de capital, margen bruto como foso, beneficio del propietario) · Lynch (1989, PEG y taxonomía) · Greenblatt (2005, EBIT/EV y rentabilidad del capital tangible) · Sloan (1996, ratio de devengos).

**Papel del modelo de lenguaje**

Ninguna variable de decisión depende del LLM. Rating, tamaño, stop, objetivo, estilo y precio de entrada salen de reglas deterministas; el modelo solo puede sobrescribir los campos de texto, y siempre después de que todo esté fijado. Sin clave de API el sistema produce exactamente los mismos dictámenes, y esa propiedad se verifica en ejecución con `assert_llm_is_decision_neutral()`.
