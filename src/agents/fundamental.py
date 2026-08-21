from typing import Dict, Any
from src.config import (MIN_REVENUE_GROWTH, MIN_NET_MARGIN, MAX_DEBT_TO_EQUITY,
                        get_llm, texto_de_respuesta_llm)
from src.state import FinancialAnalysisState

class FundamentalAnalystAgent:
    """
    Agente Gatekeeper: Evalúa la salud fundamental y el crecimiento de la empresa.
    Actúa como primer filtro de control en la máquina de estados.
    """

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        rec = state.get("reconciliation_data", {})
        metrics = rec.get("reconciled_metrics", {})

        revenue_growth = metrics.get("revenue_growth", 0.0)
        net_margin = metrics.get("net_margin", 0.0)
        debt_to_equity = metrics.get("debt_to_equity", 0.0)
        roe = metrics.get("roe", 0.0)
        pe_ratio = metrics.get("pe_ratio", 0.0)

        confidence_score = rec.get("confidence_score", 1.0)
        discrepancies = rec.get("discrepancies", [])

        reasons = []
        passed = True

        # Aplicar reglas de filtrado Gatekeeper
        if net_margin < MIN_NET_MARGIN:
            passed = False
            reasons.append(f"Margen Neto ({net_margin:.1%}) por debajo del umbral mínimo ({MIN_NET_MARGIN:.1%})")

        if revenue_growth < MIN_REVENUE_GROWTH:
            passed = False
            reasons.append(f"Crecimiento de Ingresos ({revenue_growth:.1%}) por debajo del umbral mínimo ({MIN_REVENUE_GROWTH:.1%})")

        if debt_to_equity > MAX_DEBT_TO_EQUITY:
            passed = False
            reasons.append(f"Relación Deuda/Capital ({debt_to_equity:.2f}) excede el límite permitido ({MAX_DEBT_TO_EQUITY:.2f})")

        if confidence_score < 0.5:
            reasons.append("Bajo índice de confianza en la reconciliación de datos multi-fuente")

        status_text = "APROBADO" if passed else "RECHAZADO"

        summary = f"Métricas Reconciliadas: Crecimiento Ingresos={revenue_growth:.1%}, Margen Neto={net_margin:.1%}, Deuda/Capital={debt_to_equity:.2f}, ROE={roe:.1%}. Resultado: {status_text}."
        if not passed:
            summary += " Motivos: " + "; ".join(reasons)

        # Generar informe enriquecido si hay LLM disponible
        llm = get_llm()
        if llm:
            try:
                prompt = (
                    f"Como Analista Fundamental Gatekeeper, resume la salud financiera de {ticker}:\n"
                    f"- Crecimiento Ingresos: {revenue_growth:.1%}\n"
                    f"- Margen Neto: {net_margin:.1%}\n"
                    f"- Deuda/Capital: {debt_to_equity:.2f}\n"
                    f"- ROE: {roe:.1%}\n"
                    f"- Filtro Gatekeeper: {status_text}\n"
                    f"Escribe una justificación concisa en 2 frases."
                )
                texto = texto_de_respuesta_llm(llm.invoke(prompt))
                if texto:
                    summary = texto
            except Exception as e:
                err_str = str(e)
                if "Expecting ',' delimiter" in err_str or "JSONDecodeError" in err_str:
                    print(f"[FundamentalAgent] Advertencia API LLM: La API de Hugging Face devolvió una respuesta no válida o un formato de error (causas habituales: modelo restringido/gated, token inválido o error del servidor HF). Se usará el resumen analítico determinista.")
                else:
                    print(f"[FundamentalAgent] Error al invocar LLM: {e}")

        return {
            "passed_gatekeeper": passed,
            "status": status_text,
            "metrics": metrics,
            "reasons": reasons,
            "confidence_score": confidence_score,
            "discrepancies": discrepancies,
            "summary": summary
        }
