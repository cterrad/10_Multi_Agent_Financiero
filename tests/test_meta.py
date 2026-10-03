"""
Tests de la capa de meta-etiquetado y de la maquinaria de validación.

Qué protegen
------------
1. **EL ARTEFACTO QUE VIO EL FUTURO LEVANTA EXCEPCIÓN.** Es la barrera más
   importante del módulo y la única defensa contra un peligro que ningún otro
   test de este repositorio detecta: un modelo entrenado con 2015-2025 y
   evaluado sobre 2016 produce un backtest excelente y sin ningún valor, y nada
   en las cifras lo delataría.
2. **El corte del conjunto de entrenamiento es la fecha de DESENLACE**, no la de
   emisión. Es el par `filed`/`end` del XBRL aplicado por cuarta vez, y
   relajarlo convierte el estudio en un examen de memoria.
3. **EL FACTOR SOLO RECORTA**, sobre el producto cartesiano. Mismo contrato que
   `factor_reflexion`, `aplicar_vetos` y `ajustar_precio_entrada`.
4. **La CV es purgada y con embargo**: ninguna fecha del bloque de prueba, ni de
   su embargo, aparece en el de entrenamiento.
5. **Sin artefacto, el sistema se comporta EXACTAMENTE como antes.**
6. **Ausencia ≠ cero** en las tres capas: variable ausente → sin probabilidad;
   operación sin resolver → etiqueta `None`, nunca 0.

Offline y deterministas.
"""

import copy

import numpy as np
import pandas as pd
import pytest

from src.agents.fund_manager import FundManagerAgent
from src.config import META_FACTOR_MINIMO
from src.meta.artefacto import (
    ArtefactoAnacronico,
    ArtefactoIlegible,
    MetaArtefacto,
    cargar_para,
    guardar,
)
from src.meta.banco import BancoDeEtiquetas
from src.tools.etiquetado import _etiquetar
from src.tools.meta import _consultar
from src.tools.niveles import frac_diff_ultimo, pesos_ffd
from src.tools.riesgo import _freno
from src.tools.validacion import (
    ParticionPurgadaPorGrupos,
    pesos_de_muestra,
    unicidad_media,
)


@pytest.fixture(autouse=True)
def _motor_determinista(monkeypatch):
    import src.agents.fund_manager as fm
    monkeypatch.setattr(fm, "get_llm", lambda: None)


def _artefacto(hasta="2019-12-31"):
    return MetaArtefacto(
        variables=["a", "b"], coeficientes=[0.5, -0.3], intercepto=0.1,
        media=[0.0, 0.0], escala=[1.0, 1.0],
        entrenado_hasta=hasta, entrenado_desde="2015-01-05",
        n_muestras=300, tasa_base=0.45)


# --------------------------------------------------------------------------- #
# 1. LA BARRERA: el artefacto no puede haber visto el futuro
# --------------------------------------------------------------------------- #
def test_un_artefacto_que_vio_el_futuro_levanta_excepcion(tmp_path):
    """
    ESTA ES LA BARRERA. Ningún otro test del repositorio detectaría un modelo
    entrenado sobre el futuro: `test_no_lookahead_*` mira precios,
    `test_fundamentals_respect_filed_not_end` mira `filed`. Ninguno mira de qué
    años salieron los coeficientes.
    """
    ruta = tmp_path / "art.json"
    guardar(_artefacto("2019-12-31"), ruta)

    # Usarlo en 2020 es legítimo: el entrenamiento terminó antes.
    art = cargar_para(ruta, "2020-01-15")
    assert art.entrenado_hasta == "2019-12-31"

    # Usarlo en 2019 o antes NO lo es.
    for fecha in ("2019-12-31", "2019-06-01", "2016-01-01"):
        with pytest.raises(ArtefactoAnacronico):
            cargar_para(ruta, fecha)


def test_la_comparacion_es_mayor_o_igual_y_no_estrictamente_mayor():
    """
    Un artefacto entrenado con etiquetas resueltas EL MISMO DÍA en que se
    pretende decidir ya conoce el desenlace de operaciones que en ese momento
    seguían abiertas. Por eso el corte es `>=` y no `>`.
    """
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "a.json"
        guardar(_artefacto("2020-03-16"), ruta)
        with pytest.raises(ArtefactoAnacronico):
            cargar_para(ruta, "2020-03-16")
        assert cargar_para(ruta, "2020-03-17") is not None


