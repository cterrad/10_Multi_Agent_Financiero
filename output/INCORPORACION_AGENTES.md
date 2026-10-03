# Incorporación de agentes entre repositorios — precisión del punto de entrada

> Encargo: `prompts/entry_precision_agents_prompt.md`. Sistema anfitrión:
> `10_Multi_Agent_Financiero`. Repositorios fuente: `02-trading-liquidez-prj`,
> `03-trading-strategies-prj`, `06-trading-search-strategies-prj`,
> `07-trading-falsa-ruptura-strategies-prj`.
>
> Este documento recorre las Fases 0, 2, 3 y 4. El catálogo de fuentes de datos
> (Fase 1) vive aparte, en `output/FUENTES_DATOS.md`, porque es una demanda
> permanente del proyecto y no un anexo de este encargo.

## Decisiones de arranque, declaradas

| Decisión | Valor | Motivo |
|---|---|---|
| Dependencias nuevas | `scipy` 1.15.3 + `scikit-learn` 1.7.2 | Ver §0.5. Sin `torch`, sin `xgboost`, sin `hmmlearn`, sin `statsmodels`. |
| Transformer / embeddings | **Descartado** | Instrucción explícita del usuario. Además `06/artifacts/transformer/` está VACÍO y los embeddings archivados son parquet de barras de 15 minutos: no son reconstruibles point-in-time para un sistema de barra diaria. |
| Modelos ML | `sklearn` (`HistGradientBoostingClassifier`, `LogisticRegression`) | Misma familia de algoritmo que el XGBoost de 03/06/07, sin binario externo. |
| Clave FRED | Presente en `.env` (32 caracteres, verificada contra la API) | Habilita ALFRED, que es la única vía gratuita a una serie macro con *vintage*. |
| Línea base del backtest | CAGR 3.95% · Sharpe 0.68 · DD −13.80% · 563 ops · acierto 44.6% · PF 1.38 · expectativa +1.23% · percentil vs. aleatorio 7.4 | Reproducida `--offline` en 4 m 40 s antes de tocar nada. |
| Suite determinista | 376 pasan, 1 omitida, 4.77 s | Verde antes de empezar. |

---

# FASE 0 — LECTURA PROFUNDA

## 0.1 Qué hace hoy el sistema anfitrión con el precio de entrada, verificado contra el código

