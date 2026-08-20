"""
Generación del informe markdown, el JSON de resultados y los gráficos.

Regla editorial aplicada en todo el módulo: cada cifra publicada lleva pegada
la etiqueta del régimen de datos que la produjo. Un CAGR sin régimen es una
cifra sin significado.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.backtest import metrics as M  # noqa: E402

REGIME_LABEL = {
    "pit": "POINT-IN-TIME (fundamentales SEC filtrados por `filed <= t`) — régimen limpio",
    "technical_only": "SOLO TÉCNICO (gatekeeper fundamental neutralizado) — régimen limpio",
    "biased": "SESGADO (fundamentales de HOY aplicados al pasado) — LOOK-AHEAD, solo contraste",
}


def _pct(x: Optional[float], nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "n/d"
    return f"{x * 100:.{nd}f}%"


def _num(x: Optional[float], nd: int = 2) -> str:
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "n/d"
    return f"{x:.{nd}f}"


def _money(x: Optional[float]) -> str:
    return "n/d" if x is None else f"${x:,.0f}"


# --------------------------------------------------------------------------- #
def plot_equity(curves: Dict[str, pd.Series], out_path: Path, title: str) -> Optional[Path]:
    curves = {k: v for k, v in curves.items() if v is not None and len(v) > 1}
    if not curves:
        return None
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    for name, s in curves.items():
        lw = 2.0 if "Estrategia" in name else 1.2
        ax1.plot(s.index, s.values, label=name, linewidth=lw)
    ax1.set_yscale("log")
    ax1.set_ylabel("Capital (escala log)")
    ax1.set_title(title)
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(alpha=0.3)

    strat = next((v for k, v in curves.items() if "Estrategia" in k), None)
    if strat is not None:
        dd = M.drawdown_series(strat)
        ax2.fill_between(dd.index, dd.values * 100, 0, alpha=0.4, color="crimson")
        ax2.set_ylabel("Drawdown (%)")
        ax2.grid(alpha=0.3)
    ax2.set_xlabel("Fecha")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


def plot_random_distribution(strategy_cagr: float, random_cagrs: np.ndarray,
                             out_path: Path) -> Optional[Path]:
    if random_cagrs is None or len(random_cagrs) == 0:
        return None
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.hist(random_cagrs * 100, bins=60, alpha=0.75, color="steelblue",
            label="Señales aleatorias (Monte Carlo)")
    ax.axvline(strategy_cagr * 100, color="crimson", linewidth=2.5,
               label=f"Estrategia ({strategy_cagr * 100:.2f}%)")
    ax.set_xlabel("CAGR (%)")
    ax.set_ylabel("Frecuencia")
    ax.set_title("Estrategia frente a la hipótesis nula de selección aleatoria")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
def _df_to_md(df: pd.DataFrame, float_fmt: str = "{:.4f}") -> str:
    if df is None or df.empty:
        return "_Sin datos._\n"
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].map(lambda v: "n/d" if pd.isna(v) else float_fmt.format(v))
    header = "| " + " | ".join([str(d.index.name or "")] + [str(c) for c in d.columns]) + " |"
    sep = "|" + "---|" * (len(d.columns) + 1)
    rows = ["| " + " | ".join([str(i)] + [str(v) for v in row]) + " |"
            for i, row in zip(d.index, d.values)]
    return "\n".join([header, sep] + rows) + "\n"


def _rating_ordering(ev: Optional[pd.DataFrame], horizon: str = "fwd_12m") -> Optional[Dict[str, Any]]:
    """
    ¿Ordena el rating correctamente el rendimiento futuro?

    Es la pregunta que decide si el sistema *sabe algo*, al margen de cómo se
    gestione la cartera. Si los valores marcados VENTA FUERTE rinden más que los
    marcados COMPRA FUERTE, el problema no está en los stops ni en el sizing:
    está en la señal.
    """
    col = f"{horizon}_media"
    if ev is None or ev.empty or col not in ev.columns:
        return None
    vals = {r: ev.loc[r, col] for r in ev.index if pd.notna(ev.loc[r, col])}
    buy = vals.get("COMPRA FUERTE")
    strong_sell = vals.get("VENTA FUERTE")
    if buy is None or strong_sell is None:
        return None
    best = max(vals, key=lambda k: vals[k])
    return {
        "compra_fuerte": float(buy),
        "venta_fuerte": float(strong_sell),
        "mejor_rating": best,
        "mejor_valor": float(vals[best]),
        "invertido": strong_sell > buy,
        "todos": {k: float(v) for k, v in vals.items()},
    }


def _verdict(strat: Dict[str, Any], bench: Dict[str, Any], tstats: Dict[str, float],
             trades: Dict[str, Any], regime: str, limitations: List[str],
             ordering: Optional[Dict[str, Any]] = None) -> str:
    n = trades.get("n_trades", 0)
    excess = strat.get("cagr", 0) - bench.get("cagr", 0)
    alpha_t = strat.get("alpha_tstat", 0.0)
    pval = tstats.get("p_value_unilateral", 1.0)

    if ordering and ordering["invertido"]:
        head = ("**NO.** Y el motivo es más grave que el rendimiento: **el rating no ordena "
                "el futuro en la dirección que afirma.** Los valores calificados VENTA FUERTE "
                f"rindieron de media {_pct(ordering['venta_fuerte'])} a 12 meses, frente al "
                f"{_pct(ordering['compra_fuerte'])} de los COMPRA FUERTE.\n\n"
                "  Matiz obligado antes de concluir que la señal está *invertida*: el sesgo de "
                "supervivencia golpea de forma desigual a cada categoría. VENTA FUERTE recoge "
                "sobre todo empresas con fundamentales deteriorados, y de esas solo están en el "
                "universo las que sobrevivieron hasta hoy — precisamente las que se recuperaron. "
                "La lectura defendible es más prudente: **el rating no separa ganadores de "
                "perdedores**, y el signo aparente de la inversión no puede afirmarse sin "
                "composiciones históricas del índice.")
    elif n < 30:
        head = ("**NO CONCLUYENTE.** La muestra de operaciones es demasiado pequeña "
                f"({n} operaciones) para distinguir habilidad de azar.")
    elif excess > 0 and abs(alpha_t) > 2 and pval < 0.05:
        head = ("**SÍ, con reservas.** La estrategia bate al índice con alfa "
                "estadísticamente significativo y supera la nula aleatoria.")
    elif excess > 0:
        head = ("**NO CONCLUYENTE.** La estrategia rinde por encima del índice, pero el "
                "exceso no alcanza significancia estadística: es compatible con suerte.")
    else:
        head = ("**NO.** La estrategia no ha sido rentable frente a comprar y mantener "
                "el índice en el periodo analizado.")

    lines = [
        head,
        "",
        f"- Régimen de datos del resultado principal: {REGIME_LABEL[regime]}",
        f"- CAGR estrategia {_pct(strat.get('cagr'))} vs SPY {_pct(bench.get('cagr'))} "
        f"(exceso {_pct(excess)}); Sharpe {_num(strat.get('sharpe'))} vs {_num(bench.get('sharpe'))}.",
        f"- Máximo drawdown {_pct(strat.get('max_drawdown'))}; {n} operaciones; "
        f"tasa de acierto {_pct(trades.get('hit_rate'))} frente al "
        f"{_pct(M.breakeven_hit_rate())} de equilibrio que exige el R:R 1.75 del sistema.",
        f"- Alfa anualizado {_pct(strat.get('alpha_annual'))} (t={_num(alpha_t)}); "
        f"percentil frente a señales aleatorias: {_num(tstats.get('percentil_vs_aleatorio'), 1)}.",
    ]
    if ordering:
        lines.append(
            f"- Rendimiento medio a 12 meses por rating: "
            + " · ".join(f"{k} {_pct(v)}" for k, v in sorted(
                ordering["todos"].items(), key=lambda kv: -kv[1]))
            + f". El mejor es **{ordering['mejor_rating']}**.")
    lines += [
        "",
        "**Las tres limitaciones más serias, antes de cualquier lectura positiva:**",
    ]
    lines += [f"{i}. {lim}" for i, lim in enumerate(limitations[:3], 1)]
    return "\n".join(lines)


def generate_report(results: Dict[str, Any], out_dir: Path) -> Path:
    """Escribe `backtest_report.md`, `backtest_results.json` y los PNG."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    regime = results["regime"]
    cfg = results["config"]
    strat_eq = results["equity"]
    curves = results["curves"]
    strat = results["summary"]["strategy"]
    bench_spy = results["summary"].get("spy", {})
    bench_ew = results["summary"].get("equal_weight", {})
    tstats = results.get("random_test", {})
    tstat_trades = results["trade_stats"]
    limitations = results["limitations"]

    eq_png = plot_equity(curves, out_dir / f"backtest_equity_{regime}.png",
                         f"Curva de capital — régimen {regime}")
    mc_png = plot_random_distribution(strat.get("cagr", 0.0),
                                      results.get("random_cagrs", np.array([])),
                                      out_dir / f"backtest_montecarlo_{regime}.png")

    md: List[str] = []
    a = md.append
    a("# Backtest del sistema multi-agente de recomendaciones de compra\n")
    a(f"_Generado el {datetime.now():%Y-%m-%d %H:%M}._\n")
    a(f"> **Régimen de datos:** {REGIME_LABEL[regime]}\n")

    ordering = _rating_ordering(results.get("event_study"))
    a("## 1. Veredicto ejecutivo\n")
    a(_verdict(strat, bench_spy, tstats, tstat_trades, regime, limitations, ordering) + "\n")

    a("\n## 2. Estrategia frente a los benchmarks\n")
    rows = {"Estrategia": strat}
    if bench_spy:
        rows["SPY comprar y mantener"] = bench_spy
    if bench_ew:
        rows["Universo equiponderado"] = bench_ew
    comp = pd.DataFrame({
        "CAGR": {k: _pct(v.get("cagr")) for k, v in rows.items()},
        "Retorno total": {k: _pct(v.get("total_return")) for k, v in rows.items()},
        "Volatilidad": {k: _pct(v.get("volatility")) for k, v in rows.items()},
        "Sharpe": {k: _num(v.get("sharpe")) for k, v in rows.items()},
        "Sortino": {k: _num(v.get("sortino")) for k, v in rows.items()},
        "Calmar": {k: _num(v.get("calmar")) for k, v in rows.items()},
        "Máx. drawdown": {k: _pct(v.get("max_drawdown")) for k, v in rows.items()},
        "Capital final": {k: _money(v.get("final_capital")) for k, v in rows.items()},
    })
    comp.index.name = "Cartera"
    a(_df_to_md(comp))

    if tstats:
        prof = results.get("mc_profile", {})
        a("\n**Contraste contra selección aleatoria (Monte Carlo, hipótesis nula):**\n")
        a(f"Las carteras aleatorias replican el perfil observado de la estrategia — "
          f"{prof.get('n_positions', '?')} posiciones simultáneas, "
          f"{prof.get('avg_holding_days', '?')} días de tenencia media y "
          f"{_pct(prof.get('gross_exposure'))} de exposición bruta — pero eligen los valores al "
          f"azar. Aísla la habilidad de selección de la mera exposición al mercado.\n")
        a(f"- CAGR medio de las carteras aleatorias: {_pct(tstats.get('aleatorio_media_cagr'))} "
          f"(p05 {_pct(tstats.get('aleatorio_p05_cagr'))}, p95 {_pct(tstats.get('aleatorio_p95_cagr'))}).")
        a(f"- La estrategia queda en el percentil **{_num(tstats.get('percentil_vs_aleatorio'), 1)}** "
          f"de esa distribución. p-valor unilateral: **{_num(tstats.get('p_value_unilateral'), 4)}**.\n")

    a("\n## 3. Métricas completas de la estrategia\n")
    full = pd.DataFrame({"Valor": {
        "Periodo": f"{strat.get('start')} → {strat.get('end')}",
        "Años": _num(strat.get("years"), 1),
        "Capital inicial": _money(strat.get("initial_capital")),
        "Capital final": _money(strat.get("final_capital")),
        "Retorno total": _pct(strat.get("total_return")),
        "CAGR": _pct(strat.get("cagr")),
        "Volatilidad anualizada": _pct(strat.get("volatility")),
        "Sharpe": _num(strat.get("sharpe")),
        "Sortino": _num(strat.get("sortino")),
        "Calmar": _num(strat.get("calmar")),
        "Máximo drawdown": _pct(strat.get("max_drawdown")),
        "Duración máx. del drawdown (días)": str(strat.get("max_drawdown_days")),
        "VaR 95% diario": _pct(strat.get("var_95")),
        "CVaR 95% diario": _pct(strat.get("cvar_95")),
        "Mejor año": _pct(strat.get("best_year")),
        "Peor año": _pct(strat.get("worst_year")),
        "Beta vs SPY": _num(strat.get("beta")),
        "Alfa anualizado vs SPY": _pct(strat.get("alpha_annual")),
        "t-stat del alfa": _num(strat.get("alpha_tstat")),
        "R² vs SPY": _num(strat.get("r_squared")),
        "Exposición bruta media": _pct(results.get("avg_exposure")),
        "Posiciones simultáneas medias": _num(results.get("avg_open_positions"), 1),
        "Rotación anualizada": _num(results.get("turnover")),
        "Costes totales pagados": _money(results.get("total_costs")),
        "—— Operaciones ——": "",
        "Número de operaciones": str(tstat_trades.get("n_trades", 0)),
        "Tasa de acierto": _pct(tstat_trades.get("hit_rate")),
        "Tasa de equilibrio exigida (R:R 1.75)": _pct(M.breakeven_hit_rate()),
        "Profit factor": _num(tstat_trades.get("profit_factor")),
        "Ganancia media": _pct(tstat_trades.get("avg_win_pct")),
        "Pérdida media": _pct(tstat_trades.get("avg_loss_pct")),
        "Esperanza por operación": _pct(tstat_trades.get("expectancy_pct")),
        "Días medios en cartera": _num(tstat_trades.get("avg_holding_days"), 1),
        "Mejor operación": _pct(tstat_trades.get("best_trade_pct")),
        "Peor operación": _pct(tstat_trades.get("worst_trade_pct")),
    }})
    full.index.name = "Métrica"
    a(_df_to_md(full))

    boot = results.get("bootstrap", {})
    if boot:
        a("\n**Intervalo de confianza del CAGR (bootstrap de retornos diarios, 2000 muestras):** "
          f"p05 {_pct(boot.get('cagr_p05'))} · mediana {_pct(boot.get('cagr_p50'))} · "
          f"p95 {_pct(boot.get('cagr_p95'))}. Probabilidad de CAGR negativo: "
          f"{_pct(boot.get('prob_cagr_negativo'))}.\n")

    a("\n## 4. Curva de capital y drawdown\n")
    if eq_png:
        a(f"![Curva de capital]({eq_png.name})\n")
    if mc_png:
        a(f"\n![Monte Carlo]({mc_png.name})\n")

    yearly = strat.get("calendar_year_returns", {})
    if yearly:
        a("\n**Rentabilidad por año natural:**\n")
        ydf = pd.DataFrame({"Estrategia": {k: _pct(v) for k, v in yearly.items()}})
        if bench_spy.get("calendar_year_returns"):
            ydf["SPY"] = {k: _pct(v) for k, v in bench_spy["calendar_year_returns"].items()}
        ydf.index.name = "Año"
        a(_df_to_md(ydf))

    a("\n## 5. Atribución\n")
    for label, df in [("Por rating de entrada", results.get("attr_rating")),
                      ("Por sector", results.get("attr_sector")),
                      ("Por motivo de salida", results.get("attr_exit")),
                      ("Por año de salida", results.get("attr_year"))]:
        a(f"\n### {label}\n")
        a(_df_to_md(df))

    ev = results.get("event_study")
    if ev is not None and not ev.empty:
        a("\n### Event study: rendimiento futuro por rating\n")
        a("Independiente del gestor de cartera: mide si el rating por sí solo anticipa "
          "el movimiento posterior del precio. Es la prueba más limpia de poder predictivo.\n")
        a(_df_to_md(ev))

    sub = results.get("subperiods")
    if sub is not None and not sub.empty:
        a("\n## 6. Robustez por subperiodo\n")
        a(_df_to_md(sub))

    sens = results.get("sensitivity")
    if sens is not None and not sens.empty:
        a("\n## 7. Sensibilidad a costes de transacción\n")
        a(_df_to_md(sens))

    a("\n## 8. Limitaciones y sesgos residuales\n")
    a("Esta sección no se suaviza. Cada punto es una razón concreta por la que el "
      "resultado de arriba podría no repetirse fuera de muestra.\n")
    for i, lim in enumerate(limitations, 1):
        a(f"{i}. {lim}")

    a("\n## 9. Próximos pasos para reforzar la validez\n")
    for i, step in enumerate(results["next_steps"], 1):
        a(f"{i}. {step}")

    a("\n---\n")
    a("### Reproducibilidad\n")
    a("```\n" + results["command"] + "\n```\n")
    a(f"Configuración: {json.dumps(cfg, ensure_ascii=False)}\n")
    if results.get("skips"):
        a(f"\nSeñales descartadas por falta de datos: `{json.dumps(results['skips'], ensure_ascii=False)}`\n")

    report_path = out_dir / "backtest_report.md"
    report_path.write_text("\n".join(md), encoding="utf-8")

    # JSON de resultados
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "regime": regime,
        "regime_label": REGIME_LABEL[regime],
        "config": cfg,
        "command": results["command"],
        "strategy": strat,
        "spy": bench_spy,
        "equal_weight": bench_ew,
        "trade_stats": tstat_trades,
        "random_test": tstats,
        "bootstrap": boot,
        "breakeven_hit_rate": M.breakeven_hit_rate(),
        "avg_exposure": results.get("avg_exposure"),
        "turnover": results.get("turnover"),
        "total_costs": results.get("total_costs"),
        "skips": results.get("skips"),
        "limitations": limitations,
        "next_steps": results["next_steps"],
    }
    (out_dir / "backtest_results.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    # Curva de capital cruda, para auditar
    strat_eq.to_csv(out_dir / f"backtest_equity_{regime}.csv", header=["equity"])
    if results.get("trades") is not None and not results["trades"].empty:
        results["trades"].to_csv(out_dir / f"backtest_trades_{regime}.csv", index=False)

    return report_path
