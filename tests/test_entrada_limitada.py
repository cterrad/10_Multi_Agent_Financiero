"""
Tests de la ejecución de órdenes LIMITADAS en el motor de cartera.

Qué protegen
------------
Era `NEXT_STEPS` #1: aunque existiera un nivel, el motor **no podía llevar el
precio de entrada a ninguna parte** —`Signal` no lo transportaba y `process_open`
rellenaba siempre a la apertura de t+1—, así que el ajuste de entrada era
estructuralmente inmedible. Estos tests fijan las cuatro reglas que había que
decidir, más la que hace honesta la comparación:

1. **Sin límite, el comportamiento es EXACTAMENTE el de siempre.** Es lo que
   permite que cualquier estudio anterior a este cambio se reproduzca byte a
   byte, y por tanto que la comparación antes/después signifique algo.
2. **Hueco de apertura por debajo del límite → se rellena a la APERTURA**, no al
   límite. Rellenar al límite sería regalarse un precio que el mercado no
   ofreció, y es la misma disciplina que ya gobierna el hueco por debajo del
   stop.
3. **El mínimo toca el límite → se rellena AL LÍMITE.**
4. **La orden expira → NO se abre posición.** Es la parte cara y la que hay que
   contabilizar: sin ella, una regla que solo opera cuando el precio le viene
   encima parecería mejor de lo que es.
5. **Un rebalanceo nuevo SUSTITUYE la orden viva del mismo ticker**, en lugar de
   acumularlas.

Offline y deterministas: precios sintéticos, sin red.
"""

import pandas as pd
import pytest

from src.backtest.engine import BacktestConfig, PortfolioEngine, _orden_de_compra
from src.backtest.replay import Signal

FECHAS = pd.date_range("2024-01-01", periods=30, freq="B")


def _precios(patron):
    """
    OHLC sintético a partir de una lista de (open, high, low, close).

    Se rellena hasta 30 sesiones repitiendo la última barra, para que siempre
    haya futuro suficiente.
    """
    filas = list(patron) + [patron[-1]] * (len(FECHAS) - len(patron))
    df = pd.DataFrame(filas, columns=["Open", "High", "Low", "Close"], index=FECHAS)
    df["Volume"] = 1_000_000
    return {"X": df}


def _motor(px, **cfg_kwargs):
    cfg = BacktestConfig(initial_capital=100_000.0, commission_bps=0.0,
                         slippage_bps=0.0, **cfg_kwargs)
    return PortfolioEngine(px, cfg), cfg


def _orden(limite=None, vida=10, notional=10_000.0):
    return {"side": "BUY", "ticker": "X", "notional": notional,
            "stop": 90.0, "target": 120.0, "rating": "COMPRA", "sector": "Technology",
            "estilo": "MIXTA", "conviccion": 60.0, "volatilidad": 0.25,
            "limite": limite, "sesiones_restantes": vida if limite is not None else 0,
            "nivel_origen": "SOPORTE_ESTRUCTURAL"}


# --------------------------------------------------------------------------- #
# 1. Sin límite: el comportamiento de siempre
# --------------------------------------------------------------------------- #
def test_sin_limite_se_rellena_a_la_apertura_como_siempre():
    px = _precios([(100.0, 102.0, 99.0, 101.0)] * 3)
    eng, _ = _motor(px)
    eng.schedule([_orden(limite=None)])
    eng.process_open(FECHAS[0])
    assert "X" in eng.positions
    assert eng.positions["X"].entry_price == pytest.approx(100.0)
    assert eng.ordenes_expiradas == 0


def test_la_configuracion_por_defecto_no_pone_limite():
    """
    `usar_entrada_limitada=False` es el valor por defecto, y con él el límite es
    `None` aunque la señal traiga un precio de entrada objetivo. Es lo que hace
    que el cambio sea aditivo.
    """
    s = Signal(ticker="X", date=FECHAS[0], rating="COMPRA", momentum="ALCISTA",
               passed_gatekeeper=True, close=100.0, atr=2.0, rsi=55.0,
               stop_loss=95.0, take_profit=110.0, target_weight=0.05,
               precio_entrada_objetivo=97.0)
    por_defecto = _orden_de_compra(s, 10_000.0, BacktestConfig())
    assert por_defecto["limite"] is None
    assert por_defecto["sesiones_restantes"] == 0

    con_limite = _orden_de_compra(s, 10_000.0,
                                  BacktestConfig(usar_entrada_limitada=True))
    assert con_limite["limite"] == pytest.approx(97.0)
    assert con_limite["sesiones_restantes"] > 0


