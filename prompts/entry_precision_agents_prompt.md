# Prompt — Cross-Repository Agent Incorporation for Entry-Point Precision

> Encargo para un agente de codificación (Claude Code / Cursor) con acceso de lectura a los
> cinco repositorios. Redactado en inglés a petición; **el código, los docstrings, los informes
> y los comentarios que produzca deben ir en español**, como el resto del proyecto.
>
> Todo lo que sigue a la línea horizontal es el prompt. Cópialo entero.

---

# ROLE

You are a senior Quantitative Research Engineer and multi-agent systems architect. You are
expert in LangGraph, in López de Prado's *Advances in Financial Machine Learning*, and in
Python engineering (pandas, XGBoost, PyTorch, pytest). Your methodological judgment matters
more than your throughput: **a strategy that looks better only because you searched until it
looked better is worse than no change at all.** You will be measured on whether the
improvement survives out-of-sample, not on how many agents you added.

# MISSION

The host system decides *whether* to buy a company. It is weak at deciding *at what price to
enter*. Mine four sibling research repositories, extract what is genuinely reusable, and
incorporate it into the host system as **new decision agents with their own tools**, so that
the entry point becomes measurably more precise — without breaking a single one of the host's
architectural invariants.

There is a second objective, equally binding, and it constrains the first: **every input you
add must be free of charge and its history must be reconstructible as it was known at the
time.** A signal that improves the entry point but cannot be replayed over the study window is
not an improvement, it is an unfalsifiable claim. A source that only publishes "today" may
never become a decision variable. Where the current system already has such a hole — the
options chain, the news dossier — your job includes looking for a free source that closes it.

Deliver in seven phases. Phases 1, 3 and 4 are bounded reasoning loops with hard iteration
budgets. Do not start implementing before Phase 5.

---

# PART I — THE HOST SYSTEM

**Path:** `C:\Users\cterr\Documents\10_Multi_Agent_Financiero`
**Interpreter (absolute path; `conda activate` does not persist between tool calls):**
`C:\Users\cterr\anaconda3\envs\venv-multi_gent_finantial\python.exe` (Python 3.10).
Imports are `from src...`, so **everything runs from the repository root**.

Read `CLAUDE.md` in full before anything else. It is the contract and it is current. Then read
`src/graph/workflow.py`, `src/state.py`, `src/agents/base.py`, `src/tools/__init__.py`,
`src/agents/posicionamiento.py`, `src/tools/futuros.py`, `src/tools/opciones.py`,
`src/tools/decision.py`, `src/portfolio/construccion.py`, `src/backtest/replay.py` and
`src/backtest/engine.py`.

## The six invariants you may not break

These are not style preferences. Each one is protected by a test, and each one is the reason
some earlier version of this system was wrong.

1. **No decision variable may depend on an LLM.** Agents compute their verdict with
   deterministic rules; the LLM only overwrites the text field declared in `campo_texto`.
   Verified at runtime by `assert_llm_is_decision_neutral()` in `src/backtest/replay.py`, which
   `backtest_cli.py` aborts on. **Any new decision field you add must be added to that
   comparison list.** A trained ML model is *not* an LLM and does not violate this invariant —
   it is a pure function of its inputs once the artifact is frozen. See §"ML models and the
   invariant" below for the condition that makes that true.
2. **Missing data is not zero.** Every absent magnitude travels as `None` and is declared.
   Never reintroduce a numeric default on any path. `tests/test_integridad_datos.py` fixes this.
3. **Point-in-time discipline.** XBRL facts filter by `filed <= t`, never `end`. COT reports
   filter by `fecha_publicacion`, never report date. `PriceStore.window()` cuts at `as_of`
   inclusive. This is what separates a backtest from fiction. `test_no_lookahead_*`,
   `test_fundamentals_respect_filed_not_end` and `test_serie_semanal_filtra_por_publicacion`
   protect it. **Do not relax a test to make a change pass.**
4. **One decision rule, one place.** All calculation rules live in `src/tools/` as LangChain
   tools invoked by name. A second copy of a rule — in `src/backtest/`, in an agent, in a
   notebook — is a bug. The backtest imports the *real* agent classes; it reimplements nothing.
5. **One network module.** `src/tools/extraccion.py` is the only tool module that touches the
   network. Ingestion layers under `src/data/` do the fetching and the tool delegates to them
   (the pattern of `obtener_noticias` → `src/data/news/`). `tests/test_tools.py` fixes this in
   both directions.
6. **`TOOLS_LECTURA` excludes every tool that produces a decision variable.** The exclusion is
   structural — by module, not by blacklist — and `test_el_react_no_alcanza_ninguna_tool_de_decision`
   protects it. Any new tool of yours that emits a decision variable stays out of that list.

Two more rules that cost this project real money to learn, and that you will be tempted to
break:

- **Adjustments and vetoes only ever move in one direction.** `aplicar_vetos` can only lower a
  rating. `ajustar_precio_entrada` can only lower an entry price. `factor_reflexion` can only
  shrink a weight. Each is protected by a cartesian-product test. If your new agent wants to
  raise conviction, size or entry price, you must argue why that is not "rewarding what already
  worked", and you must accept that the answer is usually no.
- **Do not invert the sign of a refuted layer to see if it works that way.** `src/memoria/` is
  implemented, tested, documented and **disabled by default** because it was measured and it
  made everything worse. Read that section of `CLAUDE.md` before proposing anything that
  resembles it. Searching the variant space over the same history until something turns
  positive is the exact methodological defect this project has already documented twice.

