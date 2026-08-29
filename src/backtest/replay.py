"""
Reconstrucción histórica del `FinancialAnalysisState` y ejecución de los
agentes REALES sobre él.

Este módulo es deliberadamente delgado: no contiene una sola regla de decisión.
Su único trabajo es fabricar, para una fecha `t`, un estado indistinguible del
que `node_ingest_and_reconcile` habría producido ese día, y después recorrer el
mismo camino que `build_financial_workflow()`:

    ingest → gatekeeper → [route_after_gatekeeper] → technical → debate → fund_manager

INCLUSIÓN DEL ANALISTA DE CALIDAD
---------------------------------
Desde que la convicción fundamental entra en el rating y en el tamaño de
posición, el `QualityAnalystAgent` es una variable de DECISIÓN y el replay lo
ejecuta como cualquier otro agente. Sus insumos —F-Score de Piotroski, Z-Score
de Altman, ROIC, devengos— se reconstruyen point-in-time en
`FundamentalStore.estados_financieros()`, con el mismo filtro `filed <= t` que
el resto de los fundamentales. Ejecutarlo con datos de hoy habría metido
look-ahead por la puerta de atrás.

Cuando un ticker no tiene estados financieros reconstruibles en la fecha `t`,
el agente devuelve `DATOS_INSUFICIENTES` y el Fund Manager limita el dictamen a
MANTENER. Esa degradación es deliberada: el sistema no debe operar con
convicción que no puede justificar.

EXCLUSIÓN DELIBERADA DEL ANALISTA DE NOTICIAS
---------------------------------------------
El grafo de producción incorpora un nodo `news_analysis` en paralelo al
gatekeeper. **El replay NO lo ejecuta, y esto es una decisión de diseño, no un
olvido.**

Dos de sus tres fuentes (Google News RSS y Tavily) son buscadores "de hoy": no
existe forma asequible de preguntarles qué se publicaba y era visible en una
fecha `t` de 2017. Reconstruir un dosier de prensa histórico con ellos
inyectaría look-ahead por dos vías simultáneas — el corpus indexado hoy excluye
lo que se borró y ordena por relevancia actual, y las fechas de los agregadores
son de republicación, no del hecho. Solo el 8-K con Ítem 2.02 tiene `filed`
exacto y sería reconstruible; con una sola de las tres fuentes el informe no
sería el que produce producción.

Por eso el Analista de Noticias es una CAPA ASESORA: informa al debate y al
informe final, pero no toca `rating` ni `position_size_pct`. Mientras eso se
mantenga, su ausencia en el replay no altera ni una sola señal, y el backtest
sigue midiendo exactamente la lógica que decide en producción. Si alguna vez se
conecta a la decisión, este backtest deja de ser válido hasta que exista un
`NewsStore` point-in-time. Queda declarado en `build_limitations()` y en
`NEXT_STEPS` de `backtest_cli.py`.

Hallazgo de la Fase 1 en el que se apoya todo lo demás
------------------------------------------------------
En los cinco agentes el LLM solo sobrescribe campos de texto, y siempre DESPUÉS
de que las variables de decisión estén fijadas:

    fundamental.py:66   summary = texto      (passed_gatekeeper ya calculado, l.30-40)
    technical.py:95     summary = texto      (momentum_classification ya calculado, l.68-75)
    news.py:370         summary = texto      (probabilidad/categoría/dirección ya calculadas)
    debate.py:101       synthesis = texto    (solo texto)
    fund_manager.py:94  summary = texto      (rating/size/SL/TP ya calculados, l.31-65)

`texto` sale de `src.config.texto_de_respuesta_llm()`, que aplana la respuesta
del proveedor a cadena y devuelve None si no hay nada utilizable — en ese caso
se conserva el resumen determinista. Es un ajuste de formato, no de contenido:
no puede introducir dependencia del LLM en ninguna decisión.

Ninguna variable de decisión depende del LLM. Por tanto ejecutar con
`get_llm() -> None` produce EXACTAMENTE los mismos ratings que producción, de
forma determinista, reproducible y a coste cero. `disable_llm()` lo garantiza y
`assert_llm_is_decision_neutral()` lo verifica en tiempo de ejecución en vez de
confiar en la lectura del código.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

import src.agents.debate as debate_mod
import src.agents.fund_manager as fm_mod
import src.agents.fundamental as fund_mod
import src.agents.news as news_mod
import src.agents.quality as quality_mod
import src.agents.technical as tech_mod
from src.data.fetcher import DataFetcher
from src.data.reconciler import DataReconciler
from src.graph.workflow import route_after_gatekeeper

# Filas mínimas en la ventana. Con >= 200 sesiones, `min(50, len)` y
# `min(200, len)` de `_add_technical_indicators` resuelven a 50 y 200, que es lo
# que ocurre en producción con `period="1y"` (~252 sesiones). Por debajo de 200
# las medias cambian silenciosamente de definición y el replay dejaría de ser
# fiel: esas fechas se descartan en lugar de producir una señal distinta.
MIN_WINDOW_ROWS = 200

BUY_RATINGS = ("COMPRA FUERTE", "COMPRA")


def disable_llm() -> None:
    """
    Fuerza el motor heurístico determinista en los cinco agentes.

    Se parchea el símbolo `get_llm` importado en cada módulo de agente (no
    `src.config.get_llm`), porque `from src.config import get_llm` fija el
    nombre en el espacio del módulo importador.

    Incluye a `src.agents.news` aunque el replay no ejecute su nodo: la
    verificación de neutralidad sí lo recorre, y dejarlo sin parchear abriría
    una llamada de red y de coste a mitad de un backtest offline.
    """
    for mod in (fund_mod, quality_mod, tech_mod, news_mod, debate_mod, fm_mod):
        mod.get_llm = lambda: None


def assert_llm_is_decision_neutral() -> Dict[str, Any]:
    """
    Verificación empírica de la hipótesis de la Fase 1.

    Ejecuta los agentes sobre un estado sintético dos veces: una con
    `get_llm() -> None` y otra con un LLM falso que devuelve texto constante y
    reconocible. Si alguna variable de decisión cambia, la hipótesis es falsa y
    el backtest no puede correr en modo heurístico.

    Cobertura del Analista de Noticias
    ---------------------------------
    El recorrido incluye al `NewsAnalystAgent` aunque el replay no ejecute su
    nodo, y lo hace por dos motivos distintos:

      1. Verificar que su propio dictamen (`impact_probability`,
         `impact_classification`, `direction_classification`, `catalysts`) es
         independiente del LLM, igual que el de los otros cuatro.
      2. Verificar la premisa que justifica excluirlo del backtest: con un
         `news_report` presente en el estado, `rating`, `position_size_pct` y
         los niveles de stop/objetivo tienen que salir IGUALES que sin él. La
         comparación directa con y sin informe de noticias la hace
         `test_news_report_does_not_alter_decision` en tests/test_news_analyst.py.

    El agente de noticias es puro: consume `state["news_data"]`, que aquí se
    fabrica sintéticamente. No toca la red.
    """
    import copy

    class _FakeLLM:
        def invoke(self, prompt):  # noqa: ARG002
            class _R:
                content = "TEXTO_FALSO_DE_VERIFICACION"
            return _R()

    state = _synthetic_state()
    modulos = (fund_mod, quality_mod, tech_mod, news_mod, debate_mod, fm_mod)
    originals = {mod.__name__: mod.get_llm for mod in modulos}

    def _run(llm_factory):
        for mod in modulos:
            mod.get_llm = llm_factory
        s = copy.deepcopy(state)
        # El nodo de calidad corre ANTES del gatekeeper, igual que en el grafo
        # de producción: sus banderas rojas deben estar en el estado cuando el
        # filtro fundamental se evalúa.
        qr = quality_mod.QualityAnalystAgent().analyze(s)
        s["quality_report"] = qr
        fr = fund_mod.FundamentalAnalystAgent().analyze(s)
        s["fundamental_report"] = fr
        s["passed_fundamental_gatekeeper"] = fr["passed_gatekeeper"]
        # En producción el nodo de noticias corre en paralelo al gatekeeper, así
        # que su informe ya está en el estado cuando se ramifica.
        nr = news_mod.NewsAnalystAgent().analyze(s)
        s["news_report"] = nr
        if route_after_gatekeeper(s) == "technical_analysis":
            s["technical_report"] = tech_mod.TechnicalAnalystAgent().analyze(s)
            s["debate_report"] = debate_mod.DebateUnitAgent().analyze(s)
        fd = fm_mod.FundManagerAgent().analyze(s)
        return {
            "passed_gatekeeper": fr["passed_gatekeeper"],
            "momentum_classification": s.get("technical_report", {}).get("momentum_classification"),
            "rating": fd["rating"],
            "position_size_pct": fd["position_size_pct"],
            "peso_objetivo": fd["peso_objetivo"],
            "stop_loss_atr": fd["stop_loss_atr"],
            "take_profit_atr": fd["take_profit_atr"],
            # Variables de decisión del Analista de Calidad. Se comparan con y
            # sin LLM igual que las demás: desde que alimentan el rating, que
            # sean independientes del modelo deja de ser una propiedad
            # deseable y pasa a ser un requisito del backtest.
            "quality_style": qr["style_classification"],
            "quality_conviccion": (qr.get("conviccion_fundamental") or {}).get("valor"),
            "quality_puntuaciones": tuple(
                (k, qr["puntuaciones"].get(k))
                for k in ("calidad", "valoracion", "crecimiento", "solvencia")
            ),
            "quality_piotroski": qr["piotroski"]["score"],
            "quality_altman": qr["altman"]["z"],
            "quality_banderas": tuple(qr["banderas_rojas"]),
            "news_impact_probability": nr["impact_probability"],
            "news_impact_classification": nr["impact_classification"],
            "news_direction_classification": nr["direction_classification"],
            "news_direction_imbalance": nr["direction_imbalance"],
            "news_catalysts": tuple(
                (c["titular"], c["categoria"], c["direccion"], c["probabilidad_impacto"])
                for c in nr["catalysts"]
            ),
        }

    try:
        heuristic = _run(lambda: None)
        with_llm = _run(lambda: _FakeLLM())
    finally:
        por_nombre = {m.__name__: m for m in modulos}
        for name, fn in originals.items():
            por_nombre[name].get_llm = fn

    diffs = {k: (heuristic[k], with_llm[k]) for k in heuristic if heuristic[k] != with_llm[k]}
    return {
        "neutral": not diffs,
        "heuristic": heuristic,
        "with_llm": with_llm,
        "divergences": diffs,
    }


def _synthetic_state() -> Dict[str, Any]:
    """Estado mínimo que atraviesa la rama aprobada del grafo."""
    tech = {
        "close": 100.0, "rsi": 60.0, "macd": 1.5, "macd_signal": 1.0, "macd_hist": 0.5,
        "bb_upper": 105.0, "bb_lower": 95.0, "atr": 2.0,
        "sma_50": 95.0, "sma_200": 90.0, "volume_rel": 1.2,
        "dist_sma_50_pct": 0.0526, "dist_sma_200_pct": 0.1111,
        "pendiente_sma_50": 0.03, "posicion_rango_52w": 0.75,
        "volatilidad_anual": 0.28, "atr_pct": 0.02,
    }
    fundamentals = {"revenue_growth": 0.20, "net_margin": 0.15, "debt_to_equity": 1.0,
                    "roe": 0.30, "pe_ratio": 25.0, "market_cap": 1.0e10,
                    "gross_margin": 0.55, "operating_margin": 0.25,
                    "price_to_book": 3.0, "ev_to_ebitda": 12.0,
                    "enterprise_value": 1.1e10, "trailing_eps": 4.0,
                    "book_value_per_share": 20.0, "current_ratio": 2.0,
                    "earnings_growth": 0.22, "dividend_yield": 0.01,
                    "free_cashflow": 6.0e8, "operating_cashflow": 9.0e8,
                    "total_debt": 2.0e9}

    # Estados financieros sintéticos de dos ejercicios: sin ellos el Analista
    # de Calidad devolvería DATOS_INSUFICIENTES y la verificación no recorrería
    # ninguna de sus ramas de decisión.
    def _s(v, f=0.85):
        return [v, v * f]

    estados = {
        "disponible": True, "bloques_ok": ["balance", "resultados", "flujos"],
        "bloques_fallidos": [],
        "balance": {
            "activos_totales": _s(1.0e10), "pasivos_totales": _s(4.0e9),
            "patrimonio": _s(6.0e9), "activo_corriente": _s(3.0e9),
            "pasivo_corriente": _s(1.2e9), "beneficios_retenidos": _s(3.5e9),
            "deuda_largo_plazo": _s(1.8e9), "deuda_total": _s(2.0e9),
            "acciones_emitidas": _s(5.0e8, 1.005), "efectivo": _s(1.0e9),
            "inmovilizado": _s(3.0e9), "fondo_comercio": [], "intangibles": [],
        },
        "resultados": {
            "ingresos": _s(5.0e9), "beneficio_bruto": _s(2.75e9), "ebit": _s(1.25e9),
            "beneficio_neto": _s(7.5e8), "gastos_financieros": _s(8.0e7),
            "impuestos": _s(2.0e8), "beneficio_antes_impuestos": _s(9.5e8),
        },
        "flujos": {
            "flujo_operativo": _s(9.0e8), "capex": _s(-3.0e8),
            "flujo_libre": _s(6.0e8), "dividendos_pagados": [], "recompras": [],
        },
    }
    return {
        "ticker": "TEST",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "yfinance_data": {"status": "SUCCESS", "fundamentals": fundamentals,
                          "technical": tech, "estados_financieros": estados,
                          "price_history_summary": {
                              "change_1m_pct": 0.02, "change_3m_pct": 0.06,
                              "change_6m_pct": 0.12, "change_12m_pct": 0.25,
                              "min_52w": 70.0, "max_52w": 110.0,
                              "close_today": 100.0, "sesiones": 252}},
        "sec_edgar_data": {"status": "NOT_USED"},
        "reconciliation_data": {
            "status": "SINGLE_VENDOR_FALLBACK", "ticker": "TEST", "confidence_score": 1.0,
            "sources_consulted": ["yfinance"], "discrepancies": [],
            "reconciled_metrics": dict(fundamentals),
        },
        # Dosier de prensa sintético: fechas fijas y `as_of` fijo, para que la
        # antigüedad (y por tanto el decaimiento) no dependa del día en que se
        # ejecute la verificación.
        "news_data": {
            "status": "SUCCESS", "ticker": "TEST", "empresa": "Test Corp",
            "as_of": "2024-03-15", "ventana_dias": 30,
            "fuentes_ok": ["sec_8k", "google_news_rss"], "fuentes_fallidas": [],
            "desde_cache": False,
            "items": [
                {"titulo": "Test Corp presenta el formulario 8-K (Item 2.02: Results of "
                           "Operations and Financial Condition)",
                 "url": "https://www.sec.gov/Archives/edgar/data/1/x.htm",
                 "fuente": "SEC EDGAR (8-K)", "fecha": "2024-03-14",
                 "extracto": "Presentacion oficial ante la SEC.", "tipo_fuente": "SEC_8K",
                 "buscadores": ["sec_8k"], "n_corroboraciones": 1,
                 "categoria_forzada": "RESULTADOS"},
                {"titulo": "Test Corp beats estimates and raises full-year guidance",
                 "url": "https://www.reuters.com/test", "fuente": "Reuters",
                 "fecha": "2024-03-13", "extracto": "Record revenue and strong demand.",
                 "tipo_fuente": "MEDIO_TIER1", "buscadores": ["google_news_rss"],
                 "n_corroboraciones": 2},
            ],
            "n_brutos": 2, "n_items": 2,
        },
        "logs": [], "passed_fundamental_gatekeeper": False,
    }


# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    ticker: str
    date: pd.Timestamp
    rating: str
    momentum: Optional[str]
    passed_gatekeeper: bool
    close: float
    atr: float
    rsi: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    target_weight: float
    sector: str = "Desconocido"
    fundamentals_as_of: Optional[str] = None
    fundamentals_filed: Optional[str] = None
    # Dictamen del Analista de Calidad. Se arrastra hasta el registro de
    # operaciones para poder atribuir el resultado por estilo de inversión, que
    # es la pregunta que el informe anterior no podía responder: ¿el sistema
    # pierde dinero en valor, en crecimiento o en ambos?
    estilo: Optional[str] = None
    conviccion: Optional[float] = None
    banderas_rojas: int = 0
    # Volatilidad anualizada realizada. La capa de cartera la necesita para
    # estimar la matriz de covarianzas y el ratio de diversificación.
    volatilidad: Optional[float] = None

    @property
    def is_buy(self) -> bool:
        return self.rating in BUY_RATINGS


# El Fund Manager emitía el tamaño como CADENA («8.0% - 10.0%»), así que el
# backtest tenía que mantener su propia tabla de pesos — una regla de decisión
# duplicada fuera de `src/agents/`, justo lo que la arquitectura prohíbe. Ahora
# emite `peso_objetivo` numérico y el replay lo consume directamente. La tabla
# se conserva solo como respaldo para estados antiguos sin ese campo.
WEIGHT_BY_RATING = {"COMPRA FUERTE": 0.09, "COMPRA": 0.055}


class HistoricalReplayer:
    """
    Reproduce la decisión del sistema para (ticker, fecha).

    Modos de datos (`mode`):
      - "pit"            : fundamentales point-in-time de SEC EDGAR. Régimen
                           limpio. Es el resultado principal.
      - "technical_only" : gatekeeper neutralizado (passed=True). Aísla el valor
                           de la capa técnica sin contaminación fundamental.
      - "biased"         : fundamentales de HOY aplicados al pasado. Es lo que
                           haría producción tal cual. LOOK-AHEAD: solo contraste.
    """

    def __init__(self, price_store, fundamental_store, mode: str = "pit",
                 sector_map: Optional[Dict[str, str]] = None):
        if mode not in ("pit", "technical_only", "biased"):
            raise ValueError(f"Modo desconocido: {mode}")
        self.prices = price_store
        self.fundamentals = fundamental_store
        self.mode = mode
        self.sector_map = sector_map or {}

        # Instancias de los componentes REALES.
        # `con_estados_financieros=False`: en el replay los estados vienen de
        # `FundamentalStore.estados_financieros()` reconstruidos point-in-time,
        # nunca de yfinance. Dejar el fetcher pidiéndolos abriría una llamada de
        # red con datos de HOY en mitad de un backtest offline.
        self.fetcher = DataFetcher(con_estados_financieros=False)
        self.reconciler = DataReconciler()
        self.fundamental_agent = fund_mod.FundamentalAnalystAgent()
        self.quality_agent = quality_mod.QualityAnalystAgent()
        self.technical_agent = tech_mod.TechnicalAnalystAgent()
        self.debate_agent = debate_mod.DebateUnitAgent()
        self.fund_manager_agent = fm_mod.FundManagerAgent()

        self.skips: Dict[str, int] = {}

    def _skip(self, reason: str) -> None:
        self.skips[reason] = self.skips.get(reason, 0) + 1

    @staticmethod
    def _retorno(window: pd.DataFrame, sesiones: int) -> Optional[float]:
        """
        Rentabilidad a `sesiones` vista sobre la ventana que termina en `t`.

        Devuelve None —no 0.0— cuando no hay histórico suficiente: el Analista
        Técnico distingue «no evaluable» de «rentabilidad nula» y puntúa cada
        caso de forma distinta.
        """
        if len(window) <= sesiones:
            return None
        base = float(window["Close"].iloc[-1 - sesiones])
        if not base:
            return None
        return round(float(window["Close"].iloc[-1]) / base - 1.0, 4)

    def build_state(self, ticker: str, date: pd.Timestamp) -> Optional[Dict[str, Any]]:
        """Estado equivalente al de `node_ingest_and_reconcile` en la fecha `date`."""
        window = self.prices.window(ticker, date, lookback_days=365)
        if window is None or len(window) < MIN_WINDOW_ROWS:
            self._skip("historia_insuficiente")
            return None

        # Indicadores calculados por la MISMA función que usa producción, sobre
        # una ventana que termina en `date`. Copia defensiva: pandas escribiría
        # las columnas de indicadores sobre el DataFrame cacheado.
        df = self.fetcher._add_technical_indicators(window.copy())
        technical = self.fetcher._extract_latest_tech_metrics(df)

        if self.mode == "technical_only":
            fundamentals = {"revenue_growth": None, "net_margin": None,
                            "debt_to_equity": None, "roe": None, "pe_ratio": None,
                            "market_cap": 0, "available": True,
                            "as_of_period_end": None, "filed": None}
            sec_payload = {"status": "NOT_USED", "source": "SEC EDGAR"}
            estados = {"disponible": False, "bloques_ok": [],
                       "bloques_fallidos": ["balance", "resultados", "flujos"],
                       "balance": {}, "resultados": {}, "flujos": {},
                       "motivo": "modo technical_only: la capa fundamental está neutralizada"}
        else:
            fundamentals = self.fundamentals.as_of(ticker, date)
            if not fundamentals.get("available"):
                self._skip("sin_fundamentales")
                return None
            sec_payload = self.fundamentals.sec_payload(ticker, date)
            # Estados financieros point-in-time para el Analista de Calidad.
            estados = self.fundamentals.estados_financieros(ticker, date)

        yf_data = {
            "status": "SUCCESS",
            "ticker": ticker.upper(),
            "company_name": ticker.upper(),
            "sector": self.sector_map.get(ticker.upper(), "Desconocido"),
            "industry": "Desconocido",
            "current_price": float(window["Close"].iloc[-1]),
            "fundamentals": {k: fundamentals[k] for k in
                             ("revenue_growth", "net_margin", "debt_to_equity", "roe",
                              "pe_ratio", "market_cap")},
            "technical": technical,
            "estados_financieros": estados,
            "price_history_summary": {
                "min_52w": float(window["Low"].min()),
                "max_52w": float(window["High"].max()),
                "close_today": float(window["Close"].iloc[-1]),
                "change_1m_pct": self._retorno(window, 20),
                "change_3m_pct": self._retorno(window, 63),
                "change_6m_pct": self._retorno(window, 126),
                "change_12m_pct": self._retorno(window, 252),
                "sesiones": int(len(window)),
            },
        }

        # Finnhub no ofrece histórico point-in-time gratuito: se declara ausente.
        # Solo altera `confidence_score`, que en la Fase 1 se verificó que no
        # interviene en ninguna decisión (fundamental.py:41-42 únicamente añade
        # un motivo al texto).
        fh_data = {"status": "NOT_AVAILABLE_IN_BACKTEST", "source": "Finnhub"}

        rec = self.reconciler.reconcile(ticker, yf_data, sec_payload, fh_data)

        return {
            "ticker": ticker.upper(),
            "company_name": yf_data["company_name"],
            "sector": yf_data["sector"],
            "industry": yf_data["industry"],
            "yfinance_data": yf_data,
            "sec_edgar_data": sec_payload,
            "finnhub_data": fh_data,
            "reconciliation_data": rec,
            "workflow_status": "INGESTED",
            # Sin `news_data` ni `news_report`: el nodo de noticias queda fuera
            # del replay a propósito (ver el encabezado del módulo). Los agentes
            # que los consultan lo hacen con `.get()` y un valor por defecto, de
            # modo que su ausencia reproduce el comportamiento previo exacto.
            "passed_fundamental_gatekeeper": False,
            "logs": [],
            "_fundamentals_meta": {
                "as_of_period_end": fundamentals.get("as_of_period_end"),
                "filed": fundamentals.get("filed"),
            },
        }

    def signal(self, ticker: str, date) -> Optional[Signal]:
        """Recorre el grafo real y devuelve la señal resultante."""
        date = pd.Timestamp(date)
        state = self.build_state(ticker, date)
        if state is None:
            return None

        # Analista de Calidad: mismo lugar que en el grafo de producción, entre
        # la ingesta y el gatekeeper, para que sus banderas rojas estén
        # disponibles también en la rama de rechazo.
        state["quality_report"] = self.quality_agent.analyze(state)

        if self.mode == "technical_only":
            # Gatekeeper neutralizado: se omite el nodo fundamental y se fuerza
            # la rama aprobada. Los agentes técnico, de debate y fund manager se
            # ejecutan sin modificar.
            state["fundamental_report"] = {
                "passed_gatekeeper": True, "status": "NEUTRALIZADO",
                "metrics": state["reconciliation_data"]["reconciled_metrics"],
                "reasons": [], "confidence_score": 1.0, "discrepancies": [],
                "summary": "Gatekeeper fundamental neutralizado (modo technical_only).",
            }
            state["passed_fundamental_gatekeeper"] = True
        else:
            report = self.fundamental_agent.analyze(state)
            state["fundamental_report"] = report
            state["passed_fundamental_gatekeeper"] = report["passed_gatekeeper"]

        if route_after_gatekeeper(state) == "technical_analysis":
            state["technical_report"] = self.technical_agent.analyze(state)
            state["debate_report"] = self.debate_agent.analyze(state)

        decision = self.fund_manager_agent.analyze(state)

        tech = state["yfinance_data"]["technical"]
        meta = state["_fundamentals_meta"]
        quality = state.get("quality_report", {}) or {}
        return Signal(
            ticker=ticker.upper(),
            date=date,
            rating=decision["rating"],
            momentum=state.get("technical_report", {}).get("momentum_classification"),
            passed_gatekeeper=state["passed_fundamental_gatekeeper"],
            close=float(tech["close"]),
            atr=float(tech["atr"]),
            rsi=float(tech["rsi"]),
            stop_loss=decision["stop_loss_atr"],
            take_profit=decision["take_profit_atr"],
            # Peso numérico emitido por el propio Fund Manager, ya escalado por
            # convicción, volatilidad y presupuesto de riesgo.
            target_weight=decision.get(
                "peso_objetivo", WEIGHT_BY_RATING.get(decision["rating"], 0.0)),
            sector=state["sector"],
            fundamentals_as_of=meta.get("as_of_period_end"),
            fundamentals_filed=meta.get("filed"),
            estilo=quality.get("style_classification"),
            conviccion=(quality.get("conviccion_fundamental") or {}).get("valor"),
            banderas_rojas=len(quality.get("banderas_rojas", [])),
            volatilidad=tech.get("volatilidad_anual"),
        )

    def signals_for_date(self, tickers: List[str], date) -> List[Signal]:
        out = []
        for t in tickers:
            try:
                s = self.signal(t, date)
            except Exception as exc:
                self._skip(f"excepcion:{type(exc).__name__}")
                continue
            if s is not None:
                out.append(s)
        return out
