"""Strategy Engine evaluation endpoint.

POST /api/v1/strategy/evaluate

Accepts a bar series (LTF + optional HTF) and optional StrategyConfig,
returns a TradeSetup domain object or null when no setup is detected.

This route is a stateless evaluation interface — it does not persist anything.
The Trade Journal (POST /api/v1/trades) is the persistence layer.
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.strategy.interfaces.bar import Bar
from app.domain.strategy.models.config import StrategyConfig
from app.domain.strategy.models.trade_setup import TradeSetup
from app.domain.strategy.services.strategy_service import StrategyService

router = APIRouter(prefix="/strategy", tags=["strategy"])


class BarInput(BaseModel):
    """A single OHLCV bar supplied in the request body."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal


class StrategyEvaluateRequest(BaseModel):
    """Request body for the strategy evaluation endpoint."""

    symbol: str
    timeframe: str | None = None
    bars: list[BarInput]
    htf_bars: list[BarInput] = []
    config: StrategyConfig | None = None


def _to_bar(b: BarInput) -> Bar:
    return Bar(
        timestamp=b.timestamp,
        open=b.open,
        high=b.high,
        low=b.low,
        close=b.close,
        volume=b.volume,
    )


@router.post("/evaluate", response_model=TradeSetup | None)
def evaluate_strategy(request: StrategyEvaluateRequest) -> TradeSetup | None:
    """Evaluate a bar series against the ICT Pure OTE strategy.

    Returns a TradeSetup when a valid setup is detected on the final bar,
    or null when no setup is present.  Both outcomes are HTTP 200.

    The absence of a setup is a valid and expected result — it means the
    strategy found no actionable setup on the provided bars.
    """
    bars = [_to_bar(b) for b in request.bars]
    htf_bars = [_to_bar(b) for b in request.htf_bars]

    return StrategyService().evaluate(
        bars=bars,
        htf_bars=htf_bars,
        symbol=request.symbol,
        config=request.config,
        timeframe=request.timeframe,
    )