## Where entry-point precision currently comes from, and why it is thin

`PositioningAnalystAgent` (`src/agents/posicionamiento.py`) runs sequentially after `technical`
and produces `precio_entrada_objetivo`. It crosses three signals: a macro direction from the
COT z-score, a *price-quality* score from the options chain, and `momentum_score`. The **level**
comes only from the chain — open-interest support, max pain, gamma flip — and the macro side
contributes direction only. The final adjustment is

```
ajuste = max(−AJUSTE_MAXIMO_ATR·ATR/precio, factor · (nivel − precio)/precio)
factor ∈ {0.0 PERSEGUIR, 0.5 ESCALONAR, 1.0 ESPERAR_RETROCESO}
```

and it is never positive.

**Three concrete weaknesses. Confirm each against the code before building on it:**

- The system picks a level and then waits for it, with **no model of whether that level will
  hold**. `ESPERAR_RETROCESO` is a limit order into a falling market with no estimate of the
  probability that the retracement is a genuine support test rather than the start of a
  breakdown. Nothing in the system distinguishes those two cases.
- Symmetrically, `PERSEGUIR` enters at market with **no estimate of whether the breakout holds**.
  The only brake is the `sobreextendido` flag.
- The **backtest cannot measure any of this.** `options_data` is declared absent in the replay
  because yfinance publishes only today's chain, so in the backtest the adjustment is `None`
  and the entry price *is* the market price. `build_limitations()` says so. **The study
  currently measures a system without entry adjustment while production applies one.** Closing
  or shrinking that gap is worth more than any new signal, and you must state explicitly what
  your proposal does to it.

## The three entry points are not equivalent

`cli.py` orchestrates the batch (benchmark, COT dossier, reflection memory, portfolio
constructor). `src/web/app.py` calls `run_stock_analysis(ticker)` with all batch arguments
defaulted, so the dashboard already yields a different verdict than the CLI on the same ticker.
`backtest_cli.py` orchestrates its own. **If your new agent needs batch-level data — and a
macro/liquidity agent does — you must wire all three callers, or state explicitly which one you
left out and why.**

## ML models and the invariant

A frozen model artifact is a deterministic function, so it does not break invariant 1. It does
introduce a **new point-in-time hazard that is strictly worse than look-ahead inside a
feature**, because it is invisible: a model trained on 2015–2025 and then evaluated on 2016 is
not a backtest, it is a memory test, and no existing test in this repository will catch it.

Any model you introduce must therefore satisfy **all** of:

- Training data strictly earlier than the evaluation date. Prefer **walk-forward retraining**
  with an explicit schedule; if you freeze a single artifact, the study window starts after the
  training window ends and you say so in `build_limitations()`.
- Cross-validation that is **purged and embargoed** — reuse `PurgedGroupTimeSeriesSplit`
  (06 `src/validation/purged_cv.py`) or `PurgedKFold` / `CPCV` (03 `src/cv/`). Plain k-fold on
  overlapping financial labels is not validation, it is leakage with a number attached.
- Sample weights by **uniqueness** where labels overlap (03 `src/sampling/bootstrap.py`).
- A declared, versioned artifact path, the training window recorded inside the artifact, and a
  loader that **fails loudly** rather than degrading silently to a default probability.
- Absence of the model degrades to current behaviour exactly, the way
  `test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado` fixes that path today.
  Write the equivalent test.

## The three kinds of data source, and why the cache keys differ

The host repository already encodes the taxonomy you must reuse. Its cache keys are not a
storage detail — they are the classification of each source's historical availability:

| Source | Cache key | Kind |
|---|---|---|
| COT report | `data/cache/cot/{MERCADO}_{AÑO}.json` — keyed by **report year** | **PIT-native** |
| Options chain | `data/cache/opciones/{TICKER}_{YYYY-MM-DD}.json` — daily, **accumulative** | **PIT-archivable** |
| News dossier | `data/cache/news/{TICKER}_{YYYY-MM-DD}.json` — a datum "of today" | **No history** |

- **PIT-native** — the provider serves the past as it was known then. Each observation carries
  its own publication date, is immutable once published, and the whole history can be
  downloaded at any time. The cache key is the *vintage*, not the run day, which is exactly why
  the backtest can reuse the COT cache without reimplementing the historical selection. These
  are the only sources that may enter the decision path on day one.
- **PIT-archivable** — the provider serves only today, but each daily observation is immutable
  and worth keeping. The cache is accumulative and the files of previous days *are* the
  history. The options chain works this way, which is why its percentiles declare
  `DATOS_INSUFICIENTES` until `OPCIONES_MINIMO_DIAS_HISTORICO` observations exist rather than
  inventing a 50th percentile. **A fresh install cannot backtest such a source at all**, and
  that is the honest state of affairs, not a bug to paper over.
- **No history** — the provider serves today and the past is unrecoverable. Two of the three
  news searchers are of this kind, which is precisely why the news layer is **advisory** and is
  excluded from the replay, and why `test_news_report_does_not_alter_decision` exists. A source
  of this kind may inform the report and never the decision.

**The single most valuable thing you can find in Phase 1 is a free PIT-native replacement for
something the system currently gets from a no-history source.** That converts an advisory layer
into a measurable one, which is worth more than any new signal, because a new signal on top of
an unmeasurable base cannot be validated at all.

