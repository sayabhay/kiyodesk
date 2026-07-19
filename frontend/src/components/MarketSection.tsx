import { useQuery } from 'react-query'
import { api, MarketSnapshot } from '../api'
import { PriceChart } from './PriceChart'

function fmt(value: string | null, decimals = 2): string {
  if (!value) return 'â€”'
  const n = parseFloat(value)
  if (isNaN(n)) return 'â€”'
  return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtPct(value: string | null): string {
  if (!value) return 'â€”'
  const n = parseFloat(value) * 100
  return `${n >= 0 ? '+' : ''}${n.toFixed(4)}%`
}

function MarketCard({ symbol }: { symbol: string }) {
  const { data, isLoading, error, dataUpdatedAt } = useQuery<MarketSnapshot>(
    ['market', symbol],
    () => api.getMarket(symbol),
    { refetchInterval: 60_000 }
  )

  const lastUpdate = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : null

  return (
    <div className="bg-brand-800 border border-brand-600 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold">{symbol}</span>
          {data && (
            <span className="text-xs text-gray-400 bg-brand-700 px-2 py-0.5 rounded-full">
              {data.provider}
            </span>
          )}
        </div>
        {lastUpdate && <span className="text-xs text-gray-500">{lastUpdate}</span>}
      </div>

      {isLoading && <div className="text-gray-400 text-sm animate-pulse">Loading...</div>}
      {!!error && <div className="text-loss text-sm">Failed to load</div>}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Price" value={`$${fmt(data.price)}`} large />
            <Stat label="Funding Rate" value={fmtPct(data.funding_rate)} />
            <Stat
              label="Open Interest"
              value={data.open_interest ? `$${fmt(data.open_interest, 0)}` : 'â€”'}
            />
            <Stat
              label="Liquidations"
              value={data.liquidation_volume ? `$${fmt(data.liquidation_volume, 0)}` : 'â€”'}
            />
          </div>
          <PriceChart symbol={symbol} />
        </>
      )}
    </div>
  )
}

function Stat({ label, value, large }: { label: string; value: string; large?: boolean }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className={large ? 'text-2xl font-bold' : 'text-sm font-medium text-gray-200'}>{value}</p>
    </div>
  )
}

export function MarketSection() {
  return (
    <section>
      <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
        Live Market
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <MarketCard symbol="BTC" />
        <MarketCard symbol="ETH" />
      </div>
    </section>
  )
}
