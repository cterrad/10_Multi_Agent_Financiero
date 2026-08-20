import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any

class DataFetcher:
    """Fetcher de datos bursátiles e indicadores técnicos de precios mediante yfinance."""

    def fetch_all(self, ticker: str) -> Dict[str, Any]:
        """Obtiene datos fundamentales brutos e historial técnico completo para un ticker."""
        symbol = ticker.upper()
        stock = yf.Ticker(symbol)
        
        # Info general y métricas
        try:
            info = stock.info or {}
        except Exception as e:
            print(f"[DataFetcher] Advertencia info yfinance {symbol}: {e}")
            info = {}

        # Historial de precios de los últimos 12 meses
        df = stock.history(period="1y")
        if df.empty:
            return {
                "status": "ERROR",
                "error": f"No se encontraron precios para el ticker {symbol}",
                "ticker": symbol
            }

        # Calcular Indicadores Técnicos
        df = self._add_technical_indicators(df)
        latest_tech = self._extract_latest_tech_metrics(df)

        # Extraer Métricas Fundamentales de yfinance
        revenue_growth = info.get("revenueGrowth", 0.0)
        net_margin = info.get("profitMargins", 0.0)
        debt_to_equity = info.get("debtToEquity", 0.0)
        if debt_to_equity and debt_to_equity > 10:
            # yfinance a veces devuelve debtToEquity en porcentaje (ej 150 -> 1.5)
            debt_to_equity = debt_to_equity / 100.0

        roe = info.get("returnOnEquity", 0.0)
        pe_ratio = info.get("trailingPE", info.get("forwardPE", 0.0))

        return {
            "status": "SUCCESS",
            "ticker": symbol,
            "company_name": info.get("shortName", info.get("longName", symbol)),
            "sector": info.get("sector", "Desconocido"),
            "industry": info.get("industry", "Desconocido"),
            "current_price": float(df["Close"].iloc[-1]),
            "fundamentals": {
                "revenue_growth": float(revenue_growth) if revenue_growth is not None else 0.0,
                "net_margin": float(net_margin) if net_margin is not None else 0.0,
                "debt_to_equity": float(debt_to_equity) if debt_to_equity is not None else 0.0,
                "roe": float(roe) if roe is not None else 0.0,
                "pe_ratio": float(pe_ratio) if pe_ratio is not None else 0.0,
                "market_cap": info.get("marketCap", 0),
            },
            "technical": latest_tech,
            "price_history_summary": {
                "min_52w": float(df["Low"].min()),
                "max_52w": float(df["High"].max()),
                "close_today": float(df["Close"].iloc[-1]),
                "change_1m_pct": float((df["Close"].iloc[-1] - df["Close"].iloc[-20]) / df["Close"].iloc[-20]) if len(df) >= 20 else 0.0
            }
        }

    def _add_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula RSI, MACD, Bandas de Bollinger, Medias Móviles (SMA 50/200) y ATR."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # 1. Medias Móviles
        df["SMA_50"] = close.rolling(window=min(50, len(close))).mean()
        df["SMA_200"] = close.rolling(window=min(200, len(close))).mean()

        # 2. RSI (14 periodos)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        # 3. MACD (12, 26, 9)
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        df["MACD"] = ema_12 - ema_26
        df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_hist"] = df["MACD"] - df["MACD_signal"]

        # 4. Bandas de Bollinger (20, 2)
        sma_20 = close.rolling(window=20).mean()
        std_20 = close.rolling(window=20).std()
        df["BB_upper"] = sma_20 + (std_20 * 2)
        df["BB_lower"] = sma_20 - (std_20 * 2)
        df["BB_middle"] = sma_20

        # 5. ATR (Average True Range - 14 periodos)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=14).mean()

        # 6. Volume Relative (vs 20d avg)
        vol_avg = df["Volume"].rolling(window=20).mean()
        df["Volume_Rel"] = df["Volume"] / (vol_avg + 1e-9)

        return df

    def _extract_latest_tech_metrics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Extrae el último valor limpio de los indicadores calculados."""
        last = df.iloc[-1]
        close = float(last["Close"])
        rsi = float(last["RSI"]) if not np.isnan(last["RSI"]) else 50.0
        macd = float(last["MACD"]) if not np.isnan(last["MACD"]) else 0.0
        macd_signal = float(last["MACD_signal"]) if not np.isnan(last["MACD_signal"]) else 0.0
        macd_hist = float(last["MACD_hist"]) if not np.isnan(last["MACD_hist"]) else 0.0
        bb_upper = float(last["BB_upper"]) if not np.isnan(last["BB_upper"]) else close * 1.05
        bb_lower = float(last["BB_lower"]) if not np.isnan(last["BB_lower"]) else close * 0.95
        atr = float(last["ATR"]) if not np.isnan(last["ATR"]) else close * 0.02
        sma_50 = float(last["SMA_50"]) if not np.isnan(last["SMA_50"]) else close
        sma_200 = float(last["SMA_200"]) if not np.isnan(last["SMA_200"]) else close
        vol_rel = float(last["Volume_Rel"]) if not np.isnan(last["Volume_Rel"]) else 1.0

        return {
            "close": close,
            "rsi": round(rsi, 2),
            "macd": round(macd, 3),
            "macd_signal": round(macd_signal, 3),
            "macd_hist": round(macd_hist, 3),
            "bb_upper": round(bb_upper, 2),
            "bb_lower": round(bb_lower, 2),
            "atr": round(atr, 2),
            "sma_50": round(sma_50, 2),
            "sma_200": round(sma_200, 2),
            "volume_rel": round(vol_rel, 2),
        }