def test_un_artefacto_ausente_o_incompleto_falla_ruidosamente(tmp_path):
    """
    **No devuelve `None`.** Quien quiera degradar ante la ausencia de modelo
    debe capturar la excepción explícitamente, para que la degradación sea una
    decisión escrita y no el efecto secundario de un `if` olvidado.
    """
    with pytest.raises(ArtefactoIlegible):
        cargar_para(tmp_path / "no_existe.json", "2020-01-01")

    malo = tmp_path / "malo.json"
    malo.write_text('{"variables": ["a"]}', encoding="utf-8")
    with pytest.raises(ArtefactoIlegible):
        cargar_para(malo, "2020-01-01")


def test_el_artefacto_es_json_legible_y_reproducible(tmp_path):
    """
    JSON y no `pickle`: un pickle es código ejecutable, no se puede revisar en un
    diff y no sobrevive a un cambio de versión de scikit-learn.
    """
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    guardar(_artefacto(), a)
    guardar(_artefacto(), b)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")
    assert '"huella"' in a.read_text(encoding="utf-8")


def test_sin_todas_las_variables_no_hay_probabilidad():
    """Ausencia ≠ cero: no se imputa la media del entrenamiento."""
    art = _artefacto()
    assert art.probabilidad({"a": 1.0, "b": 2.0}) is not None
    assert art.probabilidad({"a": 1.0}) is None
    assert art.probabilidad({"a": 1.0, "b": None}) is None
    assert art.probabilidad({"a": float("nan"), "b": 1.0}) is None


# --------------------------------------------------------------------------- #
# 2. El banco: el corte es la fecha de DESENLACE
# --------------------------------------------------------------------------- #
def _barras(desde: str, n: int, alto: float, bajo: float):
    fechas = pd.bdate_range(desde, periods=n)
    return [{"fecha": str(f.date()), "high": alto, "low": bajo, "close": (alto + bajo) / 2}
            for f in fechas]


def test_el_conjunto_filtra_por_fecha_de_desenlace_no_de_emision():
    """
    LA REGLA QUE HACE VÁLIDO TODO LO DEMÁS. Una señal del 1 de junio resuelta en
    julio NO puede entrenar un modelo que decide en junio.
    """
    banco = BancoDeEtiquetas()
    banco.anotar("2020-06-01", "AAA", {"x": 1.0}, entrada=100.0,
                 stop=90.0, objetivo=110.0, horizonte=21)
    banco.etiquetas[0].etiqueta = 1
    banco.etiquetas[0].retorno = 0.10
    banco.etiquetas[0].fecha_desenlace = "2020-07-15"

    # En junio la señal existe pero su desenlace NO se conoce.
    assert banco.conjunto("2020-06-15") == []
    assert banco.conjunto("2020-07-15") == []      # el mismo día tampoco
    assert len(banco.conjunto("2020-07-16")) == 1


def test_una_operacion_sin_terminar_no_tiene_etiqueta_cero():
    """
    `None` significa «sigue abierta»; `0` significa «acabó en pérdida».
    Colapsarlos metería en el entrenamiento desenlaces que aún no se conocen.
    """
    r = _etiquetar(_barras("2020-01-01", 5, 105.0, 99.0), entrada=100.0,
                   stop=90.0, objetivo=110.0, horizonte=21)
    assert r["etiqueta"] is None
    assert "sigue abierta" in r["motivo"]


def test_el_etiquetado_usa_el_orden_pesimista_del_motor():
    """
    Si stop y objetivo se tocan en la misma sesión, gana el stop — la misma
    regla que `process_intraday_exits`. Si divergieran, el modelo se entrenaría
    con un desenlace distinto del que el backtest simula.
    """
    barras = [{"fecha": "2020-01-02", "high": 120.0, "low": 85.0, "close": 100.0}]
    r = _etiquetar(barras, entrada=100.0, stop=90.0, objetivo=110.0, horizonte=5)
    assert r["etiqueta"] == 0
    assert r["razon"] == "stop_loss"


def test_la_barrera_vertical_etiqueta_por_el_signo_del_retorno():
    ganadora = _etiquetar(_barras("2020-01-01", 5, 105.0, 99.0), 100.0, 90.0, 110.0, 5)
    assert ganadora["etiqueta"] == 1 and ganadora["razon"] == "vertical"
    perdedora = _etiquetar(_barras("2020-01-01", 5, 99.0, 95.0), 100.0, 90.0, 110.0, 5)
    assert perdedora["etiqueta"] == 0 and perdedora["razon"] == "vertical"


