"""
Construcción de cartera: correlación, límites y presupuesto de riesgo.

La capa que el sistema no tenía. `cli.py` recorría los tickers de forma
independiente y nadie miraba nunca el conjunto: el informe recomendaba cuatro
posiciones sin decir si eran cuatro apuestas o una sola repetida, ni sumaba la
exposición.

Offline y determinista: series de precios sintéticas, sin red.
"""

import numpy as np
import pandas as pd
import pytest

from src.config import (
    CORRELACION_ALTA,
    EXPOSICION_BRUTA_MAXIMA,
    LIMITE_POR_SECTOR,
    MAXIMO_POSICIONES,
    PESO_MINIMO_OPERABLE,
    RIESGO_TOTAL_CARTERA_PCT,
)
from src.portfolio import PortfolioConstructor


def resultado(ticker, *, peso, sector="Technology", rating="COMPRA",
              estilo="CALIDAD_COMPUESTA", conviccion=70.0, precio=100.0,
              stop=90.0, volatilidad=0.25):
    return {
        "ticker": ticker,
        "company_name": f"{ticker} Inc.",
        "sector": sector,
        "quality_report": {"style_classification": estilo,
                           "conviccion_fundamental": {"valor": conviccion}},
        "technical_report": {"volatilidad_anual": volatilidad},
        "final_decision": {
            "rating": rating, "peso_objetivo": peso, "current_price": precio,
            "stop_loss_atr": stop, "take_profit_atr": precio * 1.2,
            "dimensionado": {"motivo": "prueba"},
        },
    }


def series(tickers, *, correlacion=0.0, n=200, seed=7):
    """Series de cierre con una correlación objetivo entre todos los pares."""
    rng = np.random.default_rng(seed)
    comun = rng.normal(0, 0.01, n)
    idx = pd.bdate_range("2024-01-01", periods=n)
    out = {}
    peso = correlacion ** 0.5
    for t in tickers:
        propio = rng.normal(0, 0.01, n)
        rets = peso * comun + (1 - peso ** 2) ** 0.5 * propio
        out[t] = pd.Series(100 * np.exp(np.cumsum(rets)), index=idx)
    return out


# --------------------------------------------------------------------------- #
# 1. Casos base
# --------------------------------------------------------------------------- #
def test_sin_senales_de_compra_la_cartera_queda_en_liquidez():
    c = PortfolioConstructor().construir(
        [resultado("A", peso=0.0, rating="MANTENER")], None)
    assert c.posiciones == []
    assert c.liquidez == 1.0
    assert "liquidez" in c.restricciones_activadas[0].lower()


def test_los_pesos_se_conservan_si_ninguna_restriccion_aplica():
    c = PortfolioConstructor().construir(
        [resultado("A", peso=0.04, sector="Technology"),
         resultado("B", peso=0.03, sector="Healthcare")], None)
    assert {p.ticker: round(p.peso_final, 4) for p in c.posiciones} == {"A": 0.04, "B": 0.03}
    assert c.exposicion_bruta == pytest.approx(0.07)
    assert c.liquidez == pytest.approx(0.93)


def test_los_candidatos_sin_peso_se_declaran_con_su_motivo():
    c = PortfolioConstructor().construir(
        [resultado("A", peso=0.04), resultado("B", peso=0.0, rating="VENTA")], None)
    assert [e["ticker"] for e in c.excluidas] == ["B"]
    assert c.excluidas[0]["rating"] == "VENTA"


# --------------------------------------------------------------------------- #
# 2. Correlación
# --------------------------------------------------------------------------- #
def test_la_correlacion_alta_recorta_los_pesos():
    """Dos valores con correlación 0.9 no son dos apuestas, son una y media."""
    entradas = [resultado(t, peso=0.05, sector=f"S{i}") for i, t in enumerate("ABC")]

    independientes = PortfolioConstructor().construir(
        entradas, series(list("ABC"), correlacion=0.0, seed=1))
    solapadas = PortfolioConstructor().construir(
        entradas, series(list("ABC"), correlacion=0.95, seed=1))

    assert solapadas.exposicion_bruta < independientes.exposicion_bruta
    assert any("correlación" in r for r in solapadas.restricciones_activadas)
    assert all(p.correlacion_media is not None for p in solapadas.posiciones)


def test_sin_matriz_de_correlaciones_se_declara_la_limitacion():
    """
    Es preferible no corregir a corregir con una matriz inventada — pero hay
    que decirlo, porque la diversificación declarada pasa a ser nominal.
    """
    c = PortfolioConstructor().construir([resultado("A", peso=0.04)], None)
    assert any("Sin matriz de correlaciones" in r for r in c.restricciones_activadas)
    assert "no se puede afirmar" in c.diagnostico.get("nota_diversificacion", "")


def test_los_pares_muy_correlacionados_se_listan():
    entradas = [resultado(t, peso=0.04, sector=f"S{i}") for i, t in enumerate("AB")]
    c = PortfolioConstructor().construir(entradas, series(list("AB"), correlacion=0.95))
    pares = c.diagnostico["pares_muy_correlacionados"]
    assert pares and pares[0]["correlacion"] >= CORRELACION_ALTA


