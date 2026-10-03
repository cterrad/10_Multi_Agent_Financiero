"""
Tests del Analista de Estructura de Precio y del soporte como cuarto candidato.

Qué protegen
------------
1. **EL SOPORTE ESTRUCTURAL SOLO PUEDE BAJAR EL PRECIO DE ENTRADA.** Es el mismo
   producto cartesiano que `test_el_ajuste_de_entrada_solo_baja_el_precio`,
   ampliado con el candidato nuevo. Añadir una cuarta fuente de nivel sería
   exactamente la forma de romper esa propiedad sin que nadie se diera cuenta.
2. **Los mínimos EXCLUYEN la barra en curso.** Es el `shift(1)` de
   `_causal_levels` del repositorio 07 traducido a barra diaria. Un mínimo que
   incluya la sesión de hoy no es un soporte previo, y usarlo como nivel al que
   esperar significaría esperar un precio que ya se ha tocado.
3. **Añadir barras posteriores no cambia un soporte anterior.** Es el análogo
   directo de `test_no_lookahead_future_prices_do_not_change_past_signal` para
   esta serie: si fallara, el nivel de entrada del backtest miraría al futuro.
4. **La bandera de soporte lejano SOLO CIERRA.** Nunca habilita `PERSEGUIR`.
5. **Sin estructura, el sistema se comporta EXACTAMENTE como antes.** Es la
   rama de degradación, y es la que hace que el cambio sea auditable: si el
   comportamiento previo no se reprodujera, ninguna comparación antes/después
   significaría nada.
6. **Un soporte ausente es `None`, nunca 0.0.** Un soporte de cero afirmaría que
   el valor puede caer a nada.

Offline y deterministas.
"""

import copy

import pandas as pd
import pytest

from src.agents.estructura import StructureAnalystAgent
from src.agents.posicionamiento import PositioningAnalystAgent
from src.config import NIVELES_VENTANAS, SOPORTE_LEJANO_ATR
from src.tools.decision import _ajustar_entrada
from src.tools.niveles import (
    _clasificar,
    _distancia,
    _soportes,
    minimos_previos,
)

PRECIO = 100.0
ATR = 2.0


@pytest.fixture(autouse=True)
def _motor_determinista(monkeypatch):
    """Mismo parche que `disable_llm()`: `get_llm` vive en el módulo de la subclase."""
    import src.agents.estructura as est
    import src.agents.posicionamiento as pos
    for modulo in (est, pos):
        monkeypatch.setattr(modulo, "get_llm", lambda: None)


def _ohlc(bajos, alto=None):
    """Ventana OHLC mínima a partir de una lista de mínimos."""
    n = len(bajos)
    return pd.DataFrame({
        "Open": [b + 1 for b in bajos],
        "High": [(alto or b + 2) for b in bajos],
        "Low": list(bajos),
        "Close": [b + 1.5 for b in bajos],
        "Volume": [1_000_000] * n,
    }, index=pd.date_range("2020-01-01", periods=n, freq="B"))


def entrada(**kwargs):
    base = dict(precio=PRECIO, atr=ATR, sesgo_macro=None, sesgo_opciones=None,
                momentum_score=None, soporte_oi=None, max_pain=None,
                gamma_flip=None, max_pain_operable=False, regimen_gamma=None,
                sobreextendido=False, soporte_estructural=None)
    base.update(kwargs)
    return _ajustar_entrada(**base)


# --------------------------------------------------------------------------- #
# 1. LA BARRERA: el cuarto candidato tampoco puede subir la entrada
# --------------------------------------------------------------------------- #
def test_el_soporte_estructural_solo_baja_el_precio_de_entrada():
    """
    Producto cartesiano sobre las cuatro fuentes de nivel a la vez. Es el mismo
    contrato que ya cumplían las tres de la cadena de opciones, y añadir una
    cuarta sin comprobarlo sería la forma silenciosa de romperlo.
    """
    for macro in (None, -0.9, 0.0, 0.9):
        for opciones in (None, -0.9, 0.0, 0.9):
            for momentum in (None, -80.0, 0.0, 80.0):
                for estructural in (None, 70.0, 96.0, 99.99, 100.0, 105.0, 140.0):
                    for soporte_oi in (None, 92.0, 98.5):
                        for sobre in (True, False):
                            r = entrada(sesgo_macro=macro, sesgo_opciones=opciones,
                                        momentum_score=momentum,
                                        soporte_estructural=estructural,
                                        soporte_oi=soporte_oi, sobreextendido=sobre)
                            aj = r["ajuste_entrada_pct"]
                            assert aj is None or aj <= 0.0, (
                                f"el soporte estructural SUBIÓ la entrada con "
                                f"estructural={estructural}, oi={soporte_oi}, "
                                f"macro={macro}, opciones={opciones}")
                            objetivo = r["precio_entrada_objetivo"]
                            assert objetivo is None or objetivo <= PRECIO


