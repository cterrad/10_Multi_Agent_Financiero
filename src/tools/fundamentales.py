"""
Tools del gatekeeper fundamental: el filtro de mínimos, invocable.

A diferencia de `calidad.py` y `tecnico.py`, aquí la lógica no estaba en métodos
separados sino escrita dentro de `FundamentalAnalystAgent.analyze`. Se ha
extraído respetando el ORDEN exacto de evaluación, que no es cosmético:

  1. Primero se comprueba si el caso es evaluable (magnitudes obligatorias
     presentes y confianza suficiente). Si no lo es, se devuelve
     DATOS_INSUFICIENTES y NO se evalúa ningún criterio. Invertir este orden
     produciría un RECHAZADO apoyado en una comparación contra `None`.
  2. Solo entonces se aplican los tres criterios, cada uno con su umbral, y el
     de deuda con la excepción sectorial que le corresponda.

El veredicto es de tres vías —APROBADO, RECHAZADO, DATOS_INSUFICIENTES— porque
la ausencia de datos no es evidencia de deterioro y tratarla como tal producía
un rechazo indistinguible del de una empresa realmente deteriorada.
"""

from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from src.config import (
    GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR,
    GATEKEEPER_INDUSTRIAS_SIN_MARGEN,
    MAX_DEBT_TO_EQUITY,
    MIN_NET_MARGIN,
    MIN_REVENUE_GROWTH,
    SECTOR_DESCONOCIDO,
)

# Por debajo de esta confianza en la reconciliación no se emite veredicto.
CONFIANZA_MINIMA_PARA_VEREDICTO = 0.55

# Magnitudes sin las cuales el filtro no es evaluable.
MAGNITUDES_EXIGIDAS = ("net_margin", "revenue_growth", "debt_to_equity")


def _umbral_deuda(sector: str) -> float:
    return GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR.get(sector, MAX_DEBT_TO_EQUITY)


def _evaluar(sector: str, industria: str, metricas: Dict[str, Any],
             confianza: float, n_discrepancias: int) -> Dict[str, Any]:
    """
    Aplica el filtro de mínimos. Cuerpo trasladado desde el agente sin cambios
    de comportamiento; ver el encabezado del módulo sobre el orden.
    """
    revenue_growth = metricas.get("revenue_growth")
    net_margin = metricas.get("net_margin")
    debt_to_equity = metricas.get("debt_to_equity")

    ausentes = [m for m in MAGNITUDES_EXIGIDAS if metricas.get(m) is None]
    umbral_deuda = _umbral_deuda(sector)
    exento_margen = industria in GATEKEEPER_INDUSTRIAS_SIN_MARGEN

    reasons: List[str] = []
    avisos: List[str] = []
    criterios: List[Dict[str, Any]] = []

    # ------------------- Caso 1: no evaluable ------------------------------
    if ausentes or confianza < CONFIANZA_MINIMA_PARA_VEREDICTO:
        motivos = []
        if ausentes:
            motivos.append("faltan magnitudes obligatorias: " + ", ".join(ausentes))
        if confianza < CONFIANZA_MINIMA_PARA_VEREDICTO:
            motivos.append(f"confianza en la reconciliación de {confianza:.0%}, "
                           f"por debajo del mínimo del {CONFIANZA_MINIMA_PARA_VEREDICTO:.0%}")
        return {
            "passed_gatekeeper": False,
            "status": "DATOS_INSUFICIENTES",
            "evaluable": False,
            "magnitudes_ausentes": ausentes,
            "criterios": [],
            "reasons": motivos,
            "avisos": avisos,
            "umbral_deuda_aplicado": umbral_deuda,
            "umbrales": None,
        }

    # ------------------- Caso 2: evaluación --------------------------------
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
    if n_discrepancias:
        avisos.append(f"{n_discrepancias} discrepancia(s) entre proveedores; "
                      f"confianza rebajada al {confianza:.0%}.")

    return {
        "passed_gatekeeper": passed,
        "status": "APROBADO" if passed else "RECHAZADO",
        "evaluable": True,
        "magnitudes_ausentes": [],
        "criterios": criterios,
        "reasons": reasons,
        "avisos": avisos,
        "umbral_deuda_aplicado": umbral_deuda,
        "umbrales": {"margen_neto": MIN_NET_MARGIN,
                     "crecimiento_ingresos": MIN_REVENUE_GROWTH,
                     "deuda_patrimonio": umbral_deuda},
    }


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #


@tool("evaluar_criterios_gatekeeper")
def evaluar_criterios_gatekeeper(sector: str, industria: str,
                                 metricas_reconciliadas: Dict[str, Any],
                                 confianza_datos: float,
                                 n_discrepancias: int = 0) -> Dict[str, Any]:
    """Filtro fundamental de mínimos: margen neto, crecimiento y apalancamiento.

    Emite un veredicto de TRES vías. APROBADO y RECHAZADO son juicios sobre la
    empresa; DATOS_INSUFICIENTES es un juicio sobre la información disponible, y
    se devuelve cuando falta alguna magnitud obligatoria o cuando la confianza
    de la reconciliación entre proveedores queda por debajo del mínimo. En ese
    caso no se evalúa ningún criterio: comparar contra un dato ausente produce
    un rechazo que los números no sustentan.

    El umbral de deuda es sensible al sector: aplicar el mismo límite a un banco
    que a una empresa de software es un error de categoría, y las excepciones
    están en `GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR`.

    Devuelve el veredicto, el detalle criterio a criterio con su umbral, los
    motivos del rechazo y los avisos que el informe debe declarar.
    """
    return _evaluar(sector or SECTOR_DESCONOCIDO, industria or "Desconocida",
                    metricas_reconciliadas or {}, confianza_datos, n_discrepancias)


@tool("umbral_deuda_sectorial")
def umbral_deuda_sectorial(sector: str) -> Dict[str, Any]:
    """Límite de deuda sobre patrimonio aplicable a un sector.

    Devuelve el umbral y si es una excepción sectorial o el general. En bancos,
    REITs y utilities reguladas el apalancamiento alto es la estructura normal
    del negocio, no una señal de fragilidad.
    """
    sector = sector or SECTOR_DESCONOCIDO
    return {"sector": sector,
            "umbral": _umbral_deuda(sector),
            "umbral_general": MAX_DEBT_TO_EQUITY,
            "es_excepcion_sectorial": sector in GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR}


TOOLS_FUNDAMENTALES = [evaluar_criterios_gatekeeper, umbral_deuda_sectorial]
