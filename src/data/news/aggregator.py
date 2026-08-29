"""
Agregador de las tres fuentes de noticias.

Responsabilidades, y ninguna más:

  1. Lanzar los tres buscadores EN PARALELO (son I/O-bound e independientes).
  2. Aislar sus fallos: cada uno tiene su propio try/except y su propio motivo
     declarado, de modo que la caída de uno no tumbe el nodo. Con dos fuentes
     caídas el resultado sigue siendo utilizable y se marca como DEGRADADO.
  3. Deduplicar por URL y por similitud de titular, fusionando en vez de
     duplicar. La corroboración resultante se cuenta y se conserva.
  4. Recortar a la ventana temporal y servir/poblar la caché por (ticker, día).

Aquí NO se puntúa, ni se clasifica, ni se infiere dirección: eso son reglas de
decisión y viven en `src/agents/news.py`, igual que las de los otros cuatro
agentes. Este módulo es la capa de ingesta, el equivalente a
`node_ingest_and_reconcile` para las noticias.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturoExpirado
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.config import (
    NEWS_MAX_ITEMS_PER_SOURCE, NEWS_SIMILARITY_THRESHOLD, NEWS_SOURCE_CREDIBILITY,
    NEWS_TOTAL_TIMEOUT, NEWS_WINDOW_DAYS,
)
from src.data.news import cache as news_cache
from src.data.news import google_news, sec_8k, tavily
from src.data.news.schema import dominio_de_url, ordenar_estable, tokens_titular

# Orden fijo de los buscadores. Determina el orden de `fuentes_ok` en el
# informe; sin él dependería de qué hilo termine antes.
BUSCADORES: List[Tuple[str, Any]] = [
    (sec_8k.NOMBRE, sec_8k),
    (google_news.NOMBRE, google_news),
    (tavily.NOMBRE, tavily),
]


def resolver_nombre_empresa(ticker: str) -> str:
    """
    Del símbolo al nombre largo de la empresa (yfinance).

    Buscar por nombre ("NVIDIA Corporation") da resultados mucho mejores que
    buscar por símbolo ("NVDA"), que colisiona con siglas de cualquier cosa.
    En el grafo de producción este dato ya viene resuelto en el estado por el
    nodo de ingesta; esta función es el repliegue para uso independiente.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return info.get("longName") or info.get("shortName") or ticker
    except Exception as exc:
        print(f"[NewsAggregator] No se pudo resolver el nombre de {ticker}: {exc}")
        return ticker


