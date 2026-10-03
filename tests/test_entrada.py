"""
Tests del precio de entrada: la combinación de tres vías y su integración.

Qué protegen
------------
1. **EL AJUSTE SOLO PUEDE BAJAR EL PRECIO DE ENTRADA.** Es el análogo exacto de
   «los vetos solo bajan», y se comprueba igual: sobre el producto cartesiano de
   sesgos, niveles y banderas. Si alguna combinación subiera la entrada, el
   sistema podría pagar por encima del mercado por euforia de las tres señales.
2. Que el ajuste esté acotado a un ATR, para que la entrada objetivo nunca quede
   por debajo del propio stop.
3. Que `None` y `0.0` NO se confundan: `0.0` es «entrar a mercado por
   confluencia», `None` es «no calculable». Colapsarlos sería reintroducir el
   defecto que `src/data/magnitudes.py` existe para corregir, con el agravante
   de que aquí el cero es plausible y por tanto invisible.
4. Que el agente sea capa de DECISIÓN de verdad: el precio de entrada tiene que
   mover stop, objetivo y perfil de riesgo en el Fund Manager.
5. Que sin datos de posicionamiento el sistema se comporte EXACTAMENTE como
   antes de que este agente existiera. Es la propiedad que hace que el backtest
   —donde nunca hay cadena de opciones— siga siendo interpretable.

Offline y deterministas.
"""

import copy

import pytest

from src.agents.fund_manager import FundManagerAgent
from src.agents.posicionamiento import PositioningAnalystAgent
from src.config import AJUSTE_MAXIMO_ATR
from src.tools.decision import ESCALERA, _ajustar_entrada, aplicar_vetos

PRECIO = 100.0
ATR = 2.0


@pytest.fixture(autouse=True)
def _motor_determinista(monkeypatch):
    """
    Fuerza el motor heuristico en todo el modulo.

    Sin esto, cada test que instancia un agente abre una llamada real al
    proveedor de LLM: la suite pasa de 4 segundos a mas de seis minutos, deja de
    ser determinista y cuesta dinero. Es el mismo parche que aplica
    `disable_llm()` en el backtest, y por el mismo motivo: `get_llm` se resuelve
    en el modulo de la SUBCLASE, no en `src.config`.
    """
    import src.agents.fund_manager as fm
    import src.agents.posicionamiento as pos
    for modulo in (fm, pos):
        monkeypatch.setattr(modulo, "get_llm", lambda: None)


def entrada(**kwargs):
    base = dict(precio=PRECIO, atr=ATR, sesgo_macro=None, sesgo_opciones=None,
                momentum_score=None, soporte_oi=None, max_pain=None,
                gamma_flip=None, max_pain_operable=False, regimen_gamma=None,
                sobreextendido=False)
    base.update(kwargs)
    return _ajustar_entrada(**base)


# --------------------------------------------------------------------------- #
# 1. LA BARRERA: el ajuste solo baja
# --------------------------------------------------------------------------- #
def test_el_ajuste_de_entrada_solo_baja_el_precio():
    """
    ESTA ES LA BARRERA. Ninguna combinación de señales puede subir el precio de
    entrada. Aunque las tres coincidan en euforia alcista, el sistema entra a
    mercado y no paga por encima: el sesgo del proyecto es hacia no operar
    cuando hay dudas, y pagar de más lo invertiría.
    """
    for macro in (None, -0.9, -0.2, 0.0, 0.2, 0.9):
        for opciones in (None, -0.9, -0.2, 0.0, 0.2, 0.9):
            for momentum in (None, -80.0, -10.0, 0.0, 10.0, 80.0):
                for soporte in (None, 80.0, 97.0, 99.9, 105.0, 130.0):
                    for gamma in (None, 92.0, 101.0):
                        for sobre in (True, False):
                            r = entrada(sesgo_macro=macro, sesgo_opciones=opciones,
                                        momentum_score=momentum, soporte_oi=soporte,
                                        gamma_flip=gamma, sobreextendido=sobre)
                            aj = r["ajuste_entrada_pct"]
                            assert aj is None or aj <= 0.0, (
                                f"el ajuste SUBIÓ la entrada con macro={macro}, "
                                f"opciones={opciones}, momentum={momentum}, "
                                f"soporte={soporte}, gamma={gamma}")
                            objetivo = r["precio_entrada_objetivo"]
                            assert objetivo is None or objetivo <= PRECIO


