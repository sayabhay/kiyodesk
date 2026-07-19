import { useState } from 'react'
import { useQuery } from 'react-query'
import { api, Analytics } from '../api'

function Metric({ label, value, color }: { label: string; value: string | null; color?: string }) {
  return (
    <div className="bg-brand-800 border border-brand-600 rounded-xl p-4">
      <p className="text-xs text-gray-400 mb-1">{label}</p>
      <p className={`text-xl font-bold ${color ?? 'text-white'}`}>{value ?? '—'}</p>
    </div>
  )
}

function pct(v: string | null) {
  if (!v) return null
  return `${parseFloat(v).toFixed(1)}%`
}

function dec(v: string | null, d = 2) {
  if (!v) return null
  return parseFloat(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

function pnlColor(v: string | null) {
  if (!v) return undefined
  return parseFloat(v) >= 0 ? 'text-profit' : 'text-loss'
}

export function AnalyticsSection() {
  const [symbol, setSymbol] = useState('')
  const { data, isLoading } = useQuery<Analytics>(
    ['analytics', symbol],
    () => api.getAnalytics(symbol || undefined),
    { refetchInterval: 30_000 }
  )

  return (
    <section>
      <div className="flex items-center gap-4 mb-3">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Analytics</h2>
        <select
          value={symbol}
          onChange={e => setSymbol(e.target.value)}
          className="bg-brand-700 border border-brand-600 text-sm rounded-lg px-3 py-1 text-gray-200 focus:outline-none focus:ring-1 focus:ring-accent"
        >
          <option value="">All symbols</option>
          <option value="BTC">BTC</option>
          <option value="ETH">ETH</option>
        </select>
      </div>

      {isLoading && <div className="text-gray-400 text-sm animate-pulse">Loading…</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
            <Metric label="Total Trades" value={String(data.total_trades)} />
            <Metric label="Open" value={String(data.open_trades)} />
            <Metric label="Closed" value={String(data.closed_trades)} />
            <Metric label="Win / Loss" value={`${data.winning_trades}W / ${data.losing_trades}L`} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Metric label="Win Rate" value={pct(data.win_rate)} color={data.win_rate && parseFloat(data.win_rate) >= 50 ? 'text-profit' : 'text-loss'} />
            <Metric label="Profit Factor" value={dec(data.profit_factor)} />
            <Metric label="Expectancy" value={dec(data.expectancy)} color={pnlColor(data.expectancy)} />
            <Metric label="Total P&L" value={dec(data.total_profit_loss)} color={pnlColor(data.total_profit_loss)} />
          </div>
        </>
      )}
    </section>
  )
}