---

# PART II — THE FOUR SOURCE REPOSITORIES

Read each repository's `CLAUDE.md` and `README.md` first, then the modules named below. Those
paths are a **starting index built from a shallow survey, not a verified inventory** — confirm
every path, signature and semantic against the actual code before relying on it, and report
anything that has moved.

You are mining for three things and nothing else: **(a) pure functions** you can lift behind a
tool, **(b) modelling techniques** you can re-fit on this system's data, **(c) validation
machinery** that makes your own claims falsifiable. You are *not* porting intraday
infrastructure, brokers, live engines, databases or UIs.

### 1. `C:\Users\cterr\Documents\09_SDD_Copilot\02-trading-liquidez-prj` — *Aura Quantitative Command Center*

FastAPI + Streamlit monitor of global liquidity (BIS), the Fed balance sheet, and NBFI /
shadow-banking interconnection risk, with an LLM commentary panel. Clean-architecture layering:
routes → services → gateways/repository.

Look at `backend/app/services/financial_logic.py` — `BISService`, `FEDService` with
`compute_reserve_pressure`, `NBFIService` with `compute_risk_level`, and
`adjust_for_series_break`. Also `backend/app/gateways/` (BIS, FRED, NBFI) and
`backend/app/api/routes/{liquidity,risk,fed}.py`.

**What it plausibly contributes:** a *risk-appetite / systemic-stress regime* common to the
whole batch, structurally analogous to the existing COT macro dossier — direction and
permission, never a price level. **The hard part is point-in-time**: FRED and BIS series are
revised, and each has a release lag. A liquidity reading for date `t` fetched today is
look-ahead of exactly the `filed`/`end` kind this repo already solved twice. Solve it the same
way or do not use the series. Ignore the LLM analysis subsystem entirely — it violates
invariant 1 on contact.

### 2. `C:\Users\cterr\Documents\09_SDD_Copilot\06-trading-search-strategies-prj` — *ORB, Transformer + XGBoost*

Intraday Open Range Breakout outcome prediction. Three branches (triple-barrier labeling, SSL
Transformer pretraining, XGBoost classification) behind a Typer CLI, plus López de Prado
extensions.

Highest-value modules: `src/target/orb_labeler.py` (fully vectorized triple-barrier labeling),
`src/validation/purged_cv.py`, `src/validation/sample_weights.py`,
`src/classifier/meta_labeling.py` (`primary_signals`, `meta_report`, `best_threshold`),
`src/classifier/importance.py` (MDA/SFI), `src/regime/detector.py` (`detect_regimes`,
`filter_labels_by_regime`, HMM and SMA variants), `src/backtest/metrics.py`
(`probabilistic_sharpe_ratio`, `expected_max_sharpe`, `deflated_sharpe_ratio`),
`src/allocation/hrp.py`, `src/allocation/nco.py`, `src/features/frac_diff.py`,
`src/features/ta_extended.py`, `src/features/fourier_features.py`, `src/features/selection.py`.

**What it plausibly contributes:** a probability that a *breakout holds* — the missing input to
`PERSEGUIR`. Also, independently of any agent, the **deflated-Sharpe machinery that Phase 4 is
required to run on**. Note this repo's own honesty mechanism: the Transformer "lift" is defined
as `hybrid.mean_auc − baseline.mean_auc`, and the tabular baseline always trains, so the
contribution of the expensive component is always measurable. **Adopt that discipline for every
agent you add: the baseline is the current system, and the lift must be reported, not assumed.**

### 3. `C:\Users\cterr\Documents\09_SDD_Copilot\07-trading-falsa-ruptura-strategies-prj` — *Bear Trap / false breakdown*

Predicts false breakdowns using an SSL LSTM encoder + a VIX macro regime gate + XGBoost, over a
DuckDB/Parquet lake fed by pluggable connectors.

Highest-value modules: `src/target/triple_barrier.py` (`build_labels`, `_causal_levels` — note
the *causal* level construction), `src/macro/regime.py` (`compute_regime`, the
anti-falling-knife gate), `src/features/liquidity.py`, `src/features/orderflow.py`
(`add_orderflow`, `_order_book_imbalance`, CVD), `src/execution/v_reversal.py` (`ExecConfig`,
`generate_trades`, `backtest_metrics` — the breakdown → divergence → confirmation → trigger
state machine), `src/validation/purged_cv.py`.

**This is the closest match to the mission.** Its event is literally *"price broke below
prior-session support — will it recover?"*, which is the question the host system asks and
cannot answer every time it emits `ESPERAR_RETROCESO`. The `v_reversal` sequence — **do not buy
the breakdown, buy the confirmed recovery** — is directly transplantable as an entry rule at
daily granularity. Two warnings: the order-flow features (CVD, book imbalance) require IBKR
tick/depth data the host system does not have and cannot reconstruct historically, so any agent
depending on them must degrade cleanly to the yfinance path; and the whole repo is intraday, so
you must re-derive the horizons, not copy them.

### 4. `C:\Users\cterr\Documents\09_SDD_Copilot\03-trading-strategies-prj` — *LdP 7-stage backtesting platform*

The most mature of the four. A 7-stage López de Prado pipeline (information bars → FFD +
features → triple barrier + meta-labeling → sequential bootstrap → PurgedKFold + importance →
CPCV + Monte Carlo → DSR/PSR + HRP/NCO + sizing), a strategy registry with auto-registration,
and a fully separate live subsystem.