def test_un_nivel_por_encima_del_precio_no_es_candidato():
    """
    Exigir que el nivel esté por DEBAJO del precio es lo que hace
    estructuralmente imposible subir la entrada. Una resistencia por encima no
    puede convertirse en objetivo de compra.
    """
    r = entrada(sesgo_macro=0.6, sesgo_opciones=0.6, momentum_score=60.0,
                soporte_oi=120.0, gamma_flip=115.0)
    assert r["nivel_referencia"] is None
    assert r["ajuste_entrada_pct"] is None


def test_se_elige_el_nivel_mas_alto_por_debajo_del_precio():
    """
    El retroceso más cercano es el más probable de que se rellene. Tomar el más
    bajo sería esperar un desplome, no un retroceso.
    """
    r = entrada(sesgo_macro=-0.5, sesgo_opciones=0.6, momentum_score=60.0,
                soporte_oi=90.0, gamma_flip=98.0)
    assert r["nivel_origen"] == "GAMMA_FLIP"
    assert r["nivel_referencia"] == 98.0


def test_el_max_pain_lejano_no_entra_como_nivel():
    r = entrada(sesgo_macro=-0.5, sesgo_opciones=0.6, momentum_score=60.0,
                max_pain=99.0, max_pain_operable=False)
    assert r["nivel_referencia"] is None
    r_ok = entrada(sesgo_macro=-0.5, sesgo_opciones=0.6, momentum_score=60.0,
                   max_pain=99.0, max_pain_operable=True)
    assert r_ok["nivel_origen"] == "MAX_PAIN"


# --------------------------------------------------------------------------- #
# 2. El tope en ATR
# --------------------------------------------------------------------------- #
def test_el_ajuste_esta_acotado_a_un_atr():
    """
    Un ajuste más profundo que el stop dejaría la entrada objetivo POR DEBAJO
    del propio stop, que es incoherente. El tope está en unidades de
    volatilidad, no en un porcentaje fijo, para que sea neutral al estilo.
    """
    r = entrada(sesgo_macro=-0.9, sesgo_opciones=0.9, momentum_score=90.0,
                soporte_oi=50.0)  # nivel absurdamente lejano
    tope = AJUSTE_MAXIMO_ATR * ATR / PRECIO
    assert r["ajuste_entrada_pct"] == pytest.approx(-tope)
    assert r["limitado_por_atr"] is True


def test_sin_atr_el_ajuste_sigue_sin_subir_el_precio():
    r = entrada(atr=0.0, sesgo_macro=-0.5, sesgo_opciones=0.6, momentum_score=60.0,
                soporte_oi=95.0)
    assert r["ajuste_entrada_pct"] <= 0.0


# --------------------------------------------------------------------------- #
# 3. Confluencia y divergencia
# --------------------------------------------------------------------------- #
def test_confluencia_total_entra_a_mercado():
    """Las tres confirman y nada está estirado: se entra a mercado, ajuste 0.0."""
    r = entrada(sesgo_macro=0.5, sesgo_opciones=0.4, momentum_score=60.0,
                soporte_oi=97.0)
    assert r["entrada_clasificacion"] == "PERSEGUIR"
    assert r["confluencia"] == 1.0
    assert r["ajuste_entrada_pct"] == 0.0
    assert r["precio_entrada_objetivo"] == PRECIO


def test_divergencia_con_el_momentum_exige_retroceso():
    """
    Momentum alcista contra macro en contra: el sistema no renuncia a la compra,
    exige un mejor precio para una tesis en la que solo el precio propio
    confirma.
    """
    r = entrada(sesgo_macro=-0.3, sesgo_opciones=0.05, momentum_score=60.0,
                soporte_oi=99.0)
    assert r["entrada_clasificacion"] == "ESPERAR_RETROCESO"
    assert r["confluencia"] < 0.5
    assert r["precio_entrada_objetivo"] == 99.0

    # Con el nivel más lejos que un ATR, el tope manda y la entrada no baja del
    # límite: sigue siendo ESPERAR_RETROCESO, pero recortado.
    lejos = entrada(sesgo_macro=-0.3, sesgo_opciones=0.05, momentum_score=60.0,
                    soporte_oi=97.0)
    assert lejos["entrada_clasificacion"] == "ESPERAR_RETROCESO"
    assert lejos["precio_entrada_objetivo"] == 98.0
    assert lejos["limitado_por_atr"] is True


