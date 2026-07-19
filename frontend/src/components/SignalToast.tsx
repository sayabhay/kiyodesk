/**
 * SignalToast — floating notification for brand-new trade signals.
 *
 * Subscribes to the SignalEventBus and renders a stacked list of toast cards
 * in the bottom-right corner. Each toast auto-dismisses after 8 seconds.
 *
 * Future extension: additional notification adapters (Telegram, Discord, etc.)
 * subscribe to the same signalBus — no changes needed here.
 */

import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from 'react-query'
import { api } from '../api'
import { signalBus, type SignalEvent } from '../signals/SignalEventBus'

const TOAST_TTL_MS = 8_000

interface ToastItem extends SignalEvent {
  toastId: string
}

function fmt(v: string | null, decimals = 2): string {
  if (!v) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function Toast({
  item,
  onClose,
  onAccept,
  onDismiss,
}: {
  item: ToastItem
  onClose: () => void
  onAccept: () => void
  onDismiss: () => void
}) {
  const { opportunity: opp } = item
  const isLong = opp.direction === 'long'

  return (
    <div
      className={`
        w-80 bg-brand-800 border border-brand-600 rounded-xl shadow-2xl
        border-l-4 ${isLong ? 'border-l-profit' : 'border-l-loss'}
        animate-slide-in
      `}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 pt-3 pb-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
          </span>
          <span className="text-xs font-semibold text-accent uppercase tracking-wider">
            New Signal
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-gray-500 hover:text-gray-300 text-lg leading-none"
        >
          ×
        </button>
      </div>

      {/* Body */}
      <div className="px-4 pb-3">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-base font-bold">{opp.symbol}</span>
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
              isLong
                ? 'bg-profit/20 text-profit border border-profit/30'
                : 'bg-loss/20 text-loss border border-loss/30'
            }`}
          >
            {opp.direction.toUpperCase()}
          </span>
          {opp.timeframe && (
            <span className="text-xs text-gray-500 bg-brand-700 px-2 py-0.5 rounded-full">
              {opp.timeframe}
            </span>
          )}
        </div>

        <div className="grid grid-cols-3 gap-2 mb-3">
          <div>
            <p className="text-xs text-gray-500">Entry</p>
            <p className="text-xs font-medium">${fmt(opp.entry)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">SL</p>
            <p className="text-xs font-medium text-loss">${fmt(opp.stop_loss)}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">TP</p>
            <p className="text-xs font-medium text-profit">${fmt(opp.take_profit)}</p>
          </div>
        </div>

        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-gray-400">
            R:R{' '}
            <span className="text-white font-medium">{fmt(opp.risk_reward, 1)}R</span>
          </span>
          <span className="text-xs text-gray-500">{opp.strategy}</span>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button
            onClick={onAccept}
            className="flex-1 py-1.5 text-xs rounded-lg bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30 transition-colors font-medium"
          >
            Accept
          </button>
          <button
            onClick={onDismiss}
            className="flex-1 py-1.5 text-xs rounded-lg bg-brand-700 text-gray-400 border border-brand-600 hover:text-white transition-colors"
          >
            Dismiss
          </button>
        </div>
      </div>

      {/* TTL progress bar */}
      <div className="h-0.5 bg-brand-600 rounded-b-xl overflow-hidden">
        <div
          className="h-full bg-accent/50"
          style={{
            animation: `shrink ${TOAST_TTL_MS}ms linear forwards`,
          }}
        />
      </div>
    </div>
  )
}

export function SignalToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const qc = useQueryClient()
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  useEffect(() => {
    const unsub = signalBus.subscribe((event) => {
      if (!event.isNew) return
      const toastId = `${event.opportunity.id}-${Date.now()}`
      const item: ToastItem = { ...event, toastId }

      setToasts((prev) => [...prev.slice(-4), item]) // max 5 toasts stacked

      const timer = setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.toastId !== toastId))
        timersRef.current.delete(toastId)
      }, TOAST_TTL_MS)

      timersRef.current.set(toastId, timer)
    })

    return () => {
      unsub()
      timersRef.current.forEach(clearTimeout)
    }
  }, [])

  const closeToast = (toastId: string) => {
    const timer = timersRef.current.get(toastId)
    if (timer) clearTimeout(timer)
    timersRef.current.delete(toastId)
    setToasts((prev) => prev.filter((t) => t.toastId !== toastId))
  }

  const handleAccept = async (toastId: string, id: number) => {
    try {
      await api.acceptOpportunity(id)
      qc.invalidateQueries('signals')
      qc.invalidateQueries('opportunities')
      qc.invalidateQueries('trades')
      qc.invalidateQueries('analytics')
    } catch {
      /* errors visible in OpportunitiesSection */
    }
    closeToast(toastId)
  }

  const handleDismiss = async (toastId: string, id: number) => {
    try {
      await api.rejectOpportunity(id)
      qc.invalidateQueries('signals')
      qc.invalidateQueries('opportunities')
    } catch {
      /* silent */
    }
    closeToast(toastId)
  }

  if (toasts.length === 0) return null

  return (
    <>
      {/* Inject keyframes once */}
      <style>{`
        @keyframes shrink {
          from { width: 100%; }
          to   { width: 0%;   }
        }
        @keyframes slide-in {
          from { opacity: 0; transform: translateX(2rem); }
          to   { opacity: 1; transform: translateX(0);    }
        }
        .animate-slide-in { animation: slide-in 0.25s ease-out; }
      `}</style>

      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 items-end">
        {toasts.map((item) => (
          <Toast
            key={item.toastId}
            item={item}
            onClose={() => closeToast(item.toastId)}
            onAccept={() => handleAccept(item.toastId, item.opportunity.id)}
            onDismiss={() => handleDismiss(item.toastId, item.opportunity.id)}
          />
        ))}
      </div>
    </>
  )
}
