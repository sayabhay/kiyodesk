/**
 * SignalCenter — Live signal dashboard widget.
 *
 * Sits at the top of the dashboard above the Market section.
 * Shows all active signals in a dense table layout with NEW badges,
 * filters, accept/reject/details actions, and a collapsible panel.
 *
 * Consumes useSignals() — does not own its own data fetching.
 */

import { useState } from 'react'
import type { TradeOpportunity } from '../api'
import type { SignalState } from '../signals/useSignals'

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

// ---------------------------------------------------------------------------
// Reusable detail modal (shared with OpportunitiesSection)
// ---------------------------------------------------------------------------

function SignalDetailModal({
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
            {opp.symbol}
            {opp.timeframe ? ` · ${opp.timeframe}` : ''}
            <span className="ml-2 text-sm font-normal text-gray-400">{opp.strategy}</span>
          </h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* Direction + Status */}
        <div className="flex items-center gap-2 mb-4">
          <span
            className={`px-3 py-1 rounded-full text-sm font-semibold ${
              opp.direction === 'long'
                ? 'bg-profit/20 text-profit border border-profit/30'
                : 'bg-loss/20 text-loss border border-loss/30'
            }`}
          >
            {opp.direction.toUpperCase()}
          </span>
          <span className="text-xs text-gray-500 bg-brand-700 px-2 py-1 rounded-full">
            {opp.status}
          </span>
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

        {/* Placeholder badges */}
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
          Detected {timeAgo(opp.created_at)}
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
// Signal row
// ---------------------------------------------------------------------------

function SignalRow({
  opp,
  isNew,
  onAccept,
  onReject,
  onView,
  onMarkSeen,
}: {
  opp: TradeOpportunity
  isNew: boolean
  onAccept: () => void
  onReject: () => void
  onView: () => void
  onMarkSeen: () => void
}) {
  const isLong = opp.direction === 'long'

  return (
    <tr
      className={`border-b border-brand-600 transition-colors ${
        isNew ? 'bg-accent/5 hover:bg-accent/10' : 'hover:bg-brand-700'
      }`}
      onClick={onMarkSeen}
    >
      {/* NEW badge */}
      <td className="px-3 py-3 w-14">
        {isNew ? (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-accent/20 text-accent border border-accent/30 animate-pulse">
            NEW
          </span>
        ) : (
          <span className="text-xs text-gray-600">—</span>
        )}
      </td>

      {/* Symbol */}
      <td className="px-3 py-3">
        <span className="font-bold text-sm">{opp.symbol}</span>
      </td>

      {/* Strategy */}
      <td className="px-3 py-3 hidden lg:table-cell">
        <span className="text-xs text-gray-400">{opp.strategy}</span>
      </td>

      {/* HTF / Timeframe */}
      <td className="px-3 py-3 hidden md:table-cell">
        <span className="text-xs text-gray-400">
          {opp.timeframe ?? '—'}
        </span>
      </td>

      {/* Direction */}
      <td className="px-3 py-3">
        <span
          className={`px-2 py-0.5 rounded-full text-xs font-semibold ${
            isLong
              ? 'bg-profit/20 text-profit border border-profit/30'
              : 'bg-loss/20 text-loss border border-loss/30'
          }`}
        >
          {opp.direction.toUpperCase()}
        </span>
      </td>

      {/* Entry */}
      <td className="px-3 py-3 font-medium text-sm">${fmt(opp.entry)}</td>

      {/* SL */}
      <td className="px-3 py-3 text-loss text-sm hidden sm:table-cell">
        ${fmt(opp.stop_loss)}
      </td>

      {/* TP */}
      <td className="px-3 py-3 text-profit text-sm hidden sm:table-cell">
        ${fmt(opp.take_profit)}
      </td>

      {/* R:R */}
      <td className="px-3 py-3 text-sm text-gray-200">{fmt(opp.risk_reward, 1)}R</td>

      {/* Status */}
      <td className="px-3 py-3 hidden md:table-cell">
        <span className="text-xs text-gray-500 capitalize">{opp.status}</span>
      </td>

      {/* Age */}
      <td className="px-3 py-3 text-xs text-gray-500 hidden lg:table-cell whitespace-nowrap">
        {timeAgo(opp.created_at)}
      </td>

      {/* Actions */}
      <td className="px-3 py-3">
        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={onAccept}
            className="px-2.5 py-1 text-xs rounded-lg bg-profit/20 text-profit border border-profit/30 hover:bg-profit/30 transition-colors font-medium"
          >
            Accept
          </button>
          <button
            onClick={onReject}
            className="px-2.5 py-1 text-xs rounded-lg bg-loss/20 text-loss border border-loss/30 hover:bg-loss/30 transition-colors font-medium"
          >
            Reject
          </button>
          <button
            onClick={onView}
            className="px-2.5 py-1 text-xs rounded-lg bg-brand-700 text-gray-300 hover:bg-brand-600 transition-colors"
          >
            Details
          </button>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main component — receives state from useSignals() passed as props
// ---------------------------------------------------------------------------

export function SignalCenter({ state }: { state: SignalState }) {
  const [detail, setDetail] = useState<TradeOpportunity | null>(null)

  const {
    filteredSignals,
    newSignals,
    newCount,
    isLoading,
    isOpen,
    setIsOpen,
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
  } = state

  const isNewSignal = (opp: TradeOpportunity) =>
    newSignals.some((n) => n.id === opp.id)

  return (
    <>
      <section className="bg-brand-800 border border-brand-600 rounded-xl overflow-hidden">
        {/* ---------------------------------------------------------------- */}
        {/* Header bar                                                        */}
        {/* ---------------------------------------------------------------- */}
        <div
          className="flex items-center gap-3 px-5 py-4 cursor-pointer select-none"
          onClick={() => setIsOpen(!isOpen)}
        >
          {/* Pulse indicator */}
          <div className="relative flex-shrink-0">
            {newCount > 0 ? (
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex rounded-full h-3 w-3 bg-accent" />
              </span>
            ) : (
              <span className="inline-flex rounded-full h-3 w-3 bg-brand-600" />
            )}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-300">
                Signal Center
              </h2>
              {newCount > 0 && (
                <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-accent/20 text-accent border border-accent/30 animate-pulse">
                  {newCount} NEW
                </span>
              )}
              {filteredSignals.length > 0 && newCount === 0 && (
                <span className="text-xs text-gray-500">
                  {filteredSignals.length} active
                </span>
              )}
            </div>
            <p className="text-xs text-gray-600 mt-0.5">
              ICT Pure OTE · Auto-refreshes every 10s
            </p>
          </div>

          {/* Right side controls */}
          <div
            className="flex items-center gap-2 flex-shrink-0"
            onClick={(e) => e.stopPropagation()}
          >
            {newCount > 0 && (
              <button
                onClick={markAllSeen}
                className="text-xs text-gray-400 hover:text-white transition-colors px-2 py-1 rounded bg-brand-700 border border-brand-600"
              >
                Mark all seen
              </button>
            )}
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="text-gray-500 hover:text-gray-300 transition-colors text-lg leading-none w-6 text-center"
            >
              {isOpen ? '−' : '+'}
            </button>
          </div>
        </div>

        {/* ---------------------------------------------------------------- */}
        {/* Collapsible body                                                  */}
        {/* ---------------------------------------------------------------- */}
        {isOpen && (
          <>
            {/* Filter bar */}
            <div className="flex items-center gap-3 px-5 py-2 bg-brand-700 border-t border-b border-brand-600 flex-wrap">
              <span className="text-xs text-gray-500 font-medium">Filter:</span>

              <select
                value={filterSymbol}
                onChange={(e) => setFilterSymbol(e.target.value)}
                className="bg-brand-800 border border-brand-600 text-xs rounded px-2 py-1 text-gray-300 focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="">All symbols</option>
                <option value="BTC">BTC</option>
                <option value="ETH">ETH</option>
              </select>

              <select
                value={filterTimeframe}
                onChange={(e) => setFilterTimeframe(e.target.value)}
                className="bg-brand-800 border border-brand-600 text-xs rounded px-2 py-1 text-gray-300 focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="">All timeframes</option>
                <option value="1m">1m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="1h">1h</option>
                <option value="4h">4h</option>
                <option value="1d">1d</option>
              </select>

              <select
                value={filterStrategy}
                onChange={(e) => setFilterStrategy(e.target.value)}
                className="bg-brand-800 border border-brand-600 text-xs rounded px-2 py-1 text-gray-300 focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="">All strategies</option>
                <option value="ICT Pure OTE">ICT Pure OTE</option>
              </select>

              {(filterSymbol || filterTimeframe || filterStrategy) && (
                <button
                  onClick={() => {
                    setFilterSymbol('')
                    setFilterTimeframe('')
                    setFilterStrategy('')
                  }}
                  className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                >
                  ✕ Clear
                </button>
              )}

              <span className="ml-auto text-xs text-gray-600">
                {filteredSignals.length} signal{filteredSignals.length !== 1 ? 's' : ''}
              </span>
            </div>

            {/* Table / empty state */}
            {isLoading && (
              <div className="px-5 py-8 text-gray-400 text-sm animate-pulse text-center">
                Loading signals…
              </div>
            )}

            {!isLoading && filteredSignals.length === 0 && (
              <div className="px-5 py-10 text-center">
                <p className="text-gray-600 text-sm">No active signals.</p>
                <p className="text-gray-700 text-xs mt-1">
                  Strategy Engine is monitoring the market.
                </p>
              </div>
            )}

            {!isLoading && filteredSignals.length > 0 && (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="text-xs text-gray-500 uppercase tracking-wider border-b border-brand-600">
                      <th className="px-3 py-2 w-14">Status</th>
                      <th className="px-3 py-2">Symbol</th>
                      <th className="px-3 py-2 hidden lg:table-cell">Strategy</th>
                      <th className="px-3 py-2 hidden md:table-cell">TF</th>
                      <th className="px-3 py-2">Dir</th>
                      <th className="px-3 py-2">Entry</th>
                      <th className="px-3 py-2 hidden sm:table-cell">SL</th>
                      <th className="px-3 py-2 hidden sm:table-cell">TP</th>
                      <th className="px-3 py-2">R:R</th>
                      <th className="px-3 py-2 hidden md:table-cell">State</th>
                      <th className="px-3 py-2 hidden lg:table-cell">Age</th>
                      <th className="px-3 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSignals.map((opp) => (
                      <SignalRow
                        key={opp.id}
                        opp={opp}
                        isNew={isNewSignal(opp)}
                        onAccept={() => acceptSignal(opp.id)}
                        onReject={() => dismissSignal(opp.id)}
                        onView={() => {
                          markSeen(opp.id)
                          setDetail(opp)
                        }}
                        onMarkSeen={() => markSeen(opp.id)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </section>

      {detail && <SignalDetailModal opp={detail} onClose={() => setDetail(null)} />}
    </>
  )
}