def test_acuerdo_parcial_escalona():
    r = entrada(sesgo_macro=0.4, sesgo_opciones=0.02, momentum_score=50.0,
                soporte_oi=96.0)
    assert r["entrada_clasificacion"] == "ESCALONAR"
    assert r["factor"] == 0.5
    assert r["precio_entrada_objetivo"] == 98.0


def test_sobreextension_prohibe_perseguir():
    """
    Ninguna bandera cambia el signo; todas prohíben perseguir. Es el mismo
    principio que gobierna `aplicar_vetos`.
    """
    limpio = entrada(sesgo_macro=0.5, sesgo_opciones=0.4, momentum_score=60.0,
                     soporte_oi=97.0)
    estirado = entrada(sesgo_macro=0.5, sesgo_opciones=0.4, momentum_score=60.0,
                       soporte_oi=97.0, sobreextendido=True)
    assert limpio["entrada_clasificacion"] == "PERSEGUIR"
    assert estirado["entrada_clasificacion"] == "ESCALONAR"
    assert estirado["ajuste_entrada_pct"] < limpio["ajuste_entrada_pct"]


def test_el_regimen_acelerado_acorta_la_espera():
    """
    Con los creadores de mercado cortos gamma sus coberturas aceleran el
    movimiento: el retroceso puede no llegar nunca y esperarlo entero sale caro.
    No cambia el signo, solo cuánto se espera.
    """
    amortiguado = entrada(sesgo_macro=-0.3, sesgo_opciones=0.05, momentum_score=60.0,
                          soporte_oi=97.0, regimen_gamma="AMORTIGUADO")
    acelerado = entrada(sesgo_macro=-0.3, sesgo_opciones=0.05, momentum_score=60.0,
                        soporte_oi=97.0, regimen_gamma="ACELERADO")
    assert amortiguado["entrada_clasificacion"] == "ESPERAR_RETROCESO"
    assert acelerado["entrada_clasificacion"] == "ESCALONAR"
    assert acelerado["ajuste_entrada_pct"] > amortiguado["ajuste_entrada_pct"]


# --------------------------------------------------------------------------- #
# 4. Ausencia declarada: None nunca es 0.0
# --------------------------------------------------------------------------- #
def test_ausencia_total_devuelve_none_no_cero():
    """
    `0.0` significa «entrar a mercado por confluencia». `None` significa «no
    calculable». Colapsarlos aquí sería especialmente grave porque el cero es
    plausible y por tanto invisible en el informe.
    """
    r = entrada(momentum_score=60.0)
    assert r["ajuste_entrada_pct"] is None
    assert r["precio_entrada_objetivo"] is None
    assert r["entrada_clasificacion"] == "NO_APLICABLE"


def test_un_solo_componente_no_es_confluencia():
    """Una señal aislada no es una comparación de tres vías."""
    r = entrada(momentum_score=90.0, soporte_oi=97.0)
    assert r["entrada_clasificacion"] == "NO_APLICABLE"
    assert r["componentes_disponibles"] == ["tecnico"]
    assert "dos componentes" in r["motivo"]


def test_sin_sesgo_alcista_no_hay_entrada_que_optimizar():
    r = entrada(sesgo_macro=-0.5, sesgo_opciones=-0.4, momentum_score=-60.0,
                soporte_oi=97.0)
    assert r["entrada_clasificacion"] == "NO_APLICABLE"
    assert r["ajuste_entrada_pct"] is None


def test_sin_nivel_no_hay_ajuste_aunque_haya_confluencia():
    """
    El nivel sale EXCLUSIVAMENTE de la cadena de opciones. Sin cadena no hay
    nivel, y el bloque macro por sí solo no puede producir un precio. Es la
    situación de todo el backtest y tiene que degradar limpiamente.
    """
    r = entrada(sesgo_macro=0.5, sesgo_opciones=0.4, momentum_score=60.0)
    assert r["ajuste_entrada_pct"] is None
    assert "cadena de opciones" in r["motivo"]


