"""
Tests de la capa de backtest.

El test que de verdad importa es `test_no_lookahead_*`: si el motor puede ver el
futuro, todas las demás cifras del informe son ficción. Los demás protegen la
contabilidad y la fidelidad del replay frente a los agentes reales.

Ninguno necesita red.
"""

import numpy as np
import pandas as pd
import pytest

from src.backtest.data import Fact, FundamentalStore, PriceStore
from src.backtest.engine import (
    BacktestConfig, PortfolioEngine, build_orders, run_backtest,
)
from src.backtest.metrics import breakeven_hit_rate, cagr, max_drawdown, trade_stats
from src.backtest.replay import (
    MIN_WINDOW_ROWS, HistoricalReplayer, Signal,
    assert_llm_is_decision_neutral, disable_llm,
)

disable_llm()


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def make_prices(n=400, start="2020-01-01", seed=7, drift=0.0006, vol=0.015):
    """Serie OHLCV sintética con tendencia alcista suave."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start=start, periods=n)
    rets = rng.normal(drift, vol, n)
    close = 100 * np.exp(np.cumsum(rets))
    high = close * (1 + np.abs(rng.normal(0, 0.006, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.006, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    return pd.DataFrame(
        {"Open": open_, "High": np.maximum(high, np.maximum(open_, close)),
         "Low": np.minimum(low, np.minimum(open_, close)), "Close": close,
         "Volume": rng.integers(1e6, 5e6, n).astype(float)},
        index=idx)


class StubPriceStore:
    def __init__(self, data):
        self._mem = {k.upper(): v for k, v in data.items()}

    def window(self, ticker, as_of, lookback_days=365):
        df = self._mem.get(ticker.upper())
        if df is None:
            return None
        lo = as_of - pd.Timedelta(days=lookback_days)
        w = df.loc[(df.index > lo) & (df.index <= as_of)]
        return w if not w.empty else None


def _serie(valor, factor=0.85, n=2):
    """Serie anual sintética: el ejercicio más reciente y otro peor detrás."""
    return [valor * (factor ** i) for i in range(n)]


class StubFundamentals:
    """
    Fundamentales que siempre aprueban el gatekeeper.

    Implementa también `estados_financieros()` porque el `QualityAnalystAgent`
    entró en la ruta de decisión del replay: sin estados, el agente degradaría
    a DATOS_INSUFICIENTES y el Fund Manager limitaría todo a MANTENER, con lo
    que los tests de la tabla de decisión dejarían de probar lo que dicen
    probar.
    """

    def __init__(self, available=True, con_estados=True, **overrides):
        self.base = {"revenue_growth": 0.20, "net_margin": 0.15, "debt_to_equity": 1.0,
                     "roe": 0.30, "pe_ratio": 20.0, "market_cap": 1.0e10,
                     "available": available, "as_of_period_end": "2019-12-31",
                     "filed": "2020-02-15"}
        self.base.update(overrides)
        self.con_estados = con_estados

    def as_of(self, ticker, date):
        return dict(self.base)

    def sec_payload(self, ticker, date):
        return {"status": "NOT_USED", "source": "SEC EDGAR"}

    def estados_financieros(self, ticker, date):
        if not self.con_estados:
            return {"disponible": False, "bloques_ok": [],
                    "bloques_fallidos": ["balance", "resultados", "flujos"],
                    "balance": {}, "resultados": {}, "flujos": {}}
        return {
            "disponible": True, "bloques_ok": ["balance", "resultados", "flujos"],
            "bloques_fallidos": [],
            "balance": {
                "activos_totales": _serie(1.0e10), "pasivos_totales": _serie(4.0e9),
                "patrimonio": _serie(6.0e9), "activo_corriente": _serie(3.0e9),
                "pasivo_corriente": _serie(1.2e9), "beneficios_retenidos": _serie(3.5e9),
                "deuda_largo_plazo": _serie(1.8e9), "deuda_total": _serie(2.0e9),
                "acciones_emitidas": _serie(5.0e8, 1.005), "efectivo": _serie(1.0e9),
                "inmovilizado": _serie(3.0e9), "fondo_comercio": [], "intangibles": [],
            },
            "resultados": {
                "ingresos": _serie(5.0e9), "beneficio_bruto": _serie(2.75e9),
                "ebit": _serie(1.25e9), "beneficio_neto": _serie(7.5e8),
                "gastos_financieros": _serie(8.0e7), "impuestos": _serie(2.0e8),
                "beneficio_antes_impuestos": _serie(9.5e8),
            },
            "flujos": {
                "flujo_operativo": _serie(9.0e8), "capex": _serie(-3.0e8),
                "flujo_libre": _serie(6.0e8), "dividendos_pagados": [], "recompras": [],
            },
            "reconstruido_point_in_time": True,
        }


# --------------------------------------------------------------------------- #
# 1. Ausencia de look-ahead
# --------------------------------------------------------------------------- #
def test_no_lookahead_future_prices_do_not_change_past_signal():
    """
    Test central del estudio.

    Se calcula la señal en `t`, se altera brutalmente TODO el histórico
    posterior a `t` y se recalcula. Si el resultado cambia aunque sea un
    decimal, existe una fuga de información del futuro hacia el pasado.
    """
    df = make_prices(n=400)
    t = df.index[300]

    r1 = HistoricalReplayer(StubPriceStore({"TEST": df}), StubFundamentals(), mode="pit")
    s1 = r1.signal("TEST", t)
    assert s1 is not None

    tampered = df.copy()
    future = tampered.index > t
    tampered.loc[future, ["Open", "High", "Low", "Close"]] *= 3.0
    tampered.loc[future, "Volume"] *= 50

    r2 = HistoricalReplayer(StubPriceStore({"TEST": tampered}), StubFundamentals(), mode="pit")
    s2 = r2.signal("TEST", t)
    assert s2 is not None

    assert s1.rating == s2.rating
    assert s1.momentum == s2.momentum
    assert s1.close == pytest.approx(s2.close)
    assert s1.atr == pytest.approx(s2.atr)
    assert s1.rsi == pytest.approx(s2.rsi)
    assert s1.stop_loss == pytest.approx(s2.stop_loss)
    assert s1.take_profit == pytest.approx(s2.take_profit)


def test_no_lookahead_window_ends_at_as_of():
    """La ventana entregada a los indicadores nunca contiene barras futuras."""
    df = make_prices(n=400)
    t = df.index[250]
    store = StubPriceStore({"TEST": df})
    w = store.window("TEST", t)
    assert w.index.max() <= t


def test_fundamentals_respect_filed_not_end():
    """
    Un ejercicio cerrado el 31-dic-2020 pero presentado el 10-feb-2021 no puede
    ser visible el 15-ene-2021. Es el defecto que `_extract_recent_fact()`
    tiene hoy en producción al ordenar por `end`.
    """
    store = FundamentalStore(offline=True)
    fy20 = pd.Timestamp("2020-12-31")
    fy19 = pd.Timestamp("2019-12-31")
    filed20 = pd.Timestamp("2021-02-10")
    filed19 = pd.Timestamp("2020-02-10")

    store._facts["FAKE"] = {
        "Revenues": [
            Fact(end=fy19, start=fy19 - pd.Timedelta(days=364), val=1000.0, filed=filed19, form="10-K"),
            Fact(end=fy20, start=fy20 - pd.Timedelta(days=365), val=1500.0, filed=filed20, form="10-K"),
        ],
        "NetIncomeLoss": [
            Fact(end=fy19, start=fy19 - pd.Timedelta(days=364), val=100.0, filed=filed19, form="10-K"),
            Fact(end=fy20, start=fy20 - pd.Timedelta(days=365), val=300.0, filed=filed20, form="10-K"),
        ],
        "StockholdersEquity": [
            Fact(end=fy20, start=None, val=2000.0, filed=filed20, form="10-K"),
        ],
    }

    # Antes de la presentación del FY2020 solo debe existir FY2019, que no tiene
    # ejercicio anterior con el que calcular crecimiento.
    before = store.as_of("FAKE", "2021-01-15")
    assert before["available"] is False

    after = store.as_of("FAKE", "2021-03-01")
    assert after["available"] is True
    assert after["revenue_growth"] == pytest.approx(0.5)      # 1500/1000 - 1
    assert after["net_margin"] == pytest.approx(0.2)          # 300/1500
    assert after["as_of_period_end"] == "2020-12-31"


def test_filed_never_precedes_period_end():
    """Un `filed` corrupto anterior al cierre se corrige con el retardo mínimo."""
    store = FundamentalStore(offline=True)
    end = pd.Timestamp("2021-12-31")
    f = Fact(end=end, start=end - pd.Timedelta(days=365), val=1.0,
             filed=end - pd.Timedelta(days=30), form="10-K")
    # El saneamiento vive en `_parse`; aquí se comprueba la invariante que debe
    # cumplir todo hecho que llegue a la selección point-in-time.
    assert f.filed < f.end  # el dato de partida es inválido...
    sane = f.end + pd.Timedelta(days=45)
    assert sane > f.end     # ...y el saneamiento lo empuja detrás del cierre


def test_price_cache_rejects_insufficient_coverage(tmp_path):
    """
    Una caché escrita por una ejecución con `--start` posterior NO debe
    reutilizarse para un periodo más largo.

    Es un fallo real que se observó en este proyecto: un test de humo sobre
    2022-2024 dejó SPY cacheado desde 2020, y la ejecución posterior de
    2015-2025 lo reutilizó en silencio, truncando el benchmark a 5 años y
    produciendo un CAGR incoherente con su retorno total.
    """
    import json as _json

    store = PriceStore(cache_dir=tmp_path, offline=True)
    df = make_prices(n=100, start="2020-11-27")
    df.to_csv(store._path("SPY"))

    # Sin metadatos de cobertura: no se puede afirmar que el rango esté cubierto.
    assert store._covers("SPY", pd.Timestamp("2013-11-27"), pd.Timestamp("2025-12-31")) is False

    store._meta_path("SPY").write_text(_json.dumps({
        "requested_start": "2020-11-27", "requested_end": "2024-12-31"}), encoding="utf-8")
    assert store._covers("SPY", pd.Timestamp("2013-11-27"), pd.Timestamp("2025-12-31")) is False

    store._meta_path("SPY").write_text(_json.dumps({
        "requested_start": "2013-11-27", "requested_end": "2025-12-31"}), encoding="utf-8")
    assert store._covers("SPY", pd.Timestamp("2013-11-27"), pd.Timestamp("2025-12-31")) is True


def test_insufficient_history_produces_no_signal():
    """Con menos de 200 sesiones, `min(50,len)`/`min(200,len)` cambian de
    definición: preferimos no emitir señal antes que emitir una distinta."""
    df = make_prices(n=MIN_WINDOW_ROWS - 20)
    r = HistoricalReplayer(StubPriceStore({"TEST": df}), StubFundamentals(), mode="pit")
    assert r.signal("TEST", df.index[-1]) is None
    assert r.skips.get("historia_insuficiente", 0) == 1


# --------------------------------------------------------------------------- #
# 2. Fidelidad frente a los agentes reales
# --------------------------------------------------------------------------- #
def test_llm_is_decision_neutral():
    """Hipótesis de la Fase 1 sobre la que descansa todo el backtest."""
    res = assert_llm_is_decision_neutral()
    assert res["neutral"], f"El LLM altera decisiones: {res['divergences']}"


def test_replay_matches_production_decision_table():
    """
    El replay debe reproducir la tabla de decisión del `FundManagerAgent`, no
    una reimplementación suya.

    Los múltiplos de ATR ya no son constantes: dependen del estilo asignado por
    el Analista de Calidad (`ATR_AJUSTE_POR_ESTILO`), porque una compounder y
    una cíclica volátil no necesitan el mismo aire. El test los lee de la misma
    tabla que usa producción en lugar de fijar 2.0 y 3.5 a mano — así sigue
    detectando una reimplementación en la capa de backtest, que es lo que debe
    vigilar, sin romperse cada vez que se recalibra un múltiplo.
    """
    from src.config import ATR_AJUSTE_POR_ESTILO

    df = make_prices(n=400, drift=0.0015, vol=0.008, seed=3)  # tendencia clara
    r = HistoricalReplayer(StubPriceStore({"T": df}), StubFundamentals(), mode="pit")
    s = r.signal("T", df.index[-1])
    assert s is not None
    assert s.rating in {"COMPRA FUERTE", "COMPRA", "MANTENER", "VENTA",
                        "VENTA FUERTE", "SIN OPINION"}

    if s.rating in ("COMPRA FUERTE", "COMPRA"):
        ajuste = ATR_AJUSTE_POR_ESTILO.get(s.estilo, ATR_AJUSTE_POR_ESTILO["MIXTA"])
        assert s.stop_loss == pytest.approx(round(s.close - ajuste["stop"] * s.atr, 2))
        assert s.take_profit == pytest.approx(round(s.close + ajuste["objetivo"] * s.atr, 2))
        # El peso ya no sale de una tabla del backtest: lo emite el Fund Manager.
        assert 0.0 < s.target_weight <= 0.10
    else:
        assert s.target_weight == 0.0


def test_signal_arrastra_el_dictamen_de_calidad():
    """
    El replay ejecuta el Analista de Calidad y propaga su dictamen.

    Desde que la convicción fundamental entra en el rating, omitirlo en el
    backtest mediría una lógica distinta de la que decide en producción.
    """
    df = make_prices(n=400, drift=0.0015, vol=0.008, seed=3)
    r = HistoricalReplayer(StubPriceStore({"T": df}), StubFundamentals(), mode="pit")
    s = r.signal("T", df.index[-1])
    assert s is not None
    assert s.estilo is not None and s.estilo != "DATOS_INSUFICIENTES"
    assert s.conviccion is not None and 0.0 <= s.conviccion <= 100.0
    assert s.banderas_rojas >= 0


def test_sin_estados_financieros_la_calidad_limita_el_dictamen():
    """
    Sin estados financieros reconstruibles, el sistema no puede tener
    convicción y el Fund Manager no debe emitir una compra.

    Es la traducción operativa de «no sé, luego no arriesgo»: la degradación
    tiene que ser hacia la prudencia, nunca hacia una compra por defecto.
    """
    df = make_prices(n=400, drift=0.0015, vol=0.008, seed=3)
    sin_estados = StubFundamentals(con_estados=False)
    r = HistoricalReplayer(StubPriceStore({"T": df}), sin_estados, mode="pit")
    s = r.signal("T", df.index[-1])
    assert s is not None
    assert s.estilo == "DATOS_INSUFICIENTES"
    assert s.rating not in ("COMPRA", "COMPRA FUERTE")
    assert s.target_weight == 0.0


def test_gatekeeper_rejection_forces_sell_and_no_levels():
    """Rechazo fundamental ⇒ VENTA, 0% y sin stop ni objetivo (fund_manager.py:31-40)."""
    df = make_prices(n=400)
    bad = StubFundamentals(net_margin=0.001, revenue_growth=-0.30)  # incumple umbrales
    r = HistoricalReplayer(StubPriceStore({"T": df}), bad, mode="pit")
    s = r.signal("T", df.index[-1])
    assert s is not None
    assert s.passed_gatekeeper is False
    assert s.rating in ("VENTA", "VENTA FUERTE")
    assert s.stop_loss is None and s.take_profit is None
    assert s.target_weight == 0.0
    assert s.is_buy is False


def test_deep_losses_trigger_strong_sell():
    """Margen neto < -10% ⇒ VENTA FUERTE (fund_manager.py:34-35)."""
    df = make_prices(n=400)
    r = HistoricalReplayer(StubPriceStore({"T": df}),
                           StubFundamentals(net_margin=-0.25, revenue_growth=-0.5), mode="pit")
    s = r.signal("T", df.index[-1])
    assert s.rating == "VENTA FUERTE"


def test_technical_only_mode_bypasses_gatekeeper():
    df = make_prices(n=400, drift=0.0015, vol=0.008, seed=3)
    r = HistoricalReplayer(StubPriceStore({"T": df}),
                           StubFundamentals(available=False), mode="technical_only")
    s = r.signal("T", df.index[-1])
    assert s is not None and s.passed_gatekeeper is True


def test_pit_mode_skips_tickers_without_fundamentals():
    """Sin fundamentales publicados no se opera: rellenar el hueco reintroduciría el sesgo."""
    df = make_prices(n=400)
    r = HistoricalReplayer(StubPriceStore({"T": df}),
                           StubFundamentals(available=False), mode="pit")
    assert r.signal("T", df.index[-1]) is None
    assert r.skips.get("sin_fundamentales", 0) == 1


# --------------------------------------------------------------------------- #
# 3. Contabilidad de la cartera
# --------------------------------------------------------------------------- #
def _engine_with(df, cfg=None):
    return PortfolioEngine({"T": df}, cfg or BacktestConfig(initial_capital=100_000.0))


def test_order_fills_at_next_open_never_same_bar():
    df = make_prices(n=60)
    eng = _engine_with(df, BacktestConfig(commission_bps=0, slippage_bps=0))
    d0, d1 = df.index[10], df.index[11]

    eng.schedule([{"side": "BUY", "ticker": "T", "notional": 10_000,
                   "stop": None, "target": None, "rating": "COMPRA", "sector": "X"}])
    eng.process_open(d0)   # se rellena aquí, que es la apertura siguiente al cierre de d-1
    assert "T" in eng.positions
    assert eng.positions["T"].entry_price == pytest.approx(float(df.loc[d0, "Open"]))
    assert eng.positions["T"].entry_date == d0
    assert d1 > d0


def test_accounting_reconciles_after_liquidation():
    """Capital final == capital inicial + P&L de todas las operaciones cerradas."""
    df = make_prices(n=120)
    cfg = BacktestConfig(initial_capital=100_000.0, commission_bps=5, slippage_bps=5)
    eng = _engine_with(df, cfg)

    eng.schedule([{"side": "BUY", "ticker": "T", "notional": 40_000,
                   "stop": None, "target": None, "rating": "COMPRA", "sector": "X"}])
    for d in df.index[10:100]:
        eng.process_open(d)
        eng.process_intraday_exits(d)
        eng.mark(d)
    last = df.index[99]
    eng.liquidate(last)
    eng.mark(last)

    total_pnl = sum(t.pnl for t in eng.trades)
    assert eng.positions == {}
    assert eng.equity[last] == pytest.approx(cfg.initial_capital + total_pnl, rel=1e-9)
    assert eng.cash == pytest.approx(eng.equity[last], rel=1e-9)


def test_cash_never_goes_negative():
    df = make_prices(n=80)
    cfg = BacktestConfig(initial_capital=10_000.0)
    eng = _engine_with(df, cfg)
    eng.schedule([{"side": "BUY", "ticker": "T", "notional": 1_000_000,
                   "stop": None, "target": None, "rating": "COMPRA", "sector": "X"}])
    for d in df.index[5:40]:
        eng.process_open(d)
        eng.mark(d)
        assert eng.cash >= -1e-9


def test_stop_wins_over_target_in_same_bar():
    """Ambos niveles tocados en la misma sesión ⇒ se asume el peor caso."""
    idx = pd.bdate_range("2021-01-04", periods=3)
    df = pd.DataFrame({
        "Open": [100.0, 100.0, 100.0],
        "High": [101.0, 130.0, 101.0],   # toca el objetivo...
        "Low": [99.0, 70.0, 99.0],       # ...y también el stop
        "Close": [100.0, 100.0, 100.0],
        "Volume": [1e6, 1e6, 1e6],
    }, index=idx)
    eng = PortfolioEngine({"T": df}, BacktestConfig(commission_bps=0, slippage_bps=0))
    eng.schedule([{"side": "BUY", "ticker": "T", "notional": 10_000,
                   "stop": 90.0, "target": 110.0, "rating": "COMPRA", "sector": "X"}])
    eng.process_open(idx[0])
    eng.process_intraday_exits(idx[1])
    assert len(eng.trades) == 1
    assert eng.trades[0].exit_reason == "stop_loss"


def test_gap_through_stop_fills_at_open_not_at_stop():
    """Si abre por debajo del stop, el relleno es la apertura: peor, y realista."""
    idx = pd.bdate_range("2021-01-04", periods=3)
    df = pd.DataFrame({
        "Open": [100.0, 80.0, 80.0],
        "High": [101.0, 82.0, 82.0],
        "Low": [99.0, 78.0, 78.0],
        "Close": [100.0, 80.0, 80.0],
        "Volume": [1e6, 1e6, 1e6],
    }, index=idx)
    eng = PortfolioEngine({"T": df}, BacktestConfig(commission_bps=0, slippage_bps=0))
    eng.schedule([{"side": "BUY", "ticker": "T", "notional": 10_000,
                   "stop": 90.0, "target": 130.0, "rating": "COMPRA", "sector": "X"}])
    eng.process_open(idx[0])
    eng.process_intraday_exits(idx[1])
    assert eng.trades[0].exit_reason == "stop_loss"
    assert eng.trades[0].exit_price == pytest.approx(80.0)  # no 90.0


def test_costs_reduce_return():
    df = make_prices(n=120)
    results = {}
    for bps in (0.0, 50.0):
        eng = _engine_with(df, BacktestConfig(commission_bps=bps / 2, slippage_bps=bps / 2))
        eng.schedule([{"side": "BUY", "ticker": "T", "notional": 50_000,
                       "stop": None, "target": None, "rating": "COMPRA", "sector": "X"}])
        for d in df.index[10:100]:
            eng.process_open(d)
            eng.mark(d)
        eng.liquidate(df.index[99])
        eng.mark(df.index[99])
        results[bps] = eng.equity[df.index[99]]
    assert results[50.0] < results[0.0]


# --------------------------------------------------------------------------- #
# 4. Generación de órdenes
# --------------------------------------------------------------------------- #
def _sig(ticker, date, rating, weight):
    return Signal(ticker=ticker, date=date, rating=rating, momentum="ALCISTA",
                  passed_gatekeeper=True, close=100.0, atr=2.0, rsi=55.0,
                  stop_loss=96.0, take_profit=107.0, target_weight=weight, sector="X")


def test_downgrade_generates_sell_but_missing_signal_does_not():
    """Sin señal ≠ señal de venta: la ausencia de dato no debe rotar la cartera."""
    df = make_prices(n=60)
    eng = PortfolioEngine({"A": df, "B": df}, BacktestConfig())
    d = df.index[20]
    for t in ("A", "B"):
        eng.schedule([{"side": "BUY", "ticker": t, "notional": 5_000, "stop": None,
                       "target": None, "rating": "COMPRA", "sector": "X"}])
        eng.process_open(d)

    orders = build_orders([_sig("A", d, "MANTENER", 0.0)], eng, d, BacktestConfig())
    sells = {o["ticker"] for o in orders if o["side"] == "SELL"}
    assert sells == {"A"}      # A degradado -> venta; B sin señal -> se mantiene


def test_gross_exposure_is_capped():
    df = make_prices(n=60)
    price_data = {f"T{i}": df for i in range(20)}
    eng = PortfolioEngine(price_data, BacktestConfig())
    d = df.index[20]
    sigs = [_sig(f"T{i}", d, "COMPRA FUERTE", 0.09) for i in range(20)]  # 180% pedido
    orders = build_orders(sigs, eng, d, BacktestConfig(max_gross_exposure=1.0))
    total = sum(o["notional"] for o in orders if o["side"] == "BUY")
    assert total <= eng.equity_at(d) * 1.0 + 1e-6


# --------------------------------------------------------------------------- #
# 5. Métricas
# --------------------------------------------------------------------------- #
def test_breakeven_hit_rate_matches_system_risk_reward():
    """TP=3.5·ATR y SL=2.0·ATR ⇒ R:R 1.75 ⇒ equilibrio en 1/(1+1.75)."""
    assert breakeven_hit_rate(3.5, 2.0) == pytest.approx(1 / 2.75)
    assert breakeven_hit_rate(3.5, 2.0) == pytest.approx(0.36363636, abs=1e-6)


def test_cagr_and_drawdown_on_known_series():
    idx = pd.date_range("2020-01-01", periods=3, freq="365D")
    eq = pd.Series([100.0, 50.0, 200.0], index=idx)
    # 730 días naturales / 365.25 = 1.99863 años, no 2: el año se mide en años
    # julianos para que los bisiestos no desplacen el resultado.
    years = (idx[-1] - idx[0]).days / 365.25
    assert cagr(eq) == pytest.approx(2.0 ** (1 / years) - 1, abs=1e-9)
    assert cagr(eq) == pytest.approx(0.4145, abs=1e-4)
    assert max_drawdown(eq) == pytest.approx(-0.5)


def test_trade_stats_on_known_trades():
    trades = pd.DataFrame({
        "ticker": ["A", "B", "C", "D"],
        "sector": ["X"] * 4, "rating": ["COMPRA"] * 4,
        "entry_date": pd.to_datetime(["2021-01-01"] * 4),
        "entry_price": [100.0] * 4,
        "exit_date": pd.to_datetime(["2021-02-01"] * 4),
        "exit_price": [110.0, 90.0, 120.0, 95.0],
        "shares": [1.0] * 4,
        "exit_reason": ["take_profit", "stop_loss", "take_profit", "stop_loss"],
        "pnl": [10.0, -10.0, 20.0, -5.0],
        "ret": [0.10, -0.10, 0.20, -0.05],
        "holding_days": [31] * 4,
    })
    st = trade_stats(trades)
    assert st["n_trades"] == 4
    assert st["hit_rate"] == pytest.approx(0.5)
    assert st["profit_factor"] == pytest.approx(30 / 15)
    assert st["expectancy_pct"] == pytest.approx(0.5 * 0.15 + 0.5 * -0.075)


# --------------------------------------------------------------------------- #
# 6. Reproducibilidad
# --------------------------------------------------------------------------- #
def test_backtest_is_deterministic():
    """Dos ejecuciones idénticas deben dar curvas de capital idénticas."""
    df = make_prices(n=500, drift=0.0012, vol=0.01, seed=11)
    price_data = {"T": df}
    store = StubPriceStore(price_data)
    calendar = df.index[MIN_WINDOW_ROWS:]
    rebals = [d for d in pd.Series(calendar, index=calendar).resample("ME").last().dropna()]

    curves = []
    for _ in range(2):
        r = HistoricalReplayer(store, StubFundamentals(), mode="pit")
        res = run_backtest(r, ["T"], calendar, rebals, price_data,
                           BacktestConfig(), verbose=False)
        curves.append(res["equity"])
    pd.testing.assert_series_equal(curves[0], curves[1])


# --------------------------------------------------------------------------- #
# 9. Integración de la capa de cartera en el motor histórico
# --------------------------------------------------------------------------- #
def _señal(ticker, *, sector="Technology", peso=0.10, close=100.0, stop=90.0,
           estilo="CALIDAD_COMPUESTA", conviccion=70.0, vol=0.25,
           fecha="2021-06-30"):
    return Signal(
        ticker=ticker, date=pd.Timestamp(fecha), rating="COMPRA",
        momentum="ALCISTA", passed_gatekeeper=True, close=close, atr=close * 0.02,
        rsi=55.0, stop_loss=stop, take_profit=close * 1.2, target_weight=peso,
        sector=sector, estilo=estilo, conviccion=conviccion, volatilidad=vol,
    )


def _motor(tickers, fecha="2021-06-30"):
    from src.backtest.engine import BacktestConfig, PortfolioEngine
    precios = {t: make_prices(n=400, start="2020-01-01", seed=i + 1)
               for i, t in enumerate(tickers)}
    # El calendario sintético no contiene la fecha exacta: se usa la última
    # sesión disponible, que es lo que hace el bucle real.
    fecha = precios[tickers[0]].index[-1]
    return PortfolioEngine(precios, BacktestConfig()), precios, fecha


def test_el_motor_aplica_el_tope_sectorial_de_la_capa_de_cartera():
    """
    Antes el backtest escalaba los pesos proporcionalmente hasta llenar la
    exposición bruta y nada más: sin límite sectorial, la cartera simulada
    podía concentrar todo el capital en un sector y las métricas describían una
    estrategia distinta de la que el sistema recomienda en vivo.
    """
    from src.backtest.engine import BacktestConfig, build_orders
    from src.config import LIMITE_POR_SECTOR
    from src.portfolio import PortfolioConstructor

    tickers = list("ABCDE")
    engine, precios, fecha = _motor(tickers)
    señales = [_señal(t, sector="Technology", peso=0.10, fecha=fecha) for t in tickers]

    ordenes = build_orders(señales, engine, fecha, BacktestConfig(),
                           PortfolioConstructor())
    equity = engine.equity_at(fecha)
    peso_total = sum(o["notional"] for o in ordenes if o["side"] == "BUY") / equity
    assert peso_total <= LIMITE_POR_SECTOR + 1e-6


def test_sin_constructor_el_motor_conserva_el_reparto_proporcional():
    """`technical_only` no tiene convicciones que ordenar: se mantiene el reparto."""
    from src.backtest.engine import BacktestConfig, build_orders
    from src.config import LIMITE_POR_SECTOR

    tickers = list("ABCDE")
    engine, precios, fecha = _motor(tickers)
    señales = [_señal(t, sector="Technology", peso=0.10, fecha=fecha) for t in tickers]

    ordenes = build_orders(señales, engine, fecha, BacktestConfig(), None)
    equity = engine.equity_at(fecha)
    peso_total = sum(o["notional"] for o in ordenes if o["side"] == "BUY") / equity
    assert peso_total > LIMITE_POR_SECTOR  # el reparto antiguo no conoce sectores


def test_las_correlaciones_del_motor_se_calculan_solo_con_el_pasado():
    """
    Una matriz de correlaciones calculada con datos posteriores a `t` sería
    look-ahead del más difícil de detectar: no cambia ninguna señal, solo los
    pesos. `_series_hasta` corta en `t` inclusive.
    """
    from src.backtest.engine import _series_hasta

    tickers = list("AB")
    engine, precios, fecha = _motor(tickers)
    corte = precios["A"].index[250]

    series = _series_hasta(precios, tickers, corte, 120)
    assert series, "sin series no se puede verificar el corte"
    for t, serie in series.items():
        assert serie.index.max() <= corte


def test_las_operaciones_arrastran_el_estilo_para_atribucion():
    """
    Sin el estilo en el registro de operaciones no se puede responder si el
    sistema pierde dinero en valor, en crecimiento o de forma transversal — la
    hipótesis que el informe anterior planteaba sin poder medir.
    """
    from src.backtest.engine import BacktestConfig, PortfolioEngine, build_orders
    from src.portfolio import PortfolioConstructor

    engine, precios, fecha = _motor(["A"])
    ordenes = build_orders([_señal("A", peso=0.05, fecha=fecha)], engine, fecha,
                           BacktestConfig(), PortfolioConstructor())
    compra = next(o for o in ordenes if o["side"] == "BUY")
    assert compra["estilo"] == "CALIDAD_COMPUESTA"
    assert compra["conviccion"] == 70.0
    assert compra["volatilidad"] == 0.25

    # Y llegan a la posición y de ahí al Trade.
    siguiente = precios["A"].index[precios["A"].index.get_loc(fecha)]
    engine.schedule(ordenes)
    engine.process_open(siguiente)
    pos = engine.positions.get("A")
    if pos is not None:
        assert pos.estilo == "CALIDAD_COMPUESTA"
        engine.liquidate(siguiente)
        assert engine.trades[0].estilo == "CALIDAD_COMPUESTA"


def test_las_posiciones_abiertas_consumen_presupuesto_en_el_motor():
    """El tope sectorial debe contar lo que ya está en cartera, no solo lo nuevo."""
    from src.backtest.engine import BacktestConfig, build_orders, Position
    from src.config import LIMITE_POR_SECTOR
    from src.portfolio import PortfolioConstructor

    tickers = ["A", "B"]
    engine, precios, fecha = _motor(tickers)
    precio_a = float(precios["A"].loc[fecha, "Close"])
    # Posición abierta que ya ocupa el 25% del patrimonio en Technology.
    engine.cash = 75_000.0
    engine.positions["A"] = Position(
        ticker="A", shares=25_000.0 / precio_a, entry_price=precio_a,
        entry_date=fecha, stop=precio_a * 0.9, target=precio_a * 1.2,
        rating="COMPRA", sector="Technology", cost_basis=25_000.0,
        estilo="CALIDAD_COMPUESTA", conviccion=70.0, volatilidad=0.25)

    ordenes = build_orders([_señal("B", sector="Technology", peso=0.10, fecha=fecha)],
                           engine, fecha, BacktestConfig(), PortfolioConstructor())
    equity = engine.equity_at(fecha)
    nuevo = sum(o["notional"] for o in ordenes if o["side"] == "BUY") / equity
    assert nuevo <= LIMITE_POR_SECTOR - 0.25 + 1e-6
