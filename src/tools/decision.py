"""
Tools de decision del Fund Manager: rating, vetos, niveles y tamano.

La tabla de rating y la regla de dimensionamiento viven aqui, invocables una a
una. Son las variables de decision mas sensibles del sistema —`rating`,
`peso_objetivo`, `stop_loss_atr` y `take_profit_atr`— y por eso conviene que
cada una tenga su propia entrada en la traza: cuando un dictamen sorprende, lo
primero que hay que poder ver es que puntuacion compuesta lo produjo y que veto
lo recorto despues.

REGLA DE RIESGO
---------------
    peso = (riesgo_asumible / distancia_al_stop) x factor_volatilidad

Se fija cuanto patrimonio se esta dispuesto a perder si salta el stop, y el
tamano se deduce. No al reves.

LOS VETOS SOLO BAJAN
--------------------
Ninguna condicion puede mejorar un rating. El sesgo del sistema es hacia no
operar cuando hay dudas, y una regla que subiera el dictamen abriria la puerta
a compensar una bandera roja con un multiplo atractivo.
"""

from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    AJUSTE_MAXIMO_ATR,
    ATR_AJUSTE_POR_ESTILO,
    ATR_MULTIPLO_OBJETIVO,
    ATR_MULTIPLO_STOP,
    HORIZONTE_MINIMO_DIAS,
    PESO_MAXIMO_POSICION,
    PESO_MINIMO_OPERABLE,
    FACTOR_ENTRADA,
    RIESGO_POR_POSICION_PCT,
    UMBRAL_SENAL,
    VOLATILIDAD_OBJETIVO,
)
from langchain_core.tools import tool

# Cortes de la puntuación compuesta (0-100) sobre las cinco categorías. Son la
# tabla de decisión completa del sistema: no hay ninguna otra regla que asigne
# rating.
CORTES_RATING = (
    (72.0, "COMPRA FUERTE"),
    (58.0, "COMPRA"),
    (42.0, "MANTENER"),
    (28.0, "VENTA"),
    (0.0, "VENTA FUERTE"),
)

ESCALERA = ["VENTA FUERTE", "VENTA", "MANTENER", "COMPRA", "COMPRA FUERTE"]

# Peso relativo de fundamental y técnico en la puntuación compuesta. El
# fundamental manda porque el backtest mostró que la capa técnica por sí sola
# no ordena el rendimiento futuro; el técnico modula la entrada.
PESO_FUNDAMENTAL = 0.65
PESO_TECNICO = 0.35

# Convicción supuesta cuando el Analista de Calidad no pudo evaluar. Es
# deliberadamente el punto neutro: sin información no se premia ni se castiga
# la tesis, pero el tamaño sí se recorta por la vía del factor de datos.
CONVICCION_NEUTRA = 50.0


def _bajar(rating: str, escalones: int = 1) -> str:
    i = ESCALERA.index(rating) if rating in ESCALERA else 2
    return ESCALERA[max(0, i - escalones)]


def _tope(rating: str, maximo: str) -> str:
    i = ESCALERA.index(rating) if rating in ESCALERA else 2
    j = ESCALERA.index(maximo)
    return ESCALERA[min(i, j)]


