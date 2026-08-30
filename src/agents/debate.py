"""
Capa de Debate y Mitigación de Sesgos.

QUÉ SE ARREGLA AQUÍ
-------------------
La tesis alcista se construía con una lista fija de tres frases, y la tercera
era literal:

    f"Estructura técnica con clasificación {momentum} y RSI de {rsi:.1f} "
    f"en zona de fuerte impulso."

«En zona de fuerte impulso» se imprimía SIEMPRE, independientemente del valor
del RSI. En el informe del 2026-08-21 apareció en DOCN (RSI 47.7), BE (48.6) y
GOOGL (39.3) —los tres en zona neutral o débil— acompañando además a la
clasificación «NEUTRAL» en la misma frase. El texto contradecía al dato que él
mismo citaba, y el LLM aguas abajo amplificaba la contradicción porque recibía
esa frase como insumo.

Lo mismo ocurría con las tres primeras: «Excelente crecimiento de ingresos» se
afirmaba con cualquier cifra, incluida una negativa.

Ahora cada argumento tiene una CONDICIÓN de activación y un calificativo
derivado del propio número. Si no hay nada que decir en una dirección, no se
dice: un debate honesto puede ser asimétrico, y forzar tres puntos por bando
fabrica argumentos que no existen.

La construcción de ambas tesis vive en `src/tools/debate.py`, como las tools
`construir_tesis_alcista`, `construir_tesis_bajista` y
`condiciones_de_invalidacion`. Aquí queda lo propio del agente: enfrentarlas,
incorporar el argumento de noticias al bando que corresponda y sintetizar.

El Analista de Noticias sigue siendo capa ASESORA: aporta un argumento y nada
más. No toca `rating` ni `position_size_pct`, y
`test_news_report_does_not_alter_decision` protege esa premisa porque de ella
depende la validez del backtest.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    SECTOR_DESCONOCIDO,
    get_llm,  # noqa: F401  — resuelto por módulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_DEBATE, prompt_debate
from src.state import FinancialAnalysisState
from src.tools.debate import (  # noqa: F401  — contrato público del agente
    _argumento_de_noticias,
    _calificar,
    _sintesis,
)


class DebateUnitAgent(AgenteBase):
    """
    Debate entre el investigador alcista y el bajista (abogado del diablo).

    Ambas tesis se construyen con argumentos condicionados a los datos. La
    síntesis determinista pondera las dos y declara qué tendría que ocurrir
    para invalidar la posición.
    """

    nombre = "debate"
    rol = "Unidad de Debate"
    system_prompt = SYSTEM_DEBATE
    # Único agente cuyo campo de texto no se llama `summary`.
    campo_texto = "synthesis"

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        fund = state.get("fundamental_report", {}) or {}
        tech = state.get("technical_report", {}) or {}
        quality = state.get("quality_report", {}) or {}
        rec = state.get("reconciliation_data", {}) or {}
        metrics = fund.get("metrics", {}) or {}

        news = state.get("news_report", {}) or {}
        news_frase = _argumento_de_noticias(news)
        news_direccion = news.get("direction_classification")

        alcistas = self.usar_tool("construir_tesis_alcista", {
            "metricas": metrics, "tecnico": tech,
            "calidad": quality, "sector": sector}, traza)
        bajistas = self.usar_tool("construir_tesis_bajista", {
            "metricas": metrics, "tecnico": tech, "calidad": quality,
            "reconciliacion": rec, "sector": sector}, traza)

        # El argumento de noticias se suma al bando que su dirección indique.
        # Es lo ÚNICO que la capa de noticias aporta al debate, y no altera
        # ninguna cifra: entra como una frase más.
        if news_frase and news_direccion == "ALCISTA":
            alcistas.append(news_frase)
        if news_frase and news_direccion == "BAJISTA":
            bajistas.append(news_frase)

        if not alcistas:
            alcistas.append(
                "Sin argumentos alcistas sustentados en los datos disponibles. La ausencia de "
                "tesis positiva es en sí misma información: no se fabrica un argumento para "
                "equilibrar el debate.")
        if not bajistas:
            bajistas.append(
                "Sin banderas rojas identificadas en los datos disponibles. Riesgo residual de "
                "desaceleración macroeconómica sectorial y de compresión de múltiplos.")

        bullish_case = f"TESIS ALCISTA ({ticker}): " + " ".join(alcistas)
        bearish_case = f"TESIS BAJISTA ({ticker}): " + " ".join(bajistas)

        invalidacion = self.usar_tool("condiciones_de_invalidacion", {
            "calidad": quality, "tecnico": tech, "metricas": metrics}, traza)

        synthesis = _sintesis(ticker, quality, tech, alcistas, bajistas, news_frase)

        return {
            "bullish_case": bullish_case,
            "bearish_case": bearish_case,
            "argumentos_alcistas": alcistas,
            "argumentos_bajistas": bajistas,
            "n_alcistas": len(alcistas),
            "n_bajistas": len(bajistas),
            "invalidacion": invalidacion,
            "_news_frase": news_frase,
            "resumen_determinista": synthesis,
            "synthesis": synthesis,
        }

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        quality = state.get("quality_report", {}) or {}
        return prompt_debate(
            state.get("ticker", "UNKNOWN"),
            state.get("sector") or SECTOR_DESCONOCIDO,
            quality.get("style_classification", "n/d"),
            informe,
            informe.get("_news_frase"),
        )

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        return (f"síntesis cerrada · {informe.get('n_alcistas')} argumento(s) alcista(s) "
                f"vs {informe.get('n_bajistas')} bajista(s)")
