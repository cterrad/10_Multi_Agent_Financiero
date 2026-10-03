"""
Tools de régimen de volatilidad: nivel, z-score, curva y puerta.

QUÉ CUBRE Y POR QUÉ FALTABA
----------------------------
El sistema no tenía ninguna medida de estrés sistémico. El dosier COT mide
**posicionamiento por contrato** —cuánto están largos los especuladores del
E-mini o del crudo—, que es una pregunta distinta de «en qué régimen está el
mercado». Un valor puede tener el posicionamiento a favor y estar en mitad de
una capitulación.

Es la traducción del *anti-falling-knife gate* de `src/macro/regime.py` del
repositorio 07 (*Bear Trap*) al vocabulario de este proyecto. Allí es una puerta
binaria (`vix_level <= 35 AND vix_z <= 2`) que suprime entradas largas en
pánico; aquí son cinco etiquetas y **dos mecanismos que solo cierran**, porque
el anfitrión necesita distinguir «no perseguir el precio» de «no comprar».

POR QUÉ EL VIX Y NO EL DIFERENCIAL DE CRÉDITO
----------------------------------------------
El diferencial *high yield* sería el complemento natural —el VIX mide miedo en
renta variable, el crédito mide tensión de financiación— pero FRED solo sirve
`BAMLH0A0HYM2` desde 2023-09-05, tres años de once. Una serie que no cubre la
ventana del estudio no puede entrar en la ruta de decisión: está en
`output/FUENTES_DATOS.md`, iteración 17.

DOS REGLAS QUE NO CONVIENE DESHACER
------------------------------------
1. **El z-score se calcula sobre observaciones YA PUBLICADAS.** El filtro vive
   en `src.data.fred.serie.serie_diaria`, que selecciona por
   `fecha_publicacion <= as_of`. Este módulo no vuelve a filtrar: recibe la
   serie ya recortada. Duplicar el filtro sería una segunda implementación de la
   disciplina point-in-time, el mismo bug de clase que una regla de decisión
   duplicada.
2. **La curva invertida agrava, nunca atenúa.** `VIX > VIX3M` significa que el
   estrés es inmediato y no de fondo, y solo puede empeorar la clasificación en
   un escalón. No puede mejorarla: una curva en contango durante un pánico no
   convierte el pánico en calma.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.config import (
    REGIMEN_INVERSION_CURVA,
    REGIMEN_MINIMO_OBSERVACIONES,
    REGIMEN_VENTANA_ZSCORE,
    REGIMEN_VIX_CALMA,
    REGIMEN_VIX_PANICO,
    REGIMEN_VIX_TENSION,
    REGIMEN_Z_PANICO,
    REGIMEN_Z_TENSION,
)

NO_APLICABLE = "NO_APLICABLE"

# Escalera de regímenes, de menor a mayor estrés. El orden ES la semántica: el
# agravamiento por curva invertida sube un escalón en esta lista, y no puede
# bajarlo.
ESCALERA_REGIMEN = ["CALMA", "NORMAL", "TENSION", "PANICO"]


def _valores(observaciones: Optional[List[Dict[str, Any]]]) -> List[float]:
    return [float(o["valor"]) for o in (observaciones or [])
            if o.get("valor") is not None]


def _zscore(observaciones: Optional[List[Dict[str, Any]]],
            ventana: int = REGIMEN_VENTANA_ZSCORE) -> Dict[str, Any]:
    """
    Nivel actual y z-score sobre la ventana móvil anterior.

    Devuelve `z = None` —no 0.0— por debajo de `REGIMEN_MINIMO_OBSERVACIONES`.
    Un z de 0.0 afirmaría «la volatilidad está en su media», que es una
    afirmación fuerte sobre una serie que no se ha podido reconstruir. Es la
    misma regla por la que los percentiles de opciones declaran
    DATOS_INSUFICIENTES en vez de asumir el percentil 50.
    """
    vals = _valores(observaciones)
    if not vals:
        return {"nivel": None, "z": None, "media": None, "desviacion_tipica": None,
                "n_observaciones": 0,
                "motivo": "serie de volatilidad vacía o no publicada"}

    nivel = vals[-1]
    muestra = vals[-ventana:]
    if len(muestra) < REGIMEN_MINIMO_OBSERVACIONES:
        return {"nivel": round(nivel, 2), "z": None, "media": None,
                "desviacion_tipica": None, "n_observaciones": len(vals),
                "motivo": (f"{len(muestra)} observaciones frente a las "
                           f"{REGIMEN_MINIMO_OBSERVACIONES} mínimas: el z-score no se "
                           f"emite en lugar de asumir la media")}

    media = sum(muestra) / len(muestra)
    var = sum((v - media) ** 2 for v in muestra) / (len(muestra) - 1)
    sd = math.sqrt(var)
    if sd <= 0:
        return {"nivel": round(nivel, 2), "z": None, "media": round(media, 3),
                "desviacion_tipica": 0.0, "n_observaciones": len(vals),
                "motivo": "desviación típica nula: la serie no varía en la ventana"}

    return {"nivel": round(nivel, 2), "z": round((nivel - media) / sd, 3),
            "media": round(media, 3), "desviacion_tipica": round(sd, 3),
            "n_observaciones": len(vals), "motivo": None}


def _curva(nivel_corto: Optional[float],
           nivel_largo: Optional[float]) -> Dict[str, Any]:
    """
    Cociente entre la volatilidad a un mes y a tres meses.

    Por encima de `REGIMEN_INVERSION_CURVA` la curva está invertida: el mercado
    paga más por cubrirse a corto que a medio plazo, que es la firma de un
    estrés inmediato y no de fondo. Discrimina mejor que el nivel a secas, que
    es el único insumo de la puerta del repo 07.
    """
    if not nivel_corto or not nivel_largo or nivel_largo <= 0:
        return {"ratio_curva": None, "invertida": False,
                "motivo": "falta una de las dos series de volatilidad"}
    ratio = nivel_corto / nivel_largo
    return {"ratio_curva": round(ratio, 3),
            "invertida": ratio > REGIMEN_INVERSION_CURVA, "motivo": None}


def _clasificar_regimen(nivel: Optional[float], z: Optional[float],
                        invertida: bool = False) -> Dict[str, Any]:
    """
    Cinco etiquetas por cortes sobre nivel y z-score, más la puerta.

    Manda **la peor de las dos dimensiones**, no su promedio: un VIX de 20 con
    z de +3 describe un salto brusco desde la calma, y promediarlo con el nivel
    lo disolvería. Es el mismo criterio que gobierna la memoria de reflexión
    («manda la peor dimensión, no el producto»).

    La puerta se cierra en TENSION y en PANICO. Cerrada, prohíbe perseguir el
    precio; nunca lo habilita.
    """
    if nivel is None:
        return {"clasificacion": NO_APLICABLE, "puerta_abierta": True,
                "escalon": None,
                "motivo": ("sin nivel de volatilidad: el régimen no se clasifica y la "
                           "puerta queda abierta, que es el comportamiento previo a "
                           "este agente")}

    por_nivel = (3 if nivel >= REGIMEN_VIX_PANICO else
                 2 if nivel >= REGIMEN_VIX_TENSION else
                 0 if nivel <= REGIMEN_VIX_CALMA else 1)
    por_z = (3 if (z is not None and z >= REGIMEN_Z_PANICO) else
             2 if (z is not None and z >= REGIMEN_Z_TENSION) else 1)

    escalon = max(por_nivel, por_z if z is not None else 0)
    if invertida:
        # Solo agrava, y como mucho hasta PANICO.
        escalon = min(len(ESCALERA_REGIMEN) - 1, escalon + 1)

    clasificacion = ESCALERA_REGIMEN[escalon]
    return {
        "clasificacion": clasificacion,
        "puerta_abierta": clasificacion in ("CALMA", "NORMAL"),
        "escalon": escalon,
        "escalon_por_nivel": por_nivel,
        "escalon_por_zscore": por_z if z is not None else None,
        "agravado_por_curva": bool(invertida),
        "motivo": None,
    }


def _volatilidad_relativa(volatilidad_anual: Optional[float],
                          nivel_volatilidad: Optional[float]) -> Dict[str, Any]:
    """
    Volatilidad realizada del valor frente a la implícita del mercado.

    Es lo que hace que el dictamen de este agente sea POR TICKER y no una copia
    del mismo párrafo cincuenta veces: el régimen es común al lote, pero dentro
    del mismo régimen un valor que se mueve el doble que el mercado no está en la
    misma situación que uno que se mueve la mitad.

    El VIX viene en puntos porcentuales anualizados y `volatilidad_anual` en
    tanto por uno, de ahí la división por 100.
    """
    if not volatilidad_anual or not nivel_volatilidad or nivel_volatilidad <= 0:
        return {"volatilidad_relativa": None,
                "motivo": "falta la volatilidad del valor o la del mercado"}
    return {"volatilidad_relativa": round(volatilidad_anual / (nivel_volatilidad / 100.0), 3),
            "motivo": None}


# --------------------------------------------------------------------------- #
# Fachadas @tool
# --------------------------------------------------------------------------- #
@tool("calcular_zscore_volatilidad")
def calcular_zscore_volatilidad(observaciones: List[Dict[str, Any]],
                                ventana: int = REGIMEN_VENTANA_ZSCORE) -> Dict[str, Any]:
    """Nivel actual de la volatilidad implícita y su z-score sobre la ventana móvil.

    Recibe la serie YA FILTRADA por fecha de publicación: la disciplina
    point-in-time vive en `src.data.fred.serie.serie_diaria`, que selecciona por
    `fecha_publicacion <= as_of`, y no se reimplementa aquí.

    Devuelve `z = None`, nunca 0.0, cuando no hay observaciones suficientes. Un
    z de cero afirmaría que la volatilidad está exactamente en su media, que es
    una afirmación fuerte sobre una serie que no se ha podido reconstruir.
    """
    return _zscore(observaciones, ventana)


@tool("medir_curva_volatilidad")
def medir_curva_volatilidad(nivel_corto: Optional[float],
                            nivel_largo: Optional[float]) -> Dict[str, Any]:
    """Pendiente de la curva de volatilidad implícita (un mes frente a tres meses).

    Por encima de la unidad la curva está invertida: el mercado paga más por
    cubrirse a corto que a medio plazo, que es la firma de un estrés inmediato y
    no de fondo. Discrimina mejor que el nivel a secas.

    Sin una de las dos series devuelve `ratio_curva = None` y declara el motivo.
    """
    return _curva(nivel_corto, nivel_largo)


@tool("clasificar_regimen_volatilidad")
def clasificar_regimen_volatilidad(nivel: Optional[float], z: Optional[float] = None,
                                   invertida: bool = False) -> Dict[str, Any]:
    """Clasifica el régimen de mercado en CALMA, NORMAL, TENSION o PANICO.

    Manda la PEOR de las dos dimensiones —nivel y z-score—, no su promedio: un
    nivel moderado con un z-score de +3 describe un salto brusco desde la calma,
    y promediarlo lo disolvería. La curva invertida agrava un escalón y nunca
    atenúa.

    `puerta_abierta` es falsa en TENSION y en PANICO. Cerrada, prohíbe perseguir
    el precio, en la misma familia que el RSI extremo: no cambia la dirección de
    la tesis, cierra la puerta a entrar a mercado.

    Sin nivel devuelve NO_APLICABLE con la puerta ABIERTA, que reproduce el
    comportamiento previo a que este agente existiera.
    """
    return _clasificar_regimen(nivel, z, invertida)


@tool("medir_volatilidad_relativa")
def medir_volatilidad_relativa(volatilidad_anual: Optional[float],
                               nivel_volatilidad: Optional[float]) -> Dict[str, Any]:
    """Volatilidad realizada del valor dividida por la implícita del mercado.

    Por encima de 1.0 el valor se mueve más que el mercado dentro del mismo
    régimen; por debajo, menos. Es lo que hace que el dictamen sea por valor y no
    una copia del régimen agregado.
    """
    return _volatilidad_relativa(volatilidad_anual, nivel_volatilidad)


TOOLS_REGIMEN = [
    calcular_zscore_volatilidad,
    medir_curva_volatilidad,
    clasificar_regimen_volatilidad,
    medir_volatilidad_relativa,
]