# ------------------------------------------------------------------ #
def _decision_rechazada(ticker: str, fund_report: Dict[str, Any],
                        quality_report: Dict[str, Any], precio: float,
                        estilo: str, banderas: List[str]) -> Dict[str, Any]:
    """
    Rama del gatekeeper rechazado.

    Distingue tres casos que la versión anterior colapsaba en «VENTA»:
    rechazo por deterioro real, rechazo por pérdidas severas y —el que
    faltaba— imposibilidad de evaluar por falta de datos. Emitir VENTA
    contra una empresa de la que no se sabe nada es una afirmación que los
    datos no sustentan; lo correcto es declararse sin opinión.
    """
    estado = fund_report.get("status", "RECHAZADO")
    metrics = fund_report.get("metrics", {}) or {}
    margen = metrics.get("net_margin")

    if estado == "DATOS_INSUFICIENTES":
        rating = "SIN OPINION"
        rationale = (
            f"No se emite dictamen sobre {ticker}: la cobertura de datos es insuficiente para "
            f"evaluar los fundamentales. {fund_report.get('summary', '')} "
            "Ausencia de datos no es evidencia de deterioro; emitir VENTA aquí sería afirmar "
            "algo que ninguna fuente respalda."
        )
    else:
        rating = "VENTA"
        if margen is not None and margen < -0.10:
            rating = "VENTA FUERTE"
        rationale = (f"Rechazado en el filtro fundamental. {fund_report.get('summary', '')}")

    summary = (
        f"Dictamen Final ({ticker}): {rating}. Sin asignación de cartera. "
        f"{rationale}"
    )

    return {
        "rating": rating,
        "position_size_pct": 0.0,
        "position_size_display": "0.00%",
        "peso_objetivo": 0.0,
        "dimensionado": {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0,
                         "display": "0.00%", "motivo": "no supera el filtro fundamental",
                         "factores": {}},
        "current_price": precio,
        "stop_loss_atr": None,
        "take_profit_atr": None,
        "multiplo_stop": None,
        "multiplo_objetivo": None,
        "horizonte_dias": None,
        "perfil_riesgo": {},
        "estilo": estilo,
        "desglose_decision": {"rating_final": rating, "motivo": estado},
        "vetos_aplicados": [f"Gatekeeper: {estado}"],
        "banderas_rojas": banderas,
        "rationale": rationale,
        "resumen_determinista": summary,
        "summary": summary,
    }

# ------------------------------------------------------------------ #
def _dimensionar(rating: str, conviccion: float,
                 distancia_stop_pct: Optional[float], volatilidad: float,
                 confianza_datos: float, n_banderas: int,
                 sobreextendido: bool) -> Dict[str, Any]:
    """
    Peso objetivo de la posición, en tanto por uno de la cartera.

    Cadena de cálculo, cada paso auditable:

      1. Riesgo asumible = presupuesto por posición × escala de convicción.
         Una convicción de 80/100 arriesga el doble que una de 40/100.
      2. Peso base = riesgo asumible / distancia al stop. Si el stop está a
         un 10% y se aceptan perder 75 puntos básicos, el peso es 7.5%.
      3. Factor de volatilidad = volatilidad objetivo / volatilidad real,
         acotado a 1. Iguala la contribución al riesgo entre posiciones.
      4. Descuentos por confianza en los datos, banderas rojas y
         sobreextensión técnica.
      5. Topes duros: máximo por posición y mínimo operable.

    Los ratings que no son de compra devuelven cero: el sistema es solo
    largo, y MANTENER significa no abrir posición nueva.
    """
    factores: Dict[str, Any] = {}

    if rating not in ("COMPRA", "COMPRA FUERTE"):
        return {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0, "display": "0.00%",
                "motivo": f"{rating} no genera asignación en una cartera solo larga",
                "factores": factores}

    # 1. Escala de convicción: lineal entre 40 y 90 de convicción.
    escala_conviccion = max(0.4, min(1.5, (conviccion - 30.0) / 40.0))
    factores["escala_conviccion"] = round(escala_conviccion, 3)
    riesgo_asumible = RIESGO_POR_POSICION_PCT * escala_conviccion
    factores["riesgo_asumible_pct"] = round(riesgo_asumible * 100, 3)

    # 2. Peso por presupuesto de riesgo.
    distancia = distancia_stop_pct if (distancia_stop_pct and distancia_stop_pct > 0.01) else 0.10
    factores["distancia_stop_pct"] = round(distancia, 4)
    peso = riesgo_asumible / distancia
    factores["peso_por_riesgo"] = round(peso, 4)

    # 3. Escalado por volatilidad.
    if volatilidad and volatilidad > 0:
        factor_vol = min(1.0, VOLATILIDAD_OBJETIVO / volatilidad)
    else:
        factor_vol = 1.0
    factores["factor_volatilidad"] = round(factor_vol, 3)
    peso *= factor_vol

    # 4. Descuentos.
    factor_datos = max(0.5, min(1.0, confianza_datos))
    factor_banderas = max(0.4, 1.0 - 0.2 * n_banderas)
    factor_extension = 0.7 if sobreextendido else 1.0
    factores.update({
        "factor_confianza_datos": round(factor_datos, 3),
        "factor_banderas_rojas": round(factor_banderas, 3),
        "factor_sobreextension": factor_extension,
    })
    peso *= factor_datos * factor_banderas * factor_extension

    # 5. Topes.
    peso_final = min(PESO_MAXIMO_POSICION, peso)
    if peso_final < PESO_MINIMO_OPERABLE:
        factores["descartado_por_minimo"] = True
        return {"peso_objetivo": 0.0, "peso_objetivo_pct": 0.0, "display": "0.00%",
                "motivo": (f"peso calculado {peso_final:.2%} por debajo del mínimo operable "
                           f"{PESO_MINIMO_OPERABLE:.2%}: el coste de operar supera la aportación"),
                "factores": factores}

    motivo = (f"riesgo por posición {riesgo_asumible:.2%} sobre un stop al {distancia:.1%}, "
              f"escalado por volatilidad ×{factor_vol:.2f}")
    if peso > PESO_MAXIMO_POSICION:
        motivo += f", limitado por el tope de concentración del {PESO_MAXIMO_POSICION:.0%}"

    return {
        "peso_objetivo": round(peso_final, 4),
        "peso_objetivo_pct": round(peso_final * 100, 2),
        "display": f"{peso_final * 100:.2f}%",
        "motivo": motivo,
        "factores": factores,
    }