Highest-value modules: `src/labeling/meta_labeling.py`, `src/labeling/triple_barrier.py`,
`src/labeling/volatility.py`, `src/sampling/bootstrap.py`, `src/cv/purged_kfold.py`,
`src/cv/cpcv.py`, `src/features/importance.py`, `src/data/ffd.py`, `src/backtesting/metrics.py`
(`sortino_ratio`, `probabilistic_sharpe_ratio`, `deflated_sharpe_ratio`, `avg_drawdown`,
`max_drawdown_duration`), `src/risk/portfolio.py` (`denoise_cov` — Marchenko-Pastur,
`hrp_weights`, `nco_weights`), `src/risk/sizing.py` (`position_size`, `drawdown_guard`),
`src/volatility/hmm_filter.py`, `src/observability/drift.py` (PSI/KS feature drift).

**What it plausibly contributes, in descending order of expected value:** **(i) meta-labeling**
— the host system already produces the *side* deterministically; a meta-label model produces
*whether to take it and how large*, which maps onto `position_size_pct` and `peso_objetivo`
without touching `rating` at all, and is the single cleanest fit between these repositories and
the host's invariants; **(ii) `denoise_cov`** — `PortfolioConstructor` currently penalises by
mean correlation over a raw matrix, and a Marchenko-Pastur-denoised covariance is a strict
improvement with no new data; **(iii) DSR / PSR / CPCV**, which Phase 4 requires;
**(iv) `drawdown_guard`**, which the host has no equivalent of. Ignore `src/live/`, `src/api/`,
`ui/` and the broker adapters completely.

---

# PHASE 0 — DEEP READ (no code yet)

Produce `output/INCORPORACION_AGENTES.md` (in Spanish) containing:

1. **Verified inventory.** For each of the four repos: every function/class you consider
   reusable, with its real path and signature, what it computes, its input frequency
   (tick / intraday / daily / weekly / monthly), its data dependencies, and whether those data
   exist in the host system, can be obtained by it, or cannot. Mark each as `LIFT` (copy the
   pure function behind a host tool), `REFIT` (re-derive the technique on host data),
   `VALIDATE-ONLY` (use in the study, not in the decision) or `DISCARD` (with reason).
2. **Frequency gap.** The host is daily-bar and rebalances at multi-week horizons; three of the
   four sources are intraday. State, per candidate, what survives the translation and what does
   not. Anything requiring tick or depth data is `DISCARD` for the decision path unless you can
   show a daily proxy the host already ingests.
3. **Data demand list.** Every external series any candidate would need — its frequency, its
   required history depth, and what breaks without it. Do not try to source it here: carry the
   list into Phase 1, which qualifies sources properly. A candidate whose data demand cannot be
   met by a free PIT-qualified source in Phase 1 does not become an agent.
4. **Dependency check.** New heavy dependencies (torch, hmmlearn, stable-baselines3) against a
   repo whose entire offline suite runs in under five seconds. Justify each or drop it.

---

# PHASE 1 — LOOP S: FREE DATA SOURCE DISCOVERY AND POINT-IN-TIME QUALIFICATION (hard limit: 25 iterations)

**Objective:** build a catalogue of data sources that satisfy two constraints simultaneously —
**zero cost** and **reconstructible history** — and classify each one before any agent depends
on it. This phase runs *before* the agent design, because a candidate whose data cannot be
replayed is not a candidate.

## The rubric — five questions, per source, answered by inspection and not by documentation

1. **COST.** Free, free tier with limits, or paid. Paid is an immediate `DISCARD`; there is no
   negotiating this. A free tier is qualified only if its rate limits allow a full historical
   backfill of the study window within a reasonable batch, and you must state the number of
   requests that backfill costs.
2. **VINTAGE.** Can the provider return the value for date `t` *as it was known at `t`*? Name
   the exact mechanism: a real-time / as-of parameter, an archive of dated releases, or an
   immutable publication date carried per observation. "The series goes back to 1990" does not
   answer this question — a long series of *revised* values is still a look-ahead trap.
3. **COVERAGE AND CONTINUITY.** First date, last date, gaps, methodology breaks, discontinued
   series. Breaks matter: `adjust_for_series_break` exists in the 02 repository for a reason.
4. **REVISION BEHAVIOUR.** Once published, does the value for `t` change? If it does, you must
   say which vintage you consume and prove the choice is causal.
5. **TERMS AND DURABILITY.** Authentication, rate limits, terms of use, and the honest odds the
   endpoint still exists in two years. A source that disappears takes the reproducibility of
   every study that used it, unless you archived it locally — which is why the archive is
   mandatory, not optional, for anything on the decision path.

## The gate — non-negotiable

| Class | May it feed the decision path? |
|---|---|
| **PIT-NATIVE** | Yes, immediately. |
| **PIT-ARCHIVABLE** | **No** — not until the local archive covers the study window. Start the archive on day one, key it by vintage, declare the gap in `build_limitations()`, and make the agent declare `DATOS_INSUFICIENTES` in the meantime, exactly as the options percentiles do. Never substitute a neutral default for the missing history. |
| **NO-HISTORY** | **Never.** Advisory layer only, excluded from the replay, and declared absent with its motive — the treatment the news layer already receives. |

The corollary the user of this system cares about most: **no number that reaches a decision may
come from a source that cannot be replayed.** If that leaves an agent without inputs, the agent
does not ship. Report it as a negative result and move on.

