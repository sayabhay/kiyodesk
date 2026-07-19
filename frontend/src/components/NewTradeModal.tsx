import { useState } from 'react'
import { useMutation, useQueryClient } from 'react-query'
import { api, CreateTradePayload } from '../api'

const SYMBOLS = ['BTC', 'ETH']
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']

export function NewTradeModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState<CreateTradePayload>({
    symbol: 'BTC',
    direction: 'long',
    entry_price: '',
    stop_loss: '',
    take_profit: '',
    timeframe: '1h',
    notes: '',
    strategy_version: 'v1',
  })
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const set = (k: keyof CreateTradePayload, v: string) =>
    setForm(f => ({ ...f, [k]: v }))

  const mut = useMutation(
    () => api.createTrade({
      ...form,
      stop_loss: form.stop_loss || undefined,
      take_profit: form.take_profit || undefined,
      notes: form.notes || undefined,
    }),
    {
      onSuccess: () => {
        qc.invalidateQueries('trades')
        qc.invalidateQueries('analytics')
        onClose()
      },
      onError: (e: Error) => setError(e.message),
    }
  )

  const field = (label: string, key: keyof CreateTradePayload, type = 'text', placeholder = '') => (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      <input
        type={type}
        value={form[key] as string}
        onChange={e => set(key, e.target.value)}
        placeholder={placeholder}
        className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent"
      />
    </div>
  )

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 overflow-y-auto py-8">
      <div className="bg-brand-800 border border-brand-600 rounded-xl p-6 w-full max-w-md mx-4">
        <h3 className="text-lg font-semibold mb-4">New Trade</h3>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-400 mb-1">Symbol</label>
              <select value={form.symbol} onChange={e => set('symbol', e.target.value)}
                className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent">
                {SYMBOLS.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1">Direction</label>
              <select value={form.direction} onChange={e => set('direction', e.target.value as 'long' | 'short')}
                className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent">
                <option value="long">Long</option>
                <option value="short">Short</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs text-gray-400 mb-1">Timeframe</label>
            <select value={form.timeframe} onChange={e => set('timeframe', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent">
              {TIMEFRAMES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          {field('Entry Price *', 'entry_price', 'number', '63000')}
          <div className="grid grid-cols-2 gap-3">
            {field('Stop Loss', 'stop_loss', 'number', '62000')}
            {field('Take Profit', 'take_profit', 'number', '65000')}
          </div>
          {field('Strategy Version', 'strategy_version', 'text', 'v1')}

          <div>
            <label className="block text-xs text-gray-400 mb-1">Notes</label>
            <textarea value={form.notes} onChange={e => set('notes', e.target.value)}
              rows={2} placeholder="Optional trade notes…"
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent resize-none" />
          </div>
        </div>

        {error && <p className="text-loss text-xs mt-3">{error}</p>}

        <div className="flex gap-3 mt-4">
          <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-brand-600 text-gray-400 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={!form.entry_price || mut.isLoading}
            className="flex-1 py-2 text-sm rounded-lg bg-accent font-medium hover:bg-blue-500 disabled:opacity-50 transition-colors"
          >
            {mut.isLoading ? 'Saving…' : 'Record Trade'}
          </button>
        </div>
      </div>
    </div>
  )
}
