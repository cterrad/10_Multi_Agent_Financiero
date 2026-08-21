"""
Tests de `src.config.texto_de_respuesta_llm()` y de su uso en los cinco agentes.

Motivo de existir
-----------------
Los proveedores modernos devuelven `content` como LISTA de bloques
(`[{"type": "text", "text": "..."}]`), no como cadena. Los agentes asignaban ese
`content` directamente a `summary`/`synthesis`, así que el informe y
`daily_selection.json` acababan conteniendo literalmente una lista de
diccionarios de Python —incluida la firma interna del bloque— en lugar del
texto.

Estos tests fijan el contrato: pase lo que pase, `summary` y `synthesis` son
`str`. Son offline y deterministas: el LLM es un doble, nunca se sale a la red.
"""

import pytest

import src.agents.debate as debate_mod
import src.agents.fund_manager as fm_mod
import src.agents.fundamental as fund_mod
import src.agents.news as news_mod
import src.agents.technical as tech_mod
from src.config import texto_de_respuesta_llm


class _RespuestaConBloques:
    """Lo que devuelven los proveedores que responden con bloques de contenido."""

    content = [
        {"type": "text", "text": "Primera frase del dictamen."},
        {"type": "text", "text": "Segunda frase del dictamen."},
    ]


class _RespuestaConCadena:
    content = "Un resumen en texto plano."


class _RespuestaVacia:
    content = []


class _LLMDoble:
    def __init__(self, respuesta):
        self.respuesta = respuesta

    def invoke(self, prompt):  # noqa: ARG002
        return self.respuesta


# --------------------------------------------------------------------------- #
# 1. El helper
# --------------------------------------------------------------------------- #
def test_aplana_la_lista_de_bloques():
    texto = texto_de_respuesta_llm(_RespuestaConBloques())
    assert isinstance(texto, str)
    assert texto == "Primera frase del dictamen.\nSegunda frase del dictamen."


def test_deja_pasar_el_contenido_en_cadena():
    assert texto_de_respuesta_llm(_RespuestaConCadena()) == "Un resumen en texto plano."


def test_acepta_una_cadena_pelada():
    assert texto_de_respuesta_llm("respuesta directa") == "respuesta directa"


def test_ignora_los_bloques_que_no_son_texto():
    """Los bloques de razonamiento o de firma no son el resumen."""
    class _Mixta:
        content = [
            {"type": "thinking", "thinking": "razonamiento interno"},
            {"type": "text", "text": "Lo que sí se publica."},
        ]
    assert texto_de_respuesta_llm(_Mixta()) == "Lo que sí se publica."


@pytest.mark.parametrize("respuesta", [
    _RespuestaVacia(), None, object(), "",
])
def test_sin_texto_utilizable_devuelve_none(respuesta):
    """
    Devuelve None y no cadena vacía a propósito: así el agente conserva su
    resumen determinista en vez de publicar un campo vacío.
    """
    assert texto_de_respuesta_llm(respuesta) is None


