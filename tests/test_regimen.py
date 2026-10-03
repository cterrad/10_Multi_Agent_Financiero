"""
Tests del Analista de Régimen de Volatilidad y de su fuente point-in-time.

Qué protegen
------------
1. **LA SERIE SE FILTRA POR FECHA DE PUBLICACIÓN, NUNCA POR LA DE OBSERVACIÓN.**
   Es el análogo exacto de `test_serie_semanal_filtra_por_publicacion` (COT) y de
   `test_fundamentals_respect_filed_not_end` (XBRL). Si se relaja, el backtest
   deja de medir nada: una observación semanal referida al miércoles no es
   pública hasta el jueves, y usarla el miércoles es operar con datos que nadie
   tenía.
2. **Añadir observaciones posteriores no cambia una lectura anterior.** Análogo
   de `test_no_lookahead_future_prices_do_not_change_past_signal` para esta
   serie.
3. **EL VETO DE RÉGIMEN SOLO BAJA EL RATING.** Producto cartesiano completo,
   igual que `test_los_vetos_solo_bajan_el_rating`.
4. **La puerta cerrada SOLO cierra.** Nunca habilita `PERSEGUIR`.
5. **Sin régimen, el rating no cambia.** La rama de degradación, y con la puerta
   ABIERTA: cerrarla por precaución ante la ausencia de dato convertiría una
   laguna de cobertura en una restricción de cartera, que es la forma inversa
   del defecto «ausencia ≠ cero».
6. **Un vintage cacheado NUNCA se sobrescribe**, y una redescarga con contenido
   distinto levanta excepción en lugar de reemplazarlo en silencio.
7. **Ausencia ≠ cero**: sin serie, el nivel y el z-score son `None`, no 0.0.

Offline y deterministas: no se hace ni una petición de red.
"""

import copy
import json

import pytest

from src.agents.fund_manager import FundManagerAgent
from src.agents.posicionamiento import PositioningAnalystAgent
from src.agents.regimen import RegimeAnalystAgent
from src.config import REGIMEN_MINIMO_OBSERVACIONES, REGIMEN_VENTANA_ZSCORE
from src.data.fred import cache as fred_cache
from src.data.fred.cache import VintageDivergente
from src.data.fred.serie import serie_diaria
from src.tools.decision import ESCALERA, _ajustar_entrada, aplicar_vetos
from src.tools.regimen import _clasificar_regimen, _curva, _zscore

PRECIO = 100.0
ATR = 2.0


@pytest.fixture(autouse=True)
def _motor_determinista(monkeypatch):
    import src.agents.fund_manager as fm
    import src.agents.posicionamiento as pos
    import src.agents.regimen as reg
    for modulo in (fm, pos, reg):
        monkeypatch.setattr(modulo, "get_llm", lambda: None)


def _obs(valores, desde="2024-01-01", retardo_dias=0):
    """Observaciones con fecha de publicación desplazada `retardo_dias`."""
    import datetime as dt
    d0 = dt.date.fromisoformat(desde)
    out = []
    for i, v in enumerate(valores):
        f_obs = d0 + dt.timedelta(days=i)
        out.append({"serie": "VIXCLS", "fecha": f_obs.isoformat(),
                    "fecha_publicacion": (f_obs + dt.timedelta(days=retardo_dias)).isoformat(),
                    "valor": v})
    return out


# --------------------------------------------------------------------------- #
# 1. LA BARRERA POINT-IN-TIME
# --------------------------------------------------------------------------- #
def test_la_serie_filtra_por_publicacion_y_no_por_observacion(tmp_path):
    """
    ESTE ES EL TEST QUE HACE VÁLIDO EL BACKTEST DE ESTA CAPA.

    Una observación referida al día D pero publicada el D+1 NO puede ser visible
    consultando el día D. Es el mismo par `filed`/`end` de los hechos XBRL y el
    mismo `fecha_informe`/`fecha_publicacion` del COT.
    """
    filas = _obs([10.0, 11.0, 12.0, 13.0], desde="2024-03-01", retardo_dias=1)
    fred_cache.escribir_serie("VIXCLS", 2024, filas, directorio=tmp_path)

    # El 2024-03-03 solo son públicas las observaciones del 1 y del 2.
    r = serie_diaria("VIXCLS", as_of="2024-03-03", dias=400,
                     offline=True, directorio=tmp_path)
    fechas = [o["fecha"] for o in r["observaciones"]]
    assert fechas == ["2024-03-01", "2024-03-02"], (
        f"se coló una observación aún no publicada: {fechas}")

    # Un día después, la del 3 ya es pública.
    r2 = serie_diaria("VIXCLS", as_of="2024-03-04", dias=400,
                      offline=True, directorio=tmp_path)
    assert [o["fecha"] for o in r2["observaciones"]] == [
        "2024-03-01", "2024-03-02", "2024-03-03"]


