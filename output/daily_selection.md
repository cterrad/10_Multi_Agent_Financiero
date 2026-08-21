# Informe de Inversión — Selección Multi-Agente

**Fecha de análisis:** `2026-08-21 11:46:51`  
**Universo analizado:** DOCN, NRGV, BE, GOOGL, NEM (5 valores)  
**Referencia de mercado:** SPY · 12m 21.3% · 3m 3.1%  
**Capital de referencia:** $100,000

> Este informe es el resultado de un sistema automatizado de análisis. Las recomendaciones se derivan de reglas deterministas y auditables; el modelo de lenguaje interviene únicamente en la redacción de los resúmenes, nunca en el cálculo de ratings, tamaños de posición ni niveles de riesgo. **No constituye asesoramiento de inversión.**

---

## 1. Resumen ejecutivo

| Ticker | Empresa | Sector | Estilo | Convicción | Filtro | Momentum | Dictamen | Peso | Stop | Objetivo | R:R | Horizonte |
| :--- | :--- | :--- | :--- | ---: | :---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| **DOCN** | DigitalOcean Holdings, Inc. | Technology | `CALIDAD_DETERIORADA` | 19 | ✅ | +28 | **VENTA FUERTE** | 0.00% | $92.09 | $153.30 | 1.75 | 126d |
| **NRGV** | Energy Vault Holdings, Inc. | Utilities | `ESPECULATIVA` | 0 | ❌ | n/d | **VENTA FUERTE** | 0.00% | n/d | n/d | n/d | n/d |
| **BE** | Bloom Energy Corporation | Industrials | `ESPECULATIVA` | 0 | ✅ | +34 | **VENTA FUERTE** | 0.00% | $171.16 | $265.12 | 2.00 | 42d |
| **GOOGL** | Alphabet Inc. | Communication Services | `CALIDAD_COMPUESTA` | 67 | ✅ | +26 | **COMPRA** | 6.07% | $317.30 | $387.42 | 2.00 | 252d |
| **NEM** | Newmont Corporation | Basic Materials | `CALIDAD_COMPUESTA` | 74 | ✅ | +27 | **COMPRA** | 2.89% | $115.41 | $152.09 | 2.00 | 252d |

**Cómo leer esta tabla.** La *convicción* (0-100) resume calidad, valoración, crecimiento y solvencia, ya descontada por la cobertura de datos. El *momentum* (−100 a +100) es la puntuación técnica continua. El *dictamen* sale de cruzar ambas y aplicar los vetos de riesgo. El *peso* es el resultado del presupuesto de riesgo, no un rango fijo: dos valores con el mismo dictamen pueden tener pesos muy distintos si su volatilidad o su distancia al stop difieren. *R:R* es el ratio riesgo/recompensa y el *horizonte* es el plazo al que aplican stop y objetivo.

---

## 2. Cartera propuesta

**Exposición bruta:** 8.96% · **Liquidez:** 91.04% · **Riesgo agregado si todos los stops saltan:** 0.69% del patrimonio (presupuesto: 5.0%)

| Ticker | Sector | Estilo | Convicción | Peso solicitado | Peso final | Riesgo aportado | Correlación media |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| **GOOGL** | Communication Services | `CALIDAD_COMPUESTA` | 67.0 | 6.07% | **6.07%** | 0.42% | 0.222 |
| **NEM** | Basic Materials | `CALIDAD_COMPUESTA` | 73.8 | 2.89% | **2.89%** | 0.28% | 0.222 |

**Concentración por sector** (límite: 30%)

- Communication Services: 6.07%
- Basic Materials: 2.89%

**Diagnóstico de diversificación**

- Posiciones: **2**
- Posiciones efectivas (inverso de Herfindahl): **1.78**
- Volatilidad estimada de la cartera: **2.98%**
- Suma ponderada de volatilidades: **3.75%**
- Ratio de diversificación: **1.26**

> Ratio de diversificación 1.0 significa que las posiciones se mueven como una sola; por encima de 1.3 la cartera aporta diversificación real.

> **Sobre la liquidez.** El 91.0% no invertido rinde un 2.0% anual supuesto, lo que aporta 1.82 puntos al resultado. El backtest histórico documenta que ignorar este detalle —dejar el efectivo al 0%— hacía la comparación contra el índice más pesimista de lo debido.

**Candidatos sin asignación** (y por qué):

- `DOCN` (VENTA FUERTE) — VENTA FUERTE no genera asignación en una cartera solo larga
- `NRGV` (VENTA FUERTE) — no supera el filtro fundamental
- `BE` (VENTA FUERTE) — VENTA FUERTE no genera asignación en una cartera solo larga

---

## 3. Reparto por estilo de inversión

El estilo no es una etiqueta descriptiva: determina los múltiplos de ATR del stop y del objetivo, el horizonte de la posición y los vetos que puede aplicar el Fund Manager. Un valor clasificado como TRAMPA_DE_VALOR o ESPECULATIVA no puede recibir un dictamen superior a MANTENER por muy atractivos que sean sus múltiplos.

| Estilo | Valores | Qué significa |
| :--- | :--- | :--- |
| `CALIDAD_COMPUESTA` | GOOGL, NEM | Negocio capaz de reinvertir beneficios por encima de su coste de capital durante años. Es la categoría que persigue Buffett: se paga un múltiplo razonable por una tasa de retorno sostenible, no un múltiplo bajo por un activo estancado. |
| `CALIDAD_DETERIORADA` | DOCN | Negocio rentable con varios defectos estructurales a la vez (caja, devengos, dilución o balance). La calidad operativa no compensa por sí sola un balance deteriorado: la tesis depende de que esos defectos se corrijan, y eso exige revisarla antes. |
| `ESPECULATIVA` | NRGV, BE | El perfil de riesgo domina cualquier lectura de valor o crecimiento. Solvencia comprometida o varias banderas rojas simultáneas. |

---

## 4. Fichas por compañía

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

**Lectura:** **Resumen Financiero - DOCN (Sector Tecnológico)**

DOCN ha superado con éxito el filtro fundamental gracias a un sólido crecimiento de ingresos del 28.6% y un margen neto excepcionalmente rentable del 23.3%. Además, respalda su **APROBACIÓN** con un ROE sobresaliente de 62.3%, a pesar de operar con un nivel de apalancamiento elevado de Deuda/Patrimonio de 2.13x.

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

_Convicción bruta 44.0 × cobertura de datos 1.0 × confianza en fuentes 0.894 − 20.0 por banderas rojas = **19.3**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 8/9 | FUERTE |
| Altman | Z'' (no manufactureras) | 0.04 | zona DISTRESS (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $20.76 | margen de seguridad -450.8% (0/5 criterios defensivos) |
| Greenblatt | EBIT/EV | 1.5% | por debajo del umbral |
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
| P/E | 52.9x | 26.0x | 2.04 | muy por encima del sector |
| Margen neto | 23.3% | 15% | 1.55 | muy por encima del sector |
| Deuda/Patrimonio | 2.1x | 0.6x | 3.54 | muy por encima del sector |
| Crecimiento de ingresos | 28.6% | 12% | 2.38 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**🚩 Banderas rojas:**

- Altman Z'' (no manufactureras) en zona de insolvencia (Z=0.04 < 1.1); el Z está distorsionado por un patrimonio contable negativo, así que conviene leerlo junto a la generación de caja
- Patrimonio neto negativo ($-28,690,000): los ratios sobre fondos propios (deuda/patrimonio, ROE) no son interpretables

_Cobertura de datos: 96% (OK)._

**Lectura:** Como Analista de Calidad y Valoración, aquí tienes el resumen de la tesis para **DigitalOcean (DOCN)**:

DigitalOcean opera en un segmento de infraestructura tecnológica con un atractivo ROIC operativo (13.5%) y una alta puntuación de Piotroski (8/9), lo que refleja una excelente eficiencia y disciplina operativa subyacente. Sin embargo, el negocio sufre de una "calidad deteriorada" estructural debido a un patrimonio neto negativo (-$28.69M) que distorsiona los fondos propios y sitúa a la compañía en zona de insolvencia según el Altman Z'', a pesar de su capacidad para generar caja. Por último, con una valoración extremadamente baja (2.3/100) frente a un crecimiento moderado-alto (49.4/100), el mercado descuenta un riesgo de distress financiero severo que el inversor debe sopesar frente a la viabilidad real de su flujo de caja.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +28.1/100) · **Tendencia:** ALCISTA_EN_CORRECCION · **RSI:** 47.95 (NEUTRAL)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +15.00 |
| Macd | -0.21 |
| Rsi | -0.61 |
| Bollinger | -6.03 |
| Momentum precio | +20.00 |
| **Total** | **+28.15** |

