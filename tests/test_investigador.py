"""
Tests del agente investigador ReAct.

Qué protegen
------------
Este agente es la única pieza del sistema donde el LLM elige. Toda su
legitimidad descansa en que no pueda tocar una decisión, así que los tests
comprueban exactamente eso y no su calidad de redacción:

  1. NO ALTERA LA DECISIÓN. Con y sin `research_report` en el estado, el rating,
     el peso y los niveles salen idénticos. Es el gemelo de
     `test_news_report_does_not_alter_decision`, y por el mismo motivo: si algún
     día la respuesta del modelo alimentara la decisión, el backtest dejaría de
     ser válido y ESTE TEST DEBE FALLAR.
  2. NO ALCANZA LAS TOOLS DE DECISIÓN. La barrera es la lista `TOOLS_LECTURA`.
  3. NO CORRE EN EL BACKTEST. `disable_llm()` lo desarma.
  4. EL BUCLE ESTÁ ACOTADO Y NO PIERDE LA RESPUESTA en el turno de solo
     pensamiento que devuelve Gemini.

Offline y deterministas: el LLM es un doble; nunca se sale a la red.
"""

import copy

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

import src.agents.fund_manager as fm_mod
import src.agents.investigador as inv_mod
from src.graph.investigacion import (
    MAX_TURNOS_VACIOS,
    PETICION_DE_CIERRE,
    _debe_continuar,
)
from tests.test_llm_texto import _estado_completo


# --------------------------------------------------------------------------- #
# 1. La premisa: es capa ASESORA
# --------------------------------------------------------------------------- #
def test_research_report_does_not_alter_decision():
    """
    LA PREMISA QUE SOSTIENE TODO. El informe del investigador es texto y solo
    texto: añadirlo al estado no puede mover ni una variable de decisión.

    Si este test falla, el agente ReAct ha entrado en la ruta de decisión y el
    backtest deja de medir lo que producción hace.
    """
    base = copy.deepcopy(_estado_completo())
    con_informe = copy.deepcopy(base)
    con_informe["research_report"] = {
        "ticker": "TEST",
        "pregunta": "¿Es sólido el balance?",
        "respuesta": "El balance muestra una posición de caja muy holgada y sin deuda "
                     "relevante; la compañía podría recomprar acciones agresivamente.",
        "tools_invocadas": ["obtener_datos_yfinance", "calcular_altman"],
        "advisory_only": True,
    }

    original = fm_mod.get_llm
    try:
        fm_mod.get_llm = lambda: None
        sin = fm_mod.FundManagerAgent().analyze(base)
        con = fm_mod.FundManagerAgent().analyze(con_informe)
    finally:
        fm_mod.get_llm = original

    for campo in ("rating", "position_size_pct", "peso_objetivo",
                  "stop_loss_atr", "take_profit_atr", "vetos_aplicados"):
        assert sin[campo] == con[campo], (
            f"`{campo}` cambió al añadir el informe del investigador: "
            f"{sin[campo]!r} -> {con[campo]!r}")


# --------------------------------------------------------------------------- #
# 2. La barrera de alcance
# --------------------------------------------------------------------------- #
def test_el_investigador_no_ve_las_tools_de_decision():
    """La lista que se le enlaza no contiene nada que emita un dictamen."""
    from src.tools import TOOLS_LECTURA

    prohibidas = {"calcular_rating_compuesto", "aplicar_vetos",
                  "dimensionar_posicion", "calcular_niveles_riesgo",
                  "calcular_perfil_riesgo", "construir_cartera"}
    assert not ({t.name for t in TOOLS_LECTURA} & prohibidas)


# --------------------------------------------------------------------------- #
# 3. Sin proveedor no hay agente, y eso se declara
# --------------------------------------------------------------------------- #
def test_sin_llm_falla_de_forma_explicita():
    """
    Los otros seis agentes degradan a su motor heurístico y emiten el mismo
    dictamen. Este no tiene motor al que degradar: su trabajo ES el
    razonamiento del modelo. Fallar claro es más honesto que devolver un
    informe vacío que parezca una respuesta.
    """
    original = inv_mod.get_llm
    try:
        inv_mod.get_llm = lambda: None
        with pytest.raises(inv_mod.LLMNoConfigurado):
            inv_mod.modelo_con_tools()
    finally:
        inv_mod.get_llm = original


