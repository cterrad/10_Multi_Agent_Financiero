"""
Forma normalizada de un ítem de noticia y utilidades de limpieza.

Los tres buscadores (Google News RSS, Tavily y 8-K de la SEC) devuelven
estructuras completamente distintas. Todos pasan por `normalizar_item()` y
salen con exactamente las mismas claves, que es lo que permite deduplicar,
puntuar y serializar sin ramas por origen.

Este módulo no decide nada: normaliza texto, fechas y dominios. La única
clasificación que hace es `clasificar_tipo_fuente()`, que traduce un dominio a
uno de los cubos de `NEWS_SOURCE_CREDIBILITY` — es un mapa de datos declarado
en `src/config.py`, no un juicio.
"""

from __future__ import annotations

import html
import re
import unicodedata
import urllib.parse
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

from src.config import NEWS_DOMAIN_TYPES

# Claves obligatorias de un ítem normalizado.
CLAVES_ITEM = ("titulo", "url", "fuente", "fecha", "extracto", "tipo_fuente", "buscadores")

_ETIQUETAS_HTML = re.compile(r"<[^>]+>")
_NO_ALFANUM = re.compile(r"[^a-z0-9ñ ]+")
_ESPACIOS = re.compile(r"\s+")

# Palabras vacías que aportan ruido al comparar titulares. Bilingüe, corta y
# fija: no se pretende hacer PLN, solo evitar que "the" y "de" inflen la
# similitud entre titulares que no hablan de lo mismo.
_VACIAS = frozenset("""
a al and as at by de del el en for from in la las los of on or para por que the to
with y un una is its it be has have will after over into new
""".split())


def limpiar_texto(texto: Optional[str]) -> str:
    """Quita etiquetas HTML y descodifica entidades (RSS viene con ambas)."""
    return _ESPACIOS.sub(" ", html.unescape(_ETIQUETAS_HTML.sub(" ", texto or ""))).strip()


def normalizar_texto(texto: Optional[str]) -> str:
    """Minúsculas, sin acentos y sin puntuación: base de todas las comparaciones."""
    limpio = limpiar_texto(texto).lower()
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", limpio) if unicodedata.category(c) != "Mn"
    )
    return _ESPACIOS.sub(" ", _NO_ALFANUM.sub(" ", sin_acentos)).strip()


def tokens_titular(titulo: Optional[str]) -> frozenset:
    """Conjunto de palabras significativas de un titular, para el índice de Jaccard."""
    return frozenset(p for p in normalizar_texto(titulo).split() if p not in _VACIAS and len(p) > 2)


def fecha_iso(valor: Any) -> Optional[str]:
    """
    Normaliza a 'YYYY-MM-DD' desde los formatos que aparecen en la práctica:
    RFC 822 (RSS), ISO 8601 con o sin zona (Tavily, SEC) y objetos date/datetime.
    Devuelve None si no se puede interpretar; nunca inventa una fecha.
    """
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()

    texto = str(valor).strip()
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(texto).date().isoformat()
    except (TypeError, ValueError):
        pass
    for formato in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%m/%d/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(texto[:10], formato).date().isoformat()
        except ValueError:
            continue
    return None


def dominio_de_url(url: Optional[str]) -> str:
    """Dominio en minúsculas y sin 'www.'; cadena vacía si la URL no es utilizable."""
    if not url:
        return ""
    try:
        red = urllib.parse.urlparse(url if "//" in url else f"//{url}").netloc.lower()
    except ValueError:
        return ""
    return red[4:] if red.startswith("www.") else red


# Sufijos societarios que no distinguen a una empresa de otra y estorban al
# comparar su nombre con un dominio.
_SUFIJOS_SOCIETARIOS = frozenset("""
inc incorporated corp corporation co company plc ltd limited llc lp sa sab sas
nv bv ag spa srl group holdings holding the class common stock
""".split())


def _etiqueta_registrable(dominio: str) -> str:
    """'investor.acme.co.uk' -> 'acme'; 'acme.com' -> 'acme'."""
    partes = [p for p in dominio.split(".") if p]
    if len(partes) < 2:
        return dominio
    # Dominios de segundo nivel de país (co.uk, com.mx): la etiqueta útil es la
    # anterior a las dos últimas.
    if len(partes) >= 3 and partes[-2] in ("co", "com", "org", "net", "gov", "edu"):
        return partes[-3]
    return partes[-2]


