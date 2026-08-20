# Backtest del sistema multi-agente de recomendaciones de compra

_Generado el 2026-08-19 11:11._

> **Régimen de datos:** POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio

## 1. Veredicto ejecutivo

**NO.** Y el motivo es más grave que el rendimiento: **el rating no ordena el futuro en la dirección que afirma.** Los valores calificados VENTA FUERTE rindieron de media 35.06% a 12 meses, frente al 21.02% de los COMPRA FUERTE.

  Matiz obligado antes de concluir que la señal está *invertida*: el sesgo de supervivencia golpea de forma desigual a cada categoría. VENTA FUERTE recoge sobre todo empresas con fundamentales deteriorados, y de esas solo están en el universo las que sobrevivieron hasta hoy — precisamente las que se recuperaron. La lectura defendible es más prudente: **el rating no separa ganadores de perdedores**, y el signo aparente de la inversión no puede afirmarse sin composiciones históricas del índice.

- Régimen de datos del resultado principal: POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio
- CAGR estrategia 2.11% vs SPY 13.51% (exceso -11.40%); Sharpe 0.35 vs 0.80.
- Máximo drawdown -22.57%; 928 operaciones; tasa de acierto 43.53% frente al 36.36% de equilibrio que exige el R:R 1.75 del sistema.
- Alfa anualizado -0.41% (t=-0.24); percentil frente a señales aleatorias: 1.9.
- Rendimiento medio a 12 meses por rating: VENTA FUERTE 35.06% · COMPRA 23.75% · MANTENER 21.11% · COMPRA FUERTE 21.02% · VENTA 17.51%. El mejor es **VENTA FUERTE**.