- Precio frente a medias: SMA50 -16.4% · SMA200 +22.3%
- Posición en el rango de 52 semanas: 54%
- ATR: $11.13 (9.7% del precio) · Volatilidad anualizada: 86.4%
- Momentum relativo a 12 meses frente al índice: +316.0%

**Señales:**

- Tendencia alcista de fondo con corrección: precio 114.35 por debajo de la SMA50 136.83 pero sobre la SMA200 93.48
- MACD bajista (histograma -0.058, 0.01 ATR)
- RSI neutral con sesgo débil (48.0, entre 30 y 50)
- Precio en el 20% del canal de Bollinger
- Momentum 12m (excl. último mes) +337.3% frente al +21.3% de SPY: exceso +316.0%

**Lectura:** DigitalOcean (DOCN) mantiene una estructura de tendencia alcista en fase de corrección, cotizando por debajo de su SMA50 pero cómodamente por encima de su SMA200. A pesar de mostrar un impulso técnico moderado y positivo en el acumulado, indicadores como el RSI neutral (48.0) y el MACD ligeramente negativo reflejan una pausa compradora en el corto plazo.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `MEDIA` (0.38) · **Dirección probable:** `ALCISTA`

Cobertura: 12 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-17` · **GUIDANCE** · NEUTRA · p=0.13 · _simplywall.st_ (1 fuente/s) — [The Bull Case For DigitalOcean Holdings (DOCN) Could Change Following Mixed Q2 2026 Results And Upbeat Guidance - simplywall.st](https://news.google.com/rss/articles/CBMi1AFBVV95cUxPRkZ2c1dnclFXbXdaQnZsTmhNSnVKNnhCR01HZkJJSS1Rb0ZzNnZnUEYxeEZKZ1RrRzN4dHVjcVg1TEQ2Wm92VjgzN1JCVXZCbWw4T2VMXzBaUmI3OXdDRzhuSFJvMUhtUTRjUHRFWVNZLXVVaUMxYUZlVmVFMmdQZUF3ZFhLVGxTRWxYX1EzZUE5TXJzTUxoUE1iWU9UMk5kZGk2T3FhTVd1REotTFF4cEQ2d2wzTC1fQzNpV3RrbHBGYUppRE41aHJ0dTFaSENja0hfT9IB2gFBVV95cUxOdGdhQ0xLNUJ0Rld4M3F5azFXUy16YTJtVHRsZEptRzM3SjNLWHlMa3VFMVZiNW9feFlURVRtMGhqMVI1Tm5ueVBOUTFPUnNqOG1faTNUakFvbjlZM25CWXpVX3NBaU45WnV1azdvN3J2aTJYRFBQUHpEaU5BaGVKMGFrZkphaFppMWg4Z19TeEM3UV9hcnZUUkFVSTAwbVc5TkJQcGhuR2Q4LVdWdWExUnpsUW45SUhqcUFzYVk4a2l1OFpQR3ZkeU85RGZpZktXT0QxUDNyTlpsUQ?oc=5)
- `2026-08-04` · **RESULTADOS** · NEUTRA · p=0.08 · _SEC EDGAR (8-K)_ (1 fuente/s) — [DigitalOcean Holdings, Inc. presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1582961/000162828026052135/docn-20260804.htm)
- `2026-08-12` · **GUIDANCE** · NEUTRA · p=0.08 · _24/7 Wall St._ (1 fuente/s) — [DOCN Stock Price Prediction 2025-2026 | DigitalOcean Holdings Inc Forecast - 24/7 Wall St.](https://news.google.com/rss/articles/CBMiZEFVX3lxTE41dXUyUXgycTJKY0dqem5KdGVuOGdQUUxlS1hJNlROelVFNmJWa19hbzR1V2xRMmdzcHhIVk00VlZ4VHFtdEhGTEEzcmhuZHJtVlJXb05EZTJlbkVKbFNobldONk4?oc=5)

**Lectura:** **DigitalOcean Holdings, Inc. (DOCN)** ha presentado sus resultados del segundo trimestre y el formulario 8-K, mostrando un balance mixto que fue compensado por unas previsiones de negocio optimistas. Este escenario, respaldado por nuevas revisiones en las proyecciones de precio para el periodo 2025-2026, actúa como catalizador alcista al disipar dudas operativas y reactivar el optimismo sobre el crecimiento futuro de la compañía.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (6 argumentos)

- Crecimiento de ingresos sólido del 28.6%, muy por encima del sector (mediana de Technology: 12%).
- Margen neto sólido del 23.3%, muy por encima del sector.
- Margen bruto del 57%, indicio de poder de fijación de precios.
- F-Score de Piotroski 8/9: la calidad contable mejora en rentabilidad, apalancamiento y eficiencia a la vez.
- Momentum favorable (+28.1/100), RSI 48.0 (neutral).
- Flujo de noticias con probabilidad de impacto MEDIA (0.38) y sesgo ALCISTA sobre 12 nota(s); principal catalizador: "The Bull Case For DigitalOcean Holdings (DOCN) Could Change Following Mixed Q2 2026 Results And Upbeat Guidance - simply" (capa asesora: no altera el dictamen).

**🐻 Tesis bajista** (4 argumentos)

- P/E de 52.9x frente a una mediana sectorial de 26x (2.0 veces la norma de Technology): la valoración descuenta una ejecución impecable.
- Carga financiera elevada: deuda/patrimonio de 2.13x, muy por encima del sector (mediana de Technology: 0.6x).
- Altman Z'' (no manufactureras) en 0.04, por debajo del umbral de insolvencia (1.1).
- 4 discrepancia(s) entre proveedores de datos; confianza del 89%.

**⚖️ Síntesis:** DigitalOcean Holdings (DOCN) presenta una tesis alcista fundamentada en un crecimiento de ingresos del 28.6% —que duplica la mediana del sector de tecnología (12%)—, un margen neto del 23.3% y un margen bruto del 57% que refleja poder de fijación de precios, respaldado además por un sólido F-Score de Piotroski de 8/9 y un flujo de noticias con sesgo alcista. Sin embargo, esta alta calidad operativa contrasta con riesgos financieros y de valoración significativos, evidenciados por un ratio P/E de 52.9x que duplica la norma sectorial (26x), una elevada carga de deuda con un endeudamiento patrimonial de 2.13x frente al 0.6x del sector, y un Altman Z'' de 0.04 que se sitúa por debajo del umbral de insolvencia de 1.1. En conclusión, aunque la compañía exhibe una rentabilidad y eficiencia contable superiores a la media, su cotización exige una ejecución impecable para justificar una valoración tan estricta mientras soporta una posición de solvencia muy comprometida.

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 14% en dos trimestres consecutivos.
- Que el margen neto baje del 14.0%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que el precio pierda la media de 200 sesiones ($93.48) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `VENTA FUERTE` — asignación objetivo **0.00%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **19.3**/100 × peso 0.65 + momentum normalizado **64.1**/100 × peso 0.35 = **35.0**/100
- Corte alcanzado: **VENTA** → tras los vetos: **VENTA FUERTE**

**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):

- 2 banderas rojas fundamentales: se baja un escalón

_Sin asignación: VENTA FUERTE no genera asignación en una cartera solo larga._

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $114.35 | — | — |
| Stop-loss | $92.09 | −19.5% | 2.0× |
| Objetivo | $153.30 | +34.1% | 3.5× |

- **Ratio riesgo/recompensa:** 1.75 → exige acertar el **36.4%** de las veces solo para no perder dinero.
- **Horizonte:** 126 sesiones (~6.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 126 sesiones (~6 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** **ORDEN EJECUTIVA DE INVERSIÓN: DOCN**

**Dictamen: VENTA FUERTE (Calidad Deteriorada).** 
La combinación de una baja convicción fundamental (19.3/100), un momentum deprimido (28.15/100) y graves banderas rojas —como un patrimonio neto negativo de -$28.69M y un Altman Z'' en zona crítica de insolvencia— justifica una asignación del 0.00% en cartera y el cierre inmediato de posiciones. 
Para el horizonte táctico de 126 sesiones, establecemos un precio de salida en $114.35, con un stop loss de protección en $92.09 y un objetivo técnico a la baja en $153.3 (R:R 1.75).

---

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

**Lectura:** Como Analista Fundamental Gatekeeper, la empresa NRGV muestra un crecimiento de ingresos excepcional del 104.1%, pero es insostenible debido a un margen neto negativo de -48.6% y un ROE devastador de -178.6%. Además, su apalancamiento es extremadamente peligroso con una relación Deuda/Patrimonio de 7.51x, lo que justifica plenamente su **RECHAZO** bajo estrictos criterios de salud financiera en el sector Utilities.

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
| Greenblatt | EBIT/EV | -10.2% | por debajo del umbral |
| Buffett | ROIC | -65.2% | -74.2% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 22.5% | sin indicio de foso |
| Buffett | Rendimiento FCF | -7.1% | dilución anual +10.29% |
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
| P/E | -22.9x | 18.0x | -1.27 | por debajo del sector |
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

**Lectura:** Como Analista de Calidad y Valoración, mi veredicto sobre **NRGV** es el siguiente: 

El negocio presenta una **calidad extremadamente deficiente (28.2/100)**, caracterizada por un ROIC profundamente negativo (-65.2%), destrucción neta de valor, márgenes operativos deficitarios y un consumo crónico de caja libre. A nivel financiero, la compañía se encuentra en una situación crítica de **insolvencia técnica (Altman Z'' en -7.56)**, con un apalancamiento insostenible (Deuda/Patrimonio de 7.51x) y una agresiva dilución accionarial anual del 10.3% que castiga al inversor. Por último, aunque cuantitativamente la valoración aparezca a cero, **el precio actual no refleja adecuadamente el riesgo de quiebra inminente** implícito en sus métricas de solvencia y su nula cobertura de intereses.

#### 3. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `MEDIA` (0.38) · **Dirección probable:** `ALCISTA`

Cobertura: 13 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-11` · **RESULTADOS** · NEUTRA · p=0.17 · _SEC EDGAR (8-K)_ (1 fuente/s) — [Energy Vault Holdings, Inc. presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1828536/000182853626000100/nrgv-20260811.htm)
- `2026-08-12` · **RESULTADOS** · NEUTRA · p=0.08 · _Seeking Alpha_ (1 fuente/s) — [Energy Vault Holdings, Inc. 2026 Q2 - Results - Earnings Call Presentation (NYSE:NRGV) 2026-08-12 - Seeking Alpha](https://news.google.com/rss/articles/CBMirgFBVV95cUxQaktxOTJkUi00LXZyVUtFTzloV0F6RHltUjVkeWhfWTg3ZF96S2ctUFIyMDJadjE5VzlTcExuUmNOck81REVPTndBTWlRdnJoU2hsbDhCS19YWFVuWERZZE9MZk90dGlWbVFzdWZaVWQtNGhoVUZWS2dCQWxVTVZ2MFpsTngtX0tKMktoU1RtTWVmcUljMEVhYkNyc2N3YmZBZno0bDdrbFp5NXZ6ckE?oc=5)
- `2026-08-11` · **RESULTADOS** · NEUTRA · p=0.05 · _marketscreener.com_ (1 fuente/s) — [Energy Vault Holdings, Inc. Reports Earnings Results for the Second Quarter and Six Months Ended June 30, 2026 - marketscreener.com](https://news.google.com/rss/articles/CBMi5gFBVV95cUxORktWcGlpM29DUjZoOHBpM2hRMGxhb0w0cDFtdXYxblRUcjNkMjJqOVhwLXBScDFaU0ZFZTJacHM3M2RpUGxoUWVLVGpyNGI1UnN2ckFFRG1obnUxdElORHF4SmRMMWtpMDFjcnlLaWJJVXBaVm9HVXM3dE9KbkZVVUlqU0g1NllSTm9oV3dNSkJnQXkzQjJDOElNcmloQUM1elY3WmU5V3RwdG9LVTBjcTQ2MUtDdXFaSWEwb3A5TWxMcTFvVS1xcWY1WldoS1U3UXZMaTJaM3hGbFlhZ2Vtck9lcWtkQQ?oc=5)

**Lectura:** Energy Vault Holdings, Inc. (NRGV) ha presentado sus resultados financieros correspondientes al segundo trimestre de 2026 mediante el formulario 8-K y su respectiva conferencia de resultados. Este informe operativo y financiero actúa como el catalizador principal que justifica una lectura **ALCISTA** con una probabilidad de impacto en precio **MEDIA (0.38)** tras el análisis de las 13 noticias recientes.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 4. Dictamen del Fund Manager

### 🎯 `VENTA FUERTE` — asignación objetivo **0.00%** de la cartera

**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):

- Gatekeeper: RECHAZADO

_Sin asignación: no supera el filtro fundamental._

**Orden ejecutiva:** Dictamen Final (NRGV): VENTA FUERTE. Sin asignación de cartera. Rechazado en el filtro fundamental. Como Analista Fundamental Gatekeeper, la empresa NRGV muestra un crecimiento de ingresos excepcional del 104.1%, pero es insostenible debido a un margen neto negativo de -48.6% y un ROE devastador de -178.6%. Además, su apalancamiento es extremadamente peligroso con una relación Deuda/Patrimonio de 7.51x, lo que justifica plenamente su **RECHAZO** bajo estrictos criterios de salud financiera en el sector Utilities.

---

### BE — Bloom Energy Corporation

**Sector / Industria:** Industrials / Electrical Equipment & Parts  
**Estilo:** `ESPECULATIVA` (secundarias: CICLICA)  
**Confianza en los datos:** 67% · Fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

#### 1. Filtro fundamental — APROBADO

| Criterio | Valor | Umbral | Cumple |
| :--- | ---: | ---: | :---: |
| Margen neto | 7.9% | 5.0% | ✅ |
| Crecimiento de ingresos | 165.5% | 5.0% | ✅ |
| Deuda / Patrimonio | 1.72x | 3.00x | ✅ |

- ℹ️ 5 discrepancia(s) entre proveedores; confianza rebajada al 67%.

**Lectura:** Como Analista Fundamental Gatekeeper, BE demuestra una excelente salud financiera impulsada por un impresionante crecimiento de ingresos del 165.5% y una sólida rentabilidad con un ROE del 22.2% y margen neto positivo de 7.9%. A pesar de un apalancamiento elevado con una relación Deuda/Patrimonio de 1.72x, la empresa supera con éxito los estándares de calidad, justificando su veredicto de APROBADO.

#### 2. Calidad y valoración

```
Calidad      ████████░░░░░░░░░░░░ 40/100
Valoración   ██░░░░░░░░░░░░░░░░░░ 9/100
Crecimiento  ██████████░░░░░░░░░░ 50/100
Solvencia    ██████████░░░░░░░░░░ 51/100
────────────────────────────────────────
CONVICCIÓN   ░░░░░░░░░░░░░░░░░░░░ 0/100
```

**Estilo `ESPECULATIVA`** — Solvencia 51.1/100 y 3 bandera(s) roja(s): el perfil de riesgo domina cualquier lectura de valor o crecimiento.

_Convicción bruta 36.5 × cobertura de datos 1.0 × confianza en fuentes 0.674 − 30.0 por banderas rojas = **0.0**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 4/9 | INTERMEDIO |
| Altman | Z (manufactureras) | 9.94 | zona SEGURA (seguro > 2.99, insolvencia < 1.81) |
| Graham | Nº de Graham | $9.63 | margen de seguridad -2002.6% (1/5 criterios defensivos) |
| Greenblatt | EBIT/EV | -0.1% | por debajo del umbral |
| Buffett | ROIC | -1.8% | -10.8% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 31.6% | sin indicio de foso |
| Buffett | Rendimiento FCF | 0.1% | dilución anual +22.21% |
| Lynch | PEG | 1.63 | EXIGENTE · categoría CICLICA (sobre crecimiento de ingresos) |
| Sloan | Devengos | -4.6% | beneficio respaldado por caja |

<details><summary>Desglose del F-Score de Piotroski</summary>

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ❌ | ROA=-2.01% |
| Flujo de caja operativo positivo | ✅ | FCO=113,949,000 |
| ROA en mejora | ❌ | -1.10% → -2.01% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ❌ | 38.17% → 59.45% |
| Ratio corriente en mejora | ✅ | 3.21 → 5.98 |
| Sin emisión neta de acciones | ❌ | dilución controlada |
| Margen bruto en mejora | ✅ | 27.46% → 29.02% |
| Rotación de activos en mejora | ❌ | 0.55x → 0.46x |

</details>

**Contexto sectorial (Industrials)** — el punto de comparación que convierte «P/E elevado» en una afirmación verificable:

| Métrica | Valor | Mediana del sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 270.0x | 20.0x | 13.5 | muy por encima del sector |
| Margen neto | 7.9% | 8% | 0.98 | en línea con el sector |
| Deuda/Patrimonio | 1.7x | 0.9x | 1.91 | muy por encima del sector |
| Crecimiento de ingresos | 165.5% | 7% | 23.64 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

**🚩 Banderas rojas:**

- Dilución del 22.2% anual: el crecimiento por acción es menor que el agregado
- Cobertura de intereses insuficiente (-0.57x)
- ROIC negativo (-1.8%): destruye valor sobre el capital empleado

_Cobertura de datos: 92% (OK)._

**Lectura:** Como Analista de Calidad y Valoración, esta es la síntesis de la tesis para **BE**:

1. **Calidad y Destrucción de Valor:** El negocio opera con fundamentales muy débiles (calidad 40.2/100 y ROIC negativo de -1.8%), lo que evidencia una destrucción crónica de valor sobre el capital empleado y una incapacidad operativa para cubrir sus costes de financiación (cobertura de intereses de -0.57x).
2. **Efecto Dilutivo:** Aunque presenta un perfil especulativo y cierto crecimiento bruto (50/100), este se ve severamente castigado por una agresiva dilución anual del 22.2%, provocando que el crecimiento real por acción sea muy inferior al agregado.
3. **Desajuste en Valoración:** A pesar de mostrar una puntuación de valoración aparentemente baja (8.9/100) y un PEG de 1.63, el precio **no** refleja adecuadamente la baja calidad del negocio ni el elevado riesgo de solvencia implícito en sus banderas rojas, desaconsejando su inclusión bajo criterios fundamentales estrictos.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +34.0/100) · **Tendencia:** ALCISTA_EN_CORRECCION · **RSI:** 48.59 (NEUTRAL)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +15.00 |
| Macd | +1.38 |
| Rsi | -0.42 |
| Bollinger | -1.98 |
| Momentum precio | +20.00 |
| **Total** | **+33.98** |

