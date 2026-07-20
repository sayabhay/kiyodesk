import { QueryClient, QueryClientProvider } from 'react-query'
import { SignalCenter } from './components/SignalCenter'
import { SignalToast } from './components/SignalToast'
import { MarketSection } from './components/MarketSection'
import { OpportunitiesSection } from './components/OpportunitiesSection'
import { TradeJournal } from './components/TradeJournal'
import { AnalyticsSection } from './components/AnalyticsSection'
import { DashboardSettingsSection } from './components/DashboardSettingsSection'
import { NewTradeModal } from './components/NewTradeModal'
import { useSignals } from './signals/useSignals'
import { useState } from 'react'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

function AppContent() {
  const [showNewTrade, setShowNewTrade] = useState(false)
  const signalState = useSignals()

  return (
    <div className="min-h-screen bg-brand-900">
      {/* Header */}
      <header className="border-b border-brand-600 bg-brand-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div>
            <h1 className="text-xl font-bold tracking-tight">KiyoDesk</h1>
            <p className="text-xs text-gray-400 mt-0.5">Local-first crypto intelligence</p>
          </div>
          {/* Header signal badge */}
          {signalState.newCount > 0 && (
            <button
              onClick={() => {
                signalState.setIsOpen(true)
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
              className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-accent/20 text-accent border border-accent/30 text-xs font-semibold hover:bg-accent/30 transition-colors"
            >
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-accent" />
              </span>
              {signalState.newCount} new signal{signalState.newCount !== 1 ? 's' : ''}
            </button>
          )}
        </div>
        <button
          onClick={() => setShowNewTrade(true)}
          className="px-4 py-2 bg-accent rounded-lg text-sm font-medium hover:bg-blue-500 transition-colors"
        >
          + New Trade
        </button>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6 space-y-8">
        {/* Signal Center — top of page, full-width */}
        <SignalCenter state={signalState} />

        <MarketSection />
        <DashboardSettingsSection />
        <OpportunitiesSection />
        <AnalyticsSection />
        <TradeJournal />
      </main>

      {/* Floating toast — outside main, fixed positioned */}
      <SignalToast />

      {showNewTrade && <NewTradeModal onClose={() => setShowNewTrade(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}