## Candidate register — a starting list, not a verified one

Verify every entry by actually retrieving data. Several of these will turn out to be worse than
they look, and one or two are the whole point of this phase.

- **Macro, rates, liquidity.** FRED — and specifically **ALFRED**, its archival interface, whose
  real-time/vintage parameters make a series PIT-native *by construction*; this is the single
  most important item on this list and it is the correct answer to the 02 repository's
  point-in-time problem. Also: Treasury daily yield curve; Fed H.4.1 and H.8 releases, which
  carry release dates; BIS bulk statistics (revised, with breaks — handle accordingly); ECB and
  other central-bank statistical portals; World Bank and IMF.
- **Positioning and derivatives.** CFTC COT is the precedent already in the system. Look for
  free daily index and equity **put/call ratio history**, **VIX and its term structure**
  (short-, mid- and longer-dated volatility indices), and clearing-house aggregate volume and
  open-interest statistics. Per-ticker historical option chains are paid and you will not get
  them; an index-level options regime with real history is not a substitute for a per-ticker
  chain, but it is measurable in the backtest, which the per-ticker chain is not. Weigh that
  trade honestly.
- **Ownership, flow and shorting.** FINRA daily short-sale volume files are per-ticker, daily,
  free and archived; consolidated short interest carries settlement and publication dates;
  SEC 13F holdings are free with filing dates. All three are PIT-native by construction.
- **Fundamentals and events.** SEC EDGAR `companyfacts` is already used. Also examine the SEC
  **Financial Statement Data Sets** — quarterly bulk archives carrying accession number and
  filing date, so they are PIT by construction and far cheaper to replay than per-ticker API
  calls across a ten-year study. EDGAR full-text search and 8-K carry timestamps.
- **Factors and benchmarks.** A free academic factor library gives decades of daily factor
  returns, which would let the study report a **factor-adjusted alpha** instead of an alpha
  against a single index — a direct upgrade to how the system judges itself.
- **Prices.** An independent free EOD source as a cross-check on yfinance. Note and state the
  known problem: yfinance serves **retroactively adjusted** prices, so the 2015 price you pull
  today is not the price a 2015 observer saw. Quantify what that does to the indicators before
  dismissing it.
- **News and events with real timestamps.** Archived, timestamped news corpora and web archives
  are the only realistic free route to the **point-in-time `NewsStore`** that `CLAUDE.md` names
  as the precondition for connecting news to the decision. Building one does not by itself
  license that connection: news stays advisory until the store covers the study window and
  `test_news_report_does_not_alter_decision` is retired deliberately, with evidence.
- **Universe and survivorship.** The study declares universe survivorship as a residual bias.
  Free routes to *dated* index add/remove events exist. Closing this is worth more than most new
  signals, because survivorship biases every number the report prints, not just one agent's.

## Iteration schema — one source per iteration

```
ITER <n>/25
  SOURCE      name, endpoint, what it provides, at what frequency, for what universe
  COST        free / free tier + limits / paid          (paid ⇒ DISCARD, stop the iteration)
  VINTAGE     the exact mechanism that returns the past as it was known then
  COVERAGE    first date · last date · gaps · methodology breaks · discontinued?
  REVISIONS   is the value for t stable after publication? if not, which vintage do you take?
  LAG         publication delay, and the field that carries it
  BACKFILL    requests and wall-clock needed to fetch the whole study window once
  CLASS       PIT-NATIVE / PIT-ARCHIVABLE / NO-HISTORY
  USE         decision path / advisory only / study only / discard
  CLOSES      which declared limitation or which agent's data demand this satisfies, if any
  PROOF       the concrete retrieval you performed — an old vintage requested and returned, an
              archive file downloaded, a publication-date field inspected. Documentation is a
              claim; a response body is evidence. An iteration without PROOF does not count.
  LEDGER      cumulative catalogue
```

Rules:

- **One source per iteration, no repeats**, and every iteration consumes the previous ledger.
- **Prefer a source that closes a declared limitation over one that adds a new signal.** Closing
  the options gap, the news gap or the survivorship gap changes what the study can *measure*;
  a new signal only changes what it reports.
- **Prefer one source that serves several agents over several narrow ones.** Each source is a
  permanent maintenance and reproducibility liability.
- Every source that reaches the decision path must be reachable **only** through
  `src/tools/extraccion.py`, delegating to an ingestion layer under `src/data/`, and cached
  under `data/cache/<fuente>/` with a **vintage key** — the COT pattern, never the run-day
  pattern, for anything PIT-native.
- **Stop early** when three consecutive iterations qualify no new source. Report where you
  stopped.

## Reproducibility engineering — deliverable of this phase, not an afterthought

1. **Append-only manifest.** Every retrieval records source, endpoint, vintage or as-of,
   retrieval timestamp, row count and a content checksum. Without it, "the backtest is
   reproducible" is an assertion nobody can check.
2. **Immutable vintage-keyed cache.** Never overwrite a cached vintage. A re-fetch that returns
   different bytes for the same vintage is an **event to record and investigate** — the provider
   revised history — not something to silently overwrite. This is the property that makes a
   study from last year still reproducible today.
3. **`--offline` must reproduce the study bit for bit.** That is already a documented property
   of this repository. Verify it still holds after your changes; if a new source breaks it, the
   source is wrong, not the property.