- Precio frente a medias: SMA50 -16.6% · SMA200 +8.7%
- Posición en el rango de 52 semanas: 52%
- ATR: $20.88 (10.3% del precio) · Volatilidad anualizada: 123.6%
- Momentum relativo a 12 meses frente al índice: +363.4%

**Señales:**

- Tendencia alcista de fondo con corrección: precio 202.48 por debajo de la SMA50 242.89 pero sobre la SMA200 186.28
- MACD alcista (histograma +0.721, 0.03 ATR)
- RSI neutral con sesgo débil (48.6, entre 30 y 50)
- Precio en el 40% del canal de Bollinger
- Momentum 12m (excl. último mes) +384.7% frente al +21.3% de SPY: exceso +363.4%

**Lectura:** El precio de BE cotiza en $202.48, manteniéndose por encima de su media móvil de 200 periodos ($186.28) dentro de una estructura alcista en fase de corrección. Aunque el RSI se encuentra neutral en 48.6, el histograma MACD positivo (+0.721) y la puntuación de momentum de +34.0 reflejan un sesgo moderadamente alcista sin mostrar sobrecompra ni sobreventa.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `BAJA` (0.18) · **Dirección probable:** `BAJISTA`

Cobertura: 13 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-18` · **REGULATORIO** · BAJISTA · p=0.04 · _TMX Newsfile_ (1 fuente/s) — [SHAREHOLDER ALERT Bernstein Liebhard LLP Announces A Securities Fraud Class Action Lawsuit Has Been Filed Against Bloom Energy Corporation (BE) - TMX Newsfile](https://news.google.com/rss/articles/CBMikwJBVV95cUxNYXZEVnpOTFl0NnhrQkx4NFQtQ3FaRFdLSkJmSGI0SmdRUzJsM3ZkY25XNWdVQW1BUmRDaEVDR3lHaDNBOEtMV0REcm9OVGNGOXdEdmFabDM1cnRtSVFGZHEyaUp0Y0VrNWZYSjlDVFpwdk1mWHAzTm5VVDZyTFhaY3llMUk2NzNsTHFGd0FaaE9QZkdIcjhjVDRFbXFEY0ltbFpYWmNmblpaVTdZTmMzd09GeFQzdzRadU0tNTJfUWpCZDZ3ZTE2ZmdCVjhIRXZ4cnNqV1ZDWVp3bTNsWTE5TE9CeUdmNXp5MXpHdmJpcXpRMUZaSk5fQXNWdGxFdndKclp4MFN0WlF3RUJLSW1MQXp6RQ?oc=5)
- `2026-07-28` · **RESULTADOS** · NEUTRA · p=0.04 · _SEC EDGAR (8-K)_ (1 fuente/s) — [Bloom Energy Corporation presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1664703/000162828026050150/be-20260728.htm)
- `2026-07-28` · **RESULTADOS** · ALCISTA · p=0.03 · _Business Wire_ (1 fuente/s) — [Bloom Energy Reports Record Second Quarter 2026 Financial Results and Raises Full Year 2026 Guidance - Business Wire](https://news.google.com/rss/articles/CBMi7gFBVV95cUxPUkFyaGU3UXlMaVgyemdycmcxZmh5cHJCaGNBVE4yOWhCdmVnWXV4a0VlNnFOT09ZOGE0ZWFuaDRnVTlNcXM5ZzB4VTU4T0duR1dobTFBR21MVXhkaUtKd1h4bHJ4ZlJ4SVV2a01tY0RUbF92QWFQNm13TS1RTTd5eDJhMEVaWGFXaE5NNV91dDlBRFVqRGxlNDZPQnNaS0VtSFhkQXpGanR1dUJOVW9samN3MjBBV18zLXV4X2hlR0VwanZULVVkbWQzZ1Z3dW1DRUhZbFVPYXczZ25uXzlTVk9BT2psRjg2S1haV09n?oc=5)

**Lectura:** **Qué ha pasado:** Bloom Energy ha reportado unos resultados récord en el segundo trimestre de 2026 y elevado sus previsiones anuales, aunque simultáneamente se enfrenta a una demanda colectiva por presunto fraude de valores anunciada por el bufete Bernstein Liebhard LLP. 

**Por qué puede mover la acción:** La incertidumbre legal y el riesgo reputacional derivado de la demanda por fraude introducen presión vendedora en el valor, contrarrestando el optimismo generado por los sólidos fundamentales y el incremento de guía financiera.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (3 argumentos)

- Crecimiento de ingresos excepcional del 165.5%, muy por encima del sector (mediana de Industrials: 7%).
- Margen neto aceptable del 7.9%, en línea con el sector.
- Momentum favorable (+34.0/100), RSI 48.6 (neutral).

**🐻 Tesis bajista** (5 argumentos)

- P/E de 270.0x frente a una mediana sectorial de 20x (13.5 veces la norma de Industrials): la valoración descuenta una ejecución impecable.
- Carga financiera moderada: deuda/patrimonio de 1.72x, muy por encima del sector (mediana de Industrials: 0.9x).
- Dilución del 22.2% anual: el accionista existente captura menos crecimiento del que muestra el agregado.
- 5 discrepancia(s) entre proveedores de datos; confianza del 67%.
- Flujo de noticias con probabilidad de impacto BAJA (0.18) y sesgo BAJISTA sobre 13 nota(s); principal catalizador: "SHAREHOLDER ALERT Bernstein Liebhard LLP Announces A Securities Fraud Class Action Lawsuit Has Been Filed Against Bloom " (capa asesora: no altera el dictamen).

**⚖️ Síntesis:** **Síntesis del Debate de Inversión: BE (Industrials)**

**Tesis Alcista**
Bloom Energy destaca por un crecimiento de ingresos excepcional del 165.5%, aplastando la mediana del sector industrial (7%). Este dinamismo se apoya en un margen neto aceptable del 7.9% —en línea con el sector—, un momentum favorable de +34.0/100 y un RSI neutral de 48.6. 

**Tesis Bajista**
El entusiasmo operativo choca con riesgos financieros y de valoración extremos. El ratio P/E se sitúa en unas desorbitadas 270.0x frente a la mediana sectorial de 20x (13.5 veces la norma), exigiendo una ejecución impecable. A esto se suma una deuda sobre patrimonio de 1.72x (casi el doble del sector) y una severa dilución anual del 22.2% que reduce el valor real para el accionista existente. Las discrepancias de datos (confianza del 67%) y una demanda por fraude de valores (aunque sin impacto actual según el asesor) completan un panorama de alta vulnerabilidad.

**Conclusión Imparcial**
BE ofrece un crecimiento de ingresos del 165.5% y un margen neto del 7.9% que contrastan fuertemente con una valoración excesiva (P/E de 270.0x) y una alta dilución anual del 22.2%. La elevada deuda (1.72x) y la incertidumbre legal añaden riesgo a un perfil donde el momentum favorable (+34.0) y la neutralidad técnica (RSI 48.6) apenas compensan el desequilibrio financiero. Por tanto, se trata de una apuesta especulativa sujeta a que la compañía justifique múltiplos 13.5 veces superiores a los de su sector industrial.

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 83% en dos trimestres consecutivos.
- Que el margen neto baje del 4.7%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que el precio pierda la media de 200 sesiones ($186.28) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `VENTA FUERTE` — asignación objetivo **0.00%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **0.0**/100 × peso 0.65 + momentum normalizado **67.0**/100 × peso 0.35 = **23.4**/100
- Corte alcanzado: **VENTA FUERTE**

**Ajustes a la baja aplicados** (ninguna condición puede mejorar un rating):

- Estilo ESPECULATIVA: el dictamen no puede superar MANTENER
- 3 banderas rojas fundamentales: se baja un escalón

_Sin asignación: VENTA FUERTE no genera asignación en una cartera solo larga._

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $202.48 | — | — |
| Stop-loss | $171.16 | −15.5% | 1.5× |
| Objetivo | $265.12 | +30.9% | 3.0× |

- **Ratio riesgo/recompensa:** 2.0 → exige acertar el **33.3%** de las veces solo para no perder dinero.
- **Horizonte:** 42 sesiones (~2.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 42 sesiones (~2 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** **ORDEN EJECUTIVA DE INVERSIÓN – BE**

Se emite un dictamen de **VENTA FUERTE (ESTPECULATIVA)** con una asignación del **0.00%** de la cartera, sustentado en una convicción fundamental de 0.0/100, un momentum de 33.98/100 y vetos estrictos aplicados por dilución del 22.2% anual, cobertura de intereses insuficiente (-0.57x) y un ROIC negativo (-1.8%) que destruye valor. Operativamente, se establece un precio actual de $202.48, un stop en $171.16 y un objetivo de $265.12, contemplando una relación Riesgo:Beneficio de 2.0. Esta postura táctica debe evaluarse estrictamente dentro de un horizonte de 42 sesiones, priorizando la salida total ante la persistencia de las banderas rojas estructurales.

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

**Lectura:** Como Analista Fundamental Gatekeeper, el sólido desempeño de Alphabet (GOOGL) está respaldado por un sobresaliente crecimiento de ingresos del 24.2% y un margen neto excepcional del 54.8%. Asimismo, su alta rentabilidad con un ROE de 48.7% y un bajo apalancamiento financiero de 0.19x justifican su **APROBACIÓN** bajo nuestros filtros de calidad.

#### 2. Calidad y valoración

```
Calidad      ████████████████░░░░ 80/100
Valoración   ███████░░░░░░░░░░░░░ 36/100
Crecimiento  ██████████████████░░ 91/100
Solvencia    ██████████████████░░ 92/100
────────────────────────────────────────
CONVICCIÓN   █████████████░░░░░░░ 67/100
```

**Estilo `CALIDAD_COMPUESTA`** — Calidad 80.4/100 y solvencia 91.8/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción bruta 73.8 × cobertura de datos 1.0 × confianza en fuentes 0.909 − 0.0 por banderas rojas = **67.0**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 6/9 | INTERMEDIO |
| Altman | Z'' (no manufactureras) | 7.14 | zona SEGURA (seguro > 2.6, insolvencia < 1.1) |
| Graham | Nº de Graham | $150.16 | margen de seguridad -126.9% (2/5 criterios defensivos) |
| Greenblatt | EBIT/EV | 3.9% | por debajo del umbral |
| Buffett | ROIC | 29.9% | +20.9% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 60.9% | indicio de foso competitivo |
| Buffett | Rendimiento FCF | 1.8% | dilución anual -1.01% |
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
| P/E | 17.3x | 19.0x | 0.91 | en línea con el sector |
| Margen neto | 54.8% | 12% | 4.56 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.8x | 0.24 | por debajo del sector |
| Crecimiento de ingresos | 24.2% | 8% | 3.02 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

_Cobertura de datos: 100% (OK)._

**Lectura:** Como Analista de Calidad y Valoración, aquí tienes el resumen de la tesis para **Alphabet (GOOGL)**:

Alphabet destaca como un negocio de **excepcional calidad y solvencia** (ambas por encima de 90), respaldado por un ROIC sobresaliente del 29,9% y una salud financiera blindada en zona segura según el Altman Z-Score. 

A pesar de ser una máquina de crecimiento con métricas dinámicas (PEG de 0,06 y un pilar de crecimiento de 91), el mercado ofrece una **valoración muy atractiva** (36,2/100), lo que sugiere que el precio actual no refleja plenamente su tremendo potencial operativo ni su reciente e incipiente perfil de dividendo. 

Al no presentar banderas rojas y mantener una sólida consistencia fundamental (Piotroski 6/9), la compañía se consolida como una **compra de alta convicción** bajo nuestro estilo de Calidad Compuesta y Lynch.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +26.2/100) · **Tendencia:** ALCISTA_EN_CORRECCION · **RSI:** 39.27 (NEUTRAL)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +15.00 |
| Macd | -3.34 |
| Rsi | -3.22 |
| Bollinger | -2.25 |
| Momentum precio | +20.00 |
| **Total** | **+26.19** |

- Precio frente a medias: SMA50 -3.2% · SMA200 +2.5%
- Posición en el rango de 52 semanas: 68%
- ATR: $9.35 (2.7% del precio) · Volatilidad anualizada: 37.9%
- Momentum relativo a 12 meses frente al índice: +38.2%

**Señales:**

- Tendencia alcista de fondo con corrección: precio 340.67 por debajo de la SMA50 352.00 pero sobre la SMA200 332.46
- MACD bajista (histograma -0.780, 0.08 ATR)
- RSI neutral con sesgo débil (39.3, entre 30 y 50)
- Precio en el 39% del canal de Bollinger
- Momentum 12m (excl. último mes) +59.5% frente al +21.3% de SPY: exceso +38.2%

**Lectura:** GOOGL mantiene una estructura de tendencia alcista en corrección, cotizando por debajo de su SMA de 50 periodos ($352.0) pero manteniéndose firmemente sobre su SMA de 200 periodos ($332.46). Con un RSI neutral en 39.3 y un histograma MACD negativo, el impulso actual es moderado y refleja una fase de consolidación dentro de su rango anual.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `BAJA` (0.07) · **Dirección probable:** `INCIERTA`

Cobertura: 13 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-07-22` · **RESULTADOS** · NEUTRA · p=0.02 · _SEC EDGAR (8-K)_ (1 fuente/s) — [Alphabet Inc. presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000066/goog-20260722.htm)
- `2026-08-06` · **OTROS** · NEUTRA · p=0.02 · _Reuters_ (1 fuente/s) — [Alphabet looks to raise up to $25 billion from latest bond sale, source says - Reuters](https://news.google.com/rss/articles/CBMiuAFBVV95cUxPWUk1NnFMWVUwZEJJTmpvWExsa0hoNWhpbUJXMlpFWUpoY2xtNDk4VGFBTEZORlRQSWVCd3ZsYXBtSTh1ZlJDX2E0OWtFMk5nWW5WV0VNUkJ5REpad2VMMTNrZVBqbERDYWg2QUs2N1hFcHRKRkloQ090VG9lQ3lrLTYyb3otQ243ZzhrQ1pRckZqUmpTMTJoMjVGc1IzQUJpd3BZemd2RHVZRF9WcVg1c2lDdWdia1dU?oc=5)
- `2026-07-24` · **RESULTADOS** · NEUTRA · p=0.01 · _morning-times.com_ (1 fuente/s) — [Google's Q2 earnings of $112.11B beat Wall Street's expectations on AI boom - morning-times.com](https://news.google.com/rss/articles/CBMi9wFBVV95cUxPNUp3bVNaajJHNjlNRXR3c1MtUjB4ZXNvc0VkTUs3SjNBN1lDSkdac1BnWDN0eFY3NHFtemgyS0dkOWZ4RUxFSmg1dm50dTUwMkNrc1NxTDgtOXlPVGxwNEdXTnBiQ1ZsTzNENVVxTmU5d3diSkFsRG8zUDlNR2xkYi1VeUloLVl2eE9qMnh3aTUwb0lDM2Y1el9nMl85SFg4REt4YmNqVE1Oc0hBVWVOWnNrSl9UOHhMS1NOMGRrMmFoSkZPbU04OWlORmNYd0Q2aTB5dmU5RS1Mek1WekZvRjJLT3lnR2ZLajBERUhRUmI0TVg5eUln?oc=5)

**Lectura:** Alphabet ha publicado sus resultados financieros del segundo trimestre con unos ingresos de 112.110 millones de dólares que superaron las expectativas gracias al auge de la inteligencia artificial, además de convocar una macroemisión de bonos de hasta 25.000 millones de dólares. Estos acontecimientos mantienen una **dirección probable incierta** y una **baja probabilidad de impacto en el precio (0.07)**, ya que el entusiasmo por los sólidos resultados y la IA se equilibra con la cautela del mercado ante un posible incremento significativo de la deuda corporativa.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (7 argumentos)

- Crecimiento de ingresos sólido del 24.2%, muy por encima del sector (mediana de Communication Services: 8%).
- Margen neto muy alto del 54.8%, muy por encima del sector.
- ROIC del 29.9%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 61%, indicio de poder de fijación de precios.
- PEG de 0.06 sobre crecimiento de beneficio: el múltiplo no se ha adelantado al crecimiento.
- Momentum favorable (+26.2/100), RSI 39.3 (neutral).
- Solvencia 91.8/100: el balance aguanta un escenario adverso sin comprometer la tesis.

**🐻 Tesis bajista** (1 argumento)

- 4 discrepancia(s) entre proveedores de datos; confianza del 91%.

**⚖️ Síntesis:** Alphabet (GOOGL) presenta unos fundamentales extraordinarios, destacados por un crecimiento de ingresos del 24.2% muy superior al sector, un margen neto del 54.8%, un ROIC del 29.9% que supera su coste de capital del 9% y un atractivo PEG de 0.06. Por otro lado, la tesis bajista se limita técnicamente a cuatro discrepancias entre proveedores de datos (con una confianza del 91%), mientras que el contexto de noticias neutrales y de baja probabilidad de impacto no altera el dictamen financiero. En conclusión, la abrumadora solidez de sus métricas de creación de valor, margen bruto del 61% y un balance con una solvencia de 91.8/100 eclipsa las dudas metodológicas de los proveedores, situando al valor en una posición de alta calidad fundamental a pesar del neutral momento técnico (RSI 39.3 y momentum de 26.2/100).

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 12% en dos trimestres consecutivos.
- Que el margen neto baje del 32.9%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($332.46) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `COMPRA` — asignación objetivo **6.07%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **67.0**/100 × peso 0.65 + momentum normalizado **63.1**/100 × peso 0.35 = **65.6**/100
- Corte alcanzado: **COMPRA**

**Cómo se calculó el tamaño**

> `peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

| Factor | Valor |
| :--- | ---: |
| Escala de convicción | ×0.925 |
| Riesgo asumible por posición | 0.694% del patrimonio |
| Distancia al stop | 6.9% |
| Peso por presupuesto de riesgo | 10.11% |
| Factor de volatilidad | ×0.66 |
| Factor de confianza en datos | ×0.909 |
| Factor de banderas rojas | ×1.0 |
| Factor de sobreextensión técnica | ×1.0 |
| **Peso final** | **6.07%** |

_riesgo por posición 0.69% sobre un stop al 6.9%, escalado por volatilidad ×0.66_

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $340.67 | — | — |
| Stop-loss | $317.30 | −6.9% | 2.5× |
| Objetivo | $387.42 | +13.7% | 5.0× |

- **Ratio riesgo/recompensa:** 2.0 → exige acertar el **33.3%** de las veces solo para no perder dinero.
- **Horizonte:** 252 sesiones (~12.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 252 sesiones (~12 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** Como Director de Inversiones, emito una orden ejecutiva de **COMPRA** bajo el estilo de Calidad Compuesta para GOOGL con una asignación del 6.07% de la cartera, respaldada por una convicción fundamental moderada de 67.0/100 y un momentum técnico de 26.19/100, libre de vetos y banderas rojas. La operativa se establece a un precio de $340.67, protegiendo el capital con un stop loss en $317.3 y buscando un objetivo de $387.42, lo que ofrece una relación riesgo-recompensa favorable de 2.0. Este posicionamiento estratégico contempla un horizonte temporal de 252 sesiones de mercado para consolidar la tesis de inversión.

---

### NEM — Newmont Corporation

**Sector / Industria:** Basic Materials / Gold  
**Estilo:** `CALIDAD_COMPUESTA` (secundarias: CICLICA, DIVIDENDO)  
**Confianza en los datos:** 97% · Fuentes: yfinance, SEC EDGAR (Oficial), Finnhub

#### 1. Filtro fundamental — APROBADO

| Criterio | Valor | Umbral | Cumple |
| :--- | ---: | ---: | :---: |
| Margen neto | 33.4% | 5.0% | ✅ |
| Crecimiento de ingresos | 15.1% | 5.0% | ✅ |
| Deuda / Patrimonio | 0.16x | 3.00x | ✅ |

- ℹ️ 2 discrepancia(s) entre proveedores; confianza rebajada al 97%.

**Lectura:** Newmont Corporation (NEM) demuestra una salud financiera sobresaliente en el sector de Materiales Básicos, destacando por un sólido crecimiento de ingresos del 15.1% y una alta rentabilidad con un margen neto del 33.4% y un ROE del 25.9%. Además, presenta un riesgo de apalancamiento mínimo gracias a una relación Deuda/Patrimonio de 0.16x, lo que justifica firmemente su **APROBACIÓN** como *Gatekeeper*.

#### 2. Calidad y valoración

```
Calidad      ████████████████░░░░ 79/100
Valoración   ████████████░░░░░░░░ 62/100
Crecimiento  █████████████░░░░░░░ 66/100
Solvencia    ████████████████████ 99/100
────────────────────────────────────────
CONVICCIÓN   ███████████████░░░░░ 74/100
```

**Estilo `CALIDAD_COMPUESTA`** — Calidad 79.2/100 y solvencia 99.1/100 con crecimiento sostenido: negocio capaz de reinvertir por encima de su coste de capital.

_Convicción bruta 76.2 × cobertura de datos 1.0 × confianza en fuentes 0.969 − 0.0 por banderas rojas = **73.8**._

| Escuela | Métrica | Valor | Lectura |
| :--- | :--- | ---: | :--- |
| Piotroski | F-Score | 9/9 | FUERTE |
| Altman | Z (manufactureras) | 4.8 | zona SEGURA (seguro > 2.99, insolvencia < 1.81) |
| Graham | Nº de Graham | $77.83 | margen de seguridad -64.0% (2/5 criterios defensivos) |
| Greenblatt | EBIT/EV | 8.8% | atractivo |
| Buffett | ROIC | 21.6% | +12.6% sobre el coste de capital de referencia |
| Buffett | Margen bruto | 68.0% | indicio de foso competitivo |
| Buffett | Rendimiento FCF | 5.4% | dilución anual -3.37% |
| Lynch | PEG | 1.38 | EXIGENTE · categoría CICLICA (sobre crecimiento de beneficio) |
| Sloan | Devengos | -5.7% | beneficio respaldado por caja |

<details><summary>Desglose del F-Score de Piotroski</summary>

| Criterio | Cumple | Detalle |
| :--- | :---: | :--- |
| ROA positivo | ✅ | ROA=12.40% |
| Flujo de caja operativo positivo | ✅ | FCO=10,334,000,000 |
| ROA en mejora | ✅ | 5.94% → 12.40% |
| Flujo operativo > beneficio neto | ✅ | devengos bajos |
| Apalancamiento a largo plazo a la baja | ✅ | 13.40% → 8.95% |
| Ratio corriente en mejora | ✅ | 1.63 → 2.29 |
| Sin emisión neta de acciones | ✅ | dilución controlada |
| Margen bruto en mejora | ✅ | 38.23% → 53.21% |
| Rotación de activos en mejora | ✅ | 0.33x → 0.40x |

</details>

**Contexto sectorial (Basic Materials)** — el punto de comparación que convierte «P/E elevado» en una afirmación verificable:

| Métrica | Valor | Mediana del sector | Ratio | Lectura |
| :--- | ---: | ---: | ---: | :--- |
| P/E | 15.8x | 15.0x | 1.05 | en línea con el sector |
| Margen neto | 33.4% | 8% | 4.17 | muy por encima del sector |
| Deuda/Patrimonio | 0.2x | 0.5x | 0.32 | por debajo del sector |
| Crecimiento de ingresos | 15.1% | 6% | 2.52 | muy por encima del sector |

> Las normas sectoriales son medianas estáticas de largo plazo del mercado estadounidense, no la mediana viva del sector hoy. Sirven para ordenar y contextualizar, no para valorar.

_Cobertura de datos: 100% (OK)._

**Lectura:** Como Analista de Calidad y Valoración, esta es la síntesis de la tesis para **Newmont (NEM)**:

La compañía exhibe una **calidad excepcional (79.2/100)** respaldada por una solidez financiera inquebrugable (99.1/100, Altman segura), la máxima puntuación en salud operativa según Piotroski (9/9) y una sólida eficiencia en el capital con un ROIC del 21.6%, operando sin banderas rojas que comprometan su tesis. En cuanto al precio, una valoración moderada (61.8/100) combinada con un PEG razonable de 1.38 sugiere que el mercado no está sobreexigiendo el valor, ofreciendo una atractiva oportunidad para capturar exposición al sector de materiales básicos con un perfil defensivo y de dividendo bien respaldado.

#### 3. Análisis técnico

**Momentum:** `ALCISTA` (puntuación +27.3/100) · **Tendencia:** MIXTA · **RSI:** 83.91 (SOBRECOMPRA_EXTREMA)

| Componente | Aporte a la puntuación |
| :--- | ---: |
| Tendencia | +6.00 |
| Macd | +16.56 |
| Rsi | -13.56 |
| Bollinger | +8.15 |
| Momentum precio | +10.17 |
| **Total** | **+27.32** |

- Precio frente a medias: SMA50 +26.7% · SMA200 +20.6%
- Posición en el rango de 52 semanas: 90%
- ATR: $4.89 (3.8% del precio) · Volatilidad anualizada: 50.3%
- Momentum relativo a 12 meses frente al índice: +15.2%
- ⚠️ **Valor técnicamente sobreextendido:** la entrada en este nivel asume riesgo de reversión. Afecta al tamaño de la posición, no a la tesis.

**Señales:**

- Estructura mixta: precio 127.64, SMA50 100.76, SMA200 105.82
- MACD alcista (histograma +2.025, 0.41 ATR)
- RSI en sobrecompra EXTREMA (83.9 ≥ 80): riesgo elevado de reversión a corto plazo
- Precio en el 91% del canal de Bollinger
- Momentum 12m (excl. último mes) +36.6% frente al +21.3% de SPY: exceso +15.2%

**Lectura:** NEM cotiza en $127.64, ubicándose de manera sólida por encima de sus medias móviles de 50 y 200 periodos con un histograma MACD positivo (+2.025), lo que refleja una estructura de tendencia mixta pero respaldada por un momentum alcista (+27.3/100). No obstante, el RSI se encuentra en un nivel de sobrecompra extrema (83.9) y el activo opera en el 90% de su rango de 52 semanas, advirtiendo sobre una condición técnica muy estirada a corto plazo.

#### 4. Analista de noticias — **capa asesora, no altera el dictamen**

**Probabilidad de impacto:** `MEDIA` (0.32) · **Dirección probable:** `ALCISTA`

Cobertura: 13 nota(s) en 30 días · fuentes con respuesta: sec_8k, google_news_rss · sin respuesta: tavily

**Catalizadores principales:**

- `2026-08-20` · **CORPORATIVO** · NEUTRA · p=0.23 · _Business Wire_ (1 fuente/s) — [Newmont Appoints Peter Beaven to Board of Directors - Business Wire](https://news.google.com/rss/articles/CBMirAFBVV95cUxPX3ljU3VnbEVzU2ZNWHlWYkpzTkNWZWZnWlJxY2xwaDBzLVdCYTBCTEowa01oNlgxLWJnTUJrRU9QU0lsWFVaLUdOWXFHcDVpZmlQT0l3M0ozNmMzXzhIZTYyUnNVRzRpYWVmdmlEUUlUeEE2Ml9Hd0RGdmJtZ0lOWTlNWDlPTmczTGJwN2dZTmRDWDR2bG5RY3NsZTJtMFNqM0ZmdTZLV0kwc0NJ?oc=5)
- `2026-08-18` · **OTROS** · NEUTRA · p=0.04 · _Yahoo Finance_ (1 fuente/s) — [StrikePoint Announces Agreement to Purchase the Northumberland Project, a Gold Deposit in Nevada’s Walker Lane, from Newmont Corporation - Yahoo Finance](https://news.google.com/rss/articles/CBMiwwFBVV95cUxNNGZId1l6V2VJM0JxbkxrTjFxLVIyLTJqNHR0Q25sM2dWT0tTX2d6UlVPdlVDajBLemtSdUQzcVl0cGhDOTU0N0RRYkRWZVhOQkczQkxPcjFENkdSRFl5RkFHaTJsZmZPdDMzd0VoQmhSSWU2SWJCaE5qbXd0WW5ZNzlkU2IzOUNXMGZpcWU3MktlUlozdV9Ma2Fnb254Qnd2UVVTWk51WDVEYmRZWlJwaXVGaWEwQS1zSERxZWdyQUtXbTA?oc=5)
- `2026-07-23` · **RESULTADOS** · NEUTRA · p=0.03 · _SEC EDGAR (8-K)_ (1 fuente/s) — [Newmont Corporation presenta el formulario 8-K (Ítem 2.02: Results of Operations and Financial Condition)](https://www.sec.gov/Archives/edgar/data/1164727/000116472726000034/nem-20260723.htm)

**Lectura:** Newmont Corporation ha reforzado su estructura corporativa con la incorporación de Peter Beaven a su Consejo de Administración y ha reportado sus recientes resultados financieros mediante el formulario 8-K, en un contexto de transacciones estratégicas en Nevada. Estos movimientos corporativos y operativos optimizan la gobernanza y la confianza del mercado, actúan como catalizadores de **dirección ALCISTA** y presentan una **probabilidad de impacto en el precio MEDIA (0.32)**.

> **Por qué las noticias no mueven el dictamen.** Dos de las tres fuentes son buscadores «de hoy» y no hay forma asequible de reconstruir qué era visible en una fecha pasada. Conectarlas a la decisión invalidaría el backtest hasta disponer de un almacén de noticias point-in-time. Un litigio o una investigación regulatoria relevante debe activar una **revisión manual**, no un recálculo automático del peso.

#### 5. Debate y mitigación de sesgos

**🐂 Tesis alcista** (9 argumentos)

- Crecimiento de ingresos sólido del 15.1%, muy por encima del sector (mediana de Basic Materials: 6%).
- Margen neto muy alto del 33.4%, muy por encima del sector.
- ROIC del 21.6%, por encima del coste de capital de referencia (9%): el negocio crea valor con cada euro reinvertido.
- Margen bruto del 68%, indicio de poder de fijación de precios.
- F-Score de Piotroski 9/9: la calidad contable mejora en rentabilidad, apalancamiento y eficiencia a la vez.
- Rendimiento del flujo de caja libre del 5.4%.
- Momentum favorable (+27.3/100), RSI 83.9 (sobrecompra extrema).
- Solvencia 99.1/100: el balance aguanta un escenario adverso sin comprometer la tesis.
- Flujo de noticias con probabilidad de impacto MEDIA (0.32) y sesgo ALCISTA sobre 13 nota(s); principal catalizador: "Newmont Appoints Peter Beaven to Board of Directors - Business Wire" (capa asesora: no altera el dictamen).

**🐻 Tesis bajista** (2 argumentos)

- RSI en 83.9 (sobrecompra extrema): la entrada en este nivel asume riesgo de reversión a corto plazo.
- 2 discrepancia(s) entre proveedores de datos; confianza del 97%.

**⚖️ Síntesis:** Newmont (NEM) presenta una sólida tesis alcista respaldada por un crecimiento de ingresos del 15.1% frente al 6% del sector, un margen neto del 33.4%, un margen bruto del 68% y un ROIC del 21.6% que supera el coste de capital del 9%, además de un F-Score de Piotroski perfecto de 9/9 y una solvencia de 99.1/100. En contraposición, los riesgos bajistas se centran en una sobrecompra extrema con un RSI de 83.9 que advierte un riesgo de reversión a corto plazo, sumado a 2 discrepancias entre proveedores de datos que sitúan la confianza en el 97%. Ponderando ambas posturas, la excelente creación de valor y solidez financiera de la compañía contrastan con la prudencia exigida por su actual sobrecompra técnica y las discrepancias de datos, en un contexto donde el flujo de noticias alcista de impacto medio no altera el dictamen fundamental.

**Condiciones que invalidarían la tesis** — sin ellas, esto sería una opinión, no una tesis:

- Que el crecimiento de ingresos caiga por debajo del 8% en dos trimestres consecutivos.
- Que el margen neto baje del 20.0%.
- Que el ROIC caiga por debajo del coste de capital de referencia (9%).
- Que aparezca deterioro en el F-Score de Piotroski o en el ratio de devengos, señal de que el descuento estaba justificado.
- Que el precio pierda la media de 200 sesiones ($105.82) con volumen creciente.

#### 6. Dictamen del Fund Manager

### 🎯 `COMPRA` — asignación objetivo **2.89%** de la cartera

**Cómo se llegó al dictamen**

- Convicción fundamental **73.8**/100 × peso 0.65 + momentum normalizado **63.7**/100 × peso 0.35 = **70.3**/100
- Corte alcanzado: **COMPRA**

**Cómo se calculó el tamaño**

> `peso = riesgo asumible / distancia al stop × factor de volatilidad × descuentos`

| Factor | Valor |
| :--- | ---: |
| Escala de convicción | ×1.095 |
| Riesgo asumible por posición | 0.821% del patrimonio |
| Distancia al stop | 9.6% |
| Peso por presupuesto de riesgo | 8.57% |
| Factor de volatilidad | ×0.497 |
| Factor de confianza en datos | ×0.969 |
| Factor de banderas rojas | ×1.0 |
| Factor de sobreextensión técnica | ×0.7 |
| **Peso final** | **2.89%** |

_riesgo por posición 0.82% sobre un stop al 9.6%, escalado por volatilidad ×0.50_

**Gestión del riesgo**

| Nivel | Precio | Distancia | Múltiplo ATR |
| :--- | ---: | ---: | ---: |
| Entrada (referencia) | $127.64 | — | — |
| Stop-loss | $115.41 | −9.6% | 2.5× |
| Objetivo | $152.09 | +19.2% | 5.0× |

- **Ratio riesgo/recompensa:** 2.0 → exige acertar el **33.3%** de las veces solo para no perder dinero.
- **Horizonte:** 252 sesiones (~12.0 meses). A su ATR actual, el precio necesitaría al menos 21 sesiones de avance direccional puro para alcanzar el objetivo.

> Stop y objetivo se evalúan sobre 252 sesiones (~12 meses). Fuera de ese plazo la posición se revisa, no se mantiene por inercia.

**Orden ejecutiva:** **ORDEN EJECUTIVA DE INVERSIÓN: NEM**

Tras una evaluación exhaustiva sin vetos ni banderas rojas, se emite un dictamen de **COMPRA** bajo el estilo de calidad compuesta, respaldado por una sólida convicción fundamental de 73.8/100 y un momentum de 27.32/100. Se autoriza una asignación del 2.89% de la cartera al precio actual de $127.64, estableciendo un *stop-loss* en $115.41 y un objetivo de precio en $152.09 para mantener una relación riesgo-recompensa de 2.0. Esta posición táctica está diseñada para desarrollarse en un horizonte temporal de 252 sesiones de mercado.

---

## 5. Calidad de los datos

Ningún dictamen es mejor que los datos que lo sostienen. Esta sección declara qué se sabe y qué no de cada valor, porque la ausencia de un dato se propaga a la convicción y, por esa vía, al tamaño de la posición.

| Ticker | Confianza | Fuentes | Cobertura fundamental | Campos ausentes | Discrepancias |
| :--- | ---: | :--- | ---: | :--- | ---: |
| **DOCN** | 89% | yfinance, SEC EDGAR (Oficial), Finnhub | 96% | — | 4 |
| **NRGV** | 85% | yfinance, SEC EDGAR (Oficial), Finnhub | 77% | — | 3 |
| **BE** | 67% | yfinance, SEC EDGAR (Oficial), Finnhub | 92% | — | 5 |
| **GOOGL** | 91% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 4 |
| **NEM** | 97% | yfinance, SEC EDGAR (Oficial), Finnhub | 100% | — | 2 |

**Discrepancias entre proveedores:**

- `DOCN` — revenue_growth: dispersión del 46% entre yfinance (0.286) vs Finnhub (0.2314) vs SEC EDGAR (derivado) (0.1548)
- `DOCN` — net_margin: dispersión del 19% entre yfinance (0.2326) vs Finnhub (0.2327) vs SEC EDGAR (derivado) (0.2876)
- `DOCN` — roe: dispersión del 91% entre yfinance (0.6227) vs Finnhub (0.0563)
- `DOCN` — pe_ratio: dispersión del 20% entre yfinance (52.94) vs Finnhub (66.12)
- `NRGV` — revenue_growth: dispersión del 69% entre yfinance (1.041) vs SEC EDGAR (derivado) (3.409)
- `NRGV` — debt_to_equity: dispersión del 94% entre yfinance (7.513) vs SEC EDGAR (derivado) (0.4227)
- `NRGV` — roe: dispersión del 80% entre yfinance (-1.786) vs Finnhub (-2.367) vs SEC EDGAR (derivado) (-0.463)
- `BE` — revenue_growth: dispersión del 88% entre yfinance (1.655) vs Finnhub (0.2057) vs SEC EDGAR (derivado) (0.3887)
- `BE` — net_margin: dispersión del 152% entre yfinance (0.07868) vs Finnhub (0.0025) vs SEC EDGAR (derivado) (-0.1509)
- `BE` — debt_to_equity: dispersión del 50% entre yfinance (1.716) vs SEC EDGAR (derivado) (3.406)
- `BE` — roe: dispersión del 157% entre yfinance (0.2221) vs Finnhub (0.0082) vs SEC EDGAR (derivado) (-0.3931)
- `BE` — pe_ratio: dispersión del 98% entre yfinance (270) vs Finnhub (1.159e+04)
- `GOOGL` — revenue_growth: dispersión del 43% entre yfinance (0.242) vs Finnhub (0.1715) vs SEC EDGAR (derivado) (0.1387)
- `GOOGL` — net_margin: dispersión del 31% entre yfinance (0.5477) vs Finnhub (0.5477) vs SEC EDGAR (derivado) (0.3776)
- `GOOGL` — debt_to_equity: dispersión del 41% entre yfinance (0.1886) vs SEC EDGAR (derivado) (0.1121)
- `GOOGL` — roe: dispersión del 37% entre yfinance (0.4868) vs Finnhub (0.5084) vs SEC EDGAR (derivado) (0.3183)
- `NEM` — revenue_growth: dispersión del 32% entre yfinance (0.151) vs Finnhub (0.1454) vs SEC EDGAR (derivado) (0.2134)
- `NEM` — roe: dispersión del 19% entre yfinance (0.2591) vs Finnhub (0.2505) vs SEC EDGAR (derivado) (0.2092)

<details><summary>Procedencia de cada magnitud reconciliada</summary>

- `DOCN`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `NRGV`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `BE`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `GOOGL`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance
- `NEM`: revenue_growth ← yfinance, net_margin ← yfinance, debt_to_equity ← yfinance, roe ← yfinance, pe_ratio ← yfinance

</details>

---

## 6. Limitaciones y track record

**El sistema no ha batido históricamente a comprar y mantener el índice.** El backtest point-in-time sobre 2015-2025 (`output/backtest_report.md`) documenta un CAGR del 2.11% frente al 13.51% del SPY, un Sharpe de 0.35 frente a 0.80 y un alfa anualizado de −0.41% (t = −0.24). Frente a carteras aleatorias con el mismo perfil de exposición, la estrategia queda en el percentil 1.9.

Más grave que el rendimiento: **en aquella versión el rating no ordenaba el rendimiento futuro en la dirección que afirmaba** — los valores calificados VENTA FUERTE rindieron de media un 35.06% a doce meses frente al 21.02% de los COMPRA FUERTE. La lectura prudente es que el rating no separaba ganadores de perdedores; afirmar que la señal estaba *invertida* exigiría composiciones históricas del índice para descartar el sesgo de supervivencia.

Las mejoras incorporadas en esta versión —convicción fundamental en la decisión, dimensionamiento por riesgo, corrección del clasificador de momentum— **no han sido revalidadas todavía en el backtest**. Hasta que se ejecute de nuevo `backtest_cli.py --regime pit`, el track record vigente es el anterior y las cifras de arriba son las que aplican.

**Limitaciones metodológicas que siguen vigentes:**

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
