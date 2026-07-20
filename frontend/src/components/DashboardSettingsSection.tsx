import { useEffect, useState } from 'react'
import { useMutation, useQuery } from 'react-query'
import { api, DashboardSettings } from '../api'

const MODE_OPTIONS = [
  { value: 'live', label: 'Live' },
  { value: 'paper', label: 'Paper' },
]

const TIMEFRAME_OPTIONS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
const SYMBOL_OPTIONS = ['BTC', 'ETH']
const SL_MODE_OPTIONS = [
  { value: 'fixed', label: 'Fixed' },
  { value: 'swing_low', label: 'Swing Low' },
]

function fmtDecimal(value: string | null) {
  return value ?? ''
}

export function DashboardSettingsSection() {
  const { data, isLoading, isError } = useQuery<DashboardSettings>(
    ['settings'],
    () => api.getSettings(),
    { refetchInterval: 30_000 }
  )

  const [form, setForm] = useState<Partial<DashboardSettings>>({})
  const [saved, setSaved] = useState(false)
  const mutation = useMutation((payload: Partial<DashboardSettings>) => api.updateSettings(payload), {
    onSuccess: (updated) => {
      setForm(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  useEffect(() => {
    if (data) {
      setForm(data)
    }
  }, [data])

  const updateField = (field: keyof DashboardSettings, value: string) => {
    setSaved(false)
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const cleanPayload = (): Partial<DashboardSettings> => {
    const payload: Partial<DashboardSettings> = {}

    Object.entries(form).forEach(([key, value]) => {
      if (value === undefined) {
        return
      }

      if (typeof value === 'string' && value.trim() === '') {
        payload[key as keyof DashboardSettings] = null
        return
      }

      if (
        key === 'max_concurrent_trades' && typeof value === 'string'
      ) {
        payload.max_concurrent_trades = value ? Number(value) : null
        return
      }

      payload[key as keyof DashboardSettings] = value as any
    })

    return payload
  }

  const save = () => {
    mutation.mutate(cleanPayload())
  }

  return (
    <section>
      <div className="flex flex-col md:flex-row md:items-end gap-4 mb-3">
        <div>
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
            Dashboard Settings
          </h2>
          <p className="text-xs text-gray-600 mt-0.5">
            Strategy and risk configuration for future trades.
          </p>
        </div>
        <button
          onClick={save}
          disabled={mutation.isLoading || !data}
          className="self-start px-4 py-2 rounded-lg bg-accent text-sm font-semibold text-black hover:bg-blue-400 disabled:opacity-50 transition-colors"
        >
          {mutation.isLoading ? 'Saving…' : 'Save Settings'}
        </button>
        {saved && <span className="text-xs text-green-300">Saved</span>}
      </div>

      {isLoading && <div className="text-gray-400 text-sm animate-pulse">Loading settings…</div>}
      {isError && <div className="text-loss text-sm">Unable to load settings.</div>}

      {data && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-brand-800 border border-brand-600 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Trade filters</h3>
            <label className="text-xs text-gray-400 block">Symbols</label>
            <select
              value={form.symbols ?? ''}
              onChange={(e) => updateField('symbols', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="">All symbols</option>
              {SYMBOL_OPTIONS.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            <label className="text-xs text-gray-400 block">Timeframes</label>
            <select
              value={form.timeframes ?? ''}
              onChange={(e) => updateField('timeframes', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="">All timeframes</option>
              {TIMEFRAME_OPTIONS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>

            <label className="text-xs text-gray-400 block">HTF Mapping JSON</label>
            <textarea
              value={form.htf_mapping_json ?? ''}
              onChange={(e) => updateField('htf_mapping_json', e.target.value)}
              rows={3}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>

          <div className="bg-brand-800 border border-brand-600 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Risk settings</h3>
            <label className="text-xs text-gray-400 block">Risk %</label>
            <input
              type="number"
              value={fmtDecimal(form.risk_percent ?? null)}
              onChange={(e) => updateField('risk_percent', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
            <label className="text-xs text-gray-400 block">Fixed risk</label>
            <input
              type="number"
              value={fmtDecimal(form.fixed_risk ?? null)}
              onChange={(e) => updateField('fixed_risk', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
            <label className="text-xs text-gray-400 block">SL mode</label>
            <select
              value={form.stop_loss_mode ?? ''}
              onChange={(e) => updateField('stop_loss_mode', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="">Default</option>
              {SL_MODE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <label className="text-xs text-gray-400 block">Reward ratio</label>
            <input
              type="number"
              value={fmtDecimal(form.reward_ratio ?? null)}
              onChange={(e) => updateField('reward_ratio', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>

          <div className="bg-brand-800 border border-brand-600 rounded-xl p-5 space-y-4">
            <h3 className="text-sm font-semibold text-white">Execution / risk limits</h3>
            <label className="text-xs text-gray-400 block">Execution mode</label>
            <select
              value={form.execution_mode ?? ''}
              onChange={(e) => updateField('execution_mode', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            >
              <option value="">Default</option>
              {MODE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <label className="text-xs text-gray-400 block">Account balance</label>
            <input
              type="number"
              value={fmtDecimal(form.account_balance ?? null)}
              onChange={(e) => updateField('account_balance', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
            <label className="text-xs text-gray-400 block">Max concurrent trades</label>
            <input
              type="number"
              value={form.max_concurrent_trades ?? ''}
              onChange={(e) => updateField('max_concurrent_trades', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
            <label className="text-xs text-gray-400 block">Max daily loss</label>
            <input
              type="number"
              value={fmtDecimal(form.max_daily_loss ?? null)}
              onChange={(e) => updateField('max_daily_loss', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
            <label className="text-xs text-gray-400 block">Max weekly loss</label>
            <input
              type="number"
              value={fmtDecimal(form.max_weekly_loss ?? null)}
              onChange={(e) => updateField('max_weekly_loss', e.target.value)}
              className="w-full bg-brand-700 border border-brand-600 rounded-lg px-3 py-2 text-sm text-white"
            />
          </div>
        </div>
      )}
    </section>
  )
}
