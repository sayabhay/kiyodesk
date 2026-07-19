import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { api, TradeOpportunity } from '../api'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(v: string | null, decimals = 2): string {
  if (!v) return '—'
  const n = parseFloat(v)
  if (isNaN(n)) return '—'
  return n.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

function timeAgo(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function dirBadge(dir: string) {
  return dir === 'long'
    ? 'bg-profit/20 text-profit border border-profit/30'
    : 'bg-loss/20 text-loss border border-loss/30'
}

// ---------------------------------------------------------------------------
// Opportunity Detail Modal
// ---------------------------------------------------------------------------

function OpportunityDetail({
  opp,
  onClose,
}: {
  opp: TradeOpportunity
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 py-8 overflow-y-auto">
      <div className="bg-brand-800 border border-brand-600 rounded-xl p-6 w-full max-w-lg mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">
            {opp.symbol}{opp.timeframe ? ` · ${opp.timeframe}` : ''}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Levels */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {[
            { label: 'Entry', value: `$${fmt(opp.entry)}` },
            { label: 'Stop Loss', value: `$${fmt(opp.stop_loss)}` },
            { label: 'Take Profit', value: `$${fmt(opp.take_profit)}` },
            { label: 'Risk / Reward', value: `${fmt(opp.risk_reward, 1)}R` },
          ].map(({ label, value }) => (
            <div key={label} className="bg-brand-700 rounded-lg p-3">
              <p className="text-xs text-gray-400 mb-0.5">{label}</p>
              <p className="text-sm font-medium">{value}</p>
            </div>
          ))}
        </div>

        {/* Reasons */}
        {opp.reasons.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Reasons</p>
            <ul className="space-y-1">
              {opp.reasons.map((r, i) => (
                <li key={i} className="text-xs text-gray-300 flex items-start gap-2">
                  <span className="text-profit mt-0.5">✓</span>
                  {r}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Warnings */}
        {opp.warnings.length > 0 && (
          <div className="mb-4">
            <p className="text-xs text-gray-400 uppercase tracking-wider mb-2">Warnings</p>
            <ul className="space-y-1">
              {opp.warnings.map((w, i) => (
                <li key={i} className="text-xs text-yellow-400 flex items-start gap-2">
                  <span className="mt-0.5">⚠</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Placeholders */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="bg-brand-700 rounded-lg p-3">
            <p className="text-xs text-gray-400 mb-0.5">Confidence</p>
            <p className="text-xs text-gray-500 italic">Coming in Sprint 3</p>
          </div>
          <div className="bg-brand-700 rounded-lg p-3">
            <p className="text-xs text-gray-400 mb-0.5">Market Regime</p>
            <p className="text-xs text-gray-500 italic">Coming in Sprint 4</p>
          </div>
        </div>

        <p className="text-xs text-gray-500 text-right">
          Detected {timeAgo(opp.created_at)} · Strategy: {opp.strategy}
        </p>

        <button
          onClick={onClose}
          className="mt-4 w-full py-2 text-sm rounded-lg border border-brand-600 text-gray-400 hover:text-white transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Opportunity Card
// ---------------------------------------------------------------------------

function OpportunityCard({
  opp,
  onAccept,
  onReject,
  onView,
  accepting,
  rejecting,
}: {
  opp: TradeOpportunity
  onAccept: () => void
  onReject: () => void
  onView: () => void
  accepting: boolean
  rejecting: boolean
}) {
  return (
    <div className="bg-brand-800 border border-brand-600 rounded-xl p-5">
      {/* Header row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-base font-bold">{opp.symbol}</span>
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium ${dirBadge(opp.direction)}`}
          >
            {opp.direction.toUpperCase()}
          </span>
          {opp.timeframe && (
            <span className="text-xs text-gray-500 bg-brand-700 px-2 py-0.5 rounded-full">
              {opp.timeframe}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-500">{timeAgo(opp.created_at)}</span>
      </div>

      {/* Price levels */}
      <div className="grid grid-cols-4 gap-2 mb-3">
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Entry</p>
          <p className="text-sm font-medium">${fmt(opp.entry)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Stop Loss</p>
          <p className="text-sm font-medium text-loss">${fmt(opp.stop_loss)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-0.5">Take Profit</p>
          <p className="text-sm font-medium text-profit">${fmt(opp.take_profit)}</p>
        </div>
        <div>
          <p className="text-xs text-gray-400 mb-0.5">R:R</p>
          <p className="text-sm font-medium">{fmt(opp.risk_reward, 1)}R</p>
        </div>
      </div>

      {/* Placeholder badges */}
      <div className="flex gap-2 mb-4">
        <span className="text-xs bg-brand-700 text-gray-500 px-2 py-0.5 rounded-full border border-brand-600">
          Confidence · Coming Sprint 3
        </span>
        <span className="text-xs bg-brand-700 text-gray-500 px-2 py-0.5 rounded-full border border-brand-600">
          Regime · Coming Sprint 4
        </span>
      </div>

      {/* Actions */}
      <div className="flex gap-2">
        <button
          onClick={onAccept}
          disabled={accepting || rejecting}
          className="flex-1 py-2 text-sm rounded-lg bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30 disabled:opacity-50 transition-colors font-medium"
        >
          {accepting ? 'Accepting…' : 'Accept'}
        </button>
        <button
          onClick={onReject}
          disabled={accepting || rejecting}
          className="flex-1 py-2 text-sm rounded-lg bg-loss/20 text-loss border border-loss/30 hover:bg-loss/30 disabled:opacity-50 transition-colors font-medium"
        >
          {rejecting ? 'Rejecting…' : 'Reject'}
        </button>
        <button
          onClick={onView}
          className="px-4 py-2 text-sm rounded-lg bg-brand-700 text-gray-300 hover:bg-brand-600 transition-colors"
        >
          Details
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Section
// ---------------------------------------------------------------------------

export function OpportunitiesSection() {
  const [symbol, setSymbol] = useState('')
  const [detail, setDetail] = useState<TradeOpportunity | null>(null)
  const [actingId, setActingId] = useState<{ id: number; action: 'accept' | 'reject' } | null>(
    null
  )
  const qc = useQueryClient()

  const { data: opportunities = [], isLoading } = useQuery<TradeOpportunity[]>(
    ['opportunities', symbol],
    () => api.getOpportunities(symbol || undefined),
    { refetchInterval: 30_000 }
  )

  const invalidate = () => {
    qc.invalidateQueries('opportunities')
    qc.invalidateQueries('trades')
    qc.invalidateQueries('analytics')
  }

  const accept = useMutation((id: number) => api.acceptOpportunity(id), {
    onMutate: (id) => setActingId({ id, action: 'accept' }),
    onSettled: () => { setActingId(null); invalidate() },
  })

  const reject = useMutation((id: number) => api.rejectOpportunity(id), {
    onMutate: (id) => setActingId({ id, action: 'reject' }),
    onSettled: () => { setActingId(null); invalidate() },
  })

  return (
    <>
      <section>
        <div className="flex items-center gap-4 mb-3">
          <div>
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
              Active Opportunities
            </h2>
            <p className="text-xs text-gray-600 mt-0.5">
              Strategy Engine · ICT Pure OTE
            </p>
          </div>
          <select
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            className="bg-brand-700 border border-brand-600 text-sm rounded-lg px-3 py-1 text-gray-200 focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="">All symbols</option>
            <option value="BTC">BTC</option>
            <option value="ETH">ETH</option>
          </select>
          {opportunities.length > 0 && (
            <span className="ml-auto text-xs bg-accent/20 text-accent px-2 py-0.5 rounded-full border border-accent/30">
              {opportunities.length} active
            </span>
          )}
        </div>

        {isLoading && (
          <div className="text-gray-400 text-sm animate-pulse">Loading opportunities…</div>
        )}

        {!isLoading && opportunities.length === 0 && (
          <div className="text-gray-600 text-sm py-8 text-center border border-dashed border-brand-600 rounded-xl">
            No active opportunities.{' '}
            <span className="text-gray-500">
              Strategy Engine is monitoring the market.
            </span>
          </div>
        )}

        {opportunities.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {opportunities.map(opp => (
              <OpportunityCard
                key={opp.id}
                opp={opp}
                onAccept={() => accept.mutate(opp.id)}
                onReject={() => reject.mutate(opp.id)}
                onView={() => setDetail(opp)}
                accepting={actingId?.id === opp.id && actingId.action === 'accept'}
                rejecting={actingId?.id === opp.id && actingId.action === 'reject'}
              />
            ))}
          </div>
        )}
      </section>

      {detail && <OpportunityDetail opp={detail} onClose={() => setDetail(null)} />}
    </>
  )
}