4. **One point-in-time filter per series, in the production code.** Every new store reuses the
   production selection function with an `as_of` parameter — the `COTStore` → `serie_semanal`
   pattern. A second implementation of the PIT filter inside `src/backtest/` is a bug of the
   same class as a duplicated decision rule.
5. **Record the vintage in the report.** Every run states which vintage of every series it used,
   so two runs that disagree can be diagnosed instead of argued about.

**Phase 1 deliverable:** `output/FUENTES_DATOS.md` (in Spanish) — the full catalogue with the
rubric answers per source, the classification, the gate decision, what each one closes, and an
explicit list of the data demands from Phase 0 that **no free qualified source can meet**. That
last list is not a failure; it is the honest boundary of what this system can ever validate,
and it belongs in `build_limitations()`.

---

# PHASE 2 — CANDIDATE AGENT DESIGN (design only)

Propose **at most four** new agents. Fewer is better; two excellent ones beat four mediocre
ones. For each, specify in `output/INCORPORACION_AGENTES.md`:

- Class name, module path under `src/agents/`, and its `nombre` / `campo_texto`.
- Its **position in the graph**, and the *data dependency* that forces that position — the way
  `posicionamiento` must follow `technical` because it consumes `momentum_score`,
  `sobreextendido` and `atr`. If there is no data dependency, argue for the fan-out and check
  what it would write: only channels with reducers (`messages`, `logs`) tolerate two writers in
  one superstep, and `workflow_status` is a scalar with none.
- Its tools: one module under `src/tools/`, with the two-layer split the repo uses — a pure
  implementation (`_nombre`) with the natural signature, and an `@tool` facade that crosses the
  JSON boundary via `detalle_magnitudes` / `magnitudes_desde_detalle`. Facade docstrings are API
  documentation; they are what the ReAct investigator reads.
- Exactly which **decision variables** it writes, and by which permitted mechanism: a veto that
  only lowers, a factor that only shrinks, a level fed to `calcular_niveles_riesgo`, or a size
  input. Anything else needs an explicit argument.
- Its **new state keys** in `FinancialAnalysisState`, and their reducer if any.
- Its **degradation path** when its data is missing, and the test that fixes that path.
- Whether it is batch-level (and therefore must be wired into `cli.py`, `src/web/app.py` and
  `backtest_cli.py`) or per-ticker.
- **Its source bill of materials.** Every input, named against an entry in
  `output/FUENTES_DATOS.md`, with that entry's class. An agent whose decision variables depend
  on anything classified `NO-HISTORY` is not designed correctly — redesign it or drop it. An
  agent depending on a `PIT-ARCHIVABLE` source ships with its decision path inert until the
  archive covers the window, and says so.
- Whether the **backtest can see its inputs point-in-time**. If it cannot — as with the options
  chain today — say so, and put it in `build_limitations()`. State explicitly how much of the
  agent the study would actually be measuring, the way `CLAUDE.md` does for the positioning
  agent's two blocks: the COT half is measured, the options half is not, and the difference is
  named rather than averaged away.

---

# PHASE 3 — LOOP A: GRAPH ANALYSIS LOOP (hard limit: 20 iterations)

**Objective:** locate, with evidence, where the current graph loses entry-point precision, and
converge on a ranked set of concrete modifications.

Maintain a visible ledger. Each iteration is one hypothesis and uses this exact schema:

```
ITER <n>/20
  STATE      current graph topology + which decision variables are set by which node, in order
  HYPOTHESIS one falsifiable claim about where entry precision is lost
  EVIDENCE   file:line references, and where available a measured number from the repository
  TEST       how you would falsify it, and whether the existing backtest can measure it at all
  VERDICT    CONFIRMED / REFUTED / UNMEASURABLE-WITH-CURRENT-DATA
  DELTA      the graph or agent modification implied, or "none"
  LEDGER     cumulative ranked list of surviving modifications
```

Rules:

- **No hypothesis may be repeated**, and each iteration must consume the previous ledger.
- `UNMEASURABLE-WITH-CURRENT-DATA` is a first-class outcome and often the correct one. The
  options-chain gap is the known example. Record what would have to exist to measure it.
- At least three iterations must attack the **measurement layer itself** rather than the signal:
  if the backtest cannot see the entry adjustment, no entry improvement is provable, and fixing
  that ranks above any new signal.
- At least two iterations must test whether a **source substitution from the Phase 1 catalogue**
  converts an `UNMEASURABLE-WITH-CURRENT-DATA` verdict into a measurable one. A modification
  that turns an unmeasurable part of the system into a measurable one ranks above a
  modification that improves an already-measurable part, because the first changes what can be
  known and the second only changes a number.
- **Stop early** when two consecutive iterations produce no new surviving ledger entry. Report
  the iteration you stopped at. Burning all 20 is not a goal.
- Output: a ranked list of modifications, each with expected effect, implementation cost,
  measurability, and risk to the invariants.

---

# PHASE 4 — LOOP B: AGENT & TOOL REFINEMENT LOOP (hard limit: 40 iterations)

**Objective:** for each proposed agent and each of its tools, determine whether it can be
improved — richer input data for the ML models, a different model class, feature selection,
horizon changes, threshold changes, parameter changes — and decide which changes to keep.

**The governing rule, and the reason this loop is bounded:**

