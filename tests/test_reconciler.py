import pytest
from src.data.reconciler import DataReconciler

def test_reconciler_single_vendor():
    reconciler = DataReconciler()
    yf_data = {"fundamentals": {"revenue_growth": 0.10, "net_margin": 0.20, "debt_to_equity": 0.5, "roe": 0.25}}
    sec_data = {"status": "NOT_FOUND"}
    fh_data = {"status": "NO_API_KEY"}

    rec = reconciler.reconcile("TEST", yf_data, sec_data, fh_data)
    assert rec["status"] == "SINGLE_VENDOR_FALLBACK"
    assert rec["confidence_score"] == 1.0
    assert rec["reconciled_metrics"]["net_margin"] == 0.20

def test_reconciler_with_discrepancy():
    reconciler = DataReconciler()
    yf_data = {"fundamentals": {"revenue_growth": 0.10, "net_margin": 0.20, "debt_to_equity": 0.5, "roe": 0.25}}
    sec_data = {"status": "SUCCESS", "revenues": 100000, "net_income": 5000} # Margin 5% vs YF 20%
    fh_data = {"status": "NO_API_KEY"}

    rec = reconciler.reconcile("TEST", yf_data, sec_data, fh_data)
    assert rec["status"] == "RECONCILED_WITH_DISCREPANCIES"
    assert rec["confidence_score"] < 1.0
    assert len(rec["discrepancies"]) > 0