# --------------------------------------------------------------------------- #
# 5. El veto macro solo baja
# --------------------------------------------------------------------------- #
def test_el_veto_macro_solo_baja_el_rating():
    """Producto cartesiano, igual que `test_los_vetos_solo_bajan_el_rating`."""
    for bruto in ESCALERA:
        for macro in (None, "VIENTO_A_FAVOR_FUERTE", "VIENTO_A_FAVOR", "NEUTRO",
                      "VIENTO_EN_CONTRA", "VIENTO_EN_CONTRA_FUERTE", "NO_APLICABLE"):
            r = aplicar_vetos.invoke({
                "rating_bruto": bruto, "estilo": "GARP", "banderas_rojas": [],
                "sobreextendido": False, "confianza_datos": 0.9,
                "sesgo_macro_clasificacion": macro})
            assert ESCALERA.index(r["rating"]) <= ESCALERA.index(bruto), (
                f"el sesgo macro {macro} SUBIÓ {bruto} a {r['rating']}")


def test_aplicar_vetos_sin_sesgo_macro_se_comporta_igual():
    """
    Compatibilidad: el parámetro nuevo va al final y con defecto `None`, así que
    los llamantes antiguos obtienen exactamente el resultado anterior.
    """
    args = {"rating_bruto": "COMPRA FUERTE", "estilo": "GARP", "banderas_rojas": [],
            "sobreextendido": False, "confianza_datos": 0.9}
    sin = aplicar_vetos.invoke(args)
    con_none = aplicar_vetos.invoke({**args, "sesgo_macro_clasificacion": None})
    assert sin == con_none
    assert sin["rating"] == "COMPRA FUERTE"


def test_el_viento_en_contra_fuerte_topa_en_compra():
    r = aplicar_vetos.invoke({
        "rating_bruto": "COMPRA FUERTE", "estilo": "GARP", "banderas_rojas": [],
        "sobreextendido": False, "confianza_datos": 0.9,
        "sesgo_macro_clasificacion": "VIENTO_EN_CONTRA_FUERTE"})
    assert r["rating"] == "COMPRA"
    assert any("futuros" in v for v in r["vetos"])


# --------------------------------------------------------------------------- #
# 6. Es capa de DECISIÓN: mueve los niveles del Fund Manager
# --------------------------------------------------------------------------- #
def estado_base():
    return {
        "ticker": "TEST", "passed_fundamental_gatekeeper": True,
        "fundamental_report": {"metrics": {"net_margin": 0.15}, "summary": "ok"},
        "quality_report": {"style_classification": "GARP",
                           "conviccion_fundamental": {"valor": 70.0},
                           "banderas_rojas": []},
        "technical_report": {"momentum_classification": "ALCISTA",
                             "momentum_score": 30.0, "sobreextendido": False,
                             "volatilidad_anual": 0.60},
        "debate_report": {"synthesis": "s"},
        "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR}},
    }


def test_el_precio_de_entrada_mueve_stop_objetivo_y_riesgo():
    """
    Si esto deja de cumplirse, el agente ha dejado de ser capa de decisión y el
    backtest vuelve a medir la misma lógica que produce en vivo — que es
    justamente lo que hoy NO ocurre y está declarado como limitación.
    """
    sin = FundManagerAgent().analyze(estado_base())
    con = estado_base()
    con["positioning_report"] = {
        "precio_entrada_objetivo": 98.0, "ajuste_entrada_pct": -0.02,
        "entrada_clasificacion": "ESPERAR_RETROCESO", "nivel_origen": "SOPORTE_OI",
        "sesgo_macro_clasificacion": "VIENTO_A_FAVOR"}
    ajustado = FundManagerAgent().analyze(con)

    assert ajustado["precio_entrada"] == 98.0
    assert ajustado["current_price"] == PRECIO, "el precio de mercado se conserva"
    assert ajustado["stop_loss_atr"] < sin["stop_loss_atr"]
    assert ajustado["take_profit_atr"] < sin["take_profit_atr"]
    assert (ajustado["perfil_riesgo"]["riesgo_pct"]
            > sin["perfil_riesgo"]["riesgo_pct"]), (
        "una entrada más baja con el mismo ATR arriesga una fracción mayor")