# ------------------------------------------------------------------ #
def _perfil_riesgo(precio: float, stop: Optional[float], objetivo: Optional[float],
                   atr: float, horizonte_dias: int, mult_stop: float,
                   mult_objetivo: float) -> Dict[str, Any]:
    """
    Traduce los niveles de ATR a un perfil interpretable.

    El dato que faltaba en el informe: un ratio riesgo/recompensa solo
    significa algo junto a la tasa de acierto que exige para no perder
    dinero —1/(1+R:R)— y al plazo en que se espera que ocurra. Se declara
    además cuántas sesiones necesita el precio, a su ATR actual, para
    recorrer la distancia al objetivo.
    """
    if not precio or stop is None or objetivo is None:
        return {}

    riesgo = precio - stop
    recompensa = objetivo - precio
    if riesgo <= 0:
        return {}

    rr = recompensa / riesgo
    # Recorrido esperado: el ATR es el rango medio diario, así que la
    # distancia al objetivo dividida por el ATR da las sesiones necesarias
    # en un avance direccional puro. Es un suelo optimista, no un pronóstico.
    sesiones_minimas = int(round(recompensa / atr)) if atr > 0 else None

    return {
        "riesgo_por_accion": round(riesgo, 2),
        "recompensa_por_accion": round(recompensa, 2),
        "ratio_riesgo_recompensa": round(rr, 2),
        "tasa_acierto_equilibrio": round(1.0 / (1.0 + rr), 4),
        "riesgo_pct": round(riesgo / precio, 4),
        "recompensa_pct": round(recompensa / precio, 4),
        "atr_pct": round(atr / precio, 4) if precio else None,
        "horizonte_dias": horizonte_dias,
        "horizonte_meses": round(horizonte_dias / 21.0, 1),
        "sesiones_minimas_al_objetivo": max(sesiones_minimas or 0, HORIZONTE_MINIMO_DIAS)
        if sesiones_minimas is not None else None,
        "multiplos_atr": {"stop": mult_stop, "objetivo": mult_objetivo},
        "nota_horizonte": (
            f"Stop y objetivo se evalúan sobre {horizonte_dias} sesiones "
            f"(~{horizonte_dias / 21:.0f} meses). Fuera de ese plazo la posición se revisa, "
            f"no se mantiene por inercia."),
    }

