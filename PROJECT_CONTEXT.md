# PROJECT CONTEXT

## Project

**KiyoDesk** — Local-first crypto trading intelligence platform.

## Vision

A **Strategy Intelligence Platform**, not a trading journal.
All trading intelligence flows through the Domain Engine.
Raw market data never reaches the AI layer directly.

## Current Version

**v0.5.2** — Multi-Timeframe Engine live. 465 tests passing.

## Architecture

```
Provider Engine
  ├── BinanceProvider    (price + funding + OI — Futures public API, no key)  ← default
  ├── CoinGeckoProvider  (price only, no key)                                 ← fallback
  ├── CCXTProvider       (exchange-configurable: binance/bybit/bitget/okx)
  └── KiyotakaProvider   (price + funding + OI + liquidations — key required)
      ↓
Market Scheduler  — 60s interval, snapshot collection only
      ↓
Trading Runtime   — resolves timeframes, fetches candles, orchestrates lifecycle
  ├── timeframe_config.py   VALID_TIMEFRAMES (13), DEFAULT_HTF_MAP, resolve_htf()
  └── Binance Futures CandleFeed  /fapi/v1/klines, no API key
      ↓
Domain Engine
  ├── Strategy Engine   ✅  ICT Pure OTE — swing/BOS/OTE/HTF EMA — live signals
  ├── Confidence Engine 🔲  v0.6
  ├── Market Regime     🔲  v0.7
  ├── Replay Engine     🔲  v0.9
  └── Analytics
      ↓
Trade Opportunity  — persisted, ACTIVE → TAKEN | REJECTED | INVALIDATED | EXPIRED
      ↓
Trade Journal  — accepted opportunities recorded as trades
      ↓
Dashboard  — Signal Center, Live Market, Opportunities, Analytics, Journal
      ↓
AI Assistant  🔲  v1.0 — explains Domain Engine outputs only
```

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · SQLAlchemy (async, asyncpg) · Alembic · APScheduler |
| Database | PostgreSQL — Replit-managed, `DATABASE_URL` auto-configured |
| Market data | Binance Futures public API · CoinGecko · CCXT |
| Candle feed | Binance Futures `/fapi/v1/klines` — real OHLCV, no API key |
| Frontend | React 18 · TypeScript · Vite 5 · TailwindCSS · ECharts · React Query |

## Ports

| Service | Port | External |
|---|---|---|
| Frontend (Vite) | 5000 | 80 (webview) |
| Backend (uvicorn) | 8000 | 8000 |

Frontend proxies `/api` → `localhost:8000` via Vite dev server.

## Key Modules

| File | Purpose |
|---|---|
| `backend/app/runtime/timeframe_config.py` | `VALID_TIMEFRAMES`, `DEFAULT_HTF_MAP`, `resolve_htf()`, `InvalidTimeframeError` |
| `backend/app/runtime/strategy_runtime.py` | Main orchestrator — TF resolution, candle fetch, strategy eval, persist |
| `backend/app/runtime/market_listener.py` | Scheduler callback adapter |
| `backend/app/providers/candles.py` | Binance Futures kline fetcher |
| `backend/app/core/config.py` | All settings with env var bindings |
| `backend/app/domain/strategy/services/strategy_service.py` | Public Strategy Engine boundary |
| `frontend/src/api.ts` | All frontend API calls — relative `/api/v1` base |
| `frontend/src/signals/SignalEventBus.ts` | Pub/sub bus for signal events |
| `frontend/src/signals/useSignals.ts` | Polling hook — 10s interval, localStorage seen-tracking |

## Active Signals (live)

- **BTC** — ICT Pure OTE, 15m LTF + 1h HTF (auto-resolved), Binance Futures
- **ETH** — ICT Pure OTE, 15m LTF + 1h HTF (auto-resolved), Binance Futures

## Supported Timeframes (v0.5.2)

| LTF | Auto HTF |
|---|---|
| `1m` | `5m` |
| `3m` | `15m` |
| `5m` | `15m` |
| `15m` | `1h` ← current default |
| `30m` | `4h` |
| `1h` | `4h` |
| `2h` | `12h` |
| `4h` | `12h` |
| `6h` | `1d` |
| `12h` | `1d` |
| `1d` | `1w` |
| `1w` | `1M` |
| `1M` | `1M` (HTF filter bypassed) |

## Roadmap

| Version | Status | Milestone |
|---|---|---|
| 0.1–0.4 | ✅ | Backend, journal, dashboard, analytics |
| 0.5 | ✅ | ICT Pure OTE strategy engine — live signals |
| 0.5.1 | ✅ | Replit deployment — PostgreSQL, asyncpg, Vite proxy |
| 0.5.2 | ✅ | Multi-Timeframe Engine — 13 TFs, auto-resolve, startup validation |
| 0.6 | 🔲 | Confidence Engine |
| 0.7 | 🔲 | Market Regime Engine |
| 0.8 | 🔲 | Chart Engine |
| 0.9 | 🔲 | Replay Engine |
| 1.0 | 🔲 | AI Assistant |

## Hard Rules

1. Scheduler: data collection only — no strategy calls, no trade creation.
2. Trading Runtime: the only orchestrator connecting Candle Feed → Strategy → Opportunities.
3. Strategy Engine (`ict/`): frozen — kScript is canonical reference.
4. External imports from `services/` only — never directly from `ict/`.
5. AI receives only structured Domain Engine outputs — never raw market data.
6. All frontend API calls: relative `/api/v1/...` — never `http://localhost:8000`.
7. Timeframes validated at `StrategyRuntime.__init__` — fail loudly at startup, never silently.
8. HTF candles: always fetched from provider — never resampled from LTF bars.
