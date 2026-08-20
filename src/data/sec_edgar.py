import requests
import json
from typing import Dict, Any, Optional
from src.config import SEC_EDGAR_USER_AGENT

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

class SECEdgarClient:
    """Cliente para la API oficial de la SEC (EDGAR) que obtiene reportes auditados 10-K / 10-Q."""

    def __init__(self, user_agent: str = SEC_EDGAR_USER_AGENT):
        self.headers = {"User-Agent": user_agent}
        self._ticker_to_cik_cache: Dict[str, str] = {}

    def get_cik(self, ticker: str) -> Optional[str]:
        """Obtiene el número CIK de un ticker estadounidense."""
        ticker = ticker.upper()
        if ticker in self._ticker_to_cik_cache:
            return self._ticker_to_cik_cache[ticker]

        try:
            response = requests.get(SEC_TICKERS_URL, headers=self.headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                for item in data.values():
                    if item.get("ticker") == ticker:
                        cik = str(item.get("cik_str")).zfill(10)
                        self._ticker_to_cik_cache[ticker] = cik
                        return cik
        except Exception as e:
            print(f"[SEC EDGAR] Advertencia al obtener CIK para {ticker}: {e}")

        return None

    def get_fundamental_facts(self, ticker: str) -> Dict[str, Any]:
        """Obtiene los hechos XBRL principales (Ingresos, Ganancia Neta, Activos, Deuda) desde EDGAR."""
        cik = self.get_cik(ticker)
        if not cik:
            return {"status": "NOT_FOUND", "source": "SEC EDGAR"}

        url = SEC_FACTS_URL_TEMPLATE.format(cik=cik)
        try:
            response = requests.get(url, headers=self.headers, timeout=8)
            if response.status_code == 200:
                facts = response.json().get("facts", {})
                us_gaap = facts.get("us-gaap", {})
                
                # Extraer conceptos clave de GAAP
                revenues = self._extract_recent_fact(us_gaap, ["Revenues", "SalesRevenueNet", "RevenueFromContractWithCustomerExcludingAssessedTax"])
                net_income = self._extract_recent_fact(us_gaap, ["NetIncomeLoss", "ProfitLoss"])
                assets = self._extract_recent_fact(us_gaap, ["Assets"])
                liabilities = self._extract_recent_fact(us_gaap, ["Liabilities"])

                return {
                    "status": "SUCCESS",
                    "source": "SEC EDGAR (Oficial)",
                    "cik": cik,
                    "revenues": revenues,
                    "net_income": net_income,
                    "total_assets": assets,
                    "total_liabilities": liabilities,
                }
        except Exception as e:
            print(f"[SEC EDGAR] Error al consultar datos XBRL para {ticker}: {e}")

        return {"status": "ERROR", "source": "SEC EDGAR", "ticker": ticker}

    def _extract_recent_fact(self, gaap_dict: Dict[str, Any], concept_names: list) -> Optional[float]:
        """Auxiliar para extraer la cifra más reciente de un concepto GAAP."""
        for concept in concept_names:
            if concept in gaap_dict:
                units = gaap_dict[concept].get("units", {})
                for unit_key in ["USD", "pure"]:
                    if unit_key in units:
                        items = units[unit_key]
                        if items:
                            # Filtrar reportes anuales 10-K o más recientes
                            sorted_items = sorted(items, key=lambda x: x.get("end", ""), reverse=True)
                            if sorted_items:
                                return float(sorted_items[0].get("val", 0))
        return None