def _es_dominio_de_la_empresa(dominio: str, empresa: Optional[str]) -> bool:
    """
    ¿El dominio pertenece a la propia empresa analizada?

    Una nota publicada en apple.com es comunicación directa del emisor y merece
    el mismo trato que investor.apple.com; sin esta comprobación, la sala de
    prensa corporativa acabaría en DESCONOCIDA (0.30), por debajo de un
    agregador cualquiera, que es exactamente lo contrario del orden que quiere
    el ranking de credibilidad.

    La comparación es conservadora: exige que la etiqueta registrable del
    dominio coincida con una palabra significativa del nombre de la empresa, o
    con todas ellas concatenadas ("bankofamerica.com" para "Bank of America").
    """
    if not dominio or not empresa:
        return False

    palabras = [p for p in normalizar_texto(empresa).split() if p not in _SUFIJOS_SOCIETARIOS]
    if not palabras:
        return False

    # Los conectores cortos ("of", "y") no valen como coincidencia por sí solos,
    # pero sí forman parte del dominio concatenado: "Bank of America" ->
    # "bankofamerica.com". Por eso se filtran para el conjunto y no para la unión.
    significativas = {p for p in palabras if len(p) >= 4}
    etiqueta = _etiqueta_registrable(dominio)
    return etiqueta in significativas or etiqueta == "".join(palabras)


def clasificar_tipo_fuente(url: Optional[str], fuente: Optional[str] = None,
                           empresa: Optional[str] = None) -> str:
    """
    Traduce el dominio a uno de los cubos de credibilidad de `src/config.py`.

    El orden de comprobación importa:

      1. sec.gov es fuente primaria y gana siempre.
      2. Los mapas explícitos de `NEWS_DOMAIN_TYPES` van antes que cualquier
         heurística, para que un subdominio como `media.msn.com` se clasifique
         por su medio y no por su prefijo.
      3. Solo entonces se aplican las dos heurísticas de comunicación directa
         del emisor: subdominio de relaciones con inversores y dominio propio
         de la empresa.

    Lo que no reconoce ninguna regla cae en DESCONOCIDA, que es el cubo más
    penalizado: nunca se asume calidad.
    """
    dominio = dominio_de_url(url) or normalizar_texto(fuente).replace(" ", "")
    if not dominio:
        return "DESCONOCIDA"

    if dominio.endswith("sec.gov"):
        return "SEC_8K"

    for tipo, dominios in NEWS_DOMAIN_TYPES.items():
        for conocido in dominios:
            if dominio == conocido or dominio.endswith("." + conocido):
                return tipo

    if dominio.split(".")[0] in ("investor", "investors", "ir", "press", "newsroom", "media"):
        return "IR_OFICIAL"

    if _es_dominio_de_la_empresa(dominio, empresa):
        return "IR_OFICIAL"

    return "DESCONOCIDA"


def normalizar_item(
    titulo: Any,
    url: Any,
    fuente: Any,
    fecha: Any,
    extracto: Any,
    buscador: str,
    tipo_fuente: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    empresa: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Construye un ítem con la forma canónica. Devuelve None si el titular está
    vacío: un ítem sin titular no se puede ni clasificar ni deduplicar.

    `buscadores` es una lista desde el principio (no una cadena) porque la
    deduplicación fusiona ítems y necesita acumular procedencias.
    """
    titulo_limpio = limpiar_texto(titulo)
    if not titulo_limpio:
        return None

    url_limpia = (str(url) if url else "").strip()
    item = {
        "titulo": titulo_limpio,
        "url": url_limpia,
        "fuente": limpiar_texto(fuente) or dominio_de_url(url_limpia) or "Desconocida",
        "fecha": fecha_iso(fecha),
        "extracto": limpiar_texto(extracto)[:400],
        "tipo_fuente": tipo_fuente or clasificar_tipo_fuente(url_limpia, fuente, empresa),
        "buscadores": [buscador],
    }
    if extra:
        item.update(extra)
    return item


def ordenar_estable(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Orden canónico: más reciente primero, y a igualdad de fecha por titular.

    Sin un desempate explícito, dos ejecuciones con las mismas noticias podrían
    producir listas distintas según el orden de llegada de los hilos, y el
    informe dejaría de ser reproducible.
    """
    return sorted(items, key=lambda i: (i.get("fecha") or "", i.get("titulo", "")), reverse=True)
