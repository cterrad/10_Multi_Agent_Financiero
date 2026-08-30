"""
Tools de calidad y valoración: las siete escuelas clásicas, invocables.

Antes cada escuela era un método privado de `QualityAnalystAgent`, una clase de
1 200 líneas. Eso las hacía incalculables por separado, inauditables una a una e
imposibles de exponer al agente investigador. Aquí son funciones de módulo con
su cuerpo INTACTO —el extracto es mecánico, no una reescritura— más una fachada
`@tool` que las hace invocables por nombre y serializa su entrada y su salida.

POR QUÉ HAY DOS CAPAS
---------------------
Los scorers operan sobre `Dict[str, Magnitud]`, que no es serializable y por
tanto no cabe en un `ToolMessage`. La implementación (`_altman`, `_graham`, ...)
conserva esa firma; la fachada (`calcular_altman`, `calcular_graham`, ...)
convierte en el borde con `detalle_magnitudes` / `magnitudes_desde_detalle`.

Una sola implementación por regla. Duplicar un scorer aquí y en el agente sería
exactamente el defecto que la arquitectura del proyecto prohíbe: la regla de
decisión vive en un único sitio y todo lo demás la llama.

Los docstrings de las fachadas son la descripción que lee el LLM en la rama
ReAct del agente investigador, así que se redactan como documentación de API.
"""

from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import tool

from src.config import (
    ALTMAN_SECTORES_MANUFACTURA,
    ALTMAN_Z_DISTRESS,
    ALTMAN_Z_SEGURO,
    ALTMAN_ZDD_DISTRESS,
    ALTMAN_ZDD_SEGURO,
    COBERTURA_MINIMA_ESTILO,
    DEVENGOS_ALERTA,
    DILUCION_ALERTA,
    ESTILO_CALIDAD_MINIMA,
    ESTILO_CRECIMIENTO_MINIMO,
    ESTILO_SOLVENCIA_MINIMA,
    ESTILO_TRAMPA_CALIDAD_MAXIMA,
    ESTILO_VALOR_MINIMO,
    FCF_YIELD_ACEPTABLE,
    FCF_YIELD_ATRACTIVO,
    GRAHAM_CURRENT_RATIO_MINIMO,
    GRAHAM_DEUDA_PATRIMONIO_MAXIMA,
    GRAHAM_MARGEN_SEGURIDAD_MINIMO,
    GRAHAM_MULTIPLICADOR,
    GRAHAM_PB_MAXIMO,
    GRAHAM_PE_MAXIMO,
    GREENBLATT_EY_ATRACTIVO,
    GREENBLATT_ROC_ATRACTIVO,
    LYNCH_CRECIMIENTO_RAPIDO,
    LYNCH_CRECIMIENTO_SOLIDO,
    MARGEN_BRUTO_FOSO,
    PEG_ATRACTIVO,
    PEG_CARO,
    PEG_MUY_ATRACTIVO,
    PESOS_CONVICCION,
    PIOTROSKI_DEBIL,
    PIOTROSKI_FUERTE,
    ROIC_ACEPTABLE,
    ROIC_EXCELENTE,
    SECTOR_DESCONOCIDO,
    SECTOR_NORMAS,
    SECTORES_CICLICOS,
    WACC_REFERENCIA,
)
from src.data.magnitudes import (
    Cobertura,
    Magnitud,
    detalle_magnitudes,
    magnitud,
    magnitudes_desde_detalle,
)


# Etiquetas de estilo. El orden de este tuple no implica jerarquía; la
# prioridad de asignación está en `_clasificar_estilo`.
ESTILOS = (
    "CALIDAD_COMPUESTA",
    "CALIDAD_DETERIORADA",
    "VALOR",
    "GARP",
    "CRECIMIENTO",
    "CICLICA",
    "TRAMPA_DE_VALOR",
    "ESPECULATIVA",
    "MIXTA",
)


def _escala(valor: Optional[float], malo: float, bueno: float) -> Optional[float]:
    """
    Normaliza una métrica a 0-100 por interpolación lineal acotada.

    `malo` y `bueno` marcan los extremos; `bueno < malo` invierte el sentido,
    que es lo que hace falta para métricas donde menos es mejor (P/E, devengos,
    deuda). Devuelve None si no hay dato, para que el promedio lo excluya en
    vez de contarlo como cero.
    """
    if valor is None:
        return None
    if bueno == malo:
        return 50.0
    t = (valor - malo) / (bueno - malo)
    return round(max(0.0, min(1.0, t)) * 100.0, 1)


def _promedio(componentes: Dict[str, Optional[float]]) -> Tuple[Optional[float], float, List[str]]:
    """
    Media de los componentes disponibles, con su cobertura.

    Devuelve `(puntuacion, cobertura, ausentes)`. Promediar solo lo disponible
    —en vez de imputar ceros— evita que la falta de un dato se confunda con un
    suspenso, que es exactamente el error que este proyecto arrastraba.
    """
    presentes = {k: v for k, v in componentes.items() if v is not None}
    ausentes = sorted(k for k, v in componentes.items() if v is None)
    if not presentes:
        return None, 0.0, ausentes
    puntuacion = round(sum(presentes.values()) / len(presentes), 1)
    return puntuacion, round(len(presentes) / len(componentes), 3), ausentes


def _serie(estados: Dict[str, Any], bloque: str, fila: str) -> List[Optional[float]]:
    return ((estados.get(bloque) or {}).get(fila) or [])


def _en(serie: List[Optional[float]], i: int) -> Optional[float]:
    """Elemento `i` de una serie anual (0 = ejercicio más reciente)."""
    return serie[i] if len(serie) > i else None


def _div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None or abs(b) < 1e-9:
        return None
    return a / b

