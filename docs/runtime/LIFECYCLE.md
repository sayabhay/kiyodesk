# TradeOpportunity Lifecycle

## State Machine

```
                    ┌─────────────┐
                    │    ACTIVE   │  ← created by Trading Runtime
                    └──────┬──────┘
                           │
          ┌────────────────┼─────────────────┬──────────────┐
          ▼                ▼                 ▼              ▼
      ┌────────┐     ┌──────────┐    ┌─────────────┐  ┌─────────┐
      │  TAKEN │     │ REJECTED │    │ INVALIDATED │  │ EXPIRED │
      └───┬────┘     └──────────┘    └─────────────┘  └─────────┘
          │
          ▼
    ┌───────────┐
    │ COMPLETED │
    └───────────┘
```

---

## Status Values

| Status | Description |
|---|---|
| `new` | Created but not yet evaluated (reserved for future batch ingestion) |
| `active` | Live opportunity — visible on dashboard, awaiting user decision |
| `taken` | User accepted; a Trade Journal entry has been created |
| `rejected` | User rejected; no trade created |
| `invalidated` | Strategy detected the setup has failed (e.g. SL broken before entry) |
| `expired` | TTL exceeded without user action (default: 4 hours after creation) |
| `completed` | The linked trade has been closed |

---

## Valid Transitions

| From | To | Trigger | Sets field |
|---|---|---|---|
| `active` | `taken` | User clicks Accept | `trade_id`, `taken_at` |
| `active` | `rejected` | User clicks Reject | (optional `metadata_json.rejection_notes`) |
| `active` | `invalidated` | Strategy Runtime detects failure | `invalidated_at` |
| `active` | `expired` | TTL check (future scheduled job) | — |
| `taken` | `completed` | Trade is closed (future integration) | — |

All other transitions are invalid and raise `InvalidTransitionError`.

---

## LifecycleManager

The `LifecycleManager` class owns all transitions.  Methods mutate the
`TradeOpportunity` object **in memory** and return it.  The caller is
responsible for persisting via `OpportunityRepository.update()`.

```python
from app.runtime.lifecycle_manager import LifecycleManager, InvalidTransitionError

lm = LifecycleManager()

# Accept — ACTIVE → TAKEN
lm.accept(opportunity, trade_id=42)

# Reject — ACTIVE → REJECTED
lm.reject(opportunity)

# Invalidate — ACTIVE → INVALIDATED
lm.invalidate(opportunity)

# Expire — ACTIVE → EXPIRED
lm.expire(opportunity)

# Complete — TAKEN → COMPLETED
lm.complete(opportunity)
```

### `InvalidTransitionError`

Raised when an illegal status transition is attempted.

```python
try:
    lm.accept(already_taken_opportunity, trade_id=99)
except InvalidTransitionError as e:
    print(e.current)  # "taken"
    print(e.target)   # "taken"
    print(str(e))     # "Cannot transition from 'taken' to 'taken'."
```

---

## Persistence Pattern

```python
# Transition in memory
lm.accept(opportunity, trade_id=new_trade.id)

# Persist (update() sets updated_at automatically)
updated = await repository.update(opportunity)
```

Never persist mid-transition.  Always complete the full in-memory mutation
before calling `repository.update()`.

---

## Accept Flow (API)

```
POST /api/v1/opportunities/{id}/accept
      ↓
1. Load opportunity from DB (404 if not found)
2. Check status == ACTIVE (409 if not)
3. TradeService.create(CreateTradeRequest from opportunity fields)
      → Trade Journal entry created
      → Returns trade.id
4. LifecycleManager.accept(opportunity, trade_id=trade.id)
      → opportunity.status = "taken"
      → opportunity.trade_id = trade.id
      → opportunity.taken_at = now()
5. OpportunityRepository.update(opportunity)
6. Return OpportunityResponse
```

The Strategy Engine is **not** called during accept.  The `TradeSetup` that
created this opportunity is stored in `trade_setup_json` and is sufficient.

---

## Expiry (Future)

A scheduled job will periodically scan ACTIVE opportunities whose `expires_at`
is in the past and call `LifecycleManager.expire()` on them.

This is not implemented in Sprint 2.5.  The `expires_at` field is set at
creation time (+4 hours by default) but is not currently enforced automatically.

---

## Completion (Future)

When the linked trade is closed (via `PATCH /api/v1/trades/{id}/close`),
the system will transition the opportunity from TAKEN → COMPLETED and record
final P&L against the opportunity.

This is not implemented in Sprint 2.5.  The `trade_id` link is present and
ready for this integration.
