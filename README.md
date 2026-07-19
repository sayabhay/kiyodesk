# KiyoDesk

## Trading Intelligence Platform

KiyoDesk is a **local-first crypto trading intelligence platform** built around a Domain Engine — all trading intelligence flows through the Strategy Engine and never exposes raw market data to downstream layers (AI, Analytics, Journal).

---

## Status

| Module | Status |
|---|---|
| Backend (FastAPI + PostgreSQL) | ✅ Live |
| Provider Engine (Binance, CoinGecko, CCXT) | ✅ Live |
| Strategy Engine — ICT Pure OTE | ✅ Live — firing signals |
| Trading Runtime (real OHLCV candles) | ✅ Live |
| Trade Opportunities + Lifecycle | ✅ Live |
| Trade Journal + Analytics | ✅ Live |
| Dashboard (React + Vite) | ✅ Live |
| Confidence Engine | 🔲 v0.6 |
| Market Regime Engine | 🔲 v0.7 |
| Replay Engine | 🔲 v0.9 |
| AI Assistant | 🔲 v1.0 |

---

## Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy (async) · Alembic · APScheduler
- **Database:** PostgreSQL (Replit-managed, auto-configured via `DATABASE_URL`)
- **Market data:** Binance Futures public API · CoinGecko · CCXT · Kiyotaka (optional)
- **Candle feed:** Binance Futures `/fapi/v1/klines` — real OHLCV, no API key required
- **Frontend:** React 18 · TypeScript · Vite · TailwindCSS · ECharts · React Query

---

## Running on Replit

Two workflows start automatically:

| Workflow | Command | Port |
|---|---|---|
| **Start application** (webview) | `cd frontend && npm run dev` | 5000 |
| **Backend API** | `cd backend && PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` | 8000 |

The frontend proxies all `/api` requests to the backend server-side via Vite, so the app works correctly from any external browser — not just Replit's preview pane.

### Database migrations

```bash
cd backend && PYTHONPATH=. python -m alembic upgrade head
```

---

## Key Environment Variables

| Variable | Default | Notes |
|---|---|---|
| `MARKET_PROVIDERS` | `binance,coingecko` | Comma-separated failover order |
| `MARKET_SYMBOLS` | `BTC,ETH` | Symbols to monitor |
| `MARKET_REFRESH_SECONDS` | `60` | Scheduler interval |
| `STRATEGY_TIMEFRAME` | `15m` | LTF candle interval for ICT engine |
| `STRATEGY_HTF_TIMEFRAME` | `4h` | HTF candle interval for trend filter |
| `STRATEGY_CANDLE_LIMIT` | `200` | LTF bars fetched per evaluation |
| `CCXT_EXCHANGE` | `binance` | Exchange for CCXT provider |
| `CCXT_API_KEY` / `CCXT_API_SECRET` | *(none)* | Optional — public data works without keys |
| `KIYOTAKA_API_KEY` | *(none)* | Optional Kiyotaka provider |
| `COINGECKO_API_KEY` | *(none)* | Optional Pro key for higher rate limits |

---

## Features

- **Signal Center** — ICT Pure OTE signals on BTC and ETH (15m LTF + 4h HTF), auto-refreshes every 10s
- **Live Market** — real-time price, funding rate, and open interest from Binance Futures (no API key)
- **Active Opportunities** — persisted setups with Accept / Reject workflow
- **Trade Journal** — records accepted opportunities with entry, SL, TP, and P&L tracking
- **Analytics** — win rate, profit factor, expectancy, and per-symbol breakdowns

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system diagram.

```
Provider Engine  →  Market Scheduler  →  StrategyRuntime
                                               ↓ (fetches real OHLCV candles)
                                         StrategyService (bar-by-bar replay)
                                               ↓
                                         TradeOpportunity (persisted)
                                               ↓
                                    Dashboard / Trade Journal / AI (future)
```

## Further Reading

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system diagram and layer responsibilities
- [`docs/strategy/STRATEGY.md`](docs/strategy/STRATEGY.md) — Strategy Engine usage
- [`docs/strategy/ICT.md`](docs/strategy/ICT.md) — ICT Pure OTE parameter reference
- [`docs/runtime/RUNTIME.md`](docs/runtime/RUNTIME.md) — Trading Runtime data flow
- [`docs/runtime/OPPORTUNITIES.md`](docs/runtime/OPPORTUNITIES.md) — TradeOpportunity field reference
- [`ROADMAP.md`](ROADMAP.md) — release plan and AI policy
