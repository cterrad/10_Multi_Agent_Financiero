# Backtest del sistema multi-agente de recomendaciones de compra

_Periodo del estudio: 2015-01-01 a 2025-12-31 · régimen `pit` · 50 valores · rebalanceo monthly._

_Vintage de las series: `cot` CFTC, filtrado por fecha_publicacion · `fundamentales` SEC EDGAR companyfacts, filed<=t · `opciones` ausente (histórico por ticker de pago) · `precios` caché yfinance 2015-01-01..2025-12-31 · `volatilidad` ALFRED output_type=4, filtrado por fecha_publicacion._

> **Régimen de datos:** POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio

## 1. Veredicto ejecutivo

**NO.** Y el motivo es más grave que el rendimiento: **el rating no ordena el futuro en la dirección que afirma.** Los valores calificados VENTA FUERTE rindieron de media 34.24% a 12 meses, frente al 13.89% de los COMPRA FUERTE.

  Matiz obligado antes de concluir que la señal está *invertida*: el sesgo de supervivencia golpea de forma desigual a cada categoría. VENTA FUERTE recoge sobre todo empresas con fundamentales deteriorados, y de esas solo están en el universo las que sobrevivieron hasta hoy — precisamente las que se recuperaron. La lectura defendible es más prudente: **el rating no separa ganadores de perdedores**, y el signo aparente de la inversión no puede afirmarse sin composiciones históricas del índice.

- Régimen de datos del resultado principal: POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio
- CAGR estrategia 3.97% vs SPY 13.51% (exceso -9.54%); Sharpe 0.74 vs 0.80.
- Máximo drawdown -16.15%; 532 operaciones; tasa de acierto 49.81% frente al 36.36% de equilibrio que exige el R:R 1.75 del sistema.
- Alfa anualizado 1.74% (t=1.24); percentil frente a señales aleatorias: 17.7.
- Rendimiento medio a 12 meses por rating: VENTA FUERTE 34.24% · COMPRA 28.04% · SIN OPINION 25.23% · MANTENER 19.12% · VENTA 17.89% · COMPRA FUERTE 13.89%. El mejor es **VENTA FUERTE**.

**Las tres limitaciones más serias, antes de cualquier lectura positiva:**
1. **La memoria de reflexión está desactivada**, que es la configuración de entrega. Se implementó como traducción determinista de la *low-level reflection* de FinAgent y se midió contra su contrafactual exacto sobre 2015-2025: empeoró las dos métricas de selección (percentil aleatorio 7.4 → 3.1, expectativa +1.23% → +0.95%) además del CAGR, el Sharpe y el drawdown. El código, sus tests y este contraste se conservan; la capa no decide. **Ese resultado negativo es publicable y no debe suavizarse: es exactamente el contraste que los dos papers de referencia no llegan a ejecutar.**
2. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 27.9%, así que un 72% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
3. **La exposición es una CONSECUENCIA del presupuesto de riesgo, no un objetivo.** El motor histórico dimensiona ya con `src/portfolio/construccion.py` —la misma capa que corre en vivo: límites por sector, penalización por correlación y presupuesto de riesgo agregado—, así que la cartera simulada es la que el sistema recomendaría hoy. Pero el tamaño de cada posición sale de arriesgar un 0.75% del patrimonio contra la distancia al stop, y con pocas señales simultáneas eso deja la exposición bruta en el 28%. **El sistema no define qué hacer con el resto**, y esa es una decisión de diseño que falta: una estrategia estructuralmente invertida a un tercio no puede compararse contra un índice invertido al 100% sin decirlo. Las métricas ajustadas por riesgo (Sharpe, Sortino) son la comparación honesta; el CAGR absoluto no lo es.


## 2. Estrategia frente a los benchmarks

| Cartera | CAGR | Retorno total | Volatilidad | Sharpe | Sortino | Calmar | Máx. drawdown | Capital final |
|---|---|---|---|---|---|---|---|---|
| Estrategia | 3.97% | 53.39% | 5.44% | 0.74 | 0.92 | 0.25 | -16.15% | $153,387 |
| SPY comprar y mantener | 13.51% | 302.73% | 17.79% | 0.80 | 0.98 | 0.40 | -33.72% | $402,727 |
| Universo equiponderado | 20.30% | 662.35% | 18.93% | 1.07 | 1.31 | 0.61 | -33.17% | $762,350 |


**Contraste contra selección aleatoria (Monte Carlo, hipótesis nula):**

Las carteras aleatorias replican el perfil observado de la estrategia — 4 posiciones simultáneas, 31 días de tenencia media y 27.91% de exposición bruta — pero eligen los valores al azar. Aísla la habilidad de selección de la mera exposición al mercado.

- CAGR medio de las carteras aleatorias: 4.91% (p05 3.13%, p95 6.70%).
- La estrategia queda en el percentil **17.7** de esa distribución. p-valor unilateral: **0.8230**.


## 3. Métricas completas de la estrategia

