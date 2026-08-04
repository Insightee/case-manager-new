import { useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { formatInr } from './invoiceUtils.js'

// Why the dispute is raised. Values are stored as reason_code (<=64 chars); the
// backend keeps them opaque so finance sees the category alongside the note.
const REASON_OPTIONS = [
  { value: 'cancelled_session', label: 'Cancelled session' },
  { value: 'extra_hours', label: 'Extra hours session' },
  { value: 'wrongly_marked', label: 'Wrongly marked' },
  { value: 'other', label: 'Other' },
]

function flattenSessions(data) {
  const out = []
  const seen = new Set()
  for (const c of data?.cases || []) {
    // Payout lines plus pending late entries — anything the therapist can point at.
    for (const line of [...(c.session_lines || []), ...(c.pending_late_lines || [])]) {
      if (line.session_id && !seen.has(line.session_id)) {
        seen.add(line.session_id)
        out.push({
          session_id: line.session_id,
          case_code: c.case_code,
          child_name: c.child_name,
          session_date: line.session_date,
          amount_inr: line.amount_inr,
        })
      }
    }
  }
  return out
}

/**
 * Therapist raises a dispute on their own statement: mark specific sessions +
 * a required comment. It posts session ids and text only — never an amount —
 * and the record is what the finance statement queue reads. No money is edited
 * anywhere in this flow.
 */
export function StatementDisputePanel({ data, month, invoiceId = null, onSubmitted }) {
  const sessions = useMemo(() => flattenSessions(data), [data])
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [submitted, setSubmitted] = useState(null)

  function toggle(sessionId) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(sessionId)) next.delete(sessionId)
      else next.add(sessionId)
      return next
    })
  }

  async function handleSubmit() {
    if (!reason) {
      setError('Pick a reason so finance knows what kind of correction this is.')
      return
    }
    if (!comment.trim()) {
      setError('Please add a short comment so finance knows what to look at.')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const record = await apiFetch('/api/v1/invoices/statement/disputes', {
        method: 'POST',
        body: JSON.stringify({
          month,
          invoice_id: invoiceId,
          comment: comment.trim(),
          reason_code: reason,
          session_ids: [...selected],
        }),
      })
      setSubmitted(record)
      onSubmitted?.(record)
    } catch (e) {
      setError(e.message || 'Could not submit the dispute')
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <p className="text-sm font-semibold text-amber-900">Dispute submitted — under review</p>
        <p className="mt-1 text-xs text-amber-800">
          Finance can see your note{submitted.disputed_session_ids?.length
            ? ` and the ${submitted.disputed_session_ids.length} flagged session${
                submitted.disputed_session_ids.length === 1 ? '' : 's'
              }`
            : ''}. Nothing on your statement changes while it’s reviewed.
        </p>
        <p className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-xs text-slate-700">“{submitted.comment}”</p>
      </section>
    )
  }

  return (
    <section className="rounded-xl border border-[#E2E8F0] bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-800">Something look off?</h3>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="min-h-[36px] rounded-lg border border-[#E2E8F0] px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
        >
          {open ? 'Close' : 'Dispute a line'}
        </button>
      </div>

      {open ? (
        <div className="mt-3 space-y-3">
          {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

          <label className="block text-sm font-medium text-slate-700">
            Reason
            <select
              className="mt-1 min-h-[44px] w-full rounded-xl border border-[#E2E8F0] px-3 text-sm"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            >
              <option value="">Choose a reason…</option>
              {REASON_OPTIONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          {sessions.length ? (
            <div>
              <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Pick the session this is about</p>
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {sessions.map((s) => (
                  <li key={s.session_id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4"
                        checked={selected.has(s.session_id)}
                        onChange={() => toggle(s.session_id)}
                      />
                      <span className="flex-1 text-slate-700">
                        {formatDisplayDate(s.session_date)} · {s.case_code}
                        {s.child_name ? ` · ${s.child_name}` : ''}
                      </span>
                      <span className="tabular-nums text-slate-500">{formatInr(s.amount_inr)}</span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">
              No individual payout sessions to pick this month — just tell finance what looks off below.
            </p>
          )}

          <label className="block text-sm font-medium text-slate-700">
            What’s the concern?
            <textarea
              className="mt-1 w-full rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm"
              rows={3}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="e.g. The session on the 12th was cancelled but appears in my payout."
            />
          </label>

          <p className="text-xs text-slate-500">
            You can’t change any amounts here — this just flags the statement for finance to review.
          </p>

          <button
            type="button"
            disabled={submitting}
            onClick={handleSubmit}
            className="min-h-[44px] w-full rounded-xl bg-amber-600 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {submitting ? 'Submitting…' : 'Submit dispute'}
          </button>
        </div>
      ) : null}
    </section>
  )
}
