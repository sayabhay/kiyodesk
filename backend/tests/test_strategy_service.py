"""Tests for StrategyService and the strategy evaluation route (Task 8)."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup
from app.domain.strategy.services.strategy_service import StrategyService
from fastapi.testclient import TestClient

D = Decimal


# ---------------------------------------------------------------------------
# Shared bar-building helpers (mirrors test_strategy_engine.py)
# ---------------------------------------------------------------------------


def _bar(
    close: str,
    high: str | None = None,
    low: str | None = None,
    ts_offset: int = 0,
) -> Bar:
    c = D(close)
    h = D(high) if high else c
    lo = D(low) if low else c
    return Bar(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=ts_offset),
        open=c,
        high=h,
        low=lo,
        close=c,
        volume=D("1000"),
    )


def _build_bull_scenario() -> list[Bar]:
    """Identical scenario to test_strategy_engine.py — produces one bull setup."""
    bars: list[Bar] = []
    t = 0
    for _ in range(3):
        bars.append(_bar("100", ts_offset=t))
        t += 1
    bars.append(_bar("100", high="100", low="90", ts_offset=t))
    t += 1
    for i in range(5):
        bars.append(_bar(str(100 + i), ts_offset=t))
        t += 1
    bars.append(_bar("105", high="110", low="104", ts_offset=t))
    t += 1
    for _ in range(3):
        bars.append(_bar("105", ts_offset=t))
        t += 1
    bars.append(_bar("111", ts_offset=t))
    t += 1
    for _ in range(2):
        bars.append(_bar("105", ts_offset=t))
        t += 1
    bars.append(_bar("97", high="99", low="95", ts_offset=t))
    t += 1
    return bars


def _bar_to_dict(b: Bar) -> dict[str, object]:
    return {
        "timestamp": b.timestamp.isoformat(),
        "open": str(b.open),
        "high": str(b.high),
        "low": str(b.low),
        "close": str(b.close),
        "volume": str(b.volume),
    }


# ---------------------------------------------------------------------------
# StrategyService unit tests
# ---------------------------------------------------------------------------


class TestStrategyService:
    def test_returns_none_for_empty_bars(self) -> None:
        svc = StrategyService()
        assert svc.evaluate([], [], "BTC") is None

    def test_returns_none_for_single_bar(self) -> None:
        svc = StrategyService()
        assert svc.evaluate([_bar("100")], [], "BTC") is None

    def test_returns_none_when_no_setup(self) -> None:
        """A flat bar series with no structure produces no setup."""
        svc = StrategyService()
        flat = [_bar("100", ts_offset=i) for i in range(20)]
        assert svc.evaluate(flat, [], "BTC") is None

    def test_returns_trade_setup_for_bull_scenario(self) -> None:
        """Service should detect the setup on the last bar of the bull scenario."""
        svc = StrategyService()
        bars = _build_bull_scenario()
        config = StrategyConfig(use_htf_trend=False, swing_len=3)
        result = svc.evaluate(bars, [], "BTC", config=config)
        assert isinstance(result, TradeSetup)
        assert result.direction == "long"

    def test_uses_default_config_when_none_provided(self) -> None:
        """Service must not crash when config=None is passed."""
        svc = StrategyService()
        bars = _build_bull_scenario()
        # Default config has use_htf_trend=True and no htf_bars → fail-open → still evaluates
        result = svc.evaluate(bars, [], "BTC", config=None)
        # May or may not find a setup depending on htf filter; just assert no exception
        assert result is None or isinstance(result, TradeSetup)

    def test_fresh_engine_per_call(self) -> None:
        """Each evaluate() call must produce an independent evaluation (no state leak)."""
        svc = StrategyService()
        bars = _build_bull_scenario()
        config = StrategyConfig(use_htf_trend=False, swing_len=3)
        r1 = svc.evaluate(bars, [], "BTC", config=config)
        r2 = svc.evaluate(bars, [], "BTC", config=config)
        # Both calls must agree — same bars, same result
        assert (r1 is None) == (r2 is None)
        if r1 is not None and r2 is not None:
            assert r1.entry == r2.entry


# ---------------------------------------------------------------------------
# Route integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    from app.main import create_app

    return TestClient(create_app())


class TestStrategyEvaluateRoute:
    def test_route_exists_and_returns_200(self, client: TestClient) -> None:
        payload = {
            "symbol": "BTC",
            "bars": [_bar_to_dict(_bar("100", ts_offset=i)) for i in range(20)],
        }
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 200

    def test_no_setup_returns_null(self, client: TestClient) -> None:
        """Flat bars with no structure → null response (not a 404)."""
        payload = {
            "symbol": "BTC",
            "bars": [_bar_to_dict(_bar("100", ts_offset=i)) for i in range(20)],
        }
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 200
        assert response.json() is None

    def test_bull_scenario_returns_trade_setup(self, client: TestClient) -> None:
        bars = _build_bull_scenario()
        payload = {
            "symbol": "BTC",
            "timeframe": "15m",
            "bars": [_bar_to_dict(b) for b in bars],
            "config": {
                "use_htf_trend": False,
                "swing_len": 3,
            },
        }
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["direction"] == "long"
        assert data["symbol"] == "BTC"
        assert data["strategy"] == "ICT Pure OTE"
        assert data["timeframe"] == "15m"
        assert float(data["entry"]) > 0
        assert float(data["stop_loss"]) < float(data["entry"])
        assert float(data["take_profit"]) > float(data["entry"])
        assert len(data["reasons"]) >= 1

    def test_trade_setup_contains_config_snapshot(self, client: TestClient) -> None:
        bars = _build_bull_scenario()
        payload = {
            "symbol": "BTC",
            "bars": [_bar_to_dict(b) for b in bars],
            "config": {
                "use_htf_trend": False,
                "swing_len": 3,
                "rr_ratio": "3.0",
            },
        }
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data is not None
        assert data["config_snapshot"]["rr_ratio"] == "3.0"
        assert data["config_snapshot"]["swing_len"] == 3

    def test_empty_bars_returns_null(self, client: TestClient) -> None:
        payload = {"symbol": "BTC", "bars": []}
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 200
        assert response.json() is None

    def test_missing_symbol_returns_422(self, client: TestClient) -> None:
        """symbol is required — missing it should return validation error."""
        payload = {"bars": [_bar_to_dict(_bar("100"))]}
        response = client.post("/api/v1/strategy/evaluate", json=payload)
        assert response.status_code == 422

    def test_strategy_route_appears_in_openapi(self, client: TestClient) -> None:
        """The strategy router must be registered and visible in the OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert "/api/v1/strategy/evaluate" in paths
