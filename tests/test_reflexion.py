"""
Suite sin red de la memoria de reflexión.

Fija las cuatro propiedades sin las cuales esta capa sería un lazo de ajuste
sobre el propio histórico en lugar de una calibración:

  1. **Point-in-time por fecha de DESENLACE.** Una señal emitida hace una semana
     con horizonte de 21 sesiones no se sabe todavía cómo terminó, y no puede
     influir en la decisión de hoy. Es el análogo exacto de
     `test_fundamentals_respect_filed_not_end`: si este test se relaja, el
     backtest deja de medir nada.
  2. **El factor solo baja.** 1.0 es a la vez el valor neutro y el máximo, igual
     que los vetos solo bajan y el ajuste de entrada solo recorta el precio.
  3. **Sin muestra no hay ajuste, y se declara.** Nunca una expectativa
     inventada, igual que los percentiles de opciones no se inventan un 50.
  4. **La reasignación conserva el presupuesto.** Lo que se recorta a un
     candidato va a los demás, no a la liquidez: el sistema ya opera al 30% de
     exposición y una capa que solo restara empeoraría su mayor limitación.
"""

import itertools

import pandas as pd
import pytest

from src.config import (
    PESO_MAXIMO_POSICION,
    REFLEXION_FACTOR_MINIMO,
    REFLEXION_MUESTRA_MINIMA,
)
from src.memoria import MemoriaReflexion, resolver_desde_precios
from src.portfolio.construccion import PortfolioConstructor, PosicionPropuesta
from src.tools.decision import aplicar_vetos
from src.tools.reflexion import _consultar


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _calendario(n: int = 300) -> pd.DatetimeIndex:
    return pd.bdate_range("2020-01-01", periods=n)


def _memoria_con(observaciones, resolver=None) -> MemoriaReflexion:
    """observaciones: lista de (fecha_senal, fecha_desenlace, estilo, momentum, retorno)."""
    m = MemoriaReflexion(resolver=resolver)
    for f0, f1, estilo, momentum, ret in observaciones:
        m.anotar(f0, "AAA", estilo, momentum, f1)
        m.observaciones[-1].retorno_exceso = ret
    return m


def _dosier_sintetico(media_estilo: float, n: int = 200) -> dict:
    return {
        "as_of": "2024-01-01", "horizonte_sesiones": 21, "n_total": 1000,
        "media_global": 0.0, "muestra_minima": REFLEXION_MUESTRA_MINIMA,
        "contraccion_k": 40, "evaluable": True, "motivo": None,
        "tabla": {
            "estilo": {"VALOR": {"n": n, "media": media_estilo, "error_tipico": 0.002}},
            "momentum": {},
        },
    }


