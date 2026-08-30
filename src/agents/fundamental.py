"""
Agente Gatekeeper Fundamental: primer filtro de control del grafo.

La lógica del filtro vive ahora en `src/tools/fundamentales.py`, invocable como
tool. Este módulo es el agente: decide QUÉ tools llamar y en qué orden, monta el
informe y redacta. Las tres correcciones que definen el filtro siguen intactas y
están documentadas donde se aplican:

1. VEREDICTO DE TRES VÍAS. Antes solo había APROBADO y RECHAZADO, y un campo
   ausente valía `0.0`, así que una empresa sin cobertura de datos y otra
   realmente sin ingresos producían el mismo veredicto y los mismos motivos:
   «Margen Neto (0.0%) por debajo del umbral mínimo». Eso es afirmar un hecho
   contable cuando lo que hay es un vacío de información. Ahora existe
   DATOS_INSUFICIENTES, y el Fund Manager lo traduce a SIN OPINION en vez de a
   VENTA.

2. UMBRALES SENSIBLES AL SECTOR. Aplicar el mismo límite de deuda a un banco, a
   un REIT o a una utility regulada que a una empresa de software es un error de
   categoría: en esos sectores el apalancamiento alto es la estructura normal
   del negocio, no una señal de fragilidad.

3. LA CONFIANZA EN LOS DATOS ES CONDICIÓN DE FILTRO, NO UNA NOTA AL PIE. Por
   debajo del umbral el veredicto pasa a DATOS_INSUFICIENTES.

El gatekeeper sigue respondiendo sí/no. La graduación —cuánta calidad, a qué
precio, con cuánto crecimiento— es trabajo del `QualityAnalystAgent`, que corre
antes que él y cuyas puntuaciones el Fund Manager cruza con el momentum.
"""

from typing import Any, Dict, List, Optional

from src.agents.base import AgenteBase, Traza
from src.config import SECTOR_DESCONOCIDO, get_llm, texto_de_respuesta_llm  # noqa: F401
from src.prompts import SYSTEM_GATEKEEPER, prompt_gatekeeper
from src.state import FinancialAnalysisState
from src.tools.fundamentales import (
    CONFIANZA_MINIMA_PARA_VEREDICTO,
    MAGNITUDES_EXIGIDAS,
)

__all__ = [
    "FundamentalAnalystAgent",
    "CONFIANZA_MINIMA_PARA_VEREDICTO",
    "MAGNITUDES_EXIGIDAS",
]


class FundamentalAnalystAgent(AgenteBase):
    """Evalúa la salud fundamental mínima exigible antes de seguir analizando."""

    nombre = "gatekeeper"
    rol = "Analista Fundamental (filtro de admisión)"
    system_prompt = SYSTEM_GATEKEEPER

    # ------------------------------------------------------------------ #
    def decidir(self, state: FinancialAnalysisState, traza: Traza) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        industria = state.get("industry") or "Desconocida"
        rec = state.get("reconciliation_data", {}) or {}
        metrics = rec.get("reconciled_metrics", {}) or {}
        quality = state.get("quality_report", {}) or {}

        confidence_score = rec.get("confidence_score", 1.0)
        discrepancies = rec.get("discrepancies", [])
        procedencia = rec.get("procedencia", {})

        veredicto = self.usar_tool("evaluar_criterios_gatekeeper", {
            "sector": sector,
            "industria": industria,
            "metricas_reconciliadas": metrics,
            "confianza_datos": confidence_score,
            "n_discrepancias": len(discrepancies),
        }, traza)

        # Las magnitudes llegan como None cuando no se conocen. Ese None NO se
        # convierte en cero en ningún punto de este agente.
        informe: Dict[str, Any] = {
            "passed_gatekeeper": veredicto["passed_gatekeeper"],
            "status": veredicto["status"],
            "evaluable": veredicto["evaluable"],
            "sector": sector,
            "industria": industria,
            "metrics": metrics,
            "magnitudes_ausentes": veredicto["magnitudes_ausentes"],
            "criterios": veredicto["criterios"],
            "reasons": veredicto["reasons"],
            "avisos": veredicto["avisos"],
            "umbral_deuda_aplicado": veredicto["umbral_deuda_aplicado"],
            "confidence_score": confidence_score,
            "discrepancies": discrepancies,
            "procedencia": procedencia,
        }

        if veredicto["evaluable"]:
            # Las banderas rojas del Analista de Calidad no vetan aquí —el filtro
            # es de mínimos y debe seguir siendo simple y auditable— pero se
            # arrastran para que el informe no las pierda de vista.
            informe["banderas_calidad"] = quality.get("banderas_rojas", []) or []
            informe["umbrales"] = veredicto["umbrales"]
            summary = self._resumen(ticker, sector, veredicto["status"],
                                    metrics, veredicto["umbral_deuda_aplicado"],
                                    veredicto["reasons"], veredicto["avisos"],
                                    confidence_score)
        else:
            summary = (
                f"{ticker}: NO EVALUABLE. " + "; ".join(veredicto["reasons"]) + ". "
                "No se emite veredicto fundamental: la ausencia de datos no es evidencia de "
                "deterioro, y tratarla como tal produciría un rechazo indistinguible del de una "
                "empresa realmente deteriorada."
            )

        informe["resumen_determinista"] = summary
        informe["summary"] = summary
        return informe

    # ------------------------------------------------------------------ #
    def prompt_usuario(self, state: FinancialAnalysisState,
                       informe: Dict[str, Any]) -> str:
        return prompt_gatekeeper(state.get("ticker", "UNKNOWN"),
                                 informe.get("sector", SECTOR_DESCONOCIDO), informe)

    def resumen_de_log(self, informe: Dict[str, Any]) -> str:
        estado = informe.get("status")
        destino = ("continúa a análisis técnico" if informe.get("passed_gatekeeper")
                   else "se detiene el flujo avanzado (ahorro de cómputo)")
        return f"{estado} · {destino}"

    # ------------------------------------------------------------------ #
    @staticmethod
    def _resumen(ticker: str, sector: str, estado: str, metrics: Dict[str, Any],
                 umbral_deuda: float, reasons: List[str], avisos: List[str],
                 confianza: float) -> str:
        def p(x, fmt="{:.1%}"):
            return fmt.format(x) if x is not None else "n/d"

        texto = (
            f"{ticker} ({sector}) — Métricas reconciliadas: crecimiento de ingresos "
            f"{p(metrics.get('revenue_growth'))}, margen neto "
            f"{p(metrics.get('net_margin'))}, deuda/patrimonio "
            f"{p(metrics.get('debt_to_equity'), '{:.2f}x')} frente a un límite de "
            f"{umbral_deuda:.2f}x, ROE {p(metrics.get('roe'))}, "
            f"P/E {p(metrics.get('pe_ratio'), '{:.1f}x')}. "
            f"Confianza en los datos: {confianza:.0%}. "
            f"Resultado: {estado}."
        )
        if reasons:
            texto += " Motivos: " + "; ".join(reasons) + "."
        if avisos:
            texto += " Avisos: " + " ".join(avisos)
        return texto