def _justificacion(ticker: str, rating: str, estilo: str, conviccion: Optional[float],
                   momentum: str, momentum_score: Optional[float], vetos: List[str],
                   banderas: List[str], debate: Dict[str, Any]) -> str:
    partes = [
        f"{ticker}: fundamentales aprobados; estilo {estilo} con convicción "
        f"{conviccion if conviccion is not None else 'no evaluable'}/100 y momentum {momentum} "
        f"({momentum_score:+.1f}/100)." if momentum_score is not None else
        f"{ticker}: fundamentales aprobados; estilo {estilo}."
    ]
    if vetos:
        partes.append("Ajustes a la baja aplicados: " + "; ".join(vetos) + ".")
    if banderas:
        partes.append("Banderas rojas vigentes: " + "; ".join(banderas) + ".")
    sintesis = debate.get("synthesis")
    if isinstance(sintesis, str) and sintesis:
        partes.append(f"Síntesis del debate: {sintesis}")
    return " ".join(partes)


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("calcular_rating_compuesto")
def calcular_rating_compuesto(conviccion_fundamental: Optional[float],
                              momentum_score: Optional[float]) -> Dict[str, Any]:
    """Cruza convicción fundamental y momentum en una de las cinco categorías.

    Puntuación compuesta = 0.65 x convicción + 0.35 x momentum normalizado. El
    fundamental manda porque el backtest mostró que la capa técnica por sí sola
    no ordena el rendimiento futuro; el técnico modula la entrada.

    El momentum llega en [-100, +100] y se lleva a [0, 100] antes de ponderar.
    Cuando la convicción no es evaluable se asume el punto neutro (50): sin
    información no se premia ni se castiga la tesis, y el recorte se aplica
    después por la vía del factor de datos en el dimensionamiento.

    Devuelve el rating ANTES de vetos, junto con la puntuación y los cortes
    aplicados, para que el dictamen sea reconstruible.
    """
    conviccion_efectiva = (conviccion_fundamental if conviccion_fundamental is not None
                           else CONVICCION_NEUTRA)
    momentum_norm = ((momentum_score + 100.0) / 2.0) if momentum_score is not None else 50.0
    compuesta = PESO_FUNDAMENTAL * conviccion_efectiva + PESO_TECNICO * momentum_norm
    rating = next(nombre for corte, nombre in CORTES_RATING if compuesta >= corte)
    return {
        "rating_bruto": rating,
        "puntuacion_compuesta": round(compuesta, 1),
        "conviccion_usada": round(conviccion_efectiva, 1),
        "conviccion_evaluable": conviccion_fundamental is not None,
        "momentum_normalizado": round(momentum_norm, 1),
        "peso_fundamental": PESO_FUNDAMENTAL,
        "peso_tecnico": PESO_TECNICO,
        "cortes": {nombre: corte for corte, nombre in CORTES_RATING},
    }


