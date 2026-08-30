"""
Agente Analista Técnico de Momentum.

Los cinco bloques de la puntuación viven ahora en `src/tools/tecnico.py`,
invocables uno a uno. Este módulo es el agente: los llama en orden, suma sus
aportaciones y corta el resultado en una etiqueta.

POR QUÉ EL CLASIFICADOR ES UNA PUNTUACIÓN CONTINUA
--------------------------------------------------
El sistema anterior sumaba puntos enteros alcistas y bajistas y los mapeaba a
cuatro etiquetas con una cadena de `if`. Enumerando sus 72 estados alcanzables
aparecieron tres patologías, todas verificadas contra el informe real del
2026-08-21:

1. ZONA MUERTA. NEM cotizaba a 127.64 con RSI de 83.91 —sobrecompra extrema— y
   salía NEUTRAL. El motivo: `SMA50 (100.76) < SMA200 (105.82)` sumaba 2 puntos
   bajistas por «cruce de la muerte», pese a que el precio estaba un 27% POR
   ENCIMA de ambas medias. El cruce era el retardo aritmético de dos medias
   móviles tras un desplome anterior, no una tendencia bajista vigente. Con 3
   puntos alcistas y 3 bajistas, ninguna rama se activaba y caía en el `else`.

2. NO MONOTONÍA. Con 4 puntos alcistas, pasar de 3 a 4 bajistas cambiaba la
   etiqueta de NEUTRAL a BAJISTA; pero con 5 alcistas el bajismo se ignoraba por
   completo, así que (5 alcistas, 4 bajistas) daba ALCISTA_FUERTE mientras
   (4, 4) daba BAJISTA. Más fuerza alcista podía empeorar la etiqueta.

3. RSI SIN ESCALA. Un RSI de 70.1 y uno de 95.0 restaban exactamente lo mismo.

La sustitución es una puntuación CONTINUA en [-100, +100] construida como suma
ponderada de cinco bloques. Es monótona por construcción: cualquier componente
que mejore no puede empeorar la etiqueta. Las etiquetas se conservan para no
romper el contrato con `fund_manager` y con la capa de backtest, pero ahora son
cortes sobre un número, no el resultado de una escalera de condicionales.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import (
    RSI_SOBRECOMPRA_EXTREMA,
    get_llm,  # noqa: F401  — resuelto por módulo; ver AgenteBase._obtener_llm
    texto_de_respuesta_llm,  # noqa: F401
)
from src.prompts import SYSTEM_TECNICO, prompt_tecnico
from src.state import FinancialAnalysisState
from src.tools.tecnico import (
    PESO_BOLLINGER,
    PESO_MACD,
    PESO_MOMENTUM_PRECIO,
    PESO_RSI,
    PESO_TENDENCIA,
    _etiqueta,
)


class TechnicalAnalystAgent(AgenteBase):
    """Evalúa impulso de precio, estructura de tendencia y sobreextensión."""

    nombre = "tecnico"
    rol = "Analista Técnico de Momentum"
    system_prompt = SYSTEM_TECNICO

    # `tests/test_momentum.py` invoca este corte directamente sobre la clase para
    # comprobar su monotonía. Se conserva como delegación de una línea: la
    # implementación única está en la tool.
    _etiqueta = staticmethod(_etiqueta)

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        raw_tech = state.get("yfinance_data", {}).get("technical", {}) or {}
        precios = state.get("yfinance_data", {}).get("price_history_summary", {}) or {}
        benchmark = state.get("benchmark_data", {}) or {}

        close = raw_tech.get("close", 0.0) or 0.0
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
        pendiente_50 = raw_tech.get("pendiente_sma_50", 0.0)
        dist_200 = raw_tech.get("dist_sma_200_pct", 0.0)
        dist_50 = raw_tech.get("dist_sma_50_pct", 0.0)
        posicion_52w = raw_tech.get("posicion_rango_52w", 0.5)
        volatilidad = raw_tech.get("volatilidad_anual", 0.0)

        signals: List[str] = []
        contribuciones: Dict[str, float] = {}

        # El ORDEN de estas cinco llamadas fija el orden de `contribuciones` y de
        # `signals`, que el informe imprime tal cual. No es intercambiable.

        # ---------------- 1. Estructura de tendencia ----------------------
        t = self.usar_tool("evaluar_tendencia", {
            "close": close, "sma_50": sma_50, "sma_200": sma_200,
            "pendiente_sma_50": pendiente_50, "dist_sma_200_pct": dist_200,
        }, traza)
        contribuciones["tendencia"] = t["aporte"]
        signals.append(t["texto"])
        estado_tendencia = t["estado"]

        # ---------------- 2. MACD -----------------------------------------
        m = self.usar_tool("evaluar_macd", {"macd_hist": macd_hist, "atr": atr}, traza)
        contribuciones["macd"] = m["aporte"]
        signals.append(m["texto"])

        # ---------------- 3. RSI ------------------------------------------
        r = self.usar_tool("evaluar_rsi", {"rsi": rsi}, traza)
        contribuciones["rsi"] = r["aporte"]
        signals.append(r["texto"])
        rsi_estado = r["estado"]

        # ---------------- 4. Bandas de Bollinger --------------------------
        b = self.usar_tool("evaluar_bollinger", {
            "close": close, "bb_upper": bb_upper, "bb_lower": bb_lower,
        }, traza)
        contribuciones["bollinger"] = b["aporte"]
        signals.append(b["texto"])

        # ---------------- 5. Momentum de precio ---------------------------
        mp = self.usar_tool("evaluar_momentum_precio", {
            "precios": precios, "benchmark": benchmark,
        }, traza)
        contribuciones["momentum_precio"] = mp["aporte"]
        signals.append(mp["texto"])
        momentum_relativo = mp["momentum_relativo_12m"]

        score = round(sum(contribuciones.values()), 2)
        clasificacion = self.usar_tool("clasificar_momentum", {"puntuacion": score}, traza)
        momentum = clasificacion["clasificacion"]

        # Aviso de sobreextensión: no altera la etiqueta —el momentum es lo que
        # es— pero el Fund Manager lo usa para recortar tamaño, que es donde
        # debe actuar la prudencia sobre un valor extendido.
        sobreextendido = rsi >= RSI_SOBRECOMPRA_EXTREMA or (dist_200 or 0) > 0.35

        summary = (
            f"Análisis Técnico de {ticker}: Momentum={momentum} (puntuación {score:+.1f}/100), "
            f"RSI={rsi:.1f} ({rsi_estado}), tendencia {estado_tendencia}, "
            f"MACD Hist={macd_hist:+.3f}, ATR=${atr:.2f} ({(atr / close):.1%} del precio) "
            f"si el precio es {close:.2f}. Señales: {'; '.join(signals)}."
            if close else
            f"Análisis Técnico de {ticker}: datos de precio insuficientes."
        )

        return {
            "momentum_classification": momentum,
            "momentum_score": score,
            "contribuciones": contribuciones,
            "close": close,
            "rsi": rsi,
            "rsi_estado": rsi_estado,
            "estado_tendencia": estado_tendencia,
            "sobreextendido": sobreextendido,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "atr": atr,
            "atr_pct": round(atr / close, 4) if close else None,
            "volatilidad_anual": volatilidad,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "sma_50": sma_50,
            "sma_200": sma_200,
            "dist_sma_50_pct": dist_50,
            "dist_sma_200_pct": dist_200,
            "posicion_rango_52w": posicion_52w,
            "volume_rel": vol_rel,
            "momentum_relativo_12m": momentum_relativo,
            "signals": signals,
            "resumen_determinista": summary,
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_tecnico(state.get("ticker", "UNKNOWN"), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        return (f"momentum {informe.get('momentum_classification')} "
                f"({informe.get('momentum_score'):+.1f}/100)")
