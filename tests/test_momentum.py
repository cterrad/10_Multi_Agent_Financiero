"""
Clasificador de momentum: las tres patologías que tenía y no puede recuperar.

El sistema anterior sumaba puntos enteros y los mapeaba a etiquetas con una
escalera de `if`. Enumerando sus 72 estados alcanzables aparecieron tres
defectos, los tres reproducidos aquí con los datos reales del informe del
2026-08-21.

Offline y determinista: el LLM se sustituye por `None`.
"""

import itertools

import pytest

import src.agents.technical as tech_mod
from src.config import (
    MOMENTUM_ALCISTA,
    MOMENTUM_ALCISTA_FUERTE,
    MOMENTUM_BAJISTA,
    MOMENTUM_BAJISTA_FUERTE,
    RSI_SOBRECOMPRA_EXTREMA,
)


@pytest.fixture(autouse=True)
def sin_llm(monkeypatch):
    """Ningún test de este módulo puede salir a la red ni a un proveedor de LLM."""
    monkeypatch.setattr(tech_mod, "get_llm", lambda: None)


def _estado(**tech):
    base = {
        "close": 100.0, "rsi": 50.0, "macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0,
        "bb_upper": 110.0, "bb_lower": 90.0, "atr": 2.0, "sma_50": 100.0,
        "sma_200": 100.0, "volume_rel": 1.0, "dist_sma_50_pct": 0.0,
        "dist_sma_200_pct": 0.0, "pendiente_sma_50": 0.0, "posicion_rango_52w": 0.5,
        "volatilidad_anual": 0.3, "atr_pct": 0.02,
    }
    base.update(tech)
    return {
        "ticker": "T",
        "yfinance_data": {"technical": base, "price_history_summary": {}},
    }


def _analizar(**tech):
    return tech_mod.TechnicalAnalystAgent().analyze(_estado(**tech))


# --------------------------------------------------------------------------- #
# 1. Zona muerta: el caso NEM
# --------------------------------------------------------------------------- #
def test_cruce_de_la_muerte_con_precio_muy_por_encima_no_es_tendencia_bajista():
    """
    NEM el 2026-08-21: precio 127.64, SMA50 100.76, SMA200 105.82, RSI 83.91.

    El clasificador anterior sumaba 2 puntos bajistas por «cruce de la muerte»
    (SMA50 < SMA200) pese a que el precio cotizaba un 27% POR ENCIMA de ambas
    medias, y con 3 puntos alcistas contra 3 bajistas caía en el `else` →
    NEUTRAL. El cruce era el retardo aritmético de dos medias tras un desplome
    anterior, no una tendencia bajista vigente.
    """
    r = _analizar(close=127.64, rsi=83.91, macd=7.181, macd_signal=5.156,
                  macd_hist=2.025, bb_upper=132.24, bb_lower=82.56, atr=4.89,
                  sma_50=100.76, sma_200=105.82, dist_sma_50_pct=0.2668,
                  dist_sma_200_pct=0.2062, pendiente_sma_50=0.11)

    assert r["estado_tendencia"] == "RECUPERACION"
    assert r["momentum_classification"] != "NEUTRAL"
    assert r["momentum_score"] > 0
    # Y el RSI extremo tiene que quedar declarado, aunque no invierta la etiqueta.
    assert r["rsi_estado"] == "SOBRECOMPRA_EXTREMA"
    assert r["sobreextendido"] is True


def test_cruce_de_la_muerte_con_precio_por_debajo_si_es_tendencia_bajista():
    """La corrección anterior no puede haber roto la detección legítima."""
    r = _analizar(close=85.0, sma_50=95.0, sma_200=105.0,
                  dist_sma_50_pct=-0.105, dist_sma_200_pct=-0.19,
                  pendiente_sma_50=-0.04)
    assert r["estado_tendencia"] == "BAJISTA_CONFIRMADA"
    assert r["momentum_score"] < 0


# --------------------------------------------------------------------------- #
# 2. Monotonía
# --------------------------------------------------------------------------- #
def test_la_etiqueta_es_monotona_en_la_puntuacion():
    """
    Con 4 puntos alcistas, el sistema anterior pasaba de NEUTRAL a BAJISTA al
    subir de 3 a 4 bajistas; pero con 5 alcistas ignoraba el bajismo por
    completo, así que (5, 4) daba ALCISTA_FUERTE y (4, 4) daba BAJISTA. Más
    fuerza alcista podía empeorar la etiqueta.
    """
    orden = {"BAJISTA_FUERTE": 0, "BAJISTA": 1, "NEUTRAL": 2,
             "ALCISTA": 3, "ALCISTA_FUERTE": 4}
    etiquetar = tech_mod.TechnicalAnalystAgent._etiqueta

    puntuaciones = [p / 2.0 for p in range(-200, 201)]
    niveles = [orden[etiquetar(p)] for p in puntuaciones]
    assert all(b >= a for a, b in zip(niveles, niveles[1:])), \
        "La etiqueta empeora al subir la puntuación: el clasificador no es monótono"


def test_mejorar_un_componente_nunca_empeora_la_puntuacion():
    """Monotonía extremo a extremo, no solo en el corte final."""
    agente = tech_mod.TechnicalAnalystAgent()
    base = dict(close=100.0, sma_50=98.0, sma_200=95.0, dist_sma_200_pct=0.0526,
                pendiente_sma_50=0.02, atr=2.0)

    anterior = None
    for hist in (-2.0, -1.0, 0.0, 1.0, 2.0):
        score = agente.analyze(_estado(macd_hist=hist, macd=hist,
                                       macd_signal=0.0, **base))["momentum_score"]
        if anterior is not None:
            assert score >= anterior, "Un MACD más alcista bajó la puntuación"
        anterior = score


