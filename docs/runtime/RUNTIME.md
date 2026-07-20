# Trading Runtime

## Purpose

The Trading Runtime is the orchestration layer that connects the Candle Feed,
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
| Scheduler collects snapshots only | Keeps the Scheduler a pure I/O layer with no business logic |
| Runtime is the only orchestrator | Single point of responsibility for the trading lifecycle |
| HTF candles fetched from provider | Real HTF bars required — never resampled from LTF |
| Strategy Engine is never modified | The kScript is the canonical reference; the Runtime only calls it |
| AI never receives raw market data | The Runtime produces structured Domain Engine outputs; AI consumes those |
| Timeframes validated at startup | Misconfiguration surfaces immediately, not on first tick |

---

## Module Map

```
app/runtime/
  __init__.py
  strategy_runtime.py    — orchestrator: resolves TFs, fetches OHLCV, runs strategy, persists
  market_listener.py     — callback adapter: called by scheduler after each market refresh
  opportunity_manager.py — create-or-update TradeOpportunity with deduplication
  lifecycle_manager.py   — status transitions for TradeOpportunity
  deduplicator.py        — prevents duplicate ACTIVE opportunities
  timeframe_config.py    — VALID_TIMEFRAMES, DEFAULT_HTF_MAP, resolve_htf()

app/providers/candles.py — Binance Futures kline fetcher (no API key required)
```

---

## Multi-Timeframe Configuration

### Supported execution timeframes

All timeframes are Binance Futures interval identifiers.
Minutes, hours, days, and weeks use lowercase suffixes; months use uppercase `M`.

| Timeframe | Label | Default HTF |
|---|---|---|
| `1m` | 1 minute | `5m` |
| `3m` | 3 minutes | `15m` |
| `5m` | 5 minutes | `15m` |
| `15m` | 15 minutes | `1h` |
| `30m` | 30 minutes | `4h` |
| `1h` | 1 hour | `4h` |
| `2h` | 2 hours | `12h` |
| `4h` | 4 hours | `12h` |
| `6h` | 6 hours | `1d` |
| `12h` | 12 hours | `1d` |
| `1d` | 1 day | `1w` |
| `1w` | 1 week | `1M` |
| `1M` | 1 month | `1M` ¹ |

¹ Monthly maps to itself — no higher institutional timeframe exists.
  The Strategy Engine's HTF trend filter is bypassed automatically.

### HTF resolution rules

1. If `STRATEGY_HTF_TIMEFRAME` is set and non-empty → that value is used (manual override).
2. Otherwise → `DEFAULT_HTF_MAP[STRATEGY_TIMEFRAME]` is used (auto-resolution).
3. Both the LTF and the HTF override must be in `VALID_TIMEFRAMES` or startup raises.
4. HTF candles are always fetched from Binance Futures — never calculated by resampling.

### `timeframe_config.py` API

```python
from app.runtime.timeframe_config import (
    VALID_TIMEFRAMES,      # tuple[str, ...] of all 13 valid timeframe strings
    DEFAULT_HTF_MAP,       # dict[str, str] — LTF → HTF auto-mapping
    InvalidTimeframeError, # raised on unrecognised timeframe strings
    resolve_htf,           # resolution function
)

# Auto-resolve:
resolve_htf("15m")               # → "1h"
resolve_htf("4h")                # → "12h"
resolve_htf("12h")               # → "1d"

# Manual override:
resolve_htf("1h", override="12h")   # → "12h"
resolve_htf("15m", override="4h")   # → "4h"

# Invalid → raises InvalidTimeframeError (subclass of ValueError):
resolve_htf("10m")               # ❌ not a supported timeframe
resolve_htf("1h", override="3H") # ❌ wrong case
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
  1. Resolve HTF:
       ltf = settings.strategy_timeframe           (e.g. "15m")
       htf = resolve_htf(ltf, override or None)    (e.g. "1h")

  2. Concurrent candle fetch from Binance Futures:
       asyncio.gather(
           fetch_candles(symbol, interval=ltf, limit=ltf_limit),  ← LTF bars
           fetch_candles(symbol, interval=htf, limit=htf_limit),  ← HTF bars
       )

  3. StrategyService.evaluate(ltf_bars, htf_bars, symbol, config)
       use_htf_trend = len(htf_bars) >= 2 AND ltf != htf

  4. If TradeSetup is None → return None

  5. OpportunityManager.create_or_update(setup)
       ↓  [deduplication check]
       Deduplicator.find_existing(setup, repository)
       7a. If duplicate: update trade_setup_json, return existing
       7b. If new: INSERT TradeOpportunity(status=ACTIVE)
      ↓
TradeOpportunity persisted → available on GET /api/v1/opportunities/active
```