| Métrica | Valor |
|---|---|
| Periodo | 2015-01-02 → 2025-12-30 |
| Años | 11.0 |
| Capital inicial | $100,000 |
| Capital final | $153,387 |
| Retorno total | 53.39% |
| CAGR | 3.97% |
| Volatilidad anualizada | 5.44% |
| Sharpe | 0.74 |
| Sortino | 0.92 |
| Calmar | 0.25 |
| Máximo drawdown | -16.15% |
| Duración máx. del drawdown (días) | 981 |
| VaR 95% diario | -0.56% |
| CVaR 95% diario | -0.84% |
| Mejor año | 13.30% |
| Peor año | -10.35% |
| Beta vs SPY | 0.16 |
| Alfa anualizado vs SPY | 1.74% |
| t-stat del alfa | 1.24 |
| R² vs SPY | 0.28 |
| Exposición bruta media | 27.91% |
| Posiciones simultáneas medias | 4.3 |
| Rotación anualizada | 6.52 |
| Costes totales pagados | $9,105 |
| —— Operaciones —— |  |
| Número de operaciones | 532 |
| Tasa de acierto | 49.81% |
| Tasa de equilibrio exigida (R:R 1.75) | 36.36% |
| Profit factor | 1.45 |
| Ganancia media | 8.52% |
| Pérdida media | -5.89% |
| Esperanza por operación | 1.29% |
| Días medios en cartera | 31.9 |
| Mejor operación | 23.95% |
| Peor operación | -22.91% |


**Intervalo de confianza del CAGR (bootstrap de retornos diarios, 2000 muestras):** p05 1.27% · mediana 3.99% · p95 6.78%. Probabilidad de CAGR negativo: 0.85%.


## 4. Curva de capital y drawdown

![Curva de capital](backtest_equity_pit.png)


![Monte Carlo](backtest_montecarlo_pit.png)


**Rentabilidad por año natural:**

| Año | Estrategia | SPY |
|---|---|---|
| 2015 | -0.22% | 1.29% |
| 2016 | 4.85% | 12.00% |
| 2017 | 13.30% | 21.71% |
| 2018 | 0.80% | -4.57% |
| 2019 | 9.18% | 31.22% |
| 2020 | 2.36% | 18.33% |
| 2021 | 8.82% | 28.73% |
| 2022 | -10.35% | -18.18% |
| 2023 | 10.68% | 26.18% |
| 2024 | 0.17% | 24.89% |
| 2025 | 6.20% | 18.60% |


## 5. Atribución


### Por rating de entrada

| rating | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| COMPRA | 478 | 0.4979 | 0.0136 | 49369.0481 | 31.4268 |
| COMPRA FUERTE | 54 | 0.5000 | 0.0069 | 4017.6309 | 35.8704 |


### Por estilo de inversion

| estilo | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| CALIDAD_COMPUESTA | 356 | 0.4803 | 0.0131 | 35205.1186 | 35.5000 |
| VALOR | 86 | 0.5698 | 0.0239 | 12734.1805 | 32.6744 |
| CRECIMIENTO | 86 | 0.5000 | 0.0021 | 5820.6522 | 16.8372 |
| MIXTA | 4 | 0.5000 | -0.0071 | -373.2724 | 15.7500 |


### Por sector

| sector | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| Technology | 338 | 0.5059 | 0.0154 | 36452.2523 | 31.5769 |
| Communication Services | 51 | 0.5294 | 0.0210 | 9132.0063 | 29.3922 |
| Financial Services | 46 | 0.6304 | 0.0150 | 7149.5154 | 36.8913 |
| Consumer Defensive | 22 | 0.5455 | 0.0146 | 4413.5398 | 29.5909 |
| Industrials | 6 | 0.5000 | 0.0354 | 1873.9099 | 34.1667 |
| Consumer Cyclical | 12 | 0.3333 | -0.0270 | -483.7213 | 21.5833 |
| Healthcare | 57 | 0.3333 | -0.0057 | -5150.8234 | 34.6491 |


### Por motivo de salida

| exit_reason | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| take_profit | 236 | 1.0000 | 0.0918 | 165049.9849 | 37.1525 |
| fin_backtest | 6 | 0.6667 | 0.0165 | 1524.0437 | 33.6667 |
| downgrade_VENTA | 7 | 0.7143 | 0.0273 | 1187.4414 | 34.5714 |
| downgrade_MANTENER | 73 | 0.2740 | -0.0123 | -5730.8185 | 49.8767 |
| stop_loss | 210 | 0.0000 | -0.0676 | -108643.9724 | 19.5524 |


### Por año de salida

| year | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| 2015 | 30 | 0.2667 | -0.0060 | -448.4297 | 23.4667 |
| 2016 | 35 | 0.5429 | 0.0254 | 4992.3482 | 38.4857 |
| 2017 | 57 | 0.7368 | 0.0304 | 14123.6514 | 29.3684 |
| 2018 | 50 | 0.4400 | -0.0048 | 822.1710 | 30.4600 |
| 2019 | 63 | 0.5397 | 0.0294 | 8899.6210 | 32.9841 |
| 2020 | 30 | 0.6000 | 0.0507 | 3870.5633 | 44.4333 |
| 2021 | 53 | 0.6038 | 0.0237 | 13052.5046 | 32.2075 |
| 2022 | 50 | 0.2000 | -0.0447 | -15337.1990 | 24.3000 |
| 2023 | 49 | 0.5306 | 0.0290 | 13401.6142 | 38.5714 |
| 2024 | 67 | 0.4478 | 0.0039 | 1224.4228 | 28.2090 |
| 2025 | 48 | 0.5000 | 0.0123 | 8785.4111 | 33.2917 |