`PositioningAnalystAgent.decidir()` ([posicionamiento.py:100-186](src/agents/posicionamiento.py#L100-L186))
cruza tres señales y llama a `ajustar_precio_entrada`. La regla vive en
[`_ajustar_entrada`](src/tools/decision.py#L486-L608) y sus cuatro pasos son:

1. **Confluencia** sobre `{macro, opciones, técnico}`; con menos de dos
   componentes devuelve `ajuste_entrada_pct = None`.
2. **Sobreextensión**: no cambia el signo, prohíbe perseguir.
3. **Nivel**: el candidato **más alto por debajo del precio**, elegido entre
   `SOPORTE_OI`, `GAMMA_FLIP` y `MAX_PAIN` — *los tres salen de la cadena de
   opciones*.
4. **Ajuste** acotado a `AJUSTE_MAXIMO_ATR · ATR/precio`, con `min(0.0, ajuste)`
   como blindaje explícito.

**Las tres debilidades del encargo, confirmadas línea a línea:**

| Debilidad | Confirmación |
|---|---|
| No hay modelo de si el nivel aguanta | [decision.py:586](src/tools/decision.py#L586) elige `max(candidatos)` y [decision.py:588-591](src/tools/decision.py#L588-L591) aplica el factor. No existe ninguna estimación de probabilidad en toda la ruta. `ESPERAR_RETROCESO` es una orden límite ciega. |
| No hay modelo de si la ruptura aguanta | `PERSEGUIR` sale de `confluencia >= 1.0 and not sobreextendido` ([decision.py:557-558](src/tools/decision.py#L557-L558)). El único freno es la bandera `sobreextendido`. |
| El backtest no puede medir nada de esto | [replay.py:714-722](src/backtest/replay.py#L714-L722) declara `options_data` ausente. Sin cadena no hay candidatos, y [decision.py:583](src/tools/decision.py#L583) devuelve `nivel_origen: NO_APLICABLE` con `ajuste_entrada_pct: None`. |

**Y una cuarta, que el encargo no nombra y es la más grave de todas.** Aunque
existiera un histórico de cadenas, **el motor no podría ejecutar la entrada
ajustada**. `Signal` ([replay.py:526-563](src/backtest/replay.py#L526-L563)) **no
transporta `precio_entrada_objetivo`**: arrastra `entrada_clasificacion` y
`sesgo_macro` para atribución, y nada más. `build_orders` emite órdenes con
`notional` ([engine.py:389-395](src/backtest/engine.py#L389-L395)) y
`process_open` rellena **a la apertura de t+1** ([engine.py:194-199](src/backtest/engine.py#L194-L199)).
No existe el concepto de orden limitada. Es `NEXT_STEPS` #1 y es un
**prerrequisito estricto**: cerrar la brecha de datos sin cerrar la de ejecución
no mediría nada.

## 0.2 Inventario verificado, repositorio a repositorio

Leyenda: **LIFT** = copiar la función pura detrás de una tool · **REFIT** =
rederivar la técnica sobre datos del anfitrión · **VALIDATE-ONLY** = usar en el
estudio, nunca en la decisión · **DISCARD**.

### Repo 02 — `02-trading-liquidez-prj` (Aura Quantitative Command Center)

| Ruta real | Firma verificada | Qué calcula | Frecuencia | Dependencia de datos | Veredicto |
|---|---|---|---|---|---|
| `backend/app/services/financial_logic.py` | `FEDService.compute_reserve_pressure(reserve_balances_bn: float, on_rrp_bn: float) -> float` | `on_rrp / reservas`. Una división. | Semanal | FRED `WRESBAL`, `RRPONTTLD` | **REFIT** — la fórmula es trivial; lo que hay que rehacer entera es la disciplina de *vintage*. |
| ídem | `NBFIService.compute_risk_level(exposure_bn: float, interconnectedness_ratio: float = 0.5) -> str` | Cuatro cortes → `LOW/MEDIUM/HIGH/CRITICAL` | Trimestral | ECB OFI | **DISCARD** — trimestral, revisada, sin *vintage*, y el umbral de 1 T$ es absoluto: no es comparable a lo largo de once años de crecimiento nominal. |
| ídem | `BISService.adjust_for_series_break(value: float, break_factor: float = 1.0) -> float` | `value * factor` | — | — | **DISCARD** — es una multiplicación con dos validaciones. Copiarla no aporta nada; el problema real (detectar la ruptura de serie) no lo resuelve. |
| `backend/app/gateways/fed_gateway.py` | `_FRED_SERIES = {WALCL, RRPONTTLD, WTREGEN, WRESBAL}` | Descarga las cuatro series | Semanal/diaria | FRED API | **DISCARD como código**, **conservar la lista de series**. Pide `sort_order=desc&limit=N`, es decir **el último *vintage***: es exactamente el look-ahead que el encargo advierte. Y peor: [fed_gateway.py:54](../09_SDD_Copilot/02-trading-liquidez-prj/backend/app/gateways/fed_gateway.py) cae a **datos inventados** ("stub") cuando no hay clave. Eso, en este proyecto, es la violación de «ausencia ≠ cero» en su forma más pura. |
| `backend/app/gateways/llm_gateway.py`, `services/agent/` | — | Panel de comentario LLM | — | — | **DISCARD** — viola la invariante 1 al contacto. |
| `backend/app/api/`, `db/`, `alembic/`, `frontend/` | — | FastAPI, Postgres, Streamlit | — | — | **DISCARD** — infraestructura. |

**Lectura honesta del repo 02: no hay código que valga la pena levantar.** Sus
tres funciones puras suman cinco líneas de aritmética. Lo que aporta es una
**idea** —un régimen de estrés sistémico común a todo el lote, estructuralmente
análogo al dosier COT— y esa idea vale exactamente lo que valga la
reconstrucción *vintage* de sus series, que es trabajo de la Fase 1 y no de este
repositorio.

### Repo 03 — `03-trading-strategies-prj` (plataforma LdP de 7 etapas)

| Ruta real | Firma verificada | Qué calcula | Frec. | Dependencias | Veredicto |
|---|---|---|---|---|---|
| `src/risk/portfolio.py` | `denoise_cov(cov: pd.DataFrame, q: float, bandwidth: float = 0.01) -> pd.DataFrame` | Denoising espectral Marchenko-Pastur: sustituye los autovalores de ruido por su media y renormaliza la diagonal | Cualquiera | `numpy` | **LIFT — ruta de decisión.** Solo numpy. `PortfolioConstructor` penaliza hoy por correlación media sobre una matriz cruda; esto es una mejora estricta **sin ningún dato nuevo**. |
| ídem | `corr_to_cov(corr, std) -> pd.DataFrame` | Reconstruye covarianza | — | `numpy` | **LIFT** — auxiliar de la anterior. |
| ídem | `hrp_weights(cov, corr) -> pd.Series` | Hierarchical Risk Parity | — | `scipy.cluster` | **DISCARD.** Sustituiría la capa de cartera entera por otra asignación; el encargo pide precisión de entrada, no reemplazar `construccion.py`. |
| ídem | `nco_weights(cov, mu, max_clusters, random_state)` | Nested Clustered Optimization | — | `sklearn.KMeans` | **DISCARD** — mismo motivo, y además KMeans mete dependencia de semilla en una variable de decisión. |
| `src/risk/sizing.py` | `drawdown_guard(current_equity, peak_equity, max_drawdown_pct) -> None` (lanza `RiskCheckError`) | Corta si el drawdown supera el límite | Diaria | — | **REFIT.** El anfitrión no tiene equivalente. Pero lanzar excepción no encaja: aquí sería un factor que **solo baja** el peso, o un veto. |
| ídem | `position_size(equity, signal_confidence, max_position_pct, price)` | `equity · pct · confianza / precio` | — | — | **DISCARD.** El dimensionamiento por presupuesto de riesgo del anfitrión (`peso = riesgo/distancia_al_stop × factor_vol`) es estrictamente mejor: éste ignora la distancia al stop. |
| `src/labeling/triple_barrier.py` | `get_events`, `get_bins` | Triple barrera LdP canónica | Cualquiera | `pandas` | **REFIT** — la versión de 07 es mejor punto de partida (niveles causales explícitos). |
| `src/labeling/volatility.py` | `daily_vol(close, span=20, lookback_days=1)`, `ewm_vol(returns, span=20)` | Volatilidad EWM **con `.shift(1)`** | Diaria | `pandas` | **LIFT.** El `.shift(1)` incondicional es justo la disciplina del anfitrión. |
| `src/labeling/meta_labeling.py` | `build_meta_labels(events: pd.DataFrame, side: pd.Series) -> pd.DataFrame`; `train_meta_model(X, y, sample_weight, cv, ...)` | Meta-etiquetado: el primario da el LADO, el meta da SI apostar | Cualquiera | **`xgboost`** | **REFIT con sklearn.** `build_meta_labels` es pura (pandas). `train_meta_model` hay que rehacerla: importa `XGBClassifier` y además **entrena sobre todo `X` tras usar el CV solo para "validar que el split funciona"** — hay un `break` en el primer fold. Eso no es validación. |
| `src/cv/purged_kfold.py` | `PurgedKFold(n_splits: int, t1: pd.Series, pct_embargo: float = 0.0)` | K-fold purgado por solapamiento de etiquetas | — | `sklearn.KFold` | **VALIDATE-ONLY.** |
| `src/cv/cpcv.py` | `CombinatorialPurgedCV(...)`, `cpcv_paths(...)` | Validación combinatoria purgada | — | `numpy` | **VALIDATE-ONLY.** |
| `src/sampling/bootstrap.py` | `get_ind_matrix`, `num_co_events`, `get_avg_uniqueness`, `seq_bootstrap`, `sample_weights` | Unicidad y bootstrap secuencial | — | `numpy/pandas` | **VALIDATE-ONLY** — duplicado de 06; se toma **uno solo**. |
| `src/backtesting/metrics.py` | `probabilistic_sharpe_ratio(returns, sr_benchmark=0.0)`, `deflated_sharpe_ratio(...)`, `sortino_ratio`, `avg_drawdown`, `max_drawdown_duration` | PSR/DSR y drawdown | — | `scipy` | **VALIDATE-ONLY** — duplicado de 06; se toma el de 06 (expone `expected_max_sharpe` por separado, que es lo que la Fase 4 necesita nombrar). El anfitrión ya tiene `sortino`, `max_drawdown` y `max_drawdown_duration_days` propios: **no se duplican**. |
| `src/features/importance.py` | `feat_imp_mdi`, `feat_imp_mda`, `feat_imp_sfi` | Importancia de variables | — | `sklearn` | **VALIDATE-ONLY.** |
| `src/data/ffd.py` | `ffd_weights(d, size, threshold)`, `frac_diff_ffd(...)`, `find_min_ffd(...)` | Diferenciación fraccional de ventana fija | Cualquiera | `numpy` / `statsmodels` (ADF) | **REFIT parcial** — `frac_diff_ffd` es numpy puro; `find_min_ffd` necesita ADF → o se fija `d` a mano o se descarta. |
| `src/observability/drift.py` | `population_stability_index(...)`, `ks_statistic(...)` | Deriva de variables (PSI/KS) | — | `scipy` | **VALIDATE-ONLY.** |
| `src/volatility/hmm_filter.py` | — | Filtro de régimen HMM | — | **`hmmlearn`** | **DISCARD** — dependencia. |
| `src/models/patch_tst.py`, `src/strategies/*transformer*`, `*ppo*`, `*gnn*` | — | Modelos profundos | — | **`torch`** | **DISCARD** — dependencia + instrucción del usuario. |
| `src/live/`, `src/api/`, `ui/`, `src/execution/*broker*` | — | Subsistema en vivo | — | — | **DISCARD** — instrucción explícita del encargo. |

### Repo 06 — `06-trading-search-strategies-prj` (ORB, Transformer + XGBoost)

| Ruta real | Firma verificada | Qué calcula | Frec. | Dependencias | Veredicto |
|---|---|---|---|---|---|
| `src/backtest/metrics.py` | `probabilistic_sharpe_ratio(returns: np.ndarray, benchmark_sr: float = 0.0) -> float`; `expected_max_sharpe(sharpe_std: float, n_trials: int) -> float`; `deflated_sharpe_ratio(returns, n_trials, sharpe_std=None, trial_sharpes=None) -> float`; más `observed_sharpe` y `sharpe_ratio` | PSR (LdP 2012) y DSR (LdP 2014) con la aproximación de valor extremo | — | `numpy`, `scipy.stats` | **LIFT — VALIDATE-ONLY. Es lo que la Fase 4 está OBLIGADA a usar.** El anfitrión **no tiene PSR ni DSR**: es un hueco real de su capa de métricas. |
| `src/validation/purged_cv.py` | `PurgedGroupTimeSeriesSplit(n_splits: int = 5, embargo_days: int = 2).split(session_dates: pd.Series)` | K bloques cronológicos por fecha de sesión, con purga y embargo | — | `numpy/pandas` | **LIFT — VALIDATE-ONLY.** Agrupa por fecha, que es exactamente la forma del rebalanceo del anfitrión. Se prefiere a `PurgedKFold` de 03 por eso. |
| `src/validation/sample_weights.py` | `count_concurrency(bar_ts, events)`; `average_uniqueness(bar_ts, events, concurrency=None)`; `indicator_matrix(...)`; `sequential_bootstrap(ind_mat, n=None, random_state=None)`; `compute_sample_weights(events) -> np.ndarray` | Unicidad media y pesos `abs(ret)·unicidad` normalizados a media 1 | — | `numpy/pandas` | **LIFT — VALIDATE-ONLY.** Vectorizado con array de diferencias; mejor que el de 03. |
| `src/classifier/meta_labeling.py` | `primary_signals(labels)`; `meta_report(...)`; `best_threshold(report, metric='f1', min_coverage=0.05)` | Barrido de umbral de probabilidad con cobertura mínima | — | `sklearn` | **REFIT.** `best_threshold` con `min_coverage` es la pieza que impide elegir un umbral que solo dispara tres veces. |
| `src/classifier/importance.py` | `mean_decrease_accuracy(...)`, `single_feature_importance(...)` | MDA / SFI sobre CV purgado | — | `sklearn` | **VALIDATE-ONLY.** |
| `src/regime/detector.py` | `_hmm_regimes(ret, train_mask, n_states, seed, search_reps)`; variante `sma` | Régimen bear/range/bull. **La nota de causalidad es lo valioso**: ajusta en TRAIN y aplica el *filtro* de Hamilton, nunca el suavizador ni Viterbi, que condicionan sobre retornos futuros | Diaria | **`statsmodels`** (HMM) / `pandas` (SMA) | **REFIT solo la variante SMA.** La disciplina «filtro, no suavizador» se adopta como principio general; el HMM se descarta por dependencia. |
| `src/target/orb_labeler.py` | `label_orb(...)` | Triple barrera vectorizada sobre el rango de apertura | **Intradía** | `pandas` | **DISCARD para la ruta de decisión** (frecuencia); la *técnica* entra vía 07. |
| `src/features/frac_diff.py` | `ffd_weights(d, thres, max_width)`, `frac_diff_ffd(series, d, thres)`, `min_ffd_d(...)`, `add_frac_diff_features(...)` | Diferenciación fraccional | Cualquiera | `numpy/pandas` | **REFIT** — candidato a *feature*; ver Loop B. |
| `src/features/ta_extended.py` | `add_ta_extended_features(...)` con `_macd_frame`, `_stoch_frame`, `_adx_frame`, `_bollinger_frame`, `_donchian_frame`, `_historical_vol`, `_obv_norm` | Batería de indicadores | Cualquiera | `pandas` | **DISCARD mayoritario** — el anfitrión ya calcula RSI, MACD, Bollinger, medias, ATR y volatilidad en `_add_technical_indicators`. **Solo `_donchian_frame` es nuevo** y es directamente relevante: el canal alto/bajo *son* niveles de ruptura. |
| `src/features/fourier_features.py`, `lags.py`, `selection.py` | — | Fourier, retardos, selección | — | `numpy/sklearn` | **DISCARD** — Fourier sobre 132 rebalanceos es sobreajuste con formato de espectro. |
| `src/allocation/hrp.py`, `nco.py`, `_linalg.py` | `get_hrp_weights`, `get_nco_weights` | HRP/NCO | — | `scipy/sklearn` | **DISCARD** — duplicado de 03 y mismo motivo. |
| `src/transformer/` (`model.py`, `train.py`, `embeddings.py`, `windowing.py`, `dataset.py`) | — | Preentrenamiento SSL | — | **`torch`** | **DISCARD** — instrucción del usuario. Verificado: `artifacts/transformer/` está vacío; `artifacts/embeddings/interval=15 mins/` contiene 11 parquet de barras de 15 min. |
| `src/client/db/`, `src/ingestion/`, `src/db/` | — | SQL Server / repositorio | — | — | **DISCARD.** |

### Repo 07 — `07-trading-falsa-ruptura-strategies-prj` (Bear Trap)

**Es el que más se acerca a la misión**, y la coincidencia es literal: su evento
es *«el precio ha roto por debajo del soporte de la sesión anterior — ¿se
recupera?»*, que es exactamente la pregunta que el anfitrión no sabe responder
cada vez que emite `ESPERAR_RETROCESO`.

| Ruta real | Firma verificada | Qué calcula | Frec. | Dependencias | Veredicto |
|---|---|---|---|---|---|
| `src/target/triple_barrier.py` | `build_labels(df: pd.DataFrame, tb_cfg: dict) -> pd.DataFrame`; `_causal_levels(df, atr_days) -> pd.DataFrame`; `_label_session(...)`; `_resolve(first_up, first_dn) -> tuple[int, str]` | Soporte = **mínimo de la sesión anterior** (`shift(1)`); ATR diario causal = media móvil del rango de sesiones **anteriores**; ruptura = primera barra que perfora; TP = `soporte + tp·ATR`, SL = `mínimo_de_la_señal − sl·ATR`, vertical = `max_holding_bars` | **Intradía dentro de la sesión** | `pandas` | **REFIT a granularidad diaria.** La construcción de niveles ya es estrictamente causal —`shift(1)` explícito en las dos series— y es el patrón exacto que el anfitrión exige. |
| `src/macro/regime.py` | `compute_regime(macro_df: pd.DataFrame, session_dates: pd.Series, macro_cfg: dict) -> pd.DataFrame` → `[session_date, vix_level, vix_z, macro_gate]`; puerta = `vix_level <= 35 AND vix_z <= 2` | Filtro anti-cuchillo-cayendo: en pánico sistémico, lo que parece trampa suele ser capitulación real | Diaria | `pandas` + **serie VIX** | **REFIT.** Es la pieza conceptualmente más limpia de los cuatro repos: una puerta binaria que **solo puede cerrar**, nunca abrir de más. Encaja exactamente en la familia de `aplicar_vetos`. |
| `src/features/liquidity.py` | `add_liquidity(df, week_sessions=5, round_step=1.0) -> pd.DataFrame` → `dist_prior_day_low`, `dist_prior_week_low`, `dist_round_number` | Distancia relativa a los charcos de liquidez, **todo con `shift(1)`** | Diaria | `pandas` | **LIFT (adaptado).** `numpy/pandas` puro, causal por construcción, y produce **niveles de precio concretos** — que es justo lo que hoy solo sabe dar la cadena de opciones. |
| `src/execution/v_reversal.py` | `ExecConfig(stop_buffer_atr=0.1, proba_threshold=0.85, use_proba_gate=True, use_macro_gate=True)`; `generate_trades(features, labels, regime, proba, cfg)`; `_simulate(...)`; `_resolve_exit(forward, stop, target, entry_price)` | Máquina de 4 fases: ruptura → **divergencia (CVD)** → confirmación (el cierre recupera el soporte) → disparo | Intradía | `pandas` + **CVD (order flow)** | **REFIT PARCIAL.** La fase 2 depende de `cvd_velocity`, que exige tick/profundidad de IBKR: **no reconstruible**. Las fases 1, 3 y 4 sí: *no comprar la ruptura, comprar la recuperación confirmada*. Es una regla de entrada transplantable a barra diaria. |
| `src/features/orderflow.py` | `add_orderflow(...)`, `_order_book_imbalance(...)`, CVD | Desequilibrio de libro y volumen delta acumulado | Tick | **IBKR tick/depth** | **DISCARD para la ruta de decisión.** No existe en el anfitrión ni es reconstruible históricamente a coste cero. |
| `src/validation/purged_cv.py` | — | — | — | — | **DISCARD** — idéntico al de 06; se toma uno. |
| `src/sequence/` (`model.py`, `train.py`, `embeddings.py`) | — | Encoder LSTM SSL | — | **`torch`** | **DISCARD** — instrucción del usuario. |
| `src/ingestion/` (`ibkr_connector.py`, `yfinance_connector.py`, `factory.py`, `updater.py`), `src/storage/` | — | Lago DuckDB/Parquet | — | **`duckdb`** | **DISCARD** — infraestructura; el anfitrión ya tiene su caché. |
| `src/classifier/train.py`, `predict.py`, `prepare.py`, `feature_fusion.py` | — | XGBoost | — | **`xgboost`** | **REFIT con sklearn** si algún agente lo necesita. |

## 0.3 Brecha de frecuencia

El anfitrión opera **barra diaria** y rebalancea **mensualmente** (132 fechas en
once años, tenencia media ~33 sesiones). Tres de los cuatro repos son intradía.

| Candidato | Frecuencia original | Qué sobrevive a la traducción | Qué NO sobrevive |
|---|---|---|---|
| Triple barrera de 07 | Barras intradía dentro de una sesión; horizonte `max_holding_bars = 12` barras | **La estructura entera**: soporte causal, primera perforación, tres barreras, resolución por primer toque. Solo cambian las unidades. | Los horizontes. `12 barras de 15 min ≈ 3 horas` **no** se traduce a «12 sesiones»: hay que rederivar el horizonte desde la tenencia real del anfitrión (~33 sesiones) y desde el `horizonte_dias` que ya fija `ATR_AJUSTE_POR_ESTILO`. |
| Puerta de régimen VIX de 07 | Diaria (ya) | **Todo.** El VIX es una serie diaria y la ventana z de 60 sesiones es directamente aplicable. | Nada. Es el único candidato sin brecha de frecuencia. |
| `add_liquidity` de 07 | Sesión (ya causal entre sesiones) | **Todo**, sustituyendo «sesión» por «día» y ampliando las ventanas: mínimo del día anterior → mínimo de N sesiones; mínimo de la semana → mínimo de 21/63 sesiones. | El `round_step = 1.0` fijo: sobre valores de $30 y de $900 el número redondo no está a la misma distancia relativa. Hay que escalarlo con el precio. |
| Máquina V-Reversal de 07 | Intradía, resuelta dentro de la sesión | **La secuencia lógica** ruptura → confirmación → disparo, con el stop bajo el mínimo del tramo. | La **fase de divergencia (CVD)**, que es donde vive buena parte del valor original. Y que todo se resuelva el mismo día: a barra diaria la confirmación tarda sesiones y la posición queda expuesta de un cierre a la apertura siguiente. |
| ORB de 06 | Intradía por definición (rango de apertura) | **Nada del evento.** | Todo. Un rango de apertura no existe en barra diaria. |
| CVD / desequilibrio de libro de 07 | Tick / profundidad | **Nada.** | Todo. No hay proxy diario en lo que el anfitrión ingiere: el volumen diario de yfinance no separa compra agresiva de venta agresiva. |
| PSR/DSR, CV purgado, pesos por unicidad | Agnósticos | **Todo.** Operan sobre series de retornos y sobre pares `(t0, t1)`. | Nada. |
| `denoise_cov` | Agnóstico | **Todo.** Ya recibe una matriz de covarianza. | Nada. `q = T/N` con `CORRELACION_VENTANA_DIAS` observaciones y N candidatos del rebalanceo. |

**Regla aplicada:** todo lo que exige tick o profundidad es `DISCARD` para la
ruta de decisión, sin excepción, porque no hay proxy diario que el anfitrión ya
ingiera.

## 0.4 Lista de demanda de datos → Fase 1

Ningún candidato pasa a ser agente si la Fase 1 no cualifica su fuente.

| # | Serie que haría falta | Frec. | Profundidad | Para qué candidato | Qué se rompe sin ella |
|---|---|---|---|---|---|
| D1 | **VIX** (y si es posible su estructura temporal) | Diaria | 2014→ (un año de margen para la z de 60 sesiones) | Puerta de régimen macro de 07 | El agente no existe. No hay degradación parcial: sin VIX no hay puerta. |
| D2 | **Tipos y liquidez de la Fed** con *vintage* (`WALCL`, `WRESBAL`, `RRPONTSYD`, `WTREGEN`, `DGS10`, `DGS2`, `BAMLH0A0HYM2`) | Semanal/diaria | 2014→ | Régimen de estrés sistémico (idea del repo 02) | El agente macro se queda en el COT que ya existe. Es un resultado negativo aceptable. |
| D3 | **Ratio put/call de índice con histórico real** | Diaria | 2014→ | Sustituto medible del bloque de opciones por ticker | El bloque de opciones sigue sin medirse en el backtest. |
| D4 | **Volumen de venta en corto por ticker** | Diaria | 2014→ | Presión de oferta en el nivel; candidato a *feature* del modelo de nivel | El modelo pierde una variable; no lo invalida. |
| D5 | **Interés corto consolidado** con fecha de liquidación y publicación | Quincenal | 2014→ | ídem | ídem. |
| D6 | **Factores académicos diarios** (mercado, tamaño, valor, momentum, calidad) | Diaria | 2014→ | Alfa ajustada por factores en el informe | El estudio sigue midiendo alfa contra un único índice, que confunde selección con exposición a estilo. |
| D7 | **Composición histórica del índice con fechas de alta y baja** | Evento | 2014→ | Cerrar el sesgo de supervivencia | Sigue sesgando **todas** las cifras del informe, no una sola. |
| D8 | **Cadenas de opciones por ticker con histórico** | Diaria | 2014→ | Medir el bloque de opciones tal cual es hoy | Es de pago. Se da por perdido *a priori*; la Fase 1 debe confirmarlo y buscar el sustituto de índice (D3). |
| D9 | **Noticias con marca temporal de publicación real** | Evento | 2014→ | Subir la capa de noticias de asesora a decisión | Las noticias siguen siendo asesoras. |
| D10 | **Precios EOD no reajustados retroactivamente** | Diaria | 2014→ | Cuantificar el sesgo de reajuste de yfinance | No se puede acotar cuánto distorsiona el reajuste a los indicadores. |

## 0.5 Comprobación de dependencias

| Paquete | ¿Necesario? | Veredicto | Justificación |
|---|---|---|---|
| `scipy` | Sí | **INSTALADO** (1.15.3) | `norm.cdf`, `norm.ppf`, `skew`, `kurtosis` son irreemplazables sin reimplementar la normal inversa. PSR/DSR son requisito **explícito** de la Fase 4. |
| `scikit-learn` | Sí | **INSTALADO** (1.7.2) | `HistGradientBoostingClassifier` y `LogisticRegression` con `sample_weight`, y las métricas de clasificación. Sustituye a `xgboost` sin binario externo. |
| `xgboost` | No | **DESCARTADO** | `HistGradientBoosting` es el mismo algoritmo (GBM sobre histogramas). Una dependencia menos que versionar junto a un artefacto congelado. |
| `torch` | No | **DESCARTADO** | Instrucción del usuario. Además: `06/artifacts/transformer/` vacío y embeddings a 15 min → inservibles point-in-time a barra diaria. |
| `statsmodels` | No | **DESCARTADO** | Solo lo exigen el HMM de 06 y `find_min_ffd` de 03. La variante SMA del detector de régimen no lo necesita, y `d` de la diferenciación fraccional puede fijarse. |
| `hmmlearn` | No | **DESCARTADO** | Ídem, con menos justificación aún. |
| `duckdb`, `pyarrow` | No | **DESCARTADO** | El anfitrión ya cachea en JSON/CSV y `--offline` reproduce el estudio. Cambiar el almacenamiento no es el encargo. |

**Impacto en la suite:** `scipy` y `sklearn` solo se importan dentro de los
módulos que los usan. La suite determinista **debe seguir por debajo de los 5 s**;
se verifica en la Fase 6.

---

# FASE 3 — LOOP A: DÓNDE SE PIERDE LA PRECISIÓN DE ENTRADA

> Se presenta **antes** que el diseño de la Fase 2 aunque el encargo las numere
> al revés, porque el Loop A **refutó la premisa** sobre la que el diseño iba a
> construirse, y presentar un diseño que la medición ya ha desmentido sería
> deshonesto. El diseño de la Fase 2 que sigue es el posterior a la refutación.
>
> **Parada en la iteración 12 de 20**: las iteraciones 11 y 12 no añadieron
> ninguna entrada nueva al ledger.

## ITER 1/20 — El nivel de entrada tiene un solo proveedor

```
STATE      ingest -> quality -> {gatekeeper ‖ news} -> join -> [route]
           -> technical (momentum_score, sobreextendido, atr)
           -> posicionamiento (precio_entrada_objetivo, sesgo_macro_clasificacion)
           -> debate -> fund_manager (rating, peso_objetivo, stop, objetivo)
HYPOTHESIS El `nivel_referencia` del ajuste de entrada depende EXCLUSIVAMENTE de
           la cadena de opciones, de modo que la ausencia de cadena no degrada el
           bloque: lo anula.
EVIDENCE   src/tools/decision.py:575-582 — los tres candidatos son SOPORTE_OI,
           GAMMA_FLIP y MAX_PAIN. src/tools/decision.py:583-590 — sin candidatos
           devuelve nivel_origen NO_APLICABLE y ajuste None.
           src/agents/posicionamiento.py:252-263 — `vacio` pone los tres a None
           cuando `options_data` no esta disponible.
TEST       Ejecutar el replay y contar cuantas senales tienen
           entrada_clasificacion != NO_APLICABLE.
VERDICT    CONFIRMED
DELTA      Anadir candidatos de nivel derivados del OHLCV, que el sistema ya
           tiene point-in-time.
LEDGER     [A1: niveles de precio como segunda fuente de nivel]
```

## ITER 2/20 — El estudio no ejerce ni una vez el ajuste de entrada

```
STATE      idem
HYPOTHESIS En el backtest, `ajuste_entrada_pct` es None en el 100% de las senales.
EVIDENCE   src/backtest/replay.py:714-722 declara options_data ausente SIEMPRE.
           Con `disponible=False`, `_bloque_opciones` devuelve `vacio` y quedan
           dos componentes de confluencia (macro y tecnico), suficientes para
           clasificar pero sin ningun nivel al que ajustar.
TEST       Volcado de las 5 621 senales del regimen pit.
VERDICT    CONFIRMED
DELTA      Ninguno propio: es la consecuencia de A1.
LEDGER     [A1]
```

## ITER 3/20 — Aunque hubiera nivel, el motor no sabría ejecutarlo ★

```
STATE      idem
HYPOTHESIS El precio de entrada objetivo NO LLEGA al motor de cartera, asi que
           resolver la brecha de datos no bastaria para medir nada.
EVIDENCE   src/backtest/replay.py:526-563 — `Signal` arrastra `stop_loss`,
           `take_profit`, `entrada_clasificacion` y `sesgo_macro`, pero NO
           `precio_entrada_objetivo`.
           src/backtest/engine.py:389-395 — las ordenes de compra llevan
           `notional`, `stop`, `target`; no hay campo de limite.
           src/backtest/engine.py:194-199 — `process_open` rellena SIEMPRE a
           `float(bar["Open"])` de t+1.
TEST       Basta la lectura: no existe la ruta.
VERDICT    CONFIRMED
DELTA      Anadir `precio_entrada_objetivo` a `Signal`, un campo `limite` y una
           `vida_orden` a la orden, y una regla de relleno explicita en
           `process_open`. Es NEXT_STEPS #1 y es PRERREQUISITO de A1.
           *** Es una modificacion de la CAPA DE MEDICION, no de la senal, y por
           tanto RANQUEA POR ENCIMA de cualquier senal nueva. ***
LEDGER     [★ A2: ejecucion de orden limitada en engine.py, A1]
```

## ITER 4/20 — Los niveles derivados del precio existen y son point-in-time

```
STATE      idem
HYPOTHESIS El anfitrion ya posee, point-in-time y protegido por test, todo lo
           necesario para producir niveles de soporte sin cadena de opciones.
EVIDENCE   PriceStore.window() corta en as_of inclusive (data.py:230); la cache
           lleva OHLC completo (verificado: AAPL 2013-11-27 -> 2025-12-30,
           3 040 sesiones, columnas Open/High/Low/Close/Volume).
           `_extract_latest_tech_metrics` YA publica sma_50, sma_200 y bb_lower,
           que son tres candidatos de soporte disponibles hoy mismo, en
           produccion Y en el replay, sin tocar una sola linea de ingesta.
TEST       Construir los niveles sobre las 132 fechas de rebalanceo y medir.
VERDICT    CONFIRMED — 6 500 observaciones con nivel calculable.
DELTA      A1 se concreta: `src/tools/niveles.py` con minimos previos de N
           sesiones, numero redondo escalado, y reutilizacion de sma_50/sma_200/
           bb_lower que ya estan en el estado.
LEDGER     [A2, A1]
```

## ITER 5/20 — El número redondo degenera la elección de nivel

```
STATE      idem
HYPOTHESIS La regla "el candidato mas alto por debajo del precio" combinada con
           un candidato de numero redondo hace que el redondo gane casi siempre,
           porque por construccion es el mas cercano.
EVIDENCE   Medicion sobre 6 500 observaciones:
             origen del nivel elegido: numero_redondo 65.0% · minimo_10 14.1% ·
             sma_50 8.7% · bb_inferior 7.2% · sma_200 4.3% · minimo_21 0.4%
           Profundidad mediana con redondo: 0.95% (0.46 ATR).
           Profundidad mediana sin redondo: 2.52% (1.24 ATR).
TEST       Repetir la eleccion excluyendo el numero redondo.
VERDICT    CONFIRMED
DELTA      El numero redondo del repo 07 NO se incorpora como candidato de nivel.
           Un ajuste de entrada del 0.95% es ruido frente a un ATR.
LEDGER     [A2, A1']  (A1 revisada: solo niveles estructurales)
```

## ITER 6/20 — ¿Se rellena la orden? Sí, demasiado ★

```
STATE      idem
HYPOTHESIS Una orden limitada a un soporte estructural se rellena con la
           frecuencia suficiente para no destruir la exposicion.
EVIDENCE   Tasa de relleno del nivel elegido (todos los candidatos):
             5 sesiones 63.8% · 10 sesiones 71.1% · 21 sesiones 78.2%
           Sin numero redondo (niveles estructurales, mas profundos):
             10 sesiones 48.9%
TEST       Medido sobre 6 500 observaciones.
VERDICT    CONFIRMED, pero la lectura correcta es la contraria a la esperada:
           se rellena MUCHO justamente porque el nivel esta MUY CERCA.
DELTA      Ninguno. Prepara ITER 7.
LEDGER     [A2, A1']
```

## ITER 7/20 — ★★ LA REFUTACIÓN: entrar más barato no mejora el resultado

```
STATE      idem
HYPOTHESIS REGISTRADA ANTES DE MEDIR: si la orden limitada se rellena, la
           rentabilidad posterior sera mejor que entrando a mercado, porque el
           precio de entrada es menor y el precio de salida es el mismo.
EVIDENCE   Tres reglas, misma senal, mismo horizonte de 21 sesiones, orden con
           vida de 10 sesiones, 6 421 observaciones (niveles estructurales):

             regla                        opera   ret|opera   VALOR ESPERADO
             A. MERCADO (lo de hoy)      100.0%      +1.73%          +1.726%
             B. LIMITADA al nivel         48.9%      +1.76%          +0.860%
             C. CONFIRMADA (repo 07)      40.2%      +1.71%          +0.687%

           Con todos los candidatos (niveles someros), lo mismo:
             A 100.0% +1.71% -> +1.707% | B 71.1% +1.58% -> +1.127%
             C  58.6% +1.55% -> +0.909%

           Y por profundidad del nivel, A gana en LOS CUATRO tramos:
             (0.0,0.5] ATR n=1405 | A +1.41% | B +0.96% | C +0.97%
             (0.5,1.0] ATR n=1272 | A +2.42% | B +1.48% | C +1.16%
             (1.0,2.0] ATR n=1895 | A +1.88% | B +0.72% | C +0.39%
             (2.0,inf) ATR n=1849 | A +1.33% | B +0.50% | C +0.45%
TEST       Valor esperado POR SENAL, no rentabilidad condicionada al relleno: una
           regla que solo opera cuando el precio le viene encima tiene que pagar
           el coste de lo que deja pasar. Lo que B no rellena habria rendido
           +4.09% a mercado; lo que C no confirma, +2.49%.
VERDICT    *** REFUTED. Y de forma contundente. ***
           Lo notable no es que B y C pierdan por el coste de oportunidad —eso
           era previsible—, sino que `ret|opera` sea PRACTICAMENTE IDENTICO en
           las tres (+1.71% a +1.76%). Entrar entre un 1% y un 2.5% mas barato
           NO produce un resultado mejor. La seleccion adversa cancela
           exactamente la mejora de precio: las trayectorias que vuelven a tu
           nivel son las debiles.
DELTA      *** El ajuste de entrada, tal y como esta disenado, es en el mejor de
           los casos neutro y probablemente destructivo. ***
           No se propone ningun agente que profundice el retroceso. Se propone
           MEDIRLO, que es lo que hoy no se puede hacer, y dejar que el estudio
           lo diga con las metricas de aceptacion del proyecto.
LEDGER     [★★ A3: el ajuste de entrada es refutable y hay que medirlo, A2, A1']
```

## ITER 8/20 — Pero la DISTANCIA al soporte sí informa

```
STATE      idem
HYPOTHESIS REGISTRADA: si el nivel no sirve para esperar, quiza la distancia
           hasta el sirve para juzgar el momento.
EVIDENCE   Rentabilidad a mercado a 21 sesiones por tramo de distancia al
           soporte estructural mas cercano:
             (0.0,0.5] ATR  +1.41%   (pegado al soporte)
             (0.5,1.0] ATR  +2.42%   <- el mejor
             (1.0,2.0] ATR  +1.88%
             (2.0,inf) ATR  +1.33%   (soporte lejano)
           No es monotona: es una joroba. Ni pegado al soporte ni muy lejos.
TEST       Medido sobre 6 421 observaciones. Falta comprobar si sobrevive al
           subconjunto de senales de COMPRA y a la correccion por multiplicidad.
VERDICT    CONFIRMED como asociacion; PENDIENTE como senal utilizable.
DELTA      `distancia_soporte_atr` como variable descriptiva del informe y como
           candidata a bandera de sobreextension estructural — SIEMPRE en la
           familia de las que solo cierran, nunca abren.
LEDGER     [A3, A2, A1', A4: distancia al soporte como bandera]
```

## ITER 9/20 — Sustitución de fuente: el VIX convierte un hueco en medible

```
STATE      idem
HYPOTHESIS Una puerta de regimen basada en el VIX puede entrar en la ruta de
           decision HOY y ser medida sobre el estudio ENTERO, a diferencia de
           todo lo que depende de la cadena de opciones.
EVIDENCE   FUENTES_DATOS.md ITER 2/3/4: VIXCLS es PIT-NATIVE verificado
           (vintage 2018-03-01 devuelve el episodio de febrero de 2018 tal y como
           se conocia), cubre 1990-2026, no se revisa, y ALFRED impone por si
           solo el retardo de publicacion.
           El sistema NO tiene hoy ninguna medida de estres sistemico: el COT da
           posicionamiento por contrato, no regimen de mercado.
TEST       Anadir el veto y medir sobre 2015-2025 con la misma ventana.
VERDICT    CONFIRMED — es una sustitucion que convierte un
           UNMEASURABLE-WITH-CURRENT-DATA en medible, y por la regla del encargo
           ranquea por encima de mejorar algo ya medible.
DELTA      Agente de regimen de volatilidad, de lote, con un veto que solo baja.
LEDGER     [A3, A2, A1', A4, A5: puerta de regimen VIX]
```

## ITER 10/20 — La matriz de correlaciones es ruido sin denoising

```
STATE      idem
HYPOTHESIS `PortfolioConstructor` penaliza por correlacion media sobre una
           matriz muestral cruda, cuyos autovalores pequenos son casi todos ruido
           con el numero de observaciones y activos que maneja el rebalanceo.
EVIDENCE   src/portfolio/construccion.py:305-329 — `rets.corr()` a secas.
           src/portfolio/construccion.py:409-435 — la penalizacion usa la media
           de la fila de esa matriz.
           Con `CORRELACION_VENTANA_DIAS` observaciones y N candidatos por
           rebalanceo, q = T/N cae en el rango donde Marchenko-Pastur predice que
           la mayoria del espectro es ruido.
TEST       Sustituir por `denoise_cov` (repo 03) y comparar el backtest.
           Es la unica modificacion del ledger que NO NECESITA NINGUN DATO NUEVO.
VERDICT    CONFIRMED como defecto; el efecto hay que medirlo.
DELTA      `denoise_cov` dentro de `_correlaciones`.
LEDGER     [A3, A2, A1', A4, A5, A6: denoising de la matriz de correlaciones]
```

## ITER 11/20 — El signo de la exposición gamma sigue sin verificarse

```
STATE      idem
HYPOTHESIS La convencion de signo del gamma flip se puede validar
           empiricamente.
EVIDENCE   CLAUDE.md la declara "el eslabon mas debil del bloque" y
           `build_limitations()` #7 la recoge. Validarla exigiria comparar el
           gamma_flip calculado contra el comportamiento observado del precio
           sobre una muestra — y eso exige cadenas historicas, que
           FUENTES_DATOS.md ITER 18 confirma de pago.
TEST       Imposible con datos gratuitos.
VERDICT    UNMEASURABLE-WITH-CURRENT-DATA
DELTA      Ninguno. Se conserva la limitacion tal cual esta escrita.
           Para medirlo haria falta: un archivo de cadenas por ticker con
           open interest y volatilidad implicita historicos, con al menos dos
           anos de profundidad. No existe gratis.
LEDGER     sin altas
```

## ITER 12/20 — El rating sigue sin ordenar el rendimiento futuro — PARADA

```
STATE      idem
HYPOTHESIS El defecto dominante del sistema no esta en el punto de entrada sino
           en el corte que convierte la conviccion en rating (NEXT_STEPS #5 y
           #14: el event study a 12 meses ordena las categorias AL REVES).
EVIDENCE   backtest_results.json, NEXT_STEPS #5 y #14, ya publicados.
TEST       Fuera del alcance de este encargo, que pide precision de ENTRADA.
VERDICT    CONFIRMED como problema, FUERA DE ALCANCE como delta.
DELTA      Ninguno aqui. Pero condiciona la lectura de todo lo demas: afinar el
           precio de entrada de una senal cuya direccion no ordena el rendimiento
           es optimizar el segundo decimal de un numero cuyo signo esta en duda.
           Se dice explicitamente en el informe final.
LEDGER     sin altas

>>> PARADA TEMPRANA: iteraciones 11 y 12 sin altas. Loop A detenido en 12/20.
```

## Ledger final del Loop A, ordenado

| # | Modificación | Efecto esperado | Coste | ¿Medible? | Riesgo para las invariantes |
|---|---|---|---|---|---|
| **A2** | **Ejecución de orden limitada en `engine.py` + `precio_entrada_objetivo` en `Signal`** | **Ninguno sobre la señal. Cambia lo que el estudio PUEDE VER.** | Medio | Es *la* condición de medibilidad | **Nulo** — `engine.py` es contabilidad, no decisión. No añade ninguna regla. |
| **A1'** | `src/tools/niveles.py` — soportes estructurales del OHLCV como candidatos de nivel | Da nivel al ajuste de entrada en el backtest por primera vez | Bajo | Sí, sobre el estudio entero | Bajo. Es una tool nueva en `src/tools/`, fuera de `TOOLS_LECTURA`. |
| **A3** | Medir el ajuste de entrada y publicar el resultado | **Probablemente negativo** (ITER 7) | Bajo | Sí | Nulo |
| **A5** | Agente de régimen de volatilidad (VIX vía ALFRED) | Veto que solo baja; cierra la ausencia de medida de estrés | Medio | Sí, estudio entero, fuente PIT-NATIVE | Bajo, si el veto solo baja |
| **A4** | `distancia_soporte_atr` como bandera de sobreextensión estructural | Pequeño; asociación no monótona | Bajo | Sí | Bajo, si solo cierra |
| **A6** | `denoise_cov` en la matriz de correlaciones | Desconocido; **no necesita ningún dato nuevo** | Bajo | Sí | Bajo |

---

# FASE 2 — DISEÑO DE LOS AGENTES CANDIDATOS

**Dos agentes.** El encargo permite cuatro y dice que menos es mejor. Tras el
Loop A, un tercer agente que estimara «la probabilidad de que el nivel aguante»
carecería de sentido: ITER 7 muestra que **el nivel que aguanta no paga**, así
que predecirlo mejor no cambia la decisión. Se propone en su lugar una
**incorporación medida y probablemente refutada** (§2.3), que es un entregable
válido de este encargo.

## 2.1 `StructureAnalystAgent` — Analista de Estructura de Precio

| Campo | Valor |
|---|---|
| Clase | `StructureAnalystAgent` |
| Módulo | `src/agents/estructura.py` |
| `nombre` | `"estructura"` |
| `rol` | `"Analista de Estructura de Precio"` |
| `campo_texto` | `"summary"` |
| Tools | `src/tools/niveles.py` — `identificar_soportes`, `medir_distancia_soporte`, `clasificar_estructura` |
| Ámbito | **Por ticker** |

**Posición en el grafo y dependencia de datos que la fuerza.** Entre
`technical_analysis` y `posicionamiento`. No es una preferencia: consume `atr`
y `close` del informe técnico para expresar la distancia al soporte en unidades
de volatilidad, y **`posicionamiento` consume su `nivel_soporte_estructural`**
como candidato de nivel. Es exactamente la cadena que ya obliga a
`posicionamiento` a seguir a `technical`. Colgarlo del mismo superstep que
`technical` produciría otro dictamen, y además no podría escribir
`workflow_status`, que sigue siendo un escalar sin reductor.

```
technical_analysis → estructura → posicionamiento → debate_unit → fund_manager
```

**Variables de decisión que escribe, y por qué mecanismo permitido:**

| Variable | Mecanismo | Justificación |
|---|---|---|
| `nivel_soporte_estructural: Optional[float]` | **Candidato de nivel** para `ajustar_precio_entrada`, con la misma regla de «el más alto por debajo del precio» | No es un mecanismo nuevo: es un cuarto candidato junto a `SOPORTE_OI`, `GAMMA_FLIP` y `MAX_PAIN`. El ajuste sigue acotado a `AJUSTE_MAXIMO_ATR` y sigue pasando por `min(0.0, ajuste)`. **Estructuralmente no puede subir la entrada.** |
| `soporte_lejano: bool` | **Bandera de sobreextensión** — se une por `or` a `sobreextendido` en `posicionamiento` | Familia de las que **solo cierran**: prohíbe `PERSEGUIR`, nunca lo habilita. Igual que `en_techo_del_canal`. |
| `distancia_soporte_atr: Optional[float]` | Descriptiva | Solo informe. |

**Nuevas claves de estado:** `estructura_report: Dict[str, Any]` en
`FinancialAnalysisState`. Sin reductor: un único escritor.

**Ruta de degradación.** Sin ventana OHLC utilizable (menos de las sesiones que
el mínimo previo más largo necesita), **todos** los niveles son `None`,
`status = "DATOS_INSUFICIENTES"`, `soporte_lejano = False` y el agente no aporta
ningún candidato. El comportamiento resultante es **idéntico** al actual.
Test obligatorio: `test_sin_estructura_el_ajuste_de_entrada_no_cambia`, análogo
de `test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado`.

**Lista de materiales de fuentes:**

| Insumo | Entrada en `FUENTES_DATOS.md` | Clase |
|---|---|---|
| OHLC diario | **S4** — `PriceStore` del propio anfitrión | **PIT-NATIVE** |
| `sma_50`, `sma_200`, `bb_lower`, `atr` | Ya en `technical`, calculados por `_add_technical_indicators` sobre esa misma ventana | **PIT-NATIVE** |

**¿Puede el backtest ver sus insumos point-in-time? SÍ, todos.** Es el primer
bloque del Analista de Posicionamiento que el estudio podrá medir de principio a
fin sobre las 132 fechas de rebalanceo. Eso **no** cierra la limitación nº 5:
el estudio seguirá sin medir el bloque de opciones, y el ajuste que medirá será
el que producen los soportes de precio, **no** el que producen el open interest
y el max pain. **La diferencia se nombra en `build_limitations()` en vez de
promediarse.**

## 2.2 `RegimeAnalystAgent` — Analista de Régimen de Volatilidad

| Campo | Valor |
|---|---|
| Clase | `RegimeAnalystAgent` |
| Módulo | `src/agents/regimen.py` |
| `nombre` | `"regimen"` |
| `rol` | `"Analista de Régimen de Volatilidad"` |
| `campo_texto` | `"summary"` |
| Tools | `src/tools/regimen.py` — `calcular_zscore_volatilidad`, `clasificar_regimen_volatilidad`, `medir_volatilidad_relativa` |
| Ámbito | **DE LOTE** para su insumo; por ticker para su dictamen |

**Por qué es de lote y qué implica.** El dosier VIX es idéntico para todos los
valores de la ejecución y la serie es diaria: descargarlo dentro del grafo
sería pedir el mismo fichero de FRED una vez por ticker. Sigue **exactamente**
el patrón de `cargar_contexto_macro` y viaja en el estado inicial como
`regimen_data`. Por tanto hay que cablearlo en **los tres puntos de entrada**:
`cli.py`, `src/web/app.py` y `backtest_cli.py`.

`src/web/app.py` es el caso incómodo y se resuelve igual que los demás: llama a
`run_stock_analysis(ticker)` con los argumentos de lote por defecto, así que
**el dashboard seguirá sin veto de régimen** salvo que se cablee. Se cablea, con
un `cargar_regimen()` que degrada a `{}` ante cualquier fallo — el mismo
contrato que `cargar_benchmark` y `cargar_contexto_macro`.

Su dictamen **sí es por ticker**: cruza el régimen del mercado con la
volatilidad realizada del propio valor (`volatilidad_anual`, ya en `technical`),
y `vol_relativa = volatilidad_anual / (VIX/100)` distingue un valor que se mueve
más que el mercado de uno que se mueve menos, dentro del mismo régimen.

**Posición en el grafo.** Tercera rama del fan-out desde `quality_analysis`,
convergiendo en `join_analisis`:

```
                      ┌─ gatekeeper ────┐
quality_analysis ─────┼─ news_analysis ─┼─ join_analisis → [route] → ...
                      └─ regimen ───────┘
```

Argumento del fan-out, ya que **no** hay dependencia de datos que lo fuerce:
solo consume `regimen_data` (del estado inicial) y `technical` de la ingesta.
Comprobación de escrituras en el superstep: escribe `regimen_report` (clave
propia, un solo escritor), `logs` (`operator.add`) y `messages`
(`add_messages`) — los dos con reductor. **No escribe `workflow_status`**, que
es un escalar sin reductor y lo escribe el gatekeeper en ese mismo superstep.
Es la misma restricción que ya cumple `news_analysis`.

Colocarlo en el fan-out, y no en la rama aprobada, tiene además el mismo motivo
que llevó a `quality_analysis` antes del gatekeeper: **el régimen de mercado es
justo lo que se quiere leer sobre un valor que no pasa el filtro.**

**Variables de decisión que escribe:**

| Variable | Mecanismo | Justificación |
|---|---|---|
| `regimen_clasificacion: str` ∈ {`CALMA`, `NORMAL`, `TENSION`, `PANICO`, `NO_APLICABLE`} | **Veto en `aplicar_vetos`** — `PANICO` topa el dictamen en `MANTENER`; `TENSION` lo topa en `COMPRA` | Solo baja. Es la traducción del *anti-falling-knife gate* del repo 07 al vocabulario de vetos del anfitrión. |
| `puerta_regimen: bool` | Se une por `or` negado a `sobreextendido` en `posicionamiento` | Cerrada, prohíbe `PERSEGUIR`. Nunca lo habilita. |

**Nuevas claves de estado:** `regimen_data: Dict[str, Any]` (de lote, del estado
inicial) y `regimen_report: Dict[str, Any]`. Ninguna con reductor.

**Ruta de degradación.** Sin `regimen_data` —sin clave FRED, sin red, o en un
régimen del backtest que no lo inyecte— el informe es
`status = "NO_APLICABLE"`, `regimen_clasificacion = "NO_APLICABLE"`,
`puerta_regimen = True` (abierta) y ningún veto se dispara. El comportamiento es
**idéntico** al actual. Test: `test_sin_regimen_el_rating_no_cambia`.

**Lista de materiales de fuentes:**

| Insumo | Entrada | Clase | Verificación |
|---|---|---|---|
| `VIXCLS` | **S1** | **PIT-NATIVE** | Vintage 2018-03-01 devuelto correctamente; sin revisiones en tres vintages |
| `VXVCLS` | **S2** | **PIT-NATIVE** | 2007-12-04 → 2026-09-03 |
| `volatilidad_anual` del ticker | Ya en `technical` | PIT-NATIVE | — |

**Ninguna fuente `NO-HISTORY` toca ninguna de sus variables de decisión.**

**¿Puede el backtest ver sus insumos point-in-time? SÍ, íntegramente**, y es la
diferencia con el Analista de Posicionamiento: de éste el estudio medirá el
**100%** de la lógica, no la mitad. `FREDStore` reutilizará la función de
selección de producción con `as_of`, igual que `COTStore` invoca
`serie_semanal` — nunca una segunda implementación.

## 2.3 Lo que NO se propone como agente, y por qué

| Candidato | Por qué no |
|---|---|
| Modelo de probabilidad de que el soporte aguante | ITER 7. El nivel que aguanta **no paga**: `ret\|opera` es idéntico en las tres reglas de entrada. Predecir mejor algo que no cambia el resultado es trabajo perdido. Se mide en el Loop B y se reporta. |
| Máquina V-Reversal completa (repo 07) | Su fase de divergencia depende de CVD, que exige tick/depth de IBKR (§0.2). Y la versión sin CVD, medida a barra diaria, es la **peor** de las tres reglas: EV +0.687% frente a +1.726% del mercado. |
| Agente de liquidez/estrés sistémico (repo 02) | Sus series con vintage sí existen (S3), pero el diferencial de crédito —el complemento natural del VIX— solo llega a 2023 (ITER 17 de la Fase 1). Un agente de estrés basado solo en volatilidad implícita es el Agente 2, y ya está propuesto. Añadir un segundo con las mismas series sería duplicar. |
| Meta-etiquetado sobre las señales de compra (repo 03) | **No es un agente**: mapea sobre `peso_objetivo`, que ya existe. La intención era evaluarlo como configuración del Loop B y, si sobrevivía al DSR, incorporarlo como factor que **solo recorta** en `PortfolioConstructor`. **No llegó a evaluarse** — ver «Candidatos del inventario que no se resolvieron» al final de este documento. |
| HRP / NCO | Sustituirían la capa de cartera entera. Fuera del encargo. |
| `denoise_cov` | **No es un agente**: es una mejora de `_correlaciones` dentro de `PortfolioConstructor`. Entra como A6. |

---

# FASE 4 — LOOP B: BARRIDO ACOTADO Y MEDIDO

**13 configuraciones**, todas sobre el régimen `pit`, 2015-01-01 a 2025-12-31,
50 valores, rebalanceo mensual, 10 pb de costes, 1 000 muestras de Monte Carlo.
Lo único que cambia entre ellas es la configuración declarada.

**`n_trials = 13`**, que es el número REAL de configuraciones evaluadas. Pasar
menos es la forma exacta de que el Sharpe deflactado deje de controlar nada.

## Los dos criterios de aceptación, y por qué mandan ellos

Este proyecto ya fijó para sí mismo qué significa «mejor»: el **percentil frente
a selección aleatoria** y la **expectativa por operación**. Son los dos que la
memoria de reflexión empeoró, y por los que se desactivó. Una configuración que
mejore uno y empeore el otro **se rechaza**, aunque suba el Sharpe.

Dos advertencias metodológicas que hay que leer antes que la tabla, porque
cambian lo que las cifras significan:

1. **El percentil frente a selección aleatoria NO es comparable entre
   configuraciones sin cuidado.** `random_signal_benchmark` está sembrado
   (`seed=42`), pero sus parámetros —número de posiciones simultáneas, tenencia
   media y exposición bruta— se toman del PERFIL de la propia estrategia. Si una
   configuración cambia su exposición, la hipótesis nula se recalibra con ella.
   Diferencias por debajo de un punto no son interpretables; las de siete o nueve
   sí, porque el perfil apenas se mueve entre estas variantes.
2. **El Sharpe deflactado aquí es un control DÉBIL, y conviene decirlo.** El DSR
   deflacta contra la dispersión de los Sharpe entre ensayos. Estas trece
   configuraciones son variaciones menores de una misma estrategia, así que esa
   dispersión es diminuta (~0.002 por periodo) y el listón por azar que hay que
   superar sale casi en cero. El resultado —DSR ≈ 0.98 en todas— dice literalmente
   «el Sharpe observado sobrevive a la multiplicidad de ESTA búsqueda», que es
   verdad y es mucho menos de lo que suena. El DSR está pensado para una búsqueda
   sobre estrategias genuinamente distintas. **No se presenta como respaldo.**

## Ledger del Loop B

Cada iteración registra su hipótesis **antes** de medirla. Una iteración que
reporte una métrica que no nombró en `REGISTERED` no es evidencia.

```
ITER 1/13
  TARGET       Línea base con las tres incorporaciones ABLADAS
  REGISTERED   Con `--sin-estructura --sin-regimen` y `CORRELACION_DENOISE=0`, el
               estudio tiene que reproducir la linea base publicada EXACTAMENTE.
               Si no lo hiciera, ninguna comparacion antes/despues significaria
               nada, porque el cambio no seria aditivo.
  CHANGE       ninguno (es la referencia)
  VALIDATION   no procede: es una verificacion de identidad, no una estimacion
  METRICS      CAGR 3.947% · Sharpe 0.6808 · DD -13.803% · 563 ops ·
               acierto 44.58% · PF 1.381 · expectativa +1.229% · percentil 7.4
  BASELINE     lo publicado: 3.95% · 0.68 · -13.8% · 563 · 44.6% · 1.38 ·
               +1.23% · 7.4
  LIFT         cero en las ocho cifras
  VERDICT      KEEP como referencia. **Las tres incorporaciones son aditivas y no
               invasivas**, que es la condicion para que todo lo demas sea
               interpretable.
  TRIALS       1
```

```
ITER 2/13
  TARGET       `denoise_correlaciones` en `PortfolioConstructor._correlaciones`
  REGISTERED   La matriz de correlacion muestral de un rebalanceo es mayoritariamente
               ruido segun Marchenko-Pastur, asi que limpiarla deberia mejorar la
               penalizacion por correlacion y con ella la EXPECTATIVA por operacion
               y el PERCENTIL frente a seleccion aleatoria. No necesita ningun dato
               nuevo, asi que era el candidato con mejor relacion coste/beneficio.
  CHANGE       `rets.corr()` -> autovalores bajo la frontera de ruido sustituidos
               por su media, diagonal renormalizada
  VALIDATION   mismo periodo, mismas senales, mismo Monte Carlo sembrado
  METRICS      CAGR 3.83% · Sharpe 0.66 · DD -13.80% · 563 ops · acierto 44.4% ·
               PF 1.37 · expectativa +1.25% · percentil 6.5
  LIFT         expectativa +0.02pp · **percentil -0.9** · CAGR -0.12pp · Sharpe -0.02
  VERDICT      **DISCARD.** Mejora un criterio de aceptacion y empeora el otro, que
               es exactamente el patron por el que se rechaza. El numero de
               operaciones y el drawdown no cambian —su unico canal son los PESOS—
               asi que el efecto es limpio y limpiamente negativo.
               *Se entrega implementado y DESACTIVADO por defecto*
               (`CORRELACION_DENOISE=0`), igual que la memoria de reflexion.
  TRIALS       2
```

```
ITER 3/13
  TARGET       Analista de Estructura solo, con entrada a mercado
  REGISTERED   El soporte estructural da NIVEL, asi que el ajuste de entrada deja
               de ser `None` y el stop, el objetivo y el tamano se miden desde el
               precio de entrada objetivo. Deberia mejorar la expectativa por
               operacion. La bandera `soporte_lejano` deberia ademas subir el
               acierto, al prohibir perseguir el precio en valores sin referencia
               debajo.
  CHANGE       +`estructura_report`; 4o candidato de nivel; bandera de sobreextension
  VALIDATION   mismo periodo, misma ventana
  METRICS      CAGR 3.93% · Sharpe 0.67 · DD -13.80% · 564 ops · acierto 45.9% ·
               PF 1.38 · expectativa +1.24% · percentil 7.1
  LIFT         **acierto +1.3pp** · expectativa +0.01pp · percentil -0.3 · CAGR -0.01pp
  VERDICT      **DISCARD como mejora aislada**, y la parte registrada sobre el
               acierto SI se confirmo: +1.3 puntos es el efecto de la bandera.
               Pero el percentil baja y la expectativa apenas se mueve.
               *Se entrega ACTIVADO igualmente*, y el motivo no es el rendimiento:
               es que **sin el, el estudio no puede medir el ajuste de entrada en
               absoluto** —era `None` en el 100% de las senales— y en combinacion
               con el regimen (ITER 5) si aporta.
  TRIALS       3
```

```
ITER 4/13
  TARGET       Analista de Regimen de Volatilidad solo
  REGISTERED   El veto de regimen recorta dictamenes en episodios de estres
               sistemico. Si el filtro anti-cuchillo-cayendo del repositorio 07
               traslada, deberia subir el PERCENTIL frente a seleccion aleatoria
               —descarta senales malas, que es seleccion— y la EXPECTATIVA por
               operacion, a costa de menos operaciones.
  CHANGE       +`regimen_report`; veto que topa en MANTENER/COMPRA; puerta que
               prohibe perseguir
  VALIDATION   serie de volatilidad reconstruida point-in-time via ALFRED, filtrada
               por fecha de publicacion, verificada con la prueba de rebobinado
  METRICS      CAGR 3.78% · Sharpe 0.72 · DD -15.57% · 533 ops · acierto 45.8% ·
               PF 1.42 · expectativa +1.29% · percentil 14.5
  LIFT         **percentil +7.1** · **expectativa +0.06pp** · Sharpe +0.04 ·
               PF +0.04 · acierto +1.2pp · ops -30 · **DD -1.77pp (peor)**
  VERDICT      **KEEP.** Los DOS criterios de aceptacion mejoran, y el percentil
               casi se dobla. Lo predicho se cumplio en las tres dimensiones
               registradas: menos operaciones, mejor expectativa, mejor percentil.
               El drawdown empeora, y eso hay que decirlo: el veto concentra la
               cartera en menos nombres.
  TRIALS       4
```

```
ITER 5/13
  TARGET       Estructura + Regimen, entrada a mercado
  REGISTERED   Si los dos aportan por vias distintas —uno el nivel de entrada, el
               otro un veto de mercado— la combinacion deberia superar a cualquiera
               de los dos por separado en el percentil.
  CHANGE       las dos capas activas
  VALIDATION   idem
  METRICS      CAGR 3.89% · Sharpe 0.74 · DD -15.57% · 535 ops · acierto 47.3% ·
               PF 1.44 · expectativa +1.28% · percentil 16.7
  LIFT vs T01  **percentil +9.3** · **expectativa +0.05pp** · Sharpe +0.06 ·
               PF +0.06 · **acierto +2.7pp** · DD -1.77pp (peor)
  LIFT vs T04  percentil +2.2 · acierto +1.5pp · PF +0.02 · expectativa -0.01pp
  VERDICT      **KEEP, y es la configuracion que se entrega.** Contra la linea base
               mejoran los dos criterios de aceptacion. Contra el regimen solo, la
               estructura anade percentil y acierto a cambio de una centesima de
               expectativa: la combinacion es mejor que cualquiera de las dos.
  TRIALS       5
```

### Iteraciones 6 a 13 — hipótesis registradas ANTES de medir

Las ocho que siguen se escribieron con las cifras de T01-T05 a la vista y **sin
haber visto ninguna de las suyas**. Es la condición que el encargo impone y sin
la cual el ledger no es evidencia de nada.

```
ITER 6/13 · ITER 7/13 · ITER 8/13
  TARGET       Entrada LIMITADA al soporte, con la orden viva 5, 10 y 21 sesiones
  REGISTERED   *** LA HIPOTESIS CENTRAL DE TODO EL ENCARGO. ***
               La medicion a nivel de SENAL (936 compras, stops del propio Fund
               Manager, 10 pb) ya dijo que la orden limitada mejora la operacion
               (+1.70% de expectativa frente a +1.34%) y empeora el valor esperado
               por senal (+0.78% frente a +1.34%), porque lo que no rellena acierta
               el 59.6%.
               Predigo por tanto, a nivel de CARTERA y contra T05:
                 (a) MENOS operaciones, proporcionalmente a la tasa de no relleno;
                 (b) expectativa por operacion IGUAL O MEJOR;
                 (c) CAGR y percentil PEORES;
                 (d) el efecto se agrava con la vida de la orden, porque cuanto mas
                     tiempo se espera, mas fuerte es la seleccion adversa (a 21
                     sesiones lo descartado acertaba el 71.1%).
               Si (c) fallara —si el percentil subiera— la refutacion a nivel de
               senal no trasladaria a cartera y habria que revisarla entera.
  CHANGE       `--con-entrada-limitada --vida-orden {5,10,21}`
  VALIDATION   mismas senales que T05; solo cambia la EJECUCION
  METRICS      T06/T07/T08 en la tabla de resultados
  VERDICT      DISCARD las tres, contra T05. Ver «Que predije y que salio»
  TRIALS       6, 7, 8
```

```
ITER 9/13 · ITER 10/13
  TARGET       Umbral de `soporte_lejano`: 1.5 ATR y 3.0 ATR frente a los 2.0 de T05
  REGISTERED   La bandera solo cierra, asi que bajarla a 1.5 la dispara mas veces y
               subirla a 3.0 menos. Predigo que 1.5 sube el ACIERTO por encima del
               47.3% de T05 —prohibe perseguir mas a menudo— a costa de expectativa,
               y que 3.0 hace lo contrario.
               Si NINGUNA de las dos mueve nada apreciable, la conclusion correcta
               NO es «da igual el umbral»: es que la bandera apenas actua y su
               contribucion al +2.7pp de acierto de T05 hay que reatribuirla al
               nivel de entrada.
  CHANGE       `SOPORTE_LEJANO_ATR` = 1.5 / 3.0
  METRICS      T09/T10 en la tabla de resultados
  VERDICT      INERTES. Se aplica la contingencia registrada
  TRIALS       9, 10
```

```
ITER 11/13 · ITER 12/13
  TARGET       Umbral de TENSION del VIX: 20 y 30 frente a los 25 de T05
  REGISTERED   Es el veto que produjo casi todo el lift de T04. Con el umbral en 20
               el veto muerde mas —mas dictamenes topados en COMPRA— y con 30
               menos.
               Predigo una relacion NO monotona con el percentil: el veto ayuda
               porque descarta senales malas, pero pasado un punto empieza a
               descartar buenas. Si 20 y 30 salieran AMBOS peor que 25, seria
               indicio de que 25 esta cerca de un optimo local, y eso es
               exactamente el tipo de hallazgo que hay que mirar con desconfianza:
               tres puntos de una curva sobre el mismo historico no acreditan un
               optimo, acreditan que se ha buscado uno.
               Por eso el umbral que se entrega es 25 —el del repositorio 07,
               fijado ANTES de medir— y no el mejor de los tres.
  CHANGE       `REGIMEN_VIX_TENSION` = 20 / 30
  METRICS      T11/T12 en la tabla de resultados
  VERDICT      T11 identico a T05; T12 el mejor de los trece y NO se entrega
  TRIALS       11, 12
```

```
ITER 13/13
  TARGET       Ajuste maximo de entrada de 1.0 a 0.5 ATR, con entrada limitada
  REGISTERED   Un ajuste mas somero acerca el limite al precio, asi que la orden se
               rellena mas a menudo y la seleccion adversa se atenua. Predigo que
               T13 queda ENTRE T07 (mismo periodo de vida, ajuste completo) y T05
               (entrada a mercado): mas cerca de mercado, mejor resultado.
               Si asi fuera, la lectura no es «reduzcase el ajuste a 0.5 ATR» sino
               algo mas fuerte: **el optimo de la profundidad del ajuste es cero**,
               es decir entrar a mercado, que es justo lo que T05 hace.
  CHANGE       `AJUSTE_MAXIMO_ATR=0.5` + `--con-entrada-limitada --vida-orden 10`
  METRICS      T13 en la tabla de resultados
  VERDICT      DISCARD. Peor que T07, no entre T07 y T05: la prediccion falla
  TRIALS       13
```

## Resultados de las 13 configuraciones

**Dos referencias, y confundirlas invalidaría la lectura.** T02-T05 y T09-T12
responden «¿aporta esta incorporación?» y se juzgan contra **T01**, la línea
base. T06-T08 y T13 responden «¿conviene EJECUTAR la entrada como orden
limitada?»; comparten agentes con T05 y solo cambian la ejecución, así que su
referencia es **T05**. Juzgarlas contra T01 las haría parecer mejoras cuando son
degradaciones de la configuración que sí se entrega.

| # | Configuración | Ref. | CAGR | Sharpe | DD | Ops | Acierto | PF | **Expectativa** | **Percentil** | Veredicto |
|---|---|:--|---:|---:|---:|---:|---:|---:|---:|---:|:--|
| T01 | Línea base (todo ablado) | — | +3.95% | 0.68 | −13.80% | 563 | 44.6% | 1.38 | **+1.229%** | **7.4** | _referencia_ |
| T02 | Solo denoising Marchenko-Pastur | T01 | +3.83% | 0.66 | −13.80% | 563 | 44.4% | 1.37 | +1.251% (+0.02) | 6.5 (−0.9) | **DISCARD** |
| T03 | Solo estructura, entrada a mercado | T01 | +3.93% | 0.67 | −13.80% | 564 | 45.9% | 1.38 | +1.240% (+0.01) | 7.1 (−0.3) | **DISCARD** aislada |
| T04 | Solo régimen de volatilidad | T01 | +3.78% | 0.72 | −15.57% | 533 | 45.8% | 1.42 | +1.291% (+0.06) | 14.5 (+7.1) | **KEEP** |
| **T05** | **Estructura + régimen, entrada a mercado** | T01 | **+3.89%** | **0.74** | −15.57% | 535 | **47.3%** | **1.44** | **+1.283%** (+0.05) | **16.7** (+9.3) | **KEEP — SE ENTREGA** |
| T06 | + entrada LIMITADA, vida 5 | T05 | +3.54% | 0.70 | −15.57% | 503 | 45.5% | 1.42 | +1.252% (−0.03) | 13.9 (−2.8) | **DISCARD** |
| T07 | + entrada LIMITADA, vida 10 | T05 | +3.57% | 0.70 | −15.57% | 511 | 45.8% | 1.42 | +1.271% (−0.01) | 13.9 (−2.8) | **DISCARD** |
| T08 | + entrada LIMITADA, vida 21 | T05 | +3.53% | 0.69 | −15.57% | 518 | 45.8% | 1.41 | +1.229% (−0.05) | 13.7 (−3.0) | **DISCARD** |
| T09 | Soporte lejano a 1.5 ATR | T05 | +3.87% | 0.73 | −15.57% | 535 | 47.3% | 1.44 | +1.282% (−0.00) | 16.3 (−0.4) | inerte |
| T10 | Soporte lejano a 3.0 ATR | T05 | +3.89% | 0.74 | −15.57% | 534 | 47.2% | 1.44 | +1.295% (+0.01) | 17.1 (+0.4) | inerte |
| T11 | Umbral TENSION del VIX en 20 | T05 | +3.89% | 0.74 | −15.57% | 535 | 47.3% | 1.44 | +1.283% (0.00) | 16.7 (0.0) | **idéntico** |
| T12 | Umbral TENSION del VIX en 30 | T05 | **+4.19%** | **0.78** | −15.57% | 539 | **47.7%** | **1.47** | **+1.436%** (+0.15) | **24.3** (+7.6) | **el mejor — NO se entrega** |
| T13 | + limitada 10, ajuste máx. 0.5 ATR | T05 | +3.57% | 0.70 | −15.57% | 518 | 45.4% | 1.41 | +1.221% (−0.06) | 11.5 (−5.2) | **DISCARD** |

### Una imperfección del barrido, y por qué no cambia la conclusión

**T02 a T13 corrieron todas con el denoising ACTIVADO.** Solo T01 lo abla. Fue
un defecto de diseño de la rejilla: el interruptor `CORRELACION_DENOISE` tenía
`1` por defecto cuando el barrido arrancó, y solo T01 lo puso a `0`. La
consecuencia es que **T03-T13 miden estructura y régimen POR ENCIMA del
denoising**, no en aislamiento, y la comparación T05 vs. T01 está confundida con
él.

No se disimula y no se rehace el barrido, por dos motivos que se pueden
verificar:

1. T02 acota el confundido: el denoising solo cuesta 0.12pp de CAGR y 0.9 de
   percentil. Es un orden de magnitud menor que el efecto que se está midiendo
   (+9.3 de percentil).
2. **La configuración que se entrega se ejecutó aparte, con el denoising ya
   desactivado**, y da 16.6 de percentil frente a los 16.7 de T05: las mismas
   535 operaciones, el mismo 47.29% de acierto, la misma expectativa
   (+1.2834%), el mismo drawdown. La conclusión no se mueve.

**Las cifras que se publican son las de esa ejecución final, no las de T05.**

| | Línea base (T01) | **Entregado** |
|---|---|---|
| CAGR | 3.947% | 3.884% |
| Sharpe | 0.681 | **0.735** |
| Máx. drawdown | −13.80% | −15.57% |
| Operaciones | 563 | 535 |
| Acierto | 44.58% | **47.29%** |
| Factor de beneficio | 1.381 | **1.439** |
| **Expectativa por operación** | +1.229% | **+1.283%** |
| **Percentil vs. aleatorio** | 7.4 | **16.6** |

**Sharpe deflactado, con `n_trials = 13` y una dispersión de Sharpe entre
ensayos de 0.0020:** el listón por azar sale en 0.0024 por periodo y **todas las
configuraciones dan DSR entre 0.977 y 0.991**. Como se advirtió arriba, eso no
es un respaldo: estas trece son variaciones menores de una misma estrategia, la
dispersión es diminuta y el listón que deflacta sale casi en cero. El DSR aquí
dice «el Sharpe observado sobrevive a la multiplicidad de ESTA búsqueda» y nada
más.

## Qué predije y qué salió

| Iteración | Predicción registrada | Resultado |
|---|---|---|
| T02 | El denoising mejora expectativa **y** percentil | **FALLA en parte.** Expectativa sí (+0.02pp), percentil no (−0.9). Rechazado. |
| T03 | La bandera sube el acierto | **ACIERTA** (+1.3pp), pero el percentil baja: rechazada aislada. |
| T04 | El veto sube percentil y expectativa a costa de operaciones | **ACIERTA en las tres.** |
| T05 | La combinación supera a cualquiera de las dos por separado en percentil | **ACIERTA** (16.7 > 14.5 y > 7.1). |
| T06-T08 | (a) menos operaciones · (b) expectativa igual o mejor · (c) CAGR y percentil peores · (d) se agrava con la vida de la orden | (a) **ACIERTA** · (b) **FALLA**: la expectativa BAJA en las tres · (c) **ACIERTA** · (d) **ACIERTA**: a 21 sesiones la expectativa cae exactamente a la de la línea base. |
| T09-T10 | 1.5 sube el acierto, 3.0 lo baja | **FALLA. Nada se mueve.** Se aplica la contingencia que registré: la bandera apenas actúa, y el +2.7pp de acierto de T05 hay que reatribuirlo al nivel de entrada. |
| T11-T12 | Relación no monótona con el percentil | **ACIERTA, y de forma asimétrica e informativa** — ver abajo. |
| T13 | Un ajuste más somero queda ENTRE T07 y T05 | **FALLA.** Queda por DEBAJO de T07 (percentil 11.5 frente a 13.9). Se rellena más (22 órdenes expiradas frente a 33) y el resultado empeora, lo que **refuerza** la explicación por selección adversa: más rellenos limitados es más selección adversa, no menos. |

## Los dos hallazgos que no buscaba

### 1. La clasificación de régimen la domina el z-score, no el nivel

T11 (umbral de TENSION en 20) sale **idéntico dígito a dígito** a T05 (umbral en
25): mismas 535 operaciones, mismo 47.3%, mismo percentil 16.7. Y T12 (umbral en
30) es el mejor de las trece.

La explicación está en `_clasificar_regimen`, que toma `max(escalón_por_nivel,
escalón_por_zscore)`. **La dimensión más sensible manda**, y en esta ventana esa
es el z-score: bajar el corte de nivel queda enmascarado, subirlo hasta 30 deja
el escalón TENSION cubriendo solo `[30, 35)` y por tanto casi inerte.

Lectura honesta: **el escalón TENSION al 25 está perjudicando; lo que aporta es
el escalón PANICO.** El canal no es el veto —capar COMPRA FUERTE a COMPRA no
cambia el tamaño, porque `_dimensionar` trata las dos igual— sino la **puerta**:
cerrada, prohíbe perseguir el precio, y eso mueve el ajuste de entrada, el stop,
la distancia al stop y con ella el peso.

### 2. Y aun así, el umbral que se entrega es 25, no 30

T12 mejora los dos criterios de aceptación de forma sustancial (+0.15pp de
expectativa, +7.6 de percentil) y es la mejor configuración medida. **No se
entrega.**

El motivo está registrado en el ledger **antes** de ver esa cifra: tres puntos de
una curva sobre el mismo histórico no acreditan un óptimo, acreditan que se ha
buscado uno. Adoptar el umbral que mejor midió sobre la ventana con la que se
midió es exactamente el defecto metodológico que este proyecto ya documentó dos
veces —en FinVision, en FinAgent y en su propia capa de reflexión— y revertir
esa posición justo cuando el número sale a favor sería peor que no haberla
tomado.

Se entrega 25, que es el valor fijado antes de medir, y el hallazgo va a
`NEXT_STEPS` con la validación que exigiría: **fijar el umbral con datos hasta
2019 y evaluar 2020-2025 sin volver a mirarlo.**

---

# FASE 6 — VALIDACIÓN Y VEREDICTO

## 6.1 Suite determinista

```
<python> -m pytest tests/ --ignore=tests/test_fetcher.py --ignore=tests/test_workflow.py -q
439 passed, 1 skipped in 6.16s
```

**Ningún test relajado, saltado ni borrado.** Los 376 anteriores siguen pasando
sin tocar; los 63 nuevos se reparten en cuatro ficheros:

| Fichero | Qué fija |
|---|---|
| `tests/test_estructura.py` (24) | El soporte estructural **solo baja** la entrada, sobre el producto cartesiano de las cuatro fuentes de nivel · el mínimo excluye la barra en curso · **añadir barras posteriores no cambia un soporte anterior** · la bandera solo cierra · sin estructura el ajuste no cambia · ausencia ≠ cero |
| `tests/test_regimen.py` (21) | **La serie filtra por fecha de PUBLICACIÓN**, no de observación · añadir observaciones posteriores no cambia una lectura anterior · **un vintage cacheado nunca se sobrescribe y una redescarga divergente levanta** · el veto solo baja (producto cartesiano) · la curva invertida solo agrava · sin régimen el rating no cambia |
| `tests/test_entrada_limitada.py` (9) | Sin límite, el comportamiento es el de siempre · hueco de apertura → se rellena a la apertura, no al límite · el mínimo toca → al límite · **la orden que expira NO abre posición** · un rebalanceo nuevo sustituye la orden viva |
| `tests/test_fuentes_pit.py` (6) | **Afirmado en código, no en prosa:** ninguna fuente sin historia alcanza la decisión · el archivo de volatilidad cubre la ventana · toda observación lleva su par fecha/publicación · la cadena de opciones sigue declarada ausente en el replay |

Más las dos suites en vivo (`test_fetcher.py`, `test_workflow.py`): 2 passed.

`tests/test_llm_texto.py::AGENTES` pasa de **seis a nueve** agentes. Incluía un
hueco de cobertura declarado —`PositioningAnalystAgent` no estaba, pese a
redactar `summary`— y ahora está, junto con los dos nuevos.

## 6.2 Backtest antes y después, misma ventana y mismo régimen

```
<python> backtest_cli.py --start 2015-01-01 --end 2025-12-31 --regime pit
```

| | Antes (publicado) | Después (entregado) | |
|---|---|---|---|
| CAGR | 3.947% | 3.884% | ↓ |
| Sharpe | 0.681 | **0.735** | ↑ |
| Máx. drawdown | −13.80% | −15.57% | ↓ |
| Operaciones | 563 | 535 | |
| **Tasa de acierto** | 44.58% | **47.29%** | ↑ |
| **Factor de beneficio** | 1.381 | **1.439** | ↑ |
| **Expectativa por operación** | +1.229% | **+1.283%** | ↑ |
| **Percentil vs. selección aleatoria** | 7.4 | **16.6** | ↑ |
| CAGR del índice | 13.51% | 13.51% | — |

**Los dos criterios de aceptación que este proyecto fijó para sí mismo mejoran**,
y el percentil frente a selección aleatoria se dobla con creces. A cambio, el
drawdown máximo empeora en 1.8 puntos: el veto de régimen concentra la cartera
en menos nombres, exactamente el mismo mecanismo por el que la capa de reflexión
llevó el drawdown de −13.8% a −18.0%. Aquí el intercambio sale a favor; allí no.

**Y las dos conclusiones incómodas siguen intactas, que es lo que importa:**

- **El sistema NO bate a comprar y mantener el índice.** 3.88% frente a 13.51%.
  La diferencia no se ha reducido: se ha ampliado ligeramente.
- **El percentil frente a selección aleatoria sigue por debajo de la mediana.**
  16.6 sobre 100. Elegir al azar con el mismo perfil de exposición sigue
  batiendo a este sistema cinco veces de cada seis. Que haya pasado de 7.4 a
  16.6 es una mejora real y sigue siendo un suspenso.

No suavices ninguna de las dos al editar los informes.

## 6.3 Las tres pruebas de reproducibilidad, con su salida

### (a) Doble ejecución `--offline` — idéntica byte a byte

```
  IDENTICO   backtest_report.md
  IDENTICO   backtest_results.json
  IDENTICO   backtest_equity_pit.csv
  IDENTICO   backtest_trades_pit.csv

  6a40ceed55407f27e1f4d8f014c3fde3865f029ad9fa368e8a8a348b6f37b704  repro_a/backtest_results.json
  6a40ceed55407f27e1f4d8f014c3fde3865f029ad9fa368e8a8a348b6f37b704  repro_b/backtest_results.json
```

**Esta propiedad NO se cumplía antes de este encargo.** `src/backtest/report.py`
escribía `datetime.now()` en dos sitios —la cabecera del markdown y el campo
`generated_at` del JSON—, así que dos ejecuciones `--offline` producían ficheros
distintos y la afirmación «el estudio es reproducible» no era comprobable. Es el
mismo defecto que el proyecto ya había corregido en la traza de los agentes
haciendo secuenciales los identificadores y dejando las duraciones fuera de
`Traza.a_dict()`; quedaba este.

Lo que se imprime en su lugar es más informativo, no menos: el periodo del
estudio y **el vintage de cada serie externa**, que es lo que permite
diagnosticar dos ejecuciones que discrepen en vez de discutirlas.

### (b) Recarga en frío de la fuente nueva

Se apartó `data/cache/fred/` entera y se volvió a descargar desde la red:

```
  27 ficheros antes · 27 ficheros después
  ✓ IDÉNTICAS: la recarga en frío reproduce la caché caliente byte a byte
```

**Alcance declarado.** La recarga en frío cubre **la fuente que este encargo
introduce**. No se re-descargaron los ~250 MB de precios de yfinance ni los
`companyfacts` de la SEC: son horas de tráfico contra dos proveedores con
límites de tasa, y su reproducibilidad `--offline` ya era una propiedad
establecida del repositorio. Lo que sí se verificó es que **la fuente nueva no
la rompe**.

### (c) Rebobinado de vintage

```
  as_of 2016-06-15: 400 obs · última 2016-06-15 =  20.14 · máximo visible 40.74
  as_of 2020-02-14: 400 obs · última 2020-02-14 =  13.68 · máximo visible 36.07
  as_of 2020-03-16: 400 obs · última 2020-03-16 =  82.69 · máximo visible 82.69
  as_of 2020-03-25: 400 obs · última 2020-03-25 =  63.95 · máximo visible 82.69

  observaciones de 2020 visibles el 14-feb: 31, máximo 18.84
  observaciones de marzo visibles el 25-mar: 18, máximo 82.69
```

El 14 de febrero de 2020, con el pánico a tres semanas de distancia, el máximo
del VIX visible en todo 2020 es **18.84**. El 16 de marzo es **82.69**. El
almacén devuelve lo que se sabía **entonces**, no lo que se sabe hoy.

---

# VEREDICTO FINAL

## ¿Es el punto de entrada medurablemente más preciso, o solo lo parece?

**Ninguna de las dos. La pregunta estaba mal planteada, y demostrarlo es el
resultado principal de este encargo.**

El encargo daba por supuesto que entrar más abajo mejora la entrada, y pedía
hacerlo medible. Se ha hecho medible —esa parte se ha entregado— y la medición
dice que **la premisa es falsa en este sistema**:

> Sobre 6 421 observaciones del universo completo, la rentabilidad **condicionada
> a operar** es prácticamente idéntica con las tres reglas de entrada: **+1.71%**
> entrando a mercado, **+1.76%** entrando al soporte, **+1.71%** esperando a la
> recuperación confirmada. Entrar entre un 1% y un 2.5% más barato **no produce
> un resultado mejor.** La selección adversa cancela exactamente la mejora de
> precio, porque las trayectorias que vuelven a tu nivel son las débiles.

Y a nivel de cartera, sobre el estudio completo, las tres variantes de entrada
limitada quedan por debajo de la entrada a mercado en los dos criterios de
aceptación.

Lo que sí ha mejorado el sistema es **otra cosa**, y no la que el encargo
buscaba: un **veto de régimen de mercado** apoyado en la única serie macro que
resultó ser reconstruible point-in-time de verdad. El percentil frente a
selección aleatoria pasa de 7.4 a 16.6.

## Recuento de ensayos y DSR

**13 configuraciones**, más las tres mediciones a nivel de señal de la Fase 3.
`n_trials = 13`, dispersión de Sharpe entre ensayos 0.0020, listón por azar
0.0024 por periodo, **DSR entre 0.977 y 0.991 en las trece**.

Ese DSR **no se presenta como respaldo**, y el motivo es metodológico: el
estadístico deflacta contra la dispersión entre ensayos, y trece variaciones
menores de una misma estrategia tienen una dispersión diminuta. Dice «el Sharpe
observado sobrevive a la multiplicidad de esta búsqueda» y nada más fuerte.

## Qué fuentes alimentan ahora la decisión, y bajo qué clase

| Fuente | Clase | Novedad |
|---|---|---|
| OHLCV de yfinance (`PriceStore`) | PIT-NATIVE | **Nueva en la ruta del nivel de entrada.** Ya estaba en el repositorio. |
| `VIXCLS` y `VXVCLS` vía ALFRED | PIT-NATIVE | **Nueva.** Verificada con vintage y con retardo de publicación impuesto por el proveedor. |
| SEC EDGAR `companyfacts` | PIT-NATIVE | Sin cambios |
| CFTC COT | PIT-NATIVE | Sin cambios |
| Cadena de opciones por ticker | PIT-ARCHIVABLE | Sin cambios: sigue sin cubrir la ventana y sigue declarada ausente en el replay |

## Qué puede medir hoy el estudio que antes no podía

1. **El ajuste de precio de entrada.** Era `None` en el 100% de las 5 621
   señales. Ahora hay nivel, y además el motor sabe ejecutarlo como orden
   limitada con una regla de expiración explícita.
2. **Un régimen de estrés sistémico**, del que mide el 100% de la lógica.
3. **La reproducibilidad byte a byte de su propia salida**, que no era
   comprobable.

## Qué se refuta, y se entrega refutado

| Incorporación | Estado |
|---|---|
| **Entrada limitada al soporte** | Implementada, probada, medida y **DESACTIVADA por defecto**. Segundo resultado negativo publicable del proyecto, hermano del de `src/memoria/`. |
| **Máquina V-Reversal del repo 07** (recuperación confirmada) | La peor de las tres reglas: EV +0.687% frente a +1.726% de mercado. No se incorpora. Su fase de divergencia depende de CVD, que exige datos de tick inexistentes aquí. |
| **Denoising Marchenko-Pastur** | Implementado, probado, medido y **DESACTIVADO por defecto**. Era el candidato con mejor relación coste/beneficio —no necesita ningún dato nuevo— y mejora un criterio de aceptación mientras empeora el otro. |
| **Bandera de soporte lejano** | Se entrega activa, pero medida como **prácticamente inerte**: duplicar su umbral mueve una operación de 535. |
| **Umbral de TENSION del VIX en 30** | La mejor configuración medida (+0.15pp de expectativa, +7.6 de percentil) y **NO se entrega**, por la razón registrada antes de verla. |

## La advertencia que enmarca todo lo anterior

`NEXT_STEPS` #5 sigue en pie: **el rating no ordena el rendimiento futuro**, y el
event study a doce meses ordena las categorías al revés de lo que el sistema
afirma. Afinar el precio de entrada de una señal cuya dirección no ordena el
rendimiento es optimizar el segundo decimal de un número cuyo signo está en duda.

Este encargo ha mejorado la selección de 7.4 a 16.6 de percentil sin tocar esa
cuestión. Es una mejora real sobre un problema que sigue abierto.

---

# CANDIDATOS DEL INVENTARIO QUE NO SE RESOLVIERON

Auditoría de este documento contra sí mismo. La Fase 0 marcó como `LIFT` o
`REFIT` varios elementos que **no llegaron a la Fase 4 ni al código**, y uno de
ellos con una promesa explícita. Dejarlo sin decir convertiría el inventario en
una lista de intenciones en vez de un registro de decisiones.

| Candidato | Cómo quedó marcado | Qué pasó realmente | Por qué |
|---|---|---|---|
| **Meta-etiquetado sobre las señales de compra** (repo 03) | §2.3: «se evalúa como configuración del Loop B; si sobrevive al DSR, entra como factor que solo recorta» | **NO SE EVALUÓ.** Es una promesa de este documento que no se cumplió. | El presupuesto del Loop B (13 configuraciones) se consumió entero en la pregunta del encargo —el punto de entrada—, y esta habría necesitado además construir etiquetas, CV purgado, walk-forward y un artefacto congelado: varias iteraciones por sí sola. **Es la incorporación pendiente de mayor valor esperado**, y el propio encargo la señalaba como «el encaje más limpio» entre estos repositorios y las invariantes del anfitrión. |
| `PurgedGroupTimeSeriesSplit`, `compute_sample_weights`, `CombinatorialPurgedCV`, MDA/SFI | `LIFT — VALIDATE-ONLY` | **No se levantaron.** | Sin ningún modelo entrenado en la ruta de decisión, no tendrían un solo llamante: serían código muerto que mantener. Se levantan **el día que entre el meta-etiquetado**, no antes — que es precisamente cuando pasan de adorno a requisito. Lo único de la maquinaria de validación que sí se levantó es PSR/DSR, porque la Fase 4 lo usa. |
| `drawdown_guard` (repo 03) | `REFIT` — «el anfitrión no tiene equivalente» | **No se implementó.** | Es cierto que falta y sigue faltando. No se propuso como agente en la Fase 2 porque no toca el punto de entrada, que era el encargo. Encajaría como un factor que solo recorta en `PortfolioConstructor`, junto a `factor_reflexion`. |
| Diferenciación fraccional (`frac_diff_ffd`) y canal de Donchian (`_donchian_frame`) | `REFIT` — «candidato a *feature*; ver Loop B» | **No se evaluaron.** | Son *features* para un modelo, y no hay modelo. El canal de Donchian, además, quedó cubierto de facto: los mínimos de 10/21/63 sesiones de `src/tools/niveles.py` **son** su banda inferior, calculada con la disciplina causal del repo 07. |

**Ninguno de los cuatro afecta a lo entregado ni a lo medido.** Los tres primeros
son trabajo pendiente; el cuarto está cubierto en la práctica. Se listan aquí
para que el inventario de la Fase 0 no se lea como si todo lo marcado `LIFT` o
`REFIT` hubiera acabado en el código.

---

# PARTE II — LOS CUATRO CANDIDATOS PENDIENTES

> Cierre de la sección «Candidatos del inventario que no se resolvieron».
> Análisis exhaustivo de dónde encaja cada uno en la aplicación **tal y como
> está hoy**, qué invariante toca, qué necesita que no existe, y qué se rompe si
> se hace mal.

## A. El encaje, en una tabla

| # | Candidato | ¿Dónde encaja? | ¿Toca la decisión? | Mecanismo permitido | Bloqueante |
|---|---|---|---|---|---|
| 1 | **Meta-etiquetado** | `src/meta/` + factor en `PortfolioConstructor` | **Sí** | Factor que **solo recorta**, junto a `factor_reflexion` | Necesita etiquetas resueltas y reentrenamiento walk-forward |
| 2 | **CV purgado, unicidad, CPCV, MDA/SFI** | `src/tools/validacion.py` | **No** — `VALIDATE-ONLY` | Ninguno: no produce variables de decisión | Sin (1) no tiene llamante |
| 3 | **`drawdown_guard`** | `src/tools/riesgo.py` + `PortfolioConstructor` | **Sí** | Factor que **solo recorta** la exposición bruta | **Producción no lleva curva de capital** |
| 4 | **Diferenciación fraccional / Donchian** | *Features* del modelo de (1) | No directamente | — | Sin (1) no hay modelo que las consuma |

Los cuatro están **encadenados**: (2) y (4) existen para servir a (1), y (3) es
independiente pero comparte con (1) el mismo punto de aplicación. Por eso no se
resolvieron uno a uno: o entra (1) o no entra ninguno de los tres primeros.

---

## B. Candidato 1 — Meta-etiquetado

### B.1 Qué pregunta responde, y por qué encaja tan bien aquí

El sistema anfitrión produce el **lado** de forma determinista: `rating`. El
meta-etiquetado de López de Prado (AFML cap. 3) responde a la pregunta
siguiente: *dado que el modelo primario dice comprar, ¿acierta?* — y su salida
natural no es un rating sino un **tamaño**.

Eso encaja con la arquitectura del anfitrión de una forma que casi ningún otro
candidato lo hace:

- **No toca `rating`.** El rating sigue saliendo de `calcular_rating_compuesto`
  y de `aplicar_vetos`, tal cual. El meta-modelo solo modula `peso_objetivo`.
- **Ya existe el mecanismo exacto que necesita.** `factor_reflexion` es un
  factor en `[mínimo, 1.0]` que el Fund Manager publica **sin aplicar** y que
  `PortfolioConstructor._penalizar_reflexion` aplica y reasigna. El factor del
  meta-modelo es su hermano gemelo: mismo rango, mismo punto de aplicación,
  misma reasignación del presupuesto liberado.
- **Ya existe el patrón de capa con estado point-in-time.** `src/memoria/`
  anota señales, espera a que su desenlace sea conocible, consolida y sirve un
  dosier. `src/meta/` hace lo mismo con etiquetas en vez de con medias.

### B.2 El riesgo que hace peligroso este candidato, y que no existía en ninguno de los anteriores

Un artefacto de modelo congelado **es** una función determinista, así que **no
viola la invariante nº 1**: ejecutar dos veces produce el mismo número, y el LLM
sigue sin tocar ninguna rama.

Pero introduce un peligro point-in-time **estrictamente peor que un look-ahead
dentro de una variable**, porque es invisible: *un modelo entrenado con
2015-2025 y evaluado sobre 2016 no es un backtest, es un examen de memoria*, y
**ningún test de este repositorio lo detectaría**. `test_no_lookahead_*` mira
precios; `test_fundamentals_respect_filed_not_end` mira `filed`; ninguno mira de
qué años salieron los pesos de un modelo.

Las cinco condiciones que el encargo impone, y cómo se satisface cada una:

| Condición | Cómo se cumple aquí |
|---|---|
| Datos de entrenamiento estrictamente anteriores a la fecha de evaluación | **Reentrenamiento walk-forward anual.** No se congela un artefacto único. |
| CV purgado y con embargo | `PurgedGroupTimeSeriesSplit` del repositorio 06, levantado a `src/tools/validacion.py` |
| Pesos por unicidad donde las etiquetas se solapan | `compute_sample_weights` del 06: `abs(ret) × unicidad_media` |
| Artefacto versionado, ventana de entrenamiento dentro, cargador que **falla ruidosamente** | `src/meta/artefacto.py`: JSON con `entrenado_hasta`, `n_muestras`, `features` y coeficientes. Cargar uno cuya ventana **incluya** la fecha de evaluación levanta excepción. |
| Su ausencia degrada al comportamiento actual **exacto** | Sin artefacto, `factor_meta = 1.0` y `evaluable=False`. Test obligatorio, análogo de `test_sin_regimen_el_rating_no_cambia`. |

### B.3 El punto de corte NO es la fecha de la señal: es la del desenlace

Ésta es la regla que hace válido todo lo demás, y es exactamente la misma que ya
gobierna `src/memoria/`:

> Una señal del 1 de junio con barreras que se resuelven en julio **no se sabe
> cómo terminó hasta julio**. Entrenar en junio con su etiqueta es mirar el
> futuro.

Así que el modelo que decide en la fecha `t` solo puede haberse entrenado con
señales cuya **barrera se resolvió** antes del corte de entrenamiento, no cuya
emisión fue anterior. Es el par `filed`/`end` del XBRL, el
`fecha_informe`/`fecha_publicacion` del COT y el `fecha_desenlace` de la
reflexión, aplicados por cuarta vez.

Consecuencia práctica que hay que declarar: con un horizonte medio de 33
sesiones, **el modelo de enero de 2019 no puede usar señales posteriores a
noviembre de 2018**.

### B.4 Las etiquetas salen de las barreras DEL PROPIO SISTEMA

Hay dos formas de etiquetar y solo una es honesta aquí.

- ❌ Triple barrera genérica con múltiplos de volatilidad arbitrarios. Mediría
  si el momento era bueno para *alguna* operación.
- ✅ **Triple barrera con el `stop_loss_atr`, el `take_profit_atr` y el
  `horizonte_dias` que el propio Fund Manager emitió para esa señal.** Mide
  exactamente la operación que el sistema habría abierto.

La segunda es la única que responde a la pregunta del meta-etiquetado, y además
reutiliza niveles que ya son variables de decisión publicadas: no hay ninguna
regla nueva que inventar.

### B.5 El tamaño de la muestra es el problema real, y condiciona la elección de modelo

| | |
|---|---|
| Señales de compra en el estudio | **944** |
| Con ventana de precios utilizable | 936 |
| Operaciones cerradas en la configuración entregada | 535 |
| Rebalanceos | 132 |

El meta-etiquetado clásico se entrena **solo sobre los positivos del modelo
primario** —ésa es su definición—, así que la muestra es ~944, no 5.621. Con
reentrenamiento walk-forward, el primer modelo vería del orden de 200 ejemplos.
Y las etiquetas **se solapan fuertemente** en el tiempo: la unicidad media
recortará el tamaño efectivo aún más.

**Eso descarta un GBM profundo.** Con esa muestra, `HistGradientBoosting` con
sus valores por defecto memoriza. La elección disciplinada es:

1. **Regresión logística con regularización L2 fuerte** como modelo por defecto:
   pocos parámetros, coeficientes auditables, y una probabilidad calibrada de
   fábrica — que es justo lo que un factor de tamaño necesita.
2. `HistGradientBoostingClassifier` con profundidad y hojas muy acotadas como
   alternativa, **elegida por CV purgado**, no a mano.

La ventana de entrenamiento manda sobre la elección de modelo: es un caso donde
la restricción de datos determina la arquitectura, no al revés.

### B.6 Las variables, y por qué todas son point-in-time por construcción

Todas salen del **estado de la propia señal en `t`**, que el replay ya
reconstruye point-in-time. No hay ninguna fuente nueva:

| Bloque | Variables |
|---|---|
| Calidad | `conviccion`, las cuatro puntuaciones, F-Score, Z-Score, nº de banderas rojas |
| Técnico | `momentum_score`, `rsi`, `atr_pct`, `dist_sma_50_pct`, `dist_sma_200_pct`, `posicion_rango_52w`, `volatilidad_anual` |
| Estructura | `distancia_soporte_atr`, `estructura` |
| Régimen | `nivel_volatilidad`, `zscore_volatilidad`, `ratio_curva`, `volatilidad_relativa` |
| Posicionamiento | `sesgo_macro`, `confluencia`, `ajuste_entrada_pct` |
| Riesgo | `distancia_stop_pct`, `ratio_riesgo_recompensa`, `confianza_datos` |
| Estilo | codificado por frecuencia, no por *one-hot*: con 944 muestras y 10 estilos, diez columnas casi vacías son diez formas de sobreajustar |

**El estilo y el régimen no se codifican con `pd.get_dummies`.** Con esta muestra
hay que gastar los grados de libertad con cuidado.

### B.7 Cómo llega a la decisión, y por qué solo puede recortar

```
p = P(la operación acaba en beneficio | características de la señal)

factor_meta = clip( (p − p_min) / (p_ref − p_min), FACTOR_MINIMO, 1.0 )
```

Con `p_ref` = la tasa base del conjunto de entrenamiento. Por encima de la tasa
base, factor **1.0** — nunca más.

**Y ese tope no es un detalle de implementación: es la regla nº 1 de esta
familia.** Igual que `factor_reflexion` no amplía el peso de una celda con
expectativa excelente, el meta-modelo no amplía el peso de una señal que
considera buena. Premiar con tamaño lo que el modelo cree que funcionará es
exactamente lo que convierte una capa de filtrado en una apuesta apalancada
sobre el propio modelo.

Se aplica en `PortfolioConstructor`, no en el Fund Manager, y por el mismo motivo
que la reflexión: **solo la capa de cartera ve el rebalanceo entero y puede
reasignar** el presupuesto que el recorte libera.

### B.8 Qué se romperá si esto sale mal

Un `NEXT_STEPS` honesto exige decirlo antes de medirlo:

- Si el modelo no supera a la tasa base en CV purgado, **no se entrega**. Igual
  que la reflexión.
- Si supera en CV pero empeora el percentil frente a selección aleatoria o la
  expectativa por operación, **no se entrega**. Son los dos criterios fijados.
- La calibración walk-forward se hace sobre el **mismo histórico** que después
  se evalúa. Aunque respete el point-in-time, el resultado no es enteramente
  fuera de muestra — la misma advertencia que lleva la memoria de reflexión.

---

## C. Candidato 2 — La maquinaria de validación

Es `VALIDATE-ONLY` por definición: **no produce ninguna variable de decisión**,
así que no toca ninguna invariante. Su único riesgo es ser código muerto, que es
exactamente lo que era hasta que existió (1).

| Función | De dónde | Para qué en este sistema |
|---|---|---|
| `PurgedGroupTimeSeriesSplit(n_splits, embargo_days)` | repo 06 | Elegir modelo y umbral **sin** que una etiqueta de test solape con una de train. Agrupa por fecha de señal, que es justo la forma del rebalanceo. |
| `count_concurrency`, `average_uniqueness` | repo 06 | Cuantificar el solapamiento: una señal cuyo horizonte se pisa con otras diez vale menos que una aislada. |
| `compute_sample_weights` | repo 06 | `abs(ret) × unicidad`, normalizado a media 1. Es el peso con el que se entrena. |
| `sequential_bootstrap` | repo 06 | Muestreo que favorece observaciones poco solapadas. Se levanta pero **no se usa por defecto**: con 944 muestras, remuestrear reduce aún más el tamaño efectivo. |
| `mean_decrease_accuracy` | repo 06 | Importancia de variables sobre CV purgado, para el informe. |

**Por qué el k-fold normal no sirve, dicho sin rodeos.** Una señal del 1 de junio
con horizonte hasta el 15 de julio comparte información con otra del 20 de
junio. Si la primera cae en *train* y la segunda en *test*, el modelo ya ha
visto parte de la respuesta. Un k-fold corriente sobre etiquetas solapadas no es
validación: es una fuga con un número al lado.

---

## D. Candidato 3 — `drawdown_guard`

### D.1 Qué hace y por qué el anfitrión no tiene nada parecido

`src/risk/sizing.py` del repositorio 03 lanza `RiskCheckError` cuando el
patrimonio cae más de un porcentaje desde su máximo. El anfitrión **no tiene
equivalente**: su presupuesto de riesgo es *por posición* y *agregado en un
instante*, pero nada mira la trayectoria.

### D.2 Lanzar excepción no encaja, y hay que traducirlo

Un `raise` detendría el análisis. En este sistema la traducción correcta es la
familia que ya existe: **un factor que solo recorta la exposición bruta**.

```
factor_dd = clip( 1 − (|drawdown| − umbral) / escala , mínimo, 1.0 )
```

Neutro (1.0) por encima del umbral; nunca amplía.

### D.3 El bloqueante, que es de fondo y no de implementación

> **Producción no tiene curva de capital.**

`cli.py` emite recomendaciones; no gestiona una cartera, no conoce su
patrimonio y no sabe si está en drawdown. El backtest **sí** (`engine.equity`).

Eso deja tres salidas, y solo una es aceptable:

| Salida | Veredicto |
|---|---|
| Cablearlo solo en el backtest | ❌ **Inaceptable.** Sería una variable de decisión medida en el estudio y ausente en producción: la imagen especular de la limitación nº 5, y por el mismo motivo igual de mala. |
| Persistir la curva de capital en producción | Fuera de alcance: exige que el sistema sepa qué se ejecutó, y hoy no lo sabe. |
| **Implementarlo como función pura + entrada opcional del constructor, medirlo en el backtest y declararlo INERTE en producción hasta que exista una cartera real** | ✅ Es lo que se hace, y se declara en `build_limitations()`. |

Esa tercera opción es honesta porque el parámetro es **opcional y neutro por
defecto**: sin `drawdown_actual`, el constructor se comporta exactamente igual
que hoy, en producción y en el backtest.

---

## E. Candidato 4 — Diferenciación fraccional y canal de Donchian

### E.1 El canal de Donchian ya está, y conviene decirlo

`_donchian_frame` del repositorio 06 calcula el máximo y el mínimo de N sesiones.
**`minimos_previos` de `src/tools/niveles.py` ES su banda inferior**, con dos
mejoras sobre el original: excluye la barra en curso (`shift(1)` del repo 07) y
sus ventanas son las del anfitrión. La banda superior también existe, como
`resistencia` en `_soportes`.

No hay nada que incorporar. Se cierra el candidato.

### E.2 La diferenciación fraccional sí es nueva, y solo tiene sentido con (1)

Una serie de precios es no estacionaria; sus retornos son estacionarios pero han
perdido toda la memoria. `frac_diff_ffd` busca el punto intermedio: el `d`
mínimo que hace estacionaria la serie **conservando el máximo de memoria**.

- **Como *feature* de un modelo**: tiene sentido. Es el argumento entero del
  capítulo 5 de AFML.
- **Como entrada de una regla determinista**: no. El sistema no tiene ninguna
  regla que consuma un nivel de precio transformado, y añadir una sería inventar
  una regla para justificar una técnica.

Se incorpora, por tanto, **exclusivamente como candidata a variable del
meta-modelo**, y su inclusión se decide por CV purgado como cualquier otra.

**El `d` se fija, no se busca.** `find_min_ffd` necesita el test ADF de
`statsmodels`, que está descartado. Buscar `d` sobre la misma ventana que
después se evalúa sería, además, un ensayo más que no se estaría contando.

---

## F. Qué salió al medirlo

### F.1 El meta-modelo NUNCA llega a entregarse, y el motivo es contundente

Reentrenamiento walk-forward anual sobre el estudio completo, con CV purgada de
5 particiones y 21 días de embargo, pesos por unicidad y atribución de retorno:

| Corte | Etiquetas resueltas | AUC en CV purgada | ¿Artefacto? |
|---|---:|---:|:--|
| 2015-01-30 | 0 | — | no: muestra insuficiente |
| 2016-02-29 | 56 | — | no: muestra insuficiente |
| 2017-02-28 | 114 | — | no: muestra insuficiente |
| 2018-02-28 | ≥150 | **0.4197** | **no: por debajo del azar** |
| 2019-02-28 | ≥150 | **0.4027** | **no** |
| 2020-02-28 | ≥150 | **0.4521** | **no** |
| 2021-03-31 | ≥150 | **0.4466** | **no** |
| 2022-03-31 | ≥150 | **0.4718** | **no** |
| 2023-03-31 | ≥150 | **0.4680** | **no** |
| 2024-04-30 | ≥150 | **0.4376** | **no** |
| 2025-04-30 | ≥150 | **0.4703** | **no** |

**En las ocho ventanas con muestra suficiente, la AUC está por debajo de 0.5.**
No es que el modelo no supere al azar: es que queda **sistemáticamente por
debajo**, en ocho ventanas independientes separadas por un año cada una.

La lectura no es «el modelo es malo». Es más fuerte y más útil:

> Las 23 variables que el sistema conoce en el momento de emitir una señal
> **no contienen información utilizable sobre si esa operación concreta
> acabará en beneficio.** Convicción, momentum, régimen de volatilidad,
> distancia al soporte, sesgo macro y el resto no separan las compras que
> funcionan de las que no.

Y encaja con el hallazgo que el propio informe lleva publicando desde hace dos
revalidaciones: **el rating no ordena el rendimiento futuro**. Si la puntuación
compuesta no lo ordena, es coherente que un modelo entrenado sobre sus mismos
insumos tampoco.

Un AUC ligeramente por debajo de 0.5 de forma persistente —y no oscilando
alrededor— es además la firma de un sobreajuste leve cuyo signo se invierte
fuera de muestra: el modelo aprende algo del bloque de entrenamiento que deja de
valer, o vale al revés, en el bloque siguiente. Es exactamente lo que la CV
purgada existe para revelar y lo que un k-fold corriente habría ocultado.

**La barrera funcionó como se diseñó.** `META_VENTAJA_MINIMA_AUC` impidió
entregar el artefacto, `factor_meta` se quedó en 1.0 y la capa no tocó ni un
peso. Se comprobó ejecutando el estudio con y sin `--con-meta`: **las cifras son
idénticas dígito a dígito**.

### F.2 El hallazgo que no buscaba: siete de los once años del estudio no tenían COT

Construyendo las variables del meta-modelo apareció que `sesgo_macro_ord` era
`None` en el **100%** de las señales. La causa no estaba en el meta-modelo:

> **La caché de `data/cache/cot/` solo cubría 2022-2026.** El estudio empieza en
> 2015, y `--offline` no puede descargar lo que falta. El veto macro que
> `build_limitations()` afirmaba medir **llevaba inerte los primeros siete años
> del estudio**.

Es una limitación preexistente y no declarada. Recargada la caché de 2013 a 2021
con la misma función de producción (`serie_semanal`, sin reimplementar la
selección point-in-time), el veto pasa a actuar de verdad — sobre una muestra de
prueba, 31 de 93 señales de compra con `VIENTO_EN_CONTRA_FUERTE`, que es
exactamente el caso que topa el dictamen en COMPRA.

Efecto sobre el estudio completo, aislado ejecutando la misma configuración con
la caché antigua y con la nueva:

| | COT 2022+ (antes) | COT 2013+ (después) | |
|---|---:|---:|---|
| CAGR | 3.884% | 3.968% | ↑ |
| Sharpe | 0.735 | 0.744 | ↑ |
| Máx. drawdown | −15.57% | −16.15% | ↓ |
| Operaciones | 535 | 532 | |
| **Tasa de acierto** | 47.29% | **49.81%** | ↑ |
| Factor de beneficio | 1.439 | 1.446 | ↑ |
| **Expectativa por operación** | +1.283% | **+1.291%** | ↑ |
| **Percentil vs. aleatorio** | 16.6 | **17.7** | ↑ |

> **Corrección sobre una cifra que estuve a punto de publicar inflada.** El
> control de esta comparación se ejecutó con 300 muestras de Monte Carlo y daba
> percentil **20.3**; con las 1000 por defecto da **17.7**, sobre una estrategia
> IDÉNTICA (mismo CAGR al cuarto decimal, mismas 532 operaciones, misma
> expectativa). El percentil frente a selección aleatoria arrastra por tanto del
> orden de **2,6 puntos de ruido de muestreo** entre esas dos configuraciones, y
> las dos cifras de esta tabla son las de 1000 muestras para que la comparación
> sea legítima.
>
> Es la misma advertencia que ya llevaba el Loop B —«diferencias por debajo de un
> punto no son interpretables»— y aquí muerde: **+1.1 de percentil está apenas
> por encima de ese suelo.**

**La lectura honesta, entonces.** Lo que la recarga mejora de forma clara es la
**tasa de acierto: +2.5 puntos**, de 47.3% a 49.8%, sobre 532 operaciones. Los
dos criterios de aceptación mejoran, pero marginalmente. Y el drawdown empeora
seis décimas.

Su valor principal no es el rendimiento: es que **el veto macro pasa de estar
silenciosamente inerte a medirse de verdad**. Un informe que afirmaba medir algo
que no medía era un defecto de corrección, y sigue siéndolo aunque el efecto
resulte modesto.

### F.3 Y un defecto derivado: los patrones de mercado del COT solo valen desde 2022

Al recargar, tres de los cinco contratos devolvieron **cero semanas**. Los
nombres de mercado de la CFTC cambiaron:

| Contrato | Nombre en 2025 (el patrón actual) | Nombre en 2018 |
|---|---|---|
| Cobre | `COPPER- #1` | `COPPER-GRADE #1` |
| Gas natural | `NAT GAS NYME` | `NATURAL GAS` |
| Bono 10 años | `UST 10Y NOTE` | `10-YEAR U.S. TREASURY NOTES` |

`CLAUDE.md` dice que los patrones están «verificados contra el fichero real de la
CFTC (`deacot2025.zip`)», y es cierto — **verificados contra ese fichero y solo
contra ese**. Para los anteriores a 2022 no casan.

**La pata de ÍNDICE sí funciona** (`E-MINI S&P 500`, 520 semanas), y es la que
reciben todos los valores, así que el sesgo macro se calcula para todos. Lo que
falta es la pata sectorial en energía, materiales y financieras.

**No se «arreglan» los patrones aquí.** Ampliarlos para que casen con las dos
épocas cambiaría el dosier macro de producción sin medirlo, y este encargo ya ha
gastado su presupuesto de ensayos. Va a `NEXT_STEPS` con el diagnóstico hecho.

### F.4 `drawdown_guard` y la diferenciación fraccional

| | Estado |
|---|---|
| **`drawdown_guard`** | Implementado como factor que solo recorta, probado sobre el producto cartesiano y **cableado en `PortfolioConstructor` con parámetro opcional**. **INERTE EN PRODUCCIÓN**, y eso no es un defecto de implementación: el sistema emite recomendaciones, no gestiona una cartera y no conoce su patrimonio. Cablearlo solo en el backtest sería una variable de decisión medida en el estudio y ausente en producción — la imagen especular de la limitación nº 5. Declarado. |
| **Diferenciación fraccional** | Implementada (`pesos_ffd`, `frac_diff_ultimo`) y **entra como variable del meta-modelo**, que es su único uso legítimo aquí. Como el modelo no se entrega, la variable no llega a ninguna decisión. Su calibración dejó un hallazgo con test propio: con `umbral=1e-4` hacen falta **282 rezagos** y la ventana del replay tiene ~250 sesiones, así que la variable era `None` en todas las filas — y el sistema **se negó a entrenar** en vez de imputar, que es exactamente lo que tenía que hacer. |
| **Canal de Donchian** | **Ya estaba.** `minimos_previos` de `src/tools/niveles.py` ES su banda inferior, con dos mejoras: excluye la barra en curso y usa las ventanas del anfitrión. La banda superior existe como `resistencia`. Candidato cerrado sin escribir código. |
| **Maquinaria de validación** | Levantada a `src/tools/validacion.py` y **con llamante real**: la usa el entrenamiento walk-forward. Deja de ser código muerto, que era el motivo por el que no se había levantado antes. |

## G. Veredicto de los cuatro candidatos

| # | Candidato | Estado | Entregado |
|---|---|---|---|
| 1 | **Meta-etiquetado** | **REFUTADO Y MEDIDO.** AUC por debajo de 0.5 en las ocho ventanas walk-forward. Nunca produce artefacto. | Implementado, probado y **desactivado**. Tercer resultado negativo publicable del proyecto. |
| 2 | **CV purgado, unicidad, CPCV** | **INCORPORADO.** Con llamante real. | `src/tools/validacion.py` |
| 3 | **`drawdown_guard`** | **INCORPORADO, inerte en producción.** | `src/tools/riesgo.py` + parámetro opcional del constructor |
| 4 | **Frac-diff / Donchian** | Donchian **ya estaba**; frac-diff **incorporada** como variable del modelo refutado. | `src/tools/niveles.py` |

**Y un quinto, que no estaba en la lista y resultó valer más que los cuatro: la
caché del COT no cubría siete de los once años del estudio.**