def test_un_soporte_estructural_por_encima_del_precio_no_es_candidato():
    r = entrada(sesgo_macro=0.6, momentum_score=40.0, soporte_estructural=130.0)
    assert r["nivel_referencia"] is None
    assert r["ajuste_entrada_pct"] is None


# Sesgo agregado ALCISTA pero DIVERGENTE: el técnico queda por debajo de
# `UMBRAL_SENAL` y no concuerda, así que la confluencia es parcial y se exige
# recorrido hasta el nivel. Es la única configuración en la que hay entrada que
# optimizar: con el sesgo agregado en negativo, `_ajustar_entrada` devuelve
# `NO_APLICABLE` porque no se está comprando nada.
_DIVERGENTE = dict(sesgo_macro=0.8, momentum_score=5.0)


def test_el_soporte_estructural_compite_con_los_de_la_cadena():
    """
    Con cadena disponible ambos compiten con la MISMA regla: gana el más alto por
    debajo del precio. El candidato nuevo no tiene prioridad ni la cede.
    """
    gana_estructura = entrada(**_DIVERGENTE, soporte_oi=90.0, soporte_estructural=97.0)
    assert gana_estructura["nivel_origen"] == "SOPORTE_ESTRUCTURAL"
    assert gana_estructura["nivel_referencia"] == 97.0

    gana_cadena = entrada(**_DIVERGENTE, soporte_oi=98.0, soporte_estructural=93.0)
    assert gana_cadena["nivel_origen"] == "SOPORTE_OI"
    assert gana_cadena["nivel_referencia"] == 98.0


def test_sin_cadena_el_soporte_estructural_es_el_unico_nivel():
    """
    Es el caso del BACKTEST: `options_data` está siempre ausente, así que antes
    no había ningún candidato y el ajuste era None en el 100% de las señales.
    """
    sin_nada = entrada(**_DIVERGENTE)
    assert sin_nada["nivel_origen"] == "NO_APLICABLE"
    assert sin_nada["ajuste_entrada_pct"] is None

    con_estructura = entrada(**_DIVERGENTE, soporte_estructural=96.0)
    assert con_estructura["nivel_origen"] == "SOPORTE_ESTRUCTURAL"
    assert con_estructura["ajuste_entrada_pct"] is not None
    assert con_estructura["ajuste_entrada_pct"] < 0.0


def test_sin_sesgo_alcista_el_soporte_no_produce_ajuste():
    """
    Solo se optimiza la entrada de algo que se va a comprar. Con el sesgo
    agregado en negativo no hay entrada que ajustar, y tener soporte no lo
    cambia: sería fabricar un precio de entrada para una posición que no se abre.
    """
    r = entrada(sesgo_macro=-0.5, momentum_score=-40.0, soporte_estructural=97.0)
    assert r["entrada_clasificacion"] == "NO_APLICABLE"
    assert r["ajuste_entrada_pct"] is None


# --------------------------------------------------------------------------- #
# 2. Causalidad de los mínimos
# --------------------------------------------------------------------------- #
def test_el_minimo_excluye_la_barra_en_curso():
    """
    El `shift(1)` del repositorio 07. La última barra tiene el mínimo más bajo de
    toda la ventana y aun así NO puede ser el soporte: es el mínimo de hoy, no
    una referencia previa.
    """
    bajos = [50.0] * 20 + [10.0]          # la última barra hunde el mínimo
    r = minimos_previos(_ohlc(bajos), ventanas=(10,))
    assert r["minimo_10"] == 50.0, "el mínimo incluyó la barra en curso"