### Event study: rendimiento futuro por rating

Independiente del gestor de cartera: mide si el rating por sí solo anticipa el movimiento posterior del precio. Es la prueba más limpia de poder predictivo.

| rating | n | fwd_1m_media | fwd_1m_mediana | fwd_1m_pct_positivo | fwd_1m_tstat | fwd_3m_media | fwd_3m_mediana | fwd_3m_pct_positivo | fwd_3m_tstat | fwd_6m_media | fwd_6m_mediana | fwd_6m_pct_positivo | fwd_6m_tstat | fwd_12m_media | fwd_12m_mediana | fwd_12m_pct_positivo | fwd_12m_tstat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMPRA | 749 | 0.0143 | 0.0144 | 0.5728 | 4.7052 | 0.0525 | 0.0398 | 0.6262 | 9.5582 | 0.1165 | 0.0917 | 0.7116 | 13.2977 | 0.2804 | 0.2028 | 0.7810 | 16.4770 |
| COMPRA FUERTE | 88 | 0.0143 | 0.0122 | 0.5909 | 1.9744 | 0.0435 | 0.0518 | 0.7273 | 3.1420 | 0.0769 | 0.0805 | 0.6136 | 3.4065 | 0.1389 | 0.1032 | 0.6591 | 4.4825 |
| MANTENER | 1028 | 0.0179 | 0.0165 | 0.5944 | 6.6648 | 0.0491 | 0.0424 | 0.6391 | 10.5178 | 0.0949 | 0.0744 | 0.6751 | 13.1820 | 0.1912 | 0.1625 | 0.7218 | 16.6362 |
| SIN OPINION | 285 | 0.0159 | 0.0069 | 0.5649 | 2.8445 | 0.0493 | 0.0288 | 0.6035 | 4.5223 | 0.1095 | 0.0784 | 0.6842 | 5.8564 | 0.2523 | 0.1262 | 0.7579 | 6.3777 |
| VENTA | 3216 | 0.0142 | 0.0126 | 0.5784 | 10.6314 | 0.0434 | 0.0361 | 0.6231 | 18.4903 | 0.0887 | 0.0670 | 0.6816 | 25.5280 | 0.1789 | 0.1356 | 0.7397 | 35.2350 |
| VENTA FUERTE | 211 | 0.0250 | 0.0133 | 0.5640 | 3.1512 | 0.0752 | 0.0426 | 0.6303 | 5.1932 | 0.1578 | 0.1423 | 0.6635 | 7.2758 | 0.3424 | 0.4349 | 0.7062 | 10.8941 |


## 6. Robustez por subperiodo

| Subperiodo | Retorno estrategia | Retorno SPY | Sharpe | Máx. drawdown |
|---|---|---|---|---|
| Pre-COVID 2015-2019 | 0.3046 | 0.7289 | 1.1270 | -0.0812 |
| Crash COVID 2020-02→2020-04 | 0.0000 | -0.0985 | 0.0000 | 0.0000 |
| Recuperación 2020-2021 | 0.1093 | 0.7236 | 1.2104 | -0.0429 |
| Bajista 2022 | -0.1114 | -0.1865 | -1.5248 | -0.1573 |
| Post-2023 | 0.1780 | 0.8767 | 0.9755 | -0.0478 |


## 7. Sensibilidad a costes de transacción

| Nivel de coste | CAGR | Sharpe | Máx. drawdown | Capital final |
|---|---|---|---|---|
| 0 bps ida y vuelta | 0.0463 | 0.8633 | -0.1544 | 164540.5687 |
| 5 bps ida y vuelta | 0.0430 | 0.8039 | -0.1580 | 158865.5534 |
| 10 bps ida y vuelta | 0.0397 | 0.7444 | -0.1615 | 153386.6790 |
| 25 bps ida y vuelta | 0.0298 | 0.5663 | -0.1721 | 138060.1372 |


## 7b. Actividad de la memoria de reflexión

Capa desactivada (desactivada por defecto tras el contraste de 2015-2025; se activa con --con-reflexion). Ningún peso fue recortado por expectativa histórica.


## 8. Limitaciones y sesgos residuales

Esta sección no se suaviza. Cada punto es una razón concreta por la que el resultado de arriba podría no repetirse fuera de muestra.

