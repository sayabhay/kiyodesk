# Contributing

## Branch Policy

Create a feature branch before any development. Never commit directly to `main`.

```bash
git checkout -b feat/your-feature-name
```

---

## Local Setup (Replit)

The project runs natively on Replit with two workflows:

| Workflow | Command | Port |
|---|---|---|
| **Start application** | `cd frontend && npm run dev` | 5000 |
| **Backend API** | `cd backend && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 |

### First-time setup

```bash
# Backend dependencies
pip install -r backend/requirements.txt

# Frontend dependencies
cd frontend && npm install

# Apply database migrations
cd backend && PYTHONPATH=. python -m alembic upgrade head
```

### Environment variables

Set these in Replit's Secrets / environment panel (not in `.env` files):

| Variable | Default | Description |
|---|---|---|
| `MARKET_PROVIDERS` | `binance,coingecko` | Comma-separated provider failover order |
| `MARKET_SYMBOLS` | `BTC,ETH` | Symbols to monitor |
| `MARKET_REFRESH_SECONDS` | `60` | Scheduler interval in seconds |
| `STRATEGY_TIMEFRAME` | `15m` | LTF execution timeframe (any of 13 supported values) |
| `STRATEGY_HTF_TIMEFRAME` | *(empty)* | HTF override; empty = auto-resolve via `DEFAULT_HTF_MAP` |
| `STRATEGY_CANDLE_LIMIT` | `200` | LTF bars fetched per evaluation |
| `STRATEGY_HTF_CANDLE_LIMIT` | `100` | HTF bars fetched per evaluation |
| `CCXT_API_KEY` | — | Optional — public data works without keys |
| `CCXT_API_SECRET` | — | Optional |
| `KIYOTAKA_API_KEY` | — | Optional |
| `COINGECKO_API_KEY` | — | Optional Pro key for higher rate limits |

The `DATABASE_URL` is managed by Replit and points to the project's PostgreSQL instance.
Do not set it manually.

---

## Running Tests

```bash
cd backend && PYTHONPATH=. python -m pytest tests/ -v
```

465 tests must pass before any PR is merged. The test suite covers:

- Strategy Engine (ICT logic, swing/BOS/OTE/risk)
- Timeframe configuration (`VALID_TIMEFRAMES`, `DEFAULT_HTF_MAP`, `resolve_htf`, `InvalidTimeframeError`)
- Trading Runtime (construction, MTF resolution, candle fetch, opportunity persistence)
- API endpoints (opportunities, trades, market, analytics, recent signals)

---

## Architecture Rules

These constraints are **non-negotiable** and must be upheld in every PR:

1. **The Scheduler collects data only.** It must never evaluate strategies or create trades.
2. **The Trading Runtime is the only orchestrator.** No other layer may directly trigger
   strategy evaluation or create trade opportunities.
3. **The Strategy Engine is frozen.** Do not modify `app/domain/strategy/ict/` without a
   confirmed defect. The kScript (`ICT-Pure-OTE-Strategy-ks.txt`) is the canonical reference.
4. **External code imports from `services/` only.** Never import directly from `ict/`.
5. **The Domain Engine must be independently testable** without the API, Dashboard, or AI layers.
6. **AI never receives raw market data.** The AI Assistant (v1.0) must only receive
   structured `TradeSetup`, `ConfidenceScore`, and `MarketRegime` objects.
7. **kScript fidelity.** When Python behavior and kScript behavior differ, kScript wins.
8. **Timeframes must be validated at construction time.** `StrategyRuntime.__init__` raises
   `InvalidTimeframeError` on bad LTF or HTF override — never fail silently on first tick.
9. **HTF candles must be fetched from the provider.** Never resample HTF bars from LTF data.

---

## Multi-Timeframe Configuration

`STRATEGY_TIMEFRAME` accepts any of the 13 Binance Futures interval strings. The HTF is
auto-resolved via `DEFAULT_HTF_MAP` unless `STRATEGY_HTF_TIMEFRAME` is set explicitly.

```python
from app.runtime.timeframe_config import resolve_htf

resolve_htf("15m")              # → "1h"  (auto)
resolve_htf("4h")               # → "12h" (auto)
resolve_htf("1h", override="12h")  # → "12h" (manual)
```

See `docs/runtime/RUNTIME.md` for the full timeframe table and configuration examples.

---

## Adding a New Migration

```bash
cd backend
PYTHONPATH=. python -m alembic revision --autogenerate -m "describe your change"
PYTHONPATH=. python -m alembic upgrade head
```

Migration files go in `backend/alembic/versions/`. Use the naming convention
`YYYYMMDD_NNNN_description.py`.

---

## Adding a New Provider

1. Implement `MarketDataProvider` from `app/providers/base.py`.
2. Register the provider in `_build_provider_manager()` in `app/main.py`.
3. Add the provider name to `MARKET_PROVIDERS` documentation.
4. Providers must never call the Strategy Engine or write to `trade_opportunities`.

---

## Frontend API Calls

All API calls must use the relative base path `/api/v1` (defined in `frontend/src/api.ts`).
Never hardcode `http://localhost:8000` — it breaks in any browser outside Replit's container.