def test_un_objetivo_por_encima_del_cierre_no_es_un_limite():
    """
    Sería una orden que se rellena al instante y además al peor precio. La
    comprobación es `is not None` y no `or`: un objetivo de 0.0 es un dato
    corrupto, no una ausencia.
    """
    cfg = BacktestConfig(usar_entrada_limitada=True)
    base = dict(ticker="X", date=FECHAS[0], rating="COMPRA", momentum="ALCISTA",
                passed_gatekeeper=True, close=100.0, atr=2.0, rsi=55.0,
                stop_loss=95.0, take_profit=110.0, target_weight=0.05)
    for objetivo in (None, 0.0, 100.0, 105.0):
        o = _orden_de_compra(Signal(**base, precio_entrada_objetivo=objetivo),
                             10_000.0, cfg)
        assert o["limite"] is None, f"objetivo {objetivo} no debería ser límite"


# --------------------------------------------------------------------------- #
# 2. Las tres reglas de relleno
# --------------------------------------------------------------------------- #
def test_hueco_de_apertura_rellena_a_la_apertura_no_al_limite():
    """
    Si abre por debajo del límite, el precio que el mercado ofreció es la
    apertura. Rellenar al límite sería mejorarse el precio a posteriori — la
    misma disciplina que gobierna el hueco por debajo del stop.
    """
    px = _precios([(94.0, 96.0, 93.0, 95.0)])
    eng, _ = _motor(px, usar_entrada_limitada=True)
    eng.schedule([_orden(limite=97.0)])
    eng.process_open(FECHAS[0])
    assert eng.positions["X"].entry_price == pytest.approx(94.0)


def test_el_minimo_que_toca_el_limite_rellena_al_limite():
    px = _precios([(100.0, 101.0, 96.5, 99.0)])
    eng, _ = _motor(px, usar_entrada_limitada=True)
    eng.schedule([_orden(limite=97.0)])
    eng.process_open(FECHAS[0])
    assert eng.positions["X"].entry_price == pytest.approx(97.0)


def test_la_orden_que_expira_NO_abre_posicion():
    """
    LA REGLA CARA. Sin contabilizar las señales que se dejan pasar, una regla que
    solo opera cuando el precio le viene encima parecería mejor de lo que es.
    """
    px = _precios([(100.0, 102.0, 99.5, 101.0)])
    eng, _ = _motor(px, usar_entrada_limitada=True)
    eng.schedule([_orden(limite=97.0, vida=3)])
    for f in FECHAS[:3]:
        eng.process_open(f)
    assert "X" not in eng.positions, "la orden expirada abrió posición"
    assert eng.ordenes_expiradas == 1
    assert eng.cash == pytest.approx(100_000.0), "no se debe gastar efectivo"


def test_la_orden_vive_las_sesiones_declaradas_y_ni_una_mas():
    """El precio toca el límite en la sesión 4; con vida 3 la orden ya no existe."""
    px = _precios([(100.0, 101.0, 99.5, 100.0)] * 3 + [(100.0, 101.0, 96.0, 97.0)])
    corta, _ = _motor(px, usar_entrada_limitada=True)
    corta.schedule([_orden(limite=97.0, vida=3)])
    for f in FECHAS[:4]:
        corta.process_open(f)
    assert "X" not in corta.positions

    larga, _ = _motor(px, usar_entrada_limitada=True)
    larga.schedule([_orden(limite=97.0, vida=5)])
    for f in FECHAS[:4]:
        larga.process_open(f)
    assert "X" in larga.positions
    assert larga.positions["X"].entry_price == pytest.approx(97.0)


# --------------------------------------------------------------------------- #
# 3. Una orden nueva sustituye a la viva
# --------------------------------------------------------------------------- #
def test_un_rebalanceo_nuevo_sustituye_la_orden_viva_del_mismo_ticker():
    """
    El rebalanceo es el momento en que el sistema vuelve a opinar. Conservar las
    dos órdenes dejaría al motor persiguiendo un límite calculado con una señal
    ya revisada, y las acumularía sin techo a lo largo de once años.
    """
    px = _precios([(100.0, 101.0, 99.5, 100.0)])
    eng, _ = _motor(px, usar_entrada_limitada=True)
    eng.schedule([_orden(limite=97.0, vida=10)])
    eng.process_open(FECHAS[0])          # no toca; la orden sigue viva
    assert len(eng._pending) == 1

    eng.schedule([_orden(limite=95.0, vida=10)])
    assert len(eng._pending) == 1, "se acumularon dos órdenes del mismo ticker"
    assert eng._pending[0]["limite"] == pytest.approx(95.0), "no manda la más nueva"


def test_el_stop_y_el_objetivo_se_conservan_tal_como_el_sistema_los_publica():
    """
    El sistema mide el stop y el objetivo desde `precio_entrada_objetivo`, no
    desde el precio de relleno. El motor los conserva tal cual: publicarlos así
    es una decisión del sistema y el backtest no debe mejorarlos.
    """
    px = _precios([(100.0, 101.0, 96.0, 97.5)])
    eng, _ = _motor(px, usar_entrada_limitada=True)
    eng.schedule([_orden(limite=97.0)])
    eng.process_open(FECHAS[0])
    pos = eng.positions["X"]
    assert pos.stop == pytest.approx(90.0)
    assert pos.target == pytest.approx(120.0)
