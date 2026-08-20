from typing import Dict, Any

class DataReconciler:
    """
    Consistency Checker: Módulo de reconciliación de datos multi-proveedor.
    Compara métricas fundamentales entre SEC EDGAR, Finnhub y yfinance para validar consistencia.
    """

    def reconcile(self, ticker: str, yf_data: Dict[str, Any], sec_data: Dict[str, Any], finnhub_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta la reconciliación cruzada de datos y calcula un índice de confianza.
        """
        yf_fund = yf_data.get("fundamentals", {})
        
        # Extraer ingresos de las 3 fuentes si existen
        revenue_yf = yf_fund.get("revenue_growth", 0.0)
        net_margin_yf = yf_fund.get("net_margin", 0.0)
        debt_to_equity_yf = yf_fund.get("debt_to_equity", 0.0)
        roe_yf = yf_fund.get("roe", 0.0)

        sources_used = ["yfinance"]
        discrepancies = []
        confidence_score = 1.0

        # Verificación con SEC EDGAR
        sec_status = sec_data.get("status")
        if sec_status == "SUCCESS":
            sources_used.append("SEC EDGAR (Oficial)")
            sec_rev = sec_data.get("revenues")
            sec_net_inc = sec_data.get("net_income")
            if sec_rev and sec_net_inc and sec_rev > 0:
                sec_margin = sec_net_inc / sec_rev
                # Comparar margen neto yfinance vs SEC
                if abs(sec_margin - net_margin_yf) > 0.15:
                    discrepancies.append(f"Diferencia en Margen Neto: SEC ({sec_margin:.1%}) vs yfinance ({net_margin_yf:.1%})")
                    confidence_score -= 0.15

        # Verificación con Finnhub
        fh_status = finnhub_data.get("status")
        if fh_status == "SUCCESS":
            sources_used.append("Finnhub")
            fh_margin = finnhub_data.get("net_margin_ttm")
            if fh_margin is not None:
                fh_margin_float = float(fh_margin) / 100.0 if float(fh_margin) > 1.0 else float(fh_margin)
                if abs(fh_margin_float - net_margin_yf) > 0.15:
                    discrepancies.append(f"Diferencia en Margen Finnhub: ({fh_margin_float:.1%}) vs yfinance ({net_margin_yf:.1%})")
                    confidence_score -= 0.10

        confidence_score = max(0.4, round(confidence_score, 2))

        # Métricas unificadas y reconciliadas
        reconciled_metrics = {
            "revenue_growth": revenue_yf,
            "net_margin": net_margin_yf,
            "debt_to_equity": debt_to_equity_yf,
            "roe": roe_yf,
            "pe_ratio": yf_fund.get("pe_ratio", 0.0),
        }

        status = "HIGH_CONFIDENCE"
        if len(sources_used) == 1:
            status = "SINGLE_VENDOR_FALLBACK"
        elif len(discrepancies) > 0:
            status = "RECONCILED_WITH_DISCREPANCIES"

        return {
            "status": status,
            "ticker": ticker.upper(),
            "confidence_score": confidence_score,
            "sources_consulted": sources_used,
            "discrepancies": discrepancies,
            "reconciled_metrics": reconciled_metrics
        }