def test_el_banco_solo_anota_senales_de_compra():
    """El meta-etiquetado se define sobre los positivos del modelo primario."""
    class _S:
        def __init__(self, buy):
            self.is_buy, self.date, self.ticker = buy, pd.Timestamp("2020-01-02"), "AAA"
            self.close, self.stop_loss, self.take_profit = 100.0, 90.0, 110.0
            self.variables_meta, self.horizonte_dias = {"x": 1.0}, 21
    banco = BancoDeEtiquetas()
    assert banco.anotar_senales([_S(True), _S(False), _S(True)]) == 2


# --------------------------------------------------------------------------- #
# 3. LA BARRERA: el factor solo recorta
# --------------------------------------------------------------------------- #
def test_el_factor_meta_nunca_sube_el_peso():
    """
    Producto cartesiano completo. Ninguna probabilidad, por alta que sea, puede
    ampliar un peso: eso convertiría una capa de filtrado en una apuesta
    apalancada sobre el propio modelo, con 944 muestras de entrenamiento detrás.
    """
    for p in (None, 0.0, 0.1, 0.3, 0.45, 0.5, 0.7, 0.9, 1.0):
        for base in (None, 0.0, 0.2, 0.45, 0.5, 0.8, 1.0):
            r = _consultar(p, base)
            assert r["factor_meta"] <= 1.0, f"p={p} base={base} AMPLIÓ el peso"
            assert r["factor_meta"] >= META_FACTOR_MINIMO


def test_por_encima_de_la_tasa_base_el_factor_es_exactamente_neutro():
    for p in (0.45, 0.5, 0.8, 1.0):
        assert _consultar(p, 0.45)["factor_meta"] == 1.0


def test_el_factor_es_monotono_en_la_probabilidad():
    """Más probabilidad nunca puede dar menos peso."""
    previo = 0.0
    for p in [i / 20 for i in range(21)]:
        f = _consultar(p, 0.6)["factor_meta"]
        assert f >= previo - 1e-9, f"el factor bajó al subir p a {p}"
        previo = f


def test_sin_probabilidad_el_factor_es_neutro_y_lo_declara():
    r = _consultar(None, 0.45)
    assert r["factor_meta"] == 1.0 and r["evaluable"] is False and r["motivo"]


