# ICT Pure OTE Strategy — Reference

## Overview

ICT Pure OTE (Institutional Concepts — Optimal Trade Entry) is a price-action
strategy that identifies high-probability retracement entries within Fibonacci
OTE zones following a Break of Structure.

The canonical implementation is the uploaded kScript file
`ICT-Pure-OTE-Strategy-ks.txt`. The Python port in `app/domain/strategy/ict/`
must replicate its behavior exactly. This document is the human-readable
reference for every rule and parameter.

---

## Parameter Reference

Every parameter maps 1-to-1 to a kScript `input()` declaration.

### Swing & Structure

| Python field | kScript name | Default | Range | Description |
|---|---|---|---|---|
| `swing_len` | `swingLen` | `5` | 2–20 | Pivot lookback/lookahead length. A bar is a confirmed pivot only when it is strictly the highest/lowest bar in a window of `swing_len` bars on each side. |
| `trade_dir` | `tradeDir` | `"Both"` | Both / Long Only / Short Only | Restricts which direction setups are generated. |

### HTF Trend Filter

| Python field | kScript name | Default | Description |
|---|---|---|---|
| `use_htf_trend` | `useHTFTrend` | `True` | When True, the HTF EMA slope must align with the trade direction before a zone is armed. |
| `htf_ema_len` | `emaLen` | `50` | EMA period applied to HTF bars. |
| `ema_slope_lookback` | `emaSlopeLen` | `3` | Number of bars back used for slope comparison: `ema[-1] > ema[-1 - lookback]`. |

### OTE Zone

| Python field | kScript name | Default | Description |
|---|---|---|---|
| `ote_start` | `oteStart` | `0.618` | Shallow end of the OTE zone (61.8% Fibonacci retracement). |
| `ote_end` | `oteEnd` | `0.79` | Deep end of the OTE zone (79% Fibonacci retracement). |
| `require_close_back` | `requireCloseBack` | `False` | When True, the confirming bar's close must be inside the zone (not just the wick). |

### Risk Management

| Python field | kScript name | Default | Description |
|---|---|---|---|
| `sl_buffer_pct` | `slBufferPerc` | `0.05` | Stop loss buffer as a percentage beyond the structural level. `sl = leg_low * (1 - buffer/100)` for bull; `sl = leg_high * (1 + buffer/100)` for bear. |
| `tp_mode` | `tpMode` | `"Fixed RR"` | Take profit mode: `"Fixed RR"` or `"Fib Extension"`. |
| `rr_ratio` | `rrRatio` | `2.0` | Risk:Reward multiplier for Fixed RR mode. |
| `fib_ext` | `fibExt` | `1.0` | Fibonacci extension multiplier for Fib Extension mode. |
| `invalidate_on_close` | `invalidateOnClose` | `True` | When True, the zone is cancelled if price closes beyond the stop loss before the tap. |

---

## Strategy Rules

### 1. Swing Pivot Detection

```
module: ict/swing.py
function: detect_pivots(bars, swing_len) → (swing_high | None, swing_low | None)
```

A bar at index `i` is a **confirmed pivot high** if its `high` is strictly
greater than every other bar's `high` in the window `[i - swing_len .. i + swing_len]`.

A bar at index `i` is a **confirmed pivot low** if its `low` is strictly
less than every other bar's `low` in the same window.

**Key rules:**
- Ties (two bars sharing the highest high) produce no pivot.
- A bar cannot be confirmed until `swing_len` bars to its right have closed.
- The most recently confirmed pivot is returned (scanning newest-to-oldest).
- Returns `(None, None)` when fewer than `2 * swing_len + 1` bars are available.

kScript equivalent: `pivothigh(leftbars=swingLen, rightbars=swingLen, priceIndex=2)`

---

### 2. Break of Structure (BOS)

```
module: ict/bos.py
function: detect_bos(bars, swing_high, swing_low) → (bos_up, bos_down)
```

**Bullish BOS** fires when:
```
bars[-1].close > swing_high  AND  bars[-2].close <= swing_high
```

**Bearish BOS** fires when:
```
bars[-1].close < swing_low   AND  bars[-2].close >= swing_low
```

This is a manual close-crossover check, not a high/low breakout.
The prior bar must be *at or below* (bull) / *at or above* (bear) the level.
Requires at least 2 bars.

kScript equivalent:
```
var bosUp   = !isna(swingHigh) && bars.close > swingHigh && bars.close[1] <= swingHigh
var bosDown = !isna(swingLow)  && bars.close < swingLow  && bars.close[1] >= swingLow
```

---

### 3. HTF EMA Trend Filter

```
module: ict/htf_trend.py
functions: compute_ema(bars, period) → list[Decimal]
           evaluate_trend(htf_bars, config) → (htf_bullish, htf_bearish)
```

**EMA formula:**
- Multiplier: `k = 2 / (period + 1)`
- Seed: SMA of first `period` closes
- Subsequent: `ema[i] = close[i] * k + ema[i-1] * (1 - k)`