@tool("aplicar_vetos")
def aplicar_vetos(rating_bruto: str, estilo: str, banderas_rojas: List[str],
                  sobreextendido: bool, confianza_datos: float,
                  conviccion_evaluable: bool = True,
                  sesgo_macro_clasificacion: Optional[str] = None,
                  reflexion_desfavorable: bool = False,
                  regimen_clasificacion: Optional[str] = None) -> Dict[str, Any]:
    """Recorta el rating por riesgo. Los vetos SOLO bajan, nunca suben.

    Ocho condiciones, aplicadas en orden: estilo ESPECULATIVA,
    TRAMPA_DE_VALOR o DATOS_INSUFICIENTES topan en MANTENER; dos o más banderas
    rojas bajan un escalón; un valor técnicamente sobreextendido rebaja COMPRA
    FUERTE a COMPRA —por calidad de la entrada, no por la tesis—; y una
    confianza en los datos por debajo del 60% topa en MANTENER; y un
    posicionamiento de futuros fuertemente en contra del sector topa en COMPRA;
    y una memoria de reflexión con expectativa claramente negativa topa en
    MANTENER.

    El veto macro es la UNICA via por la que el bloque de futuros toca el
    dictamen, y solo puede bajarlo. Se apoya en los informes COT de la CFTC, que
    si son reconstruibles point-in-time, a diferencia de la cadena de opciones.

    El veto de reflexion es la unica via por la que la memoria de resultados
    pasados puede cambiar un rating, y tambien solo lo baja. Exige que el
    intervalo de un error tipico de la celda quede entero por debajo de cero
    (ver `src/tools/reflexion.py`): sin esa condicion, cualquier celda con media
    ligeramente negativa dispararia un veto sobre ruido.

    El veto de regimen es la unica via por la que el estres sistemico toca el
    dictamen: PANICO topa en MANTENER y TENSION topa en COMPRA. Es la traduccion
    del filtro anti-cuchillo-cayendo del repositorio 07 — en un regimen de panico
    lo que parece una oportunidad suele ser una capitulacion en curso — al
    vocabulario de vetos de este sistema. Se apoya en la serie de volatilidad
    implicita de ALFRED, que SI es reconstruible point-in-time, a diferencia de la
    cadena de opciones: el estudio mide este veto sobre la ventana entera.

    Que ninguna condición pueda mejorar el dictamen es deliberado: el sesgo del
    sistema es hacia no operar cuando hay dudas, y permitir que un múltiplo
    atractivo compensara una bandera roja invertiría ese sesgo.

    Devuelve el rating final y la lista de vetos aplicados en texto.
    """
    rating = rating_bruto
    vetos: List[str] = []

    if not conviccion_evaluable:
        vetos.append("Convicción fundamental no evaluable: se asume el punto neutro (50) "
                     "y se recorta el tamaño por falta de datos")

    if estilo == "ESPECULATIVA":
        rating = _tope(rating, "MANTENER")
        vetos.append("Estilo ESPECULATIVA: el dictamen no puede superar MANTENER")
    elif estilo == "TRAMPA_DE_VALOR":
        rating = _tope(rating, "MANTENER")
        vetos.append("Estilo TRAMPA_DE_VALOR: barato sin calidad; no puede superar MANTENER")
    elif estilo == "DATOS_INSUFICIENTES":
        rating = _tope(rating, "MANTENER")
        vetos.append("Calidad no evaluable por cobertura de datos: no puede superar MANTENER")

    if len(banderas_rojas) >= 2:
        rating = _bajar(rating)
        vetos.append(f"{len(banderas_rojas)} banderas rojas fundamentales: se baja un escalón")

    if sobreextendido and rating == "COMPRA FUERTE":
        rating = "COMPRA"
        vetos.append("Valor técnicamente sobreextendido: se rebaja COMPRA FUERTE a COMPRA "
                     "por calidad de la entrada, no por la tesis")

    if confianza_datos < 0.6:
        rating = _tope(rating, "MANTENER")
        vetos.append(f"Confianza en los datos de {confianza_datos:.0%}: "
                     f"no puede superar MANTENER")

    if sesgo_macro_clasificacion == "VIENTO_EN_CONTRA_FUERTE":
        rating = _tope(rating, "COMPRA")
        vetos.append("Posicionamiento de futuros fuertemente en contra del sector: "
                     "el dictamen no puede superar COMPRA")

    if reflexion_desfavorable:
        rating = _tope(rating, "MANTENER")
        vetos.append("Memoria de reflexión: las señales con este perfil rindieron por debajo "
                     "del índice de forma consistente; el dictamen no puede superar MANTENER")

    if regimen_clasificacion == "PANICO":
        rating = _tope(rating, "MANTENER")
        vetos.append("Régimen de volatilidad en PANICO: en un episodio de estrés sistémico "
                     "lo que parece una oportunidad suele ser una capitulación en curso; "
                     "el dictamen no puede superar MANTENER")
    elif regimen_clasificacion == "TENSION":
        rating = _tope(rating, "COMPRA")
        vetos.append("Régimen de volatilidad en TENSION: el dictamen no puede superar COMPRA")

    return {"rating": rating, "vetos": vetos, "rating_bruto": rating_bruto}


@tool("calcular_niveles_riesgo")
def calcular_niveles_riesgo(precio: float, atr: float, estilo: str) -> Dict[str, Any]:
    """Stop, objetivo y horizonte, con múltiplos de ATR según el estilo.

    Un valor de CALIDAD_COMPUESTA y uno ESPECULATIVO no admiten el mismo stop ni
    el mismo plazo: aplicar múltiplos únicos a todo hacía que el ratio
    riesgo/recompensa fuera ininterpretable, porque no se sabía a cuántas
    sesiones aplicaba.

    Sin ATR disponible degrada a un stop del 5% y un objetivo del 10%, y lo
    declara en `fuente_niveles`.
    """
    ajuste = ATR_AJUSTE_POR_ESTILO.get(estilo, ATR_AJUSTE_POR_ESTILO["MIXTA"])
    mult_stop = ajuste.get("stop", ATR_MULTIPLO_STOP)
    mult_objetivo = ajuste.get("objetivo", ATR_MULTIPLO_OBJETIVO)
    horizonte_dias = int(ajuste.get("horizonte_dias", 126))

    stop_loss = take_profit = None
    distancia_stop_pct = None
    fuente = "sin_precio"
    if precio > 0 and atr > 0:
        stop_loss = round(precio - mult_stop * atr, 2)
        take_profit = round(precio + mult_objetivo * atr, 2)
        distancia_stop_pct = (precio - stop_loss) / precio
        fuente = "atr"
    elif precio > 0:
        stop_loss = round(precio * 0.95, 2)
        take_profit = round(precio * 1.10, 2)
        distancia_stop_pct = 0.05
        fuente = "porcentaje_fijo"

    return {
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "distancia_stop_pct": distancia_stop_pct,
        "multiplo_stop": mult_stop,
        "multiplo_objetivo": mult_objetivo,
        "horizonte_dias": horizonte_dias,
        "fuente_niveles": fuente,
    }


