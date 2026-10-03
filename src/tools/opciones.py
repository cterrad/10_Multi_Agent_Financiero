"""
Tools de la cadena de opciones del propio ticker.

Que aporta que el bloque macro no puede aportar
-----------------------------------------------
Un z-score de posicionamiento COT da direccion y conviccion, pero no da un
NIVEL DE PRECIO. La cadena si: los strikes con mayor open interest actuan como
soporte y resistencia (McMillan), el max pain es un strike concreto hacia el que
el valor agregado de lo vivo se minimiza al vencimiento, y el punto donde la
exposicion gamma agregada de los creadores de mercado cambia de signo es otro
nivel concreto. De ahi sale el precio de entrada objetivo.

QUE MIDE `clasificar_sesgo_opciones` Y QUE NO
---------------------------------------------
Mide la CALIDAD DEL PRECIO —si este es un buen sitio para comprar—, no la
direccion de la tendencia. De la tendencia ya se encarga el Analista Tecnico, y
confundir las dos cosas fue precisamente el defecto de la primera version:

    El 2026-08-30, con el sistema recien estrenado y por tanto sin historico
    acumulado, el put/call y el skew no votaban (exigian 60 observaciones) y el
    unico componente vivo era `tanh((precio - gamma_flip) / (0.05*precio))`, que
    crece cuanto mas ha subido el valor. El sesgo de opciones era por tanto un
    proxy de momentum que duplicaba la pata tecnica, la confluencia llegaba a
    1.0 sin esfuerzo y el ajuste de entrada salia 0.0 casi siempre. AAPL
    cotizaba en el percentil 98 de su canal de open interest —pegado a la
    resistencia— y recibio PERSEGUIR con entrada a mercado, que es el peor
    precio posible para una compra en largo.

De ahi las dos reglas que gobiernan este modulo:

1. **Todo componente direccional se lee en clave CONTRARIA** y debe estar
   disponible SIN historico siempre que sea posible. La posicion del precio en
   el canal de open interest y el skew normalizado por la volatilidad
   at-the-money cumplen las dos condiciones; los percentiles son la refinacion
   que llega despues.
2. **El punto de inflexion de la gamma es asimetrico.** Por debajo es una
   advertencia real con rango completo; por encima solo dice que el colchon
   queda lejos, y se escala a una fraccion. Su lectura principal no es
   direccional sino de REGIMEN: largos gamma, las coberturas amortiguan y un
   retroceso es probable que se rellene; cortos gamma, aceleran y esperarlo
   sale caro.

EL SIGNO DE LA GAMMA ES UNA CONVENCION, NO UNA MEDICION
--------------------------------------------------------
Se asume que los creadores de mercado estan largos gamma en las calls y cortos
en las puts (el cliente compra proteccion y vende calls cubiertas). Es la
convencion estandar del sector, pero la cadena publica OPEN INTEREST, no quien
esta en cada lado de cada contrato. Si la convencion falla en un valor concreto,
el punto de inflexion apunta al lado contrario. Se declara en el informe y en
`build_limitations()` del backtest.

FORMA CERRADA, NO APROXIMACION
------------------------------
Gamma y delta salen de Black-Scholes (Hull), no de diferencias finitas. Con
`q = 0` declarado: la mayoria del universo reparte dividendos modestos y una
tasa continua estimada por empresa anadiria dispersion sin cambiar el signo de
la gamma, que es lo unico que se usa.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.config import (
    GEX_ASIMETRIA_POSITIVA,
    OPCIONES_CANAL_SOBREEXTENDIDO,
    OPCIONES_MAXPAIN_DIAS_MAXIMO,
    OPCIONES_MINIMO_DIAS_HISTORICO,
    OPCIONES_MULTIPLICADOR,
    OPCIONES_OI_MINIMO_STRIKE,
    PESO_CANAL_OI,
    PESO_GEX,
    PESO_PCR,
    PESO_SKEW,
    SKEW_ESCALA,
    TIPO_LIBRE_RIESGO,
)

NO_APLICABLE = "NO_APLICABLE"
DATOS_INSUFICIENTES = "DATOS_INSUFICIENTES"

# Rango y resolucion del barrido para localizar el punto de inflexion de la
# gamma. +-20% cubre cualquier retroceso operable sin extrapolar la cadena a
# zonas donde no hay strikes cotizados.
FLIP_RANGO = 0.20
FLIP_PASOS = 201


# --------------------------------------------------------------------------- #
# Black-Scholes (Hull)
# --------------------------------------------------------------------------- #
def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _d1(s: float, k: float, t: float, r: float, sigma: float) -> float:
    return (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))


def gamma_bs(s: float, k: float, t: float, sigma: float,
             r: float = TIPO_LIBRE_RIESGO) -> Optional[float]:
    """Gamma de Black-Scholes. `None` cuando el contrato no es valorable."""
    if not s or not k or t <= 0 or not sigma or sigma <= 0:
        return None
    return _pdf(_d1(s, k, t, r, sigma)) / (s * sigma * math.sqrt(t))


def delta_bs(s: float, k: float, t: float, sigma: float, tipo: str,
             r: float = TIPO_LIBRE_RIESGO) -> Optional[float]:
    """Delta de Black-Scholes con `q = 0`. Se publica para auditar la cadena."""
    if not s or not k or t <= 0 or not sigma or sigma <= 0:
        return None
    d1 = _d1(s, k, t, r, sigma)
    return _cdf(d1) if tipo == "call" else _cdf(d1) - 1.0


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #
def _percentil(valor: Optional[float], muestra: List[float],
               minimo: int = OPCIONES_MINIMO_DIAS_HISTORICO) -> Optional[float]:
    """
    Posicion del valor en su propia distribucion historica.

    Devuelve `None` —nunca 0.5— cuando la muestra no llega al minimo. Un 0.5 se
    leeria como "en su nivel habitual", que es una afirmacion, y aqui no hay
    ninguna: solo faltan observaciones. Es el mismo criterio que
    `COBERTURA_MINIMA_ESTILO` aplica al clasificador de estilo.
    """
    limpia = [m for m in muestra if m is not None]
    if valor is None or len(limpia) < minimo:
        return None
    menores = sum(1 for m in limpia if m <= valor)
    return round(menores / len(limpia), 4)


def _ratio(numerador: Optional[float], denominador: Optional[float]) -> Optional[float]:
    if numerador is None or not denominador:
        return None
    return round(numerador / denominador, 4)


def _series_historicas(historico: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Reconstruye las series de put/call y skew de los agregados cacheados."""
    pcr_oi, pcr_vol, skew = [], [], []
    for fila in historico or []:
        r = _ratio(fila.get("oi_puts"), fila.get("oi_calls"))
        if r is not None:
            pcr_oi.append(r)
        rv = _ratio(fila.get("vol_puts"), fila.get("vol_calls"))
        if rv is not None:
            pcr_vol.append(rv)
        ivp, ivc = fila.get("iv_put_otm"), fila.get("iv_call_otm")
        if ivp is not None and ivc is not None:
            skew.append(round(ivp - ivc, 6))
    return {"pcr_oi": pcr_oi, "pcr_volumen": pcr_vol, "skew": skew}


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("calcular_put_call_ratio")
def calcular_put_call_ratio(agregados: Dict[str, Any],
                            historico: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Put/call ratio por open interest y por volumen, con su percentil historico.

    El NIVEL absoluto de un put/call no informa: 0.8 es alto en un valor y bajo
    en otro. Lo que informa es el percentil frente al historico del propio valor,
    leido en clave contraria: percentil alto significa mas cobertura de lo
    habitual (miedo) y es apoyo alcista; percentil bajo es complacencia.

    El percentil se calcula sobre la cache acumulativa de cadenas diarias. Por
    debajo del minimo de observaciones devuelve `None` y estado
    DATOS_INSUFICIENTES, nunca el percentil 50: una instalacion nueva tarda
    meses en poder emitir esta lectura y disimularlo seria inventar una senal.
    """
    pcr_oi = _ratio(agregados.get("oi_puts"), agregados.get("oi_calls"))
    pcr_vol = _ratio(agregados.get("vol_puts"), agregados.get("vol_calls"))
    series = _series_historicas(historico)
    pct = _percentil(pcr_oi, series["pcr_oi"])

    return {
        "pcr_oi": pcr_oi,
        "pcr_volumen": pcr_vol,
        "percentil_pcr": pct,
        "n_dias_historico": len(series["pcr_oi"]),
        "minimo_dias_historico": OPCIONES_MINIMO_DIAS_HISTORICO,
        "status": "SUCCESS" if pct is not None else DATOS_INSUFICIENTES,
        "lectura": ("miedo por encima de lo habitual" if pct is not None and pct >= 0.8 else
                    "complacencia" if pct is not None and pct <= 0.2 else
                    "en su rango habitual" if pct is not None else
                    "sin historico suficiente para situarlo en su distribucion"),
    }


@tool("identificar_niveles_oi")
def identificar_niveles_oi(contratos: List[Dict[str, Any]],
                           spot: Optional[float]) -> Dict[str, Any]:
    """Soporte y resistencia por concentracion de open interest (McMillan).

    El strike con mayor open interest de PUTS por debajo del precio actua como
    soporte —quien vendio esas puts se cubre comprando si el precio se acerca— y
    el de mayor open interest de CALLS por encima actua como resistencia.

    Se descartan los strikes por debajo del open interest minimo: un strike con
    doce contratos no sostiene ningun precio, y elegirlo produciria un nivel de
    entrada apoyado en ruido.

    Devuelve `None` en el nivel que no tenga ningun strike valido. Nunca el
    precio actual como sustituto.
    """
    if not spot or not contratos:
        return {"soporte_oi": None, "resistencia_oi": None, "oi_por_strike": [],
                "status": NO_APLICABLE, "motivo": "sin precio o sin cadena"}

    por_strike: Dict[float, Dict[str, int]] = {}
    for c in contratos:
        celda = por_strike.setdefault(c["strike"], {"call": 0, "put": 0})
        celda[c["tipo"]] += int(c.get("open_interest") or 0)

    puts_debajo = [(k, v["put"]) for k, v in por_strike.items()
                   if k < spot and v["put"] >= OPCIONES_OI_MINIMO_STRIKE]
    calls_encima = [(k, v["call"]) for k, v in por_strike.items()
                    if k > spot and v["call"] >= OPCIONES_OI_MINIMO_STRIKE]

    soporte = max(puts_debajo, key=lambda kv: (kv[1], kv[0]))[0] if puts_debajo else None
    resistencia = max(calls_encima, key=lambda kv: (kv[1], -kv[0]))[0] if calls_encima else None

    tabla = sorted(
        ({"strike": k, "oi_call": v["call"], "oi_put": v["put"]}
         for k, v in por_strike.items()),
        key=lambda d: -(d["oi_call"] + d["oi_put"]))[:12]

    # Posicion del precio DENTRO del canal, en [0, 1]. Es la lectura que
    # responde a "que tal precio es este para comprar": cerca de 0 el precio se
    # apoya en el soporte de open interest, cerca de 1 esta comprando contra la
    # oferta pendiente. Requiere los dos extremos; con uno solo no hay canal.
    posicion = None
    if soporte is not None and resistencia is not None and resistencia > soporte:
        posicion = round((spot - soporte) / (resistencia - soporte), 4)

    return {
        "soporte_oi": soporte,
        "resistencia_oi": resistencia,
        "posicion_en_canal": posicion,
        "en_techo_del_canal": (posicion is not None
                               and posicion >= OPCIONES_CANAL_SOBREEXTENDIDO),
        "umbral_techo": OPCIONES_CANAL_SOBREEXTENDIDO,
        "oi_por_strike": tabla,
        "oi_minimo_strike": OPCIONES_OI_MINIMO_STRIKE,
        "status": "SUCCESS" if (soporte or resistencia) else DATOS_INSUFICIENTES,
        "motivo": None if (soporte or resistencia) else
                  "ningun strike supera el open interest minimo",
    }


@tool("calcular_max_pain")
def calcular_max_pain(contratos: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Strike que minimiza el valor intrinseco agregado al vencimiento.

    `dolor(K) = suma_calls OI*max(0, K - Kc)*mult + suma_puts OI*max(0, Kp - K)*mult`,
    y el max pain es el K que lo minimiza. Es el nivel hacia el que el precio
    tiende a gravitar cerca del vencimiento.

    Se calcula sobre el vencimiento de MAYOR open interest y se declara a cuantos
    dias esta. Su fuerza es funcion de la proximidad al vencimiento: a noventa
    dias el numero sigue saliendo, pero es aritmetica y no una fuerza, asi que
    quien lo consuma debe mirar `es_operable`.
    """
    if not contratos:
        return {"max_pain": None, "status": NO_APLICABLE, "motivo": "cadena vacia"}

    oi_por_venc: Dict[str, int] = {}
    for c in contratos:
        oi_por_venc[c["vencimiento"]] = oi_por_venc.get(c["vencimiento"], 0) + int(c.get("open_interest") or 0)
    if not oi_por_venc:
        return {"max_pain": None, "status": NO_APLICABLE, "motivo": "sin open interest"}

    venc = sorted(oi_por_venc.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    lote = [c for c in contratos if c["vencimiento"] == venc]
    dias = min(c["dias"] for c in lote)
    strikes = sorted({c["strike"] for c in lote})
    if len(strikes) < 3:
        return {"max_pain": None, "status": DATOS_INSUFICIENTES, "vencimiento": venc,
                "dias": dias, "motivo": "menos de tres strikes en el vencimiento"}

    mult = OPCIONES_MULTIPLICADOR
    dolor: List[Dict[str, float]] = []
    for k in strikes:
        total = 0.0
        for c in lote:
            oi = int(c.get("open_interest") or 0)
            if not oi:
                continue
            if c["tipo"] == "call":
                total += oi * max(0.0, k - c["strike"]) * mult
            else:
                total += oi * max(0.0, c["strike"] - k) * mult
        dolor.append({"strike": k, "dolor": round(total, 2)})

    minimo = min(dolor, key=lambda d: (d["dolor"], d["strike"]))
    return {
        "max_pain": minimo["strike"],
        "vencimiento": venc,
        "dias": dias,
        "es_operable": dias <= OPCIONES_MAXPAIN_DIAS_MAXIMO,
        "dias_maximo_operable": OPCIONES_MAXPAIN_DIAS_MAXIMO,
        "n_strikes": len(strikes),
        "curva_dolor": dolor[:20],
        "status": "SUCCESS",
        "motivo": None,
    }


def _gex_en(contratos: List[Dict[str, Any]], s: float, r: float) -> Optional[float]:
    """Exposicion gamma agregada evaluada a un precio `s`, en dolares por 1%."""
    total = 0.0
    usados = 0
    for c in contratos:
        iv, oi, dias = c.get("iv"), int(c.get("open_interest") or 0), c.get("dias")
        if not iv or not oi or not dias or dias <= 0:
            continue
        g = gamma_bs(s, c["strike"], dias / 365.0, iv, r)
        if g is None:
            continue
        aporte = g * oi * OPCIONES_MULTIPLICADOR * s * s * 0.01
        total += aporte if c["tipo"] == "call" else -aporte
        usados += 1
    return total if usados else None


@tool("calcular_gamma_exposure")
def calcular_gamma_exposure(contratos: List[Dict[str, Any]], spot: Optional[float],
                            tipo_libre_riesgo: float = TIPO_LIBRE_RIESGO) -> Dict[str, Any]:
    """Exposicion gamma agregada de los creadores de mercado, en dolares por 1%.

    Gamma sale de la forma cerrada de Black-Scholes con la volatilidad implicita
    publicada por contrato. Sin volatilidad implicita no hay gamma y el bloque se
    declara NO_APLICABLE: un cero se leeria como neutralidad, que aqui seria
    falso.

    Signo positivo significa creadores de mercado LARGOS gamma: sus coberturas
    amortiguan el movimiento y el precio tiende a clavarse cerca de los strikes
    de mayor open interest, asi que un retroceso es probable que se rellene.
    Signo negativo significa cortos gamma: las coberturas aceleran el movimiento
    y esperar un retroceso puede salir caro.

    ATENCION: el signo depende de una CONVENCION —creadores largos gamma en
    calls, cortos en puts— que la cadena no permite verificar, porque publica
    open interest y no quien esta en cada lado.
    """
    if not spot or not contratos:
        return {"gex_total": None, "regimen": NO_APLICABLE, "status": NO_APLICABLE,
                "motivo": "sin precio o sin cadena"}

    total = _gex_en(contratos, float(spot), tipo_libre_riesgo)
    if total is None:
        return {"gex_total": None, "regimen": NO_APLICABLE, "status": NO_APLICABLE,
                "motivo": "ningun contrato publica volatilidad implicita utilizable"}

    por_strike: Dict[float, float] = {}
    for c in contratos:
        iv, oi, dias = c.get("iv"), int(c.get("open_interest") or 0), c.get("dias")
        if not iv or not oi or not dias or dias <= 0:
            continue
        g = gamma_bs(float(spot), c["strike"], dias / 365.0, iv, tipo_libre_riesgo)
        if g is None:
            continue
        aporte = g * oi * OPCIONES_MULTIPLICADOR * float(spot) ** 2 * 0.01
        por_strike[c["strike"]] = por_strike.get(c["strike"], 0.0) + (
            aporte if c["tipo"] == "call" else -aporte)

    return {
        "gex_total": round(total, 2),
        "regimen": "AMORTIGUADO" if total > 0 else "ACELERADO",
        "gex_por_strike": sorted(
            ({"strike": k, "gex": round(v, 2)} for k, v in por_strike.items()),
            key=lambda d: -abs(d["gex"]))[:12],
        "convencion": ("creadores de mercado largos gamma en calls y cortos en puts; "
                       "es la convencion estandar, no una medicion"),
        "status": "SUCCESS",
        "motivo": None,
    }


@tool("localizar_gamma_flip")
def localizar_gamma_flip(contratos: List[Dict[str, Any]], spot: Optional[float],
                         tipo_libre_riesgo: float = TIPO_LIBRE_RIESGO) -> Dict[str, Any]:
    """Precio al que la exposicion gamma agregada cambia de signo.

    Barre la exposicion gamma sobre un rango de +-20% alrededor del precio y
    localiza por biseccion el cruce por cero MAS CERCANO al precio actual. Es un
    nivel concreto, no una etiqueta: por encima los creadores de mercado
    amortiguan, por debajo aceleran.

    Devuelve `None` cuando no hay cambio de signo en el rango, que es una
    respuesta legitima y frecuente: significa que los creadores de mercado estan
    del mismo lado en toda la zona operable.
    """
    if not spot or not contratos:
        return {"gamma_flip": None, "status": NO_APLICABLE, "motivo": "sin precio o sin cadena"}

    s0 = float(spot)
    lo, hi = s0 * (1 - FLIP_RANGO), s0 * (1 + FLIP_RANGO)
    paso = (hi - lo) / (FLIP_PASOS - 1)
    rejilla = [lo + i * paso for i in range(FLIP_PASOS)]
    valores = [_gex_en(contratos, s, tipo_libre_riesgo) for s in rejilla]
    if any(v is None for v in valores):
        return {"gamma_flip": None, "status": NO_APLICABLE,
                "motivo": "la cadena no permite valorar la gamma en todo el rango"}

    cruces: List[float] = []
    for i in range(len(rejilla) - 1):
        a, b = valores[i], valores[i + 1]
        if a == 0.0:
            cruces.append(rejilla[i])
        elif a * b < 0:
            x0, x1 = rejilla[i], rejilla[i + 1]
            for _ in range(40):
                xm = 0.5 * (x0 + x1)
                vm = _gex_en(contratos, xm, tipo_libre_riesgo) or 0.0
                if (_gex_en(contratos, x0, tipo_libre_riesgo) or 0.0) * vm <= 0:
                    x1 = xm
                else:
                    x0 = xm
            cruces.append(0.5 * (x0 + x1))

    if not cruces:
        return {"gamma_flip": None, "status": "SUCCESS", "n_cruces": 0,
                "motivo": ("sin cambio de signo en +-20%: los creadores de mercado "
                           "estan del mismo lado en toda la zona operable")}

    flip = min(cruces, key=lambda x: abs(x - s0))
    return {"gamma_flip": round(flip, 2), "status": "SUCCESS", "n_cruces": len(cruces),
            "rango_pct": FLIP_RANGO, "motivo": None}


@tool("calcular_skew")
def calcular_skew(agregados: Dict[str, Any],
                  historico: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Asimetria de la volatilidad implicita y su percentil historico.

    `skew = IV(put fuera de dinero) - IV(call fuera de dinero)` sobre el
    vencimiento de referencia. Un skew inusualmente pronunciado senala demanda de
    cobertura cara, es decir miedo, y se lee en clave contraria igual que el
    put/call ratio.

    Se mide sobre UN vencimiento: mezclarlos meteria la estructura temporal de la
    volatilidad dentro de una medida que pretende ser de asimetria.

    Como en el put/call, lo que se usa es el percentil, y por debajo del minimo de
    observaciones se devuelve `None` con estado DATOS_INSUFICIENTES.
    """
    ivp, ivc = agregados.get("iv_put_otm"), agregados.get("iv_call_otm")
    iv_atm = agregados.get("iv_atm")
    skew = round(ivp - ivc, 6) if (ivp is not None and ivc is not None) else None
    # Normalizado por la volatilidad at-the-money: es lo que lo hace comparable
    # SIN historico. Un skew de 0.04 en un valor al 25% de volatilidad no es lo
    # mismo que en otro al 80%, y sin dividir se estaria comparando peras con
    # manzanas o —peor— esperando tres meses a poder compararlas consigo mismas.
    normalizado = (round(skew / iv_atm, 4)
                   if (skew is not None and iv_atm and iv_atm > 0) else None)
    series = _series_historicas(historico)
    pct = _percentil(skew, series["skew"])
    return {
        "skew": skew,
        "skew_normalizado": normalizado,
        "iv_put_otm": ivp,
        "iv_call_otm": ivc,
        "iv_atm": iv_atm,
        "percentil_skew": pct,
        "n_dias_historico": len(series["skew"]),
        "minimo_dias_historico": OPCIONES_MINIMO_DIAS_HISTORICO,
        # El percentil es la lectura preferida cuando hay historico; el
        # normalizado es la que permite que este bloque vote desde el dia uno.
        "status": ("SUCCESS" if pct is not None else
                   "SIN_HISTORICO" if normalizado is not None else
                   DATOS_INSUFICIENTES),
        "vencimiento_referencia": agregados.get("vencimiento_referencia"),
    }


@tool("clasificar_sesgo_opciones")
def clasificar_sesgo_opciones(posicion_en_canal: Optional[float] = None,
                              skew_normalizado: Optional[float] = None,
                              percentil_pcr: Optional[float] = None,
                              percentil_skew: Optional[float] = None,
                              gamma_flip: Optional[float] = None,
                              spot: Optional[float] = None) -> Dict[str, Any]:
    """Agrega los componentes disponibles en un sesgo de CALIDAD DEL PRECIO.

    Ojo con lo que mide este numero: no es la direccion de la tendencia —de eso
    se encarga el Analista Tecnico— sino si el precio actual es un buen sitio
    para COMPRAR. Por eso sus componentes se leen en clave contraria.

    Cuatro componentes, acotados en [-1, +1] y promediados solo sobre los
    DISPONIBLES con sus pesos renormalizados:

      - **Canal de open interest** (el que mas pesa). Posicion del precio entre
        el soporte y la resistencia de open interest, invertida: cerca del
        soporte suma, pegado a la resistencia resta. Disponible desde el primer
        dia, sin historico, y es la lectura que responde directamente a la
        pregunta que hace este bloque.
      - **Skew.** Percentil historico si lo hay; si no, el skew NORMALIZADO por
        la volatilidad at-the-money, que es comparable sin historico. Miedo caro
        en las puts suma; calls caras respecto a puts es complacencia y resta.
      - **Put/call ratio.** Solo con historico: su nivel absoluto no informa.
      - **Punto de inflexion de la gamma, ASIMETRICO.** Por debajo del nivel las
        coberturas de los creadores de mercado aceleran el movimiento en contra
        y eso es una advertencia real, con rango completo. Por encima solo dice
        que el colchon de amortiguacion queda lejos, asi que el lado positivo se
        escala a una fraccion. Sin esa asimetria el termino es una funcion
        creciente de cuanto ha subido el valor —un proxy de momentum que duplica
        la pata tecnica— y empuja a perseguir el precio justo en los valores mas
        extendidos.

    Con ningun componente disponible devuelve `None` y NO_APLICABLE. Nunca 0.0:
    un cero significaria "el precio no es ni bueno ni malo", que es una
    afirmacion sobre la cadena, y aqui lo que ocurre es que no hay cadena.
    """
    partes: List[Dict[str, Any]] = []

    if posicion_en_canal is not None:
        partes.append({
            "componente": "canal_oi",
            "valor": round(max(-1.0, min(1.0, 1.0 - 2.0 * float(posicion_en_canal))), 4),
            "peso": PESO_CANAL_OI,
            "lectura": "posicion del precio entre el soporte y la resistencia de open interest",
        })

    if percentil_skew is not None:
        partes.append({"componente": "skew_percentil",
                       "valor": round(2 * percentil_skew - 1, 4), "peso": PESO_SKEW,
                       "lectura": "skew frente a su propio historico"})
    elif skew_normalizado is not None:
        partes.append({"componente": "skew_normalizado",
                       "valor": round(math.tanh(skew_normalizado / SKEW_ESCALA), 4),
                       "peso": PESO_SKEW,
                       "lectura": "skew dividido por la volatilidad at-the-money"})

    if percentil_pcr is not None:
        partes.append({"componente": "put_call",
                       "valor": round(2 * percentil_pcr - 1, 4), "peso": PESO_PCR,
                       "lectura": "put/call frente a su propio historico"})

    if gamma_flip is not None and spot:
        distancia = (float(spot) - float(gamma_flip)) / float(spot)
        bruto = math.tanh(distancia / 0.05)
        valor = bruto * GEX_ASIMETRIA_POSITIVA if bruto > 0 else bruto
        partes.append({"componente": "gamma_flip", "valor": round(valor, 4),
                       "peso": PESO_GEX,
                       "lectura": ("por encima del punto de inflexion (lectura atenuada)"
                                   if bruto > 0 else
                                   "POR DEBAJO del punto de inflexion: las coberturas "
                                   "aceleran el movimiento en contra")})

    if not partes:
        return {"sesgo_opciones": None, "clasificacion": NO_APLICABLE,
                "componentes": [], "n_disponibles": 0,
                "motivo": "ningun componente de la cadena es evaluable"}

    peso_total = sum(p["peso"] for p in partes)
    sesgo = round(sum(p["valor"] * p["peso"] for p in partes) / peso_total, 4)

    if sesgo >= 0.45:
        etiqueta = "PRECIO_MUY_FAVORABLE"
    elif sesgo >= 0.15:
        etiqueta = "PRECIO_FAVORABLE"
    elif sesgo <= -0.45:
        etiqueta = "PRECIO_MUY_ADVERSO"
    elif sesgo <= -0.15:
        etiqueta = "PRECIO_ADVERSO"
    else:
        etiqueta = "NEUTRO"

    return {"sesgo_opciones": sesgo, "clasificacion": etiqueta, "componentes": partes,
            "n_disponibles": len(partes), "motivo": None}


TOOLS_OPCIONES = [
    calcular_put_call_ratio,
    identificar_niveles_oi,
    calcular_max_pain,
    calcular_gamma_exposure,
    localizar_gamma_flip,
    calcular_skew,
    clasificar_sesgo_opciones,
]