# --------------------------------------------------------------------------- #
# 3. Límites
# --------------------------------------------------------------------------- #
def test_el_tope_sectorial_escala_proporcionalmente():
    entradas = [resultado(t, peso=0.10, sector="Technology") for t in "ABCDE"]
    c = PortfolioConstructor().construir(entradas, None)
    assert c.por_sector["Technology"] <= LIMITE_POR_SECTOR + 1e-9
    assert any("Tope sectorial" in r for r in c.restricciones_activadas)
    # El escalado es proporcional: todas conservan el mismo peso relativo.
    pesos = [p.peso_final for p in c.posiciones]
    assert max(pesos) == pytest.approx(min(pesos))


def test_el_presupuesto_de_riesgo_agregado_limita_la_cartera():
    """
    Riesgo aportado = peso × distancia al stop. La suma es la pérdida si TODAS
    las posiciones tocan su stop a la vez — el escenario que importa, porque
    las correlaciones tienden a 1 en las caídas.
    """
    # Stops muy lejanos (-40%) en sectores distintos para esquivar el tope
    # sectorial y aislar el presupuesto de riesgo.
    entradas = [resultado(t, peso=0.10, sector=f"S{i}", precio=100.0, stop=60.0)
                for i, t in enumerate("ABCDEF")]
    c = PortfolioConstructor().construir(entradas, None)
    assert c.riesgo_total <= RIESGO_TOTAL_CARTERA_PCT + 1e-9
    assert any("presupuesto de riesgo" in r.lower() for r in c.restricciones_activadas)


def test_el_tope_de_exposicion_bruta_se_respeta():
    entradas = [resultado(t, peso=0.10, sector=f"S{i}", precio=100.0, stop=98.0)
                for i, t in enumerate("ABCDEFGHIJKL")]
    c = PortfolioConstructor().construir(entradas, None)
    assert c.exposicion_bruta <= EXPOSICION_BRUTA_MAXIMA + 1e-9


def test_el_numero_maximo_de_posiciones_conserva_las_de_mas_conviccion():
    entradas = [resultado(f"T{i}", peso=0.02, sector=f"S{i}", conviccion=float(i))
                for i in range(MAXIMO_POSICIONES + 5)]
    c = PortfolioConstructor().construir(entradas, None)
    assert len(c.posiciones) <= MAXIMO_POSICIONES
    convicciones = [p.conviccion for p in c.posiciones]
    assert min(convicciones) >= 5.0  # las cinco de menor convicción quedaron fuera


def test_los_residuos_por_debajo_del_minimo_operable_se_descartan():
    """El coste de operar supera la aportación de una posición diminuta."""
    entradas = [resultado("A", peso=PESO_MINIMO_OPERABLE / 2, sector="Technology")]
    c = PortfolioConstructor().construir(entradas, None)
    assert c.posiciones == []
    assert "mínimo operable" in c.excluidas[0]["motivo"]


# --------------------------------------------------------------------------- #
# 4. Diagnóstico
# --------------------------------------------------------------------------- #
def test_las_posiciones_efectivas_miden_concentracion_real():
    """
    Inverso del índice de Herfindahl: cuántas posiciones equiponderadas
    producirían la misma concentración.
    """
    equilibrada = PortfolioConstructor().construir(
        [resultado(t, peso=0.04, sector=f"S{i}") for i, t in enumerate("ABCD")], None)
    concentrada = PortfolioConstructor().construir(
        [resultado("A", peso=0.09, sector="S0"),
         resultado("B", peso=0.012, sector="S1"),
         resultado("C", peso=0.012, sector="S2"),
         resultado("D", peso=0.012, sector="S3")], None)

    assert equilibrada.diagnostico["posiciones_efectivas"] == pytest.approx(4.0, abs=0.05)
    assert concentrada.diagnostico["posiciones_efectivas"] < 3.0


def test_el_ratio_de_diversificacion_distingue_apuestas_independientes():
    """
    Ratio 1.0 significa que las posiciones se mueven como una sola. Es la
    pregunta que el informe anterior no se hacía.
    """
    entradas = [resultado(t, peso=0.03, sector=f"S{i}") for i, t in enumerate("ABCD")]

    independientes = PortfolioConstructor().construir(
        entradas, series(list("ABCD"), correlacion=0.0, seed=11))
    solapadas = PortfolioConstructor().construir(
        entradas, series(list("ABCD"), correlacion=0.99, seed=11))

    ratio_ind = independientes.diagnostico.get("ratio_diversificacion")
    ratio_sol = solapadas.diagnostico.get("ratio_diversificacion")
    assert ratio_ind is not None and ratio_sol is not None
    assert ratio_ind > ratio_sol
    assert ratio_sol == pytest.approx(1.0, abs=0.15)


