import { useState } from 'react'
import { useMutation, useQueryClient } from 'react-query'
import { api, Trade } from '../api'

export function CloseTradeModal({ trade, onClose }: { trade: Trade; onClose: () => void }) {
  const [exitPrice, setExitPrice] = useState('')
  const [error, setError] = useState('')
  const qc = useQueryClient()

  const mut = useMutation(
    () => api.closeTrade(trade.id, exitPrice),
    {
      onSuccess: () => {
        qc.invalidateQueries('trades')
        qc.invalidateQueries('analytics')
        onClose()
      },
      onError: (e: Error) => setError(e.message),
    }
  )

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-brand-800 border border-brand-600 rounded-xl p-6 w-full max-w-sm mx-4">
        <h3 className="text-lg font-semibold mb-1">Close Trade #{trade.id}</h3>
        <p className="text-sm text-gray-400 mb-4">
          {trade.symbol} {trade.direction} @ ${parseFloat(trade.entry_price).toLocaleString()}
        </p>
        <label className="block text-xs text-gray-400 mb-1">Exit Price</label>
        <input
          type="number"
          value={exitPrice}
          onChange={e => { setExitPrice(e.target.value); setError('') }}
          placeholder="e.g. 65000"
          className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent mb-4"
        />
        {error && <p className="text-loss text-xs mb-3">{error}</p>}
        <div className="flex gap-3">
          <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-brand-600 text-gray-400 hover:text-white transition-colors">
            Cancel
          </button>
          <button
            onClick={() => mut.mutate()}
            disabled={!exitPrice || mut.isLoading}
            className="flex-1 py-2 text-sm rounded-lg bg-accent font-medium hover:bg-blue-500 disabled:opacity-50 transition-colors"
          >
            {mut.isLoading ? 'Closing…' : 'Confirm Close'}
          </button>
        </div>
      </div>
    </div>
  )
}