**Las tres limitaciones más serias, antes de cualquier lectura positiva:**
1. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 27.8%, así que un 72% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
2. **El sistema no define qué hacer con el efectivo sobrante.** Emite pesos por posición (8-10% / 4-7%) pero nunca dice cuántas posiciones abrir ni cómo invertir el resto. La exposición del 28% es una consecuencia emergente de cuántas señales de compra aparecen, no una decisión de diseño. Buena parte de la diferencia frente al índice es simplemente no estar invertido.
3. **Divergencia de definición fundamental.** Producción lee métricas TTM de `yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, porque el TTM histórico de yfinance no es recuperable retroactivamente. El gatekeeper se evalúa por tanto con una ventana contable distinta a la de producción: los ratings del backtest son fieles a la *lógica* del sistema, no necesariamente idénticos a los que habría emitido en directo.


## 2. Estrategia frente a los benchmarks

| Cartera | CAGR | Retorno total | Volatilidad | Sharpe | Sortino | Calmar | Máx. drawdown | Capital final |
|---|---|---|---|---|---|---|---|---|
| Estrategia | 2.11% | 25.83% | 6.58% | 0.35 | 0.39 | 0.09 | -22.57% | $125,828 |
| SPY comprar y mantener | 13.51% | 302.73% | 17.79% | 0.80 | 0.98 | 0.40 | -33.72% | $402,727 |
| Universo equiponderado | 20.30% | 662.35% | 18.93% | 1.07 | 1.31 | 0.61 | -33.17% | $762,350 |


**Contraste contra selección aleatoria (Monte Carlo, hipótesis nula):**

Las carteras aleatorias replican el perfil observado de la estrategia — 4 posiciones simultáneas, 18 días de tenencia media y 27.81% de exposición bruta — pero eligen los valores al azar. Aísla la habilidad de selección de la mera exposición al mercado.

- CAGR medio de las carteras aleatorias: 4.34% (p05 2.53%, p95 6.11%).
- La estrategia queda en el percentil **1.9** de esa distribución. p-valor unilateral: **0.9810**.


## 3. Métricas completas de la estrategia

| Métrica | Valor |
|---|---|
| Periodo | 2015-01-02 → 2025-12-30 |
| Años | 11.0 |
| Capital inicial | $100,000 |
| Capital final | $125,828 |
| Retorno total | 25.83% |
| CAGR | 2.11% |
| Volatilidad anualizada | 6.58% |
| Sharpe | 0.35 |
| Sortino | 0.39 |
| Calmar | 0.09 |
| Máximo drawdown | -22.57% |
| Duración máx. del drawdown (días) | 1499 |
| VaR 95% diario | -0.67% |
| CVaR 95% diario | -1.08% |
| Mejor año | 16.80% |
| Peor año | -17.56% |
| Beta vs SPY | 0.19 |
| Alfa anualizado vs SPY | -0.41% |
| t-stat del alfa | -0.24 |
| R² vs SPY | 0.27 |
| Exposición bruta media | 27.81% |
| Posiciones simultáneas medias | 4.3 |
| Rotación anualizada | 10.89 |
| Costes totales pagados | $13,551 |
| —— Operaciones —— |  |
| Número de operaciones | 928 |
| Tasa de acierto | 43.53% |
| Tasa de equilibrio exigida (R:R 1.75) | 36.36% |
| Profit factor | 1.15 |
| Ganancia media | 7.00% |
| Pérdida media | -4.61% |
| Esperanza por operación | 0.44% |
| Días medios en cartera | 18.1 |
| Mejor operación | 40.43% |
| Peor operación | -14.95% |


**Intervalo de confianza del CAGR (bootstrap de retornos diarios, 2000 muestras):** p05 -1.08% · mediana 2.19% · p95 5.65%. Probabilidad de CAGR negativo: 14.05%.


## 4. Curva de capital y drawdown

![Curva de capital](backtest_equity_pit.png)


![Monte Carlo](backtest_montecarlo_pit.png)


**Rentabilidad por año natural:**

| Año | Estrategia | SPY |
|---|---|---|
| 2015 | -0.72% | 1.29% |
| 2016 | 1.00% | 12.00% |
| 2017 | 7.21% | 21.71% |
| 2018 | -8.63% | -4.57% |
| 2019 | 12.46% | 31.22% |
| 2020 | 16.80% | 18.33% |
| 2021 | 5.23% | 28.73% |
| 2022 | -17.56% | -18.18% |
| 2023 | 2.82% | 26.18% |
| 2024 | 7.44% | 24.89% |
| 2025 | 1.77% | 18.60% |


## 5. Atribución


### Por rating de entrada

| rating | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| COMPRA | 672 | 0.4271 | 0.0044 | 15109.4636 | 17.5640 |
| COMPRA FUERTE | 256 | 0.4570 | 0.0046 | 10718.5492 | 19.5547 |


### Por sector

| sector | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| Technology | 440 | 0.4636 | 0.0097 | 25115.9928 | 18.0227 |
| Communication Services | 101 | 0.4554 | 0.0077 | 6930.5498 | 20.4059 |
| Consumer Cyclical | 80 | 0.4375 | 0.0047 | 3410.0361 | 16.4125 |
| Financial Services | 126 | 0.4206 | 0.0000 | 913.0522 | 16.9286 |
| Industrials | 41 | 0.3902 | 0.0023 | 565.1977 | 20.3415 |
| Consumer Defensive | 20 | 0.3500 | -0.0056 | -710.0794 | 17.1000 |
| Energy | 17 | 0.2941 | -0.0155 | -1564.7765 | 13.2941 |
| Healthcare | 103 | 0.3689 | -0.0097 | -8831.9599 | 19.1262 |


### Por motivo de salida

| exit_reason | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| take_profit | 341 | 0.9971 | 0.0763 | 188277.4421 | 20.8475 |
| downgrade_MANTENER | 86 | 0.5698 | 0.0127 | 6606.3672 | 35.6047 |
| downgrade_VENTA | 13 | 0.6923 | 0.0267 | 2085.0276 | 30.1538 |
| fin_backtest | 2 | 0.5000 | -0.0023 | -30.2161 | 43.0000 |
| downgrade_VENTA FUERTE | 13 | 0.3846 | -0.0119 | -1193.4257 | 37.4615 |
| stop_loss | 473 | 0.0000 | -0.0490 | -169917.1823 | 11.9937 |


### Por año de salida

| year | n | hit_rate | avg_ret | total_pnl | avg_holding_days |
|---|---|---|---|---|---|
| 2015 | 51 | 0.3333 | -0.0019 | -1038.9030 | 14.3529 |
| 2016 | 67 | 0.4328 | 0.0036 | 845.0204 | 20.9104 |
| 2017 | 86 | 0.5814 | 0.0142 | 7730.3842 | 24.1860 |
| 2018 | 95 | 0.3263 | -0.0128 | -9345.1338 | 14.0211 |
| 2019 | 115 | 0.5217 | 0.0152 | 11374.4836 | 19.9304 |
| 2020 | 62 | 0.6613 | 0.0422 | 18104.5874 | 23.4194 |
| 2021 | 84 | 0.5238 | 0.0109 | 8097.0554 | 17.6071 |
| 2022 | 79 | 0.2152 | -0.0392 | -23566.7944 | 14.7975 |
| 2023 | 94 | 0.3830 | 0.0037 | 2292.7613 | 17.7021 |
| 2024 | 114 | 0.4123 | 0.0082 | 9150.0642 | 15.9825 |
| 2025 | 81 | 0.3951 | 0.0064 | 2184.4876 | 17.1111 |


### Event study: rendimiento futuro por rating

Independiente del gestor de cartera: mide si el rating por sí solo anticipa el movimiento posterior del precio. Es la prueba más limpia de poder predictivo.

| rating | n | fwd_1m_media | fwd_1m_mediana | fwd_1m_pct_positivo | fwd_1m_tstat | fwd_3m_media | fwd_3m_mediana | fwd_3m_pct_positivo | fwd_3m_tstat | fwd_6m_media | fwd_6m_mediana | fwd_6m_pct_positivo | fwd_6m_tstat | fwd_12m_media | fwd_12m_mediana | fwd_12m_pct_positivo | fwd_12m_tstat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| COMPRA | 755 | 0.0117 | 0.0086 | 0.5523 | 3.7322 | 0.0451 | 0.0327 | 0.6066 | 7.7423 | 0.0978 | 0.0715 | 0.6702 | 11.0705 | 0.2375 | 0.1731 | 0.7364 | 15.1490 |
| COMPRA FUERTE | 295 | 0.0101 | 0.0073 | 0.5593 | 2.3302 | 0.0441 | 0.0443 | 0.6373 | 5.4297 | 0.0961 | 0.0816 | 0.7051 | 7.9932 | 0.2102 | 0.1886 | 0.7525 | 10.1929 |
| MANTENER | 848 | 0.0201 | 0.0206 | 0.6167 | 6.9469 | 0.0532 | 0.0459 | 0.6521 | 10.8473 | 0.1129 | 0.0968 | 0.7005 | 14.0950 | 0.2111 | 0.1818 | 0.7465 | 16.0408 |
| VENTA | 3259 | 0.0139 | 0.0122 | 0.5775 | 10.4898 | 0.0429 | 0.0346 | 0.6244 | 18.5779 | 0.0855 | 0.0668 | 0.6809 | 25.0771 | 0.1751 | 0.1292 | 0.7383 | 32.5033 |
| VENTA FUERTE | 420 | 0.0280 | 0.0196 | 0.5833 | 5.2364 | 0.0741 | 0.0489 | 0.6310 | 7.3024 | 0.1545 | 0.1142 | 0.6690 | 9.3027 | 0.3506 | 0.2706 | 0.7429 | 12.6300 |


## 6. Robustez por subperiodo

| Subperiodo | Retorno estrategia | Retorno SPY | Sharpe | Máx. drawdown |
|---|---|---|---|---|
| Pre-COVID 2015-2019 | 0.1046 | 0.7289 | 0.3634 | -0.1153 |
| Crash COVID 2020-02→2020-04 | 0.0388 | -0.0985 | 3.1371 | -0.0092 |
| Recuperación 2020-2021 | 0.1574 | 0.7236 | 1.2059 | -0.0494 |
| Bajista 2022 | -0.1815 | -0.1865 | -2.3465 | -0.2054 |
| Post-2023 | 0.1256 | 0.8767 | 0.6600 | -0.0640 |


## 7. Sensibilidad a costes de transacción

| Nivel de coste | CAGR | Sharpe | Máx. drawdown | Capital final |
|---|---|---|---|---|
| 0 bps ida y vuelta | 0.0320 | 0.5135 | -0.2182 | 141449.9243 |
| 5 bps ida y vuelta | 0.0265 | 0.4302 | -0.2220 | 133246.5737 |
| 10 bps ida y vuelta | 0.0211 | 0.3512 | -0.2257 | 125828.0128 |
| 25 bps ida y vuelta | 0.0044 | 0.0991 | -0.2402 | 104911.8303 |


## 8. Limitaciones y sesgos residuales

Esta sección no se suaviza. Cada punto es una razón concreta por la que el resultado de arriba podría no repetirse fuera de muestra.

1. **La liquidez ociosa no renta nada, y es la mayor parte de la cartera.** La exposición bruta media es del 27.8%, así que un 72% del capital permanece en efectivo al 0%. Remunerarlo a letras del Tesoro (~2% medio en 2015-2025) añadiría del orden de 1.4% anual al resultado. La conclusión no cambia, pero la cifra publicada es algo más pesimista de lo que sería con una gestión de tesorería realista.
2. **El sistema no define qué hacer con el efectivo sobrante.** Emite pesos por posición (8-10% / 4-7%) pero nunca dice cuántas posiciones abrir ni cómo invertir el resto. La exposición del 28% es una consecuencia emergente de cuántas señales de compra aparecen, no una decisión de diseño. Buena parte de la diferencia frente al índice es simplemente no estar invertido.
3. **Divergencia de definición fundamental.** Producción lee métricas TTM de `yfinance.info`; el backtest usa cifras ANUALES (10-K) point-in-time de SEC EDGAR, porque el TTM histórico de yfinance no es recuperable retroactivamente. El gatekeeper se evalúa por tanto con una ventana contable distinta a la de producción: los ratings del backtest son fieles a la *lógica* del sistema, no necesariamente idénticos a los que habría emitido en directo.
4. **Sesgo de supervivencia.** El universo son 50 valores seleccionados hoy por su relevancia actual. Las empresas que quebraron o fueron excluidas nunca entran en la muestra, lo que infla el resultado en una magnitud no cuantificada aquí (la literatura sitúa el efecto entre 1 y 4 puntos de CAGR según periodo y universo).
5. **Deuda/Capital ausente se trata como 0.0.** Se replica el comportamiento de producción (`info.get("debtToEquity", 0.0)`), lo que hace que el filtro de apalancamiento se salte silenciosamente cuando el dato falta en EDGAR, en lugar de rechazar el valor.
6. **Finnhub ausente en el backtest.** No hay histórico point-in-time gratuito, así que el `confidence_score` de la reconciliación difiere del de producción. Verificado en la Fase 1 que no altera ninguna decisión (solo añade texto), pero es una divergencia real.
7. **Sin datos intradía.** Cuando stop y objetivo se tocan en la misma sesión se asume que saltó el stop. Es conservador, pero desconoce el orden real y sesga el resultado a la baja en una cuantía desconocida.
8. **Costes estimados, no reales.** Comisión y slippage son parámetros fijos en puntos básicos. No modelan impacto de mercado, y para tamaños grandes de cartera el deslizamiento real crecería con el volumen.
9. **Cobertura incompleta de señales.** Descartes por falta de datos: {'sin_fundamentales': 979}. Los tickers sin fundamentales publicados en una fecha simplemente no generan señal, lo que reduce el universo efectivo en los primeros años del estudio.
10. **Contrastes múltiples.** Se han evaluado varios regímenes, frecuencias y niveles de coste sobre el mismo periodo histórico. El p-valor mostrado no está corregido por multiplicidad: interprétese como orientativo, no como una prueba formal.

## 9. Próximos pasos para reforzar la validez

1. PRIORIDAD 1 — investigar la ordenación del rating. Antes de tocar stops, sizing o costes, comprobar si el event study mantiene el orden invertido (VENTA FUERTE rindiendo más que COMPRA FUERTE) en otros universos y periodos. Si se confirma, el problema está en la señal y ningún ajuste de gestión de cartera lo arreglará.
2. Contrastar la hipótesis más probable de esa inversión: el gatekeeper exige crecimiento de ingresos ≥5% y margen neto ≥3%, lo que descarta sistemáticamente los valores de estilo *value* y las recuperaciones cíclicas, que son justamente los que más rindieron en varios tramos del periodo. Es un sesgo de estilo, no un fallo de implementación.
3. Medir por separado el efecto del stop de 2·ATR. Con más de la mitad de las salidas disparadas por stop y una tenencia media inferior a 20 sesiones, el sistema puede estar cortando posiciones ganadoras antes de que maduren. Ejecutar una variante sin stop y otra con stop por tiempo para aislarlo.
4. Contratar o reconstruir las composiciones históricas del índice (CRSP, Norgate, Sharadar) para eliminar el sesgo de supervivencia, que hoy es el sesgo residual dominante.
5. Sustituir los fundamentales anuales por TTM point-in-time encadenando los cuatro trimestres XBRL disponibles en cada fecha, para acercar el backtest a la definición exacta que usa producción.
6. Validación walk-forward: fijar los umbrales del gatekeeper con datos hasta 2019 y evaluar 2020-2025 como out-of-sample estricto, sin volver a mirar el periodo de test.
7. Añadir datos intradía (o al menos barras horarias) para resolver correctamente el orden entre stop y objetivo dentro de la misma sesión.
8. Corregir `_extract_recent_fact()` en `src/data/sec_edgar.py` para que ordene por `filed` y no por `end`: hoy es un look-ahead latente que también afecta a producción en tiempo real.
9. Ampliar el universo más allá de las megacaps estadounidenses y comprobar si el resultado sobrevive en small caps, donde los costes y el slippage son materialmente mayores.
10. Ejecutar paper trading en directo durante 6-12 meses y comparar las señales reales con las que el replay produce para esas mismas fechas: es la única validación no retrospectiva.

---

### Reproducibilidad

```
python backtest_cli.py --start 2015-01-01 --end 2025-12-31 --rebalance monthly --regime pit --costs-bps 10.0 --capital 100000 --mc-runs 1000
```

Configuración: {"tickers": 50, "start": "2015-01-01", "end": "2025-12-31", "rebalance": "monthly", "costs_bps_round_trip": 10.0, "capital": 100000.0, "max_holding_days": null, "mc_runs": 1000, "benchmark": "SPY"}


Señales descartadas por falta de datos: `{"sin_fundamentales": 979}`
