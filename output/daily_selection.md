# Informe de Inversión — Selección Multi-Agente

**Fecha de análisis:** `2026-08-29 13:39:41`  
**Universo analizado:** NRGV, DOCN, GOOGL (3 valores)  
**Referencia de mercado:** SPY · 12m 20.9% · 3m 2.5%  
**Capital de referencia:** $1,500

> Este informe es el resultado de un sistema automatizado de análisis. Las recomendaciones se derivan de reglas deterministas y auditables; el modelo de lenguaje interviene únicamente en la redacción de los resúmenes, nunca en el cálculo de ratings, tamaños de posición ni niveles de riesgo. **No constituye asesoramiento de inversión.**

---

## 1. Resumen ejecutivo

| Ticker | Empresa | Sector | Estilo | Convicción | Filtro | Momentum | Dictamen | Peso | Stop | Objetivo | R:R | Horizonte |
| :--- | :--- | :--- | :--- | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| **NRGV** | Energy Vault Holdings, Inc. | Utilities | `ESPECULATIVA` | 0 | ❌ | n/d | **VENTA FUERTE** | 0.00% | n/d | n/d | n/d | n/d |
| **DOCN** | DigitalOcean Holdings, Inc. | Technology | `CALIDAD_DETERIORADA` | 19 | ✅ | +32 | **VENTA FUERTE** | 0.00% | $103.68 | $153.18 | 1.75 | 126d |
| **GOOGL** | Alphabet Inc. | Communication Services | `CALIDAD_COMPUESTA` | 67 | ✅ | +23 | **COMPRA** | 9.33% | $325.12 | $371.70 | 2.00 | 252d |

**Cómo leer esta tabla.** La *convicción* (0-100) resume calidad, valoración, crecimiento y solvencia, ya descontada por la cobertura de datos. El *momentum* (−100 a +100) es la puntuación técnica continua. El *dictamen* sale de cruzar ambas y aplicar los vetos de riesgo. El *peso* es el resultado del presupuesto de riesgo, no un rango fijo: dos valores con el mismo dictamen pueden tener pesos muy distintos si su volatilidad o su distancia al stop difieren. *R:R* es el ratio riesgo/recompensa y el *horizonte* es el plazo al que aplican stop y objetivo.

---

## 2. Cartera propuesta

**Exposición bruta:** 9.33% · **Liquidez:** 90.67% · **Riesgo agregado si todos los stops saltan:** 0.42% del patrimonio (presupuesto: 5.0%)

| Ticker | Sector | Estilo | Convicción | Peso solicitado | Peso final | Riesgo aportado | Correlación media |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **GOOGL** | Communication Services | `CALIDAD_COMPUESTA` | 66.9 | 9.33% | **9.33%** | 0.42% | n/d |

**Concentración por sector** (límite: 30%)

- Communication Services: 9.33%

**Diagnóstico de diversificación**

- Posiciones: **1**
- Posiciones efectivas (inverso de Herfindahl): **1.0**

> Sin matriz de correlaciones: no se puede afirmar que estas posiciones sean apuestas independientes.

> **Sobre la liquidez.** El 90.7% no invertido rinde un 2.0% anual supuesto, lo que aporta 1.81 puntos al resultado. El backtest histórico documenta que ignorar este detalle —dejar el efectivo al 0%— hacía la comparación contra el índice más pesimista de lo debido.

**Restricciones de cartera activadas:**

- Sin matriz de correlaciones disponible: no se aplicó penalización por solapamiento de riesgo. La diversificación declarada es nominal, no efectiva.

**Candidatos sin asignación** (y por qué):

- `NRGV` (VENTA FUERTE) — no supera el filtro fundamental
- `DOCN` (VENTA FUERTE) — VENTA FUERTE no genera asignación en una cartera solo larga

---

## 3. Reparto por estilo de inversión

El estilo no es una etiqueta descriptiva: determina los múltiplos de ATR del stop y del objetivo, el horizonte de la posición y los vetos que puede aplicar el Fund Manager. Un valor clasificado como TRAMPA_DE_VALOR o ESPECULATIVA no puede recibir un dictamen superior a MANTENER por muy atractivos que sean sus múltiplos.

| Estilo | Valores | Qué significa |
| :--- | :--- | :--- |
| `CALIDAD_COMPUESTA` | GOOGL | Negocio capaz de reinvertir beneficios por encima de su coste de capital durante años. Es la categoría que persigue Buffett: se paga un múltiplo razonable por una tasa de retorno sostenible, no un múltiplo bajo por un activo estancado. |
| `CALIDAD_DETERIORADA` | DOCN | Negocio rentable con varios defectos estructurales a la vez (caja, devengos, dilución o balance). La calidad operativa no compensa por sí sola un balance deteriorado: la tesis depende de que esos defectos se corrijan, y eso exige revisarla antes. |
| `ESPECULATIVA` | NRGV | El perfil de riesgo domina cualquier lectura de valor o crecimiento. Solvencia comprometida o varias banderas rojas simultáneas. |

---

## 4. Fichas por compañía

### NRGV — Energy Vault Holdings, Inc.

**Sector / Industria:** Utilities / Utilities - Renewable  
**Estilo:** `ESPECULATIVA` (secundarias: CRECIMIENTO_RAPIDO_LYNCH)  
**Confianza en los datos:** 85% · Fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

#### 1. Filtro fundamental — RECHAZADO

| Criterio | Valor | Umbral | Cumple |
| :--- | ---: | ---: | :---: |
| Margen neto | -48.6% | 5.0% | ❌ |
| Crecimiento de ingresos | 104.1% | 5.0% | ✅ |
| Deuda / Patrimonio | 7.51x | 5.00x | ❌ |

**Motivos:** Margen Neto (-48.6%) por debajo del umbral mínimo (5.0%); Relación Deuda/Capital (7.51) excede el límite permitido para Utilities (5.00)

- ℹ️ Umbral de deuda ajustado a 5.0x por ser Utilities, donde el apalancamiento alto es estructural (el umbral general es 3.0x).
- ℹ️ 3 discrepancia(s) entre proveedores; confianza rebajada al 85%.

