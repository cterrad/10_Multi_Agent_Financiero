"""
Agente Gatekeeper Fundamental: primer filtro de control del grafo.

TRES CORRECCIONES SOBRE LA VERSIÓN ANTERIOR
-------------------------------------------
1. VEREDICTO DE TRES VÍAS. Antes solo había APROBADO y RECHAZADO, y un campo
   ausente valía `0.0`, así que una empresa sin cobertura de datos y otra
   realmente sin ingresos producían el mismo veredicto y los mismos motivos:
   «Margen Neto (0.0%) por debajo del umbral mínimo». Eso es afirmar un hecho
   contable cuando lo que hay es un vacío de información. Ahora existe
   DATOS_INSUFICIENTES, y el Fund Manager lo traduce a SIN OPINION en vez de a
   VENTA.

2. UMBRALES SENSIBLES AL SECTOR. Aplicar `MAX_DEBT_TO_EQUITY = 3.0` a un banco,
   a un REIT o a una utility regulada es un error de categoría: en esos
   sectores el apalancamiento alto es la estructura normal del negocio, no una
   señal de fragilidad. `GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR` recoge las
   excepciones y el informe declara siempre qué umbral se aplicó.

3. LA CONFIANZA EN LOS DATOS ES CONDICIÓN DE FILTRO, NO UNA NOTA AL PIE. Antes
   una confianza baja solo añadía una frase al resumen. Ahora, por debajo del
   umbral, el veredicto pasa a DATOS_INSUFICIENTES.

El gatekeeper sigue respondiendo sí/no. La graduación —cuánta calidad, a qué
precio, con cuánto crecimiento— es trabajo del `QualityAnalystAgent`, que corre
antes que él y cuyas puntuaciones el Fund Manager cruza con el momentum.
"""

from typing import Any, Dict, List, Optional

from src.config import (
    GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR,
    GATEKEEPER_INDUSTRIAS_SIN_MARGEN,
    MAX_DEBT_TO_EQUITY,
    MIN_NET_MARGIN,
    MIN_REVENUE_GROWTH,
    SECTOR_DESCONOCIDO,
    get_llm,
    texto_de_respuesta_llm,
)
from src.state import FinancialAnalysisState

# Por debajo de esta confianza en la reconciliación no se emite veredicto.
CONFIANZA_MINIMA_PARA_VEREDICTO = 0.55

# Magnitudes sin las cuales el filtro no es evaluable.
MAGNITUDES_EXIGIDAS = ("net_margin", "revenue_growth", "debt_to_equity")


