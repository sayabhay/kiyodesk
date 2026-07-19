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

| Variable | Default | Required |
|---|---|---|
| `MARKET_PROVIDERS` | `binance,coingecko` | No |
| `MARKET_SYMBOLS` | `BTC,ETH` | No |
| `CCXT_API_KEY` | — | No (public data works without) |
| `CCXT_API_SECRET` | — | No |
| `KIYOTAKA_API_KEY` | — | No |
| `COINGECKO_API_KEY` | — | No (Pro key for higher limits) |

The `DATABASE_URL` is managed by Replit and points to the project's PostgreSQL instance.
Do not set it manually.

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
