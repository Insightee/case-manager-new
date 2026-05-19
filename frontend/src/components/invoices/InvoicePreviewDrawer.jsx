import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { InvoiceBreakdownView } from './InvoiceBreakdownView.jsx'
import { formatInr } from './invoiceUtils.js'

function applyLocalExcludes(preview, excludeIds) {
  if (!preview) return preview
  const exclude = new Set(excludeIds)
  const next = structuredClone(preview)
  let subtotal = 0
  let totalSessions = 0
  for (const cg of next.cases || []) {
    let caseTotal = 0
    let included = 0
    let additional = 0
    for (const line of cg.session_lines || []) {
      if (line.session_id && exclude.has(line.session_id)) {
        line.included = false
      }
      if (line.included !== false) {
        caseTotal += line.amount_inr || 0
        totalSessions += 1
        if (line.line_type === 'ADDITIONAL') additional += 1
        else if (line.line_type === 'INCLUDED') included += 1
      }
    }
    cg.therapist_share_inr = Math.round(caseTotal * 100) / 100
    cg.included_sessions = included
    cg.additional_sessions = additional
    if (cg.billing?.billing_type === 'PER_SESSION' || cg.billing_snapshot?.billing_type === 'PER_SESSION') {
      cg.display_included_sessions = cg.session_lines?.filter((l) => l.included !== false).length ?? 0
    }
    subtotal += cg.therapist_share_inr
  }
  next.subtotal_inr = Math.round(subtotal * 100) / 100
  next.total_sessions = totalSessions
  next.net_amount_inr = Math.max(next.subtotal_inr - (next.leave_deduction_inr || 0), 0)
  return next
}

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

  const pendingCount = preview.pending_late_count ?? 0

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
              {preview.total_sessions} approved sessions · {formatInr(preview.net_amount_inr)}
              {refreshing ? ' · Updating…' : null}
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close">
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
          {pendingCount > 0 ? (
            <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {pendingCount} late-added session{pendingCount === 1 ? '' : 's'} ({formatInr(preview.pending_late_inr)}) are
              excluded from payout until an admin approves the daily logs.
            </p>
          ) : null}
          <InvoiceBreakdownView
            data={preview}
            editable
            month={month}
            onToggleSession={handleToggle}
            onRefresh={refetchPreview}
            onRemoveLateSession={handleRemoveLate}
          />
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
