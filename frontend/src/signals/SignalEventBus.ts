/**
 * SignalEventBus — lightweight pub/sub singleton for trade signal events.
 *
 * Architecture note
 * -----------------
 * The bus decouples signal detection (polling, future WebSockets) from
 * notification delivery (dashboard toast, future Telegram/Discord/push).
 *
 * To add a new notification channel:
 *   1. Import `signalBus` in your adapter module.
 *   2. Call `signalBus.subscribe(listener)` — returns an unsubscribe fn.
 *   3. Call `signalBus.emit(event)` from your transport (WebSocket handler, etc.)
 *
 * Current subscribers:
 *   - SignalToast  (dashboard floating notification)
 *   - SignalCenter (header badge count via useSignals hook)
 *
 * Future subscribers (not yet implemented):
 *   - Telegram adapter
 *   - Discord webhook adapter
 *   - Email adapter
 *   - Mobile push adapter
 */

import type { TradeOpportunity } from '../api'

export interface SignalEvent {
  opportunity: TradeOpportunity
  detectedAt: Date
  /** true = brand-new id not seen before; false = re-surfaced after a page reload */
  isNew: boolean
}

export type SignalListener = (event: SignalEvent) => void

class SignalEventBus {
  private listeners = new Set<SignalListener>()

  /**
   * Subscribe to signal events.
   * @returns An unsubscribe function — call it on component unmount.
   */
  subscribe(listener: SignalListener): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  /** Emit a signal event to all current subscribers. */
  emit(event: SignalEvent): void {
    this.listeners.forEach((l) => {
      try {
        l(event)
      } catch {
        // Listener errors must never crash the bus.
      }
    })
  }

  /** Current subscriber count — useful for debugging. */
  get size(): number {
    return this.listeners.size
  }
}

/** Application-wide singleton. Import this directly; do not instantiate. */
export const signalBus = new SignalEventBus()
