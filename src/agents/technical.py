from typing import Dict, Any
from src.config import get_llm, texto_de_respuesta_llm
from src.state import FinancialAnalysisState

class TechnicalAnalystAgent:
    """
    Agente Analista Técnico (Technical ISA): Evalúa el impulso de precio, tendencia e indicadores de momentum.
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        raw_tech = state.get("yfinance_data", {}).get("technical", {})

        close = raw_tech.get("close", 0.0)
        rsi = raw_tech.get("rsi", 50.0)
        macd = raw_tech.get("macd", 0.0)
        macd_signal = raw_tech.get("macd_signal", 0.0)
        macd_hist = raw_tech.get("macd_hist", 0.0)
        bb_upper = raw_tech.get("bb_upper", close * 1.05)
        bb_lower = raw_tech.get("bb_lower", close * 0.95)
        sma_50 = raw_tech.get("sma_50", close)
        sma_200 = raw_tech.get("sma_200", close)
        atr = raw_tech.get("atr", close * 0.02)
        vol_rel = raw_tech.get("volume_rel", 1.0)

        signals = []
        bullish_points = 0
        bearish_points = 0

        # 1. Evaluación de RSI
        if rsi > 70:
            signals.append("RSI en zona de sobrecompra (>70)")
            bearish_points += 1
        elif 50 <= rsi <= 70:
            signals.append("RSI en zona alcista saludable (50-70)")
            bullish_points += 2
        elif rsi < 30:
            signals.append("RSI en zona de sobreventa (<30)")
            bullish_points += 1  # Oportunidad de rebote
        else:
            signals.append("RSI neutral (30-50)")

        # 2. Evaluación de MACD
        if macd > macd_signal and macd_hist > 0:
            signals.append("MACD con cruce alcista y momentum positivo")
            bullish_points += 2
        elif macd < macd_signal:
            signals.append("MACD con sesgo bajista")
            bearish_points += 2

        # 3. Tendencia SMA (Cruce Dorado vs Muerte)
        if close > sma_50 > sma_200:
            signals.append("Estructura de tendencia alcista fuerte (Precio > SMA50 > SMA200)")
            bullish_points += 2
        elif sma_50 < sma_200:
            signals.append("Cruce de la muerte / Tendencia SMA bajista")
            bearish_points += 2

        # 4. Bandas de Bollinger
        if close >= bb_upper:
            signals.append("Precio tocando la Banda de Bollinger Superior (Ruptura/Expansión)")
            bullish_points += 1
        elif close <= bb_lower:
            signals.append("Precio cerca de la Banda de Bollinger Inferior")
            bearish_points += 1

        # Clasificación del Momentum Técnico
        if bullish_points >= 5:
            momentum = "ALCISTA_FUERTE"
        elif bullish_points >= 3 and bearish_points <= 2:
            momentum = "ALCISTA"
        elif bearish_points >= 4:
            momentum = "BAJISTA"
        else:
            momentum = "NEUTRAL"

        summary = (
            f"Análisis Técnico de {ticker}: Momentum={momentum}, RSI={rsi:.1f}, "
            f"MACD Hist={macd_hist:.3f}, ATR=${atr:.2f}. Señales: {'; '.join(signals)}."
        )

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Como Analista Técnico especialista en Momentum, evalúa {ticker}:\n"
                    f"- Precio: ${close:.2f}\n"
                    f"- RSI: {rsi:.1f}\n"
                    f"- MACD: {macd:.3f} (Signal: {macd_signal:.3f})\n"
                    f"- Clasificación Momentum: {momentum}\n"
                    f"Sintetiza la estructura técnica en 2 oraciones."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    summary = texto
            except Exception as e:
                print(f"[TechnicalAgent] Error LLM: {e}")

        return {
            "momentum_classification": momentum,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "atr": atr,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "signals": signals,
            "summary": summary
        }
