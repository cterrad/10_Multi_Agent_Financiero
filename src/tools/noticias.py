"""
Tools del Analista de Noticias: puntuación de prensa, invocable.

El scorer completo —categoría, credibilidad de fuente, decaimiento por
antigüedad, corroboración, penalización de ruido y agregación por OR ruidoso—
vivía como funciones de módulo dentro del agente. Aquí están las mismas
funciones, sin tocar, más dos fachadas `@tool` que exponen los dos pasos con
sentido propio: puntuar los ítems y agregarlos a una probabilidad.

TODA la clasificación sale de diccionarios cerrados en `src/config.py`. Ninguna
categoría, dirección ni probabilidad procede del criterio de un modelo, y esa es
la razón de que el dictamen de noticias sea reproducible: el prototipo del que
salió este agente (`src/notebooks/agent_search_web.ipynb`) sí le pedía criterio
al LLM, y por eso no era backtesteable.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    NEWS_BEARISH_LEXICON, NEWS_BULLISH_LEXICON, NEWS_CATEGORY_KEYWORDS,
    NEWS_CATEGORY_PRIORITY, NEWS_CATEGORY_WEIGHTS, NEWS_CORROBORATION_BONUS,
    NEWS_DAYS_IF_UNDATED, NEWS_DIRECTION_MARGIN, NEWS_HALFLIFE_DAYS,
    NEWS_HIGH_IMPACT_THRESHOLD, NEWS_ITEM_PROB_MAX, NEWS_MAX_CORROBORATION_FACTOR,
    NEWS_MEDIUM_IMPACT_THRESHOLD, NEWS_NOISE_LEXICON, NEWS_NOISE_PENALTY,
    NEWS_SOURCE_CREDIBILITY, NEWS_TOP_K_ITEMS,
)
from src.data.news.schema import normalizar_texto
from langchain_core.tools import tool

# Los léxicos se normalizan una sola vez al importar: así `src/config.py` puede
# escribirlos de forma legible ("raises full-year", con acentos y guiones) y la
# comparación sigue siendo exacta contra el texto normalizado del ítem.
_CATEGORIA_KEYWORDS = {
    categoria: tuple(dict.fromkeys(normalizar_texto(k) for k in claves))
    for categoria, claves in NEWS_CATEGORY_KEYWORDS.items()
}
_LEXICO_ALCISTA = tuple(dict.fromkeys(normalizar_texto(t) for t in NEWS_BULLISH_LEXICON))
_LEXICO_BAJISTA = tuple(dict.fromkeys(normalizar_texto(t) for t in NEWS_BEARISH_LEXICON))
_LEXICO_RUIDO = tuple(dict.fromkeys(normalizar_texto(t) for t in NEWS_NOISE_LEXICON))

CATEGORIA_POR_DEFECTO = "OTROS"


# --------------------------------------------------------------------------- #
# Reglas deterministas
# --------------------------------------------------------------------------- #
def _contiene(texto_acolchado: str, termino: str) -> bool:
    """
    Coincidencia por palabra completa sobre texto ya normalizado.

    El texto viene sin puntuación y con las palabras separadas por un espacio,
    así que acolcharlo con espacios convierte un `in` en una búsqueda con
    límites de palabra: "eps" casa con "eps" pero no con "epsilon".
    """
    return f" {termino} " in texto_acolchado


def clasificar_categoria(texto: str, categoria_forzada: Optional[str] = None) -> Tuple[str, int]:
    """
    Categoría del ítem por número de coincidencias léxicas.

    `categoria_forzada` existe para el 8-K con Ítem 2.02: ahí la categoría es
    definicional (la SEC ya declara que el formulario contiene resultados), no
    una inferencia sobre el titular.

    El desempate es `NEWS_CATEGORY_PRIORITY`, un orden fijo y declarado: sin él
    la clasificación dependería del orden de iteración de un diccionario.
    """
    if categoria_forzada and categoria_forzada in NEWS_CATEGORY_WEIGHTS:
        return categoria_forzada, 1

    acolchado = f" {normalizar_texto(texto)} "
    conteos = {
        categoria: sum(1 for termino in terminos if _contiene(acolchado, termino))
        for categoria, terminos in _CATEGORIA_KEYWORDS.items()
    }
    mejor = max(conteos.values()) if conteos else 0
    if mejor == 0:
        return CATEGORIA_POR_DEFECTO, 0

    empatadas = [c for c, n in conteos.items() if n == mejor]
    for categoria in NEWS_CATEGORY_PRIORITY:
        if categoria in empatadas:
            return categoria, mejor
    return CATEGORIA_POR_DEFECTO, mejor


def inferir_direccion_item(texto: str) -> Tuple[str, int, int]:
    """
    Dirección probable de UN ítem según el léxico de severidad.

    Devuelve la etiqueta y los conteos que la explican, para que el informe
    pueda justificarla sin recalcular nada.
    """
    acolchado = f" {normalizar_texto(texto)} "
    alcistas = sum(1 for t in _LEXICO_ALCISTA if _contiene(acolchado, t))
    bajistas = sum(1 for t in _LEXICO_BAJISTA if _contiene(acolchado, t))
    if alcistas > bajistas:
        return "ALCISTA", alcistas, bajistas
    if bajistas > alcistas:
        return "BAJISTA", alcistas, bajistas
    return "NEUTRA", alcistas, bajistas


def es_ruido_promocional(texto: str) -> bool:
    """
    ¿Es un aviso de bufete captando demandantes, y no comunicación de la empresa?

    Estos avisos son formalmente REGULATORIO y llegan por newswire, así que sin
    esta comprobación entrarían con credibilidad alta y una empresa grande
    tendría noticias "de alto impacto" todas las semanas. No se descartan —un
    litigio real puede ir detrás—, solo se degradan por `NEWS_NOISE_PENALTY`.
    """
    acolchado = f" {normalizar_texto(texto)} "
    return any(_contiene(acolchado, t) for t in _LEXICO_RUIDO)


def dias_de_antiguedad(fecha: Optional[str], as_of: str) -> float:
    """
    Días entre la publicación y la fecha de análisis.

    Sin fecha se aplica `NEWS_DAYS_IF_UNDATED`, que penaliza sin descartar y no
    depende del reloj: dos ejecuciones sobre el mismo payload dan lo mismo.
    Las fechas futuras (husos horarios de los feeds) se tratan como 0 días.
    """
    if not fecha:
        return NEWS_DAYS_IF_UNDATED
    try:
        return max((date.fromisoformat(as_of) - date.fromisoformat(fecha)).days, 0)
    except (ValueError, TypeError):
        return NEWS_DAYS_IF_UNDATED


def decaimiento(dias: float) -> float:
    """Decaimiento exponencial con semivida `NEWS_HALFLIFE_DAYS`."""
    return 0.5 ** (dias / NEWS_HALFLIFE_DAYS) if NEWS_HALFLIFE_DAYS > 0 else 1.0


def factor_corroboracion(n_fuentes: int) -> float:
    """Bonus por fuentes independientes que reportan el mismo hecho, con tope."""
    return min(1.0 + NEWS_CORROBORATION_BONUS * max(n_fuentes - 1, 0),
               NEWS_MAX_CORROBORATION_FACTOR)


def puntuar_item(item: Dict[str, Any], as_of: str) -> Dict[str, Any]:
    """
    Puntúa un ítem agregado. Devuelve una copia enriquecida con TODOS los
    factores intermedios, de modo que la cifra final sea auditable término a
    término desde el informe.

        p = P_MAX · peso_categoría · credibilidad · decaimiento · corroboración

    y, si el ítem es ruido promocional de bufetes, se multiplica además por
    `NEWS_NOISE_PENALTY`.
    """
    texto = item.get("texto_agregado") or f"{item.get('titulo', '')} {item.get('extracto', '')}"

    categoria, n_coincidencias = clasificar_categoria(texto, item.get("categoria_forzada"))
    peso_categoria = NEWS_CATEGORY_WEIGHTS.get(categoria, NEWS_CATEGORY_WEIGHTS["OTROS"])
    tipo_fuente = item.get("tipo_fuente", "DESCONOCIDA")
    credibilidad = NEWS_SOURCE_CREDIBILITY.get(tipo_fuente, NEWS_SOURCE_CREDIBILITY["DESCONOCIDA"])

    dias = dias_de_antiguedad(item.get("fecha"), as_of)
    peso_tiempo = decaimiento(dias)
    corroboracion = factor_corroboracion(int(item.get("n_corroboraciones", 1)))
    direccion, n_alcistas, n_bajistas = inferir_direccion_item(texto)

    ruido = es_ruido_promocional(texto)
    probabilidad = min(
        NEWS_ITEM_PROB_MAX * peso_categoria * credibilidad * peso_tiempo * corroboracion
        * (NEWS_NOISE_PENALTY if ruido else 1.0),
        NEWS_ITEM_PROB_MAX,
    )

    puntuado = dict(item)
    puntuado.update({
        "categoria": categoria,
        "coincidencias_categoria": n_coincidencias,
        "peso_categoria": round(peso_categoria, 4),
        "credibilidad": round(credibilidad, 4),
        "dias_antiguedad": round(dias, 2),
        "decaimiento": round(peso_tiempo, 4),
        "factor_corroboracion": round(corroboracion, 4),
        "ruido_promocional": ruido,
        "direccion": direccion,
        "terminos_alcistas": n_alcistas,
        "terminos_bajistas": n_bajistas,
        "probabilidad_impacto": round(probabilidad, 4),
    })
    puntuado.pop("texto_agregado", None)
    return puntuado


def _orden_por_relevancia(puntuados: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mayor probabilidad primero; desempates fijos para que el orden no varíe."""
    return sorted(
        puntuados,
        key=lambda i: (-i["probabilidad_impacto"], i.get("fecha") or "", i.get("titulo", "")),
    )


