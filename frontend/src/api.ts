const BASE = '/api/v1'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export interface MarketSnapshot {
  symbol: string
  provider: string
  captured_at: string
  price: string | null
  funding_rate: string | null
  open_interest: string | null
  liquidation_volume: string | null
  long_liquidation_volume: string | null
  short_liquidation_volume: string | null
}

export interface MarketHistoryPoint {
  captured_at: string
  price: string | null
  funding_rate: string | null
  open_interest: string | null
  liquidation_volume: string | null
  provider: string
}

export interface MarketHistoryResponse {
  symbol: string
  points: MarketHistoryPoint[]
  total: number
}

export interface Trade {
  id: number
  symbol: string
  direction: 'long' | 'short'
  entry_price: string
  stop_loss: string | null
  take_profit: string | null
  exit_price: string | null
  status: string
  profit_loss: string | null
  profit_loss_pct: string | null
  timeframe: string | null
  notes: string | null
  strategy_version: string | null
  created_at: string
  closed_at: string | null
}

export interface Analytics {
  total_trades: number
  open_trades: number
  closed_trades: number
  winning_trades: number
  losing_trades: number
  breakeven_trades: number
  win_rate: string | null
  profit_factor: string | null
  expectancy: string | null
  total_profit_loss: string | null
  average_win: string | null
  average_loss: string | null
  largest_win: string | null
  largest_loss: string | null
}

export interface CreateTradePayload {
  symbol: string
  direction: 'long' | 'short'
  entry_price: string
  stop_loss?: string
  take_profit?: string
  timeframe?: string
  notes?: string
  strategy_version?: string
}

export interface TradeOpportunity {
  id: number
  strategy: string
  strategy_version: string | null
  symbol: string
  timeframe: string | null
  direction: 'long' | 'short'
  entry: string
  stop_loss: string
  take_profit: string
  risk_reward: string
  status: string
  created_at: string
  updated_at: string
  expires_at: string | null
  taken_at: string | null
  invalidated_at: string | null
  trade_id: number | null
  confidence: string | null   // null → "Coming in Sprint 3"
  market_regime: string | null // null → "Coming in Sprint 4"
  reasons: string[]
  warnings: string[]
  trade_setup_json: string
}

export const api = {
  getMarket: (symbol: string) =>
    request<MarketSnapshot>(`/market/${symbol}`),

  getMarketHistory: (symbol: string, limit = 100) =>
    request<MarketHistoryResponse>(`/market/${symbol}/history?limit=${limit}`),

  getTrades: (symbol?: string) =>
    request<Trade[]>(`/trades${symbol ? `?symbol=${symbol}` : ''}`),

  createTrade: (payload: CreateTradePayload) =>
    request<Trade>('/trades', { method: 'POST', body: JSON.stringify(payload) }),

  closeTrade: (id: number, exit_price: string) =>
    request<Trade>(`/trades/${id}/close`, {
      method: 'PATCH',
      body: JSON.stringify({ exit_price }),
    }),

  deleteTrade: (id: number) =>
    request<void>(`/trades/${id}`, { method: 'DELETE' }),

  getAnalytics: (symbol?: string) =>
    request<Analytics>(`/analytics${symbol ? `?symbol=${symbol}` : ''}`),

  getOpportunities: (symbol?: string) =>
    request<TradeOpportunity[]>(`/opportunities/active${symbol ? `?symbol=${symbol}` : ''}`),

  acceptOpportunity: (id: number) =>
    request<TradeOpportunity>(`/opportunities/${id}/accept`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  rejectOpportunity: (id: number) =>
    request<TradeOpportunity>(`/opportunities/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),

  getRecentSignals: (since?: string, symbol?: string) => {
    const params = new URLSearchParams()
    if (since) params.set('since', since)
    if (symbol) params.set('symbol', symbol)
    const qs = params.toString()
    return request<TradeOpportunity[]>(`/opportunities/recent${qs ? `?${qs}` : ''}`)
  },
}
