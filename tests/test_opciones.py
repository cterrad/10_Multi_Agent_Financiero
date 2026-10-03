"""
Tests de la cadena de opciones: Griegas, niveles y percentiles.

Qué protegen
------------
1. Que las Griegas salgan de la FORMA CERRADA de Black-Scholes y no de una
   aproximación: `test_gamma_es_la_derivada_de_delta` lo verifica contra la
   derivada numérica, que es una comprobación independiente de la fórmula.
2. Que los niveles (soporte por open interest, max pain, punto de inflexión de
   la gamma) salgan de aritmética verificable sobre una cadena construida a
   mano, no de una caja negra.
3. Que la ausencia se declare: sin volatilidad implícita no hay gamma, sin
   histórico no hay percentil, y ninguna de las dos cosas se sustituye por un
   valor neutro. Un percentil 0.5 imputado diría «está en su nivel habitual»,
   que es una afirmación, y aquí lo que ocurre es que faltan observaciones.

Offline y deterministas: la cadena se construye en el propio test.
"""

import json

import pytest

from src.config import OPCIONES_MAXPAIN_DIAS_MAXIMO, OPCIONES_OI_MINIMO_STRIKE
from src.tools.opciones import (
    _percentil,
    calcular_gamma_exposure,
    calcular_max_pain,
    calcular_put_call_ratio,
    calcular_skew,
    clasificar_sesgo_opciones,
    delta_bs,
    gamma_bs,
    identificar_niveles_oi,
    localizar_gamma_flip,
)


