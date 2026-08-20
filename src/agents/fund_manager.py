from typing import Dict, Any
from src.config import get_llm
from src.state import FinancialAnalysisState

class FundManagerAgent:
    """
    Agente Director del Fondo (Fund Manager):
    Toma la decisión final de inversión asignando estrictamente una de las 5 categorías:
    1. COMPRA FUERTE (Strong Buy)
    2. COMPRA (Buy)
    3. MANTENER (Hold)
    4. VENTA (Sell)
    5. VENTA FUERTE (Strong Sell)
    Calcula parámetros de gestión de riesgo basados en ATR (Stop-Loss y Take-Profit).
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        passed_gatekeeper = state.get("passed_fundamental_gatekeeper", False)
        fund_report = state.get("fundamental_report", {})
        tech_report = state.get("technical_report", {})
        debate_report = state.get("debate_report", {})
        raw_tech = state.get("yfinance_data", {}).get("technical", {})

        current_price = raw_tech.get("close", 0.0)
        atr = raw_tech.get("atr", current_price * 0.02)
        momentum = tech_report.get("momentum_classification", "NEUTRAL")
        rsi = tech_report.get("rsi", 50.0)

        # Reglas de Decisión
        if not passed_gatekeeper:
            # Si fue rechazado por el Gatekeeper fundamental
            rating = "VENTA"
            if fund_report.get("metrics", {}).get("net_margin", 0.0) < -0.10:
                rating = "VENTA FUERTE"
            
            position_size_pct = "0.0%"
            stop_loss = None
            take_profit = None
            rationale = f"Rechazado en el filtro fundamental inicial. {fund_report.get('summary', '')}"
        else:
            # Si aprobó el filtro fundamental
            if momentum == "ALCISTA_FUERTE" and rsi < 70:
                rating = "COMPRA FUERTE"
                position_size_pct = "8.0% - 10.0%"
            elif momentum in ["ALCISTA_FUERTE", "ALCISTA"]:
                rating = "COMPRA"
                position_size_pct = "4.0% - 7.0%"
            elif momentum == "NEUTRAL":
                rating = "MANTENER"
                position_size_pct = "2.0% - 3.0%"
            elif momentum == "BAJISTA" and rsi > 50:
                rating = "VENTA"
                position_size_pct = "0.0%"
            else:
                rating = "VENTA FUERTE"
                position_size_pct = "0.0%"

            # Cálculo de Stop-Loss y Take-Profit por ATR
            if current_price > 0 and atr > 0:
                stop_loss = round(current_price - (2.0 * atr), 2)
                take_profit = round(current_price + (3.5 * atr), 2)
            else:
                stop_loss = round(current_price * 0.95, 2)
                take_profit = round(current_price * 1.10, 2)

            rationale = (
                f"Fundamentales aprobados con éxito. Momentum técnico classified como {momentum}. "
                f"Síntesis de debate: {debate_report.get('synthesis', '')}"
            )

        summary = (
            f"Dictamen Final ({ticker}): {rating}. "
            f"Tamaño de posición recomendado: {position_size_pct}. "
            f"Precio actual: ${current_price:.2f}, Stop-Loss ATR: ${stop_loss if stop_loss else 'N/A'}, "
            f"Take-Profit ATR: ${take_profit if take_profit else 'N/A'}."
        )

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Como Director de Inversiones del Fondo (Fund Manager), redacta la orden ejecutiva final para {ticker}:\n"
                    f"- Dictamen: {rating}\n"
                    f"- Asignación de Cartera: {position_size_pct}\n"
                    f"- Precio Actual: ${current_price:.2f}\n"
                    f"- Stop-Loss ATR: ${stop_loss}\n"
                    f"- Take-Profit ATR: ${take_profit}\n"
                    f"- Justificación: {rationale}\n"
                    f"Entrega una recomendación profesional y formal en 3 frases."
                )
                llm_res = llm.invoke(prompt)
                if hasattr(llm_res, 'content'):
                    summary = llm_res.content
                elif isinstance(llm_res, str):
                    summary = llm_res
            except Exception as e:
                print(f"[FundManager] Error LLM: {e}")

        return {
            "rating": rating,
            "position_size_pct": position_size_pct,
            "current_price": current_price,
            "stop_loss_atr": stop_loss,
            "take_profit_atr": take_profit,
            "rationale": rationale,
            "summary": summary
        }
