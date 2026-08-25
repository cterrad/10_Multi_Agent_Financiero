"""
Integridad de datos: la ausencia de un dato NO puede confundirse con un cero.

Es el defecto más grave que tenía el sistema y el que más lejos llegaba: se
originaba en `info.get("revenueGrowth", 0.0)` y terminaba en un informe que
declaraba «inactividad operativa absoluta» sobre una empresa de la que
simplemente no había datos.

Offline y determinista: no toca la red ni el LLM.
"""

import pytest

from src.agents.fundamental import FundamentalAnalystAgent
from src.config import MAX_DEBT_TO_EQUITY, GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR
from src.data.magnitudes import (
    Cobertura,
    division,
    magnitud,
    primera_disponible,
    suma,
)
from src.data.reconciler import DataReconciler


# --------------------------------------------------------------------------- #
# 1. La primitiva
# --------------------------------------------------------------------------- #
def test_magnitud_distingue_ausencia_de_cero():
    ausente = magnitud(None, "yfinance")
    cero = magnitud(0.0, "yfinance")

    assert ausente.disponible is False
    assert cero.disponible is True
    assert ausente.texto() == "n/d"
    assert cero.texto(1) == "0.0"


@pytest.mark.parametrize("basura", [None, "", "no disponible", float("nan"), float("inf")])
def test_magnitud_sanea_valores_no_numericos(basura):
    assert magnitud(basura, "x").disponible is False


def test_division_por_cero_no_produce_infinito():
    """
    Un ratio infinito recorriendo un scorer produce clasificaciones absurdas.
    Es preferible propagar la indisponibilidad.
    """
    r = division(magnitud(5.0), magnitud(0.0))
    assert r.disponible is False
    assert "denominador nulo" in (r.nota or "")


def test_suma_exige_todos_los_sumandos_por_defecto():
    """
    Deuda corriente + no corriente: si falta un sumando el total es
    desconocido, no la suma de lo que había.
    """
    parcial = suma(magnitud(100.0), magnitud(None))
    assert parcial.disponible is False

    # Con `exigir_todas=False` se suma lo disponible: solo admisible cuando la
    # ausencia significa de verdad cero (un concepto XBRL que no aplica).
    laxa = suma(magnitud(100.0), magnitud(None), exigir_todas=False)
    assert laxa.valor == 100.0


def test_primera_disponible_respeta_la_jerarquia_de_fuentes():
    sec = magnitud(0.15, "SEC EDGAR (Oficial)")
    yf = magnitud(0.18, "yfinance")
    assert primera_disponible(magnitud(None, "x"), sec, yf).fuente == "SEC EDGAR (Oficial)"


def test_cobertura_mide_lo_que_falta():
    c = Cobertura()
    c.registrar("a", magnitud(1.0))
    c.registrar("b", magnitud(None))
    assert c.ratio == 0.5
    assert c.a_dict()["campos_ausentes"] == ["b"]


# --------------------------------------------------------------------------- #
# 2. El gatekeeper: veredicto de tres vías
# --------------------------------------------------------------------------- #
def _estado(metricas, sector="Technology", industria="Software", confianza=0.9):
    return {
        "ticker": "TEST", "sector": sector, "industry": industria,
        "reconciliation_data": {
            "reconciled_metrics": metricas, "confidence_score": confianza,
            "discrepancies": [], "procedencia": {},
        },
    }


def test_sin_datos_no_es_lo_mismo_que_ceros_reales():
    """
    EL test central de este módulo.

    Antes, una empresa sin cobertura de datos y otra realmente sin ingresos
    producían el MISMO veredicto y los MISMOS motivos. El informe del
    2026-08-21 lo mostraba: «Margen Neto (0.0%) por debajo del umbral mínimo»
    se imprimía en los dos casos, afirmando un hecho contable donde solo había
    un vacío de información.
    """
    agente = FundamentalAnalystAgent()

    sin_datos = agente.analyze(_estado(
        {"revenue_growth": None, "net_margin": None, "debt_to_equity": None,
         "roe": None, "pe_ratio": None}))
    ceros_reales = agente.analyze(_estado(
        {"revenue_growth": 0.0, "net_margin": 0.0, "debt_to_equity": 0.0,
         "roe": 0.0, "pe_ratio": 0.0}))

    assert sin_datos["status"] == "DATOS_INSUFICIENTES"
    assert sin_datos["evaluable"] is False
    assert ceros_reales["status"] == "RECHAZADO"
    assert ceros_reales["evaluable"] is True

    # Y los motivos tienen que ser distinguibles.
    assert sin_datos["reasons"] != ceros_reales["reasons"]
    assert any("magnitudes obligatorias" in m for m in sin_datos["reasons"])


def test_confianza_baja_impide_emitir_veredicto():
    agente = FundamentalAnalystAgent()
    r = agente.analyze(_estado(
        {"revenue_growth": 0.30, "net_margin": 0.25, "debt_to_equity": 0.5,
         "roe": 0.30, "pe_ratio": 20.0}, confianza=0.45))
    assert r["status"] == "DATOS_INSUFICIENTES"
    assert any("confianza" in m for m in r["reasons"])


