# KiyoDesk

## Project Overview

KiyoDesk is a local-first crypto trading intelligence platform. It monitors live market data, runs an ICT strategy engine to surface trade setups, and maintains a trade journal with analytics.

**Stack:**
- **Backend:** Python 3.12 / FastAPI + SQLAlchemy (async) + Alembic, runs on port 8000
- **Frontend:** React 18 + TypeScript + Vite + TailwindCSS + ECharts, runs on port 5000
- **Database:** Replit-managed PostgreSQL (auto-configured via `DATABASE_URL`)
- **Market data:** CoinGecko (public) → Binance CCXT (public) → Kiyotaka (optional, needs API key)

## How to Run

Two workflows start automatically:

| Workflow | Command | Port |
|---|---|---|
| **Start application** (webview) | `cd frontend && npm run dev` | 5000 |
| **Backend API** | `cd backend && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 |

The frontend proxies `/api` requests to the backend, so the Vite dev server is the single entry point.

## Environment Variables

Set in Replit Secrets or env vars:

| Variable | Default | Notes |
|---|---|---|
| `MARKET_PROVIDERS` | `coingecko,binance` | Comma-separated failover order |
| `MARKET_SYMBOLS` | `BTC,ETH` | Symbols to monitor |
| `CCXT_EXCHANGE` | `binance` | Exchange for CCXT provider |
| `CCXT_API_KEY` / `CCXT_API_SECRET` | *(none)* | Optional — public data works without keys |
| `KIYOTAKA_API_KEY` | *(none)* | Optional Kiyotaka provider |
| `COINGECKO_API_KEY` | *(none)* | Optional Pro key for higher rate limits |
| `LOG_LEVEL` | `INFO` | |

## Database Migrations

Alembic manages the schema. To apply new migrations:

```bash
cd backend && PYTHONPATH=. python -m alembic upgrade head
```

Migration files live in `backend/alembic/versions/`.

## Project Structure

```
backend/
  app/
    api/v1/          # FastAPI route handlers
    core/            # Config, logging, security
    database/        # Session, base model, migrations helper
    domain/strategy/ # ICT strategy engine (BOS, OTE, HTF trend, risk)
    providers/       # Market data providers (Binance, CoinGecko, CCXT, Kiyotaka)
    runtime/         # Market listener + strategy runtime
    scheduler/       # APScheduler market refresh job
  alembic/           # DB migration environment
frontend/
  src/               # React components and pages
```

## User Preferences

- Keep the project's existing structure and stack — no restructuring without explicit request.
