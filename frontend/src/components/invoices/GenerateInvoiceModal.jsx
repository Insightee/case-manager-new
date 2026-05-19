import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatInr, recentMonthOptions } from './invoiceUtils.js'

export function GenerateInvoiceModal({ open, onClose, onPreviewReady }) {
  const options = recentMonthOptions(6)
  const [selectedId, setSelectedId] = useState(options[0]?.id ?? '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [previewSummary, setPreviewSummary] = useState(null)

  useEffect(() => {
    if (open && options.length) {
      setSelectedId(options[0].id)
      setPreviewSummary(null)
      setError('')
    }
  }, [open])

  useEffect(() => {
    if (!open || !selectedId) return
    let cancelled = false
    setLoading(true)
    setError('')
    apiFetch(`/api/v1/invoices/preview?month=${encodeURIComponent(selectedId)}`)
      .then((data) => {
        if (!cancelled) setPreviewSummary(data)
      })
      .catch((e) => {
        if (!cancelled) {
          setPreviewSummary(null)
          setError(e.message || 'Could not load preview')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, selectedId])

  if (!open) return null

  const selected = options.find((o) => o.id === selectedId) ?? options[0]

  function handleContinue() {
    if (!previewSummary) return
    onPreviewReady?.(selectedId, previewSummary)
  }

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-[2px] sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="gen-inv-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 id="gen-inv-title" className="text-lg font-semibold text-slate-900">
              Generate invoice from logs
            </h2>
            <p className="text-sm text-slate-500">Review sessions by case before you submit</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="space-y-5 p-5">
          <div>
            <label htmlFor="inv-month" className="mb-2 block text-sm font-medium text-slate-700">
              Billing month
            </label>
            <select
              id="inv-month"
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="w-full min-h-[48px] rounded-xl border border-[#E2E8F0] bg-slate-50/80 px-4 py-3 text-base font-medium text-slate-900 outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
            >
              {options.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {loading ? (
            <p className="text-sm text-slate-500">Loading validated sessions…</p>
          ) : error ? (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{error}</p>
          ) : previewSummary ? (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/80 p-4">
              <dl className="grid gap-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="font-medium text-slate-600">Cases</dt>
                  <dd className="font-bold tabular-nums text-slate-900">{previewSummary.cases?.length ?? 0}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="font-medium text-slate-600">Validated sessions</dt>
                  <dd className="font-bold tabular-nums text-slate-900">{previewSummary.total_sessions}</dd>
                </div>
                <div className="flex justify-between gap-4 border-t border-indigo-100 pt-3">
                  <dt className="font-medium text-slate-600">Estimated payout</dt>
                  <dd className="text-lg font-bold tabular-nums text-indigo-900">{formatInr(previewSummary.net_amount_inr)}</dd>
                </div>
              </dl>
              {(previewSummary.leave_deduction_inr ?? 0) > 0 ? (
                <p className="mt-2 text-xs text-rose-700">
                  Includes leave deduction of {formatInr(previewSummary.leave_deduction_inr)}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-slate-500">No billable sessions for {selected?.label}.</p>
          )}

          <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] rounded-xl border border-[#E2E8F0] bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={loading || !previewSummary?.cases?.length}
              onClick={handleContinue}
              className="min-h-[44px] rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              Review breakdown
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