# --------------------------------------------------------------------------- #
# 3. Escala del RSI
# --------------------------------------------------------------------------- #
def test_el_rsi_penaliza_en_proporcion_al_exceso():
    """Un RSI de 70.1 y uno de 95.0 restaban exactamente lo mismo."""
    agente = tech_mod.TechnicalAnalystAgent()
    aportes = [agente.analyze(_estado(rsi=r))["contribuciones"]["rsi"]
               for r in (71.0, 78.0, 85.0, 95.0)]
    assert all(b < a for a, b in zip(aportes, aportes[1:])), \
        "La penalización por sobrecompra no crece con el exceso"


@pytest.mark.parametrize("rsi,estado", [
    (95.0, "SOBRECOMPRA_EXTREMA"),
    (83.91, "SOBRECOMPRA_EXTREMA"),
    (75.0, "SOBRECOMPRA"),
    (60.0, "ALCISTA_SALUDABLE"),
    (47.95, "NEUTRAL"),
    (39.27, "NEUTRAL"),
    (25.0, "SOBREVENTA"),
    (12.0, "SOBREVENTA_EXTREMA"),
])
def test_el_estado_del_rsi_coincide_con_el_numero(rsi, estado):
    """
    El informe anterior imprimía «en zona de fuerte impulso» con RSI de 39.3 y
    etiquetaba NEUTRAL un RSI de 83.9. El estado tiene que ser función del
    número y nada más.
    """
    assert _analizar(rsi=rsi)["rsi_estado"] == estado


def test_sobreextendido_se_declara_por_encima_del_umbral_extremo():
    assert _analizar(rsi=RSI_SOBRECOMPRA_EXTREMA + 1)["sobreextendido"] is True
    assert _analizar(rsi=65.0)["sobreextendido"] is False


# --------------------------------------------------------------------------- #
# 4. Momentum relativo
# --------------------------------------------------------------------------- #
def test_el_momentum_se_mide_contra_el_indice_cuando_hay_referencia():
    """
    Sin benchmark, «el valor sube un 20%» no distingue habilidad de selección
    de simple exposición al mercado.
    """
    agente = tech_mod.TechnicalAnalystAgent()
    precios = {"change_12m_pct": 0.30, "change_1m_pct": 0.02}

    st = _estado()
    st["yfinance_data"]["price_history_summary"] = precios
    sin_bench = agente.analyze(st)

    st_bench = _estado()
    st_bench["yfinance_data"]["price_history_summary"] = precios
    st_bench["benchmark_data"] = {"ticker": "SPY", "change_12m_pct": 0.28}
    con_bench = agente.analyze(st_bench)

    assert sin_bench["momentum_relativo_12m"] is None
    assert con_bench["momentum_relativo_12m"] is not None
    # Un valor que apenas bate al índice debe puntuar menos que en absoluto.
    assert con_bench["contribuciones"]["momentum_precio"] < \
        sin_bench["contribuciones"]["momentum_precio"]


def test_el_momentum_excluye_el_ultimo_mes():
    """
    Definición estándar del factor: 12 meses excluyendo el más reciente, que
    muestra reversión a corto plazo y contamina la señal.
    """
    agente = tech_mod.TechnicalAnalystAgent()

    st_a = _estado()
    st_a["yfinance_data"]["price_history_summary"] = {"change_12m_pct": 0.30,
                                                      "change_1m_pct": 0.25}
    st_b = _estado()
    st_b["yfinance_data"]["price_history_summary"] = {"change_12m_pct": 0.30,
                                                      "change_1m_pct": 0.0}

    # Mismo retorno a 12 meses, pero A lo debe casi todo al último mes: su
    # momentum de 11 meses es mucho menor.
    assert agente.analyze(st_a)["contribuciones"]["momentum_precio"] < \
        agente.analyze(st_b)["contribuciones"]["momentum_precio"]


# --------------------------------------------------------------------------- #
# 5. Contrato con el resto del sistema
# --------------------------------------------------------------------------- #
def test_las_etiquetas_siguen_siendo_las_que_espera_el_fund_manager():
    etiquetar = tech_mod.TechnicalAnalystAgent._etiqueta
    assert etiquetar(MOMENTUM_ALCISTA_FUERTE) == "ALCISTA_FUERTE"
    assert etiquetar(MOMENTUM_ALCISTA) == "ALCISTA"
    assert etiquetar(0.0) == "NEUTRAL"
    assert etiquetar(MOMENTUM_BAJISTA) == "BAJISTA"
    assert etiquetar(MOMENTUM_BAJISTA_FUERTE) == "BAJISTA_FUERTE"


def test_las_contribuciones_suman_la_puntuacion():
    """El desglose que se publica en el informe tiene que cuadrar."""
    r = _analizar(rsi=62.0, macd_hist=1.2, close=105.0, sma_50=100.0, sma_200=95.0,
                  dist_sma_200_pct=0.105, pendiente_sma_50=0.03)
    assert sum(r["contribuciones"].values()) == pytest.approx(r["momentum_score"], abs=0.01)


def test_sin_medias_moviles_no_revienta():
    r = _analizar(close=0.0, sma_50=0.0, sma_200=0.0)
    assert r["estado_tendencia"] == "NO_EVALUABLE"
    assert isinstance(r["summary"], str)
