import requests
from typing import Dict, Any
from src.config import FINNHUB_API_KEY

class FinnhubClient:
    """Cliente para la API de Finnhub (métrica fundamental y perfil de empresa)."""

    def __init__(self, api_key: str = FINNHUB_API_KEY):
        self.api_key = api_key
        self.base_url = "https://finnhub.io/api/v1"

    def get_company_profile(self, ticker: str) -> Dict[str, Any]:
        """Obtiene perfil general de la empresa (industria, país, capitalización)."""
        if not self.api_key:
            return {"status": "NO_API_KEY", "source": "Finnhub"}

        try:
            url = f"{self.base_url}/stock/profile2?symbol={ticker.upper()}&token={self.api_key}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                return {
                    "status": "SUCCESS",
                    "source": "Finnhub",
                    "name": data.get("name"),
                    "finnhub_industry": data.get("finnhubIndustry"),
                    "market_cap": data.get("marketCapitalization"),
                }
        except Exception as e:
            print(f"[Finnhub] Error al consultar perfil de {ticker}: {e}")

        return {"status": "ERROR", "source": "Finnhub"}

    def get_basic_financials(self, ticker: str) -> Dict[str, Any]:
        """Obtiene métricas financieras básicas y ratios en Finnhub."""
        if not self.api_key:
            return {"status": "NO_API_KEY", "source": "Finnhub"}

        try:
            url = f"{self.base_url}/stock/metric?symbol={ticker.upper()}&metric=all&token={self.api_key}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                metrics = res.json().get("metric", {})
                return {
                    "status": "SUCCESS",
                    "source": "Finnhub",
                    "pe_ratio": metrics.get("peBasicExclExtraTTM"),
                    "roe_ttm": metrics.get("roeTTM"),
                    "net_margin_ttm": metrics.get("netProfitMarginTTM"),
                    "revenue_growth_5y": metrics.get("revenueGrowth5Y"),
                }
        except Exception as e:
            print(f"[Finnhub] Error al consultar métricas de {ticker}: {e}")

        return {"status": "ERROR", "source": "Finnhub"}
