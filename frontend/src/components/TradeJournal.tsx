import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { api, Trade } from '../api'
import { CloseTradeModal } from './CloseTradeModal'

function badge(status: string) {
  return status === 'open'
    ? 'bg-blue-500/20 text-blue-300'
    : 'bg-gray-500/20 text-gray-400'
}

function dirBadge(dir: string) {
  return dir === 'long'
    ? 'bg-profit/20 text-profit'
    : 'bg-loss/20 text-loss'
}

function fmt(v: string | null) {
  if (!v) return '—'
  return parseFloat(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function pnlClass(v: string | null) {
  if (!v) return 'text-gray-400'
  return parseFloat(v) >= 0 ? 'text-profit' : 'text-loss'
}

export function TradeJournal() {
  const [symbol, setSymbol] = useState('')
  const [closing, setClosing] = useState<Trade | null>(null)
  const qc = useQueryClient()

  const { data: trades = [], isLoading } = useQuery<Trade[]>(
    ['trades', symbol],
    () => api.getTrades(symbol || undefined),
    { refetchInterval: 30_000 }
  )

  const del = useMutation((id: number) => api.deleteTrade(id), {
    onSuccess: () => {
      qc.invalidateQueries('trades')
      qc.invalidateQueries('analytics')
    },
  })

  return (
    <>
      <section>
        <div className="flex items-center gap-4 mb-3">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Trade Journal</h2>
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
        {!isLoading && trades.length === 0 && (
          <div className="text-gray-500 text-sm py-8 text-center border border-brand-600 rounded-xl">
            No trades yet. Click "+ New Trade" to add one.
          </div>
        )}

        {trades.length > 0 && (
          <div className="overflow-x-auto rounded-xl border border-brand-600">
            <table className="w-full text-sm">
              <thead className="bg-brand-700 text-gray-400 text-xs uppercase">
                <tr>
                  {['#','Symbol','Dir','Timeframe','Entry','Exit','P&L','P&L %','Status','Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-brand-600">
                {trades.map(t => (
                  <tr key={t.id} className="bg-brand-800 hover:bg-brand-700 transition-colors">
                    <td className="px-4 py-3 text-gray-400">{t.id}</td>
                    <td className="px-4 py-3 font-medium">{t.symbol}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${dirBadge(t.direction)}`}>{t.direction}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-400">{t.timeframe ?? '—'}</td>
                    <td className="px-4 py-3">${fmt(t.entry_price)}</td>
                    <td className="px-4 py-3">{t.exit_price ? `$${fmt(t.exit_price)}` : '—'}</td>
                    <td className={`px-4 py-3 font-medium ${pnlClass(t.profit_loss)}`}>
                      {t.profit_loss ? (parseFloat(t.profit_loss) >= 0 ? '+' : '') + fmt(t.profit_loss) : '—'}
                    </td>
                    <td className={`px-4 py-3 ${pnlClass(t.profit_loss_pct)}`}>
                      {t.profit_loss_pct ? `${parseFloat(t.profit_loss_pct) >= 0 ? '+' : ''}${parseFloat(t.profit_loss_pct).toFixed(2)}%` : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badge(t.status)}`}>{t.status}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {t.status === 'open' && (
                          <button onClick={() => setClosing(t)} className="text-xs px-2 py-1 bg-accent/20 text-accent rounded hover:bg-accent/40 transition-colors">
                            Close
                          </button>
                        )}
                        <button onClick={() => del.mutate(t.id)} className="text-xs px-2 py-1 bg-loss/20 text-loss rounded hover:bg-loss/40 transition-colors">
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {closing && <CloseTradeModal trade={closing} onClose={() => setClosing(null)} />}
    </>
  )
}
