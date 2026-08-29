# Backtest del sistema multi-agente de recomendaciones de compra

_Generado el 2026-08-21 12:00._

> **Régimen de datos:** POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio

## 1. Veredicto ejecutivo

**NO.** Y el motivo es más grave que el rendimiento: **el rating no ordena el futuro en la dirección que afirma.** Los valores calificados VENTA FUERTE rindieron de media 34.24% a 12 meses, frente al 18.76% de los COMPRA FUERTE.

  Matiz obligado antes de concluir que la señal está *invertida*: el sesgo de supervivencia golpea de forma desigual a cada categoría. VENTA FUERTE recoge sobre todo empresas con fundamentales deteriorados, y de esas solo están en el universo las que sobrevivieron hasta hoy — precisamente las que se recuperaron. La lectura defendible es más prudente: **el rating no separa ganadores de perdedores**, y el signo aparente de la inversión no puede afirmarse sin composiciones históricas del índice.

- Régimen de datos del resultado principal: POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio
- CAGR estrategia 3.95% vs SPY 13.51% (exceso -9.56%); Sharpe 0.68 vs 0.80.
- Máximo drawdown -13.80%; 563 operaciones; tasa de acierto 44.58% frente al 36.36% de equilibrio que exige el R:R 1.75 del sistema.
- Alfa anualizado 0.91% (t=0.67); percentil frente a señales aleatorias: 7.4.
- Rendimiento medio a 12 meses por rating: VENTA FUERTE 34.24% · COMPRA 27.40% · SIN OPINION 25.23% · MANTENER 19.06% · COMPRA FUERTE 18.76% · VENTA 17.89%. El mejor es **VENTA FUERTE**.

