# Strategy Engine

## Role in the Domain Engine

The Strategy Engine is the first and foundational layer of the Domain Engine.
It consumes normalized OHLCV bar data from the Provider Engine and produces
structured `TradeSetup` domain objects. It never writes to the database and
never reads from it.

```
Provider Engine  →  raw market data (price, funding, OI, liquidations)
      ↓
Strategy Engine  →  TradeSetup domain objects
      ↓
Confidence Engine  (v0.6)
      ↓
Market Regime Engine  (v0.7)
      ↓
Trade Journal / Dashboard / AI Assistant
```

The Strategy Engine does not decide whether a trade should be taken.
It detects whether a setup *exists*. Gating (confidence, regime, risk
management) is the responsibility of later Domain Engine layers.

---

## Current Implementation: ICT Pure OTE

Version 0.5 ships one strategy: **ICT Pure OTE** (Optimal Trade Entry).

Source of truth: `ICT-Pure-OTE-Strategy-ks.txt` (kScript canonical implementation).
The Python port must replicate kScript behavior exactly. When behavior
differs, the kScript wins.

---

## Module Map

```
app/domain/strategy/
  interfaces/
    bar.py              — Bar dataclass (OHLCV + timestamp)
  models/
    config.py           — StrategyConfig (all kScript inputs as fields)
    trade_setup.py      — TradeSetup domain object
  ict/
    swing.py            — Swing pivot detection
    bos.py              — Break of Structure detection
    htf_trend.py        — HTF EMA trend filter
    ote.py              — OTE zone state machine
    risk.py             — SL/TP/RR calculation
    engine.py           — StrategyEngine orchestrator
  services/
    strategy_service.py — Public API boundary
```

External code must only import from `services/strategy_service.py`.
Direct imports from `ict/` are reserved for tests.

---

## Input Contract

### Bar

```python
@dataclass(frozen=True)
class Bar:
    timestamp: datetime   # timezone-aware (UTC preferred)
    open:      Decimal
    high:      Decimal
    low:       Decimal
    close:     Decimal
    volume:    Decimal
```

Bars must be in **chronological order** (oldest first, newest last).
The engine processes `bars[-1]` as the current bar on each call.

### StrategyConfig

All parameters match kScript `input()` declarations with identical defaults.
See `ICT.md` for the full parameter reference.

---

## Output Contract

Returns `TradeSetup | None`.

- `TradeSetup` — a valid setup was detected on the current bar.
- `None` — no setup present. This is a normal, expected result.

`None` must never be treated as an error. Most bars produce `None`.

See `TRADE_SETUP.md` for the full field reference.

---

## Usage

### Via StrategyService (recommended for REST / one-shot evaluation)

```python
from app.domain.strategy.services.strategy_service import StrategyService
from app.domain.strategy.models.config import StrategyConfig

service = StrategyService()
setup = service.evaluate(
    bars=ltf_bars,        # list[Bar], chronological
    htf_bars=h4_bars,     # list[Bar], higher timeframe
    symbol="BTC",
    config=StrategyConfig(),
    timeframe="15m",
)

if setup:
    print(setup.direction, setup.entry, setup.stop_loss, setup.take_profit)
```

`StrategyService` replays the full bar history bar-by-bar through a fresh
`StrategyEngine` instance. The most recent `TradeSetup` detected during
replay is returned.

### Via StrategyEngine directly (for streaming / incremental feeds)

```python
from app.domain.strategy.ict.engine import StrategyEngine
from app.domain.strategy.models.config import StrategyConfig

engine = StrategyEngine(StrategyConfig())   # one instance per symbol/timeframe

# Called on every new bar:
setup = engine.evaluate(bars, htf_bars, "BTC", "15m")
```

The engine is **stateful** — `ZoneState` persists across calls. One engine
instance must be created per (symbol, timeframe) pair and reused.

### Via REST API

```
POST /api/v1/strategy/evaluate
Content-Type: application/json

{
  "symbol": "BTC",
  "timeframe": "15m",
  "bars": [ { "timestamp": "...", "open": "...", "high": "...", "low": "...", "close": "...", "volume": "..." }, ... ],
  "htf_bars": [ ... ],
  "config": { "use_htf_trend": false, "swing_len": 5 }
}
```

Response: `TradeSetup` JSON or `null`. Both are HTTP 200.

---

## Statefulness and the kScript Model

The kScript runs bar-by-bar in a sequential event loop. Each bar updates
`persist` variables (swing high/low, zone state, waiting flags). The
Python engine mirrors this with `ZoneState` stored on the `StrategyEngine`
instance. State is updated on every `evaluate()` call before the tap check.

This means:
- A BOS on bar N arms the zone.
- The tap check on bar N evaluates the *just-armed* zone.
- A tap on bar N+5 fires against the zone armed on bar N.

The `StrategyService` replicates this by replaying `bars[:i]` for
`i in range(2, len(bars)+1)`, giving the engine the same bar-by-bar
view the kScript had.
