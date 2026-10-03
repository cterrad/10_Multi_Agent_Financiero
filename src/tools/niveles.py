"""
Tools de estructura de precio: soportes derivados del OHLCV.

QUÉ PROBLEMA RESUELVEN, Y POR QUÉ NO EXISTÍAN
----------------------------------------------
Hasta ahora el `nivel_referencia` del ajuste de entrada tenía **un solo
proveedor**: la cadena de opciones. Los tres candidatos de
`src/tools/decision.py` —`SOPORTE_OI`, `GAMMA_FLIP`, `MAX_PAIN`— salen los tres
de ella, así que su ausencia no degradaba el bloque: lo anulaba. Y como el
histórico de cadenas es de pago, en el backtest la cadena está **siempre**
ausente y el ajuste de entrada era **siempre** `None`. El estudio medía, por
tanto, un sistema sin ajuste de entrada mientras producción sí lo aplicaba.

«¿A qué precio es probable que vuelva el valor?» no es una pregunta que solo
sepa responder una cadena de opciones. Este módulo la responde con OHLCV, que el
anfitrión ya tiene point-in-time, ya cacheado y ya protegido por
`test_no_lookahead_future_prices_do_not_change_past_signal`.

Es la traducción a barra diaria de `add_liquidity` y `_causal_levels` del
repositorio 07 (*Bear Trap*), más el canal inferior de Donchian del 06.

TRES REGLAS QUE NO CONVIENE DESHACER
-------------------------------------
1. **El mínimo EXCLUYE la barra en curso.** Es el `shift(1)` explícito de
   `_causal_levels`. Un mínimo que incluya la sesión de hoy no es un soporte
   previo: es el mínimo de hoy, y usarlo como nivel al que esperar significa
   esperar un precio que ya se ha tocado.
2. **El número redondo NO es candidato.** El repo 07 lo usa con un paso fijo de
   1.0. Medido sobre las 132 fechas de rebalanceo del estudio, el redondo
   ganaba la elección el **65%** de las veces —por construcción es el más
   cercano por debajo— y dejaba la profundidad mediana del nivel en un 0.95%
   (0.46 ATR), que es ruido frente a un ATR. Excluyéndolo, la profundidad
   mediana sube a 2.52% (1.24 ATR) y el nivel lo aportan los mínimos previos, la
   SMA50 y la banda inferior de Bollinger. **Reintroducirlo degenera la
   elección.**
3. **El nivel elegido es el MÁS ALTO por debajo del precio.** Misma regla que
   `_ajustar_entrada`: el retroceso más cercano es el más probable de que se
   rellene, y exigir que esté por debajo del precio es lo que hace
   estructuralmente imposible que este cálculo SUBA la entrada.

LO QUE ESTE MÓDULO **NO** AFIRMA
---------------------------------
Que esperar al nivel mejore el resultado. Medido sobre las 936 señales de compra
del régimen `pit`, con los stops y objetivos del propio Fund Manager y 10 pb de
costes, entrar al nivel **mejora la operación** (expectativa +1.70% frente a
+1.34%, factor de beneficio 1.53 frente a 1.43) y **empeora el valor esperado por
señal** (+0.78% frente a +1.34%), porque lo que la orden no rellena es
precisamente lo que sube: esas señales habrían rendido +3.56% con un **59.6% de
acierto**. Este módulo existe para que el backtest pueda por fin MEDIR esa
disyuntiva, no porque se dé por buena una de las dos ramas.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.config import NIVELES_VENTANAS, SOPORTE_LEJANO_ATR

NO_APLICABLE = "NO_APLICABLE"

# Etiquetas de la estructura. Son cortes sobre la distancia al soporte en
# unidades de ATR, igual que las de momentum son cortes sobre un número: la
# monotonía está garantizada por construcción.
ESTRUCTURA_PEGADO = "PEGADO_AL_SOPORTE"
ESTRUCTURA_APOYADO = "APOYADO"
ESTRUCTURA_HOLGADO = "HOLGADO"
ESTRUCTURA_SIN_REFERENCIA = "SIN_REFERENCIA"


# --------------------------------------------------------------------------- #
# Implementación pura sobre la ventana OHLC
# --------------------------------------------------------------------------- #
def minimos_previos(df: Any, ventanas: Any = NIVELES_VENTANAS) -> Dict[str, Optional[float]]:
    """
    Mínimo de las N barras ANTERIORES a la última, para cada N de `ventanas`.

    Recibe un `DataFrame` con columna `Low` ordenado ascendentemente y ya
    cortado en la fecha de análisis por quien llama —`PriceStore.window()` en el
    backtest, `yf.Ticker.history(period="1y")` en producción—. Este módulo no
    corta nada: la disciplina point-in-time vive en el llamante, y duplicarla
    aquí sería una segunda implementación de la misma selección.

    Devuelve `None` —nunca 0.0— para la ventana que no cabe en la historia
    disponible. Un mínimo de 0.0 se leería como «el valor llegó a valer nada».
    """
    salida: Dict[str, Optional[float]] = {}
    if df is None or "Low" not in getattr(df, "columns", []):
        return {f"minimo_{n}": None for n in ventanas}
    bajos = df["Low"].dropna()
    for n in ventanas:
        clave = f"minimo_{n}"
        if len(bajos) < n + 1:
            salida[clave] = None
            continue
        # `[-(n+1):-1]` excluye la barra en curso: el `shift(1)` del repo 07.
        v = float(bajos.iloc[-(n + 1):-1].min())
        salida[clave] = round(v, 4) if v > 0 else None
    return salida


def _soportes(minimos: Dict[str, Optional[float]], sma_50: Optional[float],
              sma_200: Optional[float], bb_inferior: Optional[float],
              precio: Optional[float]) -> Dict[str, Any]:
    """
    Reúne los candidatos y elige el más alto estrictamente por debajo del precio.

    La SMA50, la SMA200 y la banda inferior de Bollinger **ya las calcula**
    `_add_technical_indicators` sobre esa misma ventana, en producción y en el
    replay. No se recalculan aquí: dos implementaciones del mismo indicador es
    el bug de clase que este proyecto prohíbe.
    """
    candidatos: Dict[str, Optional[float]] = dict(minimos or {})
    candidatos["sma_50"] = sma_50
    candidatos["sma_200"] = sma_200
    candidatos["bb_inferior"] = bb_inferior

    disponibles = {k: float(v) for k, v in candidatos.items() if v is not None and v > 0}
    if not precio or precio <= 0:
        return {"soporte": None, "origen": NO_APLICABLE, "candidatos": candidatos,
                "por_debajo": [], "resistencia": None,
                "motivo": "sin precio de referencia"}

    por_debajo = sorted(((k, v) for k, v in disponibles.items() if v < precio),
                        key=lambda c: -c[1])
    por_encima = sorted(((k, v) for k, v in disponibles.items() if v > precio),
                        key=lambda c: c[1])

    if not por_debajo:
        return {"soporte": None, "origen": NO_APLICABLE, "candidatos": candidatos,
                "por_debajo": [],
                "resistencia": round(por_encima[0][1], 2) if por_encima else None,
                "motivo": ("ningún soporte estructural por debajo del precio: el valor "
                           "cotiza por debajo de todas sus referencias")}

    origen, nivel = por_debajo[0]
    return {
        "soporte": round(nivel, 2),
        "origen": origen,
        "candidatos": {k: (round(v, 2) if v is not None else None)
                       for k, v in candidatos.items()},
        "por_debajo": [{"origen": o, "nivel": round(n, 2)} for o, n in por_debajo],
        "resistencia": round(por_encima[0][1], 2) if por_encima else None,
        "motivo": None,
    }


def _distancia(precio: Optional[float], soporte: Optional[float],
               atr: Optional[float]) -> Dict[str, Any]:
    """
    Distancia al soporte en porcentaje y en unidades de volatilidad.

    En ATR y no solo en porcentaje porque un 3% sobre un valor que se mueve un
    1% diario y sobre otro que se mueve un 4% no describen la misma situación —
    es el mismo motivo por el que el tope del ajuste de entrada está en ATR y no
    en un porcentaje fijo.
    """
    if not precio or precio <= 0 or soporte is None or soporte <= 0:
        return {"distancia_pct": None, "distancia_atr": None,
                "motivo": "sin soporte o sin precio"}
    pct = (precio - soporte) / precio
    atr_val = (precio - soporte) / atr if atr and atr > 0 else None
    return {"distancia_pct": round(pct, 4),
            "distancia_atr": round(atr_val, 3) if atr_val is not None else None,
            "motivo": None if atr_val is not None else "sin ATR: distancia solo en porcentaje"}


def _clasificar(distancia_atr: Optional[float]) -> Dict[str, Any]:
    """
    Etiqueta de estructura y bandera de sobreextensión.

    `soporte_lejano` pertenece a la familia de las banderas que **solo cierran**:
    se une por `or` a `sobreextendido` y prohíbe perseguir el precio, igual que
    hacen el RSI extremo y el techo del canal de open interest. **Nunca habilita
    `PERSEGUIR`.**

    La asociación medida entre distancia al soporte y rentabilidad futura no es
    monótona —a 21 sesiones, el tramo (0.5, 1.0] ATR rindió +2.42% frente a
    +1.41% del tramo pegado al soporte y +1.33% del tramo por encima de 2 ATR—,
    así que la etiqueta describe y solo el extremo superior actúa.
    """
    if distancia_atr is None:
        return {"estructura": ESTRUCTURA_SIN_REFERENCIA, "soporte_lejano": False,
                "motivo": "distancia no calculable: la bandera no se activa"}
    if distancia_atr >= SOPORTE_LEJANO_ATR:
        return {"estructura": ESTRUCTURA_HOLGADO, "soporte_lejano": True,
                "motivo": (f"el soporte más cercano está a {distancia_atr:.2f} ATR "
                           f"(límite {SOPORTE_LEJANO_ATR}): el valor cotiza sin "
                           f"referencia estructural debajo")}
    if distancia_atr <= 0.5:
        return {"estructura": ESTRUCTURA_PEGADO, "soporte_lejano": False, "motivo": None}
    return {"estructura": ESTRUCTURA_APOYADO, "soporte_lejano": False, "motivo": None}


# --------------------------------------------------------------------------- #
# Fachadas @tool — cruzan la frontera JSON
# --------------------------------------------------------------------------- #
@tool("identificar_soportes")
def identificar_soportes(minimos: Dict[str, Optional[float]],
                         precio: float,
                         sma_50: Optional[float] = None,
                         sma_200: Optional[float] = None,
                         bb_inferior: Optional[float] = None) -> Dict[str, Any]:
    """Soportes estructurales derivados del precio, y el más cercano por debajo.

    Reúne los mínimos de las N sesiones anteriores —que excluyen la barra en
    curso, de modo que son extremos PASADOS y no el mínimo de hoy— junto con la
    media de 50, la de 200 y la banda inferior de Bollinger, que ya vienen
    calculadas sobre la misma ventana.

    Elige como referencia el candidato MÁS ALTO estrictamente por debajo del
    precio: es el retroceso más cercano y por tanto el más probable de que se
    rellene. Exigir que esté por debajo es lo que hace estructuralmente
    imposible que un soporte suba el precio de entrada.

    El número redondo NO es candidato. Con un paso fijo ganaba la elección el
    65% de las veces por ser siempre el más cercano, dejando la profundidad
    mediana del nivel en 0.46 ATR — ruido con formato de soporte.

    Devuelve `soporte = None` con su motivo cuando el valor cotiza por debajo de
    todas sus referencias. Nunca un cero: un soporte de 0.0 afirmaría que el
    valor puede caer a nada.
    """
    return _soportes(minimos or {}, sma_50, sma_200, bb_inferior, precio)


@tool("medir_distancia_soporte")
def medir_distancia_soporte(precio: float, soporte: Optional[float],
                            atr: Optional[float] = None) -> Dict[str, Any]:
    """Distancia del precio a su soporte estructural, en porcentaje y en ATR.

    La medida en unidades de volatilidad es la que tiene sentido comparar entre
    valores: un 3% sobre uno que se mueve un 1% al día y sobre otro que se mueve
    un 4% no describen la misma situación.

    Devuelve `None` en ambas medidas cuando falta el soporte o el precio, y solo
    en porcentaje cuando falta el ATR, declarándolo en `motivo`.
    """
    return _distancia(precio, soporte, atr)


@tool("clasificar_estructura")
def clasificar_estructura(distancia_atr: Optional[float]) -> Dict[str, Any]:
    """Etiqueta la posición del precio frente a su soporte y marca la sobreextensión.

    Tres etiquetas por cortes sobre la distancia en ATR: PEGADO_AL_SOPORTE hasta
    media unidad, APOYADO hasta el límite, HOLGADO por encima. Sin distancia
    calculable, SIN_REFERENCIA.

    HOLGADO activa `soporte_lejano`, que pertenece a la familia de banderas que
    SOLO CIERRAN: se une por `or` a la sobreextensión técnica y prohíbe
    perseguir el precio, igual que el RSI extremo. Nunca habilita PERSEGUIR ni
    sube ningún dictamen.
    """
    return _clasificar(distancia_atr)


TOOLS_NIVELES = [
    identificar_soportes,
    medir_distancia_soporte,
    clasificar_estructura,
]


# --------------------------------------------------------------------------- #
# Diferenciacion fraccional (AFML cap. 5)
# --------------------------------------------------------------------------- #
# Una serie de precios es no estacionaria; sus retornos son estacionarios pero
# han perdido toda la memoria. `frac_diff` busca el punto intermedio: el `d`
# minimo que hace estacionaria la serie CONSERVANDO el maximo de memoria.
#
# ENTRA COMO VARIABLE DE UN MODELO Y SOLO ASI. El sistema no tiene ninguna regla
# determinista que consuma un nivel de precio transformado, y anadir una seria
# inventar una regla para justificar una tecnica. Su unico consumidor es
# `src/meta/variables.py`.
#
# EL `d` SE FIJA, NO SE BUSCA. `find_min_ffd` del repositorio 03 necesita el test
# ADF de statsmodels, que esta descartado; y buscar `d` sobre la misma ventana
# que despues se evalua seria un ensayo mas sin contar en el recuento del Sharpe
# deflactado.

def pesos_ffd(d: float, umbral: float = 1e-4, ancho_maximo: int = 512) -> List[float]:
    """
    Pesos de la diferenciacion fraccional de ventana fija.

    La serie de pesos w_k = -w_{k-1} · (d - k + 1)/k decae; se trunca cuando el
    peso cae por debajo de `umbral`, que es lo que la hace de VENTANA FIJA y por
    tanto aplicable en tiempo real: cada punto usa el mismo numero de rezagos, no
    todo el histórico disponible.
    """
    w = [1.0]
    for k in range(1, ancho_maximo):
        siguiente = -w[-1] * (d - k + 1) / k
        if abs(siguiente) < umbral:
            break
        w.append(siguiente)
    return w


def frac_diff_ultimo(serie: List[float], d: float,
                     umbral: float = 1e-4) -> Optional[float]:
    """
    Valor diferenciado fraccionalmente del ULTIMO punto de la serie.

    Solo el ultimo, porque es lo unico que el meta-modelo necesita: la variable
    de la senal de hoy. Calcular la serie entera para tirar todo menos un punto
    seria trabajo desperdiciado en cada uno de los 5.621 estados del replay.

    Devuelve `None` —nunca 0.0— si no hay rezagos suficientes. Un cero seria un
    valor plausible de la propia transformacion y por tanto invisible, que es
    exactamente el defecto que `src/data/magnitudes.py` corrige.
    """
    w = pesos_ffd(d, umbral)
    if serie is None or len(serie) < len(w):
        return None
    ventana = [float(x) for x in serie[-len(w):]]
    if any(x != x for x in ventana):          # NaN
        return None
    # `w` va del rezago 0 hacia atras; la ventana va de antiguo a reciente.
    return float(sum(wi * xi for wi, xi in zip(w, reversed(ventana))))
