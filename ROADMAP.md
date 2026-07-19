# Roadmap

## Vision

KiyoDesk is a **Strategy Intelligence Platform** — not a trading journal.

The **Domain Engine** is the single source of truth for all trading intelligence.
Every other layer (Dashboard, Journal, Analytics, AI) consumes structured outputs
produced by the Domain Engine. Raw market data never reaches the AI layer directly.

## Architecture

```
Provider Engine
      ↓
Domain Engine
  ├── Strategy Engine
  ├── Confidence Engine
  ├── Market Regime Engine
  ├── Replay Engine (future)
  └── Analytics Extensions
      ↓
Trade Journal
      ↓
Dashboard
      ↓
AI Assistant
```

## Releases

- **0.1** ✅ Backend foundation and provider abstraction
- **0.2** ✅ Trade journal and market snapshots
- **0.3** ✅ React dashboard
- **0.4** ✅ Analytics
- **0.5** Strategy Engine — ICT Pure OTE (optimal trade entry, PD arrays, displacement detection)
- **0.6** Confidence Engine — multi-factor signal scoring fed by Strategy Engine outputs
- **0.7** Market Regime Engine — trend/range/expansion classification; gates Strategy Engine signals
- **0.8** Multi-layer Chart Engine — annotated chart rendering driven by Domain Engine outputs
- **0.9** Replay Engine — historical scenario replay through the full Domain Engine stack
- **1.0** AI Assistant — explains Domain Engine outputs; never analyzes raw market data directly

## AI Policy

AI development is **frozen** until v0.5, v0.6, and v0.7 are complete.
The AI Assistant must only receive structured Domain Engine outputs as input — never raw
price, funding, or liquidation data. The Domain Engine is the intelligence layer;
the AI is an explanation layer.
