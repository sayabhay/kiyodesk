import { useQuery } from 'react-query'
import ReactECharts from 'echarts-for-react'
import { api, MarketHistoryPoint } from '../api'

interface ChartPoint {
  time: string
  price: number
  oi: number | null
}

function buildPoints(points: MarketHistoryPoint[]): ChartPoint[] {
  return points.map(p => ({
    time: new Date(p.captured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    price: p.price ? parseFloat(p.price) : 0,
    oi: p.open_interest ? parseFloat(p.open_interest) : null,
  }))
}

function buildOption(points: ChartPoint[], symbol: string) {
  const times = points.map(p => p.time)
  const prices = points.map(p => p.price)
  const ois = points.map(p => p.oi)
  const hasOi = ois.some(v => v !== null)
  const validPrices = prices.filter(p => p > 0)
  const minPrice = validPrices.length ? Math.min(...validPrices) * 0.9995 : 0
  const maxPrice = validPrices.length ? Math.max(...validPrices) * 1.0005 : 1

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#111827',
      borderColor: '#1e2d40',
      borderWidth: 1,
      textStyle: { color: '#e5e7eb', fontSize: 11 },
      axisPointer: { type: 'cross', lineStyle: { color: '#374151' } },
    },
    legend: {
      show: hasOi, top: 0, right: 0,
      textStyle: { color: '#6b7280', fontSize: 10 },
      itemWidth: 10, itemHeight: 10,
    },
    grid: [
      { left: 68, right: 12, top: hasOi ? 28 : 8, bottom: hasOi ? '38%' : 28 },
      ...(hasOi ? [{ left: 68, right: 12, top: '66%', bottom: 28 }] : []),
    ],
    xAxis: [
      {
        type: 'category', data: times, gridIndex: 0,
        axisLabel: { show: !hasOi, color: '#6b7280', fontSize: 10 },
        axisLine: { lineStyle: { color: '#1e2d40' } },
        axisTick: { show: false }, splitLine: { show: false },
      },
      ...(hasOi ? [{ type: 'category', data: times, gridIndex: 1, axisLabel: { color: '#6b7280', fontSize: 10 }, axisLine: { lineStyle: { color: '#1e2d40' } }, axisTick: { show: false }, splitLine: { show: false } }] : []),
    ],
    yAxis: [
      {
        type: 'value', name: `${symbol} Price`, gridIndex: 0,
        min: minPrice, max: maxPrice,
        nameTextStyle: { color: '#6b7280', fontSize: 9 },
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => `$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}` },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: '#1a2235' } },
      },
      ...(hasOi ? [{
        type: 'value', name: 'Open Interest', gridIndex: 1,
        nameTextStyle: { color: '#6b7280', fontSize: 9 },
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v: number) => v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : `$${(v / 1e6).toFixed(0)}M` },
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: '#1a2235' } },
      }] : []),
    ],
    series: [
      {
        name: 'Price', type: 'line', data: prices,
        xAxisIndex: 0, yAxisIndex: 0,
        smooth: true, symbol: 'none',
        lineStyle: { color: '#3b82f6', width: 1.5 },
        areaStyle: {
          color: {
            type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(59,130,246,0.25)' },
              { offset: 1, color: 'rgba(59,130,246,0)' },
            ],
          },
        },
      },
      ...(hasOi ? [{ name: 'Open Interest', type: 'bar', data: ois, xAxisIndex: 1, yAxisIndex: 1, barMaxWidth: 6, itemStyle: { color: 'rgba(168,85,247,0.6)' } }] : []),
    ],
  }
}

export function PriceChart({ symbol }: { symbol: string }) {
  const { data, isLoading } = useQuery(
    ['market-history', symbol],
    () => api.getMarketHistory(symbol, 100),
    { refetchInterval: 60_000 }
  )

  if (isLoading) {
    return (
      <div className="h-44 flex items-center justify-center text-gray-500 text-xs animate-pulse mt-4">
        Loading chart...
      </div>
    )
  }

  if (!data || data.points.length < 2) {
    return (
      <div className="h-16 flex items-center justify-center text-gray-600 text-xs border border-dashed border-brand-600 rounded-lg mt-4">
        Chart fills as the scheduler collects data every 60 s
      </div>
    )
  }

  const points = buildPoints(data.points)
  const hasOi = points.some(p => p.oi !== null)

  return (
    <div className="mt-4">
      <p className="text-xs text-gray-600 mb-1">
        {data.total} stored Â· last {data.points.length} shown
      </p>
      <ReactECharts
        option={buildOption(points, symbol)}
        style={{ height: hasOi ? 220 : 160, width: '100%' }}
        opts={{ renderer: 'svg' }}
      />
    </div>
  )
}