def agregar_probabilidad(puntuados: List[Dict[str, Any]]) -> float:
    """
    Combina los ítems con OR ruidoso sobre los `NEWS_TOP_K_ITEMS` más relevantes:

        P = 1 - Π (1 - p_i)

    Es la probabilidad de que AL MENOS UNO de los catalizadores mueva el precio,
    que es justo la pregunta que hace el agente. El truncamiento en K impide que
    una cola larga de ruido de agregadores empuje la cifra hacia 1.
    """
    probabilidad = 0.0
    for item in _orden_por_relevancia(puntuados)[:NEWS_TOP_K_ITEMS]:
        probabilidad = 1.0 - (1.0 - probabilidad) * (1.0 - item["probabilidad_impacto"])
    return round(probabilidad, 4)


def clasificar_impacto(probabilidad: float) -> str:
    """Bucket en el estilo de `momentum_classification`: umbrales de config."""
    if probabilidad >= NEWS_HIGH_IMPACT_THRESHOLD:
        return "ALTA"
    if probabilidad >= NEWS_MEDIUM_IMPACT_THRESHOLD:
        return "MEDIA"
    return "BAJA"


def direccion_agregada(puntuados: List[Dict[str, Any]]) -> Tuple[str, float]:
    """
    Dirección del conjunto, ponderando cada ítem por su propia probabilidad de
    impacto: una nota bajista de un 8-K pesa más que tres titulares alcistas de
    un agregador.

    Devuelve la etiqueta y el desequilibrio normalizado a [-1, 1].
    """
    peso_alcista = sum(i["probabilidad_impacto"] for i in puntuados if i["direccion"] == "ALCISTA")
    peso_bajista = sum(i["probabilidad_impacto"] for i in puntuados if i["direccion"] == "BAJISTA")
    total = peso_alcista + peso_bajista

    if total <= 0:
        # Ningún ítem activa el léxico: hay noticias, pero no dicen en qué
        # sentido. Es INCIERTA, que no es lo mismo que MIXTA.
        return "INCIERTA", 0.0

    neto = round((peso_alcista - peso_bajista) / total, 4)
    if neto >= NEWS_DIRECTION_MARGIN:
        return "ALCISTA", neto
    if neto <= -NEWS_DIRECTION_MARGIN:
        return "BAJISTA", neto
    return "MIXTA", neto