def test_umbral_de_deuda_se_ajusta_al_sector():
    """
    Aplicar el mismo límite de deuda a un banco que a una empresa de software
    es un error de categoría: en servicios financieros el apalancamiento alto
    es la estructura normal del negocio.
    """
    agente = FundamentalAnalystAgent()
    metricas = {"revenue_growth": 0.10, "net_margin": 0.20,
                "debt_to_equity": 6.0, "roe": 0.15, "pe_ratio": 12.0}

    software = agente.analyze(_estado(metricas, sector="Technology"))
    banco = agente.analyze(_estado(metricas, sector="Financial Services"))

    assert software["passed_gatekeeper"] is False
    assert banco["passed_gatekeeper"] is True
    assert banco["umbral_deuda_aplicado"] == GATEKEEPER_DEUDA_MAXIMA_POR_SECTOR["Financial Services"]
    assert software["umbral_deuda_aplicado"] == MAX_DEBT_TO_EQUITY
    assert any("estructural" in a for a in banco["avisos"])


def test_industria_sin_margen_queda_exenta_del_filtro_de_rentabilidad():
    """
    Exigir margen positivo a una biotecnológica en fase clínica descarta por
    definición el modelo de negocio. Se sigue filtrando, pero por solvencia.
    """
    agente = FundamentalAnalystAgent()
    r = agente.analyze(_estado(
        {"revenue_growth": 0.40, "net_margin": -0.80, "debt_to_equity": 0.2,
         "roe": -0.50, "pe_ratio": None},
        sector="Healthcare", industria="Biotechnology"))
    assert r["passed_gatekeeper"] is True
    criterio_margen = next(c for c in r["criterios"] if c["criterio"] == "Margen neto")
    assert criterio_margen["exento"] is True


# --------------------------------------------------------------------------- #
# 3. Unidades de deuda/patrimonio
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bruto_pct,esperado", [
    (8.0, 0.08),       # empresa casi sin deuda: antes se leía como 8.0x y se rechazaba
    (9.9, 0.099),
    (18.86, 0.1886),
    (212.5, 2.125),
    (751.25, 7.5125),
])
def test_deuda_patrimonio_se_convierte_siempre_desde_porcentaje(bruto_pct, esperado):
    """
    yfinance publica `debtToEquity` SIEMPRE en porcentaje.

    La regla anterior `if valor > 10: valor /= 100` intentaba adivinar la
    unidad y fallaba justo en las empresas sanas: una compañía con un 8% de
    deuda sobre patrimonio se leía como 8.0x y el gatekeeper la rechazaba por
    exceso de apalancamiento.
    """
    from src.data.fetcher import DataFetcher

    fundamentals, _ = DataFetcher()._extraer_fundamentales({"debtToEquity": bruto_pct})
    assert fundamentals["debt_to_equity"] == pytest.approx(esperado)
    assert fundamentals["debt_to_equity_bruto_pct"] == pytest.approx(bruto_pct)


def test_pe_declara_de_donde_sale():
    """Mezclar trailing y forward sin dejar rastro impide comparar informes."""
    from src.data.fetcher import DataFetcher

    f = DataFetcher()
    con_trailing, _ = f._extraer_fundamentales({"trailingPE": 20.0, "forwardPE": 15.0})
    solo_forward, _ = f._extraer_fundamentales({"forwardPE": 15.0})
    ninguno, ausentes = f._extraer_fundamentales({})

    assert (con_trailing["pe_ratio"], con_trailing["pe_origen"]) == (20.0, "trailingPE")
    assert (solo_forward["pe_ratio"], solo_forward["pe_origen"]) == (15.0, "forwardPE")
    assert ninguno["pe_ratio"] is None
    assert "pe_ratio" in ausentes


def test_campos_ausentes_no_se_rellenan_con_cero():
    from src.data.fetcher import DataFetcher

    fundamentals, ausentes = DataFetcher()._extraer_fundamentales({})
    assert fundamentals["revenue_growth"] is None
    assert fundamentals["net_margin"] is None
    assert "revenue_growth" in ausentes and "net_margin" in ausentes


# --------------------------------------------------------------------------- #
# 4. Reconciliación
# --------------------------------------------------------------------------- #
def test_la_confianza_baja_cuando_faltan_fuentes():
    rec = DataReconciler()
    completo = {"fundamentals": {"revenue_growth": 0.1, "net_margin": 0.2,
                                 "debt_to_equity": 0.5, "roe": 0.25, "pe_ratio": 18.0}}
    con_sec = rec.reconcile("A", completo,
                            {"status": "SUCCESS", "revenues": 1000.0, "net_income": 200.0,
                             "stockholders_equity": 800.0, "series": {}},
                            {"status": "NO_API_KEY"})
    sin_nada = rec.reconcile("B", completo, {"status": "ERROR"}, {"status": "NO_API_KEY"})

    assert sin_nada["confidence_score"] < con_sec["confidence_score"]


def test_la_discrepancia_se_mide_de_forma_continua():
    """
    La versión anterior aplicaba la misma penalización a una diferencia del 16%
    que a una del 300%.
    """
    rec = DataReconciler()
    yf = {"fundamentals": {"revenue_growth": 0.1, "net_margin": 0.20,
                           "debt_to_equity": 0.5, "roe": 0.25, "pe_ratio": 18.0}}

    leve = rec.reconcile("A", yf, {"status": "SUCCESS", "revenues": 1000.0,
                                   "net_income": 160.0, "series": {}}, {"status": "X"})
    brutal = rec.reconcile("B", yf, {"status": "SUCCESS", "revenues": 1000.0,
                                     "net_income": -400.0, "series": {}}, {"status": "X"})

    assert brutal["confidence_score"] < leve["confidence_score"]
    assert brutal["discrepancies"][0]["dispersion_relativa"] > \
        leve["discrepancies"][0]["dispersion_relativa"]


def test_la_confianza_nunca_baja_del_suelo():
    rec = DataReconciler()
    peor = rec.reconcile("Z", {"fundamentals": {}}, {"status": "ERROR"}, {"status": "ERROR"})
    assert peor["confidence_score"] >= 0.4