def test_la_liquidez_no_invertida_se_contabiliza():
    """
    El backtest documenta un 72% de la cartera parado al 0%. Declararlo evita
    repetir esa distorsión al comparar contra el índice.
    """
    c = PortfolioConstructor().construir([resultado("A", peso=0.05)], None)
    d = c.diagnostico
    assert d["liquidez_pct"] == pytest.approx(95.0, abs=0.01)
    assert d["aportacion_liquidez_anual_pct"] > 0


def test_la_cartera_serializa_a_json_plano():
    """El informe y `daily_selection.json` consumen esta representación."""
    c = PortfolioConstructor().construir(
        [resultado("A", peso=0.04), resultado("B", peso=0.0, rating="VENTA")], None)
    d = c.a_dict()
    assert set(d) >= {"posiciones", "excluidas", "exposicion_bruta_pct", "liquidez_pct",
                      "riesgo_total_pct", "por_sector_pct", "diagnostico",
                      "restricciones_activadas"}
    assert d["posiciones"][0]["peso_final_pct"] == pytest.approx(4.0)


# --------------------------------------------------------------------------- #
# 5. Posiciones ya abiertas (integración con el motor histórico)
# --------------------------------------------------------------------------- #
def existente(ticker, *, peso, sector="Technology", precio=100.0, stop=90.0,
              volatilidad=0.25):
    return {"ticker": ticker, "sector": sector, "peso": peso, "rating": "COMPRA",
            "estilo": "CALIDAD_COMPUESTA", "conviccion": 70.0, "precio": precio,
            "stop": stop, "volatilidad": volatilidad}


def test_las_posiciones_abiertas_consumen_presupuesto_sectorial():
    """
    Sin esto, cada rebalanceo respetaría el tope del 30% por sector y aun así
    la cartera acabaría con el 90% en un solo sector tras tres rebalanceos.
    """
    c = PortfolioConstructor().construir(
        [resultado("NUEVO", peso=0.10, sector="Technology")],
        None,
        posiciones_existentes=[existente("VIEJO", peso=0.25, sector="Technology")],
    )
    assert c.por_sector["Technology"] <= LIMITE_POR_SECTOR + 1e-9
    nuevo = next(p for p in c.posiciones if p.ticker == "NUEVO")
    viejo = next(p for p in c.posiciones if p.ticker == "VIEJO")
    # La abierta no se reescala; el recorte recae íntegro sobre la nueva.
    assert viejo.peso_final == pytest.approx(0.25)
    assert nuevo.peso_final == pytest.approx(0.05, abs=1e-6)


def test_un_sector_ya_lleno_no_admite_incorporaciones():
    c = PortfolioConstructor().construir(
        [resultado("NUEVO", peso=0.08, sector="Technology")],
        None,
        posiciones_existentes=[existente("VIEJO", peso=LIMITE_POR_SECTOR, sector="Technology")],
    )
    assert [p.ticker for p in c.posiciones] == ["VIEJO"]
    assert c.excluidas[0]["ticker"] == "NUEVO"


def test_las_posiciones_abiertas_no_se_reescalan_nunca():
    """
    Reajustar la cartera entera en cada rebalanceo generaría rotación constante
    cuyo coste se comería cualquier ventaja del ajuste.
    """
    existentes = [existente(f"V{i}", peso=0.20, sector=f"S{i}", precio=100.0, stop=60.0)
                  for i in range(5)]
    c = PortfolioConstructor().construir(
        [resultado("NUEVO", peso=0.10, sector="Healthcare", precio=100.0, stop=60.0)],
        None, posiciones_existentes=existentes,
    )
    abiertas = [p for p in c.posiciones if p.fija]
    assert len(abiertas) == 5
    assert all(p.peso_final == pytest.approx(0.20) for p in abiertas)
    # El presupuesto de riesgo ya está agotado por las abiertas: la nueva cae.
    nuevas = [p for p in c.posiciones if not p.fija]
    assert nuevas == []


def test_el_tope_de_posiciones_cuenta_las_ya_abiertas():
    existentes = [existente(f"V{i}", peso=0.01, sector=f"S{i}")
                  for i in range(MAXIMO_POSICIONES)]
    c = PortfolioConstructor().construir(
        [resultado("NUEVO", peso=0.05, sector="Healthcare")],
        None, posiciones_existentes=existentes,
    )
    assert all(p.fija for p in c.posiciones)
    assert any(e["ticker"] == "NUEVO" for e in c.excluidas)


def test_la_cartera_agregada_incluye_abiertas_y_nuevas():
    c = PortfolioConstructor().construir(
        [resultado("NUEVO", peso=0.04, sector="Healthcare")],
        None,
        posiciones_existentes=[existente("VIEJO", peso=0.06, sector="Technology")],
    )
    assert {p.ticker for p in c.posiciones} == {"VIEJO", "NUEVO"}
    assert c.exposicion_bruta == pytest.approx(0.10)
    assert c.diagnostico["n_posiciones"] == 2
    d = c.a_dict()
    assert [p["ya_en_cartera"] for p in d["posiciones"]] == [True, False]
