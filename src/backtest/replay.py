"""
Reconstrucción histórica del `FinancialAnalysisState` y ejecución de los
agentes REALES sobre él.

Este módulo es deliberadamente delgado: no contiene una sola regla de decisión.
Su único trabajo es fabricar, para una fecha `t`, un estado indistinguible del
que `node_ingest_and_reconcile` habría producido ese día, y después recorrer el
mismo camino que `build_financial_workflow()`:

    ingest → gatekeeper → [route_after_gatekeeper] → technical → debate → fund_manager

Hallazgo de la Fase 1 en el que se apoya todo lo demás
------------------------------------------------------
En los cuatro agentes el LLM solo sobrescribe campos de texto:

    fundamental.py:65   summary = llm_res.content     (passed_gatekeeper ya calculado, l.29-39)
    technical.py:95     summary = llm_res.content     (momentum_classification ya calculado, l.68-75)
    debate.py:67        synthesis = llm_res.content   (solo texto)
    fund_manager.py:94  summary = llm_res.content     (rating/size/SL/TP ya calculados, l.31-65)

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
    Fuerza el motor heurístico determinista en los cuatro agentes.

    Se parchea el símbolo `get_llm` importado en cada módulo de agente (no
    `src.config.get_llm`), porque `from src.config import get_llm` fija el
    nombre en el espacio del módulo importador.
    """
    for mod in (fund_mod, tech_mod, debate_mod, fm_mod):
        mod.get_llm = lambda: None


def assert_llm_is_decision_neutral() -> Dict[str, Any]:
    """
    Verificación empírica de la hipótesis de la Fase 1.

    Ejecuta los agentes sobre un estado sintético dos veces: una con
    `get_llm() -> None` y otra con un LLM falso que devuelve texto constante y
    reconocible. Si alguna variable de decisión cambia, la hipótesis es falsa y
    el backtest no puede correr en modo heurístico.
    """
    import copy

    class _FakeLLM:
        def invoke(self, prompt):  # noqa: ARG002
            class _R:
                content = "TEXTO_FALSO_DE_VERIFICACION"
            return _R()

    state = _synthetic_state()
    originals = {mod.__name__: mod.get_llm for mod in (fund_mod, tech_mod, debate_mod, fm_mod)}

    def _run(llm_factory):
        for mod in (fund_mod, tech_mod, debate_mod, fm_mod):
            mod.get_llm = llm_factory
        s = copy.deepcopy(state)
        fr = fund_mod.FundamentalAnalystAgent().analyze(s)
        s["fundamental_report"] = fr
        s["passed_fundamental_gatekeeper"] = fr["passed_gatekeeper"]
        if route_after_gatekeeper(s) == "technical_analysis":
            s["technical_report"] = tech_mod.TechnicalAnalystAgent().analyze(s)
            s["debate_report"] = debate_mod.DebateUnitAgent().analyze(s)
        fd = fm_mod.FundManagerAgent().analyze(s)
        return {
            "passed_gatekeeper": fr["passed_gatekeeper"],
            "momentum_classification": s.get("technical_report", {}).get("momentum_classification"),
            "rating": fd["rating"],
            "position_size_pct": fd["position_size_pct"],
            "stop_loss_atr": fd["stop_loss_atr"],
            "take_profit_atr": fd["take_profit_atr"],
        }

    try:
        heuristic = _run(lambda: None)
        with_llm = _run(lambda: _FakeLLM())
    finally:
        for name, fn in originals.items():
            {m.__name__: m for m in (fund_mod, tech_mod, debate_mod, fm_mod)}[name].get_llm = fn

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
    }
    fundamentals = {"revenue_growth": 0.20, "net_margin": 0.15, "debt_to_equity": 1.0,
                    "roe": 0.30, "pe_ratio": 25.0, "market_cap": 0}
    return {
        "ticker": "TEST",
        "yfinance_data": {"status": "SUCCESS", "fundamentals": fundamentals, "technical": tech},
        "reconciliation_data": {
            "status": "SINGLE_VENDOR_FALLBACK", "ticker": "TEST", "confidence_score": 1.0,
            "sources_consulted": ["yfinance"], "discrepancies": [],
            "reconciled_metrics": dict(fundamentals),
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

    @property
    def is_buy(self) -> bool:
        return self.rating in BUY_RATINGS


# Punto medio del rango que emite el Fund Manager (fund_manager.py:45,48).
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
        self.fetcher = DataFetcher()
        self.reconciler = DataReconciler()
        self.fundamental_agent = fund_mod.FundamentalAnalystAgent()
        self.technical_agent = tech_mod.TechnicalAnalystAgent()
        self.debate_agent = debate_mod.DebateUnitAgent()
        self.fund_manager_agent = fm_mod.FundManagerAgent()

        self.skips: Dict[str, int] = {}

    def _skip(self, reason: str) -> None:
        self.skips[reason] = self.skips.get(reason, 0) + 1

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
            fundamentals = {"revenue_growth": 0.0, "net_margin": 0.0, "debt_to_equity": 0.0,
                            "roe": 0.0, "pe_ratio": 0.0, "market_cap": 0,
                            "available": True, "as_of_period_end": None, "filed": None}
            sec_payload = {"status": "NOT_USED", "source": "SEC EDGAR"}
        else:
            fundamentals = self.fundamentals.as_of(ticker, date)
            if not fundamentals.get("available"):
                self._skip("sin_fundamentales")
                return None
            sec_payload = self.fundamentals.sec_payload(ticker, date)

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
            "price_history_summary": {
                "min_52w": float(window["Low"].min()),
                "max_52w": float(window["High"].max()),
                "close_today": float(window["Close"].iloc[-1]),
                "change_1m_pct": float(
                    (window["Close"].iloc[-1] - window["Close"].iloc[-20]) / window["Close"].iloc[-20]
                ) if len(window) >= 20 else 0.0,
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
            target_weight=WEIGHT_BY_RATING.get(decision["rating"], 0.0),
            sector=state["sector"],
            fundamentals_as_of=meta.get("as_of_period_end"),
            fundamentals_filed=meta.get("filed"),
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
