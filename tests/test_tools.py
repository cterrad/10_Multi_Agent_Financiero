"""
Tests del registro de tools y de la frontera JSON.

Qué protegen
------------
Las tools son ahora el único hogar de las reglas de cálculo, así que dos
propiedades pasan a ser críticas:

  1. El REGISTRO es coherente: nombres únicos, todas invocables por nombre, y el
     subconjunto expuesto al agente ReAct no incluye ninguna tool que emita
     dictámenes. Esa última es la barrera que impide que el modelo decida.
  2. La frontera JSON es fiel: lo que entra y sale de una tool tiene que caber
     en un `ToolMessage`, es decir, ser serializable, y la conversión de
     magnitudes tiene que ir y volver sin perder procedencia.

Offline y deterministas: no se invoca ninguna tool de red.
"""

import json

import pytest

from src.data.magnitudes import (
    detalle_magnitudes,
    magnitud,
    magnitudes_desde_detalle,
)
from src.tools import REGISTRO_TOOLS, TODAS_LAS_TOOLS, TOOLS_LECTURA, obtener_tool

# Tools que producen una variable de decisión. El agente investigador NO puede
# alcanzarlas: es la barrera que sostiene la invariante del proyecto.
TOOLS_DE_DECISION = {
    "calcular_rating_compuesto",
    "aplicar_vetos",
    "calcular_niveles_riesgo",
    "dimensionar_posicion",
    "calcular_perfil_riesgo",
    "construir_cartera",
    "reconciliar_fuentes",
}

# Tools que salen a la red. No se invocan en esta suite.
TOOLS_DE_RED = {
    "obtener_datos_yfinance", "obtener_hechos_sec", "obtener_datos_finnhub",
    "obtener_noticias", "obtener_benchmark",
}


# --------------------------------------------------------------------------- #
# 1. Registro
# --------------------------------------------------------------------------- #
def test_los_nombres_no_se_repiten():
    """
    Dos tools con el mismo nombre harían que una eclipsara a la otra en el
    diccionario, y el agente ejecutaría un cálculo distinto del que cree.
    """
    nombres = [t.name for t in TODAS_LAS_TOOLS]
    assert len(nombres) == len(set(nombres)), \
        f"duplicados: {sorted({n for n in nombres if nombres.count(n) > 1})}"


def test_todas_se_obtienen_por_nombre():
    for nombre in REGISTRO_TOOLS:
        assert obtener_tool(nombre).name == nombre


def test_un_nombre_desconocido_falla_de_forma_explicita():
    """
    Un nombre mal escrito en el plan de un agente debe romper en el acto. Si
    devolviera None, el informe saldría sin ese bloque de análisis y nadie se
    enteraría.
    """
    with pytest.raises(KeyError) as exc:
        obtener_tool("calcular_lo_que_sea")
    assert "calcular_altman" in str(exc.value), "el error debe listar las válidas"


def test_toda_tool_tiene_descripcion():
    """
    El docstring es lo que el LLM lee para decidir si una tool le sirve. Una
    tool sin descripción es inutilizable en la rama ReAct.
    """
    sin_doc = [t.name for t in TODAS_LAS_TOOLS if not (t.description or "").strip()]
    assert not sin_doc, f"sin descripción: {sin_doc}"


# --------------------------------------------------------------------------- #
# 2. La barrera del agente investigador
# --------------------------------------------------------------------------- #
def test_el_react_no_alcanza_ninguna_tool_de_decision():
    """
    ESTA ES LA BARRERA. Si una tool de decisión entra en `TOOLS_LECTURA`, el
    agente ReAct podría emitir ratings o pesos y la invariante del proyecto
    dejaría de sostenerse. El backtest se invalidaría con ella.
    """
    expuestas = {t.name for t in TOOLS_LECTURA}
    filtradas = expuestas & TOOLS_DE_DECISION
    assert not filtradas, (
        f"El agente investigador alcanza tools de decisión: {sorted(filtradas)}. "
        f"Si esto es intencionado, el backtest deja de ser válido.")


def test_el_react_si_alcanza_los_scorers_de_calidad():
    """Contrapartida: sí debe poder consultar los cálculos para explicarlos."""
    expuestas = {t.name for t in TOOLS_LECTURA}
    for esperada in ("calcular_altman", "calcular_piotroski", "calcular_graham",
                     "construir_magnitudes_base"):
        assert esperada in expuestas


# --------------------------------------------------------------------------- #
# 3. Frontera JSON
# --------------------------------------------------------------------------- #
def test_las_magnitudes_hacen_ida_y_vuelta_sin_perder_procedencia():
    """
    Las magnitudes cruzan la frontera de la tool serializadas. Si el viaje
    perdiera la fuente o la disponibilidad, `Magnitud` dejaría de cumplir su
    función y volveríamos a confundir «no se sabe» con «vale cero».
    """
    original = {
        "roe": magnitud(0.31, fuente="SEC EDGAR", unidad="pct", periodo="FY2025"),
        "pe": magnitud(None, fuente="yfinance"),
        "deuda": magnitud(1.2, fuente="Finnhub", unidad="veces"),
    }
    serializado = detalle_magnitudes(original)
    json.dumps(serializado)  # debe caber en un ToolMessage

    vuelta = magnitudes_desde_detalle(serializado)
    assert detalle_magnitudes(vuelta) == serializado
    assert vuelta["pe"].disponible is False
    assert vuelta["roe"].fuente == "SEC EDGAR"
    assert vuelta["deuda"].unidad == "veces"