**Lectura:** La compañía ha sido rechazada porque, a pesar de aplicar la excepción sectorial para Utilities que eleva el límite de endeudamiento a 5.00x, registra un apalancamiento excesivo de 7.51x y un margen neto profundamente negativo de -48.6%. Adicionalmente, las tres discrepancias entre proveedores han rebajado la confianza en los datos al 85%, lo que invalida la sostenibilidad de su agresivo crecimiento de ingresos del 104.1% frente a unas pérdidas operativas insostenibles.

#### 2. Calidad y valoración

```
Calidad      ██████░░░░░░░░░░░░░░ 28/100
Valoración   ░░░░░░░░░░░░░░░░░░░░ 0/100
Crecimiento  ██████████░░░░░░░░░░ 50/100
Solvencia    █░░░░░░░░░░░░░░░░░░░ 5/100
────────────────────────────────────────
CONVICCIÓN   ░░░░░░░░░░░░░░░░░░░░ 0/100
```

**Estilo `ESPECULATIVA`** — Altman Z'' (no manufactureras) en -7.56, por debajo del umbral de insolvencia (1.1), CORROBORADO por flujo de caja libre negativo y cobertura de intereses insuficiente y margen operativo negativo: el riesgo de solvencia es real y domina cualquier lectura de calidad, valor o crecimiento.

