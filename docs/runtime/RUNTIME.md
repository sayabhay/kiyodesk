# Trading Runtime

## Purpose

The Trading Runtime is the orchestration layer that connects the Provider Engine,
the Strategy Engine, and the Trade Journal into a single automated trading lifecycle.

It is the **only** component allowed to connect:

```
Candle Feed  →  Strategy Engine  →  Trade Opportunities  →  Trade Journal
```

No other layer may directly trigger strategy evaluation or create trade opportunities.

---

## Design Constraints

| Constraint | Rationale |
|---|---|
| Scheduler collects market snapshots only | Keeps the Scheduler a pure I/O layer with no business logic |
| Runtime is the only orchestrator | Single point of responsibility for the trading lifecycle |
| Strategy Engine is never modified | The kScript is the canonical reference; the Runtime only calls it |
| AI never receives raw market data | The Runtime produces structured Domain Engine outputs; AI consumes those |
| Candle fetching is Runtime's responsibility | Decouples candle data from snapshot storage — snapshots and OHLCV serve different purposes |

---

## Module Map

```
app/runtime/
  __init__.py
  strategy_runtime.py    — orchestrator: fetches OHLCV candles, runs strategy, persists opportunity
  market_listener.py     — callback adapter: called by scheduler after each market refresh
  opportunity_manager.py — create-or-update TradeOpportunity with deduplication
  lifecycle_manager.py   — status transitions for TradeOpportunity
  deduplicator.py        — prevents duplicate ACTIVE opportunities

app/providers/candles.py — Binance Futures kline fetcher (no API key required)
```

---

## Data Flow

```
MarketScheduler._refresh_all(symbol)
      ↓  [market snapshot — price, funding, OI stored to DB]
MarketService.get_snapshot(symbol)  →  market_data table updated
      ↓  [on_refresh callback]
MarketListener.__call__(symbol)
      ↓
StrategyRuntime.on_market_update(symbol)
      ↓
  1. fetch_candles(symbol, interval="15m", limit=200)  ← LTF from Binance Futures
  2. fetch_candles(symbol, interval="4h",  limit=100)  ← HTF from Binance Futures
     (fetched concurrently via asyncio.gather)
  3. StrategyService.evaluate(ltf_bars, htf_bars, symbol, config)
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

## Candle Feed

The Runtime fetches real OHLCV bars directly from the **Binance Futures public API**
(`/fapi/v1/klines`) — no API key required. This replaces the previous approach of
converting single-price `market_data` snapshots into flat `open=high=low=close=price` bars.

```python
# app/providers/candles.py
async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 200) -> list[Bar]:
    """Fetch OHLCV bars from Binance Futures (public, no API key)."""
    ...
```

**Symbol map** (internal `BTC`/`ETH` → Binance instrument):

| App symbol | Binance instrument |
|---|---|
| `BTC` | `BTCUSDT` |
| `ETH` | `ETHUSDT` |

Each `Bar` has `timestamp` (UTC), `open`, `high`, `low`, `close`, `volume` as `Decimal`.
Bars are returned in chronological order (oldest first).

---

## Scheduler Integration

The Scheduler accepts an optional `on_refresh: Callable[[str], Awaitable[None]]` callback.
It is called **after** a successful market snapshot refresh for each symbol.

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

## Configuration

Strategy evaluation uses `StrategyConfig` with settings driven by environment variables:

| Parameter | Env var | Value | Notes |
|---|---|---|---|
| `use_htf_trend` | — | `True` when HTF bars ≥ 2 | Enabled — real 4h candles available |
| LTF interval | `STRATEGY_TIMEFRAME` | `15m` | kScript default |
| HTF interval | `STRATEGY_HTF_TIMEFRAME` | `4h` | kScript default |
| LTF bar count | `STRATEGY_CANDLE_LIMIT` | `200` | kScript default |
| `swing_len` | — | `5` | kScript default |
| `invalidate_on_close` | — | `True` | kScript default |
| `tp_mode` | — | `"Fixed RR"` | kScript default |
| `rr_ratio` | — | `2.0` | kScript default |

Per-symbol config overrides are a planned future feature.

---

## Error Handling

| Layer | Error handling |
|---|---|
| `MarketScheduler` | Catches data fetch errors per symbol; logs + continues |
| `MarketScheduler` | Catches `on_refresh` callback errors per symbol; logs + continues |
| `MarketListener` | Catches all `StrategyRuntime` errors; logs + swallows |
| `StrategyRuntime` | Catches candle fetch failures; logs warning + returns `None` |
| `StrategyRuntime` | Returns `None` on insufficient bars; propagates unexpected errors |

A runtime failure for one symbol never affects another symbol's evaluation.
