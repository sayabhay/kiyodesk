"""Pure P&L aggregation functions for closed trade analytics."""

from decimal import Decimal

from app.models.trade import Trade
from app.schemas.analytics import AnalyticsResponse

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")
_SCALE = Decimal("0.000001")


def compute_analytics(trades: list[Trade]) -> AnalyticsResponse:
    """Derive aggregate performance metrics from a list of trades.

    Only trades with status='closed' and a non-null profit_loss are included
    in the closed-trade calculations. Open trades are counted separately.
    """

    total = len(trades)
    closed = [t for t in trades if t.status == "closed" and t.profit_loss is not None]
    open_count = total - len(closed)

    if not closed:
        return AnalyticsResponse(
            total_trades=total,
            open_trades=open_count,
            closed_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate=None,
            profit_factor=None,
            expectancy=None,
            total_profit_loss=None,
            average_win=None,
            average_loss=None,
            largest_win=None,
            largest_loss=None,
        )

    pnls = [Decimal(str(t.profit_loss)) for t in closed]
    winners = [p for p in pnls if p > _ZERO]
    losers = [p for p in pnls if p < _ZERO]
    breakevens = [p for p in pnls if p == _ZERO]

    gross_profit = sum(winners, _ZERO)
    gross_loss = sum(losers, _ZERO).copy_abs()
    total_pnl = sum(pnls, _ZERO)

    n_closed = len(closed)

    win_rate = (_HUNDRED * len(winners) / n_closed).quantize(_SCALE)

    profit_factor: Decimal | None
    if gross_loss == _ZERO:
        # All trades profitable — profit factor is undefined (infinite)
        profit_factor = None
    else:
        profit_factor = (gross_profit / gross_loss).quantize(_SCALE)

    expectancy = (total_pnl / n_closed).quantize(_SCALE)

    average_win = (gross_profit / len(winners)).quantize(_SCALE) if winners else None
    average_loss = (sum(losers, _ZERO) / len(losers)).quantize(_SCALE) if losers else None
    largest_win = max(winners) if winners else None
    largest_loss = min(losers) if losers else None

    return AnalyticsResponse(
        total_trades=total,
        open_trades=open_count,
        closed_trades=n_closed,
        winning_trades=len(winners),
        losing_trades=len(losers),
        breakeven_trades=len(breakevens),
        win_rate=win_rate,
        profit_factor=profit_factor,
        expectancy=expectancy,
        total_profit_loss=total_pnl,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=largest_win,
        largest_loss=largest_loss,
    )