@tool("dimensionar_posicion")
def dimensionar_posicion(rating: str, conviccion: float,
                         distancia_stop_pct: Optional[float],
                         volatilidad: float, confianza_datos: float,
                         n_banderas: int, sobreextendido: bool) -> Dict[str, Any]:
    """Tamaño de posición como NÚMERO, derivado de un presupuesto de riesgo.

    peso = (riesgo asumible / distancia al stop) x factor de volatilidad, con
    descuentos por confianza de datos, banderas rojas y sobreextensión, acotado
    entre el mínimo operable y el máximo por posición.

    La versión anterior emitía una cadena («2.0% - 3.0%»), y por eso el tamaño no
    se podía sumar, ni escalar por volatilidad, ni presupuestar: una posición del
    3% en un valor con 80% de volatilidad aporta cuatro veces más riesgo que otra
    del 3% con 20%, y el sistema no podía ni expresar esa diferencia.
    """
    return _dimensionar(rating=rating, conviccion=conviccion,
                        distancia_stop_pct=distancia_stop_pct,
                        volatilidad=volatilidad, confianza_datos=confianza_datos,
                        n_banderas=n_banderas, sobreextendido=sobreextendido)


@tool("calcular_perfil_riesgo")
def calcular_perfil_riesgo(precio: float, stop: Optional[float],
                           objetivo: Optional[float], atr: float,
                           horizonte_dias: int, mult_stop: float,
                           mult_objetivo: float) -> Dict[str, Any]:
    """Ratio riesgo/recompensa y tasa de acierto de equilibrio.

    La tasa de equilibrio es la parte que hace operable el ratio: un R:R de 1.75
    exige acertar el 36% de las veces para no perder dinero, y esa cifra dice
    mucho más sobre si la operación tiene sentido que el ratio a secas.
    """
    return _perfil_riesgo(precio, stop, objetivo, atr, horizonte_dias,
                          mult_stop, mult_objetivo)