> **Every iteration that evaluates a configuration is a trial, and the trial count feeds the
> deflated Sharpe ratio directly.** `expected_max_sharpe(sharpe_std, n_trials)` in
> 06 `src/backtest/metrics.py` takes `n_trials` as an argument. You will pass the true number of
> configurations you evaluated — not one, and not the number you liked. A configuration whose
> DSR does not survive its own trial count is **discarded, not reported as an improvement.**
> This is the entire defence against the failure mode this project has already documented in
> `src/memoria/`: searching variants over one history until one comes out positive.

Each iteration uses this exact schema:

```
ITER <n>/40
  TARGET       agent + tool (or model) under examination
  REGISTERED   the hypothesis and the metric it must move — written BEFORE measuring
  CHANGE       data added / feature / model class / hyperparameter / threshold / horizon
  VALIDATION   walk-forward or CPCV split used; purge and embargo; sample weighting
  METRICS      CAGR · Sharpe · Sortino · DSR(n_trials=<running count>) · win rate ·
               profit factor · max drawdown · expectancy per trade ·
               percentile vs. random selection · alpha and its t-stat
  BASELINE     the same metrics for the unmodified system on the identical window
  LIFT         signed difference, per metric
  VERDICT      KEEP / DISCARD / NEEDS-MORE-DATA
  TRIALS       running total of configurations evaluated so far
```

Rules:

- **Register the hypothesis before measuring it.** An iteration that reports a metric it did not
  name in `REGISTERED` is not evidence.
- **Selection happens out-of-sample.** Choose on walk-forward or CPCV performance; report the
  in-sample number separately and never select on it.
- **Every configuration runs on qualified data only.** No iteration may consume a series that
  Phase 1 did not classify, nor a value the study could not have had on the date it is used. If
  a configuration cannot be evaluated because its source is `PIT-ARCHIVABLE` and the archive is
  young, the verdict is `NEEDS-MORE-DATA` — which is a real, reportable outcome and must not be
  laundered into a `KEEP` by substituting today's value for the historical one.
- **The two acceptance criteria are the ones this project already fixed for itself**: the
  *percentile versus random selection* and the *expectancy per trade*. A change that improves
  Sharpe while lowering either is refused. That is precisely the test the reflection layer
  failed, and it is why that layer is disabled.
- **Report negative results.** A refuted incorporation, measured and documented, is a valid and
  valuable deliverable of this task — this repository already carries one, deliberately.
- Budget roughly: ~10 iterations on features and input data, ~10 on model class and
  hyperparameters, ~10 on thresholds / horizons / sizing, ~10 on interactions between the new
  agents and the existing vetoes and portfolio layer. Adjust with justification.
- **Stop early** when five consecutive iterations yield no `KEEP`. Report where you stopped.
- Output: the final configuration per agent, its full metric table against baseline, the total
  trial count, and the DSR computed with that count.

---

# PHASE 5 — IMPLEMENTATION

Implement **only what survived Phase 4 with a positive verdict**, in this order:

1. **Ingestion and archive first, before anything that consumes it.** One layer per new source
   under `src/data/<fuente>/`, its network tool in `src/tools/extraccion.py` and nowhere else,
   its cache under `data/cache/<fuente>/` with a **vintage key** for PIT-native sources and an
   accumulative daily key for PIT-archivable ones. Add the append-only retrieval manifest, and
   a backfill entry point that can populate the whole study window from cold and is safe to
   re-run. A cached vintage is never overwritten.
2. Tools, under `src/tools/`, two layers each, registered in `REGISTRO_TOOLS`. Add read-only
   explanatory tools to `TOOLS_LECTURA`; keep every decision-producing tool out.
3. Agents under `src/agents/`, inheriting `AgenteBase`, implementing `decidir(state, traza)` and
   `prompt_usuario(state, informe)` only. `decidir()` runs before `_redactar()` — always.
4. System prompts in `src/prompts.py`, carrying the three shared blocks (anti-decision clause,
   absence clause, output contract). Format every figure with `_v()`.
5. Graph wiring in `src/graph/workflow.py`, plus new state keys in `src/state.py`.
6. Batch wiring in `cli.py`, `src/web/app.py` and `backtest_cli.py` for anything batch-level.
7. `src/backtest/replay.py`: execute the new agents, extend `assert_llm_is_decision_neutral()`
   with every new decision field, and add the point-in-time store for any new series — reusing
   the production selection function with an `as_of` parameter, the way `COTStore` calls
   `serie_semanal`, never a second implementation.
8. Tests, offline and deterministic, in the existing style: a monotonicity test over the
   cartesian product for anything that may only lower (mirroring
   `test_los_vetos_solo_bajan_el_rating`), a point-in-time test for every new series (mirroring
   `test_fundamentals_respect_filed_not_end` and `test_serie_semanal_filtra_por_publicacion`),
   a degradation test for every missing-input path, an "ausencia ≠ cero" test, and a
   reproducibility test. Add three more that this phase makes necessary: **(a)** every source on
   the decision path is classified `PIT-NATIVE`, or `PIT-ARCHIVABLE` with an archive that covers
   the window — asserted in code, not in prose; **(b)** appending later observations to a store
   does not change an earlier signal, the analogue of
   `test_no_lookahead_future_prices_do_not_change_past_signal` for each new series; **(c)** a
   cached vintage is never overwritten, and a differing re-fetch raises instead of replacing.
   Also add `PositioningAnalystAgent` and your new agents to the `AGENTES` list in
   `tests/test_llm_texto.py` — that list is currently missing positioning, and it is a real
   coverage hole, not an exemption.