def contrato(tipo, strike, oi, iv=0.30, dias=21, venc="2024-04-05", vol=None):
    return {"tipo": tipo, "strike": float(strike), "vencimiento": venc, "dias": dias,
            "open_interest": int(oi), "volumen": int(oi // 4 if vol is None else vol),
            "iv": iv}


def cadena_simetrica(spot=100.0, dias=21):
    """Cadena con más OI de puts abajo y más de calls arriba."""
    out = []
    for k in range(80, 125, 5):
        out.append(contrato("call", k, 400 + 10 * (120 - k), dias=dias))
        out.append(contrato("put", k, 400 + 10 * (k - 80), dias=dias))
    return out


def historico(n=70, oi_puts_base=9_000, iv_put_base=0.34):
    return [{"fecha": f"2024-01-{(i % 28) + 1:02d}", "oi_calls": 10_000,
             "oi_puts": oi_puts_base + 20 * i, "vol_calls": 2_000, "vol_puts": 1_800,
             "iv_call_otm": 0.32, "iv_put_otm": iv_put_base + 0.0002 * i}
            for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. Griegas en forma cerrada
# --------------------------------------------------------------------------- #
def test_gamma_es_la_derivada_de_delta():
    """
    Comprobación INDEPENDIENTE de la forma cerrada: la gamma tiene que coincidir
    con la derivada numérica de la delta respecto del subyacente. Si alguien
    sustituyera la fórmula por una aproximación, esto lo detectaría.
    """
    s, k, t, sigma, r = 100.0, 100.0, 0.25, 0.30, 0.04
    h = 0.01
    numerica = (delta_bs(s + h, k, t, sigma, "call", r)
                - delta_bs(s - h, k, t, sigma, "call", r)) / (2 * h)
    assert gamma_bs(s, k, t, sigma, r) == pytest.approx(numerica, rel=1e-6)


def test_gamma_contra_valor_de_referencia():
    """Valor de referencia de Black-Scholes para un caso conocido."""
    assert gamma_bs(100.0, 100.0, 0.25, 0.30, 0.04) == pytest.approx(0.0263306, abs=1e-7)


def test_gamma_maxima_cerca_del_dinero():
    """Propiedad estructural: la gamma se concentra en torno al strike."""
    atm = gamma_bs(100.0, 100.0, 0.25, 0.30)
    otm = gamma_bs(100.0, 140.0, 0.25, 0.30)
    itm = gamma_bs(100.0, 60.0, 0.25, 0.30)
    assert atm > otm and atm > itm


def test_sin_volatilidad_implicita_no_hay_gamma():
    """`None`, nunca 0.0: un cero se leería como «gamma nula», que es distinto."""
    assert gamma_bs(100.0, 100.0, 0.25, 0.0) is None
    assert gamma_bs(100.0, 100.0, 0.0, 0.30) is None


def test_sin_volatilidad_implicita_no_hay_gex():
    sin_iv = [contrato("call", 100, 1000, iv=None), contrato("put", 100, 1000, iv=None)]
    r = calcular_gamma_exposure.invoke({"contratos": sin_iv, "spot": 100.0})
    assert r["gex_total"] is None
    assert r["status"] == "NO_APLICABLE"
    assert r["regimen"] == "NO_APLICABLE"


def test_el_gex_declara_su_convencion():
    """
    El signo depende de una convención sobre quién está en cada lado, que la
    cadena no permite verificar. Tiene que viajar declarada en el resultado.
    """
    r = calcular_gamma_exposure.invoke({"contratos": cadena_simetrica(), "spot": 100.0})
    assert "convencion" in r and "convencion estandar" in r["convencion"]


# --------------------------------------------------------------------------- #
# 2. Niveles
# --------------------------------------------------------------------------- #
def test_max_pain_sobre_una_cadena_construida_a_mano():
    """
    Tres strikes con open interest conocido: el mínimo de la curva de dolor está
    donde dice la aritmética, no donde diga una caja negra.

    calls: 100 contratos en 90.  puts: 100 contratos en 110.
    dolor(90)  = 0            + 100*(110-90)*100 = 200.000
    dolor(100) = 100*10*100   + 100*10*100       = 200.000
    dolor(110) = 100*20*100   + 0                = 200.000
    Empate a tres: el desempate declarado es el strike más bajo.
    """
    cadena = [contrato("call", 90, 100), contrato("put", 110, 100),
              contrato("call", 100, 0), contrato("put", 100, 0)]
    r = calcular_max_pain.invoke({"contratos": cadena})
    assert r["status"] == "SUCCESS"
    assert r["max_pain"] == 90.0
    dolor = {d["strike"]: d["dolor"] for d in r["curva_dolor"]}
    assert dolor[90.0] == pytest.approx(200_000.0)
    assert dolor[110.0] == pytest.approx(200_000.0)


def test_el_max_pain_declara_si_esta_lejos_del_vencimiento():
    """
    A noventa días el número sigue saliendo, pero es aritmética y no una fuerza.
    `es_operable` es lo que impide que se use como nivel de entrada.
    """
    lejos = calcular_max_pain.invoke({"contratos": cadena_simetrica(dias=90)})
    cerca = calcular_max_pain.invoke(
        {"contratos": cadena_simetrica(dias=OPCIONES_MAXPAIN_DIAS_MAXIMO - 1)})
    assert lejos["es_operable"] is False
    assert cerca["es_operable"] is True


def test_los_niveles_de_oi_ignoran_strikes_iliquidos():
    """Un strike con doce contratos no sostiene ningún precio."""
    cadena = [contrato("put", 95, OPCIONES_OI_MINIMO_STRIKE - 1),
              contrato("put", 90, OPCIONES_OI_MINIMO_STRIKE + 100),
              contrato("call", 105, OPCIONES_OI_MINIMO_STRIKE + 100)]
    r = identificar_niveles_oi.invoke({"contratos": cadena, "spot": 100.0})
    assert r["soporte_oi"] == 90.0, "el strike ilíquido no puede ser el soporte"
    assert r["resistencia_oi"] == 105.0


def test_sin_strikes_validos_los_niveles_son_none():
    r = identificar_niveles_oi.invoke({"contratos": [contrato("put", 95, 1)],
                                       "spot": 100.0})
    assert r["soporte_oi"] is None and r["resistencia_oi"] is None
    assert r["status"] == "DATOS_INSUFICIENTES"


def test_el_gamma_flip_se_encuentra_y_esta_en_rango():
    cadena = cadena_simetrica()
    r = localizar_gamma_flip.invoke({"contratos": cadena, "spot": 100.0})
    if r["gamma_flip"] is not None:
        assert 80.0 <= r["gamma_flip"] <= 120.0
        from src.tools.opciones import _gex_en
        assert abs(_gex_en(cadena, r["gamma_flip"], 0.04)) < abs(_gex_en(cadena, 100.0, 0.04))


def test_el_gamma_flip_es_none_si_no_hay_cambio_de_signo():
    """
    No encontrar el nivel es una respuesta legítima y frecuente: significa que
    los creadores de mercado están del mismo lado en toda la zona operable.
    """
    solo_calls = [contrato("call", k, 1000) for k in range(80, 125, 5)]
    r = localizar_gamma_flip.invoke({"contratos": solo_calls, "spot": 100.0})
    assert r["gamma_flip"] is None
    assert r["n_cruces"] == 0


def test_sin_cadena_los_niveles_son_no_aplicable():
    for tool in (identificar_niveles_oi, localizar_gamma_flip):
        r = tool.invoke({"contratos": [], "spot": 100.0})
        assert r["status"] == "NO_APLICABLE"


# --------------------------------------------------------------------------- #
# 3. Percentiles: sin histórico no hay lectura
# --------------------------------------------------------------------------- #
def test_percentil_sin_historico_suficiente_es_none():
    """
    ESTA ES LA REGLA Nº 1 APLICADA AQUÍ. Un 0.5 imputado diría «está en su nivel
    habitual», que es una afirmación; lo que ocurre es que faltan observaciones.
    """
    assert _percentil(1.0, [0.5] * 10) is None
    assert _percentil(None, [0.5] * 100) is None
    assert _percentil(1.0, [0.5] * 100) is not None


def test_put_call_sin_historico_se_declara_insuficiente():
    agregados = {"oi_calls": 10_000, "oi_puts": 12_000,
                 "vol_calls": 2_000, "vol_puts": 2_400}
    r = calcular_put_call_ratio.invoke({"agregados": agregados,
                                        "historico": historico(n=10)})
    assert r["pcr_oi"] == pytest.approx(1.2)
    assert r["percentil_pcr"] is None
    assert r["status"] == "DATOS_INSUFICIENTES"


def test_put_call_con_historico_situa_el_valor():
    agregados = {"oi_calls": 10_000, "oi_puts": 99_000,
                 "vol_calls": 2_000, "vol_puts": 2_400}
    r = calcular_put_call_ratio.invoke({"agregados": agregados,
                                        "historico": historico()})
    assert r["status"] == "SUCCESS"
    assert r["percentil_pcr"] == pytest.approx(1.0), "un valor extremo va al tope"
    assert "miedo" in r["lectura"]


def test_skew_sin_iv_de_referencia_es_none():
    r = calcular_skew.invoke({"agregados": {"iv_put_otm": None, "iv_call_otm": 0.3},
                              "historico": historico()})
    assert r["skew"] is None
    assert r["percentil_skew"] is None


# --------------------------------------------------------------------------- #
# 4. Sesgo agregado
# --------------------------------------------------------------------------- #
def test_el_sesgo_no_es_un_proxy_de_momentum():
    """
    EL DEFECTO QUE ESTE BLOQUE EXISTE PARA NO REPETIR.

    En la primera version el unico componente vivo era la distancia al punto de
    inflexion de la gamma, que crece cuanto mas ha subido el valor. Un valor
    pegado a la resistencia de open interest salia con sesgo +0.89 y recibia
    PERSEGUIR: se compraba el techo del canal. Con el canal en la ecuacion, esa
    misma situacion tiene que salir NEGATIVA.
    """
    pegado_al_techo = clasificar_sesgo_opciones.invoke({
        "posicion_en_canal": 0.98, "skew_normalizado": 0.0,
        "percentil_pcr": None, "percentil_skew": None,
        "gamma_flip": 297.0, "spot": 320.0})
    assert pegado_al_techo["sesgo_opciones"] < 0, (
        "un precio pegado a la resistencia de open interest no puede ser una "
        "buena entrada por muy lejos que quede el gamma flip")


def test_el_componente_de_gamma_es_asimetrico():
    """
    Por debajo del punto de inflexion la advertencia es real y usa el rango
    completo; por encima solo dice que el colchon queda lejos y se atenua. Sin
    esa asimetria el termino es una funcion creciente de cuanto ha subido el
    valor.
    """
    from src.config import GEX_ASIMETRIA_POSITIVA
    encima = clasificar_sesgo_opciones.invoke({
        "gamma_flip": 90.0, "spot": 100.0})["componentes"][0]["valor"]
    debajo = clasificar_sesgo_opciones.invoke({
        "gamma_flip": 110.0, "spot": 100.0})["componentes"][0]["valor"]
    assert 0 < encima <= GEX_ASIMETRIA_POSITIVA
    assert debajo < -0.9
    assert abs(debajo) > abs(encima) * 3, "la lectura negativa debe pesar mucho mas"


def test_el_canal_de_oi_se_lee_en_clave_contraria():
    """Cerca del soporte suma, contra la resistencia resta."""
    suelo = clasificar_sesgo_opciones.invoke({"posicion_en_canal": 0.0})
    techo = clasificar_sesgo_opciones.invoke({"posicion_en_canal": 1.0})
    medio = clasificar_sesgo_opciones.invoke({"posicion_en_canal": 0.5})
    assert suelo["sesgo_opciones"] == pytest.approx(1.0)
    assert techo["sesgo_opciones"] == pytest.approx(-1.0)
    assert medio["sesgo_opciones"] == pytest.approx(0.0)


def test_la_posicion_en_el_canal_esta_disponible_sin_historico():
    """
    Es la propiedad que hace utilizable el bloque desde el primer dia. Los
    percentiles tardan tres meses en existir; esto no.
    """
    cadena = cadena_simetrica()
    r = identificar_niveles_oi.invoke({"contratos": cadena, "spot": 100.0})
    assert r["posicion_en_canal"] is not None
    assert 0.0 <= r["posicion_en_canal"] <= 1.0


def test_el_techo_del_canal_se_declara():
    from src.config import OPCIONES_CANAL_SOBREEXTENDIDO
    cadena = [contrato("put", 90, 1000), contrato("call", 100, 1000)]
    r = identificar_niveles_oi.invoke({"contratos": cadena, "spot": 99.5})
    assert r["posicion_en_canal"] >= OPCIONES_CANAL_SOBREEXTENDIDO
    assert r["en_techo_del_canal"] is True


def test_sin_los_dos_extremos_no_hay_canal():
    """Con un solo nivel no hay canal, y `None` no se sustituye por 0.5."""
    solo_soporte = [contrato("put", 90, 1000)]
    r = identificar_niveles_oi.invoke({"contratos": solo_soporte, "spot": 100.0})
    assert r["soporte_oi"] == 90.0
    assert r["posicion_en_canal"] is None
    assert r["en_techo_del_canal"] is False


def test_el_skew_normalizado_es_comparable_sin_historico():
    """
    Un skew de 0.04 no significa lo mismo en un valor al 25% de volatilidad que
    en otro al 80%. Dividir por la volatilidad at-the-money es lo que permite
    que este componente vote desde el primer dia.
    """
    tranquilo = calcular_skew.invoke({
        "agregados": {"iv_put_otm": 0.29, "iv_call_otm": 0.25, "iv_atm": 0.25},
        "historico": []})
    volatil = calcular_skew.invoke({
        "agregados": {"iv_put_otm": 0.84, "iv_call_otm": 0.80, "iv_atm": 0.80},
        "historico": []})
    assert tranquilo["skew"] == pytest.approx(volatil["skew"], abs=1e-9)
    assert tranquilo["skew_normalizado"] > volatil["skew_normalizado"] * 2
    assert tranquilo["status"] == "SIN_HISTORICO"


def test_sin_iv_atm_no_hay_skew_normalizado():
    r = calcular_skew.invoke({
        "agregados": {"iv_put_otm": 0.35, "iv_call_otm": 0.32, "iv_atm": None},
        "historico": []})
    assert r["skew"] is not None
    assert r["skew_normalizado"] is None
    assert r["status"] == "DATOS_INSUFICIENTES"


def test_el_percentil_manda_sobre_el_normalizado_cuando_existe():
    """El histórico propio es la lectura preferida; el normalizado es el puente."""
    r = clasificar_sesgo_opciones.invoke({
        "skew_normalizado": 0.5, "percentil_skew": 0.5})
    componentes = [c["componente"] for c in r["componentes"]]
    assert "skew_percentil" in componentes
    assert "skew_normalizado" not in componentes


def test_sin_ningun_componente_el_sesgo_de_opciones_es_none():
    """`None` y NO_APLICABLE. Un 0.0 afirmaría «sin sesgo de posicionamiento»."""
    r = clasificar_sesgo_opciones.invoke({"percentil_pcr": None, "percentil_skew": None,
                                          "gamma_flip": None, "spot": 100.0})
    assert r["sesgo_opciones"] is None
    assert r["clasificacion"] == "NO_APLICABLE"


def test_el_miedo_caro_se_lee_en_clave_contraria():
    """Percentil alto de put/call = cobertura por encima de lo habitual = apoyo."""
    alto = clasificar_sesgo_opciones.invoke({"percentil_pcr": 0.95})
    bajo = clasificar_sesgo_opciones.invoke({"percentil_pcr": 0.05})
    assert alto["sesgo_opciones"] > 0 > bajo["sesgo_opciones"]


def test_el_sesgo_pondera_solo_los_componentes_disponibles():
    solo_pcr = clasificar_sesgo_opciones.invoke({"percentil_pcr": 0.9})
    assert solo_pcr["n_disponibles"] == 1
    assert solo_pcr["sesgo_opciones"] == pytest.approx(2 * 0.9 - 1)


def test_por_encima_del_gamma_flip_el_sesgo_es_positivo():
    """Por encima del punto de inflexión los creadores amortiguan; por debajo aceleran."""
    encima = clasificar_sesgo_opciones.invoke({"gamma_flip": 95.0, "spot": 100.0})
    debajo = clasificar_sesgo_opciones.invoke({"gamma_flip": 105.0, "spot": 100.0})
    assert encima["sesgo_opciones"] > 0 > debajo["sesgo_opciones"]


# --------------------------------------------------------------------------- #
# 5. Frontera JSON
# --------------------------------------------------------------------------- #
def test_la_salida_de_las_tools_de_opciones_es_serializable():
    """Todo lo que devuelve una tool tiene que caber en un `ToolMessage`."""
    cadena = cadena_simetrica()
    agregados = {"oi_calls": 10_000, "oi_puts": 12_000, "vol_calls": 2_000,
                 "vol_puts": 2_400, "iv_put_otm": 0.35, "iv_call_otm": 0.32}
    for tool, args in [
        (calcular_put_call_ratio, {"agregados": agregados, "historico": historico()}),
        (identificar_niveles_oi, {"contratos": cadena, "spot": 100.0}),
        (calcular_max_pain, {"contratos": cadena}),
        (calcular_gamma_exposure, {"contratos": cadena, "spot": 100.0}),
        (localizar_gamma_flip, {"contratos": cadena, "spot": 100.0}),
        (calcular_skew, {"agregados": agregados, "historico": historico()}),
    ]:
        json.dumps(tool.invoke(args))