def test_la_salida_de_los_scorers_es_serializable():
    """Todo lo que devuelve una tool tiene que caber en un `ToolMessage`."""
    from src.tools.tecnico import evaluar_bollinger, evaluar_macd, evaluar_rsi

    for tool, args in [
        (evaluar_rsi, {"rsi": 71.4}),
        (evaluar_macd, {"macd_hist": 0.42, "atr": 2.0}),
        (evaluar_bollinger, {"close": 100.0, "bb_upper": 105.0, "bb_lower": 95.0}),
    ]:
        json.dumps(tool.invoke(args))


# --------------------------------------------------------------------------- #
# 4. Las tools calculan lo mismo que antes
# --------------------------------------------------------------------------- #
def test_el_rsi_penaliza_proporcionalmente_al_exceso():
    """
    La corrección que motivó el clasificador continuo: un 83.9 no puede restar
    lo mismo que un 70.1.
    """
    from src.tools.tecnico import evaluar_rsi

    leve = evaluar_rsi.invoke({"rsi": 70.1})["aporte"]
    extremo = evaluar_rsi.invoke({"rsi": 83.9})["aporte"]
    assert extremo < leve < 0


def test_el_umbral_de_deuda_es_sectorial():
    """Aplicar el límite de una empresa de software a un banco es un error de categoría."""
    from src.config import GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR
    from src.tools.fundamentales import umbral_deuda_sectorial

    generico = umbral_deuda_sectorial.invoke({"sector": "Technology"})
    assert generico["es_excepcion_sectorial"] is False

    sector_apalancado = next(iter(GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR))
    especial = umbral_deuda_sectorial.invoke({"sector": sector_apalancado})
    assert especial["es_excepcion_sectorial"] is True
    assert especial["umbral"] == GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR[sector_apalancado]


def test_el_gatekeeper_no_evalua_criterios_sin_datos():
    """
    Con una magnitud obligatoria ausente el veredicto es DATOS_INSUFICIENTES y
    NO se evalúa ningún criterio: comparar contra `None` produciría un rechazo
    que los números no sustentan.
    """
    from src.tools.fundamentales import evaluar_criterios_gatekeeper

    r = evaluar_criterios_gatekeeper.invoke({
        "sector": "Technology", "industria": "Software",
        "metricas_reconciliadas": {"net_margin": 0.2, "revenue_growth": None,
                                   "debt_to_equity": 0.5},
        "confianza_datos": 1.0,
    })
    assert r["status"] == "DATOS_INSUFICIENTES"
    assert r["criterios"] == []
    assert r["passed_gatekeeper"] is False


def test_los_vetos_solo_bajan_el_rating():
    """
    Ninguna condición puede mejorar un dictamen. Si alguna lo hiciera, una
    bandera roja podría compensarse con un múltiplo atractivo y el sesgo del
    sistema se invertiría.
    """
    from src.tools.decision import ESCALERA, aplicar_vetos

    for bruto in ESCALERA:
        for estilo in ("ESPECULATIVA", "TRAMPA_DE_VALOR", "DATOS_INSUFICIENTES", "GARP"):
            for banderas in ([], ["a"], ["a", "b"]):
                for sobre in (True, False):
                    for confianza in (0.4, 0.9):
                        r = aplicar_vetos.invoke({
                            "rating_bruto": bruto, "estilo": estilo,
                            "banderas_rojas": banderas, "sobreextendido": sobre,
                            "confianza_datos": confianza})
                        assert ESCALERA.index(r["rating"]) <= ESCALERA.index(bruto), (
                            f"{estilo}/{banderas}/{sobre}/{confianza} SUBIÓ "
                            f"{bruto} a {r['rating']}")


# --------------------------------------------------------------------------- #
# 5. La separación entre red y cálculo
# --------------------------------------------------------------------------- #
def test_las_tools_de_red_estan_donde_deben():
    """
    Todo lo que sale a la red vive en `src.tools.extraccion`. Mirando los
    imports de un agente se sabe si puede hacer una petición, y esa propiedad se
    pierde en cuanto una tool de red se cuela en otro módulo.
    """
    for nombre in TOOLS_DE_RED:
        tool = obtener_tool(nombre)
        modulo = getattr(tool.func, "__module__", "")
        assert modulo == "src.tools.extraccion", f"{nombre} vive en {modulo}"


def test_los_scorers_no_estan_en_el_modulo_de_red():
    """La contrapartida: ningún cálculo puro debe vivir junto a los fetchers."""
    for nombre in ("calcular_altman", "calcular_piotroski", "evaluar_rsi",
                   "calcular_rating_compuesto"):
        modulo = getattr(obtener_tool(nombre).func, "__module__", "")
        assert modulo != "src.tools.extraccion"
