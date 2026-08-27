import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { InvoiceBreakdownView } from './InvoiceBreakdownView.jsx'
import { StatementSummary } from './StatementSummary.jsx'
import { StatementDisputePanel } from './StatementDisputePanel.jsx'
import { applyLocalExcludes, formatInr, formatModalHeaderSummary } from './invoiceUtils.js'

export function InvoicePreviewDrawer({ open, month, preview: initialPreview, onClose, onSubmitted }) {
  const [serverPreview, setServerPreview] = useState(initialPreview)
  const [preview, setPreview] = useState(initialPreview)
  const [excludeIds, setExcludeIds] = useState([])
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const refetchPreview = useCallback(async () => {
    if (!month) return
    setRefreshing(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/invoices/preview?month=${encodeURIComponent(month)}`)
      setServerPreview(data)
    } catch (e) {
      setError(e.message || 'Could not refresh preview')
    } finally {
      setRefreshing(false)
    }
  }, [month])

  useEffect(() => {
    if (initialPreview) {
      setServerPreview(initialPreview)
      setExcludeIds([])
      setNotes('')
      setError('')
    }
  }, [initialPreview, open])

  useEffect(() => {
    if (serverPreview) {
      setPreview(applyLocalExcludes(serverPreview, excludeIds))
    }
  }, [serverPreview, excludeIds])

  if (!open || !preview) return null

  const attendanceGist = formatModalHeaderSummary(preview.attendance_summary)
  const pendingCount = preview.pending_approval_count ?? preview.pending_late_count ?? 0

  function handleToggle(_caseId, line) {
    if (!line.session_id) return
    const sid = line.session_id
    setExcludeIds((prev) => (prev.includes(sid) ? prev.filter((id) => id !== sid) : [...prev, sid]))
  }

  async function handleRemoveLate(sessionId) {
    setError('')
    try {
      await apiFetch(`/api/v1/invoices/late-sessions/${sessionId}`, { method: 'DELETE' })
      await refetchPreview()
    } catch (e) {
      setError(e.message || 'Could not remove session')
    }
  }

  async function handleSubmit() {
    setSubmitting(true)
    setError('')
    try {
      const inv = await apiFetch('/api/v1/invoices/submit', {
        method: 'POST',
        body: JSON.stringify({
          month,
          notes: notes.trim() || null,
          edits: excludeIds.length ? { exclude_session_ids: excludeIds } : null,
        }),
      })
      onSubmitted?.(inv)
      onClose()
    } catch (e) {
      setError(e.message || 'Submit failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-[95] flex justify-end bg-slate-900/40 backdrop-blur-[2px]"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-2xl flex-col border-l border-[#E2E8F0] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Invoice preview — {preview.month_label || month}</h2>
            <p className="text-sm text-slate-500">
              {formatInr(preview.net_amount_inr)}
              {attendanceGist ? ` · ${attendanceGist}` : ` · ${preview.total_sessions ?? 0} approved`}
              {pendingCount > 0
                ? ` · ${pendingCount} pending (${formatInr(preview.pending_approval_inr ?? preview.pending_late_inr)})`
                : null}
              {refreshing ? ' · Updating…' : null}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close">
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
          <StatementSummary data={preview} cutover={false} />
          <div className="mt-6">
            <InvoiceBreakdownView
              data={preview}
              editable
              month={month}
              hideSummary
              onToggleSession={handleToggle}
              onRefresh={refetchPreview}
              onRemoveLateSession={handleRemoveLate}
            />
          </div>
          <div className="mt-6">
            <StatementDisputePanel data={preview} month={month} invoiceId={null} />
          </div>
          <label className="mt-6 block text-sm font-medium text-slate-700">
            Notes for finance (optional)
            <textarea
              className="mt-2 w-full rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. One session was rescheduled and logged late"
            />
          </label>
        </div>

        <footer className="flex gap-2 border-t border-[#E2E8F0] px-5 py-4">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] flex-1 rounded-xl border border-[#E2E8F0] bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={submitting || !preview.cases?.length}
            onClick={handleSubmit}
            className="min-h-[44px] flex-1 rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit for review'}
          </button>
        </footer>
      </div>
    </div>
  )
}