# ================================================================== #
# Magnitudes base
# ================================================================== #
def _magnitudes_base(fundamentals: Dict[str, Any], estados: Dict[str, Any],
                     sec: Dict[str, Any], metricas_rec: Dict[str, Any],
                     tecnico: Dict[str, Any]) -> Dict[str, Magnitud]:
    """
    Reúne en un único mapa todo lo que los scorers necesitan, prefiriendo
    los estados financieros (cifra auditada, comparable interanualmente)
    sobre `yfinance.info` (agregado TTM sin trazabilidad).
    """
    def yfv(clave: str) -> Optional[float]:
        return fundamentals.get(clave)

    balance_activos = _en(_serie(estados, "balance", "activos_totales"), 0)
    balance_pasivos = _en(_serie(estados, "balance", "pasivos_totales"), 0)
    balance_patrimonio = _en(_serie(estados, "balance", "patrimonio"), 0)
    ebit = _en(_serie(estados, "resultados", "ebit"), 0)
    ingresos = _en(_serie(estados, "resultados", "ingresos"), 0)
    beneficio_neto = _en(_serie(estados, "resultados", "beneficio_neto"), 0)
    flujo_op = _en(_serie(estados, "flujos", "flujo_operativo"), 0)
    capex = _en(_serie(estados, "flujos", "capex"), 0)
    efectivo = _en(_serie(estados, "balance", "efectivo"), 0)
    deuda_total = _en(_serie(estados, "balance", "deuda_total"), 0)
    impuestos = _en(_serie(estados, "resultados", "impuestos"), 0)
    antes_impuestos = _en(_serie(estados, "resultados", "beneficio_antes_impuestos"), 0)

    precio = tecnico.get("close")
    capitalizacion = yfv("market_cap")
    # El capex viene con signo negativo en el estado de flujos.
    capex_abs = abs(capex) if capex is not None else None
    flujo_libre = (flujo_op - capex_abs) if (flujo_op is not None and capex_abs is not None) \
        else yfv("free_cashflow")

    tasa_impositiva = _div(impuestos, antes_impuestos)
    if tasa_impositiva is None or not (0.0 <= tasa_impositiva <= 0.6):
        # Fuera de ese rango la tasa efectiva es un artefacto contable
        # (créditos fiscales, pérdidas). Se usa la tasa legal estadounidense
        # como referencia declarada en lugar de propagar un valor absurdo.
        tasa_impositiva = 0.21

    nopat = ebit * (1.0 - tasa_impositiva) if ebit is not None else None
    capital_invertido = None
    if balance_patrimonio is not None and deuda_total is not None:
        capital_invertido = balance_patrimonio + deuda_total - (efectivo or 0.0)
    valor_empresa = yfv("enterprise_value")
    if valor_empresa is None and capitalizacion is not None and deuda_total is not None:
        valor_empresa = capitalizacion + deuda_total - (efectivo or 0.0)

    crudos: Dict[str, Tuple[Optional[float], str, str]] = {
        # (valor, fuente, unidad)
        "precio": (precio, "yfinance", "usd"),
        "capitalizacion": (capitalizacion, "yfinance", "usd"),
        "valor_empresa": (valor_empresa, "derivada", "usd"),
        "ingresos": (ingresos if ingresos is not None else sec.get("revenues"),
                     "estados financieros", "usd"),
        "beneficio_neto": (beneficio_neto if beneficio_neto is not None else sec.get("net_income"),
                           "estados financieros", "usd"),
        "ebit": (ebit, "estados financieros", "usd"),
        "activos_totales": (balance_activos if balance_activos is not None else sec.get("total_assets"),
                            "estados financieros", "usd"),
        "pasivos_totales": (balance_pasivos if balance_pasivos is not None else sec.get("total_liabilities"),
                            "estados financieros", "usd"),
        "patrimonio": (balance_patrimonio if balance_patrimonio is not None
                       else sec.get("stockholders_equity"), "estados financieros", "usd"),
        "flujo_operativo": (flujo_op, "estados financieros", "usd"),
        "capex": (capex_abs, "estados financieros", "usd"),
        "flujo_libre": (flujo_libre, "derivada", "usd"),
        "efectivo": (efectivo, "estados financieros", "usd"),
        "deuda_total": (deuda_total if deuda_total is not None else yfv("total_debt"),
                        "estados financieros", "usd"),
        "nopat": (nopat, "derivada", "usd"),
        "capital_invertido": (capital_invertido, "derivada", "usd"),
        "tasa_impositiva": (tasa_impositiva, "derivada", "pct"),
        # Ratios ya reconciliados: se toman del reconciliador para que el
        # gatekeeper y este agente no puedan discrepar entre sí.
        "margen_neto": (metricas_rec.get("net_margin"), "reconciliado", "pct"),
        "crecimiento_ingresos": (metricas_rec.get("revenue_growth"), "reconciliado", "pct"),
        "deuda_patrimonio": (metricas_rec.get("debt_to_equity"), "reconciliado", "veces"),
        "roe": (metricas_rec.get("roe"), "reconciliado", "pct"),
        "pe": (metricas_rec.get("pe_ratio"), "reconciliado", "veces"),
        "margen_bruto": (yfv("gross_margin"), "yfinance", "pct"),
        "margen_operativo": (yfv("operating_margin"), "yfinance", "pct"),
        "precio_valor_libro": (yfv("price_to_book"), "yfinance", "veces"),
        "precio_ventas": (yfv("price_to_sales"), "yfinance", "veces"),
        "ev_ebitda": (yfv("ev_to_ebitda"), "yfinance", "veces"),
        "bpa": (yfv("trailing_eps"), "yfinance", "usd"),
        "valor_libro_accion": (yfv("book_value_per_share"), "yfinance", "usd"),
        "ratio_corriente": (yfv("current_ratio"), "yfinance", "veces"),
        "crecimiento_beneficio": (yfv("earnings_growth"), "yfinance", "pct"),
        "rentabilidad_dividendo": (yfv("dividend_yield"), "yfinance", "pct"),
        "beta": (yfv("beta"), "yfinance", "ratio"),
        "volatilidad_anual": (tecnico.get("volatilidad_anual"), "derivada", "pct"),
    }

    base = {k: magnitud(v, fuente=f, unidad=u) for k, (v, f, u) in crudos.items()}

    # --- derivadas que dependen de las anteriores ---------------------
    base["roic"] = magnitud(_div(nopat, capital_invertido), "derivada", "pct")
    base["fcf_yield"] = magnitud(_div(flujo_libre, capitalizacion), "derivada", "pct")
    base["beneficio_propietario"] = magnitud(flujo_libre, "derivada (Buffett)", "usd")
    base["earnings_yield"] = magnitud(_div(ebit, valor_empresa), "derivada", "pct")
    base["rotacion_activos"] = magnitud(_div(ingresos, balance_activos), "derivada", "veces")
    base["cobertura_intereses"] = magnitud(
        _div(ebit, abs(_en(_serie(estados, "resultados", "gastos_financieros"), 0) or 0.0) or None),
        "derivada", "veces")
    return base

# ================================================================== #
# Piotroski
# ================================================================== #
def _piotroski(estados: Dict[str, Any], sec: Dict[str, Any]) -> Dict[str, Any]:
    """
    F-Score de 9 puntos.

    Cada criterio se evalúa solo si están los dos ejercicios que exige; los
    que no se pueden evaluar NO puntúan y se declaran, de modo que un
    F-Score de 5/9 con 7 criterios evaluables no se confunda con un 5/9
    completo. `score_normalizado` es la comparación honesta entre empresas
    con distinta cobertura.
    """
    activos = _serie(estados, "balance", "activos_totales")
    neto = _serie(estados, "resultados", "beneficio_neto")
    flujo = _serie(estados, "flujos", "flujo_operativo")
    deuda_lp = _serie(estados, "balance", "deuda_largo_plazo")
    act_corr = _serie(estados, "balance", "activo_corriente")
    pas_corr = _serie(estados, "balance", "pasivo_corriente")
    acciones = _serie(estados, "balance", "acciones_emitidas")
    bruto = _serie(estados, "resultados", "beneficio_bruto")
    ingresos = _serie(estados, "resultados", "ingresos")

    criterios: List[Dict[str, Any]] = []

    def evaluar(nombre: str, condicion: Optional[bool], detalle: str) -> None:
        criterios.append({
            "criterio": nombre,
            "cumple": condicion,
            "evaluable": condicion is not None,
            "detalle": detalle,
        })

    roa_0 = _div(_en(neto, 0), _en(activos, 0))
    roa_1 = _div(_en(neto, 1), _en(activos, 1))
    evaluar("ROA positivo", None if roa_0 is None else roa_0 > 0,
            f"ROA={roa_0:.2%}" if roa_0 is not None else "sin datos")
    evaluar("Flujo de caja operativo positivo",
            None if _en(flujo, 0) is None else _en(flujo, 0) > 0,
            f"FCO={_en(flujo, 0):,.0f}" if _en(flujo, 0) is not None else "sin datos")
    evaluar("ROA en mejora",
            None if (roa_0 is None or roa_1 is None) else roa_0 > roa_1,
            f"{roa_1:.2%} → {roa_0:.2%}" if (roa_0 is not None and roa_1 is not None) else "sin datos")
    # Calidad del beneficio: la caja debe superar al beneficio contable.
    evaluar("Flujo operativo > beneficio neto",
            None if (_en(flujo, 0) is None or _en(neto, 0) is None)
            else _en(flujo, 0) > _en(neto, 0),
            "devengos bajos" if (_en(flujo, 0) is not None and _en(neto, 0) is not None
                                 and _en(flujo, 0) > _en(neto, 0)) else "sin datos o devengos altos")

    apal_0 = _div(_en(deuda_lp, 0), _en(activos, 0))
    apal_1 = _div(_en(deuda_lp, 1), _en(activos, 1))
    evaluar("Apalancamiento a largo plazo a la baja",
            None if (apal_0 is None or apal_1 is None) else apal_0 <= apal_1,
            f"{apal_1:.2%} → {apal_0:.2%}" if (apal_0 is not None and apal_1 is not None) else "sin datos")

    corr_0 = _div(_en(act_corr, 0), _en(pas_corr, 0))
    corr_1 = _div(_en(act_corr, 1), _en(pas_corr, 1))
    evaluar("Ratio corriente en mejora",
            None if (corr_0 is None or corr_1 is None) else corr_0 > corr_1,
            f"{corr_1:.2f} → {corr_0:.2f}" if (corr_0 is not None and corr_1 is not None) else "sin datos")

    evaluar("Sin emisión neta de acciones",
            None if (_en(acciones, 0) is None or _en(acciones, 1) is None)
            else _en(acciones, 0) <= _en(acciones, 1) * 1.02,
            "dilución controlada" if (_en(acciones, 0) is not None and _en(acciones, 1) is not None)
            else "sin datos")

    mb_0 = _div(_en(bruto, 0), _en(ingresos, 0))
    mb_1 = _div(_en(bruto, 1), _en(ingresos, 1))
    evaluar("Margen bruto en mejora",
            None if (mb_0 is None or mb_1 is None) else mb_0 > mb_1,
            f"{mb_1:.2%} → {mb_0:.2%}" if (mb_0 is not None and mb_1 is not None) else "sin datos")

    rot_0 = _div(_en(ingresos, 0), _en(activos, 0))
    rot_1 = _div(_en(ingresos, 1), _en(activos, 1))
    evaluar("Rotación de activos en mejora",
            None if (rot_0 is None or rot_1 is None) else rot_0 > rot_1,
            f"{rot_1:.2f}x → {rot_0:.2f}x" if (rot_0 is not None and rot_1 is not None) else "sin datos")

    evaluables = [c for c in criterios if c["evaluable"]]
    score = sum(1 for c in evaluables if c["cumple"])
    n_eval = len(evaluables)

    if n_eval == 0:
        lectura = "NO_EVALUABLE"
    elif score >= PIOTROSKI_FUERTE:
        lectura = "FUERTE"
    elif score <= PIOTROSKI_DEBIL:
        lectura = "DEBIL"
    else:
        lectura = "INTERMEDIO"

    return {
        "score": score if n_eval else None,
        "criterios_evaluables": n_eval,
        "score_normalizado": round(9.0 * score / n_eval, 1) if n_eval else None,
        "lectura": lectura,
        "detalle": criterios,
    }