class FundamentalAnalystAgent:
    """Evalúa la salud fundamental mínima exigible antes de seguir analizando."""

    def analyze(self, state: FinancialAnalysisState) -> Dict[str, Any]:
        ticker = state.get("ticker", "UNKNOWN")
        sector = state.get("sector") or SECTOR_DESCONOCIDO
        industria = state.get("industry") or "Desconocida"
        rec = state.get("reconciliation_data", {}) or {}
        metrics = rec.get("reconciled_metrics", {}) or {}
        quality = state.get("quality_report", {}) or {}

        confidence_score = rec.get("confidence_score", 1.0)
        discrepancies = rec.get("discrepancies", [])
        procedencia = rec.get("procedencia", {})

        # Las magnitudes llegan como None cuando no se conocen. Ese None NO se
        # convierte en cero en ningún punto de este agente.
        revenue_growth = metrics.get("revenue_growth")
        net_margin = metrics.get("net_margin")
        debt_to_equity = metrics.get("debt_to_equity")
        roe = metrics.get("roe")
        pe_ratio = metrics.get("pe_ratio")

        ausentes = [m for m in MAGNITUDES_EXIGIDAS if metrics.get(m) is None]
        umbral_deuda = GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR.get(sector, MAX_DEBT_TO_EQUITY)
        exento_margen = industria in GATEKEEPER_INDUSTRIAS_SIN_MARGEN

        reasons: List[str] = []
        avisos: List[str] = []
        criterios: List[Dict[str, Any]] = []

        # ------------------- Caso 1: no evaluable --------------------------
        if ausentes or confidence_score < CONFIANZA_MINIMA_PARA_VEREDICTO:
            motivos = []
            if ausentes:
                motivos.append("faltan magnitudes obligatorias: " + ", ".join(ausentes))
            if confidence_score < CONFIANZA_MINIMA_PARA_VEREDICTO:
                motivos.append(f"confianza en la reconciliación de {confidence_score:.0%}, "
                               f"por debajo del mínimo del {CONFIANZA_MINIMA_PARA_VEREDICTO:.0%}")
            summary = (
                f"{ticker}: NO EVALUABLE. " + "; ".join(motivos) + ". "
                "No se emite veredicto fundamental: la ausencia de datos no es evidencia de "
                "deterioro, y tratarla como tal produciría un rechazo indistinguible del de una "
                "empresa realmente deteriorada."
            )
            informe = {
                "passed_gatekeeper": False,
                "status": "DATOS_INSUFICIENTES",
                "evaluable": False,
                "sector": sector,
                "industria": industria,
                "metrics": metrics,
                "magnitudes_ausentes": ausentes,
                "criterios": [],
                "reasons": motivos,
                "avisos": avisos,
                "umbral_deuda_aplicado": umbral_deuda,
                "confidence_score": confidence_score,
                "discrepancies": discrepancies,
                "procedencia": procedencia,
                "resumen_determinista": summary,
                "summary": summary,
            }
            return self._con_texto_llm(informe, ticker, sector, "NO EVALUABLE",
                                       revenue_growth, net_margin, debt_to_equity, roe)

        # ------------------- Caso 2: evaluación ----------------------------
        passed = True

        if exento_margen:
            avisos.append(
                f"Industria {industria}: exenta del filtro de margen neto. Exigir rentabilidad "
                "positiva descartaría por definición el modelo de negocio; el control de riesgo "
                "se traslada a solvencia y caja, que evalúa el Analista de Calidad.")
            criterios.append({"criterio": "Margen neto", "valor": net_margin,
                              "umbral": None, "cumple": None, "exento": True})
        else:
            cumple = net_margin >= MIN_NET_MARGIN
            criterios.append({"criterio": "Margen neto", "valor": net_margin,
                              "umbral": MIN_NET_MARGIN, "cumple": cumple, "exento": False})
            if not cumple:
                passed = False
                reasons.append(f"Margen Neto ({net_margin:.1%}) por debajo del umbral mínimo "
                               f"({MIN_NET_MARGIN:.1%})")

        cumple = revenue_growth >= MIN_REVENUE_GROWTH
        criterios.append({"criterio": "Crecimiento de ingresos", "valor": revenue_growth,
                          "umbral": MIN_REVENUE_GROWTH, "cumple": cumple, "exento": False})
        if not cumple:
            passed = False
            reasons.append(f"Crecimiento de Ingresos ({revenue_growth:.1%}) por debajo del umbral "
                           f"mínimo ({MIN_REVENUE_GROWTH:.1%})")

        cumple = debt_to_equity <= umbral_deuda
        criterios.append({"criterio": "Deuda / Patrimonio", "valor": debt_to_equity,
                          "umbral": umbral_deuda, "cumple": cumple, "exento": False,
                          "umbral_sectorial": sector in GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR})
        if not cumple:
            passed = False
            reasons.append(f"Relación Deuda/Capital ({debt_to_equity:.2f}) excede el límite "
                           f"permitido para {sector} ({umbral_deuda:.2f})")

        if sector in GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR:
            avisos.append(f"Umbral de deuda ajustado a {umbral_deuda:.1f}x por ser {sector}, "
                          f"donde el apalancamiento alto es estructural "
                          f"(el umbral general es {MAX_DEBT_TO_EQUITY:.1f}x).")
        if discrepancies:
            avisos.append(f"{len(discrepancies)} discrepancia(s) entre proveedores; "
                          f"confianza rebajada al {confidence_score:.0%}.")

        # Las banderas rojas del Analista de Calidad no vetan aquí —el filtro
        # es de mínimos y debe seguir siendo simple y auditable— pero se
        # arrastran para que el informe no las pierda de vista.
        banderas = quality.get("banderas_rojas", []) or []

        status_text = "APROBADO" if passed else "RECHAZADO"
        summary = self._resumen(ticker, sector, status_text, revenue_growth, net_margin,
                                debt_to_equity, roe, pe_ratio, umbral_deuda, reasons,
                                avisos, confidence_score)

        informe = {
            "passed_gatekeeper": passed,
            "status": status_text,
            "evaluable": True,
            "sector": sector,
            "industria": industria,
            "metrics": metrics,
            "magnitudes_ausentes": [],
            "criterios": criterios,
            "reasons": reasons,
            "avisos": avisos,
            "banderas_calidad": banderas,
            "umbral_deuda_aplicado": umbral_deuda,
            "umbrales": {"margen_neto": MIN_NET_MARGIN,
                         "crecimiento_ingresos": MIN_REVENUE_GROWTH,
                         "deuda_patrimonio": umbral_deuda},
            "confidence_score": confidence_score,
            "discrepancies": discrepancies,
            "procedencia": procedencia,
            "resumen_determinista": summary,
            "summary": summary,
        }
        return self._con_texto_llm(informe, ticker, sector, status_text,
                                   revenue_growth, net_margin, debt_to_equity, roe)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _resumen(ticker: str, sector: str, estado: str, crecimiento: Optional[float],
                 margen: Optional[float], deuda: Optional[float], roe: Optional[float],
                 pe: Optional[float], umbral_deuda: float, reasons: List[str],
                 avisos: List[str], confianza: float) -> str:
        def p(x, fmt="{:.1%}"):
            return fmt.format(x) if x is not None else "n/d"

        texto = (
            f"{ticker} ({sector}) — Métricas reconciliadas: crecimiento de ingresos "
            f"{p(crecimiento)}, margen neto {p(margen)}, deuda/patrimonio "
            f"{p(deuda, '{:.2f}x')} frente a un límite de {umbral_deuda:.2f}x, ROE {p(roe)}, "
            f"P/E {p(pe, '{:.1f}x')}. Confianza en los datos: {confianza:.0%}. "
            f"Resultado: {estado}."
        )
        if reasons:
            texto += " Motivos: " + "; ".join(reasons) + "."
        if avisos:
            texto += " Avisos: " + " ".join(avisos)
        return texto

    @staticmethod
    def _con_texto_llm(informe: Dict[str, Any], ticker: str, sector: str, estado: str,
                       crecimiento: Optional[float], margen: Optional[float],
                       deuda: Optional[float], roe: Optional[float]) -> Dict[str, Any]:
        """
        Único punto donde interviene el LLM: reescribe `summary` y nada más.

        Se llama SIEMPRE después de fijar `passed_gatekeeper`, y usa
        `texto_de_respuesta_llm` porque los proveedores modernos devuelven
        `content` como lista de bloques; asignarlo directamente metía una lista
        de diccionarios de Python en el informe.
        """
        llm = get_llm()
        if not llm:
            return informe

        def p(x, fmt="{:.1%}"):
            return fmt.format(x) if x is not None else "no disponible"

        try:
            prompt = (
                f"Como Analista Fundamental Gatekeeper, resume la salud financiera de {ticker} "
                f"(sector {sector}):\n"
                f"- Crecimiento de ingresos: {p(crecimiento)}\n"
                f"- Margen neto: {p(margen)}\n"
                f"- Deuda/Patrimonio: {p(deuda, '{:.2f}x')}\n"
                f"- ROE: {p(roe)}\n"
                f"- Veredicto del filtro: {estado}\n"
                f"Escribe una justificación concisa en 2 frases. Si alguna métrica figura como "
                f"no disponible, dilo explícitamente en vez de asumir que vale cero."
            )
            texto = texto_de_respuesta_llm(llm.invoke(prompt))
            if texto:
                informe["summary"] = texto
        except Exception as e:
            err = str(e)
            if "Expecting ',' delimiter" in err or "JSONDecodeError" in err:
                print("[FundamentalAgent] Advertencia: el proveedor de LLM devolvió una respuesta "
                      "no válida (modelo restringido, token inválido o error del servidor). "
                      "Se conserva el resumen determinista.")
            else:
                print(f"[FundamentalAgent] Error al invocar LLM: {e}")
        return informe