# --------------------------------------------------------------------------- #
# 2. Los cinco agentes
# --------------------------------------------------------------------------- #
def _estado_completo():
    """Estado que atraviesa la rama aprobada, con dosier de noticias incluido."""
    tech = {"close": 100.0, "rsi": 60.0, "macd": 1.5, "macd_signal": 1.0, "macd_hist": 0.5,
            "bb_upper": 105.0, "bb_lower": 95.0, "atr": 2.0,
            "sma_50": 95.0, "sma_200": 90.0, "volume_rel": 1.2}
    metricas = {"revenue_growth": 0.20, "net_margin": 0.15, "debt_to_equity": 1.0,
                "roe": 0.30, "pe_ratio": 25.0, "market_cap": 0}
    return {
        "ticker": "TEST",
        "company_name": "Test Corp",
        "passed_fundamental_gatekeeper": True,
        "yfinance_data": {"status": "SUCCESS", "fundamentals": metricas, "technical": tech},
        "reconciliation_data": {"confidence_score": 1.0, "discrepancies": [],
                                "reconciled_metrics": dict(metricas)},
        "fundamental_report": {"metrics": dict(metricas), "summary": "ok",
                               "passed_gatekeeper": True},
        "technical_report": {"momentum_classification": "ALCISTA_FUERTE", "rsi": 60.0},
        "debate_report": {"synthesis": "sintesis previa"},
        "news_data": {
            "status": "SUCCESS", "empresa": "Test Corp", "as_of": "2024-03-15",
            "ventana_dias": 30, "fuentes_ok": ["sec_8k"], "fuentes_fallidas": [],
            "items": [{"titulo": "Test Corp reports fourth quarter results",
                       "url": "https://www.sec.gov/x", "fuente": "SEC EDGAR (8-K)",
                       "fecha": "2024-03-14", "extracto": "", "tipo_fuente": "SEC_8K",
                       "buscadores": ["sec_8k"], "n_corroboraciones": 1,
                       "categoria_forzada": "RESULTADOS"}],
        },
    }


AGENTES = [
    (fund_mod, "FundamentalAnalystAgent", "summary"),
    (tech_mod, "TechnicalAnalystAgent", "summary"),
    (news_mod, "NewsAnalystAgent", "summary"),
    (debate_mod, "DebateUnitAgent", "synthesis"),
    (fm_mod, "FundManagerAgent", "summary"),
]


@pytest.mark.parametrize("modulo,clase,campo", AGENTES,
                         ids=[c for _, c, _ in AGENTES])
def test_el_campo_de_texto_nunca_es_una_lista(modulo, clase, campo):
    """
    Con un proveedor que responde por bloques, el informe debe recibir texto.
    Esta es la regresión concreta: antes salía `[{'type': 'text', ...}]`.
    """
    original = modulo.get_llm
    try:
        modulo.get_llm = lambda: _LLMDoble(_RespuestaConBloques())
        informe = getattr(modulo, clase)().analyze(_estado_completo())
    finally:
        modulo.get_llm = original

    assert isinstance(informe[campo], str), f"{clase} publicó un {type(informe[campo])}"
    assert informe[campo] == "Primera frase del dictamen.\nSegunda frase del dictamen."


@pytest.mark.parametrize("modulo,clase,campo", AGENTES,
                         ids=[c for _, c, _ in AGENTES])
def test_respuesta_vacia_conserva_el_texto_determinista(modulo, clase, campo):
    """Si el LLM no devuelve nada utilizable, no se pierde el resumen calculado."""
    original = modulo.get_llm
    try:
        modulo.get_llm = lambda: None
        determinista = getattr(modulo, clase)().analyze(_estado_completo())[campo]

        modulo.get_llm = lambda: _LLMDoble(_RespuestaVacia())
        con_llm_vacio = getattr(modulo, clase)().analyze(_estado_completo())[campo]
    finally:
        modulo.get_llm = original

    assert con_llm_vacio == determinista
    assert con_llm_vacio  # no es cadena vacía


@pytest.mark.parametrize("modulo,clase,campo", AGENTES,
                         ids=[c for _, c, _ in AGENTES])
def test_el_fallo_del_llm_no_rompe_al_agente(modulo, clase, campo):
    """Una excepción del proveedor degrada al motor determinista, no propaga."""
    class _LLMQueFalla:
        def invoke(self, prompt):  # noqa: ARG002
            raise RuntimeError("503 del proveedor")

    original = modulo.get_llm
    try:
        modulo.get_llm = lambda: None
        determinista = getattr(modulo, clase)().analyze(_estado_completo())[campo]

        modulo.get_llm = lambda: _LLMQueFalla()
        tras_el_fallo = getattr(modulo, clase)().analyze(_estado_completo())[campo]
    finally:
        modulo.get_llm = original

    assert tras_el_fallo == determinista