def test_anadir_observaciones_posteriores_no_cambia_una_lectura_anterior(tmp_path):
    """
    Análogo de `test_no_lookahead_future_prices_do_not_change_past_signal`. Si
    ampliar la serie cambiara lo que se sabía en una fecha pasada, el z-score de
    2018 dependería de lo ocurrido en 2024.
    """
    cortas = _obs([10.0 + (i % 5) for i in range(40)], desde="2024-01-01")
    fred_cache.escribir_serie("VIXCLS", 2024, cortas, directorio=tmp_path)
    antes = serie_diaria("VIXCLS", as_of="2024-02-01", dias=400,
                         offline=True, directorio=tmp_path)

    largas = cortas + _obs([80.0] * 20, desde="2024-02-10")
    # Se escribe en OTRO directorio: el vintage original es inmutable (ver el
    # test de más abajo), así que no se puede sobrescribir.
    otro = tmp_path / "ampliada"
    otro.mkdir()
    fred_cache.escribir_serie("VIXCLS", 2024, largas, directorio=otro)
    despues = serie_diaria("VIXCLS", as_of="2024-02-01", dias=400,
                           offline=True, directorio=otro)

    assert antes["observaciones"] == despues["observaciones"], (
        "una observación posterior cambió lo conocible en una fecha anterior")


def test_un_vintage_cacheado_nunca_se_sobrescribe(tmp_path):
    """
    Que el proveedor reescriba historia ya consumida es un EVENTO que registrar,
    no algo que absorber en silencio: cualquier estudio ejecutado con la versión
    anterior dejaría de ser reproducible sin que nada lo dijera.
    """
    filas = _obs([10.0, 11.0], desde="2024-05-01")
    info = fred_cache.escribir_serie("VIXCLS", 2024, filas, directorio=tmp_path)
    assert info["escrito"] is True

    # Reescribir lo MISMO es inocuo y no vuelve a tocar el disco.
    repetido = fred_cache.escribir_serie("VIXCLS", 2024, filas, directorio=tmp_path)
    assert repetido["escrito"] is False
    assert repetido["huella"] == info["huella"]

    # Reescribir algo DISTINTO levanta.
    distintas = _obs([10.0, 99.0], desde="2024-05-01")
    with pytest.raises(VintageDivergente):
        fred_cache.escribir_serie("VIXCLS", 2024, distintas, directorio=tmp_path)

    # Y el fichero en disco sigue siendo el original.
    en_disco = fred_cache.leer_serie("VIXCLS", 2024, directorio=tmp_path)
    assert en_disco == filas


def test_una_serie_ausente_se_declara_y_no_devuelve_ceros(tmp_path):
    r = serie_diaria("NO_EXISTE", as_of="2024-06-01", dias=400,
                     offline=True, directorio=tmp_path)
    assert r["observaciones"] == []
    assert r["n_observaciones"] == 0
    assert r["fallos"], "una serie no disponible debe declarar su motivo"


# --------------------------------------------------------------------------- #
# 2. El scorer: ausencia ≠ cero
# --------------------------------------------------------------------------- #
def test_sin_observaciones_el_nivel_y_el_zscore_son_none():
    r = _zscore([])
    assert r["nivel"] is None and r["z"] is None
    assert r["motivo"]


def test_por_debajo_del_minimo_no_se_emite_zscore():
    """
    Misma regla que los percentiles de opciones: se declara
    DATOS_INSUFICIENTES en vez de asumir la media. Un z de 0.0 afirmaría que la
    volatilidad está exactamente en su media.
    """
    pocas = _obs([15.0] * (REGIMEN_MINIMO_OBSERVACIONES - 1))
    r = _zscore(pocas)
    assert r["nivel"] == 15.0, "el NIVEL sí es conocible con una sola observación"
    assert r["z"] is None
    assert str(REGIMEN_MINIMO_OBSERVACIONES) in (r["motivo"] or "")


def test_el_zscore_se_calcula_sobre_la_ventana_movil():
    valores = [10.0 + (i % 4) for i in range(REGIMEN_VENTANA_ZSCORE)] + [40.0]
    r = _zscore(_obs(valores))
    assert r["nivel"] == 40.0
    assert r["z"] is not None and r["z"] > 3.0