# --------------------------------------------------------------------------- #
# Deduplicación
# --------------------------------------------------------------------------- #
def _similitud_titulares(a: str, b: str) -> float:
    """Índice de Jaccard sobre las palabras significativas de dos titulares."""
    ta, tb = tokens_titular(a), tokens_titular(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _credibilidad(item: Dict[str, Any]) -> float:
    return NEWS_SOURCE_CREDIBILITY.get(item.get("tipo_fuente", "DESCONOCIDA"), 0.0)


def _fusionar(grupo: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Funde un grupo de ítems que hablan del mismo hecho en uno solo.

    El canónico es el de mayor credibilidad (un 8-K gana a un agregador aunque
    el agregador llegara antes), con la fecha y el titular como desempates para
    que el resultado no dependa del orden de llegada de los hilos.

    La corroboración se mide en DOMINIOS distintos, no en buscadores distintos:
    que Tavily y Google News encuentren el mismo artículo de Reuters no es
    corroboración; que Reuters y Businesswire cuenten el mismo hecho, sí.
    """
    canonico = dict(sorted(
        grupo,
        key=lambda i: (-_credibilidad(i), i.get("fecha") or "", i.get("titulo", "")),
    )[0])

    dominios = sorted({dominio_de_url(i.get("url")) or (i.get("fuente") or "").lower()
                       for i in grupo} - {""})
    buscadores = sorted({b for i in grupo for b in i.get("buscadores", [])})
    fechas = sorted(f for f in (i.get("fecha") for i in grupo) if f)

    canonico["buscadores"] = buscadores
    canonico["fuentes_corroborantes"] = dominios
    canonico["n_corroboraciones"] = max(len(dominios), 1)
    # La fecha del hecho es la primera vez que aparece publicado, no la de la
    # copia más creíble: usar la más antigua evita rejuvenecer noticias viejas
    # que un agregador reposteó ayer.
    canonico["fecha"] = fechas[0] if fechas else canonico.get("fecha")
    # El texto de todas las versiones alimenta la clasificación por palabras
    # clave: un titular escueto más el extracto de otra fuente clasifican mejor.
    canonico["texto_agregado"] = " ".join(
        dict.fromkeys(
            [i.get("titulo", "") for i in grupo] + [i.get("extracto", "") for i in grupo]
        )
    ).strip()
    return canonico


def deduplicar(items: List[Dict[str, Any]],
               umbral: float = NEWS_SIMILARITY_THRESHOLD) -> List[Dict[str, Any]]:
    """
    Agrupa por URL exacta y por similitud de titular, y fusiona cada grupo.

    Se recorre en orden canónico (`ordenar_estable`) para que la asignación a
    grupos sea reproducible: con umbrales de similitud, el orden de visita puede
    cambiar el reparto cuando hay cadenas de titulares parecidos.
    """
    grupos: List[List[Dict[str, Any]]] = []
    por_url: Dict[str, int] = {}

    for item in ordenar_estable(items):
        url = (item.get("url") or "").strip().rstrip("/")
        indice = por_url.get(url) if url else None

        if indice is None:
            for i, grupo in enumerate(grupos):
                if any(_similitud_titulares(item.get("titulo", ""), g.get("titulo", "")) >= umbral
                       for g in grupo):
                    indice = i
                    break

        if indice is None:
            grupos.append([item])
            indice = len(grupos) - 1
        else:
            grupos[indice].append(item)

        if url:
            por_url.setdefault(url, indice)

    return ordenar_estable([_fusionar(g) for g in grupos])


# --------------------------------------------------------------------------- #
# Recolección
# --------------------------------------------------------------------------- #
def _en_ventana(item: Dict[str, Any], corte: str) -> bool:
    """Los ítems sin fecha se conservan: el scorer ya los penaliza por antigüedad."""
    fecha = item.get("fecha")
    return True if not fecha else fecha >= corte


def recolectar(ticker: str, empresa: Optional[str] = None,
               ventana_dias: int = NEWS_WINDOW_DAYS,
               max_items: int = NEWS_MAX_ITEMS_PER_SOURCE,
               as_of: Optional[str] = None,
               usar_cache: bool = True,
               timeout_total: float = NEWS_TOTAL_TIMEOUT) -> Dict[str, Any]:
    """
    Payload de noticias normalizado y deduplicado para `ticker`.

    Nunca lanza: si las tres fuentes fallan devuelve `status="SIN_DATOS"` con la
    lista de motivos. El nodo del grafo debe poder emitir un informe degradado
    antes que romper el análisis del valor.
    """
    ticker = ticker.upper()
    dia = as_of or date.today().isoformat()

    if usar_cache:
        cacheado = news_cache.leer(ticker, dia)
        if cacheado:
            cacheado["desde_cache"] = True
            return cacheado

    empresa = empresa or resolver_nombre_empresa(ticker)

    brutos: List[Dict[str, Any]] = []
    fuentes_ok: List[str] = []
    fuentes_fallidas: List[Dict[str, str]] = []

    # Los tres buscadores son independientes y de red: se lanzan a la vez y se
    # recogen con un presupuesto de tiempo común.
    with ThreadPoolExecutor(max_workers=len(BUSCADORES), thread_name_prefix="news") as pool:
        futuros = {
            nombre: pool.submit(modulo.buscar, empresa, ticker, max_items, ventana_dias)
            for nombre, modulo in BUSCADORES
        }
        limite = datetime.now() + timedelta(seconds=timeout_total)
        for nombre, futuro in futuros.items():
            restante = max((limite - datetime.now()).total_seconds(), 0.1)
            try:
                resultado = futuro.result(timeout=restante)
                brutos.extend(resultado)
                fuentes_ok.append(nombre)
            except FuturoExpirado:
                futuro.cancel()
                fuentes_fallidas.append({"buscador": nombre,
                                         "motivo": f"tiempo agotado ({timeout_total:.0f}s)"})
            except Exception as exc:
                fuentes_fallidas.append({"buscador": nombre,
                                         "motivo": f"{type(exc).__name__}: {exc}"})

    corte = (date.fromisoformat(dia) - timedelta(days=ventana_dias)).isoformat()
    en_ventana = [i for i in brutos if _en_ventana(i, corte)]
    items = deduplicar(en_ventana)

    if fuentes_ok and fuentes_fallidas:
        estado = "DEGRADADO"
    elif fuentes_ok:
        estado = "SUCCESS"
    else:
        estado = "SIN_DATOS"

    payload = {
        "status": estado,
        "ticker": ticker,
        "empresa": empresa,
        "as_of": dia,
        "ventana_dias": ventana_dias,
        "items": items,
        "n_brutos": len(brutos),
        "n_items": len(items),
        "fuentes_ok": fuentes_ok,
        "fuentes_fallidas": fuentes_fallidas,
        "desde_cache": False,
    }

    if usar_cache and estado != "SIN_DATOS":
        news_cache.escribir(ticker, payload, dia)
    return payload
