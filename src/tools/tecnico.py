"""
Tools del analista técnico: los cinco bloques del momentum, invocables.

Los cuerpos vienen extraídos de `TechnicalAnalystAgent` sin una sola
modificación: la puntuación continua en [-100, +100] y su monotonía son
exactamente las de antes. Lo único nuevo es que cada bloque se puede invocar,
inspeccionar y trazar por separado.

Cada tool devuelve `(aporte, texto)` en forma de diccionario para que el
`ToolMessage` conserve las dos cosas que el informe necesita: cuánto sumó el
bloque a la puntuación y por qué.
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

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
)


# Pesos de los cinco bloques. Suman 100 para que `momentum_score` se lea como
# porcentaje de convicción direccional.
PESO_TENDENCIA = 30.0
PESO_MACD = 20.0
PESO_RSI = 20.0
PESO_BOLLINGER = 10.0
PESO_MOMENTUM_PRECIO = 20.0


def _acotar(x: float, minimo: float = -1.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, x))


# ------------------------------------------------------------------ #
def _tendencia(close: float, sma_50: float, sma_200: float,
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

def _rsi(rsi: float):
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

def _bollinger(close: float, bb_upper: float, bb_lower: float):
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

def _momentum_precio(precios: Dict[str, Any], benchmark: Dict[str, Any]):
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


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #
# Los cinco bloques ya trabajan con tipos serializables, así que aquí la
# conversión es trivial: solo se da nombre y forma de diccionario al par
# (aporte, texto) que devuelven, y se aplica el peso del bloque.


@tool("evaluar_tendencia")
def evaluar_tendencia(close: float, sma_50: float, sma_200: float,
                      pendiente_sma_50: float, dist_sma_200_pct: float) -> Dict[str, Any]:
    """Estructura de tendencia, corregida por el retardo de las medias móviles.

    El cruce SMA50/SMA200 mira 200 sesiones atrás. Tras un desplome seguido de
    una recuperación fuerte, la SMA50 puede seguir por debajo de la SMA200
    durante meses mientras el precio ya cotiza muy por encima de ambas; leerlo
    como tendencia bajista invierte el signo de la señal justo en los valores
    con más impulso. Cuando el precio supera la SMA200 por encima del umbral y
    la SMA50 sube, se declara RECUPERACION y puntúa en positivo.

    Pesa 30 puntos sobre 100 de la puntuación de momentum.
    """
    norm, texto, estado = _tendencia(close, sma_50, sma_200, pendiente_sma_50, dist_sma_200_pct)
    return {"normalizado": norm, "aporte": round(PESO_TENDENCIA * norm, 2),
            "estado": estado, "texto": texto, "peso": PESO_TENDENCIA}


@tool("evaluar_macd")
def evaluar_macd(macd_hist: float, atr: float) -> Dict[str, Any]:
    """Convergencia/divergencia de medias, normalizada por el ATR.

    Un histograma de 2.0 significa cosas distintas en una acción de 3 dólares
    que en una de 340: sin normalizar por volatilidad, el bloque puntuaba el
    precio nominal y no el impulso. Se divide por medio ATR y se acota a
    [-1, +1].

    Pesa 20 puntos sobre 100 de la puntuación de momentum.
    """
    norm = 0.0
    if atr and atr > 0:
        norm = _acotar(macd_hist / (0.5 * atr))
    elif macd_hist:
        norm = 1.0 if macd_hist > 0 else -1.0
    texto = (f"MACD {'alcista' if macd_hist > 0 else 'bajista'} "
             f"(histograma {macd_hist:+.3f}, {abs(macd_hist) / atr:.2f} ATR)"
             if atr else f"MACD con histograma {macd_hist:+.3f}")
    return {"normalizado": norm, "aporte": round(PESO_MACD * norm, 2),
            "texto": texto, "peso": PESO_MACD}


@tool("evaluar_rsi")
def evaluar_rsi(rsi: float) -> Dict[str, Any]:
    """RSI en escala continua, con penalización proporcional al exceso.

    Por debajo de 50 el impulso es débil; entre 50 y la sobrecompra es saludable
    y suma; a partir del umbral de sobrecompra resta, y la penalización crece
    con la distancia hasta saturar en la sobrecompra extrema. Un RSI de 83.9 no
    puede puntuar igual que uno de 70.1, que era el defecto del clasificador
    anterior.

    Pesa 20 puntos sobre 100 de la puntuación de momentum.
    """
    norm, texto, estado = _rsi(rsi)
    return {"normalizado": norm, "aporte": round(PESO_RSI * norm, 2),
            "estado": estado, "texto": texto, "peso": PESO_RSI}


@tool("evaluar_bollinger")
def evaluar_bollinger(close: float, bb_upper: float, bb_lower: float) -> Dict[str, Any]:
    """Posición del precio dentro del canal de Bollinger.

    Escala continua de -1 (banda inferior) a +1 (banda superior). En la banda
    superior la lectura es ambigua a propósito —ruptura o agotamiento— y por eso
    este bloque pesa la mitad que los demás.

    Pesa 10 puntos sobre 100 de la puntuación de momentum.
    """
    norm, texto = _bollinger(close, bb_upper, bb_lower)
    return {"normalizado": norm, "aporte": round(PESO_BOLLINGER * norm, 2),
            "texto": texto, "peso": PESO_BOLLINGER}


@tool("evaluar_momentum_precio")
def evaluar_momentum_precio(precios: Dict[str, Any],
                            benchmark: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Factor momentum de Jegadeesh-Titman: 12 meses excluyendo el último.

    El mes más reciente muestra reversión a corto plazo y contamina la señal si
    se incluye, así que se excluye. Con datos del índice se puntúa el EXCESO
    sobre el benchmark; sin ellos, la rentabilidad absoluta, y se declara la
    limitación. Es la única pata con evidencia de sección cruzada de las cinco.

    Pesa 20 puntos sobre 100 de la puntuación de momentum.
    """
    norm, texto, relativo = _momentum_precio(precios, benchmark or {})
    return {"normalizado": norm, "aporte": round(PESO_MOMENTUM_PRECIO * norm, 2),
            "momentum_relativo_12m": relativo, "texto": texto,
            "peso": PESO_MOMENTUM_PRECIO}


@tool("clasificar_momentum")
def clasificar_momentum(puntuacion: float) -> Dict[str, Any]:
    """Corta la puntuación continua en las cinco etiquetas de momentum.

    ALCISTA_FUERTE, ALCISTA, NEUTRAL, BAJISTA, BAJISTA_FUERTE. El corte es
    monótono por construcción: la etiqueta solo puede mejorar si la puntuación
    sube, que es la propiedad que la escalera de condicionales anterior no
    cumplía.
    """
    return {"puntuacion": puntuacion, "clasificacion": _etiqueta(puntuacion),
            "cortes": {"alcista_fuerte": MOMENTUM_ALCISTA_FUERTE,
                       "alcista": MOMENTUM_ALCISTA,
                       "bajista": MOMENTUM_BAJISTA,
                       "bajista_fuerte": MOMENTUM_BAJISTA_FUERTE}}


TOOLS_TECNICO = [
    evaluar_tendencia,
    evaluar_macd,
    evaluar_rsi,
    evaluar_bollinger,
    evaluar_momentum_precio,
    clasificar_momentum,
]