def test_sin_meta_el_fund_manager_decide_igual():
    """
    Rama de degradación: con `meta_data` ausente el dictamen es EXACTAMENTE el
    de antes de que esta capa existiera.
    """
    base = {
        "ticker": "TEST", "sector": "Technology", "passed_fundamental_gatekeeper": True,
        "yfinance_data": {"technical": {"close": 100.0, "atr": 2.0,
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
    sin = FundManagerAgent().analyze(copy.deepcopy(base))
    vacio = copy.deepcopy(base)
    vacio["meta_data"] = {}
    con = FundManagerAgent().analyze(vacio)
    for k in ("rating", "position_size_pct", "peso_objetivo",
              "stop_loss_atr", "take_profit_atr"):
        assert sin[k] == con[k], f"`{k}` cambió sin meta-modelo"
    assert sin["factor_meta"] == 1.0


# --------------------------------------------------------------------------- #
# 4. La CV purgada con embargo
# --------------------------------------------------------------------------- #
def test_la_particion_purga_el_bloque_y_embarga_lo_posterior():
    """
    Un k-fold corriente sobre etiquetas solapadas no es validación: es una fuga
    con un número al lado. Aquí se comprueba que ninguna fecha del bloque de
    prueba, ni de su embargo, aparece en el de entrenamiento.
    """
    fechas = pd.bdate_range("2020-01-01", periods=200)
    serie = pd.Series(fechas)
    particion = ParticionPurgadaPorGrupos(n_particiones=4, embargo_dias=10)
    n = 0
    for tr, te in particion.split(serie):
        n += 1
        f_tr, f_te = set(serie.iloc[tr]), set(serie.iloc[te])
        assert not (f_tr & f_te), "una fecha de prueba se coló en entrenamiento"
        hasta = max(f_te)
        embargo = {f for f in serie if hasta < f <= hasta + pd.Timedelta(days=10)}
        assert not (f_tr & embargo), "el embargo posterior no se respetó"
    assert n >= 3


def test_todas_las_filas_de_una_fecha_caen_del_mismo_lado():
    """
    Agrupa por fecha porque todas las señales de un rebalanceo comparten fecha:
    partirlas metería en el mismo fold dos observaciones que el sistema emitió a
    la vez con la misma información.
    """
    fechas = pd.Series(sum([[d] * 5 for d in pd.bdate_range("2020-01-01", periods=40)], []))
    for tr, te in ParticionPurgadaPorGrupos(4, 5).split(fechas):
        assert not (set(fechas.iloc[tr]) & set(fechas.iloc[te]))


# --------------------------------------------------------------------------- #
# 5. Unicidad y pesos
# --------------------------------------------------------------------------- #
def test_una_etiqueta_aislada_es_mas_unica_que_una_solapada():
    t0 = ["2020-01-01"] * 5 + ["2021-01-01"]
    t1 = ["2020-02-01"] * 5 + ["2021-02-01"]
    u = unicidad_media(t0, t1)
    assert u[5] > u[0], "la etiqueta aislada debería ser más única"
    assert u[5] == pytest.approx(1.0, abs=0.05)


def test_los_pesos_se_normalizan_a_media_uno():
    """Reordenan la importancia relativa; no inflan ni desinflan la muestra."""
    t0 = ["2020-01-01", "2020-01-15", "2020-06-01"]
    t1 = ["2020-02-01", "2020-02-15", "2020-07-01"]
    w = pesos_de_muestra(t0, t1, [0.10, -0.05, 0.02])
    assert w.mean() == pytest.approx(1.0)


def test_sin_retornos_utilizables_los_pesos_son_neutros():
    w = pesos_de_muestra(["2020-01-01"] * 3, ["2020-02-01"] * 3, [0.0, 0.0, 0.0])
    assert np.allclose(w, 1.0)


# --------------------------------------------------------------------------- #
# 6. Freno por drawdown
# --------------------------------------------------------------------------- #
def test_el_freno_por_drawdown_nunca_amplia():
    for dd in (None, 0.5, 0.0, -0.01, -0.10, -0.15, -0.30, -0.90):
        assert _freno(dd)["factor_drawdown"] <= 1.0, f"drawdown {dd} amplió"


def test_una_cartera_en_maximos_no_recibe_freno():
    assert _freno(0.0)["factor_drawdown"] == 1.0
    assert _freno(-0.05)["factor_drawdown"] == 1.0     # por debajo del umbral


def test_el_freno_es_monotono_en_el_drawdown():
    previo = 1.0
    for dd in [-i / 100 for i in range(0, 61, 5)]:
        f = _freno(dd)["factor_drawdown"]
        assert f <= previo + 1e-9, f"el freno se relajó al empeorar el drawdown a {dd}"
        previo = f


def test_sin_curva_de_capital_el_freno_es_neutro_y_lo_declara():
    """Es el estado PERMANENTE en producción: el sistema no gestiona cartera."""
    r = _freno(None)
    assert r["factor_drawdown"] == 1.0 and r["evaluable"] is False
    assert "producción" in r["motivo"]


# --------------------------------------------------------------------------- #
# 7. Diferenciación fraccional
# --------------------------------------------------------------------------- #
def test_los_pesos_ffd_caben_en_la_ventana_del_replay():
    """
    Con `umbral=1e-4` hacían falta 282 rezagos y la ventana del replay tiene ~250
    sesiones, así que la variable era `None` en TODAS las filas y el meta-modelo
    se negaba a entrenar. El síntoma fue el correcto —«0 etiquetas utilizables»
    en lugar de un modelo sobre datos imputados— pero el umbral estaba mal.
    """
    from src.config import FFD_D, FFD_UMBRAL
    assert len(pesos_ffd(FFD_D, FFD_UMBRAL)) < 200


def test_frac_diff_devuelve_none_sin_rezagos_suficientes():
    """Nunca 0.0: sería un valor plausible de la propia transformación."""
    assert frac_diff_ultimo([1.0, 2.0, 3.0], 0.4) is None
    assert frac_diff_ultimo(None, 0.4) is None


def test_frac_diff_conserva_memoria_frente_a_la_primera_diferencia():
    """
    El punto entero de la técnica: `d=1` es la primera diferencia y no conserva
    memoria; `d=0.4` sí. Sobre una serie con tendencia, el valor con `d` bajo
    tiene que ser sensiblemente mayor que la diferencia simple.
    """
    serie = [100.0 * (1.0003 ** i) for i in range(300)]
    frac = frac_diff_ultimo(serie, 0.4, 5e-4)
    diff = serie[-1] - serie[-2]
    assert frac is not None and abs(frac) > abs(diff)