1. **La memoria de reflexión está desactivada**, que es la configuración de entrega. Se implementó como traducción determinista de la *low-level reflection* de FinAgent y se midió contra su contrafactual exacto sobre 2015-2025: empeoró las dos métricas de selección (percentil aleatorio 7.4 → 3.1, expectativa +1.23% → +0.95%) además del CAGR, el Sharpe y el drawdown. El código, sus tests y este contraste se conservan; la capa no decide. **Ese resultado negativo es publicable y no debe suavizarse: es exactamente el contraste que los dos papers de referencia no llegan a ejecutar.**
2. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 27.9%, así que un 72% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
3. **La exposición es una CONSECUENCIA del presupuesto de riesgo, no un objetivo.** El motor histórico dimensiona ya con `src/portfolio/construccion.py` —la misma capa que corre en vivo: límites por sector, penalización por correlación y presupuesto de riesgo agregado—, así que la cartera simulada es la que el sistema recomendaría hoy. Pero el tamaño de cada posición sale de arriesgar un 0.75% del patrimonio contra la distancia al stop, y con pocas señales simultáneas eso deja la exposición bruta en el 28%. **El sistema no define qué hacer con el resto**, y esa es una decisión de diseño que falta: una estrategia estructuralmente invertida a un tercio no puede compararse contra un índice invertido al 100% sin decirlo. Las métricas ajustadas por riesgo (Sharpe, Sortino) son la comparación honesta; el CAGR absoluto no lo es.
4. **Divergencia de definición fundamental.** Producción lee métricas TTM de `yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, porque el TTM histórico de yfinance no es recuperable retroactivamente. El gatekeeper se evalúa por tanto con una ventana contable distinta a la de producción: los ratings del backtest son fieles a la *lógica* del sistema, no necesariamente idénticos a los que habría emitido en directo.
5. **El ajuste de entrada que este estudio mide NO es el que produce la cadena de opciones.** El Analista de Posicionamiento elige el nivel entre cuatro candidatos: soporte de open interest, max pain, punto de inflexión de la gamma y **soporte estructural del precio**. Los tres primeros salen de la cadena, cuyo histórico por ticker es de pago, así que en el estudio están siempre ausentes. El cuarto sale del OHLCV y sí es reconstruible point-in-time, y por eso el ajuste de entrada por fin se mide — pero se mide **con soportes de precio, no con open interest**. Son dos niveles distintos y el informe no los promedia: lo que estas cifras evalúan es la regla de entrada apoyada en la estructura del precio. La versión que corre en vivo, con cadena disponible, elegirá a veces otro nivel.
6. **Medido: esperar al soporte NO mejora el resultado, y probablemente lo empeora.** Sobre las 936 señales de compra del régimen `pit`, con los stops y objetivos del propio Fund Manager y 10 pb de costes, entrar al nivel MEJORA la operación (expectativa +1.70% frente a +1.34%, factor de beneficio 1.53 frente a 1.43) y EMPEORA el valor esperado por señal (+0.78% frente a +1.34%), porque lo que la orden no rellena es precisamente lo que sube: esas señales habrían rendido +3.56% con un **59.6% de acierto** frente al 45.3% de la línea base. La selección adversa cancela exactamente la mejora de precio. Por eso `--con-entrada-limitada` existe pero está DESACTIVADA por defecto: es una medición, no una preferencia.
7. **Del posicionamiento en futuros solo se mide el veto.** El bloque macro sí es reconstruible: `COTStore` filtra los informes de la CFTC por fecha de PUBLICACIÓN (viernes) y no por la del informe (martes), que es el mismo par `filed`/`end` de los hechos XBRL. Lo que el estudio mide es por tanto el veto que topa en COMPRA con viento macro fuertemente en contra; la dirección macro, por sí sola, no elige nivel.
8. **Del régimen de volatilidad se mide el 100%, y es la única capa de la que puede decirse.** `VIXCLS` y `VXVCLS` llegan por ALFRED, cuyos parámetros de tiempo real devuelven la serie tal y como se conocía en una fecha y adjuntan a cada observación su fecha de publicación. Verificado contra la API: la observación semanal del miércoles 2020-03-25 es invisible consultando ese mismo día y aparece el 26. El retardo no hay que modelarlo, hay que no estorbarlo, y `FREDStore` invoca la MISMA función de selección de producción con `as_of` en lugar de reimplementarla.
9. **La curva de volatilidad no es reconstruible antes de 2014.** `VXVCLS` observa desde 2007 pero su ARCHIVO en ALFRED empieza en 2014: pedir 2013 devuelve «the series does not exist in ALFRED». No afecta a la ventana del estudio, que empieza en 2015, pero sí acota cualquier extensión hacia atrás. Cuando falta, `ratio_curva` es `None` y el agravamiento por curva invertida no se aplica — nunca se asume contango.
10. **El meta-modelo está DESACTIVADO, y es una medición, no una duda de diseño.** `--con-meta` activa el meta-etiquetado de López de Prado con reentrenamiento walk-forward, CV purgada con embargo y pesos por unicidad. En las OCHO ventanas con muestra suficiente la AUC en validación cruzada purgada salió por DEBAJO de 0.5 —0.40, 0.40, 0.45, 0.45, 0.47, 0.47, 0.44, 0.47— así que la barrera de `META_VENTAJA_MINIMA_AUC` impidió entregar artefacto en todas ellas y el factor se quedó en 1.0. Ejecutar con y sin la bandera produce cifras idénticas. **La lectura es que las 23 variables que el sistema conoce al emitir una señal no contienen información utilizable sobre si esa compra concreta acabará en beneficio**, lo que es coherente con el hallazgo ya publicado de que el rating tampoco ordena el rendimiento futuro.
11. **La caché del COT no cubría siete de los once años del estudio, y ahora sí.** `data/cache/cot/` solo contenía 2022-2026, así que el veto macro que este informe afirmaba medir estuvo INERTE de 2015 a 2021. Recargada de 2013 en adelante con la misma función de producción, el veto actúa: **la tasa de acierto sube 2.5 puntos** (47.3% → 49.8%) sobre 532 operaciones, la expectativa pasa de +1.283% a +1.291% y el percentil frente a selección aleatoria de 16.6 a 17.7 — las dos últimas, mejoras marginales. El drawdown empeora de −15.57% a −16.15%. **El valor de esta corrección no es el rendimiento sino la corrección misma: un informe que afirmaba medir un veto que llevaba siete años inerte estaba equivocado, y lo seguía estando aunque el efecto resulte modesto.**
12. **Del sesgo macro se mide la pata de ÍNDICE; la SECTORIAL falta antes de 2022.** Los nombres de mercado de la CFTC cambiaron: el patrón `COPPER- #1` no casa con `COPPER-GRADE #1`, ni `NAT GAS NYME` con `NATURAL GAS`, ni `UST 10Y NOTE` con `10-YEAR U.S. TREASURY NOTES`. Los patrones estaban verificados contra `deacot2025.zip` y solo contra ese. El contrato de índice —`E-MINI S&P 500`, que reciben TODOS los valores— sí resuelve con 520 semanas, así que el sesgo macro se calcula para todos; lo que falta es la pata sectorial de energía, materiales y financieras en el primer tramo del estudio.
13. **El freno por drawdown está implementado y es INERTE EN PRODUCCIÓN.** `drawdown_guard` traducido a un factor que solo recorta la exposición. El backtest conoce la curva de capital; producción NO: el sistema emite recomendaciones, no gestiona una cartera y no sabe su patrimonio. Cablearlo solo en el estudio sería una variable de decisión medida aquí y ausente en vivo — la imagen especular exacta de la divergencia del ajuste de entrada. Por eso el parámetro es opcional y neutro por defecto, y por eso estas cifras NO lo incluyen.
14. **El sesgo de reajuste retroactivo de los precios sigue SIN CUANTIFICAR.** yfinance sirve precios ajustados por splits y dividendos con la información de hoy, así que el precio de 2015 que se descarga hoy no es el que vio un observador de 2015. Afecta por igual a los indicadores técnicos y a los soportes estructurales. La Fase 1 buscó una fuente EOD independiente para acotarlo y la única gratuita probada está tras un desafío anti-bot, así que la magnitud del efecto es desconocida.
15. **El signo de la exposición gamma es una convención, no una medición.** Se asume que los creadores de mercado están largos gamma en calls y cortos en puts. Es la convención estándar del sector, pero la cadena publica open interest y no quién está en cada lado de cada contrato. Si esa convención falla en un valor concreto, el punto de inflexión calculado apunta al lado contrario. Solo afecta a producción: en el backtest no hay cadena.
16. **Los percentiles de put/call y de skew necesitan histórico propio.** Se calculan sobre la caché acumulativa de cadenas diarias, así que una instalación nueva no puede emitirlos hasta acumular `OPCIONES_MINIMO_DIAS_HISTORICO` observaciones. Hasta entonces se declaran DATOS_INSUFICIENTES en lugar de asumir el percentil 50, y el sesgo de opciones se apoya solo en el punto de inflexión de la gamma.
17. **El mapa sector→futuro es sectorial, no industrial.** Bancos y REITs comparten la entrada del bono a 10 años pese a no responder igual al mismo contrato, y «Basic Materials» mezcla mineras de metales industriales con químicas. Los sectores sin contrato correlato claro no reciben pata sectorial y se evalúan solo con el índice: se declara NO_APLICABLE en lugar de forzar un proxy.
18. **Normas sectoriales estáticas.** El contexto de valoración compara cada múltiplo contra una mediana de largo plazo del mercado estadounidense (`SECTOR_NORMAS` en `src/config.py`), no contra la mediana viva del sector en la fecha simulada. En un backtest de once años eso introduce un anacronismo: el P/E mediano del software en 2015 no era el de 2025. Las etiquetas de estilo ordenan y contextualizan, pero no deben leerse como una valoración relativa exacta.
19. **Coste de capital constante.** El ROIC se compara contra un WACC de referencia único (`WACC_REFERENCIA`) en lugar de estimarlo por empresa y por fecha. Es una decisión consciente —la dispersión de un WACC estimado con beta y estructura de capital superaría la señal que aporta— pero implica que «crea valor» significa «supera un umbral fijo», no «supera su propio coste de capital».
20. **Sesgo de supervivencia.** El universo son 50 valores seleccionados hoy por su relevancia actual. Las empresas que quebraron o fueron excluidas nunca entran en la muestra, lo que infla el resultado en una magnitud no cuantificada aquí (la literatura sitúa el efecto entre 1 y 4 puntos de CAGR según periodo y universo).
21. **Deuda/Capital ausente se trata como 0.0.** Se replica el comportamiento de producción (`info.get("debtToEquity", 0.0)`), lo que hace que el filtro de apalancamiento se salte silenciosamente cuando el dato falta en EDGAR, en lugar de rechazar el valor.
22. **Finnhub ausente en el backtest.** No hay histórico point-in-time gratuito, así que el `confidence_score` de la reconciliación difiere del de producción. Verificado en la Fase 1 que no altera ninguna decisión (solo añade texto), pero es una divergencia real.
23. **Analista de Noticias excluido del backtest.** El grafo de producción ejecuta un nodo `news_analysis` que este replay NO recorre. Dos de sus tres fuentes (Google News RSS y Tavily) son buscadores "de hoy": no existe forma asequible de recuperar qué estaba publicado y visible en una fecha pasada, y sus corpus indexados hoy omiten lo que se borró y fechan por republicación, no por el hecho. Solo el 8-K con Ítem 2.02 tiene `filed` exacto y sería reconstruible. Por eso las noticias son hoy una CAPA ASESORA: aparecen en el informe diario y alimentan el debate, pero no tocan `rating` ni `position_size_pct`, de modo que su ausencia aquí no altera ni una sola señal. La contrapartida es que el valor predictivo de esa capa está SIN MEDIR: no hay ninguna evidencia en este informe de que las noticias aporten nada.
24. **Sin datos intradía.** Cuando stop y objetivo se tocan en la misma sesión se asume que saltó el stop. Es conservador, pero desconoce el orden real y sesga el resultado a la baja en una cuantía desconocida.
25. **Costes estimados, no reales.** Comisión y slippage son parámetros fijos en puntos básicos. No modelan impacto de mercado, y para tamaños grandes de cartera el deslizamiento real crecería con el volumen.
26. **Cobertura incompleta de señales.** Descartes por falta de datos: {'sin_fundamentales': 979}. Los tickers sin fundamentales publicados en una fecha simplemente no generan señal, lo que reduce el universo efectivo en los primeros años del estudio.
27. **El percentil frente a selección aleatoria arrastra ruido de muestreo.** La misma estrategia —mismo CAGR al cuarto decimal, mismas 532 operaciones, misma expectativa— da percentil 20.3 con 300 muestras de Monte Carlo y 17.7 con 1000. Son del orden de 2.6 puntos de ruido. Las cifras publicadas usan siempre las 1000 por defecto, y **una diferencia de percentil por debajo de uno o dos puntos entre configuraciones no es interpretable.**
28. **Contrastes múltiples.** Se han evaluado varios regímenes, frecuencias y niveles de coste sobre el mismo periodo histórico. El p-valor mostrado no está corregido por multiplicidad: interprétese como orientativo, no como una prueba formal.