**Las tres limitaciones más serias, antes de cualquier lectura positiva:**
1. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 30.4%, así que un 70% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
2. **La exposición es una CONSECUENCIA del presupuesto de riesgo, no un objetivo.** El motor histórico dimensiona ya con `src/portfolio/construccion.py` —la misma capa que corre en vivo: límites por sector, penalización por correlación y presupuesto de riesgo agregado—, así que la cartera simulada es la que el sistema recomendaría hoy. Pero el tamaño de cada posición sale de arriesgar un 0.75% del patrimonio contra la distancia al stop, y con pocas señales simultáneas eso deja la exposición bruta en el 30%. **El sistema no define qué hacer con el resto**, y esa es una decisión de diseño que falta: una estrategia estructuralmente invertida a un tercio no puede compararse contra un índice invertido al 100% sin decirlo. Las métricas ajustadas por riesgo (Sharpe, Sortino) son la comparación honesta; el CAGR absoluto no lo es.
3. **Divergencia de definición fundamental.** Producción lee métricas TTM de `yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, porque el TTM histórico de yfinance no es recuperable retroactivamente. El gatekeeper se evalúa por tanto con una ventana contable distinta a la de producción: los ratings del backtest son fieles a la *lógica* del sistema, no necesariamente idénticos a los que habría emitido en directo.


## 2. Estrategia frente a los benchmarks

| Cartera | CAGR | Retorno total | Volatilidad | Sharpe | Sortino | Calmar | Máx. drawdown | Capital final |
|---|---|---|---|---|---|---|---|---|
| Estrategia | 3.95% | 53.04% | 5.96% | 0.68 | 0.86 | 0.29 | -13.80% | $153,037 |
| SPY comprar y mantener | 13.51% | 302.73% | 17.79% | 0.80 | 0.98 | 0.40 | -33.72% | $402,727 |
| Universo equiponderado | 20.30% | 662.35% | 18.93% | 1.07 | 1.31 | 0.61 | -33.17% | $762,350 |


**Contraste contra selección aleatoria (Monte Carlo, hipótesis nula):**

Las carteras aleatorias replican el perfil observado de la estrategia — 5 posiciones simultáneas, 33 días de tenencia media y 30.38% de exposición bruta — pero eligen los valores al azar. Aísla la habilidad de selección de la mera exposición al mercado.

- CAGR medio de las carteras aleatorias: 5.42% (p05 3.72%, p95 6.96%).
- La estrategia queda en el percentil **7.4** de esa distribución. p-valor unilateral: **0.9260**.


## 3. Métricas completas de la estrategia

| Métrica | Valor |
|---|---|
| Periodo | 2015-01-02 → 2025-12-30 |
| Años | 11.0 |
| Capital inicial | $100,000 |
| Capital final | $153,037 |
| Retorno total | 53.04% |
| CAGR | 3.95% |
| Volatilidad anualizada | 5.96% |
| Sharpe | 0.68 |
| Sortino | 0.86 |
| Calmar | 0.29 |
| Máximo drawdown | -13.80% |
| Duración máx. del drawdown (días) | 1392 |
| VaR 95% diario | -0.61% |
| CVaR 95% diario | -0.93% |
| Mejor año | 13.89% |
| Peor año | -10.78% |
| Beta vs SPY | 0.22 |
| Alfa anualizado vs SPY | 0.91% |
| t-stat del alfa | 0.67 |
| R² vs SPY | 0.43 |
| Exposición bruta media | 30.38% |
| Posiciones simultáneas medias | 4.7 |
| Rotación anualizada | 6.73 |
| Costes totales pagados | $9,514 |
| —— Operaciones —— |  |
| Número de operaciones | 563 |
| Tasa de acierto | 44.58% |
| Tasa de equilibrio exigida (R:R 1.75) | 36.36% |
| Profit factor | 1.38 |
| Ganancia media | 9.98% |
| Pérdida media | -5.81% |
| Esperanza por operación | 1.23% |
| Días medios en cartera | 33.4 |
| Mejor operación | 39.76% |
| Peor operación | -18.10% |


**Intervalo de confianza del CAGR (bootstrap de retornos diarios, 2000 muestras):** p05 0.96% · mediana 3.91% · p95 7.16%. Probabilidad de CAGR negativo: 1.20%.


## 4. Curva de capital y drawdown

![Curva de capital](backtest_equity_pit.png)


![Monte Carlo](backtest_montecarlo_pit.png)


**Rentabilidad por año natural:**

| Año | Estrategia | SPY |
|---|---|---|
| 2015 | 2.53% | 1.29% |
| 2016 | 3.58% | 12.00% |
| 2017 | 13.89% | 21.71% |
| 2018 | -2.76% | -4.57% |
| 2019 | 11.79% | 31.22% |
| 2020 | 2.67% | 18.33% |
| 2021 | 12.34% | 28.73% |
| 2022 | -10.78% | -18.18% |
| 2023 | 7.89% | 26.18% |
| 2024 | 1.54% | 24.89% |
| 2025 | 3.24% | 18.60% |


## 5. Atribución


### Por rating de entrada

| rating | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| COMPRA | 478 | 0.4351 | 0.0097 | 37549.1258 | 32.4749 |
| COMPRA FUERTE | 85 | 0.5059 | 0.0267 | 15487.8736 | 38.6000 |


### Por estilo de inversion

| estilo | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| CALIDAD_COMPUESTA | 382 | 0.4450 | 0.0141 | 41324.9076 | 37.7199 |
| VALOR | 89 | 0.4831 | 0.0185 | 10077.8611 | 31.7978 |
| CRECIMIENTO | 88 | 0.4091 | -0.0011 | 1901.9583 | 16.9886 |
| MIXTA | 4 | 0.5000 | -0.0049 | -267.7275 | 17.5000 |


### Por sector

| sector | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| Technology | 362 | 0.4530 | 0.0147 | 35761.8755 | 32.9006 |
| Communication Services | 50 | 0.4600 | 0.0240 | 9801.0353 | 27.5800 |
| Financial Services | 50 | 0.5200 | 0.0098 | 4272.5908 | 36.5400 |
| Consumer Defensive | 26 | 0.4231 | 0.0051 | 2366.5944 | 28.0000 |
| Industrials | 6 | 0.5000 | 0.0364 | 1986.1820 | 35.6667 |
| Healthcare | 56 | 0.3929 | 0.0033 | 1112.8796 | 43.4107 |
| Consumer Cyclical | 13 | 0.1538 | -0.0481 | -2264.1582 | 24.2308 |


### Por motivo de salida

| exit_reason | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| take_profit | 226 | 1.0000 | 0.1070 | 185853.4632 | 43.0088 |
| fin_backtest | 6 | 0.6667 | 0.0165 | 1534.8611 | 33.6667 |
| downgrade_VENTA | 8 | 0.7500 | 0.0301 | 1275.1913 | 53.1250 |
| downgrade_MANTENER | 41 | 0.3659 | -0.0017 | -201.1740 | 49.1463 |
| stop_loss | 282 | 0.0000 | -0.0621 | -135425.3421 | 22.8440 |


### Por año de salida

| year | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| 2015 | 27 | 0.2963 | 0.0103 | 2540.2001 | 29.1852 |
| 2016 | 36 | 0.4444 | 0.0115 | 3336.1404 | 38.4444 |
| 2017 | 55 | 0.6364 | 0.0320 | 14611.6621 | 29.4182 |
| 2018 | 60 | 0.3167 | -0.0169 | -2948.1682 | 31.9833 |
| 2019 | 69 | 0.5072 | 0.0359 | 12029.8484 | 33.5942 |
| 2020 | 39 | 0.6154 | 0.0420 | 4165.1911 | 39.3590 |
| 2021 | 49 | 0.5918 | 0.0339 | 17032.8922 | 43.0408 |
| 2022 | 56 | 0.1964 | -0.0455 | -15999.8691 | 27.7143 |
| 2023 | 56 | 0.4643 | 0.0246 | 10365.6636 | 39.3571 |
| 2024 | 66 | 0.4091 | 0.0083 | 3248.3430 | 28.8788 |
| 2025 | 50 | 0.4200 | 0.0066 | 4655.0960 | 29.4200 |


### Event study: rendimiento futuro por rating

Independiente del gestor de cartera: mide si el rating por sí solo anticipa el movimiento posterior del precio. Es la prueba más limpia de poder predictivo.

| rating | n | fwd_1m_media | fwd_1m_mediana | fwd_1m_pct_positivo | fwd_1m_tstat | fwd_3m_media | fwd_3m_mediana | fwd_3m_pct_positivo | fwd_3m_tstat | fwd_6m_media | fwd_6m_mediana | fwd_6m_pct_positivo | fwd_6m_tstat | fwd_12m_media | fwd_12m_mediana | fwd_12m_pct_positivo | fwd_12m_tstat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMPRA | 765 | 0.0180 | 0.0170 | 0.5895 | 5.8768 | 0.0565 | 0.0419 | 0.6340 | 10.3349 | 0.1192 | 0.0996 | 0.7124 | 13.6191 | 0.2740 | 0.2018 | 0.7712 | 16.1119 |
| COMPRA FUERTE | 171 | 0.0094 | 0.0116 | 0.5731 | 1.8008 | 0.0407 | 0.0389 | 0.6784 | 4.0870 | 0.0768 | 0.0656 | 0.6316 | 4.9086 | 0.1876 | 0.1435 | 0.7135 | 7.6557 |
| MANTENER | 929 | 0.0161 | 0.0135 | 0.5845 | 5.7010 | 0.0467 | 0.0423 | 0.6340 | 9.4788 | 0.0940 | 0.0716 | 0.6760 | 12.3840 | 0.1906 | 0.1627 | 0.7244 | 15.9263 |
| SIN OPINION | 285 | 0.0159 | 0.0069 | 0.5649 | 2.8445 | 0.0493 | 0.0288 | 0.6035 | 4.5223 | 0.1095 | 0.0784 | 0.6842 | 5.8564 | 0.2523 | 0.1262 | 0.7579 | 6.3777 |
| VENTA | 3216 | 0.0142 | 0.0126 | 0.5784 | 10.6314 | 0.0434 | 0.0361 | 0.6231 | 18.4903 | 0.0887 | 0.0670 | 0.6816 | 25.5280 | 0.1789 | 0.1356 | 0.7397 | 35.2350 |
| VENTA FUERTE | 211 | 0.0250 | 0.0133 | 0.5640 | 3.1512 | 0.0752 | 0.0426 | 0.6303 | 5.1932 | 0.1578 | 0.1423 | 0.6635 | 7.2758 | 0.3424 | 0.4349 | 0.7062 | 10.8941 |


## 6. Robustez por subperiodo

| Subperiodo | Retorno estrategia | Retorno SPY | Sharpe | Máx. drawdown |
|---|---|---|---|---|
| Pre-COVID 2015-2019 | 0.3148 | 0.7289 | 1.0506 | -0.0896 |
| Crash COVID 2020-02→2020-04 | -0.0311 | -0.0985 | -1.2752 | -0.0649 |
| Recuperación 2020-2021 | 0.1703 | 0.7236 | 1.7105 | -0.0430 |
| Bajista 2022 | -0.1162 | -0.1865 | -1.4416 | -0.1338 |
| Post-2023 | 0.1337 | 0.8767 | 0.7678 | -0.0623 |


## 7. Sensibilidad a costes de transacción

| Nivel de coste | CAGR | Sharpe | Máx. drawdown | Capital final |
|---|---|---|---|---|
| 0 bps ida y vuelta | 0.0463 | 0.7924 | -0.1316 | 164511.2837 |
| 5 bps ida y vuelta | 0.0429 | 0.7366 | -0.1348 | 158670.1758 |
| 10 bps ida y vuelta | 0.0395 | 0.6808 | -0.1380 | 153036.9995 |
| 25 bps ida y vuelta | 0.0293 | 0.5137 | -0.1476 | 137312.1627 |


## 8. Limitaciones y sesgos residuales

Esta sección no se suaviza. Cada punto es una razón concreta por la que el resultado de arriba podría no repetirse fuera de muestra.

1. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 30.4%, así que un 70% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
2. **La exposición es una CONSECUENCIA del presupuesto de riesgo, no un objetivo.** El motor histórico dimensiona ya con `src/portfolio/construccion.py` —la misma capa que corre en vivo: límites por sector, penalización por correlación y presupuesto de riesgo agregado—, así que la cartera simulada es la que el sistema recomendaría hoy. Pero el tamaño de cada posición sale de arriesgar un 0.75% del patrimonio contra la distancia al stop, y con pocas señales simultáneas eso deja la exposición bruta en el 30%. **El sistema no define qué hacer con el resto**, y esa es una decisión de diseño que falta: una estrategia estructuralmente invertida a un tercio no puede compararse contra un índice invertido al 100% sin decirlo. Las métricas ajustadas por riesgo (Sharpe, Sortino) son la comparación honesta; el CAGR absoluto no lo es.
3. **Divergencia de definición fundamental.** Producción lee métricas TTM de `yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, porque el TTM histórico de yfinance no es recuperable retroactivamente. El gatekeeper se evalúa por tanto con una ventana contable distinta a la de producción: los ratings del backtest son fieles a la *lógica* del sistema, no necesariamente idénticos a los que habría emitido en directo.
4. **Normas sectoriales estáticas.** El contexto de valoración compara cada múltiplo contra una mediana de largo plazo del mercado estadounidense (`SECTOR_NORMAS` en `src/config.py`), no contra la mediana viva del sector en la fecha simulada. En un backtest de once años eso introduce un anacronismo: el P/E mediano del software en 2015 no era el de 2025. Las etiquetas de estilo ordenan y contextualizan, pero no deben leerse como una valoración relativa exacta.
5. **Coste de capital constante.** El ROIC se compara contra un WACC de referencia único (`WACC_REFERENCIA`) en lugar de estimarlo por empresa y por fecha. Es una decisión consciente —la dispersión de un WACC estimado con beta y estructura de capital superaría la señal que aporta— pero implica que «crea valor» significa «supera un umbral fijo», no «supera su propio coste de capital».
6. **Sesgo de supervivencia.** El universo son 50 valores seleccionados hoy por su relevancia actual. Las empresas que quebraron o fueron excluidas nunca entran en la muestra, lo que infla el resultado en una magnitud no cuantificada aquí (la literatura sitúa el efecto entre 1 y 4 puntos de CAGR según periodo y universo).
7. **Deuda/Capital ausente se trata como 0.0.** Se replica el comportamiento de producción (`info.get("debtToEquity", 0.0)`), lo que hace que el filtro de apalancamiento se salte silenciosamente cuando el dato falta en EDGAR, en lugar de rechazar el valor.
8. **Finnhub ausente en el backtest.** No hay histórico point-in-time gratuito, así que el `confidence_score` de la reconciliación difiere del de producción. Verificado en la Fase 1 que no altera ninguna decisión (solo añade texto), pero es una divergencia real.
9. **Analista de Noticias excluido del backtest.** El grafo de producción ejecuta un nodo `news_analysis` que este replay NO recorre. Dos de sus tres fuentes (Google News RSS y Tavily) son buscadores "de hoy": no existe forma asequible de recuperar qué estaba publicado y visible en una fecha pasada, y sus corpus indexados hoy omiten lo que se borró y fechan por republicación, no por el hecho. Solo el 8-K con Ítem 2.02 tiene `filed` exacto y sería reconstruible. Por eso las noticias son hoy una CAPA ASESORA: aparecen en el informe diario y alimentan el debate, pero no tocan `rating` ni `position_size_pct`, de modo que su ausencia aquí no altera ni una sola señal. La contrapartida es que el valor predictivo de esa capa está SIN MEDIR: no hay ninguna evidencia en este informe de que las noticias aporten nada.
10. **Sin datos intradía.** Cuando stop y objetivo se tocan en la misma sesión se asume que saltó el stop. Es conservador, pero desconoce el orden real y sesga el resultado a la baja en una cuantía desconocida.
11. **Costes estimados, no reales.** Comisión y slippage son parámetros fijos en puntos básicos. No modelan impacto de mercado, y para tamaños grandes de cartera el deslizamiento real crecería con el volumen.
12. **Cobertura incompleta de señales.** Descartes por falta de datos: {'sin_fundamentales': 979}. Los tickers sin fundamentales publicados en una fecha simplemente no generan señal, lo que reduce el universo efectivo en los primeros años del estudio.
13. **Contrastes múltiples.** Se han evaluado varios regímenes, frecuencias y niveles de coste sobre el mismo periodo histórico. El p-valor mostrado no está corregido por multiplicidad: interprétese como orientativo, no como una prueba formal.

