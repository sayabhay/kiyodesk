# Changelog

## v0.5.2 — Multi-Timeframe Engine Enhancement

### Added
- **`timeframe_config.py`** (`backend/app/runtime/timeframe_config.py`) — new module defining:
  - `VALID_TIMEFRAMES` — all 13 Binance Futures interval strings (`1m 3m 5m 15m 30m 1h 2h 4h 6h 12h 1d 1w 1M`).
  - `DEFAULT_HTF_MAP` — spec-required LTF→HTF auto-mapping (`15m→1h`, `1h→4h`, `4h→12h`, `12h→1d`, `1d→1w`, `1w→1M`, `1M→1M`, etc.).
  - `InvalidTimeframeError` — `ValueError` subclass; message includes the bad value and the full valid list.
  - `resolve_htf(ltf, override=None)` — resolves the HTF interval; override wins when non-empty; raises `InvalidTimeframeError` on any invalid value.
- **`strategy_htf_candle_limit`** setting (`STRATEGY_HTF_CANDLE_LIMIT`, default `100`) — controls how many HTF bars are fetched per evaluation, independently of the LTF limit.
- **47 new tests** in `backend/tests/test_timeframe_config.py` covering every spec-required mapping, all 13 override paths, wrong-case and empty-string errors, `InvalidTimeframeError` attributes and message content.
- **34 new tests** in `backend/tests/test_strategy_runtime.py` covering runtime construction for all 13 LTF options, override path, invalid config startup failure, concurrent candle fetch with correct intervals and limits, HTF-filter bypass when `ltf == htf`, and `Settings` field defaults.
- **Dashboard settings persistence** — frontend dashboard settings panel now saves strategy, risk, and execution configuration through the backend `/api/v1/settings` endpoint.

### Changed
- **`StrategyRuntime`** refactored:
  - Resolves LTF and HTF at **construction time** — bad config raises `InvalidTimeframeError` on startup, not silently on first tick.
  - Exposes `ltf_interval` and `htf_interval` as read-only properties.
  - Fetches LTF and HTF candles **concurrently** (`asyncio.gather`), each with its own limit.
  - HTF trend filter is **disabled automatically** when `ltf == htf` (monthly edge case — no higher timeframe exists).
- **`strategy_htf_timeframe` default** changed from `"4h"` → `""` (empty string). Empty = auto-resolve via `DEFAULT_HTF_MAP`; any non-empty value = manual override.
- All 465 tests pass (81 new + 384 pre-existing).

---

## v0.5.1 — Replit Deployment & Live Signal Feed

### Added
- **Real OHLCV candle feed** (`backend/app/providers/candles.py`) — fetches Binance Futures
  klines (`/fapi/v1/klines`) with no API key required. LTF (15m, 200 bars) and HTF (4h, 100
  bars) fetched concurrently on every scheduler tick.
- **PostgreSQL support** — async engine uses `asyncpg` driver; Alembic migrations use
  `psycopg2-binary`. SSL handling normalised for Replit's managed database (`sslmode=disable`
  → `connect_args={"ssl": False}`).
- `async_database_url` and `sync_database_url` properties on `Settings` for dialect-aware
  URL construction.
- `_engine_kwargs()` helper in `session.py` maps `sslmode=disable` to asyncpg `connect_args`.

### Changed
- **StrategyRuntime** now fetches real OHLCV candles from Binance Futures directly instead of
  converting single-price `market_data` rows into flat `open=high=low=close=price` bars.
  HTF trend filter (`use_htf_trend`) is now enabled — real 4h candles make the EMA slope
  filter meaningful.
- **Provider order** changed to `binance,coingecko` — Binance Futures public endpoints supply
  funding rate and open interest; CoinGecko is the price-only fallback.
- **CORS policy** broadened to `allow_origins=["*"]` with `allow_credentials=False` for
  Replit proxy compatibility.
- **Vite dev server** configured with `host: "0.0.0.0"`, `allowedHosts: true`, and a
  `/api` proxy to `http://localhost:8000` so the frontend works from any external browser.
- **API base URL** in `frontend/src/api.ts` changed from the hardcoded
  `http://localhost:8000/api/v1` to the relative `/api/v1`. This fixes "Failed to load"
  errors when the app is opened outside Replit's preview pane.

### Fixed
- `asyncpg` `connect()` rejected `sslmode` keyword argument from PostgreSQL URL —
  stripped from async URL and mapped to engine `connect_args`.
- Frontend API calls failed in external browsers because `localhost:8000` resolved to the
  user's own machine rather than the Replit container.

---

## v0.5.0 — Strategy Engine: ICT Pure OTE

Initial release of the Strategy Engine — faithful Python port of the ICT Pure OTE kScript.

### Added
- `StrategyEngine` — stateful orchestrator with `ZoneState` persisting across bar evaluations.
- Swing pivot detection (`swing.py`) — strict pivot high/low matching kScript `pivothigh/pivotlow`.
- Break of Structure detection (`bos.py`) — close-crossover BOS (up and down).
- HTF EMA trend filter (`htf_trend.py`) — EMA slope using `k = 2 / (period + 1)`, fail-open when insufficient bars.
- OTE zone state machine (`ote.py`) — arm on BOS, tap check (wick or close-back), disarm after tap.
- Risk calculation (`risk.py`) — Fixed RR and Fib Extension TP modes; entry guard before TP.
- `StrategyService` — stateless bar-by-bar replay facade, public API boundary.
- `TradeSetup` domain object — serializable, carries `config_snapshot` for audit trail.
- `TradeOpportunity` model — persisted setup with full lifecycle state machine.
- `LifecycleManager` — owns all status transitions; raises `InvalidTransitionError` on illegal moves.
- `OpportunityManager` — create-or-update with `Deduplicator` (entry ± tolerance check).
- REST endpoints: `GET /opportunities`, `GET /opportunities/active`, `GET /opportunities/{id}`,
  `POST /opportunities/{id}/accept`, `POST /opportunities/{id}/reject`.
- `CCXTProvider` — exchange-configurable provider (binance/bybit/bitget/okx), concurrent
  ticker + funding + OI fetch, per-request exchange instances.

---

## v0.4.0 — Analytics

- Analytics aggregation endpoint: win rate, profit factor, expectancy, per-symbol breakdowns.
- Analytics section on dashboard.

---

## v0.3.0 — React Dashboard

- React 18 + TypeScript + Vite + TailwindCSS frontend.
- Live Market section with price charts (ECharts).
- Trade Journal UI with close / delete actions.

---

## v0.2.0 — Trade Journal & Market Snapshots

- `market_data` table and scheduler-driven snapshots (60s interval).
- Trade Journal model, REST endpoints (CRUD + close).
- Provider failover via `ProviderManager`.

---

## v0.1.0 — Initial Repository

- FastAPI application factory with lifespan management.
- `BinanceProvider`, `CoinGeckoProvider`, `KiyotakaProvider` base implementations.
- SQLAlchemy async session + Alembic migration scaffold.
- APScheduler integration for market data collection.