## 9. Próximos pasos para reforzar la validez

1. RESUELTO — la regla de ejecución de ÓRDENES LIMITADAS ya está en `engine.py`. La orden lleva como límite el `precio_entrada_objetivo`, vive `vida_orden_sesiones` sesiones, se rellena a la apertura si esta abre por debajo del límite, al límite si el mínimo lo toca, y **se cancela sin abrir posición** si expira. Esa tercera rama es la que hace honesta la comparación. Se activa con `--con-entrada-limitada` y está DESACTIVADA por defecto porque la medición la desaconseja, no porque falte código.
2. NO comprar histórico de cadenas de opciones todavía. La pregunta que justificaba el gasto —«¿mejora el resultado entrar más abajo?»— ya tiene respuesta medida, y es que NO: sobre las 936 señales de compra del estudio, entrar al soporte mejora la operación (+1.70% frente a +1.34% de expectativa) y empeora el valor esperado por señal (+0.78% frente a +1.34%), porque lo que la orden no rellena acierta el 59.6% de las veces. Un nivel MEJOR —de open interest en vez de de precio— podría cambiar la magnitud, pero tendría que invertir el signo de la selección adversa para cambiar la conclusión, y no hay ninguna razón para esperar que lo haga. Reconsiderarlo solo con evidencia en vivo.
3. Ampliar los patrones de `SECTOR_A_FUTURO` para que casen con las DOS convenciones de nombres de la CFTC (`COPPER-GRADE #1` y `COPPER- #1`, `NATURAL GAS` y `NAT GAS NYME`, `10-YEAR U.S. TREASURY NOTES` y `UST 10Y NOTE`). `_elegir_mercado` ya resuelve la ambigüedad quedándose con el de mayor interés abierto, así que el mecanismo existe. NO se hizo en esta revalidación porque cambiaría el dosier macro de producción sin medirlo, y el presupuesto de ensayos ya estaba gastado: hacerlo exige su propio contraste.
4. Reevaluar el meta-etiquetado con OTRO universo o con etiquetas de horizonte más corto. Lo medido aquí es que las 23 variables del sistema no separan las compras que funcionan de las que no, con AUC bajo 0.5 en ocho ventanas. Antes de volver a intentarlo conviene resolver la pregunta de la que depende: **por qué el rating no ordena el rendimiento futuro**. Un meta-modelo sobre los insumos de una señal cuya dirección no ordena difícilmente puede ordenar él.
5. Decidir qué hacer con el freno por drawdown. Está implementado y probado pero es inerte en producción porque el sistema no gestiona una cartera. Las dos salidas honestas son: persistir una curva de capital en producción —lo que exige que el sistema sepa qué se ejecutó, y hoy no lo sabe— o retirarlo. Dejarlo activo solo en el backtest no es una de ellas.
6. PRIORIDAD 1 DE ESTA REVALIDACIÓN — validar walk-forward el umbral de TENSION del régimen de volatilidad. El barrido midió que subirlo de 25 a 30 es la MEJOR de las trece configuraciones evaluadas (expectativa +1.44% frente a +1.28%, percentil 24.3 frente a 16.7), y que bajarlo a 20 no cambia absolutamente nada. La explicación es mecánica: `_clasificar_regimen` toma el MÁXIMO de los escalones por nivel y por z-score, y en esta ventana manda el z-score, así que bajar el corte de nivel queda enmascarado y subirlo hasta 30 deja el escalón TENSION casi inerte. La lectura sería que el escalón TENSION perjudica y solo el de PANICO aporta. **Pero se entrega 25, que es el valor fijado ANTES de medir**: tres puntos de una curva sobre el mismo histórico no acreditan un óptimo, acreditan que se ha buscado uno, y adoptar el que mejor midió sería el defecto que este proyecto ya documentó tres veces. La validación que lo resolvería: fijar el umbral con datos hasta 2019 y evaluar 2020-2025 sin volver a mirarlo.
7. Comprobar si la bandera `soporte_lejano` merece existir. Duplicar su umbral de 1.5 a 3.0 ATR mueve UNA operación de 535 y deja el acierto en 47.2% frente a 47.3%: es prácticamente inerte, así que el +2.7pp de acierto que aporta el Analista de Estructura viene del nivel de entrada y no de ella. O se reformula para que actúe, o se retira: una bandera que no dispara es código que hay que mantener sin contrapartida.
8. Investigar por qué la selección adversa cancela EXACTAMENTE la mejora de precio. Lo llamativo de la medición no es que la regla limitada pierda por coste de oportunidad —eso era previsible— sino que la rentabilidad CONDICIONADA a operar sea prácticamente idéntica en las tres reglas (+1.71% a mercado, +1.76% al límite, +1.71% con recuperación confirmada). Si eso se sostiene en otro universo, dice algo sobre la eficiencia del precio de entrada a barra diaria que va mucho más allá de este sistema.
9. Construir el `NewsStore` point-in-time sobre el índice diario de EDGAR (`edgar/daily-index/{año}/QTR{n}/form.{fecha}.idx`), que la Fase 1 acreditó como PIT-NATIVE: cada presentación viene con su fecha exacta y el archivo llega a 1994. Cubre resultados y hechos relevantes, no prensa general. Construirlo NO autoriza por sí solo a conectar las noticias a la decisión: siguen siendo asesoras hasta que el almacén cubra la ventana y `test_news_report_does_not_alter_decision` se retire deliberadamente.
10. Validar empíricamente la convención de signo de la exposición gamma contrastando el `gamma_flip` calculado contra el comportamiento observado del precio en una muestra de valores, antes de darle más peso en la elección de nivel.
11. Afinar el mapa sector→futuro a nivel de INDUSTRIA. Bancos y REITs no responden igual al bono a 10 años, y una aerolínea y una petrolera tienen signos opuestos frente al crudo pese a caer en sectores distintos hoy por casualidad.
12. HIPÓTESIS DESCARTADA CON DATOS: la reflexión de bajo nivel de FinAgent (arXiv:2402.18485), traducida a reglas deterministas y medida contra su contrafactual exacto sobre 2015-2025, EMPEORA la selección: percentil frente a señales aleatorias 7.4 → 3.1, expectativa por operación +1.23% → +0.95%, drawdown −13.8% → −18.0%. La capa actuó (recortó el 18.3% de las señales con factor medio ×0.93), así que no es un problema de activación. La lectura más probable es que el rendimiento relativo de un perfil a un mes REVIERTE en lugar de persistir. La línea de investigación honesta no es invertir el signo sobre el mismo histórico —eso es el defecto metodológico de los papers de referencia— sino declarar la hipótesis contraria de antemano y contrastarla con validación walk-forward sobre 2020-2025, o con otro horizonte de desenlace que el de 21 sesiones.
13. PRIORIDAD 1 — investigar la ordenación del rating. Antes de tocar stops, sizing o costes, comprobar si el event study mantiene el orden invertido (VENTA FUERTE rindiendo más que COMPRA FUERTE) en otros universos y periodos. Si se confirma, el problema está en la señal y ningún ajuste de gestión de cartera lo arreglará.
14. HIPÓTESIS DESCARTADA CON DATOS: no es un sesgo contra el *value*. La atribución por estilo (`attr_estilo`) muestra que las operaciones etiquetadas VALOR son las de MEJOR rentabilidad media del sistema, y que el lastre está en CRECIMIENTO, con rentabilidad media negativa pese a un número de operaciones similar. La línea de investigación correcta es por qué el sistema paga múltiplos de crecimiento que después no se materializan: revisar el peso del momentum en la puntuación compuesta y el umbral de PEG que habilita GARP.
15. Medir por separado el efecto del stop de 2·ATR. Con más de la mitad de las salidas disparadas por stop y una tenencia media inferior a 20 sesiones, el sistema puede estar cortando posiciones ganadoras antes de que maduren. Ejecutar una variante sin stop y otra con stop por tiempo para aislarlo.
16. Contratar o reconstruir las composiciones históricas del índice (CRSP, Norgate, Sharadar) para eliminar el sesgo de supervivencia, que hoy es el sesgo residual dominante.
17. Sustituir los fundamentales anuales por TTM point-in-time encadenando los cuatro trimestres XBRL disponibles en cada fecha, para acercar el backtest a la definición exacta que usa producción.
18. Validación walk-forward: fijar los umbrales del gatekeeper con datos hasta 2019 y evaluar 2020-2025 como out-of-sample estricto, sin volver a mirar el periodo de test.
19. Añadir datos intradía (o al menos barras horarias) para resolver correctamente el orden entre stop y objetivo dentro de la misma sesión.
20. Definir una política explícita para el capital no invertido. La exposición bruta que produce el presupuesto de riesgo es estructuralmente baja, y hoy el remanente se queda en efectivo al 0%. Las tres opciones razonables —remunerarlo a letras, invertirlo en el índice como posición residual, o subir el riesgo por posición— tienen implicaciones muy distintas y ninguna está tomada. Mientras no se decida, el CAGR absoluto compara una cartera a un tercio de exposición contra un índice al 100%.
21. Sustituir `SECTOR_NORMAS` por la mediana calculada sobre un conjunto de comparables en cada fecha. Es lo que convierte el contexto sectorial de una referencia estática en una valoración relativa point-in-time, y elimina el anacronismo declarado en las limitaciones.
22. Investigar por qué el rating sigue sin ordenar el rendimiento futuro pese a que la convicción fundamental ya entra en la decisión. La incorporación del Analista de Calidad mejoró notablemente el perfil de riesgo —el Sharpe casi se dobló y el drawdown máximo se redujo a la mitad— pero el orden de las categorías sigue invertido. Eso apunta a que el problema no está en la calidad del análisis fundamental sino en el corte que convierte la convicción en rating, o en el horizonte al que se mide: doce meses puede ser un plazo inadecuado para señales cuya tenencia media es de 33 sesiones.
23. Reconstruir el riesgo legal y regulatorio de forma point-in-time desde EDGAR (8-K Ítem 8.01 y el apartado de Procedimientos Legales del 10-K). Es la única vía para que un litigio material entre en la decisión sin romper el backtest: a diferencia de la prensa, esas presentaciones tienen fecha `filed` exacta.
24. Construir un `NewsStore` point-in-time antes de dejar que las noticias entren en la decisión. El único camino barato es el histórico completo de 8-K/10-Q de EDGAR filtrado por `filed <= t` (mismo patrón que `FundamentalStore`), que cubre resultados y hechos relevantes pero no prensa general; el resto exigiría un proveedor de archivo de noticias con marca temporal (RavenPack, Dow Jones DNA). Hasta entonces, subir el Analista de Noticias de capa asesora a variable de decisión dejaría el sistema sin backtest válido.
25. Medir la capa de noticias por separado con un event study sobre los 8-K con Ítem 2.02, que sí son reconstruibles point-in-time: comparar el rendimiento a 1, 5 y 20 sesiones tras la presentación frente al resto del universo. Es la forma de saber si la `impact_probability` correlaciona con algo antes de darle peso en el rating.
26. Ampliar el universo más allá de las megacaps estadounidenses y comprobar si el resultado sobrevive en small caps, donde los costes y el slippage son materialmente mayores.
27. Ejecutar paper trading en directo durante 6-12 meses y comparar las señales reales con las que el replay produce para esas mismas fechas: es la única validación no retrospectiva.

---

### Reproducibilidad

```
python backtest_cli.py --start 2015-01-01 --end 2025-12-31 --rebalance monthly --regime pit --costs-bps 10.0 --capital 100000 --mc-runs 1000
```

Configuración: {"tickers": 50, "start": "2015-01-01", "end": "2025-12-31", "rebalance": "monthly", "costs_bps_round_trip": 10.0, "capital": 100000.0, "max_holding_days": null, "mc_runs": 1000, "benchmark": "SPY"}


Señales descartadas por falta de datos: `{"sin_fundamentales": 979}`
