"""
Simulador de cartera.

Convenciones de ejecución (todas conservadoras a propósito):

1. La señal se calcula con el CIERRE de la sesión de rebalanceo `t` y se ejecuta
   a la APERTURA de `t+1`. Nunca se rellena en la misma barra que genera la señal.
2. Los stops y objetivos se evalúan intradía contra el rango High/Low. Si en la
   misma barra se tocan ambos, se asume el PEOR caso: salta el stop.
3. Si el precio abre con hueco más allá del stop, se rellena en la apertura, no
   en el stop.
4. Comisión y slippage se aplican en cada lado, siempre en contra.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from src.backtest.replay import Signal


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_gross_exposure: float = 1.0
    max_holding_days: Optional[int] = None   # None = sin límite temporal
    allow_resize: bool = False               # no reescalar posiciones existentes

    @property
    def commission(self) -> float:
        return self.commission_bps / 10_000.0

    @property
    def slippage(self) -> float:
        return self.slippage_bps / 10_000.0


@dataclass
class Position:
    ticker: str
    shares: float
    entry_price: float
    entry_date: pd.Timestamp
    stop: Optional[float]
    target: Optional[float]
    rating: str
    sector: str
    cost_basis: float          # efectivo desembolsado, comisión incluida


@dataclass
class Trade:
    ticker: str
    sector: str
    rating: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    shares: float
    exit_reason: str
    pnl: float
    ret: float
    holding_days: int


class PortfolioEngine:
    """Contabilidad de la cartera. No conoce ni una regla de decisión."""

    def __init__(self, price_data: Dict[str, pd.DataFrame], config: BacktestConfig):
        self.px = price_data
        self.cfg = config
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity: Dict[pd.Timestamp, float] = {}
        self.exposure: Dict[pd.Timestamp, float] = {}
        self.n_open: Dict[pd.Timestamp, int] = {}
        self.total_costs = 0.0
        self._pending: List[Dict[str, Any]] = []

    # ---------------- utilidades de precio ----------------
    def _bar(self, ticker: str, date: pd.Timestamp) -> Optional[pd.Series]:
        df = self.px.get(ticker)
        if df is None or date not in df.index:
            return None
        return df.loc[date]

    def _last_close(self, ticker: str, date: pd.Timestamp) -> Optional[float]:
        df = self.px.get(ticker)
        if df is None:
            return None
        sub = df.loc[df.index <= date, "Close"]
        return float(sub.iloc[-1]) if len(sub) else None

    # ---------------- valoración ----------------
    def market_value(self, date: pd.Timestamp) -> float:
        total = 0.0
        for pos in self.positions.values():
            px = self._last_close(pos.ticker, date)
            if px is not None:
                total += pos.shares * px
        return total

    def equity_at(self, date: pd.Timestamp) -> float:
        return self.cash + self.market_value(date)

    # ---------------- órdenes ----------------
    def schedule(self, orders: List[Dict[str, Any]]) -> None:
        """Encola órdenes para ejecutarse en la apertura de la siguiente sesión."""
        self._pending.extend(orders)

    def _execute_sell(self, pos: Position, date: pd.Timestamp, price: float, reason: str) -> None:
        fill = price * (1 - self.cfg.slippage)
        gross = pos.shares * fill
        commission = gross * self.cfg.commission
        self.cash += gross - commission
        self.total_costs += commission + pos.shares * price * self.cfg.slippage

        proceeds = gross - commission
        pnl = proceeds - pos.cost_basis
        self.trades.append(Trade(
            ticker=pos.ticker, sector=pos.sector, rating=pos.rating,
            entry_date=pos.entry_date, entry_price=pos.entry_price,
            exit_date=date, exit_price=fill, shares=pos.shares,
            exit_reason=reason, pnl=pnl,
            ret=pnl / pos.cost_basis if pos.cost_basis else 0.0,
            holding_days=int((date - pos.entry_date).days),
        ))
        self.positions.pop(pos.ticker, None)

    def _execute_buy(self, order: Dict[str, Any], date: pd.Timestamp, price: float) -> None:
        fill = price * (1 + self.cfg.slippage)
        notional = min(order["notional"], self.cash / (1 + self.cfg.commission))
        if notional <= 0 or fill <= 0:
            return
        shares = notional / fill
        if shares <= 0:
            return
        gross = shares * fill
        commission = gross * self.cfg.commission
        if gross + commission > self.cash:
            return
        self.cash -= gross + commission
        self.total_costs += commission + shares * price * self.cfg.slippage

        # Stop y objetivo del sistema son niveles absolutos calculados sobre el
        # CIERRE de la señal (fund_manager.py:61-62). Se conservan tal cual: el
        # sistema los publica así y el backtest no debe mejorarlos.
        self.positions[order["ticker"]] = Position(
            ticker=order["ticker"], shares=shares, entry_price=fill, entry_date=date,
            stop=order.get("stop"), target=order.get("target"),
            rating=order["rating"], sector=order.get("sector", "Desconocido"),
            cost_basis=gross + commission,
        )

    def process_open(self, date: pd.Timestamp) -> None:
        """Ejecuta en la apertura de `date` las órdenes generadas el cierre anterior."""
        if not self._pending:
            return
        pending, self._pending = self._pending, []

        # Ventas primero: liberan efectivo para las compras del mismo día.
        for order in [o for o in pending if o["side"] == "SELL"]:
            pos = self.positions.get(order["ticker"])
            if pos is None:
                continue
            bar = self._bar(pos.ticker, date)
            if bar is None:
                continue
            self._execute_sell(pos, date, float(bar["Open"]), order.get("reason", "rebalance"))

        for order in [o for o in pending if o["side"] == "BUY"]:
            if order["ticker"] in self.positions:
                continue
            bar = self._bar(order["ticker"], date)
            if bar is None:
                continue
            self._execute_buy(order, date, float(bar["Open"]))

    def process_intraday_exits(self, date: pd.Timestamp) -> None:
        """
        Stops y objetivos contra el rango de la barra.

        Orden de resolución deliberadamente pesimista: si en la misma sesión se
        tocan stop y objetivo, se asume que saltó el stop. Sin datos intradía es
        imposible saber cuál ocurrió antes, y equivocarse al alza infla el
        resultado sistemáticamente.
        """
        # Nota: una posición abierta hoy en la apertura también se evalúa contra
        # el rango completo de la sesión, incluido el tramo anterior al relleno.
        # Es ligeramente pesimista —ese mínimo previo no pudo activar una orden
        # que aún no existía— y se prefiere a la alternativa optimista.
        for ticker in list(self.positions.keys()):
            pos = self.positions[ticker]
            bar = self._bar(ticker, date)
            if bar is None:
                continue
            low, high, open_ = float(bar["Low"]), float(bar["High"]), float(bar["Open"])

            if pos.stop is not None and low <= pos.stop:
                fill = min(open_, pos.stop) if open_ < pos.stop else pos.stop
                self._execute_sell(pos, date, fill, "stop_loss")
                continue

            if pos.target is not None and high >= pos.target:
                fill = max(open_, pos.target) if open_ > pos.target else pos.target
                self._execute_sell(pos, date, fill, "take_profit")
                continue

            if self.cfg.max_holding_days is not None and \
                    (date - pos.entry_date).days >= self.cfg.max_holding_days:
                self._execute_sell(pos, date, float(bar["Close"]), "max_holding")

    def mark(self, date: pd.Timestamp) -> None:
        eq = self.equity_at(date)
        self.equity[date] = eq
        self.exposure[date] = (self.market_value(date) / eq) if eq > 0 else 0.0
        self.n_open[date] = len(self.positions)

    def liquidate(self, date: pd.Timestamp) -> None:
        for ticker in list(self.positions.keys()):
            pos = self.positions[ticker]
            px = self._last_close(ticker, date)
            if px is not None:
                self._execute_sell(pos, date, px, "fin_backtest")

    # ---------------- resultados ----------------
    def equity_series(self) -> pd.Series:
        return pd.Series(self.equity).sort_index()

    def exposure_series(self) -> pd.Series:
        return pd.Series(self.exposure).sort_index()

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(columns=[
                "ticker", "sector", "rating", "entry_date", "entry_price", "exit_date",
                "exit_price", "shares", "exit_reason", "pnl", "ret", "holding_days"])
        return pd.DataFrame([t.__dict__ for t in self.trades])


# --------------------------------------------------------------------------- #
def build_orders(signals: List[Signal], engine: PortfolioEngine,
                 date: pd.Timestamp, cfg: BacktestConfig) -> List[Dict[str, Any]]:
    """
    Traduce las señales del cierre de `date` en órdenes para la apertura de la
    sesión siguiente.

    Regla de salida por degradación: si un ticker en cartera deja de estar en
    {COMPRA FUERTE, COMPRA} en el rebalanceo, se vende. Un ticker sin señal ese
    día (por ejemplo, sin fundamentales publicados) se MANTIENE: la ausencia de
    dato no es una señal de venta, y tratarla como tal generaría rotación
    fantasma.
    """
    orders: List[Dict[str, Any]] = []
    by_ticker = {s.ticker: s for s in signals}
    buys = [s for s in signals if s.is_buy]

    for ticker, pos in engine.positions.items():
        sig = by_ticker.get(ticker)
        if sig is not None and not sig.is_buy:
            orders.append({"side": "SELL", "ticker": ticker, "reason": f"downgrade_{sig.rating}"})

    equity = engine.equity_at(date)
    held = set(engine.positions.keys())
    sold = {o["ticker"] for o in orders}
    new_buys = [s for s in buys if s.ticker not in held]
    if not new_buys or equity <= 0:
        return orders

    # Peso comprometido por las posiciones que se mantienen.
    committed = 0.0
    for ticker, pos in engine.positions.items():
        if ticker in sold:
            continue
        px = engine._last_close(ticker, date)
        if px:
            committed += (pos.shares * px) / equity

    budget = max(0.0, cfg.max_gross_exposure - committed)
    wanted = sum(s.target_weight for s in new_buys)
    scale = min(1.0, budget / wanted) if wanted > 0 else 0.0
    if scale <= 0:
        return orders

    for s in sorted(new_buys, key=lambda x: -x.target_weight):
        notional = equity * s.target_weight * scale
        if notional <= 0:
            continue
        orders.append({
            "side": "BUY", "ticker": s.ticker, "notional": notional,
            "stop": s.stop_loss, "target": s.take_profit,
            "rating": s.rating, "sector": s.sector,
        })
    return orders


def run_backtest(replayer, tickers: List[str], calendar: pd.DatetimeIndex,
                 rebal_dates: List[pd.Timestamp], price_data: Dict[str, pd.DataFrame],
                 cfg: BacktestConfig, verbose: bool = True) -> Dict[str, Any]:
    """Bucle diario principal. Devuelve curva de capital, operaciones y señales."""
    engine = PortfolioEngine(price_data, cfg)
    rebal = set(pd.DatetimeIndex(rebal_dates))
    all_signals: List[Signal] = []

    for i, date in enumerate(calendar):
        engine.process_open(date)
        engine.process_intraday_exits(date)
        engine.mark(date)

        if date in rebal and i < len(calendar) - 1:
            sigs = replayer.signals_for_date(tickers, date)
            all_signals.extend(sigs)
            engine.schedule(build_orders(sigs, engine, date, cfg))
            if verbose:
                n_buy = sum(1 for s in sigs if s.is_buy)
                print(f"  {date.date()}  señales={len(sigs):3d}  compras={n_buy:3d}  "
                      f"posiciones={len(engine.positions):3d}  equity=${engine.equity[date]:,.0f}")

    if len(calendar):
        engine.liquidate(calendar[-1])
        engine.mark(calendar[-1])

    return {
        "equity": engine.equity_series(),
        "exposure": engine.exposure_series(),
        "n_open": pd.Series(engine.n_open).sort_index(),
        "trades": engine.trades_frame(),
        "signals": all_signals,
        "total_costs": engine.total_costs,
        "skips": dict(replayer.skips),
    }


# --------------------------------------------------------------------------- #
# Benchmarks
# --------------------------------------------------------------------------- #
def buy_and_hold(price_data: Dict[str, pd.DataFrame], ticker: str,
                 calendar: pd.DatetimeIndex, capital: float) -> pd.Series:
    df = price_data.get(ticker)
    if df is None:
        return pd.Series(dtype=float)
    px = df["Close"].reindex(calendar).ffill().dropna()
    if px.empty:
        return pd.Series(dtype=float)
    return capital * px / px.iloc[0]


def equal_weight(price_data: Dict[str, pd.DataFrame], tickers: List[str],
                 calendar: pd.DatetimeIndex, capital: float) -> pd.Series:
    cols = {}
    for t in tickers:
        df = price_data.get(t)
        if df is None:
            continue
        s = df["Close"].reindex(calendar).ffill()
        if s.notna().sum() > 0:
            cols[t] = s
    if not cols:
        return pd.Series(dtype=float)
    prices = pd.DataFrame(cols)
    rets = prices.pct_change().fillna(0.0)
    port = rets.mean(axis=1)
    return capital * (1 + port).cumprod()


def random_signal_benchmark(price_data: Dict[str, pd.DataFrame], tickers: List[str],
                            calendar: pd.DatetimeIndex, n_positions: int,
                            avg_holding_days: int, gross_exposure: float,
                            cfg: BacktestConfig, n_runs: int = 1000,
                            seed: int = 42) -> Dict[str, Any]:
    """
    Monte Carlo de la hipótesis nula de SELECCIÓN: mismo universo, mismo número
    medio de posiciones simultáneas, mismo periodo medio de tenencia y **la
    misma exposición bruta media** que la estrategia, pero eligiendo los tickers
    al azar.

    Igualar la exposición es imprescindible: una estrategia que pasa la mitad
    del tiempo en liquidez comparada contra carteras aleatorias 100% invertidas
    no mediría habilidad de selección, sino diferencia de exposición al mercado.
    La pregunta que responde este contraste es "¿elige bien los valores?", y el
    benchmark SPY responde por separado a "¿merece la pena frente a estar
    invertido y punto?".
    """
    rng = np.random.default_rng(seed)
    closes = {}
    for t in tickers:
        df = price_data.get(t)
        if df is not None:
            closes[t] = df["Close"].reindex(calendar).ffill()
    if not closes:
        return {"finals": np.array([]), "cagrs": np.array([])}

    prices = pd.DataFrame(closes)
    rets = prices.pct_change().fillna(0.0).values
    n_days, n_assets = rets.shape
    years = (calendar[-1] - calendar[0]).days / 365.25 if n_days > 1 else 1.0
    hold = max(1, int(avg_holding_days * 252 / 365))
    n_pos = max(1, min(n_positions, n_assets))
    expo = max(0.0, gross_exposure)

    # Coste por rotación completa de la cartera invertida (ida + vuelta), medido
    # sobre el capital total, no por posición: rotar n_pos posiciones de peso
    # expo/n_pos cada una cuesta lo mismo que rotar `expo` de capital una vez.
    cost_per_turnover = (cfg.commission + cfg.slippage) * 2 * expo
    n_turnovers = int(np.ceil(n_days / hold))
    drag_per_day = cost_per_turnover * n_turnovers / max(1, n_days)

    finals = np.empty(n_runs)
    for r in range(n_runs):
        weights = np.zeros((n_days, n_assets))
        d = 0
        while d < n_days:
            pick = rng.choice(n_assets, size=n_pos, replace=False)
            end = min(d + hold, n_days)
            weights[d:end, pick] = expo / n_pos
            d = end
        port = (rets * weights).sum(axis=1) - drag_per_day
        finals[r] = float(np.prod(1 + port))

    cagrs = finals ** (1 / years) - 1 if years > 0 else finals - 1
    return {"finals": finals, "cagrs": cagrs}