def test_sin_una_de_las_dos_series_la_curva_es_none():
    r = _curva(20.0, None)
    assert r["ratio_curva"] is None and r["invertida"] is False
    assert r["motivo"]


def test_la_curva_invertida_solo_agrava_nunca_atenua():
    """
    `VIX > VIX3M` significa estrés inmediato. Puede empeorar la clasificación un
    escalón; jamás mejorarla. Una curva en contango durante un pánico no
    convierte el pánico en calma.
    """
    for nivel in (10.0, 16.0, 20.0, 27.0, 40.0):
        for z in (None, -1.0, 0.0, 0.5, 1.5, 2.5):
            plano = _clasificar_regimen(nivel, z, invertida=False)
            agravado = _clasificar_regimen(nivel, z, invertida=True)
            assert agravado["escalon"] >= plano["escalon"], (
                f"la curva invertida MEJORÓ el régimen con nivel={nivel}, z={z}")


def test_sin_nivel_el_regimen_no_es_aplicable_y_la_puerta_queda_abierta():
    r = _clasificar_regimen(None, None)
    assert r["clasificacion"] == "NO_APLICABLE"
    assert r["puerta_abierta"] is True, (
        "cerrar la puerta por falta de dato convertiría una laguna de cobertura "
        "en una restricción de cartera")


# --------------------------------------------------------------------------- #
# 3. LA BARRERA: el veto solo baja
# --------------------------------------------------------------------------- #
def test_el_veto_de_regimen_solo_baja_el_rating():
    """
    Producto cartesiano completo, igual que `test_los_vetos_solo_bajan_el_rating`.
    Ninguna combinación de régimen puede MEJORAR un dictamen.
    """
    regimenes = (None, "NO_APLICABLE", "CALMA", "NORMAL", "TENSION", "PANICO")
    for bruto in ESCALERA:
        for estilo in ("MIXTA", "CALIDAD_COMPUESTA", "ESPECULATIVA"):
            for banderas in ([], ["a"], ["a", "b"]):
                for sobre in (True, False):
                    for conf in (0.5, 0.8, 1.0):
                        base = aplicar_vetos.func(
                            rating_bruto=bruto, estilo=estilo,
                            banderas_rojas=banderas, sobreextendido=sobre,
                            confianza_datos=conf, regimen_clasificacion=None)
                        for reg in regimenes:
                            r = aplicar_vetos.func(
                                rating_bruto=bruto, estilo=estilo,
                                banderas_rojas=banderas, sobreextendido=sobre,
                                confianza_datos=conf, regimen_clasificacion=reg)
                            assert ESCALERA.index(r["rating"]) <= ESCALERA.index(base["rating"]), (
                                f"el régimen {reg} SUBIÓ el rating de {bruto}")


def test_panico_topa_en_mantener_y_tension_en_compra():
    p = aplicar_vetos.func(rating_bruto="COMPRA FUERTE", estilo="MIXTA",
                           banderas_rojas=[], sobreextendido=False,
                           confianza_datos=1.0, regimen_clasificacion="PANICO")
    assert p["rating"] == "MANTENER"
    assert any("PANICO" in v for v in p["vetos"])

    t = aplicar_vetos.func(rating_bruto="COMPRA FUERTE", estilo="MIXTA",
                           banderas_rojas=[], sobreextendido=False,
                           confianza_datos=1.0, regimen_clasificacion="TENSION")
    assert t["rating"] == "COMPRA"


def test_calma_y_no_aplicable_no_cambian_nada():
    base = aplicar_vetos.func(rating_bruto="COMPRA", estilo="MIXTA",
                              banderas_rojas=[], sobreextendido=False,
                              confianza_datos=1.0)
    for reg in ("CALMA", "NORMAL", "NO_APLICABLE", None):
        r = aplicar_vetos.func(rating_bruto="COMPRA", estilo="MIXTA",
                               banderas_rojas=[], sobreextendido=False,
                               confianza_datos=1.0, regimen_clasificacion=reg)
        assert r["rating"] == base["rating"]
        assert r["vetos"] == base["vetos"]


# --------------------------------------------------------------------------- #
# 4. La puerta solo cierra
# --------------------------------------------------------------------------- #
def test_la_puerta_cerrada_prohibe_perseguir_pero_nunca_lo_habilita():
    def entrada(sobre):
        return _ajustar_entrada(precio=PRECIO, atr=ATR, sesgo_macro=0.6,
                                sesgo_opciones=0.7, momentum_score=70.0,
                                soporte_oi=None, max_pain=None, gamma_flip=None,
                                max_pain_operable=False, regimen_gamma=None,
                                sobreextendido=sobre, soporte_estructural=96.0)
    abierta = entrada(False)
    cerrada = entrada(True)
    assert abierta["entrada_clasificacion"] == "PERSEGUIR"
    assert cerrada["entrada_clasificacion"] != "PERSEGUIR"
    assert (cerrada["ajuste_entrada_pct"] or 0.0) <= (abierta["ajuste_entrada_pct"] or 0.0)


