import pytest
from src.graph.workflow import run_stock_analysis

def test_workflow_execution():
    # Probar con un ticker real como AAPL
    result = run_stock_analysis("AAPL")
    
    assert result["workflow_status"] == "COMPLETED"
    assert "fundamental_report" in result
    assert "final_decision" in result
    
    final = result["final_decision"]
    valid_ratings = ["COMPRA FUERTE", "COMPRA", "MANTENER", "VENTA", "VENTA FUERTE"]
    assert final["rating"] in valid_ratings
    assert "position_size_pct" in final