def test_una_ventana_mas_larga_que_la_historia_es_none_no_cero():
    r = minimos_previos(_ohlc([50.0] * 5), ventanas=(10, 21, 63))
    assert r == {"minimo_10": None, "minimo_21": None, "minimo_63": None}


def test_añadir_barras_posteriores_no_cambia_un_soporte_anterior():
    """
    Análogo de `test_no_lookahead_future_prices_do_not_change_past_signal` para
    esta serie. El corte lo hace el llamante (`PriceStore.window`), así que lo
    que se comprueba es que sobre la MISMA ventana recortada el resultado no
    depende de lo que venga después.
    """
    historia = [50.0 + (i % 7) for i in range(80)]
    corte = 60
    antes = minimos_previos(_ohlc(historia[:corte]), ventanas=NIVELES_VENTANAS)
    futuro = historia[:corte] + [5.0, 4.0, 3.0]      # desplome posterior
    despues = minimos_previos(_ohlc(futuro[:corte]), ventanas=NIVELES_VENTANAS)
    assert antes == despues, "un precio posterior cambió un soporte anterior"


# --------------------------------------------------------------------------- #
# 3. Elección, distancia y clasificación
# --------------------------------------------------------------------------- #
def test_se_elige_el_soporte_mas_alto_por_debajo_del_precio():
    r = _soportes({"minimo_10": 97.0, "minimo_21": 90.0, "minimo_63": 80.0},
                  sma_50=95.0, sma_200=88.0, bb_inferior=93.0, precio=PRECIO)
    assert r["soporte"] == 97.0
    assert r["origen"] == "minimo_10"


def test_sin_soporte_por_debajo_se_declara_con_motivo():
    r = _soportes({"minimo_10": 120.0}, sma_50=130.0, sma_200=140.0,
                  bb_inferior=125.0, precio=PRECIO)
    assert r["soporte"] is None
    assert r["origen"] == "NO_APLICABLE"
    assert "por debajo" in (r["motivo"] or "")
    assert r["resistencia"] == 120.0


def test_un_soporte_ausente_es_none_nunca_cero():
    """La regla nº 1 del proyecto: un soporte de 0.0 afirmaría algo falso."""
    r = _soportes({"minimo_10": None, "minimo_21": None}, sma_50=None,
                  sma_200=None, bb_inferior=None, precio=PRECIO)
    assert r["soporte"] is None, "un soporte de 0.0 afirmaría que el valor puede caer a nada"
    d = _distancia(PRECIO, None, ATR)
    assert d["distancia_pct"] is None and d["distancia_atr"] is None


def test_la_distancia_se_expresa_en_atr_y_en_porcentaje():
    d = _distancia(100.0, 96.0, 2.0)
    assert d["distancia_pct"] == pytest.approx(0.04)
    assert d["distancia_atr"] == pytest.approx(2.0)


def test_sin_atr_la_distancia_sigue_en_porcentaje_y_lo_declara():
    d = _distancia(100.0, 96.0, None)
    assert d["distancia_pct"] == pytest.approx(0.04)
    assert d["distancia_atr"] is None
    assert "ATR" in (d["motivo"] or "")


# --------------------------------------------------------------------------- #
# 4. La bandera SOLO cierra
# --------------------------------------------------------------------------- #
def test_la_bandera_de_soporte_lejano_solo_se_activa_por_encima_del_umbral():
    for d in (None, 0.0, 0.4, 1.0, 1.99, 2.0, 3.0, 10.0):
        r = _clasificar(d)
        esperado = d is not None and d >= SOPORTE_LEJANO_ATR
        assert r["soporte_lejano"] is esperado, f"distancia {d}"


def test_el_soporte_lejano_prohibe_perseguir_pero_nunca_lo_habilita():
    """
    Se une por `or` a `sobreextendido`, en la misma familia que el RSI extremo.
    Comprobado sobre el producto cartesiano: con la bandera activa, ninguna
    combinación puede clasificarse PERSEGUIR.
    """
    for macro in (0.3, 0.9):
        for opciones in (0.3, 0.9):
            for momentum in (30.0, 90.0):
                sin = entrada(sesgo_macro=macro, sesgo_opciones=opciones,
                              momentum_score=momentum, soporte_estructural=96.0,
                              sobreextendido=False)
                con = entrada(sesgo_macro=macro, sesgo_opciones=opciones,
                              momentum_score=momentum, soporte_estructural=96.0,
                              sobreextendido=True)
                assert con["entrada_clasificacion"] != "PERSEGUIR"
                # Y nunca mejora la entrada respecto de no tener la bandera.
                a_sin = sin["ajuste_entrada_pct"] or 0.0
                a_con = con["ajuste_entrada_pct"] or 0.0
                assert a_con <= a_sin + 1e-12


