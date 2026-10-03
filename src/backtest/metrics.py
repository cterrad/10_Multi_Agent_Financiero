"""
Métricas de rendimiento, riesgo, atribución y significancia estadística.

Todo se calcula sobre la curva de capital diaria y el registro de operaciones.
Ninguna función aquí conoce la estrategia: reciben series y devuelven números.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


# --------------------------------------------------------------------------- #
# Rendimiento y riesgo
# --------------------------------------------------------------------------- #
def daily_returns(equity: pd.Series) -> pd.Series:
    return equity.pct_change().dropna()


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] <= 0:
        return 0.0
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    if years <= 0:
        return 0.0
    return float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1)


def annualized_vol(rets: pd.Series) -> float:
    return float(rets.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(rets) > 1 else 0.0


def sharpe(rets: pd.Series, rf: float = 0.0) -> float:
    if len(rets) < 2:
        return 0.0
    excess = rets - rf / TRADING_DAYS
    sd = excess.std(ddof=1)
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS)) if sd > 0 else 0.0


def sortino(rets: pd.Series, rf: float = 0.0) -> float:
    if len(rets) < 2:
        return 0.0
    excess = rets - rf / TRADING_DAYS
    downside = excess[excess < 0]
    dd = downside.std(ddof=1) if len(downside) > 1 else 0.0
    return float(excess.mean() / dd * np.sqrt(TRADING_DAYS)) if dd and dd > 0 else 0.0


def drawdown_series(equity: pd.Series) -> pd.Series:
    return equity / equity.cummax() - 1.0


def max_drawdown(equity: pd.Series) -> float:
    return float(drawdown_series(equity).min()) if len(equity) else 0.0


def max_drawdown_duration_days(equity: pd.Series) -> int:
    """Racha más larga por debajo del máximo histórico previo."""
    if len(equity) < 2:
        return 0
    under = equity < equity.cummax()
    longest = current = 0
    start: Optional[pd.Timestamp] = None
    for date, flag in under.items():
        if flag:
            if start is None:
                start = date
            current = (date - start).days
            longest = max(longest, current)
        else:
            start = None
    return int(longest)


def calmar(equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    return float(cagr(equity) / mdd) if mdd > 1e-9 else 0.0


def var_cvar(rets: pd.Series, level: float = 0.95) -> Dict[str, float]:
    if len(rets) < 20:
        return {"var": 0.0, "cvar": 0.0}
    q = float(np.quantile(rets, 1 - level))
    tail = rets[rets <= q]
    return {"var": q, "cvar": float(tail.mean()) if len(tail) else q}


def calendar_year_returns(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return pd.Series(dtype=float)
    yearly = equity.resample("YE").last()
    first = pd.Series([equity.iloc[0]], index=[equity.index[0] - pd.Timedelta(days=1)])
    joined = pd.concat([first, yearly])
    out = joined.pct_change().dropna()
    out.index = [d.year for d in out.index]
    return out


def alpha_beta(rets: pd.Series, bench: pd.Series, rf: float = 0.0) -> Dict[str, float]:
    """Regresión OLS de los excesos diarios. Alfa anualizado y su t-stat."""
    joined = pd.concat([rets, bench], axis=1, join="inner").dropna()
    if len(joined) < 30:
        return {"alpha_annual": 0.0, "beta": 0.0, "alpha_tstat": 0.0, "r_squared": 0.0}
    y = joined.iloc[:, 0].values - rf / TRADING_DAYS
    x = joined.iloc[:, 1].values - rf / TRADING_DAYS
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    a, b = float(coef[0]), float(coef[1])
    resid = y - X @ coef
    n, k = len(y), 2
    dof = n - k
    if dof <= 0:
        return {"alpha_annual": a * TRADING_DAYS, "beta": b, "alpha_tstat": 0.0, "r_squared": 0.0}
    s2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se_a = float(np.sqrt(s2 * xtx_inv[0, 0]))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(resid @ resid) / ss_tot if ss_tot > 0 else 0.0
    return {
        "alpha_annual": a * TRADING_DAYS,
        "beta": b,
        "alpha_tstat": a / se_a if se_a > 0 else 0.0,
        "r_squared": r2,
    }


def performance_summary(equity: pd.Series, bench: Optional[pd.Series] = None,
                        rf: float = 0.0) -> Dict[str, Any]:
    if equity is None or len(equity) < 2:
        return {"error": "curva de capital insuficiente"}
    rets = daily_returns(equity)
    yearly = calendar_year_returns(equity)
    out = {
        "start": str(equity.index[0].date()),
        "end": str(equity.index[-1].date()),
        "years": (equity.index[-1] - equity.index[0]).days / 365.25,
        "initial_capital": float(equity.iloc[0]),
        "final_capital": float(equity.iloc[-1]),
        "total_return": float(equity.iloc[-1] / equity.iloc[0] - 1),
        "cagr": cagr(equity),
        "volatility": annualized_vol(rets),
        "sharpe": sharpe(rets, rf),
        "sortino": sortino(rets, rf),
        "calmar": calmar(equity),
        "max_drawdown": max_drawdown(equity),
        "max_drawdown_days": max_drawdown_duration_days(equity),
        "best_year": float(yearly.max()) if len(yearly) else 0.0,
        "worst_year": float(yearly.min()) if len(yearly) else 0.0,
        "positive_days_pct": float((rets > 0).mean()) if len(rets) else 0.0,
        "calendar_year_returns": {int(k): float(v) for k, v in yearly.items()},
    }
    out.update({f"{k}_95": v for k, v in var_cvar(rets, 0.95).items()})
    if bench is not None and len(bench) > 1:
        b = daily_returns(bench)
        out.update(alpha_beta(rets, b, rf))
    return out


# --------------------------------------------------------------------------- #
# Operaciones
# --------------------------------------------------------------------------- #
def trade_stats(trades: pd.DataFrame) -> Dict[str, Any]:
    if trades is None or trades.empty:
        return {"n_trades": 0}
    wins = trades[trades["pnl"] > 0]
    losses = trades[trades["pnl"] <= 0]
    gross_win = float(wins["pnl"].sum())
    gross_loss = float(abs(losses["pnl"].sum()))
    hit = len(wins) / len(trades)
    avg_win = float(wins["ret"].mean()) if len(wins) else 0.0
    avg_loss = float(losses["ret"].mean()) if len(losses) else 0.0
    return {
        "n_trades": int(len(trades)),
        "hit_rate": hit,
        "profit_factor": gross_win / gross_loss if gross_loss > 0 else float("inf"),
        "avg_win_pct": avg_win,
        "avg_loss_pct": avg_loss,
        "avg_trade_pct": float(trades["ret"].mean()),
        "median_trade_pct": float(trades["ret"].median()),
        "expectancy_pct": hit * avg_win + (1 - hit) * avg_loss,
        "avg_holding_days": float(trades["holding_days"].mean()),
        "best_trade_pct": float(trades["ret"].max()),
        "worst_trade_pct": float(trades["ret"].min()),
        "total_pnl": float(trades["pnl"].sum()),
        "exit_reason_counts": trades["exit_reason"].value_counts().to_dict(),
    }


def breakeven_hit_rate(reward_atr: float = 3.5, risk_atr: float = 2.0) -> float:
    """
    Tasa de acierto mínima para no perder dinero con el R:R que impone el
    sistema (fund_manager.py:61-62): TP = +3.5·ATR, SL = -2.0·ATR.
        p·R - (1-p)·1 = 0  ->  p = 1 / (1 + R)
    """
    r = reward_atr / risk_atr
    return 1.0 / (1.0 + r)


def attribution(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    if trades is None or trades.empty or by not in trades.columns:
        return pd.DataFrame()
    g = trades.groupby(by)
    return pd.DataFrame({
        "n": g.size(),
        "hit_rate": g["pnl"].apply(lambda s: float((s > 0).mean())),
        "avg_ret": g["ret"].mean(),
        "total_pnl": g["pnl"].sum(),
        "avg_holding_days": g["holding_days"].mean(),
    }).sort_values("total_pnl", ascending=False)


def attribution_by_year(trades: pd.DataFrame) -> pd.DataFrame:
    if trades is None or trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["year"] = pd.to_datetime(t["exit_date"]).dt.year
    return attribution(t, "year").sort_index()


def turnover(trades: pd.DataFrame, equity: pd.Series) -> float:
    """Rotación anualizada: notional negociado / capital medio / años."""
    if trades is None or trades.empty or equity.empty:
        return 0.0
    notional = float((trades["shares"] * trades["entry_price"]).sum()
                     + (trades["shares"] * trades["exit_price"]).sum())
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    avg_eq = float(equity.mean())
    return notional / avg_eq / years if avg_eq > 0 and years > 0 else 0.0


# --------------------------------------------------------------------------- #
# Event study: ¿predice algo el rating, al margen del gestor de cartera?
# --------------------------------------------------------------------------- #
def event_study(signals: List[Any], price_data: Dict[str, pd.DataFrame],
                horizons_months: tuple = (1, 3, 6, 12)) -> pd.DataFrame:
    """
    Rendimiento futuro a 1/3/6/12 meses tras cada señal, agrupado por rating.

    Es la prueba más limpia del poder predictivo: no depende del sizing, ni de
    los stops, ni de la gestión de efectivo. Si aquí no hay separación entre
    COMPRA FUERTE y VENTA, el sistema no aporta información.
    """
    rows = []
    for s in signals:
        df = price_data.get(s.ticker)
        if df is None:
            continue
        fut = df.loc[df.index > s.date, "Close"]
        if fut.empty:
            continue
        entry = float(fut.iloc[0])
        rec = {"ticker": s.ticker, "date": s.date, "rating": s.rating,
               "momentum": s.momentum, "sector": s.sector,
               # Estilo y convicción del Analista de Calidad. Permiten preguntar
               # al event study si el sistema falla en un estilo concreto —el
               # gatekeeper descarta sistemáticamente el value y las
               # recuperaciones cíclicas— o de forma transversal.
               "estilo": getattr(s, "estilo", None),
               "conviccion": getattr(s, "conviccion", None)}
        for h in horizons_months:
            tgt = s.date + pd.DateOffset(months=h)
            win = fut.loc[fut.index <= tgt]
            rec[f"fwd_{h}m"] = float(win.iloc[-1] / entry - 1) if len(win) >= 2 else np.nan
        rows.append(rec)

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    g = df.groupby("rating")
    summary = pd.DataFrame({"n": g.size()})
    for h in horizons_months:
        col = f"fwd_{h}m"
        summary[f"{col}_media"] = g[col].mean()
        summary[f"{col}_mediana"] = g[col].median()
        summary[f"{col}_pct_positivo"] = g[col].apply(
            lambda s: float((s > 0).mean()) if s.notna().any() else np.nan)
        # t-stat de una muestra: ¿es la media distinta de cero?
        summary[f"{col}_tstat"] = g[col].apply(
            lambda s: float(s.mean() / (s.std(ddof=1) / np.sqrt(s.notna().sum())))
            if s.notna().sum() > 2 and s.std(ddof=1) > 0 else np.nan)
    return summary


# --------------------------------------------------------------------------- #
# Significancia
# --------------------------------------------------------------------------- #
def bootstrap_cagr(equity: pd.Series, n: int = 2000, seed: int = 42) -> Dict[str, float]:
    """Intervalo de confianza del CAGR remuestreando los retornos diarios con reemplazo."""
    rets = daily_returns(equity)
    if len(rets) < 30:
        return {}
    rng = np.random.default_rng(seed)
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    vals = rets.values
    sims = np.empty(n)
    for i in range(n):
        sample = rng.choice(vals, size=len(vals), replace=True)
        sims[i] = float(np.prod(1 + sample)) ** (1 / years) - 1
    return {
        "cagr_p05": float(np.percentile(sims, 5)),
        "cagr_p50": float(np.percentile(sims, 50)),
        "cagr_p95": float(np.percentile(sims, 95)),
        "prob_cagr_negativo": float((sims < 0).mean()),
    }


def percentile_vs_random(strategy_cagr: float, random_cagrs: np.ndarray) -> Dict[str, float]:
    if random_cagrs is None or len(random_cagrs) == 0:
        return {}
    return {
        "percentil_vs_aleatorio": float((random_cagrs < strategy_cagr).mean() * 100),
        "aleatorio_media_cagr": float(np.mean(random_cagrs)),
        "aleatorio_p05_cagr": float(np.percentile(random_cagrs, 5)),
        "aleatorio_p95_cagr": float(np.percentile(random_cagrs, 95)),
        "p_value_unilateral": float((random_cagrs >= strategy_cagr).mean()),
    }


# --------------------------------------------------------------------------- #
# Sharpe probabilístico y deflactado (López de Prado 2012, 2014)
# --------------------------------------------------------------------------- #
# Levantados de `src/backtest/metrics.py` del repositorio 06. El anfitrión no
# tenía ninguno de los dos, y es un hueco real de su capa de métricas: un Sharpe
# a secas es una estimación puntual que ignora la longitud del registro, la
# asimetría y las colas de la distribución, y sobre todo ignora que el mejor de
# MUCHAS variantes probadas está sesgado al alza por selección.
#
# Es exactamente la defensa que este proyecto necesita contra el defecto que ya
# documentó dos veces: buscar en el espacio de variantes sobre el mismo
# histórico hasta que una salga positiva.

_EULER_MASCHERONI = 0.5772156649015329


def observed_sharpe(rets: pd.Series) -> float:
    """Sharpe POR PERIODO, sin anualizar. Es la unidad que PSR y DSR usan."""
    r = pd.Series(rets).dropna()
    if len(r) < 2:
        return float("nan")
    sd = float(r.std(ddof=1))
    return 0.0 if sd == 0 else float(r.mean() / sd)


def probabilistic_sharpe_ratio(rets: pd.Series, benchmark_sr: float = 0.0) -> float:
    """
    P(Sharpe verdadero por periodo > `benchmark_sr`), en [0, 1].

    Corrige por longitud del registro, asimetría y curtosis. Una serie corta y
    con colas gruesas necesita un Sharpe observado mucho mayor para sostener la
    misma afirmación que una larga y normal.
    """
    from scipy.stats import kurtosis, norm, skew

    r = pd.Series(rets).dropna().to_numpy(dtype=float)
    n = len(r)
    if n < 3:
        return float("nan")
    sr = observed_sharpe(pd.Series(r))
    if not np.isfinite(sr):
        return float("nan")
    g3 = float(skew(r))
    g4 = float(kurtosis(r, fisher=False))
    denom = np.sqrt(max(1e-12, 1.0 - g3 * sr + (g4 - 1.0) / 4.0 * sr ** 2))
    if not np.isfinite(denom) or denom == 0:
        return float("nan")
    return float(norm.cdf((sr - benchmark_sr) * np.sqrt(n - 1) / denom))


def expected_max_sharpe(sharpe_std: float, n_trials: int) -> float:
    """
    Sharpe máximo ESPERADO por azar tras `n_trials` configuraciones probadas.

    Aproximación de valor extremo de López de Prado (2014). Escala con la
    dispersión de los Sharpe entre variantes: una búsqueda más amplia infla el
    listón que la estrategia tiene que superar para no ser un hallazgo del azar.

    `n_trials` es el número REAL de configuraciones evaluadas. No es uno, y no
    es el número que convenga: pasar un recuento menor del real es la forma
    exacta de que este control deje de controlar nada.
    """
    from scipy.stats import norm

    if n_trials < 2 or sharpe_std <= 0:
        return 0.0
    g = _EULER_MASCHERONI
    z_hi = float(norm.ppf(1.0 - 1.0 / n_trials))
    z_lo = float(norm.ppf(1.0 - 1.0 / (n_trials * np.e)))
    return float(sharpe_std * ((1.0 - g) * z_hi + g * z_lo))


def deflated_sharpe_ratio(rets: pd.Series, n_trials: int,
                          sharpe_std: Optional[float] = None,
                          trial_sharpes: Optional[List[float]] = None) -> Dict[str, Any]:
    """
    Sharpe deflactado: PSR contra el listón del máximo esperado por azar.

    Se le pasa o bien `sharpe_std` —la dispersión de los Sharpe de las variantes
    evaluadas— o bien `trial_sharpes`, la lista completa, de la que se deducen
    tanto la dispersión como el recuento.

    Un DSR por debajo de 0.95 significa que el resultado NO sobrevive a su
    propio recuento de ensayos, y en ese caso la configuración se descarta en
    lugar de reportarse como mejora.
    """
    if trial_sharpes is not None and len(trial_sharpes) > 1:
        arr = np.asarray(trial_sharpes, dtype=float)
        sharpe_std = float(arr.std(ddof=1))
        n_trials = int(len(arr))
    if sharpe_std is None:
        raise ValueError("deflated_sharpe_ratio necesita sharpe_std o trial_sharpes")

    sr_estrella = expected_max_sharpe(sharpe_std, n_trials)
    dsr = probabilistic_sharpe_ratio(rets, benchmark_sr=sr_estrella)
    return {
        "dsr": dsr,
        "psr_vs_cero": probabilistic_sharpe_ratio(rets, benchmark_sr=0.0),
        "sharpe_observado_periodo": observed_sharpe(rets),
        "sharpe_maximo_esperado": sr_estrella,
        "n_trials": int(n_trials),
        "sharpe_std_ensayos": round(float(sharpe_std), 6),
        "supera": bool(np.isfinite(dsr) and dsr >= 0.95),
    }
