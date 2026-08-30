"""
Tests de la traza tipada de los agentes.

Qué protegen
------------
La traza es lo que permite responder «de dónde salió esta cifra» sin releer el
código, así que tiene que cumplir tres cosas:

  1. Estar bien FORMADA: cada `AIMessage` con `tool_calls` tiene su `ToolMessage`
     correspondiente, emparejados por `tool_call_id`. Un par roto no da error en
     ninguna parte; simplemente deja un hueco en la auditoría.
  2. Ser REPRODUCIBLE: dos ejecuciones del mismo análisis producen la misma
     traza. Con identificadores aleatorios no lo era, y `daily_selection.json`
     cambiaba entero en cada pasada.
  3. Tener ids ÚNICOS: `add_messages` deduplica por `id`, así que un id repetido
     hace DESAPARECER mensajes del estado sin ningún error visible.

Offline y deterministas: el LLM es un doble o está desactivado.
"""

import copy

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

import src.agents.debate as debate_mod
import src.agents.fund_manager as fm_mod
import src.agents.fundamental as fund_mod
import src.agents.news as news_mod
import src.agents.quality as quality_mod
import src.agents.technical as tech_mod
from tests.test_llm_texto import _estado_completo

AGENTES = [
    (fund_mod, "FundamentalAnalystAgent"),
    (quality_mod, "QualityAnalystAgent"),
    (tech_mod, "TechnicalAnalystAgent"),
    (news_mod, "NewsAnalystAgent"),
    (debate_mod, "DebateUnitAgent"),
    (fm_mod, "FundManagerAgent"),
]
IDS = [c for _, c in AGENTES]


def _ejecutar(modulo, clase):
    """Ejecuta un agente con el motor determinista y devuelve su informe."""
    original = modulo.get_llm
    try:
        modulo.get_llm = lambda: None
        return getattr(modulo, clase)().analyze(copy.deepcopy(_estado_completo()))
    finally:
        modulo.get_llm = original


# --------------------------------------------------------------------------- #
# 1. Forma de la traza
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_la_traza_empieza_con_la_tarea(modulo, clase):
    """El primer mensaje declara qué se le pidió al agente."""
    mensajes = _ejecutar(modulo, clase)["_mensajes"]
    assert isinstance(mensajes[0], HumanMessage)
    assert mensajes[0].content


@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_la_traza_termina_con_el_texto_publicado(modulo, clase):
    """
    El último mensaje es el dictamen redactado. Cierra la traza con lo que el
    informe va a imprimir, de modo que se puede comparar la conclusión con los
    pasos que la produjeron sin salir de la lista.
    """
    informe = _ejecutar(modulo, clase)
    ultimo = informe["_mensajes"][-1]
    assert isinstance(ultimo, AIMessage)
    campo = "synthesis" if clase == "DebateUnitAgent" else "summary"
    assert ultimo.content == informe[campo]


@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_cada_tool_call_tiene_su_resultado(modulo, clase):
    """
    Emparejamiento por `tool_call_id`. Un par roto no lanza ninguna excepción:
    simplemente deja la traza incompleta, que es la peor forma de fallar para
    algo cuyo propósito es auditar.
    """
    mensajes = _ejecutar(modulo, clase)["_mensajes"]
    pedidos = {tc["id"]: tc["name"]
               for m in mensajes for tc in (getattr(m, "tool_calls", None) or [])}
    devueltos = {m.tool_call_id: m.name for m in mensajes if isinstance(m, ToolMessage)}
    assert pedidos == devueltos


@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_los_ids_de_mensaje_son_unicos(modulo, clase):
    """
    `add_messages` deduplica por `id`. Con ids repetidos, LangGraph fusiona
    mensajes y la traza pierde pasos sin dar ningún error.
    """
    ids = [m.id for m in _ejecutar(modulo, clase)["_mensajes"]]
    assert len(ids) == len(set(ids)), f"ids repetidos: {sorted({i for i in ids if ids.count(i) > 1})}"
    assert all(ids), "todo mensaje debe llevar id"


# --------------------------------------------------------------------------- #
# 2. Reproducibilidad
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_la_traza_es_reproducible(modulo, clase):
    """
    Dos ejecuciones del mismo análisis producen la misma traza serializada. Sin
    esta propiedad, `daily_selection.json` cambia entero en cada pasada y
    cualquier diff entre dos días deja de significar nada.
    """
    a = _ejecutar(modulo, clase)["_traza"]
    b = _ejecutar(modulo, clase)["_traza"]
    assert a == b


@pytest.mark.parametrize("modulo,clase", AGENTES, ids=IDS)
def test_la_traza_publicada_no_lleva_tiempos(modulo, clase):
    """
    Las duraciones van al JSONL, no al informe: son irrepetibles por naturaleza
    y meterlas en el informe rompería la reproducibilidad de arriba.
    """
    for registro in _ejecutar(modulo, clase)["_traza"]["tools"]:
        assert "duracion_ms" not in registro


# --------------------------------------------------------------------------- #
# 3. Los agentes usan tools de verdad
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modulo,clase,minimo", [
    (quality_mod, "QualityAnalystAgent", 10),   # las siete escuelas y la agregación
    (tech_mod, "TechnicalAnalystAgent", 6),     # los cinco bloques y la etiqueta
    (fm_mod, "FundManagerAgent", 5),            # rating, vetos, niveles, tamaño, riesgo
    (fund_mod, "FundamentalAnalystAgent", 1),
    (news_mod, "NewsAnalystAgent", 2),
    (debate_mod, "DebateUnitAgent", 3),
], ids=IDS)
def test_cada_agente_invoca_sus_tools(modulo, clase, minimo):
    """
    Comprueba que el análisis pasa realmente por el registro de tools y no por
    una copia de la lógica escondida en el agente. Si alguien reimplantara un
    scorer dentro del agente, el recuento caería.
    """
    traza = _ejecutar(modulo, clase)["_traza"]
    assert len(traza["tools"]) >= minimo, \
        f"{clase} solo invocó {[t['tool'] for t in traza['tools']]}"


def test_el_analista_de_calidad_recorre_las_siete_escuelas():
    """Ninguna escuela puede quedarse fuera en silencio."""
    traza = _ejecutar(quality_mod, "QualityAnalystAgent")["_traza"]
    invocadas = {t["tool"] for t in traza["tools"]}
    for escuela in ("calcular_piotroski", "calcular_altman", "calcular_graham",
                    "calcular_buffett", "calcular_lynch", "calcular_greenblatt",
                    "calcular_devengos_sloan"):
        assert escuela in invocadas, f"falta {escuela}"


# --------------------------------------------------------------------------- #
# 4. El estado y sus reductores
# --------------------------------------------------------------------------- #
def test_el_estado_declara_reductores_en_logs_y_mensajes():
    """
    Sin reductor, dos nodos del mismo superstep no pueden escribir el mismo
    canal: LangGraph aborta con `InvalidUpdateError`. Es lo que obligaba al
    analista de noticias a no registrar nada.
    """
    from typing import get_type_hints

    from src.state import FinancialAnalysisState

    hints = get_type_hints(FinancialAnalysisState, include_extras=True)
    for canal in ("logs", "messages"):
        assert hasattr(hints[canal], "__metadata__"), \
            f"`{canal}` no declara reductor y volvería a chocar en el fan-out"
