"""
Ingesta de precios, indicadores técnicos y fundamentales desde yfinance.

Tres defectos verificados que este módulo corrige respecto de la versión
anterior, y que conviene no reintroducir:

1. `info.get("revenueGrowth", 0.0)` convertía la AUSENCIA de dato en un cero
   contable. El gatekeeper rechazaba después la empresa por «crecimiento 0.0%
   por debajo del umbral», afirmando un hecho que nadie había medido. Ahora
   todo campo ausente viaja como `None` y se declara en `campos_ausentes`.

2. `if debt_to_equity > 10: debt_to_equity /= 100` intentaba adivinar la unidad.
   yfinance devuelve `debtToEquity` SIEMPRE en porcentaje, así que la regla
   funcionaba para las empresas apalancadas y fallaba justo en las sanas: una
   compañía con un 8% de deuda sobre patrimonio se leía como 8.0x y el
   gatekeeper la rechazaba por exceso de apalancamiento. Ahora se divide
   siempre entre 100 y se conserva el valor bruto para auditoría.

3. `info.get("trailingPE", info.get("forwardPE", 0.0))` mezclaba dos métricas
   distintas sin dejar rastro de cuál se había usado. Ahora se publican por
   separado y `pe_origen` dice cuál alimentó la decisión.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from typing import Any, Dict, List, Optional

# Campos de `yfinance.info` que se recogen tal cual, con el nombre interno que
# usará el resto del sistema. La lista es explícita a propósito: un `info`
# completo trae ~150 claves de estabilidad desigual y solo estas se auditan.
CAMPOS_INFO = {
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "net_margin": "profitMargins",
    "gross_margin": "grossMargins",
    "operating_margin": "operatingMargins",
    "ebitda_margin": "ebitdaMargins",
    "roe": "returnOnEquity",
    "roa": "returnOnAssets",
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "price_to_book": "priceToBook",
    "price_to_sales": "priceToSalesTrailing12Months",
    "enterprise_value": "enterpriseValue",
    "ev_to_ebitda": "enterpriseToEbitda",
    "ev_to_revenue": "enterpriseToRevenue",
    "ebitda": "ebitda",
    "market_cap": "marketCap",
    "shares_outstanding": "sharesOutstanding",
    "book_value_per_share": "bookValue",
    "trailing_eps": "trailingEps",
    "forward_eps": "forwardEps",
    "free_cashflow": "freeCashflow",
    "operating_cashflow": "operatingCashflow",
    "total_cash": "totalCash",
    "total_debt": "totalDebt",
    "total_revenue": "totalRevenue",
    "current_ratio": "currentRatio",
    "quick_ratio": "quickRatio",
    "beta": "beta",
    "dividend_yield": "dividendYield",
    "payout_ratio": "payoutRatio",
    "held_percent_insiders": "heldPercentInsiders",
    "short_percent_of_float": "shortPercentOfFloat",
}

# Filas de los estados financieros anuales que alimentan Piotroski, Altman,
# ROIC y el ratio de devengos. Cada entrada lista los nombres alternativos con
# que yfinance las etiqueta según el sector y la versión.
FILAS_BALANCE = {
    "activos_totales": ["Total Assets"],
    "pasivos_totales": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "activo_corriente": ["Current Assets", "Total Current Assets"],
    "pasivo_corriente": ["Current Liabilities", "Total Current Liabilities"],
    "patrimonio": ["Stockholders Equity", "Total Stockholder Equity",
                   "Common Stock Equity"],
    "deuda_total": ["Total Debt"],
    "deuda_largo_plazo": ["Long Term Debt"],
    "beneficios_retenidos": ["Retained Earnings"],
    "efectivo": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "acciones_emitidas": ["Ordinary Shares Number", "Share Issued"],
    "inmovilizado": ["Net PPE", "Net Property Plant And Equipment"],
    "fondo_comercio": ["Goodwill"],
    "intangibles": ["Goodwill And Other Intangible Assets"],
}

FILAS_RESULTADOS = {
    "ingresos": ["Total Revenue", "Operating Revenue"],
    "beneficio_bruto": ["Gross Profit"],
    "ebit": ["EBIT", "Operating Income"],
    "beneficio_neto": ["Net Income", "Net Income Common Stockholders"],
    "gastos_financieros": ["Interest Expense"],
    "impuestos": ["Tax Provision"],
    "beneficio_antes_impuestos": ["Pretax Income"],
}

FILAS_FLUJOS = {
    "flujo_operativo": ["Operating Cash Flow", "Total Cash From Operating Activities"],
    "capex": ["Capital Expenditure"],
    "flujo_libre": ["Free Cash Flow"],
    "dividendos_pagados": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "recompras": ["Repurchase Of Capital Stock"],
}


def _fila(df: Optional[pd.DataFrame], nombres: List[str]) -> List[Optional[float]]:
    """
    Serie anual de una fila del estado financiero, de más reciente a más
    antigua. Devuelve `[]` si la fila no existe en ninguno de sus alias.
    """
    if df is None or df.empty:
        return []
    for nombre in nombres:
        if nombre in df.index:
            serie = df.loc[nombre]
            valores: List[Optional[float]] = []
            for v in serie.tolist():
                try:
                    f = float(v)
                    valores.append(None if (np.isnan(f) or np.isinf(f)) else f)
                except (TypeError, ValueError):
                    valores.append(None)
            return valores
    return []


def _limpio(valor: Any) -> Optional[float]:
    """Convierte a float o devuelve None. Nunca inventa un cero."""
    if valor is None or valor == "":
        return None
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    if np.isnan(f) or np.isinf(f):
        return None
    return f


class DataFetcher:
    """Fetcher de datos bursátiles, indicadores técnicos y estados financieros."""

    def __init__(self, con_estados_financieros: bool = True):
        # Los estados financieros son tres peticiones extra por ticker. Se
        # pueden desactivar para análisis rápidos: el resto del sistema degrada
        # a `NO_DISPONIBLE` en las métricas que dependen de ellos en vez de
        # fallar.
        self.con_estados_financieros = con_estados_financieros

    def fetch_all(self, ticker: str) -> Dict[str, Any]:
        """Datos brutos e indicadores técnicos para un ticker."""
        symbol = ticker.upper()
        stock = yf.Ticker(symbol)

        try:
            info = stock.info or {}
        except Exception as e:
            print(f"[DataFetcher] Advertencia info yfinance {symbol}: {e}")
            info = {}

        try:
            df = stock.history(period="1y")
        except Exception as e:
            return {"status": "ERROR", "ticker": symbol,
                    "error": f"Fallo al descargar precios de {symbol}: {e}"}

        if df is None or df.empty:
            return {
                "status": "ERROR",
                "error": f"No se encontraron precios para el ticker {symbol}",
                "ticker": symbol,
            }

        df = self._add_technical_indicators(df)
        latest_tech = self._extract_latest_tech_metrics(df)

        fundamentals, ausentes = self._extraer_fundamentales(info)
        estados = self._fetch_estados_financieros(stock) if self.con_estados_financieros else {}

        return {
            "status": "SUCCESS",
            "ticker": symbol,
            "company_name": info.get("shortName") or info.get("longName") or symbol,
            "sector": info.get("sector") or "Desconocido",
            "industry": info.get("industry") or "Desconocido",
            "current_price": float(df["Close"].iloc[-1]),
            "fundamentals": fundamentals,
            "campos_ausentes": ausentes,
            "estados_financieros": estados,
            "technical": latest_tech,
            "price_history_summary": self._resumen_precios(df),
        }

    # ------------------------------------------------------------------ #
    # Fundamentales
    # ------------------------------------------------------------------ #
    def _extraer_fundamentales(self, info: Dict[str, Any]):
        """
        Traduce `yfinance.info` a las claves internas, sin defaults silenciosos.

        Devuelve `(fundamentals, campos_ausentes)`. Un campo ausente vale `None`
        y aparece listado, de modo que el reconciliador pueda penalizar la
        confianza y el gatekeeper distinga «no lo sé» de «vale cero».
        """
        fundamentals: Dict[str, Any] = {}
        ausentes: List[str] = []

        for interno, externo in CAMPOS_INFO.items():
            v = _limpio(info.get(externo))
            fundamentals[interno] = v
            if v is None:
                ausentes.append(interno)

        # --- Deuda / patrimonio -------------------------------------------
        # yfinance publica `debtToEquity` en PORCENTAJE (212.5 significa 2.125x).
        # La conversión es incondicional: la regla anterior `if v > 10: v /= 100`
        # dejaba sin convertir a las empresas con menos de un 10% de deuda y las
        # rechazaba después como si tuvieran hasta 10x de apalancamiento.
        de_bruto = _limpio(info.get("debtToEquity"))
        fundamentals["debt_to_equity_bruto_pct"] = de_bruto
        fundamentals["debt_to_equity"] = de_bruto / 100.0 if de_bruto is not None else None
        if de_bruto is None:
            ausentes.append("debt_to_equity")

        # --- P/E ------------------------------------------------------------
        # Se conserva cuál de los dos alimentó la decisión: mezclar trailing y
        # forward sin dejar rastro impide comparar dos informes entre sí.
        trailing, forward = fundamentals.get("trailing_pe"), fundamentals.get("forward_pe")
        if trailing is not None:
            fundamentals["pe_ratio"], fundamentals["pe_origen"] = trailing, "trailingPE"
        elif forward is not None:
            fundamentals["pe_ratio"], fundamentals["pe_origen"] = forward, "forwardPE"
        else:
            fundamentals["pe_ratio"], fundamentals["pe_origen"] = None, None
            ausentes.append("pe_ratio")

        # yfinance devuelve `dividendYield` unas veces en tanto por uno y otras
        # en porcentaje. Un 450% de rentabilidad por dividendo no existe.
        dy = fundamentals.get("dividend_yield")
        if dy is not None and dy > 1.0:
            fundamentals["dividend_yield"] = dy / 100.0

        return fundamentals, sorted(set(ausentes))

    def _fetch_estados_financieros(self, stock: "yf.Ticker") -> Dict[str, Any]:
        """
        Series anuales de balance, resultados y flujos de caja.

        Sin esto no hay Piotroski (necesita variaciones interanuales), ni Altman
        (necesita capital circulante y beneficios retenidos), ni ROIC, ni ratio
        de devengos. Cada bloque se captura por separado: que falte el cash-flow
        no debe impedir calcular el Z-Score.
        """
        estados: Dict[str, Any] = {"disponible": False, "bloques_ok": [], "bloques_fallidos": []}

        for clave, atributo, filas in (
            ("balance", "balance_sheet", FILAS_BALANCE),
            ("resultados", "income_stmt", FILAS_RESULTADOS),
            ("flujos", "cashflow", FILAS_FLUJOS),
        ):
            try:
                df = getattr(stock, atributo)
                datos = {nombre: _fila(df, alias) for nombre, alias in filas.items()}
                if any(datos.values()):
                    estados[clave] = datos
                    estados["bloques_ok"].append(clave)
                else:
                    estados[clave] = {}
                    estados["bloques_fallidos"].append(clave)
            except Exception as e:
                estados[clave] = {}
                estados["bloques_fallidos"].append(clave)
                print(f"[DataFetcher] Advertencia {atributo}: {e}")

        estados["disponible"] = bool(estados["bloques_ok"])
        return estados

    # ------------------------------------------------------------------ #
    # Técnico
    # ------------------------------------------------------------------ #
    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcula RSI, MACD, Bandas de Bollinger, SMA 50/200, ATR y volumen relativo.

        Antes descarta las barras SIN CIERRE. yfinance devuelve a veces una fila
        final con `Close` a NaN —una sesión abierta, un festivo o simplemente un
        hueco del proveedor—, y `_extract_latest_tech_metrics` toma la última
        fila sin condiciones. Ese NaN se propagaba a `close`, y de ahí a `atr`,
        al stop, al objetivo y al perfil de riesgo.

        El fallo no era visible porque `bool(float("nan"))` es True: el Fund
        Manager creía tener precio, entraba en la rama larga del resumen y
        reventaba con `KeyError: 'ratio_riesgo_recompensa'` al pedirle al perfil
        de riesgo una clave que este no había podido calcular. Se manifestó
        analizando AAPL en vivo.

        Una barra sin cierre no es una barra con precio cero: es una barra que no
        existe. Eliminarla es la misma regla que gobierna el resto del sistema
        —ausencia de dato ≠ cero— aplicada a la serie de precios.
        """
        df = df[df["Close"].notna()].copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        df["SMA_50"] = close.rolling(window=min(50, len(close))).mean()
        df["SMA_200"] = close.rolling(window=min(200, len(close))).mean()

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_12 - ema_26
        df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

        sma_20 = close.rolling(window=20).mean()
        std_20 = close.rolling(window=20).std()
        df["BB_upper"] = sma_20 + (std_20 * 2)
        df["BB_lower"] = sma_20 - (std_20 * 2)
        df["BB_middle"] = sma_20

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=14).mean()

        vol_avg = df["Volume"].rolling(window=20).mean()
        df["Volume_Rel"] = df["Volume"] / (vol_avg + 1e-9)

        return df

    def _extract_latest_tech_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Último valor limpio de cada indicador, más el contexto de tendencia que
        el clasificador de momentum necesita para no confundir el retardo de una
        media móvil con una tendencia bajista vigente.
        """
        if df.empty:
            # Sin una sola barra con cierre no hay indicadores que extraer. Se
            # devuelve el bloque vacío para que los consumidores apliquen su
            # propia degradación en vez de recibir NaN disfrazados de precio.
            return {}

        last = df.iloc[-1]
        close = float(last["Close"])

        def val(col: str, defecto: float) -> float:
            v = last[col]
            return float(v) if not pd.isna(v) else defecto

        sma_50 = val("SMA_50", close)
        sma_200 = val("SMA_200", close)
        cierres = df["Close"]

        # Pendiente normalizada de la SMA50 sobre 20 sesiones: distingue una
        # media que sube de una que baja aunque el cruce siga sin producirse.
        pendiente_sma50 = 0.0
        if len(df) >= 21 and not pd.isna(df["SMA_50"].iloc[-21]) and df["SMA_50"].iloc[-21] != 0:
            pendiente_sma50 = float(df["SMA_50"].iloc[-1] / df["SMA_50"].iloc[-21] - 1.0)

        max_52w = float(df["High"].max())
        min_52w = float(df["Low"].min())
        rango = max_52w - min_52w

        return {
            "close": close,
            "rsi": round(val("RSI", 50.0), 2),
            "macd": round(val("MACD", 0.0), 3),
            "macd_signal": round(val("MACD_signal", 0.0), 3),
            "macd_hist": round(val("MACD_hist", 0.0), 3),
            "bb_upper": round(val("BB_upper", close * 1.05), 2),
            "bb_lower": round(val("BB_lower", close * 0.95), 2),
            "atr": round(val("ATR", close * 0.02), 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "volume_rel": round(val("Volume_Rel", 1.0), 2),
            # --- contexto de tendencia ---
            "dist_sma_50_pct": round(close / sma_50 - 1.0, 4) if sma_50 else 0.0,
            "dist_sma_200_pct": round(close / sma_200 - 1.0, 4) if sma_200 else 0.0,
            "pendiente_sma_50": round(pendiente_sma50, 4),
            "posicion_rango_52w": round((close - min_52w) / rango, 4) if rango > 0 else 0.5,
            "volatilidad_anual": self._volatilidad_anualizada(cierres),
            "atr_pct": round(val("ATR", close * 0.02) / close, 4) if close else 0.0,
        }

    @staticmethod
    def _volatilidad_anualizada(cierres: pd.Series, ventana: int = 60) -> float:
        """Volatilidad realizada anualizada. Es el insumo del dimensionamiento."""
        if len(cierres) < 20:
            return 0.0
        rets = cierres.pct_change().dropna().tail(ventana)
        if rets.empty:
            return 0.0
        v = float(rets.std() * np.sqrt(252))
        return round(v, 4) if not (np.isnan(v) or np.isinf(v)) else 0.0

    def _resumen_precios(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Rentabilidades a varios plazos y peor caída del año."""
        close = df["Close"]
        ultimo = float(close.iloc[-1])

        def retorno(sesiones: int) -> Optional[float]:
            """
            Rentabilidad a `sesiones` vista.

            Con `period="1y"` yfinance devuelve unas 250 sesiones, así que
            exigir estrictamente más de 252 dejaba `change_12m_pct` en None
            SIEMPRE y anulaba en silencio la pata de momentum del analista
            técnico. Se admite hasta un 10% menos de histórico usando la barra
            más antigua disponible; por debajo de eso el dato no se estima.
            """
            if len(close) < 2:
                return None
            disponibles = len(close) - 1
            if disponibles < sesiones * 0.9:
                return None
            base = float(close.iloc[-1 - min(sesiones, disponibles)])
            return round(ultimo / base - 1.0, 4) if base else None

        acumulado = close / close.cummax() - 1.0
        return {
            "min_52w": float(df["Low"].min()),
            "max_52w": float(df["High"].max()),
            "close_today": ultimo,
            "change_1m_pct": retorno(20),
            "change_3m_pct": retorno(63),
            "change_6m_pct": retorno(126),
            "change_12m_pct": retorno(252),
            "max_drawdown_1y": round(float(acumulado.min()), 4),
            "sesiones": int(len(close)),
        }

    def fetch_series_precios(self, tickers: List[str], periodo: str = "1y") -> Dict[str, pd.Series]:
        """
        Series de cierre para varios tickers, usadas por la capa de cartera para
        estimar la matriz de correlaciones. Se pide en una sola llamada: hacerlo
        ticker a ticker multiplicaría la latencia sin ganar nada.
        """
        limpios = [t.upper() for t in tickers if t]
        if not limpios:
            return {}
        try:
            datos = yf.download(limpios, period=periodo, progress=False,
                                auto_adjust=True, group_by="ticker")
        except Exception as e:
            print(f"[DataFetcher] Advertencia al descargar series conjuntas: {e}")
            return {}

        series: Dict[str, pd.Series] = {}
        for t in limpios:
            try:
                if len(limpios) == 1:
                    serie = datos["Close"] if "Close" in datos else None
                else:
                    serie = datos[t]["Close"] if t in datos else None
                if serie is not None:
                    serie = serie.dropna()
                    if not serie.empty:
                        series[t] = serie
            except Exception:
                continue
        return series
