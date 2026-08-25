import requests
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from src.config import SEC_EDGAR_USER_AGENT

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL_TEMPLATE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL_TEMPLATE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accesion}/{documento}"

# Ítem del formulario 8-K que corresponde a la publicación de resultados.
# Es el ancla de fuente primaria del Analista de Noticias: a diferencia de
# cualquier feed de prensa, trae fecha `filed` exacta y contenido no editorial.
ITEM_8K_RESULTADOS = "2.02"

# Conceptos us-gaap por magnitud, ordenados por preferencia. Los cuatro
# primeros grupos son los que ya consumía el reconciliador; el resto existe
# para que el Analista de Calidad pueda calcular Piotroski, Altman, ROIC y el
# ratio de devengos contra la fuente OFICIAL en lugar de contra un agregador.
CONCEPTOS_XBRL = {
    "revenues": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
        "RetainedEarningsAppropriated",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "gross_profit": ["GrossProfit"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
    ],
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["DebtCurrent", "LongTermDebtCurrent", "ShortTermBorrowings"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ],
    "property_plant_equipment": [
        "PropertyPlantAndEquipmentNet",
    ],
}

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

    def get_fundamental_facts(self, ticker: str,
                              as_of: Optional[str] = None) -> Dict[str, Any]:
        """
        Hechos XBRL de la última memoria publicada, más la del ejercicio
        anterior para las magnitudes de flujo.

        `series` trae los dos últimos ejercicios anuales de cada concepto de
        flujo, que es lo que exigen las variaciones interanuales del F-Score de
        Piotroski. Sin la serie no hay «ΔROA», solo un ROA suelto.
        """
        cik = self.get_cik(ticker)
        if not cik:
            return {"status": "NOT_FOUND", "source": "SEC EDGAR"}

        url = SEC_FACTS_URL_TEMPLATE.format(cik=cik)
        try:
            response = requests.get(url, headers=self.headers, timeout=12)
            if response.status_code != 200:
                return {"status": "ERROR", "source": "SEC EDGAR", "ticker": ticker,
                        "http_status": response.status_code}

            us_gaap = response.json().get("facts", {}).get("us-gaap", {})

            valores: Dict[str, Any] = {}
            series: Dict[str, Any] = {}
            ausentes = []
            for nombre, conceptos in CONCEPTOS_XBRL.items():
                historial = self._serie_de_hechos(us_gaap, conceptos, as_of=as_of)
                if historial:
                    valores[nombre] = historial[0]["val"]
                    series[nombre] = historial[:4]
                else:
                    valores[nombre] = None
                    ausentes.append(nombre)

            return {
                "status": "SUCCESS",
                "source": "SEC EDGAR (Oficial)",
                "cik": cik,
                "series": series,
                "as_of": as_of,
                "campos_ausentes": sorted(ausentes),
                **valores,
            }
        except Exception as e:
            print(f"[SEC EDGAR] Error al consultar datos XBRL para {ticker}: {e}")

        return {"status": "ERROR", "source": "SEC EDGAR", "ticker": ticker}

    def _serie_de_hechos(self, gaap_dict: Dict[str, Any], concept_names: list,
                         as_of: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Historial de un concepto GAAP, del cierre contable más reciente al más
        antiguo, con dos garantías sobre la versión anterior.

        1. DEDUPLICACIÓN POR REEXPRESIÓN. Un mismo cierre puede presentarse
           varias veces (el 10-K original y una reexpresión posterior). Antes se
           ordenaba la lista cruda por `end` y se devolvía el primer elemento,
           que podía ser cualquiera de las versiones según el orden en que la
           SEC las hubiera devuelto. Ahora se conserva una sola por cierre: la
           de `filed` más reciente.

        2. FILTRO POINT-IN-TIME OPCIONAL. Con `as_of` se descartan los hechos
           publicados después de esa fecha (`filed <= as_of`), que es la
           disciplina que aplica `FundamentalStore` en el backtest. Sin `as_of`
           —el caso de producción, que pregunta «qué se sabe hoy»— no hay
           look-ahead posible: `companyfacts` solo contiene hechos ya
           presentados. El parámetro existe para que quien reutilice este
           cliente en una consulta histórica no tenga que reimplementar la
           selección, que era el riesgo latente registrado en
           `output/AUDIT.md` §4.3.

        Se prefieren los hechos anuales (10-K); si no hay ninguno se admiten los
        trimestrales, y `form` declara cuál se usó.
        """
        for concept in concept_names:
            if concept not in gaap_dict:
                continue
            units = gaap_dict[concept].get("units", {})
            for unit_key in ("USD", "shares", "pure", "USD/shares"):
                items = units.get(unit_key)
                if not items:
                    continue

                limpios = []
                for it in items:
                    filed, end = it.get("filed"), it.get("end")
                    if not filed or not end or it.get("val") is None:
                        continue
                    if as_of and filed > as_of:
                        continue
                    limpios.append({
                        "val": float(it["val"]),
                        "end": end,
                        "start": it.get("start"),
                        "filed": filed,
                        "form": it.get("form", ""),
                        "fy": it.get("fy"),
                        "fp": it.get("fp"),
                        "concepto": concept,
                        "unidad": unit_key,
                    })
                if not limpios:
                    continue

                anuales = [x for x in limpios if x["form"].startswith("10-K")]
                elegidos = anuales or limpios
                por_cierre: Dict[str, Dict[str, Any]] = {}
                for x in elegidos:
                    actual = por_cierre.get(x["end"])
                    if actual is None or x["filed"] > actual["filed"]:
                        por_cierre[x["end"]] = x
                return sorted(por_cierre.values(),
                              key=lambda x: (x["end"], x["filed"]), reverse=True)
        return []

    def _extract_recent_fact(self, gaap_dict: Dict[str, Any], concept_names: list,
                             as_of: Optional[str] = None) -> Optional[float]:
        """Cifra más reciente de un concepto GAAP. Se conserva por compatibilidad."""
        historial = self._serie_de_hechos(gaap_dict, concept_names, as_of=as_of)
        return historial[0]["val"] if historial else None

    def get_recent_8k_earnings(self, ticker: str, dias: int = 30,
                               max_items: int = 10) -> Dict[str, Any]:
        """
        Formularios 8-K recientes con el Ítem 2.02 ("Results of Operations and
        Financial Condition"), es decir, publicaciones de resultados.

        Por qué esta fuente es distinta de las otras dos del Analista de
        Noticias: el campo `filingDate` de EDGAR es la fecha real en que el
        hecho se hizo público, no una estimación editorial. Es la única de las
        tres con potencial point-in-time, y por eso encabeza el ranking de
        credibilidad (`NEWS_SOURCE_CREDIBILITY["SEC_8K"] = 1.0`).

        Devuelve siempre un dict con `status`; nunca lanza. El agregador
        distingue SUCCESS de los demás estados para declarar qué fuentes
        respondieron.
        """
        cik = self.get_cik(ticker)
        if not cik:
            return {"status": "NOT_FOUND", "source": "SEC EDGAR 8-K", "filings": []}

        url = SEC_SUBMISSIONS_URL_TEMPLATE.format(cik=cik)
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return {"status": "ERROR", "source": "SEC EDGAR 8-K",
                        "http_status": response.status_code, "filings": []}

            recientes = response.json().get("filings", {}).get("recent", {})
            corte = (datetime.now(timezone.utc).date() - timedelta(days=dias)).isoformat()
            cik_int = str(int(cik))  # las rutas de Archives no llevan ceros a la izquierda

            filings = []
            formularios = recientes.get("form", [])
            for i in range(len(formularios)):
                if formularios[i] != "8-K":
                    continue
                items = recientes.get("items", [""] * len(formularios))[i] or ""
                if ITEM_8K_RESULTADOS not in [x.strip() for x in items.split(",")]:
                    continue

                filed = recientes.get("filingDate", [""] * len(formularios))[i]
                if not filed or filed < corte:
                    continue

                accesion = recientes.get("accessionNumber", [""] * len(formularios))[i]
                documento = recientes.get("primaryDocument", [""] * len(formularios))[i]
                filings.append({
                    "accession_number": accesion,
                    "filed": filed,
                    "report_date": recientes.get("reportDate", [""] * len(formularios))[i] or None,
                    "items": items,
                    "description": recientes.get("primaryDocDescription",
                                                 [""] * len(formularios))[i] or "",
                    "url": SEC_ARCHIVES_URL_TEMPLATE.format(
                        cik_int=cik_int,
                        accesion=accesion.replace("-", ""),
                        documento=documento,
                    ) if accesion and documento else "https://www.sec.gov/cgi-bin/browse-edgar",
                })
                if len(filings) >= max_items:
                    break

            return {"status": "SUCCESS", "source": "SEC EDGAR 8-K", "cik": cik,
                    "filings": filings}
        except Exception as e:
            print(f"[SEC EDGAR] Error al consultar 8-K de {ticker}: {e}")
            return {"status": "ERROR", "source": "SEC EDGAR 8-K", "filings": []}