# --------------------------------------------------------------------------- #
# 5. El agente
# --------------------------------------------------------------------------- #
def _dosier(valores_corto, valores_largo=None):
    largo = valores_largo if valores_largo is not None else [v + 2 for v in valores_corto]
    return {
        "disponible": True, "as_of": "2024-06-28",
        "series": {
            "VIXCLS": {"serie": "VIXCLS", "observaciones": _obs(valores_corto)},
            "VXVCLS": {"serie": "VXVCLS", "observaciones": _obs(largo)},
        },
        "fallos": [], "serie_volatilidad": "VIXCLS", "serie_volatilidad_3m": "VXVCLS",
    }


def _estado(dosier=None):
    est = {"ticker": "TEST", "sector": "Technology",
           "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR,
                                           "volatilidad_anual": 0.28}}}
    if dosier is not None:
        est["regimen_data"] = dosier
    return est


def test_el_agente_publica_regimen_nivel_y_puerta():
    valores = [12.0 + (i % 3) for i in range(REGIMEN_VENTANA_ZSCORE)] + [38.0]
    inf = RegimeAnalystAgent().analyze(_estado(_dosier(valores)))
    assert inf["status"] == "SUCCESS"
    assert inf["regimen_clasificacion"] == "PANICO"
    assert inf["puerta_regimen"] is False
    assert inf["nivel_volatilidad"] == 38.0
    assert inf["volatilidad_relativa"] is not None
    assert isinstance(inf["summary"], str) and inf["summary"]


def test_el_agente_degrada_sin_dosier():
    inf = RegimeAnalystAgent().analyze(_estado())
    assert inf["status"] == "NO_APLICABLE"
    assert inf["regimen_clasificacion"] == "NO_APLICABLE"
    assert inf["puerta_regimen"] is True
    assert inf["nivel_volatilidad"] is None
    assert isinstance(inf["summary"], str) and inf["summary"]


def test_sin_regimen_el_rating_no_cambia():
    """
    LA RAMA DE DEGRADACIÓN. Con `regimen_report` ausente el Fund Manager produce
    exactamente el mismo dictamen que antes de que este agente existiera.
    """
    base = {
        "ticker": "TEST", "sector": "Technology",
        "passed_fundamental_gatekeeper": True,
        "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR,
                                        "volatilidad_anual": 0.28}},
        "fundamental_report": {"passed_gatekeeper": True, "status": "APROBADO",
                               "summary": "ok", "metrics": {}},
        "quality_report": {"style_classification": "CALIDAD_COMPUESTA",
                           "conviccion_fundamental": {"valor": 75.0},
                           "banderas_rojas": []},
        "technical_report": {"momentum_score": 45.0, "momentum_classification": "ALCISTA",
                             "sobreextendido": False, "volatilidad_anual": 0.28},
        "reconciliation_data": {"confidence_score": 1.0},
    }
    sin_clave = FundManagerAgent().analyze(copy.deepcopy(base))

    con_vacio = copy.deepcopy(base)
    con_vacio["regimen_report"] = {"regimen_clasificacion": "NO_APLICABLE",
                                   "puerta_regimen": True}
    resultado = FundManagerAgent().analyze(con_vacio)

    for clave in ("rating", "position_size_pct", "peso_objetivo",
                  "stop_loss_atr", "take_profit_atr"):
        assert sin_clave[clave] == resultado[clave], f"`{clave}` cambió sin régimen"


def test_el_agente_es_reproducible():
    valores = [15.0 + (i % 4) for i in range(REGIMEN_VENTANA_ZSCORE + 5)]
    a = RegimeAnalystAgent().analyze(_estado(_dosier(valores)))
    b = RegimeAnalystAgent().analyze(_estado(_dosier(valores)))
    assert a["_traza"] == b["_traza"]
    assert a["signals"] == b["signals"]


def test_el_agente_no_alcanza_la_red():
    import src.agents.regimen as mod
    fuente = open(mod.__file__, encoding="utf-8").read()
    for prohibido in ("import requests", "import urllib", "from src.tools.extraccion",
                      "src.data.fred.serie"):
        assert prohibido not in fuente, f"el agente importa {prohibido}"