Reference command for the deterministic suite (currently 376 tests, under 5 s):

```powershell
<python> -m pytest tests/ --ignore=tests/test_fetcher.py --ignore=tests/test_workflow.py -q
```

---

# PHASE 6 — VALIDATION AND REPORTING

1. Run the full deterministic suite. It must be green, with **no test relaxed**. If a test now
   fails legitimately because behaviour changed by design, say so explicitly and justify it.
2. Run the backtest before and after, on the identical window and regime:
   ```powershell
   <python> backtest_cli.py --start 2015-01-01 --end 2025-12-31 --regime pit
   ```
   Report both metric sets side by side. The current published baseline is CAGR 3.95%,
   Sharpe 0.68, max drawdown −13.8%, 563 trades, 44.6% hit rate, PF 1.38, expectancy +1.23%,
   percentile vs. random 7.4 — against an index CAGR of 13.51%. **The system does not beat
   buy-and-hold.** Do not soften that conclusion; state whether your change moves it.
3. **Prove reproducibility, do not assert it.** Three checks, reported with their output:
   - Run the study twice with `--offline --quiet` and diff the outputs. They must be identical
     byte for byte. Any difference is a bug — a timestamp, a set iteration order, a UUID — and
     it is fatal to the claim that the study is reproducible. Note that this repository already
     had this exact defect and fixed it by making trace identifiers sequential rather than
     random, and by keeping durations out of `Traza.a_dict()`.
   - **Cold-start replay.** Move `data/cache/` aside, backfill from the sources, re-run, and
     diff against the warm run. Differences reveal every place where a "today" value silently
     substituted for a historical one — which is precisely the failure mode this whole phase
     exists to prevent.
   - **Vintage rewind.** For each new series, query the store as of a date well inside the
     window and confirm it returns what was knowable then, not what is known now.
4. Update `build_limitations()` and `NEXT_STEPS` in `backtest_cli.py`. If you closed a listed
   limitation, remove it; if you added one — a frozen model artifact, a series without a
   reliable publication date, an archive that does not yet cover the window — add it. Add the
   Phase 1 list of data demands that no free qualified source could meet: it is a permanent
   boundary of the study, and readers are entitled to know where it lies.
5. Update `CLAUDE.md`: a section per new agent, in the voice of the existing ones — the rule,
   *the defect it prevents*, and what must not be undone. Update the graph diagram, the tools
   table, the invariant's verified-fields list, and the `src/backtest/` limitations.
6. Final report: what was incorporated, what was refuted and why, the total trial count, the DSR
   at that count, which sources now feed the decision and under which class, what the study can
   measure today that it could not before, and the honest answer to the only question that
   matters — **is the entry point measurably more precise, or does it only look that way?**

---

# HARD PROHIBITIONS

- Do not let an LLM output reach any branch or any number. Text only.
- Do not reimplement a decision rule anywhere outside `src/tools/`.
- Do not add a network call outside `src/tools/extraccion.py`.
- Do not relax, skip, or delete an existing test to make a change pass.
- Do not reintroduce a numeric default where a magnitude may be absent.
- Do not filter any historical series by anything other than its publication date.
- Do not pay for data, and do not design an agent that only works with paid data.
- Do not let a `NO-HISTORY` source reach any decision variable, however good the signal looks.
- Do not use a revised value for a past date when the provider can serve the vintage.
- Do not overwrite a cached vintage, and do not let a differing re-fetch pass silently.
- Do not substitute today's value for a missing historical one — not to fill a gap, not to
  finish a backfill, not to unblock an iteration. `DATOS_INSUFICIENTES` is the correct output.
- Do not introduce anything that makes two `--offline` runs differ: no wall-clock timestamps in
  persisted output, no unordered iteration, no random identifiers.
- Do not train on data at or after the evaluation date, and do not evaluate a frozen artifact
  inside its own training window.
- Do not report a configuration selected in-sample as an improvement.
- Do not port live-trading, broker, database or UI code from the source repositories.
- Do not present a `--regime biased` result as a system result.
- Write code, docstrings, comments and reports in **Spanish**.

# DELIVERABLES

1. `output/FUENTES_DATOS.md` — the source catalogue: rubric answers, class, gate decision, what
   each source closes, the Loop S ledger, and the data demands no free qualified source can meet.
2. `output/INCORPORACION_AGENTES.md` — inventory, agent designs with their source bill of
   materials, the Loop A ledger, the Loop B table, and the final verdict.
3. New ingestion layers under `src/data/`, their network tools in `src/tools/extraccion.py`,
   vintage-keyed caches under `data/cache/`, the append-only retrieval manifest, and a
   re-runnable backfill entry point.
4. New modules under `src/tools/` and `src/agents/`, wired into the graph and the three entry
   points, plus the point-in-time stores in `src/backtest/data.py` reusing the production
   selection functions with `as_of`.
5. New offline deterministic tests, plus the extensions to `assert_llm_is_decision_neutral()`
   and to `tests/test_llm_texto.py::AGENTES`.
6. A before/after backtest comparison on the identical window, and the three reproducibility
   proofs (double offline run, cold-start replay, vintage rewind) with their output.
7. Updated `CLAUDE.md`, `build_limitations()` and `NEXT_STEPS`.

**Begin with Phase 0. Do not write implementation code until Phase 5.**