**Slope check:**
- `htf_bullish = ema[-1] > ema[-1 - slope_lookback]`
- `htf_bearish = ema[-1] < ema[-1 - slope_lookback]`

**Bypass rules (both return `True`):**
- `use_htf_trend = False`
- Fewer than `htf_ema_len + ema_slope_lookback` bars available (fail-open)

A flat EMA (slope = 0) produces `htf_bullish = False, htf_bearish = False`,
blocking both directions. This is correct kScript behavior.

kScript equivalent:
```
var htfBullish = !useHTFTrend || h4ema > h4ema[emaSlopeLen]
var htfBearish = !useHTFTrend || h4ema < h4ema[emaSlopeLen]
```

---

### 4. OTE Zone State Machine

```
module: ict/ote.py
dataclass: ZoneState
functions: compute_bull_zone, compute_bear_zone, update_zone, check_tap
```

#### Zone Arming

On **bullish BOS** (when `long_enabled` and `htf_bullish`):
```
ote_top    = leg_high - (leg_high - leg_low) * ote_start
ote_bottom = leg_high - (leg_high - leg_low) * ote_end
sl         = leg_low  * (1 - sl_buffer_pct / 100)
waiting_bull = True
waiting_bear = False   ← opposing zone always cancelled
```

On **bearish BOS** (when `short_enabled` and `htf_bearish`):
```
ote_bottom = leg_low + (leg_high - leg_low) * ote_start
ote_top    = leg_low + (leg_high - leg_low) * ote_end
sl         = leg_high * (1 + sl_buffer_pct / 100)
waiting_bear = True
waiting_bull = False
```

The leg is always measured from the most recently confirmed swing low to
swing high (bull) or swing high to swing low (bear) at the time of BOS.

#### Zone Invalidation

When `invalidate_on_close = True`:
- Bull zone: if `close < bull_sl` → `waiting_bull = False`
- Bear zone: if `close > bear_sl` → `waiting_bear = False`

Invalidation runs on the **same bar** as arming. A BOS bar that also closes
beyond the SL immediately disarms the zone.

#### Entry Tap

**Bullish tap:**
```
tap     = waiting_bull AND bar.low <= ote_top AND bar.high >= ote_bottom
confirm = tap AND (not require_close_back OR bar.close >= ote_bottom)
```

**Bearish tap:**
```
tap     = waiting_bear AND bar.high >= ote_bottom AND bar.low <= ote_top
confirm = tap AND (not require_close_back OR bar.close <= ote_top)
```

After a confirmed tap the zone is disarmed (`waiting_bull/bear = False`).

---

### 5. Risk Management

```
module: ict/risk.py
functions: calculate_bull_risk, calculate_bear_risk → RiskLevels | None
```

#### Entry Guard

Before computing TP, the risk guard must pass:
- Bull: `entry - sl > 0`  (kScript: `if (bars.close - bullSL > 0)`)
- Bear: `sl - entry > 0`  (kScript: `if (bearSL - bars.close > 0)`)

Returns `None` if the guard fails. The engine skips the setup.

#### Take Profit Modes

**Fixed RR:**
```
bull: tp = entry + (entry - sl) * rr_ratio
bear: tp = entry - (sl - entry) * rr_ratio
```

**Fib Extension:**
```
bull: tp = leg_high + (leg_high - leg_low) * fib_ext
bear: tp = leg_low  - (leg_high - leg_low) * fib_ext
```

#### Risk/Reward

Derived R:R stored on `RiskLevels.risk_reward`:
```
rr = abs(tp - entry) / abs(entry - sl)
```

---

## Known Behavioral Notes

- **Invalidation on arming bar**: The kScript evaluates arming and invalidation
  on the same bar. If BOS fires and the same bar closes beyond the SL,
  the zone is immediately invalidated. The Python engine replicates this.

- **Single active zone**: Only one direction can be `waiting` at a time.
  A new BOS in either direction cancels the opposing zone unconditionally.

- **No re-entry on same zone**: After a tap (confirmed or not), the zone is
  disarmed. A new BOS is required to arm a new zone.

- **HTF bars are separate**: HTF bars are supplied independently of LTF bars.
  The engine does not resample LTF bars to produce HTF bars. The caller is
  responsible for supplying pre-resampled HTF data.

---

## TODOs / Clarification Requests

- **FVG/OB identification**: The kScript does not explicitly detect Fair Value
  Gaps or Order Blocks. The OTE zone is Fibonacci-only. If FVG/OB confluence
  is desired in a future version, this must be explicitly approved.

- **Volume confirmation**: The kScript has no volume-based filters. Any
  volume-based confidence scoring belongs in the Confidence Engine (v0.6),
  not here.

- **Multi-timeframe OTE nesting**: The kScript evaluates a single LTF.
  Nested HTF OTE zones (e.g. daily OTE within 4H OTE) are not in scope for
  v0.5 and require explicit design approval before implementation.
