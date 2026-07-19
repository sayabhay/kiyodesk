# Trading Runtime

## Purpose

The Trading Runtime is the orchestration layer that connects the Provider Engine,
the Strategy Engine, and the Trade Journal into a single automated trading lifecycle.

It is the **only** component allowed to connect:

```
Market Data  →  Strategy Engine  →  Trade Opportunities  →  Trade Journal
```

No other layer may directly trigger strategy evaluation or create trade opportunities.

---

## Design Constraints

| Constraint | Rationale |
|---|---|
| Scheduler collects data only | Keeps the Scheduler a pure I/O layer with no business logic |
| Runtime is the only orchestrator | Single point of responsibility for the trading lifecycle |
| Strategy Engine is never modified | Sprint 2 is frozen; the Runtime only calls it |
| AI never receives raw market data | The Runtime produces structured Domain Engine outputs; AI consumes those |

---

## Module Map

```
app/runtime/
  __init__.py
  strategy_runtime.py    — orchestrator: loads bars, runs strategy, persists opportunity
  market_listener.py     — callback adapter: called by scheduler after each refresh
  opportunity_manager.py — create-or-update TradeOpportunity with deduplication
  lifecycle_manager.py   — status transitions for TradeOpportunity
  deduplicator.py        — prevents duplicate ACTIVE opportunities
```

---

## Data Flow

```
MarketScheduler._refresh_all(symbol)
      ↓  [data collection — no business logic]
MarketService.get_snapshot(symbol)  →  market_data table updated
      ↓  [on_refresh callback]
MarketListener.__call__(symbol)
      ↓
StrategyRuntime.on_market_update(symbol)
      ↓
  1. MarketDataRepository.list_history(symbol, limit=200)
  2. Convert MarketData rows → list[Bar]
  3. StrategyService.evaluate(bars, htf_bars, symbol, config)
  4. If TradeSetup is None → return None
  5. OpportunityManager.create_or_update(setup)
      ↓  [deduplication check]
  6. Deduplicator.find_existing(setup, repository)
  7a. If duplicate: update trade_setup_json, return existing
  7b. If new: INSERT TradeOpportunity(status=ACTIVE)
      ↓
TradeOpportunity persisted → available on GET /api/v1/opportunities/active
```

---

## Scheduler Integration

The Scheduler accepts an optional `on_refresh: Callable[[str], Awaitable[None]]` callback.
It is called **after** a successful market data refresh for each symbol.

```python
# In main.py lifespan:
runtime  = StrategyRuntime(settings)
listener = MarketListener(runtime)
scheduler = MarketScheduler(settings, provider_manager, on_refresh=listener)
```

The Scheduler calls `await on_refresh(symbol)` and catches any exception independently
per symbol — a listener failure never blocks market data collection.

`MarketListener` wraps `StrategyRuntime` and swallows exceptions so a strategy error
never propagates back to the Scheduler.

---

## Bar Loading

Market data is stored as single-price snapshots in the `market_data` table
(one row per 60-second scheduler tick).  The Runtime converts each row to a `Bar`
with `open = high = low = close = price` and `volume = 0`.

```python
def _market_data_to_bar(row: MarketData) -> Bar:
    price = row.price or Decimal("0")
    return Bar(timestamp=row.captured_at, open=price, high=price,
               low=price, close=price, volume=Decimal("0"))
```

**TODO (future sprint):** Replace with true OHLCV candles when a candle-history
endpoint is available from the Provider Engine. Until then:
- `use_htf_trend = False` (HTF EMA slope on single-price bars is not meaningful)
- Swing detection and BOS work correctly on close-only data

---

## Configuration

The `StrategyRuntime` uses `StrategyConfig` defaults for all evaluations.
Per-symbol config overrides are a planned future feature.

Key defaults applied by the Runtime:

| Parameter | Value | Reason |
|---|---|---|
| `use_htf_trend` | `False` | Single-price bars — HTF slope filter not meaningful yet |
| `swing_len` | `5` | kScript default |
| `invalidate_on_close` | `True` | kScript default |
| `tp_mode` | `"Fixed RR"` | kScript default |
| `rr_ratio` | `2.0` | kScript default |

---

## Error Handling

| Layer | Error handling |
|---|---|
| `MarketScheduler` | Catches data fetch errors per symbol; logs + continues |
| `MarketScheduler` | Catches `on_refresh` callback errors per symbol; logs + continues |
| `MarketListener` | Catches all `StrategyRuntime` errors; logs + swallows |
| `StrategyRuntime` | Returns `None` on insufficient data; propagates unexpected errors |

A runtime failure for one symbol never affects another symbol's evaluation.