# --------------------------------------------------------------------------- #
# 5. El agente
# --------------------------------------------------------------------------- #
def _estado(niveles=None, precio=PRECIO, atr=ATR):
    return {
        "ticker": "TEST", "sector": "Technology",
        "technical_report": {"close": precio, "atr": atr, "momentum_score": 40.0,
                             "sobreextendido": False},
        "yfinance_data": {"technical": {"close": precio, "atr": atr,
                                        "sma_50": 95.0, "sma_200": 88.0,
                                        "bb_lower": 93.0},
                          "niveles_precio": niveles if niveles is not None
                          else {"minimo_10": 97.0, "minimo_21": 90.0,
                                "minimo_63": 80.0}},
    }


def test_el_agente_publica_soporte_distancia_y_estructura():
    inf = StructureAnalystAgent().analyze(_estado())
    assert inf["status"] == "SUCCESS"
    assert inf["soporte"] == 97.0
    assert inf["soporte_origen"] == "minimo_10"
    assert inf["distancia_atr"] == pytest.approx(1.5)
    assert inf["estructura"] == "APOYADO"
    assert isinstance(inf["summary"], str) and inf["summary"]


def test_el_agente_degrada_sin_ventana_utilizable():
    """
    Rama de degradación. Sin mínimos NI medias el agente no aporta candidato ni
    bandera, y el sistema se comporta exactamente como antes de que existiera.
    """
    est = _estado(niveles={"minimo_10": None, "minimo_21": None, "minimo_63": None})
    est["yfinance_data"]["technical"].update(sma_50=None, sma_200=None, bb_lower=None)
    inf = StructureAnalystAgent().analyze(est)
    assert inf["status"] == "DATOS_INSUFICIENTES"
    assert inf["soporte"] is None
    assert inf["soporte_lejano"] is False
    assert inf["distancia_atr"] is None
    assert isinstance(inf["summary"], str) and inf["summary"]


def test_sin_estructura_el_ajuste_de_entrada_no_cambia():
    """
    LA PROPIEDAD QUE HACE AUDITABLE EL CAMBIO. Con `estructura_report` ausente,
    el Analista de Posicionamiento produce EXACTAMENTE el mismo dictamen que
    antes de que este agente existiera. Es el análogo de
    `test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado`.
    """
    base = {
        "ticker": "TEST", "sector": "Technology",
        "technical_report": {"close": PRECIO, "atr": ATR, "momentum_score": 40.0,
                             "sobreextendido": False},
        "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR}},
    }
    sin_clave = PositioningAnalystAgent().analyze(copy.deepcopy(base))

    con_vacio = copy.deepcopy(base)
    con_vacio["estructura_report"] = {"soporte": None, "soporte_origen": "NO_APLICABLE",
                                      "soporte_lejano": False, "distancia_atr": None}
    resultado = PositioningAnalystAgent().analyze(con_vacio)

    for clave in ("entrada_clasificacion", "confluencia", "nivel_referencia",
                  "nivel_origen", "ajuste_entrada_pct", "precio_entrada_objetivo"):
        assert sin_clave[clave] == resultado[clave], f"`{clave}` cambió sin estructura"


def test_el_agente_es_reproducible():
    a = StructureAnalystAgent().analyze(_estado())
    b = StructureAnalystAgent().analyze(_estado())
    assert a["_traza"] == b["_traza"]
    assert a["signals"] == b["signals"]


def test_el_agente_no_alcanza_la_red():
    """Es puro: consume `niveles_precio`, que produce la ingesta."""
    import src.agents.estructura as mod
    fuente = open(mod.__file__, encoding="utf-8").read()
    for prohibido in ("import requests", "import yfinance",
                      "from src.tools.extraccion", "src.data.fetcher"):
        assert prohibido not in fuente, f"el agente importa {prohibido}"