# ================================================================== #
# Altman
# ================================================================== #
def _altman(base: Dict[str, Magnitud], estados: Dict[str, Any],
            sector: str) -> Dict[str, Any]:
    """
    Z-Score de solvencia. Variante Z clásica para manufactureras y Z'' para
    el resto, que es como Altman la calibró: aplicar el Z de 1968 a una
    empresa de software da lecturas sistemáticamente pesimistas porque la
    rotación de activos (X5) penaliza los modelos ligeros en capital.
    """
    act_corr = _en(_serie(estados, "balance", "activo_corriente"), 0)
    pas_corr = _en(_serie(estados, "balance", "pasivo_corriente"), 0)
    retenidos = _en(_serie(estados, "balance", "beneficios_retenidos"), 0)

    activos = base["activos_totales"].valor if base["activos_totales"].disponible else None
    pasivos = base["pasivos_totales"].valor if base["pasivos_totales"].disponible else None
    ebit = base["ebit"].valor if base["ebit"].disponible else None
    ingresos = base["ingresos"].valor if base["ingresos"].disponible else None
    capitalizacion = base["capitalizacion"].valor if base["capitalizacion"].disponible else None
    patrimonio = base["patrimonio"].valor if base["patrimonio"].disponible else None

    circulante = (act_corr - pas_corr) if (act_corr is not None and pas_corr is not None) else None
    x1 = _div(circulante, activos)
    x2 = _div(retenidos, activos)
    x3 = _div(ebit, activos)
    x5 = _div(ingresos, activos)

    manufactura = sector in ALTMAN_SECTORES_MANUFACTURA
    variante = "Z (manufactureras)" if manufactura else "Z'' (no manufactureras)"

    if manufactura:
        x4 = _div(capitalizacion, pasivos)
        componentes = {"X1": x1, "X2": x2, "X3": x3, "X4": x4, "X5": x5}
        pesos = {"X1": 1.2, "X2": 1.4, "X3": 3.3, "X4": 0.6, "X5": 1.0}
        seguro, distress = ALTMAN_Z_SEGURO, ALTMAN_Z_DISTRESS
    else:
        x4 = _div(patrimonio, pasivos)
        componentes = {"X1": x1, "X2": x2, "X3": x3, "X4": x4}
        pesos = {"X1": 6.56, "X2": 3.26, "X3": 6.72, "X4": 1.05}
        seguro, distress = ALTMAN_ZDD_SEGURO, ALTMAN_ZDD_DISTRESS

    faltan = [k for k, v in componentes.items() if v is None]
    if faltan:
        return {
            "z": None, "variante": variante, "zona": "NO_EVALUABLE",
            "componentes": componentes, "componentes_ausentes": faltan,
            "umbral_seguro": seguro, "umbral_distress": distress,
        }

    z = round(sum(pesos[k] * componentes[k] for k in componentes), 2)
    zona = "SEGURA" if z > seguro else ("DISTRESS" if z < distress else "GRIS")
    return {
        "z": z, "variante": variante, "zona": zona,
        "componentes": {k: round(v, 4) for k, v in componentes.items()},
        "componentes_ausentes": [],
        "umbral_seguro": seguro, "umbral_distress": distress,
    }