# --------------------------------------------------------------------------- #
# 1. Disciplina point-in-time
# --------------------------------------------------------------------------- #
def test_la_memoria_respeta_la_fecha_de_desenlace():
    """
    Una observación desenlazada DESPUÉS de `as_of` no puede entrar en el dosier.

    Es la propiedad que hace válido todo el backtest de esta capa. Se comprueba
    con dos observaciones idénticas salvo por su desenlace y un retorno de signo
    opuesto: si la futura se colara, la media cambiaría de signo.
    """
    pasada = (pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03"), "VALOR", "ALCISTA", +0.10)
    futura = (pd.Timestamp("2020-02-04"), pd.Timestamp("2020-03-03"), "VALOR", "ALCISTA", -0.90)
    memoria = _memoria_con([pasada, futura])

    dosier = memoria.dosier(pd.Timestamp("2020-02-10"))

    assert dosier["n_total"] == 1, "solo la observación ya desenlazada debe contar"
    assert dosier["tabla"]["estilo"]["VALOR"]["media"] == pytest.approx(0.10)

    # Y una vez pasada la fecha de desenlace, sí entra.
    posterior = memoria.dosier(pd.Timestamp("2020-03-10"))
    assert posterior["n_total"] == 2
    assert posterior["tabla"]["estilo"]["VALOR"]["media"] < 0


def test_preguntar_hacia_atras_no_contamina_los_agregados():
    """
    Consultar una fecha anterior a la última consolidada reconstruye desde cero.

    Sin esa reconstrucción el cursor incremental dejaría en los agregados
    observaciones posteriores a la fecha preguntada, que es look-ahead con
    apariencia de optimización.
    """
    memoria = _memoria_con([
        (pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03"), "VALOR", "ALCISTA", +0.10),
        (pd.Timestamp("2020-02-04"), pd.Timestamp("2020-03-03"), "VALOR", "ALCISTA", -0.90),
    ])
    memoria.dosier(pd.Timestamp("2020-03-10"))          # avanza el cursor al final
    vuelta = memoria.dosier(pd.Timestamp("2020-02-10"))  # y ahora pregunta hacia atrás

    assert vuelta["n_total"] == 1
    assert vuelta["tabla"]["estilo"]["VALOR"]["media"] == pytest.approx(0.10)


def test_anotar_senales_usa_el_calendario_no_dias_naturales():
    """El desenlace cae en una sesión real, no en un festivo sin precio."""
    cal = _calendario()
    memoria = MemoriaReflexion(horizonte=21)

    class _S:
        ticker, estilo, momentum = "AAA", "VALOR", "ALCISTA"
        date = cal[0]

    assert memoria.anotar_senales([_S()], cal) == 1
    assert memoria.observaciones[0].fecha_desenlace == cal[21]

    # Una señal cuyo horizonte se sale del calendario no se anota: nunca podría
    # desenlazarse y solo ensuciaría el almacén.
    class _Tarde(_S):
        date = cal[-3]

    assert memoria.anotar_senales([_Tarde()], cal) == 0


def test_el_resolver_devuelve_none_y_no_cero_sin_precios():
    """Una observación sin desenlace medible no es una observación de retorno nulo."""
    precios = {"AAA": pd.DataFrame(
        {"Close": [100.0, 110.0]},
        index=pd.to_datetime(["2020-01-06", "2020-02-03"]))}
    resolver = resolver_desde_precios(precios, benchmark="SPY")

    assert resolver("AAA", pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03")) == \
        pytest.approx(0.10)
    assert resolver("ZZZ", pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03")) is None


def test_la_cohorte_se_mide_contra_si_misma():
    """
    A cada señal se le resta la media de las demás del mismo rebalanceo.

    Es la corrección que hizo útil la capa. Midiendo solo contra el índice, la
    memoria recortó 62 de 5.621 señales del histórico real con factor medio
    x0.99 —nada—, porque este universo bate al SPY y casi ninguna celda caía por
    debajo de cero. Contra el índice se mide exposición; contra la cohorte, que
    es lo que hace este test, se mide selección.
    """
    f0, f1 = pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03")
    memoria = MemoriaReflexion()
    for i, (estilo, ret) in enumerate(
            [("VALOR", 0.10), ("VALOR", 0.08), ("CRECIMIENTO", 0.02),
             ("CRECIMIENTO", 0.00), ("MIXTA", 0.05)]):
        memoria.anotar(f0, f"T{i}", estilo, "ALCISTA", f1)
        memoria.observaciones[-1].retorno_exceso = ret

    dosier = memoria.dosier(pd.Timestamp("2020-02-10"))

    # Media de la cohorte = 5.0%. Todas las medias quedan centradas en cero.
    assert dosier["media_global"] == pytest.approx(0.0, abs=1e-9)
    assert dosier["tabla"]["estilo"]["VALOR"]["media"] == pytest.approx(0.04)
    assert dosier["tabla"]["estilo"]["CRECIMIENTO"]["media"] == pytest.approx(-0.04)


def test_una_cohorte_pequena_no_se_centra():
    """Con tres observaciones, su media es ruido y no describe el día."""
    f0, f1 = pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03")
    memoria = MemoriaReflexion()
    for i, ret in enumerate([0.10, 0.08, 0.06]):
        memoria.anotar(f0, f"T{i}", "VALOR", "ALCISTA", f1)
        memoria.observaciones[-1].retorno_exceso = ret

    dosier = memoria.dosier(pd.Timestamp("2020-02-10"))
    assert dosier["media_global"] == pytest.approx(0.08)   # sin centrar


def test_consolidar_dos_veces_no_resta_la_media_dos_veces():
    """
    La resta transversal es idempotente.

    `retorno_relativo` se guarda aparte de `retorno_exceso` justo por esto: si
    se sobrescribiera el dato crudo, cada reconstrucción del índice —que ocurre
    al preguntar hacia atrás en el tiempo— volvería a centrar lo ya centrado y
    la tabla se iría a cero.
    """
    f0, f1 = pd.Timestamp("2020-01-06"), pd.Timestamp("2020-02-03")
    memoria = MemoriaReflexion()
    for i, (estilo, ret) in enumerate(
            [("VALOR", 0.10), ("VALOR", 0.08), ("CRECIMIENTO", 0.02),
             ("CRECIMIENTO", 0.00), ("MIXTA", 0.05)]):
        memoria.anotar(f0, f"T{i}", estilo, "ALCISTA", f1)
        memoria.observaciones[-1].retorno_exceso = ret

    primero = memoria.dosier(pd.Timestamp("2020-02-10"))
    memoria._reindexar()
    segundo = memoria.dosier(pd.Timestamp("2020-02-10"))

    assert segundo["tabla"]["estilo"]["VALOR"]["media"] == \
        pytest.approx(primero["tabla"]["estilo"]["VALOR"]["media"])
    assert segundo["tabla"]["estilo"]["VALOR"]["media"] == pytest.approx(0.04)


def test_el_resolver_descuenta_el_indice():
    """
    El desenlace se mide EN EXCESO sobre el índice.

    Sin restarlo, la memoria aprendería que 2015-2021 fue alcista y le pondría
    expectativa positiva a todo: el factor sería 1.0 siempre y la capa no
    mediría selección, sino mercado.
    """
    idx = pd.to_datetime(["2020-01-06", "2020-02-03"])
    precios = {
        "AAA": pd.DataFrame({"Close": [100.0, 110.0]}, index=idx),   # +10%
        "SPY": pd.DataFrame({"Close": [100.0, 108.0]}, index=idx),   # +8%
    }
    resolver = resolver_desde_precios(precios, benchmark="SPY")
    assert resolver("AAA", idx[0], idx[1]) == pytest.approx(0.02)


# --------------------------------------------------------------------------- #
# 2. El factor solo baja
# --------------------------------------------------------------------------- #
def test_el_factor_de_reflexion_nunca_sube_el_peso():
    """
    Producto cartesiano de expectativas y muestras: el factor jamás supera 1.0.

    Mismo contrato que `test_los_vetos_solo_bajan_el_rating` y que
    `test_el_ajuste_de_entrada_solo_baja_el_precio`. Premiar con tamaño lo que
    ya funcionó es la definición operativa de perseguir el rendimiento pasado.
    """
    medias = [-0.30, -0.05, -0.01, 0.0, 0.01, 0.05, 0.30]
    muestras = [1, REFLEXION_MUESTRA_MINIMA - 1, REFLEXION_MUESTRA_MINIMA, 500]
    momentums = [None, "ALCISTA", "BAJISTA"]

    for media, n, momentum in itertools.product(medias, muestras, momentums):
        res = _consultar(_dosier_sintetico(media, n), "VALOR", momentum)
        assert res["factor"] <= 1.0, (media, n, momentum)
        assert res["factor"] >= REFLEXION_FACTOR_MINIMO, (media, n, momentum)


def test_una_expectativa_positiva_deja_el_peso_intacto():
    res = _consultar(_dosier_sintetico(+0.03, 300), "VALOR", None)
    assert res["factor"] == 1.0
    assert res["desfavorable"] is False


def test_una_expectativa_negativa_recorta_y_habilita_el_veto():
    res = _consultar(_dosier_sintetico(-0.04, 300), "VALOR", None)
    assert res["factor"] < 1.0
    assert res["desfavorable"] is True


def test_el_veto_de_reflexion_solo_baja_el_rating():
    """El veto nuevo no puede mejorar ningún dictamen, en ninguna combinación."""
    escalera = ["VENTA FUERTE", "VENTA", "MANTENER", "COMPRA", "COMPRA FUERTE"]
    for bruto in escalera:
        sin = aplicar_vetos.invoke({
            "rating_bruto": bruto, "estilo": "GARP", "banderas_rojas": [],
            "sobreextendido": False, "confianza_datos": 1.0,
            "reflexion_desfavorable": False})
        con = aplicar_vetos.invoke({
            "rating_bruto": bruto, "estilo": "GARP", "banderas_rojas": [],
            "sobreextendido": False, "confianza_datos": 1.0,
            "reflexion_desfavorable": True})
        assert escalera.index(con["rating"]) <= escalera.index(sin["rating"])


# --------------------------------------------------------------------------- #
# 3. Sin muestra no hay ajuste, y se declara
# --------------------------------------------------------------------------- #
def test_sin_historia_la_capa_es_neutra_y_lo_declara():
    """
    Una instalación recién puesta en marcha no penaliza a nadie.

    Y lo dice: `evaluable=False` con motivo, nunca un 1.0 mudo indistinguible de
    «no hay nada que penalizar». Es la misma distinción que separa un ajuste de
    entrada de 0.0 de uno ausente.
    """
    for dosier in ({}, None, {"tabla": {}, "evaluable": False, "motivo": "sin muestra"}):
        res = _consultar(dosier, "VALOR", "ALCISTA")
        assert res["factor"] == 1.0
        assert res["evaluable"] is False
        assert res["motivo"]


def test_una_celda_por_debajo_del_minimo_no_ajusta():
    """Aunque la expectativa sea pésima: veinte observaciones no son evidencia."""
    res = _consultar(_dosier_sintetico(-0.50, REFLEXION_MUESTRA_MINIMA - 1), "VALOR", None)
    assert res["factor"] == 1.0
    assert res["evaluable"] is False


def test_la_contraccion_amortigua_las_celdas_pequenas():
    """Con la misma media, más muestra implica más recorte."""
    poca = _consultar(_dosier_sintetico(-0.04, REFLEXION_MUESTRA_MINIMA), "VALOR", None)
    mucha = _consultar(_dosier_sintetico(-0.04, 4000), "VALOR", None)
    assert mucha["factor"] < poca["factor"] <= 1.0


# --------------------------------------------------------------------------- #
# 4. La reasignación conserva el presupuesto
# --------------------------------------------------------------------------- #
def _pos(ticker: str, peso: float, factor: float) -> PosicionPropuesta:
    return PosicionPropuesta(
        ticker=ticker, empresa=ticker, sector="Technology", rating="COMPRA",
        estilo="GARP", conviccion=60.0, peso_solicitado=peso, peso_final=peso,
        precio=100.0, stop=90.0, volatilidad=0.25, factor_reflexion=factor)


def test_la_reasignacion_conserva_la_exposicion():
    """
    Lo recortado a un candidato va a los demás, no a la liquidez.

    Es la diferencia entre la variante «solo penalizar» y la elegida: el sistema
    ya opera con una exposición bruta media del 30%, y una capa que solo restara
    agravaría la limitación que el propio informe declara como la mayor.
    """
    candidatas = [_pos("AAA", 0.04, 0.5), _pos("BBB", 0.04, 1.0), _pos("CCC", 0.04, 1.0)]
    antes = sum(p.peso_final for p in candidatas)
    restricciones: list = []

    PortfolioConstructor()._penalizar_reflexion(candidatas, restricciones)

    assert sum(p.peso_final for p in candidatas) == pytest.approx(antes)
    assert candidatas[0].peso_final < 0.04     # la penalizada baja
    assert candidatas[1].peso_final > 0.04     # las limpias suben
    assert candidatas[2].peso_final > 0.04
    assert restricciones


def test_la_reasignacion_no_supera_el_tope_de_concentracion():
    """Conservar la exposición nunca justifica romper el límite por posición."""
    candidatas = [_pos("AAA", 0.09, 0.4), _pos("BBB", PESO_MAXIMO_POSICION - 0.001, 1.0)]
    PortfolioConstructor()._penalizar_reflexion(candidatas, [])
    assert all(p.peso_final <= PESO_MAXIMO_POSICION + 1e-9 for p in candidatas)


def test_sin_receptores_el_presupuesto_no_se_reparte():
    """
    Con un único candidato y penalizado, no hay a quién reasignar.

    El peso se queda recortado y el freno efectivo pasa a ser el veto. Que este
    caso exista está documentado en `_penalizar_reflexion`; el test lo fija para
    que nadie lo "arregle" devolviéndole el peso al penalizado.
    """
    candidatas = [_pos("AAA", 0.05, 0.5)]
    PortfolioConstructor()._penalizar_reflexion(candidatas, [])
    assert candidatas[0].peso_final == pytest.approx(0.025)


def test_sin_penalizadas_la_capa_no_toca_nada():
    candidatas = [_pos("AAA", 0.04, 1.0), _pos("BBB", 0.03, 1.0)]
    restricciones: list = []
    PortfolioConstructor()._penalizar_reflexion(candidatas, restricciones)
    assert [p.peso_final for p in candidatas] == [0.04, 0.03]
    assert not restricciones
    assert all(not p.ajustes for p in candidatas)
