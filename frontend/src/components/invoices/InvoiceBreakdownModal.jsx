import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { BillingCalcErrorNotice } from '../shared/BillingCalcErrorNotice.jsx'
import { InvoiceBreakdownView } from './InvoiceBreakdownView.jsx'
import { applyLocalExcludes, formatInr, formatModalHeaderSummary, isInvoiceAmendable } from './invoiceUtils.js'

export function InvoiceBreakdownModal({
  invoiceId,
  invoiceStatus,
  title,
  open,
  onClose,
  onAmended,
}) {
  const [serverData, setServerData] = useState(null)
  const [excludeIds, setExcludeIds] = useState([])
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const amendable = isInvoiceAmendable(invoiceStatus)

  const loadBreakdown = useCallback(async () => {
    if (!invoiceId) return
    setLoading(true)
    setError('')
    try {
      const d = await apiFetch(`/api/v1/invoices/${invoiceId}/breakdown`)
      setServerData(d)
      setNotes(d?.notes || '')
      setExcludeIds([])
    } catch (e) {
      setServerData(null)
      setError(e)
    } finally {
      setLoading(false)
    }
  }, [invoiceId])

  useEffect(() => {
    if (!open || !invoiceId) return
    void loadBreakdown()
  }, [open, invoiceId, loadBreakdown])

  const displayData = useMemo(() => {
    if (!serverData) return null
    if (!amendable) return serverData
    return applyLocalExcludes(serverData, excludeIds)
  }, [serverData, excludeIds, amendable])

  const refetchBreakdown = useCallback(async () => {
    setRefreshing(true)
    setError('')
    try {
      await loadBreakdown()
    } finally {
      setRefreshing(false)
    }
  }, [loadBreakdown])

  function handleToggle(_caseId, line) {
    if (!line.session_id) return
    const sid = line.session_id
    setExcludeIds((prev) => (prev.includes(sid) ? prev.filter((id) => id !== sid) : [...prev, sid]))
  }

  async function handleRemoveLate(sessionId) {
    setError('')
    try {
      await apiFetch(`/api/v1/invoices/late-sessions/${sessionId}`, { method: 'DELETE' })
      await refetchBreakdown()
    } catch (e) {
      setError(e.message || 'Could not remove session')
    }
  }

  async function handleSaveAmendments() {
    if (!invoiceId) return
    setSaving(true)
    setError('')
    try {
      await apiFetch(`/api/v1/invoices/${invoiceId}/amend`, {
        method: 'POST',
        body: JSON.stringify({
          notes: notes.trim() || null,
          edits: excludeIds.length ? { exclude_session_ids: excludeIds } : null,
        }),
      })
      onAmended?.()
      onClose()
    } catch (e) {
      setError(e)
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const sessionCount = displayData?.sessions_count ?? displayData?.total_sessions ?? 0
  const attendanceGist = formatModalHeaderSummary(displayData?.attendance_summary)
  const hasSessionLines = (displayData?.cases || []).some(
    (c) =>
      (c.session_lines?.length || 0) +
        (c.pending_approval_lines?.length || c.pending_late_lines?.length || 0) +
        (c.child_absence_lines?.length || 0) >
      0,
  )
  const hasCaseTotals = (displayData?.cases || []).some((c) => (c.therapist_share_inr ?? 0) > 0)
  const hasCases = hasSessionLines || hasCaseTotals
  const snapshotIncomplete = Boolean(displayData?.snapshot_incomplete || displayData?.from_stored_header)

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[96dvh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-[#E2E8F0] bg-white shadow-2xl sm:max-h-[92vh] sm:rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-[#E2E8F0] px-4 py-4 sm:px-5">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-slate-900">{title || 'Invoice breakdown'}</h2>
            {displayData ? (
              <p className="mt-1 text-sm leading-snug text-slate-500">
                {displayData.month} · {formatInr(displayData.net_amount_inr ?? displayData.amount_inr)}
                {attendanceGist ? ` · ${attendanceGist}` : ` · ${sessionCount} session${sessionCount === 1 ? '' : 's'}`}
                {refreshing ? ' · Updating…' : null}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] min-w-[44px] shrink-0 rounded-lg p-2 text-slate-500 hover:bg-slate-100"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5">
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
          {error ? (
            <BillingCalcErrorNotice error={error} audience="therapist" className="mb-3" tone="error" />
          ) : null}
          {amendable && displayData ? (
            <p className="mb-4 rounded-lg border border-indigo-100 bg-indigo-50/80 px-3 py-2 text-sm text-indigo-950">
              Exclude sessions you did not conduct, add forgotten visits, or remove pending late entries. Changes are
              saved for admin or case manager review before payout.
            </p>
          ) : null}
          {!loading && displayData ? (
            <>
              {!hasSessionLines && hasCaseTotals ? (
                <p className="mb-4 text-sm text-amber-800">
                  {snapshotIncomplete
                    ? 'Session line detail is not stored for this payout — case totals below match the approved statement.'
                    : 'Case totals are shown below; individual session lines are not on file for this invoice.'}
                </p>
              ) : null}
              {!hasCases ? (
                <p className="mb-4 text-sm text-amber-800">
                  No session lines found for this invoice. Add approved logs for the month or use Generate Invoice to
                  rebuild.
                </p>
              ) : null}
              <InvoiceBreakdownView
                data={displayData}
                editable={amendable}
                month={displayData.month}
                onToggleSession={amendable ? handleToggle : undefined}
                onRefresh={amendable ? refetchBreakdown : undefined}
                onRemoveLateSession={amendable ? handleRemoveLate : undefined}
              />
              {amendable ? (
                <label className="mt-6 block text-sm font-medium text-slate-700">
                  Notes for finance (optional)
                  <textarea
                    className="mt-2 w-full rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm"
                    rows={2}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    placeholder="Explain exclusions or late additions"
                  />
                </label>
              ) : null}
            </>
          ) : null}
        </div>

        {amendable && displayData ? (
          <footer className="flex shrink-0 gap-2 border-t border-[#E2E8F0] px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] flex-1 rounded-xl border border-[#E2E8F0] bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              Close
            </button>
            <button
              type="button"
              disabled={saving || !hasCases}
              onClick={handleSaveAmendments}
              className="min-h-[44px] flex-1 rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save for review'}
            </button>
          </footer>
        ) : displayData && !loading ? (
          <footer className="shrink-0 border-t border-[#E2E8F0] px-4 py-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:px-5">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] w-full rounded-xl bg-indigo-600 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Done
            </button>
          </footer>
        ) : null}
      </div>
    </div>
  )
}