## 9. Próximos pasos para reforzar la validez

1. PRIORIDAD 1 — investigar la ordenación del rating. Antes de tocar stops, sizing o costes, comprobar si el event study mantiene el orden invertido (VENTA FUERTE rindiendo más que COMPRA FUERTE) en otros universos y periodos. Si se confirma, el problema está en la señal y ningún ajuste de gestión de cartera lo arreglará.
2. Contrastar la hipótesis más probable de esa inversión: el gatekeeper exige crecimiento de ingresos ≥5% y margen neto ≥3%, lo que descarta sistemáticamente los valores de estilo *value* y las recuperaciones cíclicas, que son justamente los que más rindieron en varios tramos del periodo. Es un sesgo de estilo, no un fallo de implementación.
3. Medir por separado el efecto del stop de 2·ATR. Con más de la mitad de las salidas disparadas por stop y una tenencia media inferior a 20 sesiones, el sistema puede estar cortando posiciones ganadoras antes de que maduren. Ejecutar una variante sin stop y otra con stop por tiempo para aislarlo.
4. Contratar o reconstruir las composiciones históricas del índice (CRSP, Norgate, Sharadar) para eliminar el sesgo de supervivencia, que hoy es el sesgo residual dominante.
5. Sustituir los fundamentales anuales por TTM point-in-time encadenando los cuatro trimestres XBRL disponibles en cada fecha, para acercar el backtest a la definición exacta que usa producción.
6. Validación walk-forward: fijar los umbrales del gatekeeper con datos hasta 2019 y evaluar 2020-2025 como out-of-sample estricto, sin volver a mirar el periodo de test.
7. Añadir datos intradía (o al menos barras horarias) para resolver correctamente el orden entre stop y objetivo dentro de la misma sesión.
8. Definir una política explícita para el capital no invertido. La exposición bruta que produce el presupuesto de riesgo es estructuralmente baja, y hoy el remanente se queda en efectivo al 0%. Las tres opciones razonables —remunerarlo a letras, invertirlo en el índice como posición residual, o subir el riesgo por posición— tienen implicaciones muy distintas y ninguna está tomada. Mientras no se decida, el CAGR absoluto compara una cartera a un tercio de exposición contra un índice al 100%.
9. Sustituir `SECTOR_NORMAS` por la mediana calculada sobre un conjunto de comparables en cada fecha. Es lo que convierte el contexto sectorial de una referencia estática en una valoración relativa point-in-time, y elimina el anacronismo declarado en las limitaciones.
10. Revalidar el sistema completo tras la incorporación del Analista de Calidad a la decisión. El track record publicado corresponde a la versión anterior, en la que el rating salía de momentum y RSI únicamente; las cifras de rendimiento no son transferibles a la versión actual hasta ejecutar de nuevo el régimen `pit`.
11. Reconstruir el riesgo legal y regulatorio de forma point-in-time desde EDGAR (8-K Ítem 8.01 y el apartado de Procedimientos Legales del 10-K). Es la única vía para que un litigio material entre en la decisión sin romper el backtest: a diferencia de la prensa, esas presentaciones tienen fecha `filed` exacta.
12. Construir un `NewsStore` point-in-time antes de dejar que las noticias entren en la decisión. El único camino barato es el histórico completo de 8-K/10-Q de EDGAR filtrado por `filed <= t` (mismo patrón que `FundamentalStore`), que cubre resultados y hechos relevantes pero no prensa general; el resto exigiría un proveedor de archivo de noticias con marca temporal (RavenPack, Dow Jones DNA). Hasta entonces, subir el Analista de Noticias de capa asesora a variable de decisión dejaría el sistema sin backtest válido.
13. Medir la capa de noticias por separado con un event study sobre los 8-K con Ítem 2.02, que sí son reconstruibles point-in-time: comparar el rendimiento a 1, 5 y 20 sesiones tras la presentación frente al resto del universo. Es la forma de saber si la `impact_probability` correlaciona con algo antes de darle peso en el rating.
14. Ampliar el universo más allá de las megacaps estadounidenses y comprobar si el resultado sobrevive en small caps, donde los costes y el slippage son materialmente mayores.
15. Ejecutar paper trading en directo durante 6-12 meses y comparar las señales reales con las que el replay produce para esas mismas fechas: es la única validación no retrospectiva.

---

### Reproducibilidad

```
python backtest_cli.py --start 2015-01-01 --end 2025-12-31 --rebalance monthly --regime pit --costs-bps 10.0 --capital 100000 --mc-runs 1000
```

Configuración: {"tickers": 50, "start": "2015-01-01", "end": "2025-12-31", "rebalance": "monthly", "costs_bps_round_trip": 10.0, "capital": 100000.0, "max_holding_days": null, "mc_runs": 1000, "benchmark": "SPY"}


Señales descartadas por falta de datos: `{"sin_fundamentales": 979}`
