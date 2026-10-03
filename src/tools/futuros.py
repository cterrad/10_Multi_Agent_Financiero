"""
Tools del bloque macro: posicionamiento de especuladores en futuros.

Que aporta y que NO aporta
--------------------------
Da DIRECCION —viento a favor o en contra del sector—, no un nivel de precio. El
nivel sale de la cadena de opciones (`src/tools/opciones.py`). Esa asimetria es
deliberada y tiene consecuencias en el backtest: el bloque macro es
reconstruible point-in-time y el de opciones no.

POR QUE EL Z-SCORE Y NO EL NIVEL
--------------------------------
El numero de contratos netos no dice nada por si solo: 300.000 contratos largos
en el crudo es mucho o poco segun lo que sea habitual en ese mercado. Lo que
informa es la DESVIACION respecto de su propio historico, que es el criterio de
Carver para posicionamiento sistematico y el mismo que Sinclair aplica a
cualquier metrica de sentimiento.

Y la posicion neta se normaliza por INTERES ABIERTO antes de tipificarla. Sin
normalizar, el crecimiento secular del mercado de futuros entra como senal: una
serie de contratos brutos de tres anos mide, en parte, cuanto ha crecido el
mercado. Es el mismo error de categoria que leer un histograma MACD sin
normalizar por ATR, que `evaluar_macd` ya corrige.

EXTREMO NO ES LO MISMO QUE DIRECCION
------------------------------------
Un z-score moderado confirma tendencia; uno extremo senala posicionamiento
hacinado, que es una advertencia contraria. La resolucion NO invierte el signo:
invertirlo con |z| > 2 produce un clasificador no monotono, que es exactamente
la patologia que el momentum por puntos enteros tenia y que el clasificador
continuo vino a corregir. El extremo se marca aparte y lo unico que hace es
prohibir perseguir el precio.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.config import (
    COT_ESCALA,
    COT_MINIMO_SEMANAS,
    COT_Z_EXTREMO,
    FUTURO_INDICE,
    MACRO_VIENTO_CONTRA,
    MACRO_VIENTO_CONTRA_FUERTE,
    MACRO_VIENTO_FAVOR,
    MACRO_VIENTO_FAVOR_FUERTE,
    SECTOR_A_FUTURO,
)

NO_APLICABLE = "NO_APLICABLE"


def _acotar(x: float, minimo: float = -1.0, maximo: float = 1.0) -> float:
    return max(minimo, min(maximo, x))


# --------------------------------------------------------------------------- #
def _posicion_neta(fila: Dict[str, Any]) -> Optional[float]:
    """Posicion neta no comercial normalizada por interes abierto."""
    oi = fila.get("interes_abierto")
    largos = fila.get("no_comercial_largos")
    cortos = fila.get("no_comercial_cortos")
    if not oi or largos is None or cortos is None:
        return None
    return (largos - cortos) / float(oi)


def _zscore(serie: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Tipifica la ultima posicion neta frente a la ventana.

    Con menos de `COT_MINIMO_SEMANAS` observaciones devuelve `z=None` y lo
    declara: una desviacion tipica calculada sobre veinte semanas no es una
    medida de extremo, y publicarla como si lo fuera es peor que no publicarla.
    """
    netas = [n for n in (_posicion_neta(f) for f in serie or []) if n is not None]
    if len(netas) < COT_MINIMO_SEMANAS:
        return {"z": None, "disponible": False, "n_semanas": len(netas),
                "motivo": (f"{len(netas)} semanas de historico, por debajo del minimo "
                           f"{COT_MINIMO_SEMANAS}")}

    n = len(netas)
    media = sum(netas) / n
    varianza = sum((x - media) ** 2 for x in netas) / n
    sigma = math.sqrt(varianza)
    if sigma <= 1e-12:
        return {"z": None, "disponible": False, "n_semanas": n,
                "motivo": "la serie de posicionamiento no tiene dispersion"}

    actual = netas[-1]
    z = (actual - media) / sigma
    return {
        "z": round(z, 4),
        "disponible": True,
        "n_semanas": n,
        "posicion_neta": round(actual, 6),
        "media": round(media, 6),
        "desviacion_tipica": round(sigma, 6),
        "extremo": abs(z) >= COT_Z_EXTREMO,
        "motivo": None,
    }


def _sesgo_de_z(z: Optional[float], signo: int) -> Optional[float]:
    """z-score a sesgo acotado en (-1, +1), monotono en z."""
    if z is None:
        return None
    return round(signo * math.tanh(z / COT_ESCALA), 4)


