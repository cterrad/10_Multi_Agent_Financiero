"""
Tools de extracción y reconciliación de datos.

Son las ÚNICAS tools del sistema que tocan la red. Esa separación es
deliberada y ya existía en el diseño: `node_ingest_and_reconcile` consulta a los
proveedores una sola vez y todos los agentes posteriores consumen el estado ya
reconciliado sin volver a salir. Convertir la ingesta en tools no cambia esa
propiedad —la cambia de sitio— y por eso este módulo está separado del resto:
mirando los imports de un agente se sabe si puede o no hacer una petición.

Ninguna fuente es obligatoria salvo yfinance. La ausencia de Finnhub o un fallo
de la SEC bajan la confianza y se declaran en `sources_consulted`, pero no
detienen el flujo: un valor no se deja de analizar porque un proveedor no
conteste.
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.data.fetcher import DataFetcher
from src.data.finnhub_client import FinnhubClient
from src.data.reconciler import DataReconciler
from src.data.sec_edgar import SECEdgarClient

# Instancias de módulo: los clientes son baratos de crear pero mantienen sesión
# HTTP y caché en memoria, así que compartirlos evita repetir handshakes.
_fetcher = DataFetcher()
_fetcher_sin_estados = DataFetcher(con_estados_financieros=False)
_sec = SECEdgarClient()
_finnhub = FinnhubClient()
_reconciler = DataReconciler()


@tool("obtener_datos_yfinance")
def obtener_datos_yfinance(ticker: str,
                           con_estados_financieros: bool = True) -> Dict[str, Any]:
    """Descarga de yfinance precios, indicadores técnicos y ratios fundamentales.

    Devuelve cuatro bloques: `fundamentals` (ratios TTM), `technical`
    (RSI, MACD, Bollinger, medias, ATR, volatilidad), `price_history_summary`
    (rentabilidades a 1, 3, 6 y 12 meses) y `estados_financieros` (balance,
    resultados y flujos por ejercicio) cuando se piden.

    Toda magnitud que yfinance no publique viaja como `None` y se declara en
    `campos_ausentes`. Nunca como cero: una empresa sin cobertura de datos y
    otra realmente sin ingresos no pueden producir el mismo veredicto.

    HACE UNA PETICIÓN DE RED.
    """
    f = _fetcher if con_estados_financieros else _fetcher_sin_estados
    return f.fetch_all(ticker)


@tool("obtener_hechos_sec")
def obtener_hechos_sec(ticker: str, as_of: Optional[str] = None) -> Dict[str, Any]:
    """Hechos financieros XBRL de SEC EDGAR (`companyfacts`).

    Cifras presentadas ante el regulador, con su fecha de presentación (`filed`)
    además de la de cierre (`end`). Esa distinción es la que hace posible el
    backtest: un ejercicio cerrado el 31 de diciembre no es público hasta el
    10-K de febrero.

    `as_of` (YYYY-MM-DD) filtra por `filed <= as_of` y deduplica reexpresiones
    quedándose con la presentación más reciente de cada cierre. En producción se
    omite —la pregunta es qué se sabe hoy—; existe para que una consulta
    histórica no reintroduzca look-ahead por descuido.

    HACE UNA PETICIÓN DE RED.
    """
    return _sec.get_fundamental_facts(ticker, as_of=as_of) if as_of \
        else _sec.get_fundamental_facts(ticker)


@tool("obtener_datos_finnhub")
def obtener_datos_finnhub(ticker: str) -> Dict[str, Any]:
    """Métricas básicas de Finnhub, como tercera fuente de contraste.

    Opcional: requiere `FINNHUB_API_KEY`. Sin clave devuelve un estado de no
    configurado, lo que baja la confianza de la reconciliación pero no detiene
    nada. Su valor está en el contraste, no en el dato: dos fuentes que
    coinciden dan más confianza que una sola que afirma.

    HACE UNA PETICIÓN DE RED.
    """
    return _finnhub.get_basic_financials(ticker)


@tool("reconciliar_fuentes")
def reconciliar_fuentes(ticker: str, datos_yfinance: Dict[str, Any],
                        hechos_sec: Dict[str, Any],
                        datos_finnhub: Dict[str, Any]) -> Dict[str, Any]:
    """Cruza las tres fuentes y emite las métricas de consenso con su confianza.

    Para cada magnitud coincidente elige un valor, registra de qué proveedor
    salió (`procedencia`) y anota las discrepancias. El `confidence_score`
    resultante, acotado en [0.4, 1.0], penaliza dos cosas distintas: que las
    fuentes se contradigan y que falten datos. Penalizar solo lo primero
    producía el absurdo de declarar SINGLE_VENDOR_FALLBACK con una confianza
    del 100%.

    Es cálculo puro: no toca la red.
    """
    return _reconciler.reconcile(ticker, datos_yfinance, hechos_sec, datos_finnhub)


@tool("obtener_noticias")
def obtener_noticias(ticker: str, empresa: Optional[str] = None) -> Dict[str, Any]:
    """Dosier de prensa reciente, deduplicado y con la procedencia de cada ítem.

    Tres buscadores en paralelo: 8-K de la SEC con Ítem 2.02, Google News RSS y
    Tavily (requiere `TAVILY_API_KEY` y el paquete `langchain-tavily`). Cada uno
    con su propio try/except: el peor caso es un dosier vacío con los motivos,
    nunca una excepción que tumbe el análisis.

    Deduplica por URL y por similitud de titulares, y cuenta la corroboración en
    DOMINIOS distintos, no en buscadores distintos: tres agregadores citando la
    misma nota de prensa son una fuente, no tres.

    HACE PETICIONES DE RED. La caché es diaria porque las noticias son un dato
    de hoy.
    """
    from src.data.news import recolectar
    return recolectar(ticker, empresa=empresa or ticker)


@tool("obtener_benchmark")
def obtener_benchmark(ticker: str = "SPY") -> Dict[str, Any]:
    """Rentabilidades del índice de referencia, para medir momentum RELATIVO.

    Sin esta referencia, «el valor sube un 20% a doce meses» no distingue
    habilidad de selección de simple exposición al mercado — que es exactamente
    la crítica que el contraste de Monte Carlo del backtest hace a la
    estrategia. Un fallo devuelve un diccionario vacío y el sistema degrada a
    momentum absoluto declarándolo, en lugar de detenerse.

    HACE UNA PETICIÓN DE RED.
    """
    datos = _fetcher_sin_estados.fetch_all(ticker)
    if datos.get("status") != "SUCCESS":
        return {}
    resumen = datos.get("price_history_summary", {}) or {}
    return {
        "ticker": ticker.upper(),
        "change_1m_pct": resumen.get("change_1m_pct"),
        "change_3m_pct": resumen.get("change_3m_pct"),
        "change_6m_pct": resumen.get("change_6m_pct"),
        "change_12m_pct": resumen.get("change_12m_pct"),
        "volatilidad_anual": (datos.get("technical", {}) or {}).get("volatilidad_anual"),
    }


TOOLS_EXTRACCION = [
    obtener_datos_yfinance,
    obtener_hechos_sec,
    obtener_datos_finnhub,
    reconciliar_fuentes,
    obtener_noticias,
    obtener_benchmark,
]

# Subconjunto expuesto al agente investigador: consultan datos, no los alteran.
# `obtener_noticias` queda fuera a propósito — es la fuente más lenta y la que
# más cuota consume, y el investigador razona sobre fundamentales.
TOOLS_EXTRACCION_LECTURA = [
    obtener_datos_yfinance,
    obtener_hechos_sec,
    obtener_benchmark,
]
