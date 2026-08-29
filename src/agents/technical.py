"""
Agente Analista Técnico de Momentum.

POR QUÉ SE REESCRIBIÓ EL CLASIFICADOR
-------------------------------------
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

from src.config import (
    MOMENTUM_ALCISTA,
    MOMENTUM_ALCISTA_FUERTE,
    MOMENTUM_BAJISTA,
    MOMENTUM_BAJISTA_FUERTE,
    RSI_SOBRECOMPRA,
    RSI_SOBRECOMPRA_EXTREMA,
    RSI_SOBREVENTA,
    RSI_SOBREVENTA_EXTREMA,
    UMBRAL_TENDENCIA_RECUPERADA,
    get_llm,
    texto_de_respuesta_llm,
)
from src.state import FinancialAnalysisState

# Pesos de los cinco bloques. Suman 100 para que `momentum_score` se lea como
# porcentaje de convicción direccional.
PESO_TENDENCIA = 30.0
PESO_MACD = 20.0
PESO_RSI = 20.0
PESO_BOLLINGER = 10.0
PESO_MOMENTUM_PRECIO = 20.0


def _acotar(x: float, minimo: float = -1.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, x))


class TechnicalAnalystAgent:
    """Evalúa impulso de precio, estructura de tendencia y sobreextensión."""

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
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

        # ---------------- 1. Estructura de tendencia ----------------------
        tendencia_norm, tendencia_texto, estado_tendencia = self._tendencia(
            close, sma_50, sma_200, pendiente_50, dist_200
        )
        contribuciones["tendencia"] = round(PESO_TENDENCIA * tendencia_norm, 2)
        signals.append(tendencia_texto)

        # ---------------- 2. MACD -----------------------------------------
        # Se normaliza el histograma por el ATR: un histograma de 2.0 significa
        # cosas distintas en una acción de 3$ que en una de 340$. La versión
        # anterior comparaba el signo y nada más.
        macd_norm = 0.0
        if atr and atr > 0:
            macd_norm = _acotar(macd_hist / (0.5 * atr))
        elif macd_hist:
            macd_norm = 1.0 if macd_hist > 0 else -1.0
        contribuciones["macd"] = round(PESO_MACD * macd_norm, 2)
        signals.append(
            f"MACD {'alcista' if macd_hist > 0 else 'bajista'} "
            f"(histograma {macd_hist:+.3f}, {abs(macd_hist) / atr:.2f} ATR)"
            if atr else f"MACD con histograma {macd_hist:+.3f}"
        )

        # ---------------- 3. RSI ------------------------------------------
        rsi_norm, rsi_texto, rsi_estado = self._rsi(rsi)
        contribuciones["rsi"] = round(PESO_RSI * rsi_norm, 2)
        signals.append(rsi_texto)

        # ---------------- 4. Bandas de Bollinger --------------------------
        bb_norm, bb_texto = self._bollinger(close, bb_upper, bb_lower)
        contribuciones["bollinger"] = round(PESO_BOLLINGER * bb_norm, 2)
        signals.append(bb_texto)

        # ---------------- 5. Momentum de precio ---------------------------
        # El factor momentum académico (Jegadeesh-Titman): rentabilidad a 6-12
        # meses excluyendo el último mes. Es la única pata con evidencia de
        # sección cruzada de las cinco, y no estaba en el sistema anterior.
        mom_norm, mom_texto, momentum_relativo = self._momentum_precio(precios, benchmark)
        contribuciones["momentum_precio"] = round(PESO_MOMENTUM_PRECIO * mom_norm, 2)
        signals.append(mom_texto)

        score = round(sum(contribuciones.values()), 2)
        momentum = self._etiqueta(score)

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

        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Como Analista Técnico especialista en Momentum, evalúa {ticker}:\n"
                    f"- Precio: ${close:.2f} (SMA50 ${sma_50}, SMA200 ${sma_200})\n"
                    f"- RSI: {rsi:.1f} — estado: {rsi_estado}\n"
                    f"- Estructura de tendencia: {estado_tendencia}\n"
                    f"- MACD histograma: {macd_hist:+.3f}\n"
                    f"- Puntuación de momentum: {score:+.1f}/100 → {momentum}\n"
                    f"- Posición en el rango de 52 semanas: {posicion_52w:.0%}\n"
                    f"Sintetiza la estructura técnica en 2 oraciones. "
                    f"No afirmes impulso fuerte si el RSI es neutral ni tendencia bajista "
                    f"si el precio cotiza por encima de sus medias."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    summary = texto
            except Exception as e:
                print(f"[TechnicalAgent] Error LLM: {e}")

        return {
            "momentum_classification": momentum,
            "momentum_score": score,
            "contribuciones": contribuciones,
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
            "summary": summary,
        }

    # ------------------------------------------------------------------ #
    def _tendencia(self, close: float, sma_50: float, sma_200: float,
                   pendiente_50: float, dist_200: float):
        """
        Estructura de tendencia, corrigiendo el retardo de las medias móviles.

        El cruce SMA50/SMA200 mira 200 sesiones atrás. Tras un desplome seguido
        de una recuperación fuerte, la SMA50 puede seguir por debajo de la
        SMA200 durante meses mientras el precio ya cotiza muy por encima de
        ambas. Leer eso como «tendencia bajista» —lo que hacía la versión
        anterior— invierte el signo de la señal justo en los valores con más
        impulso. El caso NEM es exactamente ese.

        La regla: cuando el precio supera la SMA200 en más de
        `UMBRAL_TENDENCIA_RECUPERADA` y la SMA50 tiene pendiente positiva, el
        cruce pendiente se declara RECUPERACION y puntúa en positivo, aunque
        con menos peso que una tendencia ya confirmada.
        """
        if not close or not sma_50 or not sma_200:
            return 0.0, "Estructura de tendencia no evaluable (faltan medias móviles)", "NO_EVALUABLE"

        sobre_50 = close > sma_50
        sobre_200 = close > sma_200
        cruce_dorado = sma_50 > sma_200

        if sobre_50 and sobre_200 and cruce_dorado:
            return (1.0,
                    f"Tendencia alcista confirmada: precio {close:.2f} > SMA50 {sma_50:.2f} > SMA200 {sma_200:.2f}",
                    "ALCISTA_CONFIRMADA")

        if not cruce_dorado and sobre_200 and dist_200 > UMBRAL_TENDENCIA_RECUPERADA and pendiente_50 > 0:
            return (0.55,
                    f"Tendencia en recuperación: el precio cotiza un {dist_200:.1%} sobre la SMA200 "
                    f"y la SMA50 sube ({pendiente_50:+.1%} en 20 sesiones); el cruce SMA50<SMA200 "
                    f"es retardo del indicador, no tendencia bajista vigente",
                    "RECUPERACION")

        if sobre_200 and cruce_dorado:
            return (0.5,
                    f"Tendencia alcista de fondo con corrección: precio {close:.2f} por debajo de la "
                    f"SMA50 {sma_50:.2f} pero sobre la SMA200 {sma_200:.2f}",
                    "ALCISTA_EN_CORRECCION")

        if not sobre_200 and not cruce_dorado:
            return (-1.0,
                    f"Tendencia bajista confirmada: precio {close:.2f} < SMA200 {sma_200:.2f} "
                    f"y SMA50 {sma_50:.2f} por debajo de la SMA200",
                    "BAJISTA_CONFIRMADA")

        if not sobre_200:
            return (-0.5,
                    f"Precio por debajo de la SMA200 ({sma_200:.2f}) con cruce aún alcista: "
                    f"tendencia en deterioro",
                    "DETERIORO")

        return (0.2, f"Estructura mixta: precio {close:.2f}, SMA50 {sma_50:.2f}, SMA200 {sma_200:.2f}",
                "MIXTA")

    def _rsi(self, rsi: float):
        """
        RSI en escala continua con penalización proporcional al exceso.

        Tramos: por debajo de 50 el impulso es débil; entre 50 y la sobrecompra
        es saludable y suma; a partir de `RSI_SOBRECOMPRA` empieza a restar, y
        la penalización crece con la distancia hasta saturar en la sobrecompra
        extrema. Un 83.9 no puede leerse igual que un 70.1, que era el defecto
        señalado en la revisión.
        """
        if rsi is None:
            return 0.0, "RSI no disponible", "NO_DISPONIBLE"

        if rsi >= RSI_SOBRECOMPRA_EXTREMA:
            exceso = (rsi - RSI_SOBRECOMPRA_EXTREMA) / max(100.0 - RSI_SOBRECOMPRA_EXTREMA, 1e-6)
            return (-0.6 - 0.4 * _acotar(exceso, 0.0, 1.0),
                    f"RSI en sobrecompra EXTREMA ({rsi:.1f} ≥ {RSI_SOBRECOMPRA_EXTREMA:.0f}): "
                    f"riesgo elevado de reversión a corto plazo",
                    "SOBRECOMPRA_EXTREMA")

        if rsi > RSI_SOBRECOMPRA:
            avance = (rsi - RSI_SOBRECOMPRA) / max(RSI_SOBRECOMPRA_EXTREMA - RSI_SOBRECOMPRA, 1e-6)
            return (-0.6 * avance,
                    f"RSI en sobrecompra ({rsi:.1f} > {RSI_SOBRECOMPRA:.0f})",
                    "SOBRECOMPRA")

        if rsi >= 50:
            avance = (rsi - 50.0) / max(RSI_SOBRECOMPRA - 50.0, 1e-6)
            return (0.4 + 0.6 * avance,
                    f"RSI en zona alcista saludable ({rsi:.1f}, entre 50 y {RSI_SOBRECOMPRA:.0f})",
                    "ALCISTA_SALUDABLE")

        if rsi > RSI_SOBREVENTA:
            # 30-50 es genuinamente neutral: ni impulso ni oportunidad de rebote.
            avance = (rsi - RSI_SOBREVENTA) / max(50.0 - RSI_SOBREVENTA, 1e-6)
            return (-0.3 + 0.3 * avance,
                    f"RSI neutral con sesgo débil ({rsi:.1f}, entre {RSI_SOBREVENTA:.0f} y 50)",
                    "NEUTRAL")

        if rsi > RSI_SOBREVENTA_EXTREMA:
            return (0.15,
                    f"RSI en sobreventa ({rsi:.1f} < {RSI_SOBREVENTA:.0f}): posible rebote técnico",
                    "SOBREVENTA")

        return (0.35,
                f"RSI en sobreventa EXTREMA ({rsi:.1f} ≤ {RSI_SOBREVENTA_EXTREMA:.0f}): "
                f"reversión al alza estadísticamente probable, tendencia de fondo aún negativa",
                "SOBREVENTA_EXTREMA")

    def _bollinger(self, close: float, bb_upper: float, bb_lower: float):
        """Posición dentro del canal, en escala continua de -1 (suelo) a +1 (techo)."""
        if not close or not bb_upper or not bb_lower or bb_upper <= bb_lower:
            return 0.0, "Bandas de Bollinger no evaluables"
        posicion = (close - bb_lower) / (bb_upper - bb_lower)
        norm = _acotar(2.0 * posicion - 1.0)
        if posicion >= 0.95:
            texto = f"Precio en la banda superior de Bollinger (percentil {posicion:.0%} del canal): ruptura o agotamiento"
        elif posicion <= 0.05:
            texto = f"Precio en la banda inferior de Bollinger (percentil {posicion:.0%} del canal)"
        else:
            texto = f"Precio en el {posicion:.0%} del canal de Bollinger"
        return norm, texto

    def _momentum_precio(self, precios: Dict[str, Any], benchmark: Dict[str, Any]):
        """
        Momentum de sección cruzada y fuerza relativa contra el índice.

        Se usa la rentabilidad a 12 meses EXCLUYENDO el último mes, que es la
        definición estándar del factor: el mes más reciente muestra reversión a
        corto plazo y contamina la señal si se incluye.

        Cuando hay datos del benchmark en el estado, se resta su rentabilidad y
        se puntúa el exceso. Sin benchmark, se puntúa la rentabilidad absoluta y
        se declara la limitación en `momentum_relativo`.
        """
        r12 = precios.get("change_12m_pct")
        r1 = precios.get("change_1m_pct")
        if r12 is None:
            return 0.0, "Momentum de precio no evaluable (menos de 12 meses de histórico)", None

        r12_ex1 = (1.0 + r12) / (1.0 + r1) - 1.0 if r1 is not None else r12

        bench_12m = benchmark.get("change_12m_pct")
        if bench_12m is not None:
            exceso = r12_ex1 - bench_12m
            norm = _acotar(exceso / 0.30)
            texto = (f"Momentum 12m (excl. último mes) {r12_ex1:+.1%} frente al "
                     f"{bench_12m:+.1%} de {benchmark.get('ticker', 'el índice')}: "
                     f"exceso {exceso:+.1%}")
            return norm, texto, round(exceso, 4)

        norm = _acotar(r12_ex1 / 0.40)
        return (norm,
                f"Momentum 12m (excl. último mes) {r12_ex1:+.1%}; sin referencia de índice disponible",
                None)

    @staticmethod
    def _etiqueta(score: float) -> str:
        """
        Corte de la puntuación continua en las cuatro etiquetas históricas.

        Monótono por construcción: la etiqueta solo puede mejorar si la
        puntuación sube. Se añade BAJISTA_FUERTE, que el sistema anterior no
        podía expresar aunque el `fund_manager` ya la contemplaba.
        """
        if score >= MOMENTUM_ALCISTA_FUERTE:
            return "ALCISTA_FUERTE"
        if score >= MOMENTUM_ALCISTA:
            return "ALCISTA"
        if score <= MOMENTUM_BAJISTA_FUERTE:
            return "BAJISTA_FUERTE"
        if score <= MOMENTUM_BAJISTA:
            return "BAJISTA"
        return "NEUTRAL"
