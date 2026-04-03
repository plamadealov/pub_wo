import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_analyze_mock_weights() -> None:
    body = {
        "positions": [
            {"ticker": "SBER", "weight": 40},
            {"ticker": "GAZP", "weight": 60},
        ],
        "trading_days": 500,
        "alpha": 0.05,
        "market_index": "IMOEX",
        "use_mock": True,
    }
    r = client.post("/api/portfolio/analyze", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["mode"] == "mock"
    assert data["portfolio_beta"] > 0
    assert len(data["per_ticker"]) == 2
    assert abs(sum(p["weight"] for p in data["per_ticker"]) - 1.0) < 1e-5
    assert data["var_1d"] > 0 and data["es_1d"] >= data["var_1d"]
    assert data["confidence_level"] == pytest.approx(0.95)
    assert data["warnings"]


def test_analyze_mock_notionals() -> None:
    body = {
        "positions": [
            {"ticker": "sber", "notional": 100_000},
            {"ticker": "LKOH", "notional": 300_000},
        ],
        "use_mock": True,
    }
    r = client.post("/api/portfolio/analyze", json=body)
    assert r.status_code == 200
    w = [p["weight"] for p in r.json()["per_ticker"]]
    assert w[0] == pytest.approx(0.25)
    assert w[1] == pytest.approx(0.75)


def test_analyze_rejects_mixed_weight_notional() -> None:
    body = {
        "positions": [
            {"ticker": "SBER", "weight": 0.5},
            {"ticker": "GAZP", "notional": 1000},
        ],
    }
    r = client.post("/api/portfolio/analyze", json=body)
    assert r.status_code == 422


def test_resolve_instrument() -> None:
    try:
        r = client.get("/api/instruments/resolve", params={"ticker": "sber"})
    except Exception:
        pytest.skip("MOEX ISS / сеть недоступны в этой среде")
    if r.status_code != 200:
        pytest.skip("MOEX ISS недоступен в этой среде")
    d = r.json()
    assert d["canonical_ticker"] == "SBER"
    assert d["source"] == "moex"