_Convicción bruta 20.9 × cobertura de datos 1.0 × confianza en fuentes 0.853 − 30.0 por banderas rojas = **0.0**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 4/8 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | -7.56 | zona DISTRESS (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | n/d | margen de seguridad n/d (0/5 criterios defensivos) |
| Greenblatt | EBIT/EV | -10.7% | por debajo del umbral |
| Buffett | ROIC | -65.2% | -74.2% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 22.5% | sin indicio de foso |
| Buffett | Rendimiento FCF | -7.5% | dilución anual +10.29% |
| Lynch | PEG | None | NO_EVALUABLE · categoría CRECIMIENTO_RAPIDO (sobre crecimiento de ingresos) |
| Sloan | Devengos | -31.3% | beneficio respaldado por caja |

<details><summary>Desglose del F-Score de Piotroski</summary>

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ❌ | ROA=-33.12% |
| Flujo de caja operativo positivo | ❌ | FCO=-5,649,000 |
| ROA en mejora | ✅ | -73.82% → -33.12% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | — | sin datos |
| Ratio corriente en mejora | ❌ | 1.26 → 0.73 |
| Sin emisión neta de acciones | ❌ | dilución controlada |
| Margen bruto en mejora | ✅ | 13.39% → 23.56% |
| Rotación de activos en mejora | ✅ | 0.25x → 0.65x |

</details>

**Contexto sectorial (Utilities)** — el punto de comparación que convierte «P/E elevado» en una afirmación verificable:

| Métrica | Valor | Mediana del sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | -21.7x | 18.0x | -1.2 | por debajo del sector |
| Margen neto | -48.6% | 11% | -4.42 | por debajo del sector |
| Deuda/Patrimonio | 7.5x | 1.5x | 5.01 | muy por encima del sector |
| Crecimiento de ingresos | 104.1% | 4% | 26.02 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**🚩 Banderas rojas:**

- Altman Z'' (no manufactureras) en zona de insolvencia (Z=-7.56 < 1.1)
- Dilución del 10.3% anual: el crecimiento por acción es menor que el agregado
- Margen neto negativo (-48.6%)
- Flujo de caja libre negativo: el negocio consume caja
- Apalancamiento muy elevado (Deuda/Patrimonio 7.51x)
- Cobertura de intereses insuficiente (-10.33x)
- ROIC negativo (-65.2%): destruye valor sobre el capital empleado

_Cobertura de datos: 77% (OK)._

**Lectura:** La cobertura de datos se sitúa en el setenta y siete por ciento, lo que advierte sobre una visibilidad incompleta que amplifica el riesgo de un negocio cuya penalización por solvencia y su Altman en zona de distress reflejan una destrucción severa de valor por un ROIC negativo del menos sesenta y cinco coma dos por ciento y un consumo constante de caja. El estilo especulativo asignado, secundado por un perfil de crecimiento rápido Lynch, resulta plenamente justificado ante una estructura con un apalancamiento de siete coma cincuenta y una veces y una cobertura de intereses insuficiente de menos diez coma treinta y tres veces, donde la dilución anual del diez coma tres por ciento castiga al accionista. La valoración de cero sobre cien evidencia que el precio actual no captura correctamente la gravedad de estas tensiones financieras, haciendo que cualquier expectativa de expansión quede supeditada a la superación de una crisis existencial de liquidez y endeudamiento.

#### 3. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `BAJA` (0.24) · **Dirección probable:** `ALCISTA`

Cobertura: 11 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-25` · **RESULTADOS** · NEUTRA · p=0.09 · _vinanet.vn_ (1 fuente/s) — [Energy (NRGV) Q2 2026 Results: EPS Exceeds Its Estimate in the Latest Session; Market Reaction - vinanet.vn](https://news.google.com/rss/articles/CBMilgJBVV95cUxQNGdidkY1Tmh3WHB3UDN1RUhrS2lpSFU5QVpSZWNTZVNscnRHX0JMakhoZWdLbTZKR1ZIWTVYaW1rMVBuUEFjdWY5VDRjUWNvbVFKQ0xjbUt0SnhBQU81YXVVY2VYS2VXMDJFWUFIQjRfZHBXeC1tSHhDZEM4a1FwTHYwalhoVzBOUnNPNjFvYUd2ZjQ5SzY0SkVKZzBYZlJhVWcyZGliYnVNRnFUOGUyd2dMZWRiRXhLNVdaNmhrd21wZlZxZ25VT0lPZDJmY0hUTUtzNHBWdTc2MzRFTlR5ZnJyNDdMWXhmWWRaX2JMdXBCLWVZR053WGxGZklKOUxiMDdsM3UxSklONEJKQWU2aUIzbDZNZw?oc=5)
- `2026-08-11` · **RESULTADOS** · NEUTRA · p=0.08 · _SEC EDGAR (8-K)_ (1 fuente/s) — [Energy Vault Holdings, Inc. presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1828536/000182853626000100/nrgv-20260811.htm)
- `2026-08-12` · **RESULTADOS** · NEUTRA · p=0.04 · _Seeking Alpha_ (1 fuente/s) — [Energy Vault Holdings, Inc. 2026 Q2 - Results - Earnings Call Presentation (NYSE:NRGV) 2026-08-12 - Seeking Alpha](https://news.google.com/rss/articles/CBMirgFBVV95cUxQaktxOTJkUi00LXZyVUtFTzloV0F6RHltUjVkeWhfWTg3ZF96S2ctUFIyMDJadjE5VzlTcExuUmNOck81REVPTndBTWlRdnJoU2hsbDhCS19YWFVuWERZZE9MZk90dGlWbVFzdWZaVWQtNGhoVUZWS2dCQWxVTVZ2MFpsTngtX0tKMktoU1RtTWVmcUljMEVhYkNyc2N3YmZBZno0bDdrbFp5NXZ6ckE?oc=5)

**Lectura:** Energy Vault Holdings, Inc. ha presentado su formulario 8-K y la presentación de resultados del segundo trimestre de 2026 en Seeking Alpha, donde se afirma que el beneficio por acción superó las estimaciones, aunque el informe debe interpretarse con cautela debido a que la fuente tavily no respondió a la búsqueda. Este conjunto de hechos corporativos y estimaciones superadas genera un desequilibrio positivo que apunta a una dirección probable alcista con una probabilidad de impacto en el precio baja (0.24) basada en el análisis de las once noticias de los últimos treinta días.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 4. Dictamen del Fund Manager

### 🎯 `VENTA FUERTE` — asignación objetivo **0.00%** de la cartera

**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):

- Gatekeeper: RECHAZADO

_Sin asignación: no supera el filtro fundamental._

**Orden ejecutiva:** La mesa ejecutará una postura de VENTA FUERTE estilo ESPECULATIVA sobre NRGV con una asignación nula del 0.00% de la cartera debido a que el Gatekeeper ha emitido un rechazo categórico y se han activado múltiples banderas rojas críticas, incluyendo el Altman Z en zona de insolvencia de -7.56 y un ROIC negativo del -65.2%. Aunque el precio actual es de $3.75, la orden carece de stop, objetivo, riesgo/recompensa y horizonte temporal determinado al figurar como no disponible, al igual que el momentum y una convicción fundamental nula de 0/100. Esta directiva refleja una operación bloqueada por veto estricto que prohíbe cualquier exposición ante la destrucción estructural de valor y la quema de caja de la compañía.

---

### DOCN — DigitalOcean Holdings, Inc.

**Sector / Industria:** Technology / Software - Infrastructure  
**Estilo:** `CALIDAD_DETERIORADA` (secundarias: POSIBLE_REESTRUCTURACION)  
**Confianza en los datos:** 89% · Fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

#### 1. Filtro fundamental — APROBADO

| Criterio | Valor | Umbral | Cumple |
| :--- | ---: | ---: | :---: |
| Margen neto | 23.3% | 5.0% | ✅ |
| Crecimiento de ingresos | 28.6% | 5.0% | ✅ |
| Deuda / Patrimonio | 2.13x | 3.00x | ✅ |

- ℹ️ 4 discrepancia(s) entre proveedores; confianza rebajada al 89%.

**Lectura:** La compañía ha obtenido el veredicto de APROBADO gracias a una sólida combinación de expansión comercial y rentabilidad, reflejada en un crecimiento de ingresos del 28.6% y un margen neto del 23.3%. Aunque las cuatro discrepancias entre proveedores han rebajado la confianza en los datos al 89%, su apalancamiento se mantiene holgadamente por debajo del límite sectorial de 3.00x establecido para el sector Technology con una Deuda/Patrimonio de 2.13x.

#### 2. Calidad y valoración

```
Calidad      █████████████░░░░░░░ 66/100
Valoración   ░░░░░░░░░░░░░░░░░░░░ 2/100
Crecimiento  ██████████░░░░░░░░░░ 49/100
Solvencia    ███████████░░░░░░░░░ 53/100
────────────────────────────────────────
CONVICCIÓN   ████░░░░░░░░░░░░░░░░ 19/100
```

**Estilo `CALIDAD_DETERIORADA`** — Calidad de negocio alta (65.6/100) pero con 2 defectos estructurales simultáneos: Altman Z'' (no manufactureras) en zona de insolvencia (Z=0.04 < 1.1); el Z está distorsionado por un patrimonio contable negativo, así que conviene leerlo junto a la generación de caja; Patrimonio neto negativo ($-28,690,000): los ratios sobre fondos propios (deuda/patrimonio, ROE) no son interpretables. La rentabilidad del negocio no compensa por sí sola un balance o una calidad contable deteriorados.

_Convicción bruta 44.0 × cobertura de datos 1.0 × confianza en fuentes 0.892 − 20.0 por banderas rojas = **19.3**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 8/9 | FUERTE |
| Altman | Z'' (no manufactureras) | 0.04 | zona DISTRESS (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $20.95 | margen de seguridad -480.8% (0/5 criterios defensivos) |
| Greenblatt | EBIT/EV | 1.6% | por debajo del umbral |
| Buffett | ROIC | 13.5% | +4.5% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 57.2% | indicio de foso competitivo |
| Buffett | Rendimiento FCF | 0.3% | dilución anual -0.31% |
| Lynch | PEG | None | NO_EVALUABLE · categoría EN_CONTRACCION (sobre crecimiento de beneficio) |
| Sloan | Devengos | -2.7% | beneficio respaldado por caja |

<details><summary>Desglose del F-Score de Piotroski</summary>

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=14.11% |
| Flujo de caja operativo positivo | ✅ | FCO=309,604,000 |
| ROA en mejora | ✅ | 5.16% → 14.11% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 90.63% → 52.82% |
| Ratio corriente en mejora | ❌ | 2.45 → 0.69 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ✅ | 59.69% → 59.86% |
| Rotación de activos en mejora | ✅ | 0.48x → 0.49x |

</details>

**Contexto sectorial (Technology)** — el punto de comparación que convierte «P/E elevado» en una afirmación verificable:

| Métrica | Valor | Mediana del sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 50.5x | 26.0x | 1.94 | muy por encima del sector |
| Margen neto | 23.3% | 15% | 1.55 | muy por encima del sector |
| Deuda/Patrimonio | 2.1x | 0.6x | 3.54 | muy por encima del sector |
| Crecimiento de ingresos | 28.6% | 12% | 2.38 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**🚩 Banderas rojas:**

- Altman Z'' (no manufactureras) en zona de insolvencia (Z=0.04 < 1.1); el Z está distorsionado por un patrimonio contable negativo, así que conviene leerlo junto a la generación de caja
- Patrimonio neto negativo ($-28,690,000): los ratios sobre fondos propios (deuda/patrimonio, ROE) no son interpretables

_Cobertura de datos: 96% (OK)._

**Lectura:** La compañía se clasifica bajo el estilo de calidad deteriorada debido a un ROIC de 13.5% y un puntaje de Piotroski de 8/9 que chocan frontalmente contra un patrimonio neto negativo de $-28,690,000 y un Altman Z en zona de distress de 0.04 que anulan la interpretabilidad de los ratios sobre fondos propios, aunque la cobertura de datos del 96% permite sostener analíticamente que la rentabilidad operativa no logra blindar un balance estructuralmente quebrado. El precio actual, con una valoración de 2/100 y un PEG no disponible, no refleja adecuadamente esta asimetría de riesgo, ya que el mercado parece ignorar que el aparente atractivo operativo se evapora ante la incapacidad de la caja para compensar la insolvencia contable. Este diagnóstico exige un horizonte de inversión ultracorto y un seguimiento riguroso de la liquidez, dado que la etiqueta asignada no es un mero matiz estético sino la advertencia de que la fragilidad financiera domina por completo la tesis.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +32.4/100) · **Tendencia:** ALCISTA_EN_CORRECCION · **RSI:** 48.29 (NEUTRAL)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +15.00 |
| Macd | -1.26 |
| Rsi | -0.51 |
| Bollinger | -0.85 |
| Momentum precio | +20.00 |
| **Total** | **+32.38** |

- Precio frente a medias: SMA50 -7.1% · SMA200 +27.8%
- Posición en el rango de 52 semanas: 58%
- ATR: $9.00 (7.4% del precio) · Volatilidad anualizada: 83.3%
- Momentum relativo a 12 meses frente al índice: +247.7%

**Señales:**

- Tendencia alcista de fondo con corrección: precio 121.68 por debajo de la SMA50 130.92 pero sobre la SMA200 95.25
- MACD bajista (histograma -0.284, 0.03 ATR)
- RSI neutral con sesgo débil (48.3, entre 30 y 50)
- Precio en el 46% del canal de Bollinger
- Momentum 12m (excl. último mes) +268.6% frente al +20.9% de SPY: exceso +247.7%

**Lectura:** El activo presenta una puntuación de +32.4/100 con estructura alcista en corrección, cotizando a 121.68 dólares por debajo de una SMA50 de 130.92 dólares pero apoyado sobre una SMA200 de 95.25 dólares que refleja la inercia del indicador tras un desplome anterior. Con un RSI neutral en 48.3 y un histograma MACD negativo de -0.284, el impulso actual no muestra una fuerza sostenida y el valor no se encuentra sobreextendido al situarse al 58% de su rango de 52 semanas.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `BAJA` (0.16) · **Dirección probable:** `ALCISTA`

Cobertura: 9 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-17` · **GUIDANCE** · NEUTRA · p=0.06 · _simplywall.st_ (1 fuente/s) — [The Bull Case For DigitalOcean Holdings (DOCN) Could Change Following Mixed Q2 2026 Results And Upbeat Guidance - simplywall.st](https://news.google.com/rss/articles/CBMi1AFBVV95cUxPRkZ2c1dnclFXbXdaQnZsTmhNSnVKNnhCR01HZkJJSS1Rb0ZzNnZnUEYxeEZKZ1RrRzN4dHVjcVg1TEQ2Wm92VjgzN1JCVXZCbWw4T2VMXzBaUmI3OXdDRzhuSFJvMUhtUTRjUHRFWVNZLXVVaUMxYUZlVmVFMmdQZUF3ZFhLVGxTRWxYX1EzZUE5TXJzTUxoUE1iWU9UMk5kZGk2T3FhTVd1REotTFF4cEQ2d2wzTC1fQzNpV3RrbHBGYUppRE41aHJ0dTFaSENja0hfT9IB2gFBVV95cUxOdGdhQ0xLNUJ0Rld4M3F5azFXUy16YTJtVHRsZEptRzM3SjNLWHlMa3VFMVZiNW9feFlURVRtMGhqMVI1Tm5ueVBOUTFPUnNqOG1faTNUakFvbjlZM25CWXpVX3NBaU45WnV1azdvN3J2aTJYRFBQUHpEaU5BaGVKMGFrZkphaFppMWg4Z19TeEM3UV9hcnZUUkFVSTAwbVc5TkJQcGhuR2Q4LVdWdWExUnpsUW45SUhqcUFzYVk4a2l1OFpQR3ZkeU85RGZpZktXT0QxUDNyTlpsUQ?oc=5)
- `2026-08-04` · **RESULTADOS** · NEUTRA · p=0.04 · _SEC EDGAR (8-K)_ (1 fuente/s) — [DigitalOcean Holdings, Inc. presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1582961/000162828026052135/docn-20260804.htm)
- `2026-08-04` · **RESULTADOS** · NEUTRA · p=0.03 · _Business Wire_ (1 fuente/s) — [DigitalOcean Announces Second Quarter 2026 Financial Results - Business Wire](https://news.google.com/rss/articles/CBMiuAFBVV95cUxPSVBXcE11TVNXRVhnZW5GUjJBdWlSSmM3dGlrYzVTWVQycjNQVXpOaUFvNDNROWxfR1RmZ2FnZlhGXzJnbXNDNmlJNUx5REFSUm9kYmFaQmVscFBJb3NYdVJTbktCdEN4OElyQ2xiNWVBZ2poWXVIcG94SjhQRVlPWEJvT1BfZUhZQXpBa3ZyQVNwV3hWQ3JvNHh2TUZDUlBKTFJrbVQwZW1uY1VZN0l3aVFwdXAyaW1E?oc=5)

**Lectura:** El informe sobre DigitalOcean Holdings, Inc. se encuentra degradado debido a que la fuente tavily no respondió, aunque se han analizado 9 noticias en treinta días que incluyen la presentación del formulario 8-K ante el regulador y comunicados oficiales sobre los resultados del segundo trimestre de 2026. Con una probabilidad de impacto en el precio baja de 0.16 y una dirección probable alcista basada en un desequilibrio de +1.00, la cotización podría verse impulsada por la combinación de resultados y orientaciones optimistas a pesar de las cifras mixtas reportadas.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (6 argumentos)

- Crecimiento de ingresos sólido del 28.6%, muy por encima del sector (mediana de Technology: 12%).
- Margen neto sólido del 23.3%, muy por encima del sector.
- Margen bruto del 57%, indicio de poder de fijación de precios.
- F-Score de Piotroski 8/9: la calidad contable mejora en rentabilidad, apalancamiento y eficiencia a la vez.
- Momentum favorable (+32.4/100), RSI 48.3 (neutral).
- Flujo de noticias con probabilidad de impacto BAJA (0.16) y sesgo ALCISTA sobre 9 nota(s); principal catalizador: "The Bull Case For DigitalOcean Holdings (DOCN) Could Change Following Mixed Q2 2026 Results And Upbeat Guidance - simply" (capa asesora: no altera el dictamen).

**🐻 Tesis bajista** (4 argumentos)

- P/E de 50.5x frente a una mediana sectorial de 26x (1.9 veces la norma de Technology): la valoración descuenta una ejecución impecable.
- Carga financiera elevada: deuda/patrimonio de 2.13x, muy por encima del sector (mediana de Technology: 0.6x).
- Altman Z'' (no manufactureras) en 0.04, por debajo del umbral de insolvencia (1.1).
- 4 discrepancia(s) entre proveedores de datos; confianza del 89%.

**⚖️ Síntesis:** La unidad de debate concluye que DigitalOcean Holdings exhibe fortalezas operativas destacadas, evidenciadas por un crecimiento de ingresos del 28.6% frente al 12% del sector, un margen neto del 23.3%, un margen bruto del 57% y un F-Score de Piotroski de 8 de 9. No obstante, estas fortalezas chocan frontalmente con vulnerabilidades financieras críticas, reflejadas en un ratio P/E de 50.5x que duplica la mediana sectorial de 26x, una elevada deuda sobre patrimonio de 2.13x y un Altman Z de no manufactureras de 0.04 que se sitúa profundamente por debajo del umbral de insolvencia de 1.1. Por consiguiente, bajo el estilo asignado de calidad deteriorada y con un flujo de noticias de impacto bajo pero sesgo alcista que no altera el dictamen, la compañía presenta una alta calidad fundamental mermada por un riesgo de insolvencia y una sobrevaloración severas que invalidarían la tesis si se infringen los umbrales críticos establecidos.

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 14% en dos trimestres consecutivos.
- Que el margen neto baje del 14.0%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que el precio pierda la media de 200 sesiones ($95.25) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `VENTA FUERTE` — asignación objetivo **0.00%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **19.3**/100 × peso 0.65 + momentum normalizado **66.2**/100 × peso 0.35 = **35.7**/100
- Corte alcanzado: **VENTA** → tras los vetos: **VENTA FUERTE**

**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):

- 2 banderas rojas fundamentales: se baja un escalón

_Sin asignación: VENTA FUERTE no genera asignación en una cartera solo larga._

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $121.68 | — | — |
| Stop-loss | $103.68 | −14.8% | 2.0× |
| Objetivo | $153.18 | +25.9% | 3.5× |

- **Ratio riesgo/recompensa:** 1.75 → exige acertar el **36.4%** de las veces solo para no perder dinero.
- **Horizonte:** 126 sesiones (~6.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 126 sesiones (~6 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** Se ejecuta la orden de venta fuerte sobre DOCN con una asignación nula en cartera, operando bajo el dictamen de calidad deteriorada y una débil convicción fundamental de 19 sobre 100 que contrasta con su impulso de más 32 sobre 100, todo ello condicionado por dos banderas rojas fundamentales relativas a la insolvencia según el modelo Altman y un patrimonio neto negativo de menos 28 millones 690 mil dólares que obligan a descender un escalón. La mesa gestionará la posición limitando el riesgo mediante el stop situado exactamente en 103,68 dólares frente al objetivo de 153,18 dólares fijado para un precio actual de 121,68 dólares, manteniendo la operación dentro de un horizonte temporal de 126 sesiones con una relación de riesgo beneficio de 1,75. Las restricciones de la directiva son estrictas al no existir margen para interpretaciones optimistas debido a que el patrimonio negativo invalida los ratios sobre fondos propios y sitúa a la compañía en zona de vulnerabilidad financiera.

---

### GOOGL — Alphabet Inc.

**Sector / Industria:** Communication Services / Internet Content & Information  
**Estilo:** `CALIDAD_COMPUESTA` (secundarias: DIVIDENDO, CRECIMIENTO_RAPIDO_LYNCH)  
**Confianza en los datos:** 91% · Fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

#### 1. Filtro fundamental — APROBADO

| Criterio | Valor | Umbral | Cumple |
| :--- | ---: | ---: | :---: |
| Margen neto | 54.8% | 5.0% | ✅ |
| Crecimiento de ingresos | 24.2% | 5.0% | ✅ |
| Deuda / Patrimonio | 0.19x | 3.00x | ✅ |

- ℹ️ 4 discrepancia(s) entre proveedores; confianza rebajada al 91%.

**Lectura:** La sólida generación de caja y los excepcionales márgenes netos de Alphabet superan con holgura los filtros de rentabilidad y endeudamiento exigidos por el comité, a pesar de que las discrepancias entre proveedores redujeron levemente la confianza en la información. Este perfil de alta calidad operativa y prudente estructura financiera justifica plenamente el veredicto de APROBADO, confirmando que la compañía es apta para su análisis en profundidad.

#### 2. Calidad y valoración

```
Calidad      ████████████████░░░░ 80/100
Valoración   ███████░░░░░░░░░░░░░ 35/100
Crecimiento  ██████████████████░░ 91/100
Solvencia    ██████████████████░░ 92/100
────────────────────────────────────────
CONVICCIÓN   █████████████░░░░░░░ 67/100
```

**Estilo `CALIDAD_COMPUESTA`** — Calidad 80.4/100 y solvencia 91.8/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción bruta 73.5 × cobertura de datos 1.0 × confianza en fuentes 0.909 − 0.0 por banderas rojas = **66.9**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 6/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 7.14 | zona SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $151.07 | margen de seguridad -125.5% (2/5 criterios defensivos) |
| Greenblatt | EBIT/EV | 3.9% | por debajo del umbral |
| Buffett | ROIC | 29.9% | +20.9% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 60.9% | indicio de foso competitivo |
| Buffett | Rendimiento FCF | 1.7% | dilución anual -1.01% |
| Lynch | PEG | 0.06 | MUY_ATRACTIVO · categoría CRECIMIENTO_RAPIDO (sobre crecimiento de beneficio) |
| Sloan | Devengos | -5.5% | beneficio respaldado por caja |

<details><summary>Desglose del F-Score de Piotroski</summary>

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

**Contexto sectorial (Communication Services)** — el punto de comparación que convierte «P/E elevado» en una afirmación verificable:

| Métrica | Valor | Mediana del sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 17.4x | 19.0x | 0.92 | en línea con el sector |
| Margen neto | 54.8% | 12% | 4.56 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.8x | 0.24 | por debajo del sector |
| Crecimiento de ingresos | 24.2% | 8% | 3.02 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

_Cobertura de datos: 100% (OK)._

**Lectura:** La cobertura completa del cien por ciento permite diagnosticar a Alphabet como un negocio de calidad compuesta con destellos de crecimiento rápido y retornos sobresalientes, avalado por un ROIC del veintinueve con nueve por ciento que confirma su capacidad de reinversión muy por encima del coste de capital sin que aparezca ninguna bandera roja en el horizonte. La fortaleza financiera se refleja en una zona segura según Altman y una sólida puntuación de Piotroski de seis sobre nueve, lo que sustenta un crecimiento de noventa y uno sobre cien y una convicción fundamental de sesenta y siete sobre cien respaldada por un PEG extremadamente atractivo de cero con cero seis. Sin embargo, este despliegue de ventajas competitivas choca con una valoración de treinta y cinco sobre cien, lo que indica que el precio actual del mercado no solo reconoce la alta calidad del negocio, sino que exige una lectura muy precisa de los múltiplos de riesgo para justificar la entrada en el horizonte temporal asignado.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +22.8/100) · **Tendencia:** ALCISTA_EN_CORRECCION · **RSI:** 33.73 (NEUTRAL)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +15.00 |
| Macd | -2.52 |
| Rsi | -4.88 |
| Bollinger | -4.78 |
| Momentum precio | +20.00 |
| **Total** | **+22.82** |

- Precio frente a medias: SMA50 -2.7% · SMA200 +2.0%
- Posición en el rango de 52 semanas: 67%
- ATR: $6.21 (1.8% del precio) · Volatilidad anualizada: 37.0%
- Momentum relativo a 12 meses frente al índice: +36.3%

**Señales:**

- Tendencia alcista de fondo con corrección: precio 340.65 por debajo de la SMA50 350.12 pero sobre la SMA200 334.04
- MACD bajista (histograma -0.392, 0.06 ATR)
- RSI neutral con sesgo débil (33.7, entre 30 y 50)
- Precio en el 26% del canal de Bollinger
- Momentum 12m (excl. último mes) +57.2% frente al +20.9% de SPY: exceso +36.3%

**Lectura:** GOOGL muestra una estructura alcista en corrección con el precio de 340.65 dólares cotizando por debajo de la media de 50 periodos ubicada en 350.12 dólares pero manteniéndose sobre la media de 200 periodos en 334.04 dólares. Dado que el RSI de 33.7 se encuentra en zona neutral y el activo no está sobreextendido situándose al 67 por ciento de su rango anual, la puntuación de momentum de 22.8 sobre 100 refleja un impulso sostenido sin agotamiento actual a pesar de la debilidad mostrada por el histograma MACD en -0.392.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `BAJA` (0.24) · **Dirección probable:** `ALCISTA`

Cobertura: 12 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-28` · **RESULTADOS** · ALCISTA · p=0.12 · _webull.com_ (1 fuente/s) — [Alphabet (GOOGL) Q2 2026 Earnings: Revenue Beats, Cloud Surges 82% - webull.com](https://news.google.com/rss/articles/CBMimwFBVV95cUxOSXJDNzkxOFBVSmxsZThoNmt3Z0kweFhIT096V095YWdJd2wzWVU1MUtLVW81VGdJb0VIbmVncmFYcmZxRThuTFdsbzQ2OWs0OVJNYVVoRmsybWw4aHdGQW5zLXdOcWJHalNfczBfUTE2SFluYTFHT2ZubExJSWlVRzJmMUFiMGh0MlQzbUpPYmJ6Szl0QVI1Mm81cw?oc=5)
- `2026-08-28` · **OTROS** · NEUTRA · p=0.07 · _MarketWatch_ (1 fuente/s) — [Alphabet Inc. Cl C stock underperforms Friday when compared to competitors despite daily gains - MarketWatch](https://news.google.com/rss/articles/CBMigAJBVV95cUxQc09Hb3dxYm9iS0Q0d1hfZE4tempMMlZSR0NBSEtXeFE5ZEhQSjMyM2xyNmFiRFpDU0VVNExrNXdYbmYxTWZmSGxTRkJ5Wlp2dnNZQzlmdE83WjB2aEVTc0kzTkJuZTc4RHFJYm1pbGxOal9jbHR0dnlGR3VSMlNHYXZ5S3FMVElMcjdNeDhwSEJGRGhHR2x4YnNZSEJPZGwtSDdEaThZa09fUVF6akhfMURkblBpY2RXUnVDWjFHREFnX0RuWFByVXYyekRvSmFMaXFNWXNETE1TSGFkcEVTY2ZpMWV4WjQwOHFKcEVCUnBjSUZyQUJTeWNkWGdoREdq?oc=5)
- `2026-08-27` · **OTROS** · NEUTRA · p=0.03 · _Britannica_ (1 fuente/s) — [Alphabet, Inc. | History, Products, & Business Segments - Britannica](https://news.google.com/rss/articles/CBMiWEFVX3lxTE5NVVd3cUlOc29HTUJyTDBvd0RQZlA2YWJScFZpd05EemlQZ09teUlLaFpKQUdlQUZQdFQ0VFBFQkU4YTdZcm04TXpxaVpGNkY0OEluLU5NZlo?oc=5)

**Lectura:** El informe sobre Alphabet Inc. refleja resultados trimestrales positivos impulsados por un fuerte crecimiento en la nube que sustentan una dirección probable alcista, con una probabilidad de impacto en el precio baja de 0,24 basada en doce noticias analizadas de treinta días, aunque el análisis está degradado debido a que la fuente tavily no respondió. Las menciones a los resultados proceden de titulares de agregadores y artículos web sin confirmación regulatoria directa explícita en los metadatos, y no se dispone de magnitud numérica cuantificada para el impacto estimado más allá de los datos cerrados proporcionados.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (8 argumentos)

- Crecimiento de ingresos sólido del 24.2%, muy por encima del sector (mediana de Communication Services: 8%).
- Margen neto muy alto del 54.8%, muy por encima del sector.
- ROIC del 29.9%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 61%, indicio de poder de fijación de precios.
- PEG de 0.06 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Momentum favorable (+22.8/100), RSI 33.7 (neutral).
- Solvencia 91.8/100: el balance aguanta un escenario adverso sin comprometer la tesis.
- Flujo de noticias con probabilidad de impacto BAJA (0.24) y sesgo ALCISTA sobre 12 nota(s); principal catalizador: "Alphabet (GOOGL) Q2 2026 Earnings: Revenue Beats, Cloud Surges 82% - webull.com" (capa asesora: no altera el dictamen).

**🐻 Tesis bajista** (1 argumento)

- 4 discrepancia(s) entre proveedores de datos; confianza del 91%.

**⚖️ Síntesis:** La tesis alcista para GOOGL se sostiene sobre sólidos fundamentos cuantitativos que incluyen un crecimiento de ingresos del 24.2% frente al 8% de la mediana del sector, un margen neto del 54.8% y un ROIC del 29.9% que supera el coste de capital del 9%, reflejando creación de valor respaldada además por un margen bruto del 61%, un PEG de 0.06, un momentum de 22.8 sobre 100, un RSI de 33.7 y una solvencia de 91.8 sobre 100. Por el contrario, la tesis bajista no aporta argumentos sustentados en los datos, limitándose a señalar cuatro discrepancias entre proveedores y una confianza del 91%, mientras que el flujo de noticias muestra un sesgo alcista con baja probabilidad de impacto de 0.24 sobre doce notas. La conclusión de la unidad de debate evidencia un desequilibrio claro, donde la postura alcista está respaldada exhaustivamente por métricas financieras y operativas, frente a una postura bajista fundamentada únicamente en discrepancias de proveedores sin datos negativos adicionales.

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 12% en dos trimestres consecutivos.
- Que el margen neto baje del 32.9%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($334.04) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `COMPRA` — asignación objetivo **9.33%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **66.9**/100 × peso 0.65 + momentum normalizado **61.4**/100 × peso 0.35 = **65.0**/100
- Corte alcanzado: **COMPRA**

**Cómo se calculó el tamaño**

> `peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

| Factor | Valor |
| :--- | ---: |
| Escala de convicción | ×0.923 |
| Riesgo asumible por posición | 0.692% del patrimonio |
| Distancia al stop | 4.6% |
| Peso por presupuesto de riesgo | 15.18% |
| Factor de volatilidad | ×0.676 |
| Factor de confianza en datos | ×0.909 |
| Factor de banderas rojas | ×1.0 |
| Factor de sobreextensión técnica | ×1.0 |
| **Peso final** | **9.33%** |

_riesgo por posición 0.69% sobre un stop al 4.6%, escalado por volatilidad ×0.68_

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $340.65 | — | — |
| Stop-loss | $325.12 | −4.6% | 2.5× |
| Objetivo | $371.70 | +9.1% | 5.0× |

- **Ratio riesgo/recompensa:** 2.0 → exige acertar el **33.3%** de las veces solo para no perder dinero.
- **Horizonte:** 252 sesiones (~12.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 252 sesiones (~12 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** La mesa ejecutará una orden de compra sobre GOOGL asignando el 9.33 por ciento de la cartera al precio actual de 340.65 dólares, respaldada por una convicción fundamental de 67 sobre 100 y un momentum de 23 sobre 100, sin que consten vetos ni banderas rojas que limiten la operativa. La gestión del riesgo queda fijada estrictamente en un nivel de stop de 325.12 dólares frente a un objetivo de 371.70 dólares, lo que arroja una relación de riesgo beneficio de 2.00 en un horizonte temporal de 252 sesiones. Esta directriz se emite bajo el estilo de calidad compuesta con los parámetros cerrados indicados, obligando a la mesa a respetar íntegramente los límites de precio y plazo sin desviaciones ni redondeos.

---

## 5. Calidad de los datos

Ningún dictamen es mejor que los datos que lo sostienen. Esta sección declara qué se sabe y qué no de cada valor, porque la ausencia de un dato se propaga a la convicción y, por esa vía, al tamaño de la posición.

| Ticker | Confianza | Fuentes | Cobertura fundamental | Campos ausentes | Discrepancias |
| :--- | ---: | :--- | ---: | :--- | ---: |
| **NRGV** | 85% | yfinance, SEC EDGAR (Oficial), Finnhub | 77% | — | 3 |
| **DOCN** | 89% | yfinance, SEC EDGAR (Oficial), Finnhub | 96% | — | 4 |
| **GOOGL** | 91% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 4 |

**Discrepancias entre proveedores:**

- `NRGV` — revenue_growth: dispersión del 69% entre yfinance (1.041) vs SEC EDGAR (derivado) (3.409)
- `NRGV` — debt_to_equity: dispersión del 94% entre yfinance (7.513) vs SEC EDGAR (derivado) (0.4227)
- `NRGV` — roe: dispersión del 80% entre yfinance (-1.786) vs Finnhub (-2.367) vs SEC EDGAR (derivado) (-0.463)
- `DOCN` — revenue_growth: dispersión del 46% entre yfinance (0.286) vs Finnhub (0.2314) vs SEC EDGAR (derivado) (0.1548)
- `DOCN` — net_margin: dispersión del 19% entre yfinance (0.2326) vs Finnhub (0.2327) vs SEC EDGAR (derivado) (0.2876)
- `DOCN` — roe: dispersión del 91% entre yfinance (0.6227) vs Finnhub (0.0563)
- `DOCN` — pe_ratio: dispersión del 24% entre yfinance (50.55) vs Finnhub (66.12)
- `GOOGL` — revenue_growth: dispersión del 43% entre yfinance (0.242) vs Finnhub (0.1715) vs SEC EDGAR (derivado) (0.1387)
- `GOOGL` — net_margin: dispersión del 31% entre yfinance (0.5477) vs Finnhub (0.5477) vs SEC EDGAR (derivado) (0.3776)
- `GOOGL` — debt_to_equity: dispersión del 41% entre yfinance (0.1886) vs SEC EDGAR (derivado) (0.1121)
- `GOOGL` — roe: dispersión del 37% entre yfinance (0.4868) vs Finnhub (0.5084) vs SEC EDGAR (derivado) (0.3183)

<details><summary>Procedencia de cada magnitud reconciliada</summary>

- `NRGV`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `DOCN`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `GOOGL`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance

</details>

---

## 6. Limitaciones y track record

**El sistema NO bate a comprar y mantener el índice.** Backtest en régimen `pit` sobre 2015-01-02 → 2025-12-30 (generado el 2026-08-21T12:00, ver `output/backtest_report.md`):

| Métrica | Estrategia | SPY |
| :--- | ---: | ---: |
| CAGR | 3.9% | 13.5% |
| Volatilidad anualizada | 6.0% | 17.8% |
| Sharpe | 0.68 | 0.80 |
| Sortino | 0.86 | 0.98 |
| Máximo drawdown | -13.8% | -33.7% |

Frente a la selección aleatoria, la estrategia queda en el **percentil 7.4** — **por debajo** de la mediana de carteras aleatorias con el mismo perfil de exposición, lo que significa que la selección de valores no aporta.

> **Cuidado al comparar el CAGR.** La estrategia opera con una volatilidad del 6.0% frente al 17.8% del índice, porque el presupuesto de riesgo la mantiene estructuralmente poco invertida. Comparar rentabilidades absolutas entre carteras con perfiles de riesgo tan distintos favorece mecánicamente a la más expuesta; el Sharpe y el Sortino son la comparación pertinente.

**Limitaciones metodológicas vigentes:**

- **Universo con sesgo de supervivencia.** Solo se analizan valores que existen hoy.
- **Normas sectoriales estáticas.** Las medianas de comparación son de largo plazo, no la mediana viva del sector. Ordenan y contextualizan; no valoran.
- **Coste de capital constante.** Se usa un WACC de referencia común en lugar de estimarlo por empresa: la dispersión de un WACC estimado con beta y estructura de capital sería mayor que la señal que aporta.
- **Sin datos intradía.** La ejecución se modela al cierre y la apertura siguiente.
- **Riesgo legal y regulatorio fuera de la decisión.** Un litigio por fraude de valores aparece en la capa de noticias pero no toca el tamaño de la posición, porque esa capa no es reconstruible point-in-time. Debe activar revisión manual.
- **Sin Finnhub histórico** en el backtest, y contrastes múltiples sin corregir.

---

## 7. Anexo metodológico

**Umbrales del filtro fundamental**

- Margen neto mínimo: 5.0%
- Crecimiento de ingresos mínimo: 5.0%
- Deuda/Patrimonio máxima: 3.00x (ajustada al alza en servicios financieros, inmobiliario y utilities, donde el apalancamiento alto es estructural)

**Política de riesgo y cartera**

- Riesgo por posición: 0.75% del patrimonio al stop
- Riesgo agregado máximo: 5.0%
- Peso máximo por posición: 10%
- Límite por sector: 30%
- Exposición bruta máxima: 95%
- Volatilidad objetivo por posición: 25% anualizada

**Origen de las reglas de calidad y valoración**

- *Piotroski (2000)* — F-Score de 9 puntos sobre rentabilidad, apalancamiento y eficiencia, medidos como variación interanual.
- *Altman (1968)* — Z-Score de solvencia; variante Z'' para no manufactureras.
- *Graham (1949)* — Número de Graham y criterios del inversor defensivo.
- *Buffett* — ROIC sostenido sobre el coste del capital, margen bruto como aproximación al foso, beneficio del propietario.
- *Lynch (1989)* — PEG y taxonomía por perfil de crecimiento.
- *Greenblatt (2005)* — rendimiento del beneficio sobre valor de empresa y rentabilidad del capital tangible.
- *Sloan (1996)* — ratio de devengos: el beneficio que no es caja revierte.

**Papel del modelo de lenguaje**

Ninguna variable de decisión depende del LLM. Los agentes calculan rating, tamaño, stop, objetivo y etiqueta de estilo con reglas deterministas; el modelo solo puede sobrescribir los campos de texto, y siempre después de que todo esté fijado. Sin clave de API el sistema produce exactamente los mismos dictámenes. Esta propiedad se verifica en tiempo de ejecución con `assert_llm_is_decision_neutral()`.
