import pytest
from src.data.fetcher import DataFetcher

def test_fetch_all_structure():
    fetcher = DataFetcher()
    data = fetcher.fetch_all("AAPL")
    
    assert data["status"] == "SUCCESS"
    assert data["ticker"] == "AAPL"
    assert "fundamentals" in data
    assert "technical" in data
    
    tech = data["technical"]
    assert "rsi" in tech
    assert "macd" in tech
    assert "atr" in tech
    assert "bb_upper" in tech
    assert "bb_lower" in tech
    assert 0 <= tech["rsi"] <= 100