def test_el_backtest_lo_desarma():
    """
    `disable_llm()` tiene que cubrirlo: encadena varias llamadas al proveedor
    por invocación y una sola dejada suelta abriría red y coste en mitad de un
    backtest offline.
    """
    from src.backtest.replay import disable_llm

    original = inv_mod.get_llm
    try:
        disable_llm()
        with pytest.raises(inv_mod.LLMNoConfigurado):
            inv_mod.modelo_con_tools()
    finally:
        inv_mod.get_llm = original


# --------------------------------------------------------------------------- #
# 4. El bucle
# --------------------------------------------------------------------------- #
def _ai(texto="", tool_calls=None):
    return AIMessage(content=texto, tool_calls=tool_calls or [])


def test_con_tool_calls_el_bucle_continua():
    estado = {"messages": [HumanMessage(content="?"),
                           _ai(tool_calls=[{"name": "calcular_altman", "args": {}, "id": "1"}])]}
    assert _debe_continuar(estado) == "continuar"


def test_con_texto_el_bucle_termina():
    estado = {"messages": [HumanMessage(content="?"), _ai("La respuesta es 0.04.")]}
    assert _debe_continuar(estado) == "fin"


def test_un_turno_de_solo_pensamiento_no_se_toma_por_respuesta():
    """
    Gemini cierra a veces con un `content` de un único bloque sin texto. La
    condición del curso —«¿hay tool_calls? si no, fin»— lo tomaba por respuesta
    final y el agente devolvía una cadena vacía habiendo consultado cuatro
    tools. Se observó analizando DOCN.
    """
    class _SoloPensamiento(AIMessage):
        pass

    vacio = AIMessage(content=[{"type": "text", "text": "",
                                "extras": {"signature": "abc"}}])
    estado = {"messages": [HumanMessage(content="?"), vacio]}
    assert _debe_continuar(estado) == "reintentar"


def test_la_insistencia_esta_acotada():
    """
    Un modelo que nunca produce texto no puede encadenar llamadas
    indefinidamente. El tope se cuenta sobre las peticiones de cierre ya
    enviadas, porque `_nodo_reencauzar` intercala un turno de usuario y los
    vacíos nunca quedan consecutivos.
    """
    vacio = AIMessage(content=[{"type": "text", "text": ""}])
    mensajes = [HumanMessage(content="?")]
    for _ in range(MAX_TURNOS_VACIOS):
        mensajes += [vacio, HumanMessage(content=PETICION_DE_CIERRE)]
    mensajes.append(vacio)
    assert _debe_continuar({"messages": mensajes}) == "fin"


# --------------------------------------------------------------------------- #
# 5. Extracción del texto
# --------------------------------------------------------------------------- #
def test_la_respuesta_se_aplana_a_texto():
    """
    Los turnos del modelo llegan como lista de bloques. Volcarlos con `str()`
    imprimiría `[{'type': 'text', ...}]` en el informe, que es el defecto que
    `texto_de_respuesta_llm` existe para cortar y que reapareció aquí.
    """
    mensajes = [
        SystemMessage(content="sistema"),
        HumanMessage(content="pregunta"),
        _ai(tool_calls=[{"name": "calcular_altman", "args": {}, "id": "1"}]),
        ToolMessage(tool_call_id="1", name="calcular_altman", content='{"z": 0.04}'),
        AIMessage(content=[{"type": "text", "text": "El Z-Score es 0.04."}]),
    ]
    resumen = inv_mod.resumen_de_traza(mensajes)
    assert resumen["respuesta"] == "El Z-Score es 0.04."
    assert resumen["tools_invocadas"] == ["calcular_altman"]
    assert isinstance(resumen["respuesta"], str)