# --------------------------------------------------------------------------- ## =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("puntuar_noticias")
def puntuar_noticias(items: List[Dict[str, Any]], as_of: str) -> List[Dict[str, Any]]:
    """Puntúa cada noticia del dosier y las ordena por relevancia.

    Para cada ítem calcula su probabilidad de mover el precio como producto de
    cinco factores: peso de la categoría (resultados, guía, regulatorio, M&A...),
    credibilidad del tipo de fuente, decaimiento exponencial por antigüedad,
    bonus por corroboración en dominios distintos y penalización si el titular
    tiene forma de contenido promocional.

    Categoría y dirección salen de diccionarios cerrados de palabras clave, no
    del criterio de un modelo: es lo que hace el dictamen reproducible.

    `as_of` es la fecha de referencia para el decaimiento (YYYY-MM-DD).
    """
    return _orden_por_relevancia([puntuar_item(i, as_of) for i in items])


@tool("agregar_impacto_noticias")
def agregar_impacto_noticias(items_puntuados: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Agrega las noticias puntuadas en una probabilidad de impacto y una dirección.

    La agregación es un OR ruidoso sobre los `NEWS_TOP_K_ITEMS` ítems de mayor
    probabilidad: dos noticias independientes que apuntan al mismo sitio elevan
    la probabilidad conjunta, pero nunca por encima de 1, y una décima noticia
    marginal no la infla.

    Devuelve la probabilidad, su bucket (ALTA / MEDIA / BAJA), la dirección
    probable y el desequilibrio alcista-bajista que la sustenta. La dirección es
    MIXTA cuando ninguno de los dos lados supera el margen: es un resultado, no
    un empate por falta de análisis.
    """
    probabilidad = agregar_probabilidad(items_puntuados)
    direccion, desequilibrio = direccion_agregada(items_puntuados)
    return {
        "impact_probability": probabilidad,
        "impact_classification": clasificar_impacto(probabilidad),
        "direction_classification": direccion,
        "direction_imbalance": desequilibrio,
        "n_items": len(items_puntuados),
        "top_k_considerados": min(len(items_puntuados), NEWS_TOP_K_ITEMS),
    }


TOOLS_NOTICIAS = [puntuar_noticias, agregar_impacto_noticias]