# ------------------------------------------------------------------ #
# Precio de entrada
# ------------------------------------------------------------------ #
def _ajustar_entrada(precio: float, atr: float,
                     sesgo_macro: Optional[float],
                     sesgo_opciones: Optional[float],
                     momentum_score: Optional[float],
                     soporte_oi: Optional[float] = None,
                     max_pain: Optional[float] = None,
                     gamma_flip: Optional[float] = None,
                     max_pain_operable: bool = False,
                     regimen_gamma: Optional[str] = None,
                     sobreextendido: bool = False,
                     soporte_estructural: Optional[float] = None) -> Dict[str, Any]:
    """
    Confluencia de tres senales -> precio de entrada objetivo.

    PASO 1 - Confluencia. Los tres componentes son el sesgo macro (COT), el de
    la cadena de opciones y el momentum propio del valor. Se promedian y se
    cuenta que fraccion de los DISPONIBLES coincide en signo con la media. Con
    un solo componente no hay confluencia que medir: una senal aislada no es una
    comparacion de tres vias, y fingir que lo es seria justo el defecto que este
    bloque existe para evitar.

    PASO 2 - Sobreextension. Ninguna bandera cambia el signo; todas prohiben
    perseguir el precio. Es el mismo principio que gobierna `aplicar_vetos`.

    PASO 3 - Nivel. Se elige el candidato MAS ALTO por debajo del precio: es el
    retroceso mas cercano y por tanto el mas probable de que se rellene. Tomar
    el mas bajo seria esperar un desplome. Exigir que este por debajo del precio
    es lo que hace estructuralmente imposible que este calculo SUBA la entrada.

    Los candidatos eran TRES y salian los tres de la cadena de opciones, de modo
    que sin cadena no habia nivel y el ajuste era None SIEMPRE — que es
    exactamente lo que ocurre en el backtest, donde el historico de cadenas no es
    reconstruible con fuentes gratuitas. `SOPORTE_ESTRUCTURAL` es el cuarto y sale
    del OHLCV (`src/tools/niveles.py`), que el sistema si tiene point-in-time. Es
    lo que permite que el estudio MIDA por primera vez el ajuste de entrada.
    Con cadena disponible ambos compiten con la misma regla; sin ella, el
    estructural es el unico y el bloque deja de anularse.

    PASO 4 - Ajuste, acotado a `AJUSTE_MAXIMO_ATR` veces el ATR. El tope esta en
    unidades de volatilidad y no en un porcentaje fijo porque un ajuste mas
    profundo que el stop dejaria la entrada objetivo por DEBAJO del propio stop.

    `ajuste_entrada_pct = 0.0` significa "entrar a mercado por confluencia".
    `None` significa "no calculable". No son lo mismo y no deben colapsarse.
    """
    componentes: Dict[str, Optional[float]] = {
        "macro": sesgo_macro,
        "opciones": sesgo_opciones,
        "tecnico": (momentum_score / 100.0) if momentum_score is not None else None,
    }
    disponibles = {k: v for k, v in componentes.items() if v is not None}

    base: Dict[str, Any] = {
        "componentes": {k: (round(v, 4) if v is not None else None)
                        for k, v in componentes.items()},
        "componentes_disponibles": sorted(disponibles),
        "sobreextendido": bool(sobreextendido),
        "regimen_gamma": regimen_gamma,
        "tope_atr": AJUSTE_MAXIMO_ATR,
    }

    def sin_ajuste(motivo: str, **extra: Any) -> Dict[str, Any]:
        return {**base, "entrada_clasificacion": "NO_APLICABLE", "confluencia": None,
                "sesgo_medio": None, "nivel_referencia": None,
                "nivel_origen": "NO_APLICABLE", "ajuste_entrada_pct": None,
                "precio_entrada_objetivo": None, "motivo": motivo, **extra}

    if len(disponibles) < 2:
        return sin_ajuste("menos de dos componentes disponibles: no hay confluencia "
                          "que medir")

    sesgo_medio = round(sum(disponibles.values()) / len(disponibles), 4)
    if sesgo_medio <= 0:
        return sin_ajuste("el sesgo agregado no es alcista: no hay entrada que optimizar",
                          sesgo_medio=sesgo_medio)

    concordes = [v for v in disponibles.values()
                 if (v > 0) == (sesgo_medio > 0) and abs(v) >= UMBRAL_SENAL]
    confluencia = round(len(concordes) / len(disponibles), 4)

    if confluencia >= 1.0 and not sobreextendido:
        clasificacion = "PERSEGUIR"
    elif confluencia >= 0.5:
        clasificacion = "ESCALONAR"
    else:
        clasificacion = "ESPERAR_RETROCESO"

    # Regimen gamma: con los creadores de mercado cortos gamma sus coberturas
    # aceleran el movimiento, asi que el retroceso puede no llegar nunca y
    # esperarlo entero sale caro. No cambia el signo, solo cuanto se espera.
    if regimen_gamma == "ACELERADO" and clasificacion == "ESPERAR_RETROCESO":
        clasificacion = "ESCALONAR"

    candidatos: List[Any] = []
    if soporte_oi is not None and 0 < soporte_oi < precio:
        candidatos.append(("SOPORTE_OI", float(soporte_oi)))
    if gamma_flip is not None and 0 < gamma_flip < precio:
        candidatos.append(("GAMMA_FLIP", float(gamma_flip)))
    if max_pain is not None and max_pain_operable and 0 < max_pain < precio:
        candidatos.append(("MAX_PAIN", float(max_pain)))
    if soporte_estructural is not None and 0 < soporte_estructural < precio:
        candidatos.append(("SOPORTE_ESTRUCTURAL", float(soporte_estructural)))

    if not candidatos or not precio:
        return {**base, "entrada_clasificacion": "NO_APLICABLE",
                "confluencia": confluencia, "sesgo_medio": sesgo_medio,
                "nivel_referencia": None, "nivel_origen": "NO_APLICABLE",
                "ajuste_entrada_pct": None, "precio_entrada_objetivo": None,
                "clasificacion_previa": clasificacion,
                "motivo": ("ningun nivel de referencia por debajo del precio: ni la cadena "
                           "de opciones ni la estructura de precio ofrecen un candidato")}

    nivel_origen, nivel = max(candidatos, key=lambda c: c[1])
    bruto = (nivel - precio) / precio
    tope = -AJUSTE_MAXIMO_ATR * (atr / precio) if (atr and precio) else bruto
    ajuste = max(tope, FACTOR_ENTRADA[clasificacion] * bruto)
    # Blindaje explicito: el ajuste NUNCA puede subir el precio de entrada.
    ajuste = min(0.0, ajuste)

    return {
        **base,
        "entrada_clasificacion": clasificacion,
        "confluencia": confluencia,
        "sesgo_medio": sesgo_medio,
        "nivel_referencia": round(nivel, 2),
        "nivel_origen": nivel_origen,
        "candidatos": [{"origen": o, "nivel": round(n, 2)} for o, n in candidatos],
        "ajuste_bruto_pct": round(bruto, 4),
        "factor": FACTOR_ENTRADA[clasificacion],
        "ajuste_entrada_pct": round(ajuste, 4),
        "precio_entrada_objetivo": round(precio * (1 + ajuste), 2),
        "limitado_por_atr": ajuste <= tope + 1e-9 and tope > bruto,
        "motivo": None,
    }


