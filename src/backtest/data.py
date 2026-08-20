"""
Capa de datos point-in-time para el backtest.

Dos almacenes, ambos con caché en disco para que el backtest sea reejecutable
offline y bit a bit reproducible:

- `PriceStore`      : OHLCV ajustado por splits/dividendos (yfinance), una única
                      descarga por ticker cubriendo todo el periodo de estudio.
- `FundamentalStore`: fundamentales reconstruidos desde SEC EDGAR companyfacts
                      filtrando por el campo `filed` (no por `end`), que es lo
                      único que elimina el look-ahead fundamental.

NOTA CRÍTICA SOBRE `filed` vs `end`
-----------------------------------
`src/data/sec_edgar.py::_extract_recent_fact` ordena los hechos XBRL por `end`
(fin del periodo contable) y toma el más reciente. El periodo fiscal que termina
el 31-dic-2023 no es público hasta que se presenta el 10-K, típicamente en
feb-2024. Usar `end` en un backtest permite operar en enero con cifras que nadie
conocía. Aquí se filtra siempre por `filed <= t`, y cuando un hecho carece de
`filed` se le aplica un retardo mínimo de 45 días naturales sobre `end`.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
import yfinance as yf

from src.config import SEC_EDGAR_USER_AGENT

CACHE_ROOT = Path(os.getenv("BACKTEST_CACHE_DIR", "data/cache"))
PRICE_CACHE = CACHE_ROOT / "prices"
SEC_CACHE = CACHE_ROOT / "sec"

# Retardo mínimo asumido entre el cierre del periodo contable y su publicación
# cuando el hecho XBRL no trae fecha `filed`.
MIN_REPORTING_LAG_DAYS = 45

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Conceptos us-gaap ordenados por preferencia.
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]
NET_INCOME_CONCEPTS = ["NetIncomeLoss", "ProfitLoss"]
EQUITY_CONCEPTS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
# Deuda financiera, para aproximar la definición de `debtToEquity` de yfinance
# (deuda con coste, no pasivo total).
DEBT_CURRENT_CONCEPTS = ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"]
DEBT_NONCURRENT_CONCEPTS = ["LongTermDebtNoncurrent", "LongTermDebt"]


def _ensure_dirs() -> None:
    PRICE_CACHE.mkdir(parents=True, exist_ok=True)
    SEC_CACHE.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Precios
# --------------------------------------------------------------------------- #
class PriceStore:
    """OHLCV ajustado, descargado una vez y servido desde disco."""

    def __init__(self, cache_dir: Path = PRICE_CACHE, offline: bool = False):
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self._mem: Dict[str, pd.DataFrame] = {}
        _ensure_dirs()

    # Colchón previo a `start` para que el primer rebalanceo disponga de la
    # misma ventana de 1 año que usa producción.
    WARMUP_DAYS = 400

    def _path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}.csv"

    def _meta_path(self, ticker: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}.meta.json"

    def _covers(self, ticker: str, dl_start: pd.Timestamp, end: pd.Timestamp) -> bool:
        """
        ¿Cubre la descarga cacheada el rango pedido?

        Se compara contra el rango SOLICITADO al descargar, no contra las fechas
        presentes en el CSV: un valor que salió a bolsa en 2019 nunca tendrá
        filas de 2015 por muchas veces que se pida, y reintentarlo en cada
        ejecución sería un bucle de descargas inútiles.

        Sin este control, una ejecución previa con un `--start` posterior deja
        en caché un histórico truncado que las siguientes reutilizan en
        silencio, recortando el periodo de estudio sin avisar.
        """
        meta_path = self._meta_path(ticker)
        if not meta_path.exists():
            return False
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            return (pd.Timestamp(meta["requested_start"]) <= dl_start
                    and pd.Timestamp(meta["requested_end"]) >= end)
        except Exception:
            return False

    def load(self, ticker: str, start: str, end: str) -> Optional[pd.DataFrame]:
        """
        Devuelve el histórico completo cacheado del ticker (no recortado a
        [start, end]: el backtest necesita el año previo a `start` como warm-up
        de los indicadores).
        """
        ticker = ticker.upper()
        dl_start = pd.Timestamp(start) - pd.Timedelta(days=self.WARMUP_DAYS)
        end_ts = pd.Timestamp(end)

        if ticker in self._mem:
            return self._mem[ticker]

        path = self._path(ticker)
        cached_ok = path.exists() and self._covers(ticker, dl_start, end_ts)

        if cached_ok:
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            if not df.empty:
                self._mem[ticker] = df
                return df

        if self.offline:
            if path.exists():
                df = pd.read_csv(path, index_col=0, parse_dates=True)
                if not df.empty:
                    print(f"[PriceStore] AVISO: {ticker} en caché no cubre "
                          f"{dl_start.date()}→{end_ts.date()}; se usa lo disponible "
                          f"({df.index.min().date()}→{df.index.max().date()}). "
                          f"Reejecuta sin --offline para completarlo.")
                    self._mem[ticker] = df
                    return df
            return None

        try:
            df = yf.Ticker(ticker).history(
                start=dl_start.strftime("%Y-%m-%d"),
                end=end_ts.strftime("%Y-%m-%d"), auto_adjust=True)
        except Exception as exc:  # pragma: no cover - depende de la red
            print(f"[PriceStore] Error descargando {ticker}: {exc}")
            return None

        if df is None or df.empty:
            print(f"[PriceStore] Sin precios para {ticker}")
            return None

        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df.to_csv(path)
        self._meta_path(ticker).write_text(json.dumps({
            "requested_start": dl_start.strftime("%Y-%m-%d"),
            "requested_end": end_ts.strftime("%Y-%m-%d"),
            "rows": int(len(df)),
            "first_bar": df.index.min().strftime("%Y-%m-%d"),
            "last_bar": df.index.max().strftime("%Y-%m-%d"),
        }), encoding="utf-8")
        self._mem[ticker] = df
        return df

    def window(self, ticker: str, as_of: pd.Timestamp, lookback_days: int = 365) -> Optional[pd.DataFrame]:
        """
        Ventana histórica que TERMINA en `as_of` (inclusive), replicando
        `stock.history(period="1y")` de producción.

        Devuelve None si no hay historia suficiente. El corte por fecha es el
        único blindaje real contra look-ahead técnico: ninguna fila posterior a
        `as_of` entra jamás en el cálculo de indicadores.
        """
        df = self._mem.get(ticker.upper())
        if df is None:
            return None
        lo = as_of - pd.Timedelta(days=lookback_days)
        win = df.loc[(df.index > lo) & (df.index <= as_of)]
        return win if not win.empty else None


# --------------------------------------------------------------------------- #
# Fundamentales point-in-time
# --------------------------------------------------------------------------- #
@dataclass
class Fact:
    end: pd.Timestamp
    start: Optional[pd.Timestamp]
    val: float
    filed: pd.Timestamp
    form: str

    @property
    def duration_days(self) -> Optional[int]:
        if self.start is None:
            return None
        return int((self.end - self.start).days)


class FundamentalStore:
    """
    Reconstruye fundamentales anuales conocibles en una fecha dada, desde los
    companyfacts de SEC EDGAR.

    Divergencia documentada frente a producción: producción lee TTM de
    `yfinance.info`; aquí se usan cifras ANUALES (10-K) point-in-time. No existe
    forma de obtener el TTM histórico de yfinance retroactivamente, así que esta
    es la aproximación insesgada más cercana. Ambos miden lo mismo con distinta
    ventana, y la diferencia se declara en el informe.
    """

    def __init__(self, cache_dir: Path = SEC_CACHE, offline: bool = False,
                 user_agent: str = SEC_EDGAR_USER_AGENT):
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.headers = {"User-Agent": user_agent}
        self._facts: Dict[str, Dict[str, List[Fact]]] = {}
        self._cik_map: Optional[Dict[str, str]] = None
        _ensure_dirs()

    # ---------------- CIK ----------------
    def _load_cik_map(self) -> Dict[str, str]:
        if self._cik_map is not None:
            return self._cik_map
        path = self.cache_dir / "_company_tickers.json"
        data = None
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        elif not self.offline:
            try:
                r = requests.get(SEC_TICKERS_URL, headers=self.headers, timeout=15)
                if r.status_code == 200:
                    data = r.json()
                    path.write_text(json.dumps(data), encoding="utf-8")
            except Exception as exc:  # pragma: no cover
                print(f"[FundamentalStore] Error obteniendo mapa CIK: {exc}")
        self._cik_map = {}
        if data:
            for item in data.values():
                self._cik_map[str(item.get("ticker", "")).upper()] = str(item.get("cik_str")).zfill(10)
        return self._cik_map

    # ---------------- companyfacts ----------------
    def _raw_facts(self, ticker: str) -> Optional[Dict[str, Any]]:
        ticker = ticker.upper()
        path = self.cache_dir / f"{ticker}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        if self.offline:
            return None
        cik = self._load_cik_map().get(ticker)
        if not cik:
            path.write_text(json.dumps({"_unavailable": "cik_not_found"}), encoding="utf-8")
            return None
        try:
            time.sleep(0.15)  # SEC pide <= 10 req/s
            r = requests.get(SEC_FACTS_URL.format(cik=cik), headers=self.headers, timeout=30)
            if r.status_code != 200:
                return None
            data = r.json()
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as exc:  # pragma: no cover
            print(f"[FundamentalStore] Error companyfacts {ticker}: {exc}")
            return None

    def _parse(self, ticker: str) -> Dict[str, List[Fact]]:
        ticker = ticker.upper()
        if ticker in self._facts:
            return self._facts[ticker]

        raw = self._raw_facts(ticker)
        out: Dict[str, List[Fact]] = {}
        if not raw or "_unavailable" in raw:
            self._facts[ticker] = out
            return out

        gaap = raw.get("facts", {}).get("us-gaap", {})
        wanted = set(
            REVENUE_CONCEPTS + NET_INCOME_CONCEPTS + EQUITY_CONCEPTS
            + DEBT_CURRENT_CONCEPTS + DEBT_NONCURRENT_CONCEPTS + ["Assets", "Liabilities"]
        )
        for concept in wanted & set(gaap.keys()):
            items = gaap[concept].get("units", {}).get("USD", [])
            parsed: List[Fact] = []
            for it in items:
                try:
                    end = pd.Timestamp(it["end"])
                except Exception:
                    continue
                start = None
                if it.get("start"):
                    try:
                        start = pd.Timestamp(it["start"])
                    except Exception:
                        start = None
                filed_raw = it.get("filed")
                if filed_raw:
                    try:
                        filed = pd.Timestamp(filed_raw)
                    except Exception:
                        filed = end + pd.Timedelta(days=MIN_REPORTING_LAG_DAYS)
                else:
                    filed = end + pd.Timedelta(days=MIN_REPORTING_LAG_DAYS)
                # Blindaje: nunca aceptar un `filed` anterior al cierre del periodo.
                if filed < end:
                    filed = end + pd.Timedelta(days=MIN_REPORTING_LAG_DAYS)
                try:
                    val = float(it.get("val"))
                except (TypeError, ValueError):
                    continue
                parsed.append(Fact(end=end, start=start, val=val, filed=filed,
                                   form=str(it.get("form", ""))))
            if parsed:
                out[concept] = parsed

        self._facts[ticker] = out
        return out

    # ---------------- selección point-in-time ----------------
    @staticmethod
    def _annual(facts: List[Fact], as_of: pd.Timestamp) -> List[Fact]:
        """Hechos de flujo anuales (330-400 días) ya publicados en `as_of`."""
        vis = [f for f in facts if f.filed <= as_of]
        ann = [f for f in vis if f.duration_days and 330 <= f.duration_days <= 400]
        return ann

    @staticmethod
    def _dedup_latest_filed(facts: List[Fact]) -> Dict[pd.Timestamp, Fact]:
        """Un valor por fecha de cierre: el último presentado (posible restatement)."""
        best: Dict[pd.Timestamp, Fact] = {}
        for f in facts:
            cur = best.get(f.end)
            if cur is None or f.filed > cur.filed:
                best[f.end] = f
        return best

    def _flow_series(self, ticker: str, concepts: List[str], as_of: pd.Timestamp) -> List[Fact]:
        parsed = self._parse(ticker)
        for concept in concepts:
            if concept not in parsed:
                continue
            ann = self._annual(parsed[concept], as_of)
            if len(ann) >= 1:
                best = self._dedup_latest_filed(ann)
                return sorted(best.values(), key=lambda f: f.end, reverse=True)
        return []

    def _instant(self, ticker: str, concepts: List[str], as_of: pd.Timestamp) -> Optional[float]:
        """Hecho de stock (balance) más reciente ya publicado en `as_of`."""
        parsed = self._parse(ticker)
        for concept in concepts:
            if concept not in parsed:
                continue
            vis = [f for f in parsed[concept] if f.filed <= as_of and f.duration_days is None]
            if not vis:
                vis = [f for f in parsed[concept] if f.filed <= as_of]
            if vis:
                best = self._dedup_latest_filed(vis)
                latest = max(best.values(), key=lambda f: f.end)
                return latest.val
        return None

    def _instant_sum(self, ticker: str, concepts: List[str], as_of: pd.Timestamp) -> float:
        total = 0.0
        for concept in concepts:
            v = self._instant(ticker, [concept], as_of)
            if v is not None:
                total += v
        return total

    def as_of(self, ticker: str, date) -> Dict[str, Any]:
        """
        Fundamentales conocibles en `date`, en el mismo formato y con las mismas
        claves que `DataFetcher.fetch_all()["fundamentals"]`.

        `available=False` cuando EDGAR no aporta lo suficiente. El motor NO debe
        operar tickers sin fundamentales en modo point-in-time: hacerlo
        reintroduciría el sesgo que este módulo existe para eliminar.
        """
        as_of = pd.Timestamp(date)
        empty = {
            "revenue_growth": 0.0, "net_margin": 0.0, "debt_to_equity": 0.0,
            "roe": 0.0, "pe_ratio": 0.0, "market_cap": 0,
            "available": False, "as_of_period_end": None, "filed": None,
        }

        revs = self._flow_series(ticker, REVENUE_CONCEPTS, as_of)
        nets = self._flow_series(ticker, NET_INCOME_CONCEPTS, as_of)
        if not revs or not nets:
            return empty

        rev_cur = revs[0]
        # Ejercicio anterior: cierre entre 300 y 430 días antes del actual.
        rev_prev = next(
            (f for f in revs[1:] if 300 <= (rev_cur.end - f.end).days <= 430), None
        )
        if rev_prev is None or rev_prev.val <= 0 or rev_cur.val <= 0:
            return empty

        revenue_growth = rev_cur.val / rev_prev.val - 1.0

        # Beneficio neto del mismo ejercicio que los ingresos (tolerancia ±20 días).
        net_cur = next((f for f in nets if abs((f.end - rev_cur.end).days) <= 20), None)
        if net_cur is None:
            return empty
        net_margin = net_cur.val / rev_cur.val

        equity = self._instant(ticker, EQUITY_CONCEPTS, as_of)
        debt = (self._instant_sum(ticker, DEBT_CURRENT_CONCEPTS, as_of)
                + self._instant_sum(ticker, DEBT_NONCURRENT_CONCEPTS, as_of))

        # Producción hace `info.get("debtToEquity", 0.0)`: cuando el dato falta,
        # vale 0.0 y el filtro de deuda pasa. Se replica ese comportamiento en
        # lugar de inventar un valor, para no introducir una divergencia.
        debt_to_equity = 0.0
        roe = 0.0
        if equity and equity > 0:
            debt_to_equity = debt / equity if debt > 0 else 0.0
            roe = net_cur.val / equity

        return {
            "revenue_growth": float(revenue_growth),
            "net_margin": float(net_margin),
            "debt_to_equity": float(debt_to_equity),
            "roe": float(roe),
            "pe_ratio": 0.0,  # no interviene en la decisión; solo en texto del debate
            "market_cap": 0,
            "available": True,
            "as_of_period_end": rev_cur.end.strftime("%Y-%m-%d"),
            "filed": max(rev_cur.filed, net_cur.filed).strftime("%Y-%m-%d"),
        }

    def sec_payload(self, ticker: str, date) -> Dict[str, Any]:
        """Equivalente point-in-time de `SECEdgarClient.get_fundamental_facts()`."""
        as_of = pd.Timestamp(date)
        revs = self._flow_series(ticker, REVENUE_CONCEPTS, as_of)
        nets = self._flow_series(ticker, NET_INCOME_CONCEPTS, as_of)
        if not revs or not nets:
            return {"status": "NOT_FOUND", "source": "SEC EDGAR (point-in-time)"}
        return {
            "status": "SUCCESS",
            "source": "SEC EDGAR (point-in-time)",
            "revenues": revs[0].val,
            "net_income": nets[0].val,
            "total_assets": self._instant(ticker, ["Assets"], as_of),
            "total_liabilities": self._instant(ticker, ["Liabilities"], as_of),
        }


# --------------------------------------------------------------------------- #
# Fundamentales "de hoy" (régimen SESGADO, solo para contraste)
# --------------------------------------------------------------------------- #
class TodayFundamentalStore:
    """
    Lee `yfinance.info` una vez por ticker y devuelve el MISMO valor para
    cualquier fecha histórica. Es exactamente lo que hace producción y es
    look-ahead puro: en 2016 nadie conocía el margen TTM de 2026.

    Existe únicamente para cuantificar cuánto infla el sesgo los resultados.
    Todo output generado con este almacén va etiquetado como SESGADO.
    """

    def __init__(self, cache_dir: Path = CACHE_ROOT / "today", offline: bool = False):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self._mem: Dict[str, Dict[str, Any]] = {}

    def as_of(self, ticker: str, date) -> Dict[str, Any]:  # noqa: ARG002 - fecha ignorada a propósito
        ticker = ticker.upper()
        if ticker in self._mem:
            return dict(self._mem[ticker])

        path = self.cache_dir / f"{ticker}.json"
        info: Dict[str, Any] = {}
        if path.exists():
            info = json.loads(path.read_text(encoding="utf-8"))
        elif not self.offline:
            try:
                info = yf.Ticker(ticker).info or {}
                path.write_text(json.dumps({k: v for k, v in info.items()
                                            if isinstance(v, (int, float, str, bool, type(None)))}),
                                encoding="utf-8")
            except Exception as exc:  # pragma: no cover
                print(f"[TodayFundamentalStore] {ticker}: {exc}")
                info = {}

        dte = info.get("debtToEquity") or 0.0
        if dte and dte > 10:
            dte = dte / 100.0
        out = {
            "revenue_growth": float(info.get("revenueGrowth") or 0.0),
            "net_margin": float(info.get("profitMargins") or 0.0),
            "debt_to_equity": float(dte),
            "roe": float(info.get("returnOnEquity") or 0.0),
            "pe_ratio": float(info.get("trailingPE") or info.get("forwardPE") or 0.0),
            "market_cap": info.get("marketCap", 0),
            "available": bool(info),
            "as_of_period_end": "TODAY (SESGADO)",
            "filed": "TODAY (SESGADO)",
        }
        self._mem[ticker] = out
        return dict(out)

    def sec_payload(self, ticker: str, date) -> Dict[str, Any]:  # noqa: ARG002
        return {"status": "NOT_USED", "source": "SEC EDGAR"}


def trading_calendar(price_store: PriceStore, tickers: List[str],
                     start: str, end: str) -> pd.DatetimeIndex:
    """Unión de las fechas de cotización de todos los tickers, recortada a [start, end]."""
    idx = pd.DatetimeIndex([])
    for t in tickers:
        df = price_store._mem.get(t.upper())
        if df is not None:
            idx = idx.union(df.index)
    return idx[(idx >= pd.Timestamp(start)) & (idx <= pd.Timestamp(end))]


def rebalance_dates(calendar: pd.DatetimeIndex, freq: str = "monthly") -> List[pd.Timestamp]:
    """Última sesión de cada mes/semana. La señal se calcula con el cierre de esa sesión."""
    if len(calendar) == 0:
        return []
    s = pd.Series(calendar, index=calendar)
    rule = {"monthly": "ME", "weekly": "W-FRI", "quarterly": "QE"}.get(freq)
    if rule is None:
        raise ValueError(f"Frecuencia de rebalanceo no soportada: {freq}")
    return [d for d in s.resample(rule).last().dropna().tolist()]