def _etiqueta_macro(sesgo: Optional[float]) -> str:
    """
    Corte del sesgo continuo sobre las cinco etiquetas.

    Monotono por construccion: la etiqueta solo puede mejorar si el sesgo sube.
    Mismo mecanismo que `_etiqueta` en `src/tools/tecnico.py`.
    """
    if sesgo is None:
        return NO_APLICABLE
    if sesgo >= MACRO_VIENTO_FAVOR_FUERTE:
        return "VIENTO_A_FAVOR_FUERTE"
    if sesgo >= MACRO_VIENTO_FAVOR:
        return "VIENTO_A_FAVOR"
    if sesgo <= MACRO_VIENTO_CONTRA_FUERTE:
        return "VIENTO_EN_CONTRA_FUERTE"
    if sesgo <= MACRO_VIENTO_CONTRA:
        return "VIENTO_EN_CONTRA"
    return "NEUTRO"


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("resolver_contrato_sectorial")
def resolver_contrato_sectorial(sector: str) -> Dict[str, Any]:
    """Contrato de futuros cuyo posicionamiento informa sobre un sector.

    Devuelve el simbolo del contrato, el nombre del mercado en los informes de la
    CFTC y el SIGNO de la relacion: +1 si el subyacente al alza es viento a favor
    (una petrolera con el crudo caro), -1 si es viento en contra.

    Un sector que no figura en el mapa devuelve `es_aplicable=False` y no recibe
    pata sectorial. No se le asigna un proxy: forzar un contrato para un sector
    sin relacion clara produce un numero donde no hay senal, que es peor que
    declarar NO_APLICABLE. El contrato de indice si aplica a todos los sectores,
    porque mide apetito de riesgo agregado y no exposicion sectorial.
    """
    cfg = SECTOR_A_FUTURO.get(sector)
    if not cfg:
        return {"sector": sector, "es_aplicable": False, "contrato": None,
                "cot_mercado": None, "signo": None,
                "motivo": (f"el sector {sector!r} no tiene un contrato de futuros "
                           f"correlato claro; solo se aplica la pata de indice"),
                "indice": dict(FUTURO_INDICE)}
    return {"sector": sector, "es_aplicable": True, "contrato": cfg["contrato"],
            "cot_mercado": cfg["cot"], "signo": cfg["signo"], "motivo": None,
            "indice": dict(FUTURO_INDICE)}


@tool("calcular_zscore_cot")
def calcular_zscore_cot(serie: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Tipifica el posicionamiento especulativo frente a su propio historico.

    Toma la serie semanal de informes COT y calcula el z-score de la posicion
    NETA NO COMERCIAL —especuladores— normalizada por interes abierto. Se usa la
    categoria no comercial porque los comerciales cubren produccion o inventario
    y su posicion la dicta el negocio, no una opinion.

    La normalizacion por interes abierto no es cosmetica: el numero bruto de
    contratos crece con el tamano del mercado, asi que un z-score sobre la serie
    sin normalizar mide en parte ese crecimiento.

    Marca `extremo` cuando el posicionamiento esta hacinado. El extremo NO
    invierte el signo del sesgo; solo prohibe perseguir el precio.

    Con menos semanas que el minimo devuelve `z=None` con su motivo, nunca un
    cero que se leeria como posicionamiento neutro.
    """
    return _zscore(serie)


@tool("clasificar_sesgo_macro")
def clasificar_sesgo_macro(componentes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega las patas disponibles en un sesgo macro y su etiqueta.

    Cada componente es `{"contrato", "papel", "z", "signo", "extremo"}`. El sesgo
    de cada pata es `signo * tanh(z / escala)`, acotado en (-1, +1) y monotono en
    el z-score; el sesgo agregado es la media de las patas DISPONIBLES.

    Promediar solo sobre lo disponible es deliberado: imputar un cero a una pata
    ausente convertiria una ausencia en una lectura neutra, que es la regla
    numero uno del proyecto. Un valor cuyo sector no tiene contrato correlato se
    evalua solo con la pata de indice y lo declara.

    Devuelve NO_APLICABLE si no hay ninguna pata evaluable.
    """
    detalle: List[Dict[str, Any]] = []
    sesgos: List[float] = []
    extremo = False

    for comp in componentes or []:
        sesgo = _sesgo_de_z(comp.get("z"), int(comp.get("signo") or 1))
        detalle.append({
            "contrato": comp.get("contrato"),
            "papel": comp.get("papel"),
            "z": comp.get("z"),
            "signo": comp.get("signo"),
            "sesgo": sesgo,
            "extremo": bool(comp.get("extremo")),
            "motivo": comp.get("motivo"),
        })
        if sesgo is not None:
            sesgos.append(sesgo)
            extremo = extremo or bool(comp.get("extremo"))

    if not sesgos:
        return {"sesgo_macro": None, "clasificacion": NO_APLICABLE, "extremo": False,
                "componentes": detalle, "n_disponibles": 0}

    sesgo_macro = round(sum(sesgos) / len(sesgos), 4)
    return {
        "sesgo_macro": sesgo_macro,
        "clasificacion": _etiqueta_macro(sesgo_macro),
        "extremo": extremo,
        "componentes": detalle,
        "n_disponibles": len(sesgos),
        "cortes": {"viento_a_favor_fuerte": MACRO_VIENTO_FAVOR_FUERTE,
                   "viento_a_favor": MACRO_VIENTO_FAVOR,
                   "viento_en_contra": MACRO_VIENTO_CONTRA,
                   "viento_en_contra_fuerte": MACRO_VIENTO_CONTRA_FUERTE},
    }


TOOLS_FUTUROS = [
    resolver_contrato_sectorial,
    calcular_zscore_cot,
    clasificar_sesgo_macro,
]
