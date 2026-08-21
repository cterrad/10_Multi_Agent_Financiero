from typing import Any, Dict, Optional
from src.config import get_llm, texto_de_respuesta_llm
from src.state import FinancialAnalysisState

def _argumento_de_noticias(news_report: Dict[str, Any]) -> Optional[str]:
    """
    Traduce el informe del Analista de Noticias a una frase para el debate.

    Es un ARGUMENTO, no una decisión: la probabilidad y la dirección ya vienen
    calculadas y aquí solo se redactan. Devuelve None cuando no hay noticias,
    y en ese caso el debate produce exactamente el mismo texto que antes de
    existir esta capa — que es lo que mantiene el backtest comparable.
    """
    if not news_report or not news_report.get("n_items"):
        return None

    catalizador = (news_report.get("catalysts") or [{}])[0].get("titular", "")
    return (
        f"Flujo de noticias con probabilidad de impacto "
        f"{news_report.get('impact_classification', 'N/A')} "
        f"({news_report.get('impact_probability', 0.0):.2f}) y sesgo "
        f"{news_report.get('direction_classification', 'N/A')} sobre "
        f"{news_report.get('n_items', 0)} nota(s); principal catalizador: "
        f"\"{catalizador[:120]}\" (capa asesora: no altera el dictamen)."
    )


class DebateUnitAgent:
    """
    Capa de Debate y Mitigación de Sesgos:
    Ejecuta un debate entre el Bullish Researcher y el Bearish Researcher (Abogado del Diablo).
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        fund = state.get("fundamental_report", {})
        tech = state.get("technical_report", {})
        rec = state.get("reconciliation_data", {})
        metrics = fund.get("metrics", {})

        rev_growth = metrics.get("revenue_growth", 0.0)
        net_margin = metrics.get("net_margin", 0.0)
        pe_ratio = metrics.get("pe_ratio", 0.0)
        debt = metrics.get("debt_to_equity", 0.0)

        rsi = tech.get("rsi", 50.0)
        momentum = tech.get("momentum_classification", "NEUTRAL")

        news = state.get("news_report", {}) or {}
        news_frase = _argumento_de_noticias(news)
        news_direccion = news.get("direction_classification")

        # 1. Tesis Bullish (Alcista)
        bullish_arguments = [
            f"Excelente crecimiento de ingresos ({rev_growth:.1%}) demostrando expansión de mercado.",
            f"Margen neto sólido del {net_margin:.1%}, garantizando rentabilidad y generación de caja.",
            f"Estructura técnica con clasificación {momentum} y RSI de {rsi:.1f} en zona de fuerte impulso."
        ]
        if news_frase and news_direccion == "ALCISTA":
            bullish_arguments.append(news_frase)
        bullish_case = f"TESIS ALCISTA ({ticker}): " + " ".join(bullish_arguments)

        # 2. Tesis Bearish (Bajista / Abogado del Diablo)
        bearish_arguments = []
        if pe_ratio > 30:
            bearish_arguments.append(f"Múltiplo P/E elevado ({pe_ratio:.1f}x) que sugiere sobrevaloración.")
        if rsi > 68:
            bearish_arguments.append(f"RSI en nivel elevado ({rsi:.1f}), vulnerable a correcciones de corto plazo.")
        if debt > 1.5:
            bearish_arguments.append(f"Carga financiera moderada/alta con Deuda/Capital en {debt:.2f}.")
        if len(rec.get("discrepancies", [])) > 0:
            bearish_arguments.append("Discrepancias encontradas en la reconciliación multi-fuente de datos.")
        
        if not bearish_arguments:
            bearish_arguments.append("Riesgo de desaceleración macroeconómica sectorial y volatilidad del mercado general.")

        if news_frase and news_direccion == "BAJISTA":
            bearish_arguments.append(news_frase)
        bearish_case = f"TESIS BAJISTA ({ticker}): " + " ".join(bearish_arguments)

        # 3. Síntesis del Debate
        synthesis = (
            f"DEBATE BALANCEADO: La empresa presenta fundamentos sólidos (Crecimiento {rev_growth:.1%}, Margen {net_margin:.1%}), "
            f"pero enfrenta los siguientes factores de riesgo destacados por el analista bajista: {bearish_arguments[0]}."
        )
        if news_frase:
            synthesis += f" Lectura del Analista de Noticias: {news_frase}"

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Realiza la síntesis de un debate de inversión sobre {ticker}:\n"
                    f"- Argumentos Alcistas: {bullish_case}\n"
                    f"- Argumentos Bajistas: {bearish_case}\n"
                    + (f"- Contexto de noticias (asesor): {news_frase}\n" if news_frase else "")
                    + f"Escribe una conclusión imparcial de 3 frases ponderando ambas posturas."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    synthesis = texto
            except Exception as e:
                print(f"[DebateUnit] Error LLM: {e}")

        return {
            "bullish_case": bullish_case,
            "bearish_case": bearish_case,
            "synthesis": synthesis
        }
