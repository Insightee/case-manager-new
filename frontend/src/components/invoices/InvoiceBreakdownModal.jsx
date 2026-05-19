import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { InvoiceBreakdownView } from './InvoiceBreakdownView.jsx'
import { formatInr } from './invoiceUtils.js'

export function InvoiceBreakdownModal({ invoiceId, title, open, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !invoiceId) return
    let cancelled = false
    setLoading(true)
    setError('')
    apiFetch(`/api/v1/invoices/${invoiceId}/breakdown`)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e) => {
        if (!cancelled) {
          setData(null)
          setError(e.message || 'Failed to load breakdown')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, invoiceId])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-[2px] sm:items-center"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{title || 'Invoice breakdown'}</h2>
            {data ? (
              <p className="text-sm text-slate-500">
                {data.month} · {formatInr(data.amount_inr)} · {data.sessions_count} sessions
              </p>
            ) : null}
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close">
            ×
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          {!loading && data ? <InvoiceBreakdownView data={data} /> : null}
        </div>
      </div>
    </div>
  )
}
