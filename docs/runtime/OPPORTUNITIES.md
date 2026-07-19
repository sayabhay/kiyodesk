# Trade Opportunities

## What Is a TradeOpportunity?

A `TradeOpportunity` is a persisted record created by the Trading Runtime when
the Strategy Engine detects a valid `TradeSetup`.  It represents a structured
trading opportunity that the user can Accept or Reject via the dashboard.

```
TradeSetup (domain object, ephemeral)
      ↓
Trading Runtime
      ↓
TradeOpportunity (persisted, has lifecycle)
      ↓
User Decision: Accept → Trade Journal entry
               Reject → lifecycle only, no trade
```

---

## Field Reference

| Field | Type | Description |
|---|---|---|
| `id` | `int` | Primary key |
| `strategy` | `str` | Strategy name (e.g. `"ICT Pure OTE"`) |
| `strategy_version` | `str \| None` | Strategy version string |
| `symbol` | `str` | Ticker symbol (e.g. `"BTC"`) |
| `timeframe` | `str \| None` | Chart timeframe label (e.g. `"15m"`) |
| `direction` | `str` | `"long"` or `"short"` |
| `entry` | `Decimal` | Suggested entry price |
| `stop_loss` | `Decimal` | Calculated stop loss |
| `take_profit` | `Decimal` | Calculated take profit |
| `risk_reward` | `Decimal` | Derived R:R = `abs(tp - entry) / abs(entry - sl)` |
| `status` | `str` | Current lifecycle status (see below) |
| `created_at` | `datetime` | When the opportunity was first detected |
| `updated_at` | `datetime` | Last modification time |
| `expires_at` | `datetime \| None` | When the opportunity expires (default: +4 hours) |
| `taken_at` | `datetime \| None` | When the user accepted it |
| `invalidated_at` | `datetime \| None` | When the strategy invalidated it |
| `trade_id` | `int \| None` | FK → `trades.id`, set when accepted |
| `confidence` | `Decimal \| None` | **null until v0.6** — Confidence Engine score |
| `market_regime` | `str \| None` | **null until v0.7** — Market Regime classification |
| `trade_setup_json` | `str` | Full `TradeSetup` serialized as JSON (immutable audit trail) |
| `metadata_json` | `str \| None` | Arbitrary future metadata (e.g. rejection notes) |
| `entry_tolerance` | `Decimal` | Tolerance used for deduplication |

---

## Placeholder Fields

### `confidence` — null until Sprint 3 (v0.6)

The Confidence Engine will score each `TradeSetup` against confluence factors:
session timing, volume confirmation, PD array alignment, trend context.  Until
then, `confidence` is always `null`.

The dashboard displays: **"Confidence · Coming in Sprint 3"**

### `market_regime` — null until Sprint 4 (v0.7)

The Market Regime Engine will classify market state (trending, ranging, expanding)
and gate Strategy Engine signals.  Until then, `market_regime` is always `null`.

The dashboard displays: **"Regime · Coming in Sprint 4"**

---

## Deduplication

The Runtime never creates duplicate ACTIVE opportunities for the same setup.

**Duplicate criteria:**
- `strategy` equals
- `symbol` equals (case-insensitive)
- `timeframe` equals (both None, or both same value)
- `direction` equals
- `abs(entry - new_entry) <= entry_tolerance`
- `status == "active"`

When a duplicate is found, the existing opportunity is **updated** (refreshed
`trade_setup_json` and `updated_at`) rather than a new row being inserted.

Default `entry_tolerance = 0.01` (1 cent).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/v1/opportunities` | List all (query: `symbol`, `status`, `limit`) |
| `GET` | `/api/v1/opportunities/active` | List ACTIVE opportunities |
| `GET` | `/api/v1/opportunities/{id}` | Get one by id |
| `POST` | `/api/v1/opportunities/{id}/accept` | Accept → create Trade Journal entry |
| `POST` | `/api/v1/opportunities/{id}/reject` | Reject → lifecycle only |

### Accept

1. Load opportunity (404 if not found)
2. Verify status is ACTIVE (409 if not)
3. Create `Trade` via `TradeService.create()` using opportunity fields
4. Transition opportunity: ACTIVE → TAKEN, set `trade_id`
5. Return updated opportunity

The Strategy Engine is **not** called during accept.  It already produced
the `TradeSetup`; the opportunity carries the full setup in `trade_setup_json`.

### Reject

1. Load opportunity (404 if not found)
2. Transition: ACTIVE → REJECTED
3. Optional `notes` stored in `metadata_json`
4. No trade is created

---

## `trade_setup_json`

Every `TradeOpportunity` stores the complete `TradeSetup` that created it as
a JSON string.  This is the immutable audit trail.

```json
{
  "symbol": "BTC",
  "direction": "long",
  "entry": "64000",
  "stop_loss": "63500",
  "take_profit": "65000",
  "risk_reward": "2.0",
  "reasons": ["Bullish BOS confirmed", "Price tapped OTE zone 61.8%–79.0%"],
  "warnings": ["HTF filter disabled"],
  "config_snapshot": { ... all 13 StrategyConfig fields ... }
}
```

The API response parses `reasons` and `warnings` out of this JSON for
convenience.  The full JSON is also returned in `trade_setup_json` for
clients that need the complete `TradeSetup`.
