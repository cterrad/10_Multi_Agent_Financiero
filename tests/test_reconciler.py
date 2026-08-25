import pytest
from src.data.reconciler import DataReconciler

def test_reconciler_single_vendor():
    """
    Con una sola fuente la confianza tiene que BAJAR.

    Este test fijaba antes `confidence_score == 1.0`, que era precisamente el
    defecto: el estado decía SINGLE_VENDOR_FALLBACK y la puntuación decía
    confianza total. Como el gatekeeper solo avisaba por debajo de 0.5, ese
    aviso era inalcanzable. Menos información tiene que valer menos confianza.
    """
    reconciler = DataReconciler()
    yf_data = {"fundamentals": {"revenue_growth": 0.10, "net_margin": 0.20,
                                "debt_to_equity": 0.5, "roe": 0.25}}
    sec_data = {"status": "NOT_FOUND"}
    fh_data = {"status": "NO_API_KEY"}

    rec = reconciler.reconcile("TEST", yf_data, sec_data, fh_data)
    assert rec["status"] == "SINGLE_VENDOR_FALLBACK"
    assert rec["confidence_score"] < 1.0
    assert rec["confidence_score"] >= 0.4
    assert rec["reconciled_metrics"]["net_margin"] == 0.20
    assert [f["fuente"] for f in rec["sources_failed"]] == ["SEC EDGAR", "Finnhub"]


def test_reconciler_penaliza_campos_ausentes():
    """
    Un campo que falta rebaja la confianza y NO se convierte en cero.

    Es la propiedad que separa «no lo sé» de «vale cero»: antes ambos
    producían `0.0` y el gatekeeper rechazaba la empresa por «margen del 0.0%
    por debajo del umbral», afirmando un hecho contable inexistente.
    """
    reconciler = DataReconciler()
    completo = {"fundamentals": {"revenue_growth": 0.10, "net_margin": 0.20,
                                 "debt_to_equity": 0.5, "roe": 0.25, "pe_ratio": 18.0}}
    incompleto = {"fundamentals": {"revenue_growth": 0.10}}
    sec_data = {"status": "NOT_FOUND"}
    fh_data = {"status": "NO_API_KEY"}

    rec_completo = reconciler.reconcile("A", completo, sec_data, fh_data)
    rec_incompleto = reconciler.reconcile("B", incompleto, sec_data, fh_data)

    assert rec_incompleto["confidence_score"] < rec_completo["confidence_score"]
    assert rec_incompleto["reconciled_metrics"]["net_margin"] is None
    assert "net_margin" in rec_incompleto["cobertura"]["campos_ausentes"]


def test_reconciler_completa_huecos_desde_la_sec():
    """
    Reconciliar es COMPLETAR, no solo avisar.

    La versión anterior copiaba las cinco magnitudes de yfinance sin excepción
    y usaba la SEC únicamente para encender una luz de aviso. Si yfinance no
    trae el margen pero la SEC sí, el margen debe salir de la SEC.
    """
    reconciler = DataReconciler()
    yf_data = {"fundamentals": {"revenue_growth": 0.10, "debt_to_equity": 0.5}}
    sec_data = {"status": "SUCCESS", "revenues": 1000.0, "net_income": 150.0,
                "stockholders_equity": 500.0, "series": {}}
    fh_data = {"status": "NO_API_KEY"}

    rec = reconciler.reconcile("TEST", yf_data, sec_data, fh_data)
    assert rec["reconciled_metrics"]["net_margin"] == pytest.approx(0.15)
    assert "SEC EDGAR" in rec["procedencia"]["net_margin"]["fuente_elegida"]

def test_reconciler_with_discrepancy():
    reconciler = DataReconciler()
    yf_data = {"fundamentals": {"revenue_growth": 0.10, "net_margin": 0.20, "debt_to_equity": 0.5, "roe": 0.25}}
    sec_data = {"status": "SUCCESS", "revenues": 100000, "net_income": 5000} # Margin 5% vs YF 20%
    fh_data = {"status": "NO_API_KEY"}

    rec = reconciler.reconcile("TEST", yf_data, sec_data, fh_data)
    assert rec["status"] == "RECONCILED_WITH_DISCREPANCIES"
    assert rec["confidence_score"] < 1.0
    assert len(rec["discrepancies"]) > 0