---

## Candle Feed

Real OHLCV bars are fetched from the **Binance Futures public API**
(`/fapi/v1/klines`) — no API key required.

```python
# app/providers/candles.py
async def fetch_candles(symbol: str, interval: str = "15m", limit: int = 200) -> list[Bar]:
    """Fetch OHLCV bars from Binance Futures (public, no API key)."""
```

**Symbol map** (app-level → Binance instrument):

| App symbol | Binance instrument |
|---|---|
| `BTC` | `BTCUSDT` |
| `ETH` | `ETHUSDT` |

Bars are returned in chronological order (oldest first), matching the kScript
convention. Each `Bar` has `timestamp` (UTC), `open`, `high`, `low`, `close`,
and `volume` as `Decimal`.

---

## Scheduler Integration

The Scheduler accepts an optional `on_refresh: Callable[[str], Awaitable[None]]`
callback called **after** a successful market snapshot refresh for each symbol.
It also supports an optional `on_idle: Callable[[], Awaitable[None]]` callback that
runs once after all symbols are refreshed.

```python
# In main.py lifespan:
runtime  = StrategyRuntime(active_settings)   # validates TFs at construction time
listener = MarketListener(runtime)
trade_monitor = TradeMonitor(provider_manager, AsyncSessionLocal)
scheduler = MarketScheduler(
    settings,
    provider_manager,
    on_refresh=listener,
    on_idle=trade_monitor.run,
)
```

`MarketListener` wraps `StrategyRuntime` and swallows exceptions so a strategy
error never propagates back to the Scheduler.

`TradeMonitor` uses the `on_idle` hook to scan all open journal trades after a
market refresh cycle, close any trades whose market price has crossed
`stop_loss` or `take_profit`, and mark linked `TAKEN` opportunities as
`COMPLETED`.

---

## Configuration

All timeframe and candle settings are read from environment variables.

| Env var | `Settings` field | Default | Description |
|---|---|---|---|
| `STRATEGY_TIMEFRAME` | `strategy_timeframe` | `15m` | LTF execution timeframe |
| `STRATEGY_HTF_TIMEFRAME` | `strategy_htf_timeframe` | *(empty)* | Manual HTF override; empty → auto-resolve |
| `STRATEGY_CANDLE_LIMIT` | `strategy_candle_limit` | `200` | LTF bars fetched per evaluation |
| `STRATEGY_HTF_CANDLE_LIMIT` | `strategy_htf_candle_limit` | `100` | HTF bars fetched per evaluation |

### Example configurations

```bash
# Default (15m LTF, auto-resolved 1h HTF)
STRATEGY_TIMEFRAME=15m

# 1h execution with auto-resolved 4h HTF
STRATEGY_TIMEFRAME=1h

# 4h execution with auto-resolved 12h HTF
STRATEGY_TIMEFRAME=4h

# Manual override — 1h LTF with 12h HTF
STRATEGY_TIMEFRAME=1h
STRATEGY_HTF_TIMEFRAME=12h

# Daily chart (LTF=1d → HTF=1w auto)
STRATEGY_TIMEFRAME=1d
```

---

## Error Handling

| Layer | Error handling |
|---|---|
| `StrategyRuntime.__init__` | `InvalidTimeframeError` on bad LTF or HTF override → startup fails loudly |
| `MarketScheduler` | Catches data fetch errors per symbol; logs + continues |
| `MarketScheduler` | Catches `on_refresh` callback errors per symbol; logs + continues |
| `MarketListener` | Catches all `StrategyRuntime` errors; logs + swallows |
| `StrategyRuntime.on_market_update` | Catches candle fetch failures; logs warning + returns `None` |
| `StrategyRuntime.on_market_update` | Returns `None` on < 2 LTF bars; propagates unexpected errors |

A runtime failure for one symbol never affects another symbol's evaluation.