# ================================================================== #
# Graham
# ================================================================== #
def _graham(base: Dict[str, Magnitud], fundamentals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Número de Graham y criterios del inversor defensivo.

    El Número de Graham —raíz de 22.5 × BPA × valor contable por acción—
    solo tiene sentido con beneficio y patrimonio positivos. Con BPA
    negativo no se devuelve un número imaginario ni un cero: se declara
    NO_APLICABLE, porque una empresa en pérdidas está fuera del universo
    que Graham describía.
    """
    bpa = base["bpa"].valor if base["bpa"].disponible else None
    vlpa = base["valor_libro_accion"].valor if base["valor_libro_accion"].disponible else None
    precio = base["precio"].valor if base["precio"].disponible else None
    pe = base["pe"].valor if base["pe"].disponible else None
    pb = base["precio_valor_libro"].valor if base["precio_valor_libro"].disponible else None
    corriente = base["ratio_corriente"].valor if base["ratio_corriente"].disponible else None
    de = base["deuda_patrimonio"].valor if base["deuda_patrimonio"].disponible else None

    numero = None
    margen_seguridad = None
    if bpa is not None and vlpa is not None and bpa > 0 and vlpa > 0:
        numero = round((GRAHAM_MULTIPLICADOR * bpa * vlpa) ** 0.5, 2)
        if precio:
            margen_seguridad = round((numero - precio) / numero, 4)

    criterios = [
        {"criterio": f"P/E < {GRAHAM_PE_MAXIMO:.0f}",
         "cumple": None if pe is None else (0 < pe < GRAHAM_PE_MAXIMO),
         "valor": pe},
        {"criterio": f"P/VC < {GRAHAM_PB_MAXIMO}",
         "cumple": None if pb is None else (0 < pb < GRAHAM_PB_MAXIMO),
         "valor": pb},
        {"criterio": f"P/E x P/VC < {GRAHAM_MULTIPLICADOR}",
         "cumple": None if (pe is None or pb is None) else (0 < pe * pb < GRAHAM_MULTIPLICADOR),
         "valor": round(pe * pb, 2) if (pe is not None and pb is not None) else None},
        {"criterio": f"Ratio corriente > {GRAHAM_CURRENT_RATIO_MINIMO}",
         "cumple": None if corriente is None else corriente > GRAHAM_CURRENT_RATIO_MINIMO,
         "valor": corriente},
        {"criterio": f"Deuda/Patrimonio < {GRAHAM_DEUDA_PATRIMONIO_MAXIMA}",
         "cumple": None if de is None else de < GRAHAM_DEUDA_PATRIMONIO_MAXIMA,
         "valor": de},
    ]
    evaluables = [c for c in criterios if c["cumple"] is not None]
    cumplidos = sum(1 for c in evaluables if c["cumple"])

    return {
        "numero_graham": numero,
        "estado_numero": "OK" if numero is not None else "NO_APLICABLE (BPA o valor contable no positivos)",
        "margen_seguridad": margen_seguridad,
        "margen_exigido": GRAHAM_MARGEN_SEGURIDAD_MINIMO,
        "cumple_margen": None if margen_seguridad is None
                         else margen_seguridad >= GRAHAM_MARGEN_SEGURIDAD_MINIMO,
        "criterios": criterios,
        "criterios_cumplidos": cumplidos,
        "criterios_evaluables": len(evaluables),
    }

# ================================================================== #
# Greenblatt / Buffett / Lynch / Sloan
# ================================================================== #
def _greenblatt(base: Dict[str, Magnitud]) -> Dict[str, Any]:
    """Fórmula mágica: rendimiento del beneficio y rentabilidad del capital."""
    ey = base["earnings_yield"].valor if base["earnings_yield"].disponible else None
    roic = base["roic"].valor if base["roic"].disponible else None
    return {
        "earnings_yield": round(ey, 4) if ey is not None else None,
        "return_on_capital": round(roic, 4) if roic is not None else None,
        "ey_atractivo": None if ey is None else ey >= GREENBLATT_EY_ATRACTIVO,
        "roc_atractivo": None if roic is None else roic >= GREENBLATT_ROC_ATRACTIVO,
        "umbral_ey": GREENBLATT_EY_ATRACTIVO,
        "umbral_roc": GREENBLATT_ROC_ATRACTIVO,
    }

def _buffett(base: Dict[str, Magnitud], estados: Dict[str, Any]) -> Dict[str, Any]:
    """
    Criterios de negocio excelente: ROIC por encima del coste del capital,
    margen bruto alto como aproximación al foso, y beneficio del
    propietario positivo.
    """
    roic = base["roic"].valor if base["roic"].disponible else None
    margen_bruto = base["margen_bruto"].valor if base["margen_bruto"].disponible else None
    fcf_yield = base["fcf_yield"].valor if base["fcf_yield"].disponible else None
    flujo_libre = base["flujo_libre"].valor if base["flujo_libre"].disponible else None

    # Dilución: variación de acciones en circulación entre los dos últimos
    # ejercicios. Un ROE alto financiado emitiendo acciones no llega al
    # accionista existente.
    acciones = _serie(estados, "balance", "acciones_emitidas")
    dilucion = None
    if _en(acciones, 0) is not None and _en(acciones, 1):
        dilucion = _en(acciones, 0) / _en(acciones, 1) - 1.0

    return {
        "roic": round(roic, 4) if roic is not None else None,
        "wacc_referencia": WACC_REFERENCIA,
        "roic_menos_wacc": round(roic - WACC_REFERENCIA, 4) if roic is not None else None,
        "crea_valor": None if roic is None else roic > WACC_REFERENCIA,
        "roic_excelente": None if roic is None else roic >= ROIC_EXCELENTE,
        "margen_bruto": round(margen_bruto, 4) if margen_bruto is not None else None,
        "indicio_de_foso": None if margen_bruto is None else margen_bruto >= MARGEN_BRUTO_FOSO,
        "beneficio_propietario": flujo_libre,
        "fcf_yield": round(fcf_yield, 4) if fcf_yield is not None else None,
        "dilucion_anual": round(dilucion, 4) if dilucion is not None else None,
        "dilucion_excesiva": None if dilucion is None else dilucion > DILUCION_ALERTA,
    }

def _lynch(base: Dict[str, Magnitud], sector: str) -> Dict[str, Any]:
    """
    PEG y taxonomía de Lynch.

    El PEG se calcula contra el crecimiento de BENEFICIO cuando existe y,
    en su defecto, contra el de ingresos, declarando cuál se ha usado: son
    cosas distintas y presentarlas como la misma es lo que produce PEG
    engañosamente bajos en empresas que crecen en ventas sin ganar dinero.
    """
    pe = base["pe"].valor if base["pe"].disponible else None
    crec_bpa = base["crecimiento_beneficio"].valor if base["crecimiento_beneficio"].disponible else None
    crec_ing = base["crecimiento_ingresos"].valor if base["crecimiento_ingresos"].disponible else None

    crecimiento, base_crec = (crec_bpa, "beneficio") if crec_bpa is not None \
        else (crec_ing, "ingresos")

    peg = None
    if pe is not None and pe > 0 and crecimiento is not None and crecimiento > 0.01:
        peg = round(pe / (crecimiento * 100.0), 2)

    if peg is None:
        lectura = "NO_EVALUABLE"
    elif peg <= PEG_MUY_ATRACTIVO:
        lectura = "MUY_ATRACTIVO"
    elif peg <= PEG_ATRACTIVO:
        lectura = "ATRACTIVO"
    elif peg <= PEG_CARO:
        lectura = "EXIGENTE"
    else:
        lectura = "CARO"

    crec = crecimiento if crecimiento is not None else 0.0
    if sector in SECTORES_CICLICOS:
        categoria = "CICLICA"
    elif crec >= LYNCH_CRECIMIENTO_RAPIDO:
        categoria = "CRECIMIENTO_RAPIDO"
    elif crec >= LYNCH_CRECIMIENTO_SOLIDO:
        categoria = "SOLIDA"
    elif crecimiento is None:
        categoria = "NO_EVALUABLE"
    elif crec < 0:
        categoria = "EN_CONTRACCION"
    else:
        categoria = "LENTO_CRECIMIENTO"

    return {
        "peg": peg,
        "lectura_peg": lectura,
        "crecimiento_usado": round(crecimiento, 4) if crecimiento is not None else None,
        "base_del_crecimiento": base_crec if crecimiento is not None else None,
        "categoria_lynch": categoria,
    }

def _devengos(base: Dict[str, Magnitud]) -> Dict[str, Any]:
    """Ratio de devengos de Sloan: (beneficio − caja operativa) / activos."""
    neto = base["beneficio_neto"].valor if base["beneficio_neto"].disponible else None
    flujo = base["flujo_operativo"].valor if base["flujo_operativo"].disponible else None
    activos = base["activos_totales"].valor if base["activos_totales"].disponible else None
    ratio = None
    if neto is not None and flujo is not None and activos:
        ratio = (neto - flujo) / activos
    return {
        "ratio_devengos": round(ratio, 4) if ratio is not None else None,
        "umbral_alerta": DEVENGOS_ALERTA,
        "alerta": None if ratio is None else ratio > DEVENGOS_ALERTA,
        "lectura": ("beneficio respaldado por caja" if (ratio is not None and ratio <= 0)
                    else "beneficio con componente de devengo" if ratio is not None
                    else "no evaluable"),
    }

# ================================================================== #
# Contexto sectorial
# ================================================================== #
def _contexto_sectorial(base: Dict[str, Magnitud], sector: str) -> Dict[str, Any]:
    """
    Compara los múltiplos contra la norma del sector.

    «P/E elevado» sin referencia era una afirmación vacía: 17x es caro en
    una minera y barato en software. Aquí cada múltiplo se expresa como
    proporción de la norma sectorial y se traduce a una lectura.
    """
    norma = SECTOR_NORMAS.get(sector, SECTOR_NORMAS[SECTOR_DESCONOCIDO])
    comparaciones = {}

    for clave, clave_norma, mas_es_mejor in (
        ("pe", "pe", False),
        ("margen_neto", "margen_neto", True),
        ("deuda_patrimonio", "deuda_patrimonio", False),
        ("crecimiento_ingresos", "crecimiento", True),
    ):
        m = base.get(clave)
        referencia = norma[clave_norma]
        if m is None or not m.disponible or not referencia:
            comparaciones[clave] = {"valor": None, "referencia_sector": referencia,
                                    "ratio": None, "lectura": "no evaluable"}
            continue
        valor = float(m.valor)
        ratio = valor / referencia if referencia else None
        if ratio is None:
            lectura = "no evaluable"
        elif mas_es_mejor:
            lectura = ("muy por encima del sector" if ratio >= 1.5 else
                       "por encima del sector" if ratio >= 1.1 else
                       "en línea con el sector" if ratio >= 0.9 else
                       "por debajo del sector")
        else:
            lectura = ("muy por encima del sector" if ratio >= 1.5 else
                       "por encima del sector" if ratio >= 1.1 else
                       "en línea con el sector" if ratio >= 0.9 else
                       "por debajo del sector")
        comparaciones[clave] = {
            "valor": round(valor, 4),
            "referencia_sector": referencia,
            "ratio": round(ratio, 2) if ratio is not None else None,
            "lectura": lectura,
        }

    return {
        "sector": sector,
        "norma_aplicada": norma,
        "es_ciclico": sector in SECTORES_CICLICOS,
        "comparaciones": comparaciones,
        "advertencia": ("Las normas sectoriales son medianas estáticas de largo plazo "
                        "del mercado estadounidense, no la mediana viva del sector hoy. "
                        "Sirven para ordenar y contextualizar, no para valorar."),
    }

# ================================================================== #
# Puntuaciones
# ================================================================== #
def _puntuaciones(base: Dict[str, Magnitud], piotroski: Dict[str, Any],
                  altman: Dict[str, Any], graham: Dict[str, Any],
                  greenblatt: Dict[str, Any], buffett: Dict[str, Any],
                  lynch: Dict[str, Any], devengos: Dict[str, Any]):
    """
    Cuatro puntuaciones de 0 a 100 y la cobertura con que se calculó cada
    una. Los extremos de cada escala son los umbrales publicados de cada
    escuela, no percentiles del universo: así el número significa lo mismo
    hoy que dentro de un año, independientemente de qué tickers se analicen.
    """
    def v(clave: str) -> Optional[float]:
        m = base.get(clave)
        return float(m.valor) if (m is not None and m.disponible) else None

    calidad = {
        "roic": _escala(v("roic"), 0.0, ROIC_EXCELENTE * 1.6),
        "margen_bruto": _escala(v("margen_bruto"), 0.10, 0.70),
        "margen_operativo": _escala(v("margen_operativo"), -0.05, 0.35),
        "roe": _escala(v("roe"), 0.0, 0.35),
        "piotroski": _escala(piotroski.get("score_normalizado"), 2.0, 8.0),
        "devengos": _escala(devengos.get("ratio_devengos"), DEVENGOS_ALERTA, -0.10),
        "rotacion": _escala(v("rotacion_activos"), 0.2, 1.5),
    }
    valoracion = {
        "pe": _escala(v("pe") if (v("pe") or 0) > 0 else None, 45.0, 10.0),
        "ev_ebitda": _escala(v("ev_ebitda") if (v("ev_ebitda") or 0) > 0 else None, 25.0, 7.0),
        "fcf_yield": _escala(v("fcf_yield"), 0.0, FCF_YIELD_ATRACTIVO * 1.5),
        "earnings_yield": _escala(v("earnings_yield"), 0.0, GREENBLATT_EY_ATRACTIVO * 1.8),
        "precio_valor_libro": _escala(
            v("precio_valor_libro") if (v("precio_valor_libro") or 0) > 0 else None, 8.0, 1.0),
        "margen_graham": _escala(graham.get("margen_seguridad"), -0.50, 0.40),
        "peg": _escala(lynch.get("peg"), PEG_CARO * 1.5, PEG_MUY_ATRACTIVO),
    }
    crecimiento = {
        "ingresos": _escala(v("crecimiento_ingresos"), -0.05, 0.35),
        "beneficio": _escala(v("crecimiento_beneficio"), -0.10, 0.35),
        "reinversion": _escala(v("roic"), 0.0, ROIC_EXCELENTE * 1.4),
    }
    solvencia = {
        "altman": _escala(altman.get("z"),
                          altman.get("umbral_distress", 1.1),
                          altman.get("umbral_seguro", 2.6) * 1.4),
        "deuda_patrimonio": _escala(v("deuda_patrimonio"), 4.0, 0.20),
        "ratio_corriente": _escala(v("ratio_corriente"), 0.6, 2.5),
        "cobertura_intereses": _escala(v("cobertura_intereses"), 1.0, 10.0),
        "flujo_libre": _escala(v("fcf_yield"), -0.05, FCF_YIELD_ACEPTABLE * 2),
        "dilucion": _escala(buffett.get("dilucion_anual"), DILUCION_ALERTA * 2.5, -0.02),
    }

    resultado, coberturas = {}, {}
    for nombre, componentes in (("calidad", calidad), ("valoracion", valoracion),
                                ("crecimiento", crecimiento), ("solvencia", solvencia)):
        puntuacion, cobertura, ausentes = _promedio(componentes)
        resultado[nombre] = puntuacion
        resultado[f"{nombre}_componentes"] = {k: val for k, val in componentes.items()}
        resultado[f"{nombre}_ausentes"] = ausentes
        coberturas[nombre] = cobertura

    return resultado, coberturas

def _conviccion(puntuaciones: Dict[str, Any], cobertura: float,
                banderas: List[str], confianza_datos: float) -> Dict[str, Any]:
    """
    Convicción fundamental 0-100.

    Tres correcciones sobre la media ponderada, todas en la misma
    dirección: no saber es motivo para arriesgar menos.
      · Cobertura de datos incompleta.
      · Confianza del reconciliador (desacuerdo entre proveedores).
      · Banderas rojas, que descuentan de forma lineal y acotada.
    """
    disponibles = {k: puntuaciones[k] for k in PESOS_CONVICCION
                   if puntuaciones.get(k) is not None}
    if not disponibles:
        return {"valor": None, "bruta": None, "motivo": "sin puntuaciones evaluables",
                "factor_cobertura": cobertura, "factor_confianza": confianza_datos,
                "descuento_banderas": 0.0}

    peso_total = sum(PESOS_CONVICCION[k] for k in disponibles)
    bruta = sum(PESOS_CONVICCION[k] * v for k, v in disponibles.items()) / peso_total

    # La cobertura no puede anular la convicción por sí sola, pero sí
    # recortarla hasta la mitad: el suelo de 0.5 evita que un dato ausente
    # convierta una empresa excelente en no invertible.
    factor_cobertura = 0.5 + 0.5 * min(1.0, cobertura / max(COBERTURA_MINIMA_ESTILO, 1e-6))
    factor_cobertura = min(1.0, factor_cobertura)
    descuento = min(30.0, 10.0 * len(banderas))

    valor = max(0.0, min(100.0, bruta * factor_cobertura * confianza_datos - descuento))
    return {
        "valor": round(valor, 1),
        "bruta": round(bruta, 1),
        "factor_cobertura": round(factor_cobertura, 3),
        "factor_confianza": round(confianza_datos, 3),
        "descuento_banderas": descuento,
        "pesos": PESOS_CONVICCION,
        "puntuaciones_usadas": sorted(disponibles),
    }

# ================================================================== #
# Banderas rojas y estilo
# ================================================================== #
def _banderas_rojas(base: Dict[str, Magnitud], piotroski: Dict[str, Any],
                    altman: Dict[str, Any], devengos: Dict[str, Any],
                    buffett: Dict[str, Any]) -> List[str]:
    """
    Condiciones que, por sí solas, justifican reducir tamaño o no operar.

    Solo se levanta la bandera cuando el dato EXISTE y es malo. Un dato
    ausente no es una bandera roja: se refleja en la cobertura, que ya
    recorta la convicción por otra vía.
    """
    banderas: List[str] = []

    def val(clave: str) -> Optional[float]:
        m = base.get(clave)
        return float(m.valor) if (m is not None and m.disponible) else None

    if altman.get("zona") == "DISTRESS":
        patrimonio_neg = (val("patrimonio") is not None and val("patrimonio") < 0)
        matiz = ("; el Z está distorsionado por un patrimonio contable negativo, así que "
                 "conviene leerlo junto a la generación de caja" if patrimonio_neg else "")
        banderas.append(
            f"Altman {altman['variante']} en zona de insolvencia "
            f"(Z={altman['z']} < {altman['umbral_distress']}){matiz}")
    if piotroski.get("lectura") == "DEBIL":
        banderas.append(
            f"F-Score de Piotroski débil ({piotroski['score']}/{piotroski['criterios_evaluables']} criterios evaluables)")
    if devengos.get("alerta"):
        banderas.append(
            f"Devengos elevados ({devengos['ratio_devengos']:.1%} de los activos): el beneficio no está respaldado por caja")
    if buffett.get("dilucion_excesiva"):
        banderas.append(
            f"Dilución del {buffett['dilucion_anual']:.1%} anual: el crecimiento por acción es menor que el agregado")

    margen = val("margen_neto")
    if margen is not None and margen < 0:
        banderas.append(f"Margen neto negativo ({margen:.1%})")
    fcf = val("flujo_libre")
    if fcf is not None and fcf < 0:
        banderas.append("Flujo de caja libre negativo: el negocio consume caja")
    de = val("deuda_patrimonio")
    if de is not None and de > 4.0:
        banderas.append(f"Apalancamiento muy elevado (Deuda/Patrimonio {de:.2f}x)")
    cobertura_int = val("cobertura_intereses")
    if cobertura_int is not None and cobertura_int < 1.5:
        banderas.append(f"Cobertura de intereses insuficiente ({cobertura_int:.2f}x)")
    roic = val("roic")
    if roic is not None and roic < 0:
        banderas.append(f"ROIC negativo ({roic:.1%}): destruye valor sobre el capital empleado")

    # El patrimonio neto negativo no aparece en ningún ratio porque los
    # ratios que lo llevan en el denominador se declaran ausentes: sin esta
    # bandera, una empresa con fondos propios negativos —normalmente por
    # años de recompras por encima del beneficio acumulado— pasaría sin
    # dejar rastro. No es necesariamente un problema (hay compounders que
    # operan así de forma sostenida), pero sí un hecho que el informe debe
    # declarar en vez de silenciar.
    patrimonio = val("patrimonio")
    if patrimonio is not None and patrimonio < 0:
        banderas.append(
            f"Patrimonio neto negativo (${patrimonio:,.0f}): los ratios sobre fondos "
            f"propios (deuda/patrimonio, ROE) no son interpretables")

    return banderas

def _clasificar_estilo(puntuaciones: Dict[str, Any], base: Dict[str, Magnitud],
                       lynch: Dict[str, Any], sector: str, cobertura: float,
                       banderas: List[str],
                       componentes: Optional[Dict[str, Any]] = None,
                       altman: Optional[Dict[str, Any]] = None):
    """
    Etiqueta de estilo. Reglas ordenadas por prioridad; la primera que se
    cumple gana, y el motivo se devuelve explícito para que el informe
    pueda justificar la etiqueta en vez de afirmarla.

    La distinción crítica es VALOR frente a TRAMPA_DE_VALOR: barato con
    calidad es valor; barato sin calidad es, la mayoría de las veces,
    barato por un motivo. Graham compraba lo primero; el sistema anterior
    no distinguía.
    """
    componentes = componentes or {}
    if cobertura < COBERTURA_MINIMA_ESTILO:
        return ("DATOS_INSUFICIENTES", [],
                f"Cobertura de datos {cobertura:.0%}, por debajo del mínimo "
                f"{COBERTURA_MINIMA_ESTILO:.0%} exigido para clasificar.")

    calidad = puntuaciones.get("calidad")
    valor = puntuaciones.get("valoracion")
    crecimiento = puntuaciones.get("crecimiento")
    solvencia = puntuaciones.get("solvencia")

    def valor_de(clave: str) -> Optional[float]:
        m = base.get(clave)
        return float(m.valor) if (m is not None and m.disponible) else None

    def sup(x: Optional[float], umbral: float) -> bool:
        return x is not None and x >= umbral

    def inf(x: Optional[float], umbral: float) -> bool:
        return x is not None and x <= umbral

    secundarias: List[str] = []
    if sector in SECTORES_CICLICOS:
        secundarias.append("CICLICA")
    rd = base.get("rentabilidad_dividendo")
    if rd is not None and rd.disponible and float(rd.valor) >= 0.03:
        secundarias.append("DIVIDENDO")
    if lynch.get("categoria_lynch") == "CRECIMIENTO_RAPIDO":
        secundarias.append("CRECIMIENTO_RAPIDO_LYNCH")
    if lynch.get("categoria_lynch") == "EN_CONTRACCION":
        secundarias.append("POSIBLE_REESTRUCTURACION")

    # 1. Solvencia comprometida manda sobre cualquier otra lectura.
    #
    # El Z-Score en zona de insolvencia entra aquí de forma explícita y no
    # solo a través de la puntuación de solvencia. El motivo es que esa
    # puntuación es un PROMEDIO de seis componentes: una empresa puede
    # sacar 61/100 en solvencia —arrastrada al alza por el ratio corriente
    # y por un deuda/patrimonio favorable— mientras su Altman está en
    # 0.04, muy por debajo del umbral de insolvencia. Promediar el riesgo
    # de quiebra con métricas de liquidez lo diluye justo cuando más
    # importa, y el resultado observado fue una empresa en zona de
    # insolvencia etiquetada como CALIDAD_COMPUESTA.
    # El Z-Score en zona de insolvencia entra aquí de forma explícita y no
    # solo a través de la puntuación de solvencia, que es un PROMEDIO de
    # seis componentes: una empresa puede sacar 61/100 en solvencia
    # —arrastrada al alza por el ratio corriente— mientras su Altman está
    # en 0.04. Promediar el riesgo de quiebra con métricas de liquidez lo
    # diluye justo cuando más importa.
    #
    # PERO el veto EXIGE CORROBORACIÓN DE CAJA, y esto no es una
    # concesión: el Z'' se calibró sobre empresas industriales y de
    # mercados emergentes, y dos de sus cuatro términos —beneficios
    # retenidos y valor contable de los fondos propios, ambos sobre
    # activos— se vuelven muy negativos en compañías que han recomprado
    # acciones por encima de su beneficio acumulado. Eso describe a buena
    # parte del software rentable, que genera caja de sobra y no tiene
    # ningún riesgo de quiebra. Marcarlas ESPECULATIVAS por un ratio de
    # 1968 sería un falso positivo sistemático de todo un sector.
    #
    # La corroboración que se exige es de CAJA, no contable: que el
    # negocio consuma caja, no pueda pagar sus intereses o pierda dinero
    # en la operativa. Con cualquiera de las tres, el Z está describiendo
    # un problema real; sin ninguna, está describiendo una estructura de
    # capital agresiva y se queda como bandera roja.
    zona_altman = (altman or {}).get("zona")
    fcf = valor_de("fcf_yield")
    cobertura_intereses = valor_de("cobertura_intereses")
    margen_operativo = valor_de("margen_operativo")

    estres_caja: List[str] = []
    if fcf is not None and fcf < 0:
        estres_caja.append("flujo de caja libre negativo")
    if cobertura_intereses is not None and cobertura_intereses < 1.5:
        estres_caja.append("cobertura de intereses insuficiente")
    if margen_operativo is not None and margen_operativo < 0:
        estres_caja.append("margen operativo negativo")

    if zona_altman == "DISTRESS" and estres_caja:
        return ("ESPECULATIVA", secundarias,
                f"Altman {(altman or {}).get('variante', 'Z-Score')} en "
                f"{(altman or {}).get('z')}, por debajo del umbral de insolvencia "
                f"({(altman or {}).get('umbral_distress')}), CORROBORADO por "
                f"{' y '.join(estres_caja)}: el riesgo de solvencia es real y domina "
                f"cualquier lectura de calidad, valor o crecimiento.")

    if inf(solvencia, 35) or len(banderas) >= 3:
        return ("ESPECULATIVA", secundarias,
                f"Solvencia {solvencia}/100 y {len(banderas)} bandera(s) roja(s): el perfil de "
                "riesgo domina cualquier lectura de valor o crecimiento.")

    # 2. Barato pero de mala calidad: trampa de valor.
    #
    # La comparación se hace contra los MÚLTIPLOS DE TITULAR (P/E, P/VC,
    # EV/EBITDA), no contra la puntuación compuesta de valoración. El motivo
    # es la mecánica misma de la trampa: lo que atrae al inversor es el
    # múltiplo contable barato que aparece en cualquier filtro. La
    # puntuación compuesta incluye el rendimiento del flujo de caja libre,
    # que en una trampa de valor suele ser malo y arrastra el compuesto a
    # zona neutra — precisamente el caso que hay que detectar se quedaba sin
    # etiquetar por promediar la señal de alarma con la señal de reclamo.
    titulares = {k: componentes.get(k) for k in
                 ("pe", "precio_valor_libro", "ev_ebitda")}
    valor_titular, _, _ = _promedio(titulares)
    if sup(valor_titular, ESTILO_VALOR_MINIMO) and inf(calidad, ESTILO_TRAMPA_CALIDAD_MAXIMA):
        return ("TRAMPA_DE_VALOR", secundarias,
                f"Múltiplos contables atractivos ({valor_titular}/100 en P/E, P/VC y "
                f"EV/EBITDA) sobre una calidad de negocio de {calidad}/100: el descuento "
                f"parece justificado por el deterioro, no una oportunidad. La valoración "
                f"compuesta, que sí incorpora el flujo de caja, se queda en {valor}/100.")

    # 3. Negocio excelente a precio razonable: la compounder de Buffett.
    #
    # El límite de una bandera roja no es cosmético. La etiqueta describe el
    # NEGOCIO, no el precio, así que puede convivir con una valoración
    # exigente; pero no con dos defectos estructurales simultáneos —déficit
    # de caja, devengos altos, dilución, patrimonio negativo—. Sin este
    # corte, el informe llegaba a imprimir `CALIDAD_COMPUESTA` junto a dos
    # banderas rojas y una convicción de 19/100, y esa combinación no la
    # firma ningún analista.
    if (sup(calidad, ESTILO_CALIDAD_MINIMA) and sup(solvencia, ESTILO_SOLVENCIA_MINIMA)
            and (crecimiento is None or crecimiento >= 40) and len(banderas) <= 1):
        return ("CALIDAD_COMPUESTA", secundarias,
                f"Calidad {calidad}/100 y solvencia {solvencia}/100 con crecimiento sostenido: "
                "negocio capaz de reinvertir por encima de su coste de capital.")

    # 3-bis. Calidad alta pero con varios defectos estructurales a la vez.
    # No es una compounder ni una especulativa: es un buen negocio con
    # problemas concretos que el informe debe nombrar en vez de suavizar.
    if sup(calidad, ESTILO_CALIDAD_MINIMA) and len(banderas) >= 2:
        return ("CALIDAD_DETERIORADA", secundarias,
                f"Calidad de negocio alta ({calidad}/100) pero con {len(banderas)} defectos "
                f"estructurales simultáneos: {'; '.join(banderas[:2])}. La rentabilidad del "
                f"negocio no compensa por sí sola un balance o una calidad contable "
                f"deteriorados.")

    # 4. Crecimiento a precio razonable: el GARP de Lynch.
    if (sup(crecimiento, 55) and lynch.get("peg") is not None
            and lynch["peg"] <= PEG_ATRACTIVO and sup(calidad, 50)):
        return ("GARP", secundarias,
                f"Crecimiento {crecimiento}/100 con PEG de {lynch['peg']}: se paga el crecimiento "
                "a un múltiplo que el propio crecimiento justifica.")

    # 5. Crecimiento puro: caro por definición, el riesgo es de ejecución.
    if sup(crecimiento, ESTILO_CRECIMIENTO_MINIMO):
        return ("CRECIMIENTO", secundarias,
                f"Crecimiento {crecimiento}/100 frente a valoración {valor}/100: la tesis depende "
                "de que el crecimiento se mantenga; el múltiplo no ofrece margen de error.")

    # 6. Valor con calidad suficiente.
    if sup(valor, ESTILO_VALOR_MINIMO) and sup(calidad, 45):
        return ("VALOR", secundarias,
                f"Valoración {valor}/100 con calidad de {calidad}/100: descuento sobre un negocio "
                "que sigue funcionando.")

    # 7. Cíclica: se etiqueta como principal solo si nada anterior encajó.
    if sector in SECTORES_CICLICOS:
        return ("CICLICA", [s for s in secundarias if s != "CICLICA"],
                f"Sector cíclico ({sector}) sin una lectura dominante de valor, calidad ni "
                "crecimiento: el múltiplo depende de la fase del ciclo, no del negocio.")

    return ("MIXTA", secundarias,
            f"Perfil sin dominancia clara (calidad {calidad}, valoración {valor}, "
            f"crecimiento {crecimiento}, solvencia {solvencia}).")

# ================================================================== #
# Resumen determinista
# ================================================================== #
def _resumen_determinista(ticker: str, estilo: str, puntuaciones: Dict[str, Any],
                          conviccion: Dict[str, Any], piotroski: Dict[str, Any],
                          altman: Dict[str, Any], graham: Dict[str, Any],
                          buffett: Dict[str, Any], lynch: Dict[str, Any],
                          banderas: List[str], cobertura: float, status: str) -> str:
    def n(x, sufijo="/100"):
        return f"{x}{sufijo}" if x is not None else "n/d"

    partes = [
        f"Calidad y Valoración de {ticker}: estilo {estilo}.",
        f"Calidad {n(puntuaciones.get('calidad'))}, Valoración {n(puntuaciones.get('valoracion'))}, "
        f"Crecimiento {n(puntuaciones.get('crecimiento'))}, Solvencia {n(puntuaciones.get('solvencia'))}.",
        f"Convicción fundamental {n(conviccion.get('valor'))}.",
        f"Piotroski {piotroski.get('score')}/{piotroski.get('criterios_evaluables')} evaluables "
        f"({piotroski.get('lectura')}); Altman {altman.get('variante')} = {altman.get('z')} "
        f"({altman.get('zona')}).",
        f"ROIC {buffett.get('roic')} frente a coste de capital {buffett.get('wacc_referencia')}; "
        f"PEG {lynch.get('peg')} ({lynch.get('lectura_peg')}).",
    ]
    if graham.get("margen_seguridad") is not None:
        partes.append(
            f"Margen de seguridad sobre el Número de Graham "
            f"({graham['numero_graham']}): {graham['margen_seguridad']:.1%}.")
    if banderas:
        partes.append("Banderas rojas: " + "; ".join(banderas) + ".")
    partes.append(f"Cobertura de datos {cobertura:.0%} ({status}).")
    return " ".join(partes)


# =========================================================================== #
# Fachadas @tool
# =========================================================================== #
# Todo lo de arriba opera con `Magnitud`. Lo de aquí abajo habla JSON, que es lo
# único que cabe en un `ToolMessage` y lo único que un LLM puede rellenar. La
# conversión ocurre en una sola línea por tool y nunca al revés: ninguna fachada
# recalcula nada.

def _mg(magnitudes: Dict[str, Any]) -> Dict[str, Magnitud]:
    """Rehidrata el mapa de magnitudes que llega serializado desde el estado."""
    return magnitudes_desde_detalle(magnitudes)


@tool("construir_magnitudes_base")
def construir_magnitudes_base(fundamentales: Dict[str, Any],
                              estados_financieros: Dict[str, Any],
                              hechos_sec: Dict[str, Any],
                              metricas_reconciliadas: Dict[str, Any],
                              tecnico: Dict[str, Any]) -> Dict[str, Any]:
    """Reúne en un único mapa las magnitudes que consumen los siete scorers.

    Prefiere los estados financieros auditados sobre los agregados TTM de
    yfinance, que no son trazables ni comparables interanualmente. Devuelve cada
    magnitud con su procedencia y su disponibilidad, nunca un cero por ausencia.

    Es la primera tool que invoca el Analista de Calidad: el resto reciben su
    salida como argumento `magnitudes`.
    """
    return detalle_magnitudes(
        _magnitudes_base(fundamentales, estados_financieros, hechos_sec,
                         metricas_reconciliadas, tecnico))


@tool("calcular_piotroski")
def calcular_piotroski(estados_financieros: Dict[str, Any],
                       hechos_sec: Dict[str, Any]) -> Dict[str, Any]:
    """F-Score de Piotroski (2000): nueve puntos de calidad contable.

    Mide rentabilidad, apalancamiento y eficiencia operativa como VARIACIÓN
    interanual, no como nivel. Por eso exige series de dos ejercicios: con una
    sola foto el F-Score no es calculable, y los puntos se marcan como no
    evaluados en lugar de suspenderlos.

    Devuelve `score` (0-9), `maximo_evaluable`, el detalle de los nueve
    criterios y la lectura (fuerte / neutral / débil).
    """
    return _piotroski(estados_financieros, hechos_sec)


@tool("calcular_altman")
def calcular_altman(magnitudes: Dict[str, Any], estados_financieros: Dict[str, Any],
                    sector: str) -> Dict[str, Any]:
    """Z-Score de solvencia de Altman (1968).

    Usa el Z clásico en sectores manufactureros y la variante Z-doble-prima en
    el resto, que es como Altman la calibró: el Z de 1968 penaliza los modelos
    ligeros en capital a través de la rotación de activos, y aplicarlo a
    software o servicios produce falsos positivos de insolvencia sistemáticos.

    Devuelve `z`, `zona` (SEGURA / GRIS / DISTRESS), la variante empleada y los
    términos por separado para que la cifra sea auditable.
    """
    return _altman(_mg(magnitudes), estados_financieros, sector)


@tool("calcular_graham")
def calcular_graham(magnitudes: Dict[str, Any],
                    fundamentales: Dict[str, Any]) -> Dict[str, Any]:
    """Número de Graham (1949) y criterios defensivos del inversor.

    Calcula el valor intrínseco conservador, el margen de seguridad frente al
    precio, y el cumplimiento de los límites clásicos de P/E, P/VC, ratio
    corriente y deuda.

    Con beneficio por acción negativo devuelve NO_APLICABLE en lugar de un cero:
    la fórmula no está definida ahí, y un cero se leería como ausencia de valor
    intrínseco.
    """
    return _graham(_mg(magnitudes), fundamentales)


@tool("calcular_greenblatt")
def calcular_greenblatt(magnitudes: Dict[str, Any]) -> Dict[str, Any]:
    """Fórmula mágica de Greenblatt (2005): baratura y calidad en dos números.

    Rendimiento del beneficio (EBIT sobre valor de empresa) y rentabilidad del
    capital tangible. Usa valor de empresa y no capitalización precisamente para
    que la deuda no quede fuera de la comparación entre compañías con
    estructuras de capital distintas.
    """
    return _greenblatt(_mg(magnitudes))


@tool("calcular_buffett")
def calcular_buffett(magnitudes: Dict[str, Any],
                     estados_financieros: Dict[str, Any]) -> Dict[str, Any]:
    """Criterios de calidad de negocio al estilo Buffett.

    ROIC contra el coste de capital de referencia (`WACC_REFERENCIA`), margen
    bruto como aproximación al foso competitivo, beneficio del propietario
    (flujo operativo menos inversión de mantenimiento) sobre capitalización, y
    dilución acumulada de accionistas.

    Devuelve además `crea_valor`: si el retorno sobre el capital invertido supera
    o no a lo que ese capital cuesta.
    """
    return _buffett(_mg(magnitudes), estados_financieros)


@tool("calcular_lynch")
def calcular_lynch(magnitudes: Dict[str, Any], sector: str) -> Dict[str, Any]:
    """PEG y taxonomía de crecimiento de Peter Lynch (1989).

    Declara SIEMPRE sobre qué crecimiento se calculó el PEG —beneficio o
    ingresos—, porque no son la misma magnitud y un PEG de 1.2 significa cosas
    distintas según cuál se usara. Clasifica el perfil en rápido, sólido o lento
    y lo cruza con el múltiplo pagado.
    """
    return _lynch(_mg(magnitudes), sector)


@tool("calcular_devengos_sloan")
def calcular_devengos_sloan(magnitudes: Dict[str, Any]) -> Dict[str, Any]:
    """Ratio de devengos de Sloan (1996): cuánto del beneficio no es caja.

    Beneficio neto menos flujo de caja operativo, sobre activos totales. El
    hallazgo de Sloan es que la parte del beneficio que no llega a caja
    revierte: un ratio alto anticipa decepciones aunque la cuenta de resultados
    luzca bien.
    """
    return _devengos(_mg(magnitudes))


@tool("calcular_contexto_sectorial")
def calcular_contexto_sectorial(magnitudes: Dict[str, Any], sector: str) -> Dict[str, Any]:
    """Sitúa cada múltiplo frente a la norma de su sector.

    Un P/E de 30 es caro en utilities y barato en software. Sin este contraste
    los múltiplos absolutos comparan cosas incomparables, que es el error que
    hace parecer cara a toda la tecnología y barata a toda la banca.
    """
    return _contexto_sectorial(_mg(magnitudes), sector)


@tool("calcular_puntuaciones")
def calcular_puntuaciones(magnitudes: Dict[str, Any], piotroski: Dict[str, Any],
                          altman: Dict[str, Any], graham: Dict[str, Any],
                          greenblatt: Dict[str, Any], buffett: Dict[str, Any],
                          lynch: Dict[str, Any], devengos: Dict[str, Any]) -> Dict[str, Any]:
    """Agrega las siete escuelas en cuatro puntuaciones de 0 a 100.

    Calidad, valoración, crecimiento y solvencia. Cada una promedia SOLO sus
    componentes disponibles y publica su propia cobertura: imputar ceros
    convertiría una ausencia de dato en un suspenso, que es el defecto que este
    sistema arrastraba.

    Devuelve `{"puntuaciones": ..., "coberturas": ...}`.
    """
    puntuaciones, coberturas = _puntuaciones(_mg(magnitudes), piotroski, altman,
                                             graham, greenblatt, buffett, lynch, devengos)
    return {"puntuaciones": puntuaciones, "coberturas": coberturas}


@tool("calcular_conviccion")
def calcular_conviccion(puntuaciones: Dict[str, Any], cobertura: float,
                        banderas_rojas: List[str],
                        confianza_datos: float) -> Dict[str, Any]:
    """Convicción fundamental de 0 a 100, ya descontada por lo que no se sabe.

    Media ponderada de las cuatro puntuaciones (`PESOS_CONVICCION`) recortada
    por la cobertura de datos, por la confianza de la reconciliación entre
    proveedores y por las banderas rojas detectadas. El Fund Manager la cruza
    con el momentum para emitir el rating, así que es variable de DECISIÓN.
    """
    return _conviccion(puntuaciones, cobertura, banderas_rojas, confianza_datos)


@tool("detectar_banderas_rojas")
def detectar_banderas_rojas(magnitudes: Dict[str, Any], piotroski: Dict[str, Any],
                            altman: Dict[str, Any], devengos: Dict[str, Any],
                            buffett: Dict[str, Any]) -> List[str]:
    """Condiciones que por sí solas justifican reducir tamaño o no operar.

    Insolvencia corroborada por caja, devengos por encima del umbral de alerta,
    dilución sostenida, F-Score en zona débil, destrucción de valor sobre el
    capital invertido. Devuelve la lista de banderas en texto; la lista vacía es
    un resultado válido y significativo.
    """
    return _banderas_rojas(_mg(magnitudes), piotroski, altman, devengos, buffett)


@tool("clasificar_estilo")
def clasificar_estilo(puntuaciones: Dict[str, Any], magnitudes: Dict[str, Any],
                      lynch: Dict[str, Any], sector: str, cobertura: float,
                      banderas_rojas: List[str],
                      componentes_valoracion: Optional[Dict[str, Any]] = None,
                      altman: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Asigna el estilo de inversión: VALOR, GARP, CRECIMIENTO, CALIDAD_COMPUESTA...

    No es una etiqueta decorativa: elige los múltiplos de ATR y el horizonte del
    stop y del objetivo (`ATR_AJUSTE_POR_ESTILO`) y habilita vetos. ESPECULATIVA
    y TRAMPA_DE_VALOR no pueden superar MANTENER por atractivos que sean sus
    múltiplos.

    Por debajo de `COBERTURA_MINIMA_ESTILO` devuelve DATOS_INSUFICIENTES en vez
    de clasificar con huecos. Devuelve `{"estilo", "etiquetas_secundarias",
    "motivo"}`.
    """
    estilo, secundarias, motivo = _clasificar_estilo(
        puntuaciones, _mg(magnitudes), lynch, sector, cobertura, banderas_rojas,
        componentes_valoracion, altman)
    return {"estilo": estilo, "etiquetas_secundarias": secundarias, "motivo": motivo}


TOOLS_CALIDAD = [
    construir_magnitudes_base,
    calcular_piotroski,
    calcular_altman,
    calcular_graham,
    calcular_greenblatt,
    calcular_buffett,
    calcular_lynch,
    calcular_devengos_sloan,
    calcular_contexto_sectorial,
    calcular_puntuaciones,
    calcular_conviccion,
    detectar_banderas_rojas,
    clasificar_estilo,
]
