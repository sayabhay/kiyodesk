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
| Multi-Timeframe Engine (all 13 TFs, auto-resolve) | ✅ Live — v0.5.2 |
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
| `STRATEGY_TIMEFRAME` | `15m` | LTF execution timeframe (any of 13 supported TFs) |
| `STRATEGY_HTF_TIMEFRAME` | *(empty)* | HTF override; empty = auto-resolve from `DEFAULT_HTF_MAP` |
| `STRATEGY_CANDLE_LIMIT` | `200` | LTF bars fetched per evaluation |
| `STRATEGY_HTF_CANDLE_LIMIT` | `100` | HTF bars fetched per evaluation |
| `CCXT_EXCHANGE` | `binance` | Exchange for CCXT provider |
| `CCXT_API_KEY` / `CCXT_API_SECRET` | *(none)* | Optional — public data works without keys |
| `KIYOTAKA_API_KEY` | *(none)* | Optional Kiyotaka provider |
| `COINGECKO_API_KEY` | *(none)* | Optional Pro key for higher rate limits |

### Supported execution timeframes

`STRATEGY_TIMEFRAME` accepts any of these 13 Binance Futures interval strings:

| Value | Label | Auto-resolved HTF |
|---|---|---|
| `1m` | 1 minute | `5m` |
| `3m` | 3 minutes | `15m` |
| `5m` | 5 minutes | `15m` |
| `15m` | 15 minutes | `1h` ← default |
| `30m` | 30 minutes | `4h` |
| `1h` | 1 hour | `4h` |
| `2h` | 2 hours | `12h` |
| `4h` | 4 hours | `12h` |
| `6h` | 6 hours | `1d` |
| `12h` | 12 hours | `1d` |
| `1d` | 1 day | `1w` |
| `1w` | 1 week | `1M` |
| `1M` | 1 month | `1M` (HTF filter bypassed) |

---

## Features

- **Signal Center** — ICT Pure OTE signals on BTC and ETH, auto-refreshes every 10s. Default: 15m LTF + 1h HTF (auto-resolved).
- **Multi-Timeframe Engine** — configurable LTF execution across all 13 timeframes; HTF auto-resolved or manually overridden; both validated at startup.
- **Live Market** — real-time price, funding rate, and open interest from Binance Futures (no API key)
- **Active Opportunities** — persisted setups with Accept / Reject workflow
- **Trade Journal** — records accepted opportunities with entry, SL, TP, and P&L tracking
- **Analytics** — win rate, profit factor, expectancy, and per-symbol breakdowns

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system diagram.

```
Provider Engine  →  Market Scheduler  →  StrategyRuntime
                                               ↓
                                     resolve_htf(ltf, override)   ← timeframe_config.py
                                               ↓ (concurrent)
                               fetch_candles(symbol, ltf, ltf_limit)
                               fetch_candles(symbol, htf, htf_limit)   ← Binance Futures
                                               ↓
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
- [`docs/runtime/RUNTIME.md`](docs/runtime/RUNTIME.md) — Trading Runtime and MTF configuration
- [`docs/runtime/OPPORTUNITIES.md`](docs/runtime/OPPORTUNITIES.md) — TradeOpportunity field reference
- [`ROADMAP.md`](ROADMAP.md) — release plan and AI policy
- [`CHANGELOG.md`](CHANGELOG.md) — per-version change history