def test_sin_posicionamiento_el_fund_manager_usa_el_precio_de_mercado():
    """
    La rama de degradación, que es la que corre en TODO el backtest: sin informe
    de posicionamiento el comportamiento es exactamente el anterior a que este
    agente existiera.
    """
    sin = FundManagerAgent().analyze(estado_base())
    vacio = estado_base()
    vacio["positioning_report"] = {
        "ajuste_entrada_pct": None, "precio_entrada_objetivo": None,
        "entrada_clasificacion": "NO_APLICABLE", "sesgo_macro_clasificacion": "NO_APLICABLE"}
    con_vacio = FundManagerAgent().analyze(vacio)
    for clave in ("rating", "position_size_pct", "stop_loss_atr", "take_profit_atr",
                  "peso_objetivo"):
        assert sin[clave] == con_vacio[clave], f"`{clave}` cambió sin datos de entrada"


def test_un_precio_de_entrada_cero_no_se_confunde_con_ausencia():
    """
    `pos.get(...) or current_price` habría funcionado por accidente con 0.0 y
    habría enmascarado un dato corrupto. La comprobación es `is None`.
    """
    corrupto = estado_base()
    corrupto["positioning_report"] = {"precio_entrada_objetivo": 0.0,
                                      "ajuste_entrada_pct": -1.0}
    r = FundManagerAgent().analyze(corrupto)
    assert r["stop_loss_atr"] is None, (
        "un precio de entrada de 0.0 no debe sustituirse en silencio por el de mercado")


# --------------------------------------------------------------------------- #
# 7. El agente
# --------------------------------------------------------------------------- #
def test_el_agente_degrada_sin_datos_de_posicionamiento():
    est = {"ticker": "TEST", "sector": "Technology",
           "technical_report": {"close": PRECIO, "atr": ATR, "momentum_score": 55.0,
                                "sobreextendido": False},
           "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR}}}
    inf = PositioningAnalystAgent().analyze(est)
    assert inf["status"] == "DATOS_INSUFICIENTES"
    assert inf["sesgo_macro"] is None
    assert inf["sesgo_opciones"] is None
    assert inf["ajuste_entrada_pct"] is None
    assert inf["entrada_clasificacion"] == "NO_APLICABLE"
    assert isinstance(inf["summary"], str) and inf["summary"]


def test_el_agente_es_reproducible():
    """
    Dos ejecuciones del mismo análisis deben producir la misma traza. Con
    identificadores no deterministas, `daily_selection.json` cambiaría entero en
    cada pasada y cualquier diff sería inútil.
    """
    est = {"ticker": "TEST", "sector": "Energy",
           "technical_report": {"close": PRECIO, "atr": ATR, "momentum_score": 40.0,
                                "sobreextendido": False},
           "yfinance_data": {"technical": {"close": PRECIO, "atr": ATR}}}
    a = PositioningAnalystAgent().analyze(copy.deepcopy(est))
    b = PositioningAnalystAgent().analyze(copy.deepcopy(est))
    assert a["_traza"] == b["_traza"]
    assert a["signals"] == b["signals"]


def test_el_agente_no_alcanza_la_red():
    """
    Es puro, como el Analista de Noticias: consume `futures_data` y
    `options_data` ya ingeridos. Si importara una tool de extracción, podría
    hacer una petición en mitad de un backtest offline.
    """
    import src.agents.posicionamiento as mod
    fuente = open(mod.__file__, encoding="utf-8").read()
    # La mencion a `yfinance_data` es legitima: es la clave del estado ya
    # ingerido. Lo que no puede aparecer es la IMPORTACION de un cliente de red
    # ni de las tools de extraccion.
    assert "src.tools.extraccion" not in fuente
    assert "import yfinance" not in fuente
    assert "import requests" not in fuente
    assert "from src.data.futuros" not in fuente
    assert "from src.data.opciones" not in fuente
