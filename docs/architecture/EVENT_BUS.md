# Event Bus Architecture

KiyoDesk uses an internal asynchronous Event Bus to decouple major system components. This allows for a reactive architecture where components can emit events without knowing who is listening.

## Standard Event Model

Each event follows a standard schema defined in `app/schemas/events.py`:

```json
{
    "event_id": "uuid-v4",
    "event_type": "SignalCreated",
    "timestamp": "2026-07-20T09:00:00Z",
    "source": "TradingRuntime",
    "correlation_id": "optional-id",
    "payload": { ... }
}
```

## Supported Events

| Event Type | Source | Description |
|---|---|---|
| `SignalCreated` | TradingRuntime | New trade opportunity detected |
| `SignalUpdated` | TradingRuntime | Existing opportunity updated |
| `SignalDismissed` | OpportunitiesAPI | Opportunity rejected by user |
| `TradeAccepted` | OpportunitiesAPI | Opportunity converted to a trade |
| `TradeOpened` | TradesAPI | Manual trade opened |
| `ManualClose` | TradesAPI | Trade closed manually by user |
| `StopLossHit` | TradeMonitor | Trade closed via stop loss |
| `TakeProfitHit` | TradeMonitor | Trade closed via take profit |
| `TradeClosed` | TradeMonitor | Trade closed (generic) |
| `SettingsUpdated` | SettingsAPI | Dashboard or risk settings changed |

## Usage

### Publishing an Event

```python
from app.schemas.events import Event
from app.services.event_bus import event_bus

await event_bus.publish(Event(
    event_type="SignalCreated",
    source="MyModule",
    payload={"symbol": "BTC"}
))
```

### Subscribing to Events

```python
from app.services.event_bus import event_bus

async def my_subscriber(event):
    print(f"Received {event.event_type} from {event.source}")

# Subscribe to a specific event type
await event_bus.subscribe(my_subscriber, "SignalCreated")

# Subscribe to all events (global)
await event_bus.subscribe(my_subscriber)
```

## Future Integrations

The Event Bus is designed to support future modules without modifying the core implementation:

1. **Notification Providers**: A dedicated service will subscribe to relevant events (e.g., `SignalCreated`, `StopLossHit`) and forward them to Telegram, Discord, etc.
2. **AI Assistant**: The AI layer will subscribe to trade events to provide context-aware insights and performance analysis.
3. **Analytics**: Real-time analytics can be computed by subscribing to trade lifecycle events instead of polling the database.