@tool("ajustar_precio_entrada")
def ajustar_precio_entrada(precio: float, atr: float,
                           sesgo_macro: Optional[float] = None,
                           sesgo_opciones: Optional[float] = None,
                           momentum_score: Optional[float] = None,
                           soporte_oi: Optional[float] = None,
                           max_pain: Optional[float] = None,
                           gamma_flip: Optional[float] = None,
                           max_pain_operable: bool = False,
                           regimen_gamma: Optional[str] = None,
                           sobreextendido: bool = False,
                           soporte_estructural: Optional[float] = None) -> Dict[str, Any]:
    """Precio de entrada objetivo a partir de la confluencia de tres senales.

    Cruza el sesgo macro de posicionamiento en futuros, el sesgo de
    posicionamiento en la cadena de opciones y el momentum propio del valor. Si
    los tres confirman y nada esta sobreextendido se entra a mercado
    (`ajuste_entrada_pct = 0.0`). Si divergen, se exige un retroceso hasta el
    nivel de referencia que marque el open interest, el max pain, el punto de
    inflexion de la exposicion gamma o el soporte estructural del precio.

    El soporte estructural es el cuarto candidato y el unico que NO depende de la
    cadena de opciones, asi que es el unico disponible en el backtest. Sin el, el
    ajuste de entrada era `None` en el 100% de las senales del estudio y la
    logica quedaba sin medir.

    El ajuste SOLO puede bajar el precio de entrada, nunca subirlo, y esta
    acotado a un ATR: uno mas profundo dejaria la entrada objetivo por debajo del
    propio stop. Es el mismo sesgo que rige los vetos, que solo bajan.

    Devuelve `ajuste_entrada_pct = None` —no 0.0— cuando no hay dos componentes
    disponibles o no hay ningun nivel por debajo del precio. `0.0` significa
    "entrar a mercado por confluencia", que es una lectura distinta.

    VARIABLE DE DECISION: su salida alimenta `calcular_niveles_riesgo`, y por esa
    via el stop, el objetivo y el tamano. Queda FUERA de `TOOLS_LECTURA`.
    """
    return _ajustar_entrada(
        precio=precio, atr=atr, sesgo_macro=sesgo_macro, sesgo_opciones=sesgo_opciones,
        momentum_score=momentum_score, soporte_oi=soporte_oi, max_pain=max_pain,
        gamma_flip=gamma_flip, max_pain_operable=max_pain_operable,
        regimen_gamma=regimen_gamma, sobreextendido=sobreextendido,
        soporte_estructural=soporte_estructural)


TOOLS_DECISION = [
    calcular_rating_compuesto,
    aplicar_vetos,
    calcular_niveles_riesgo,
    dimensionar_posicion,
    calcular_perfil_riesgo,
    ajustar_precio_entrada,
]
