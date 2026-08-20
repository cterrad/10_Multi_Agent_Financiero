from typing import Dict, Any
from src.config import get_llm
from src.state import FinancialAnalysisState

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

        # 1. Tesis Bullish (Alcista)
        bullish_arguments = [
            f"Excelente crecimiento de ingresos ({rev_growth:.1%}) demostrando expansión de mercado.",
            f"Margen neto sólido del {net_margin:.1%}, garantizando rentabilidad y generación de caja.",
            f"Estructura técnica con clasificación {momentum} y RSI de {rsi:.1f} en zona de fuerte impulso."
        ]
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

        bearish_case = f"TESIS BAJISTA ({ticker}): " + " ".join(bearish_arguments)

        # 3. Síntesis del Debate
        synthesis = (
            f"DEBATE BALANCEADO: La empresa presenta fundamentos sólidos (Crecimiento {rev_growth:.1%}, Margen {net_margin:.1%}), "
            f"pero enfrenta los siguientes factores de riesgo destacados por el analista bajista: {bearish_arguments[0]}."
        )

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Realiza la síntesis de un debate de inversión sobre {ticker}:\n"
                    f"- Argumentos Alcistas: {bullish_case}\n"
                    f"- Argumentos Bajistas: {bearish_case}\n"
                    f"Escribe una conclusión imparcial de 3 frases ponderando ambas posturas."
                )
                llm_res = llm.invoke(prompt)
                if hasattr(llm_res, 'content'):
                    synthesis = llm_res.content
                elif isinstance(llm_res, str):
                    synthesis = llm_res
            except Exception as e:
                print(f"[DebateUnit] Error LLM: {e}")

        return {
            "bullish_case": bullish_case,
            "bearish_case": bearish_case,
            "synthesis": synthesis
        }
