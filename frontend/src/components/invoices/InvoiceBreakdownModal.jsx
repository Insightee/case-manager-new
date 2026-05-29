import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { InvoiceBreakdownView } from './InvoiceBreakdownView.jsx'
import { applyLocalExcludes, formatInr, isInvoiceAmendable } from './invoiceUtils.js'

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
      setError(e.message || 'Failed to load breakdown')
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
      setError(e.message || 'Could not save changes')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  const sessionCount = displayData?.sessions_count ?? displayData?.total_sessions ?? 0
  const hasCases = (displayData?.cases || []).some(
    (c) => (c.session_lines?.length || 0) + (c.pending_late_lines?.length || 0) > 0,
  )

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-[2px] sm:items-center"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">{title || 'Invoice breakdown'}</h2>
            {displayData ? (
              <p className="text-sm text-slate-500">
                {displayData.month} · {formatInr(displayData.net_amount_inr ?? displayData.amount_inr)} ·{' '}
                {sessionCount} session{sessionCount === 1 ? '' : 's'}
                {refreshing ? ' · Updating…' : null}
              </p>
            ) : null}
          </div>
          <button type="button" onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" aria-label="Close">
            ×
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading ? <p className="text-sm text-slate-500">Loading…</p> : null}
          {error ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
          {amendable && displayData ? (
            <p className="mb-4 rounded-lg border border-indigo-100 bg-indigo-50/80 px-3 py-2 text-sm text-indigo-950">
              Exclude sessions you did not conduct, add forgotten visits, or remove pending late entries. Changes are
              saved for admin or case manager review before payout.
            </p>
          ) : null}
          {!loading && displayData ? (
            <>
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
          <footer className="flex gap-2 border-t border-[#E2E8F0] px-5 py-4">
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
        ) : null}
      </div>
    </div>
  )
}
