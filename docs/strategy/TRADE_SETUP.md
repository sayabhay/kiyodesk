# TradeSetup — Domain Object Reference

## What It Is

`TradeSetup` is the structured output of the Strategy Engine. It represents
a detected trading opportunity — not a trade order, not a database record,
not a buy/sell signal.

```
Strategy Engine → TradeSetup → { Dashboard, Trade Journal, Confidence Engine, AI Assistant }
```

`TradeSetup` is defined in `app/domain/strategy/models/trade_setup.py` as a
Pydantic `BaseModel`. It is serializable to JSON and can travel across any
application layer.

---

## What It Is Not

- **Not a trade order.** `TradeSetup` does not instruct any system to open
  a position. It is informational.
- **Not a database model.** It is never persisted directly. When a trader
  decides to act on a setup, they record it via `POST /api/v1/trades`, which
  creates a `Trade` journal entry.
- **Not a guarantee.** A `TradeSetup` means the strategy detected a structural
  condition. Whether to act is a human decision (for now).

---

## Field Reference

| Field | Type | Description |
|---|---|---|
| `symbol` | `str` | Uppercase ticker symbol (e.g. `"BTC"`). |
| `direction` | `"long" \| "short"` | Trade direction as determined by BOS. |
| `entry` | `Decimal` | Suggested entry price — the `close` of the confirming bar. |
| `stop_loss` | `Decimal` | Calculated stop loss. Bull: below `leg_low`. Bear: above `leg_high`. |
| `take_profit` | `Decimal` | Calculated take profit (Fixed RR or Fib Extension). |
| `risk_reward` | `Decimal` | Derived R:R = `abs(tp - entry) / abs(entry - sl)`. |
| `timeframe` | `str \| None` | Optional timeframe label supplied by the caller (e.g. `"15m"`). |
| `strategy` | `str` | Always `"ICT Pure OTE"` for this engine. |
| `reasons` | `list[str]` | Human-readable confluence factors that triggered this setup. |
| `warnings` | `list[str]` | Non-fatal cautions about relaxed configuration settings. |
| `swing_high` | `Decimal \| None` | The leg high used to compute the OTE zone. |
| `swing_low` | `Decimal \| None` | The leg low used to compute the OTE zone. |
| `ote_top` | `Decimal` | Upper boundary of the OTE zone (shallower retracement). |
| `ote_bottom` | `Decimal` | Lower boundary of the OTE zone (deeper retracement). |
| `leg_low` | `Decimal` | Low of the measured move leg. |
| `leg_high` | `Decimal` | High of the measured move leg. |
| `timestamp` | `datetime` | Timestamp of the triggering (tap) bar. Timezone-aware. |
| `config_snapshot` | `StrategyConfig` | Immutable copy of the config used to produce this setup. Audit trail. |

---

## The `reasons` Field

`reasons` is a list of strings explaining why this setup fired. Consumers
should display these to the trader. Examples:

```
"Bullish BOS confirmed"
"Price tapped OTE zone 61.8%–79.0% retracement"
"Leg: 63000 → 65000"
"TP: Fixed RR 2.0R"
```

The Confidence Engine (v0.6) will append its own scored factors to a
derived object. `TradeSetup.reasons` contains only Strategy Engine factors.

## The `warnings` Field

`warnings` is a list of non-fatal cautions. A setup with warnings is still
valid but the trader should be aware. Examples:

```
"HTF trend filter disabled"
"require_close_back disabled — wick entry accepted"
```

---

## The `config_snapshot` Field

Every `TradeSetup` carries the exact `StrategyConfig` that produced it.
This is an immutable audit trail — it lets consumers (Analytics, AI)
know precisely which parameters were active when the setup was detected.

The `config_snapshot` is especially important for replay and backtesting:
when a historical setup is reviewed, its config is self-contained.

---

## How Consumers Use TradeSetup

### Dashboard
Renders the setup visually: OTE zone box, entry/SL/TP levels, reasons list,
warnings badges. Does not modify `TradeSetup`.

### Trade Journal
When the trader decides to act, they call `POST /api/v1/trades` with the
`entry_price`, `stop_loss`, `take_profit`, `symbol`, `direction`, and
`strategy_version` from the `TradeSetup`. The journal then enriches the
record with the current market snapshot.

Future: the journal will accept a `TradeSetup` directly and auto-populate
all fields.

### Confidence Engine (v0.6)
Receives a `TradeSetup` and scores it against additional confluence factors
(session timing, volume, regime alignment). Returns a `ConfidenceScore`
wrapping the original `TradeSetup`. The `TradeSetup` is never mutated.

### AI Assistant (v1.0)
Receives `TradeSetup` objects (not raw market data) as structured context.
Explains the setup in natural language based on `reasons`, `warnings`,
`config_snapshot`, and the structural levels. The AI never analyzes raw
price series.

---

## JSON Representation

```json
{
  "symbol": "BTC",
  "direction": "long",
  "entry": "64000",
  "stop_loss": "63500",
  "take_profit": "65000",
  "risk_reward": "2.0",
  "timeframe": "15m",
  "strategy": "ICT Pure OTE",
  "reasons": [
    "Bullish BOS confirmed",
    "Price tapped OTE zone 61.8%–79.0% retracement",
    "Leg: 63000 → 65000",
    "TP: Fixed RR 2.0R"
  ],
  "warnings": [],
  "swing_high": "65000",
  "swing_low": "63000",
  "ote_top": "63820",
  "ote_bottom": "63580",
  "leg_low": "63000",
  "leg_high": "65000",
  "timestamp": "2026-07-18T12:00:00+00:00",
  "config_snapshot": {
    "swing_len": 5,
    "trade_dir": "Both",
    "use_htf_trend": true,
    "htf_ema_len": 50,
    "ema_slope_lookback": 3,
    "ote_start": "0.618",
    "ote_end": "0.79",
    "require_close_back": false,
    "sl_buffer_pct": "0.05",
    "tp_mode": "Fixed RR",
    "rr_ratio": "2.0",
    "fib_ext": "1.0",
    "invalidate_on_close": true
  }
}
```
