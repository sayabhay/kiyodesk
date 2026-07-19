"""StrategyConfig — all configurable parameters from the ICT Pure OTE kScript.

Every field maps 1-to-1 to a kScript input() declaration.
Defaults match the kScript defaults exactly.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class StrategyConfig(BaseModel):
    """Configuration for the ICT Pure OTE strategy.

    kScript input() mapping
    -----------------------
    swing_len           ← Swing Pivot Length         (default 5)
    trade_dir           ← Trade Direction             (default "Both")
    use_htf_trend       ← Use HTF EMA Trend Filter   (default true)
    htf_ema_len         ← HTF EMA Length              (default 50)
    ema_slope_lookback  ← EMA Slope Lookback          (default 3)
    ote_start           ← OTE Zone Start              (default 0.618)
    ote_end             ← OTE Zone End                (default 0.79)
    require_close_back  ← Require Close Back Inside   (default false)
    sl_buffer_pct       ← SL Buffer Percent           (default 0.05)
    tp_mode             ← TP Mode                     (default "Fixed RR")
    rr_ratio            ← Risk Reward Ratio           (default 2.0)
    fib_ext             ← Fib Extension               (default 1.0)
    invalidate_on_close ← Invalidate On Close         (default true)
    """

    # --- Swing & Structure ---
    swing_len: int = Field(default=5, ge=2, le=20)
    trade_dir: Literal["Both", "Long Only", "Short Only"] = "Both"

    # --- HTF Trend Filter ---
    use_htf_trend: bool = True
    htf_ema_len: int = Field(default=50, ge=5, le=300)
    ema_slope_lookback: int = Field(default=3, ge=1, le=20)

    # --- OTE Zone ---
    ote_start: Decimal = Field(default=Decimal("0.618"))
    ote_end: Decimal = Field(default=Decimal("0.79"))
    require_close_back: bool = False

    # --- Risk Management ---
    sl_buffer_pct: Decimal = Field(default=Decimal("0.05"))
    tp_mode: Literal["Fixed RR", "Fib Extension"] = "Fixed RR"
    rr_ratio: Decimal = Field(default=Decimal("2.0"))
    fib_ext: Decimal = Field(default=Decimal("1.0"))
    invalidate_on_close: bool = True

    model_config = {"frozen": True}
