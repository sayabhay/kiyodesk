/**
 * useSignals — React hook for the Live Signal Center.
 *
 * Responsibilities:
 *  - Polls GET /api/v1/opportunities/active every 10 seconds.
 *  - Tracks which opportunity ids have been "seen" in localStorage.
 *  - Emits SignalEvents on the bus for every brand-new unseen opportunity.
 *  - Provides accept / reject / dismiss / mark-seen actions.
 *  - Supports client-side filtering by symbol, timeframe, and strategy.
 */

import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from 'react-query'
import { api, type TradeOpportunity } from '../api'
import { signalBus } from './SignalEventBus'

const SEEN_KEY = 'kiyodesk:seen_signals'
const COLLAPSE_KEY = 'kiyodesk:signal_center_open'

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

function loadSeenIds(): Set<number> {
  try {
    const raw = localStorage.getItem(SEEN_KEY)
    if (!raw) return new Set()
    return new Set(JSON.parse(raw) as number[])
  } catch {
    return new Set()
  }
}

function saveSeenIds(ids: Set<number>): void {
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify([...ids]))
  } catch {
    // localStorage may be unavailable (private browsing, storage full).
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface SignalState {
  /** All currently ACTIVE opportunities (unfiltered). */
  signals: TradeOpportunity[]
  /** Filtered subset matching current symbol/timeframe/strategy filters. */
  filteredSignals: TradeOpportunity[]
  /** Unseen subset of filteredSignals. */
  newSignals: TradeOpportunity[]
  /** Total unseen count across ALL signals (ignores filters — drives header badge). */
  newCount: number
  isLoading: boolean

  // Actions
  markSeen: (id: number) => void
  markAllSeen: () => void
  /** Reject opportunity AND mark seen. */
  dismissSignal: (id: number) => void
  acceptSignal: (id: number) => void

  // Filters
  filterSymbol: string
  setFilterSymbol: (s: string) => void
  filterTimeframe: string
  setFilterTimeframe: (s: string) => void
  filterStrategy: string
  setFilterStrategy: (s: string) => void

  // Collapse state
  isOpen: boolean
  setIsOpen: (v: boolean) => void
}

export function useSignals(): SignalState {
  const qc = useQueryClient()

  // Seen ids — initialised from localStorage once.
  const [seenIds, setSeenIdsState] = useState<Set<number>>(loadSeenIds)

  // Track which ids have already been emitted this session to avoid
  // re-emitting on every poll cycle.
  const emittedRef = useRef<Set<number>>(new Set())

  // Filters
  const [filterSymbol, setFilterSymbol] = useState('')
  const [filterTimeframe, setFilterTimeframe] = useState('')
  const [filterStrategy, setFilterStrategy] = useState('')

  // Collapse state — persisted
  const [isOpen, setIsOpenState] = useState<boolean>(() => {
    try {
      const v = localStorage.getItem(COLLAPSE_KEY)
      return v === null ? true : v === 'true'
    } catch {
      return true
    }
  })

  const setIsOpen = (v: boolean) => {
    setIsOpenState(v)
    try {
      localStorage.setItem(COLLAPSE_KEY, String(v))
    } catch {
      /* ignore */
    }
  }

  // Persist seen ids helper
  const setSeenIds = (next: Set<number>) => {
    setSeenIdsState(next)
    saveSeenIds(next)
  }

  // ---------------------------------------------------------------------------
  // Polling query — 10 second interval
  // ---------------------------------------------------------------------------

  const { data: signals = [], isLoading } = useQuery<TradeOpportunity[]>(
    ['signals'],
    () => api.getOpportunities(),
    {
      refetchInterval: 10_000,
      refetchIntervalInBackground: true,
    }
  )

  // ---------------------------------------------------------------------------
  // New signal detection — emit on bus for brand-new ids
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const now = new Date()
    signals.forEach((opp) => {
      if (!emittedRef.current.has(opp.id)) {
        emittedRef.current.add(opp.id)
        const isNew = !seenIds.has(opp.id)
        if (isNew) {
          signalBus.emit({ opportunity: opp, detectedAt: now, isNew: true })
        }
      }
    })
  }, [signals]) // eslint-disable-line react-hooks/exhaustive-deps
  // seenIds intentionally excluded — we only want to emit once per id per session.

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const filteredSignals = signals.filter((opp) => {
    if (filterSymbol && opp.symbol !== filterSymbol) return false
    if (filterTimeframe && opp.timeframe !== filterTimeframe) return false
    if (filterStrategy && opp.strategy !== filterStrategy) return false
    return true
  })

  const newSignals = filteredSignals.filter((opp) => !seenIds.has(opp.id))

  // Unfiltered new count — drives the header badge
  const newCount = signals.filter((opp) => !seenIds.has(opp.id)).length

  // ---------------------------------------------------------------------------
  // Actions
  // ---------------------------------------------------------------------------

  const markSeen = (id: number) => {
    const next = new Set(seenIds)
    next.add(id)
    setSeenIds(next)
  }

  const markAllSeen = () => {
    const next = new Set(seenIds)
    signals.forEach((opp) => next.add(opp.id))
    setSeenIds(next)
  }

  const invalidate = () => {
    qc.invalidateQueries('signals')
    qc.invalidateQueries('opportunities')
    qc.invalidateQueries('trades')
    qc.invalidateQueries('analytics')
  }

  const rejectMutation = useMutation((id: number) => api.rejectOpportunity(id), {
    onSuccess: (_data, id) => {
      markSeen(id)
      invalidate()
    },
  })

  const acceptMutation = useMutation((id: number) => api.acceptOpportunity(id), {
    onSuccess: (_data, id) => {
      markSeen(id)
      invalidate()
    },
  })

  const dismissSignal = (id: number) => {
    rejectMutation.mutate(id)
  }

  const acceptSignal = (id: number) => {
    acceptMutation.mutate(id)
  }

  return {
    signals,
    filteredSignals,
    newSignals,
    newCount,
    isLoading,
    markSeen,
    markAllSeen,
    dismissSignal,
    acceptSignal,
    filterSymbol,
    setFilterSymbol,
    filterTimeframe,
    setFilterTimeframe,
    filterStrategy,
    setFilterStrategy,
    isOpen,
    setIsOpen,
  }
}
