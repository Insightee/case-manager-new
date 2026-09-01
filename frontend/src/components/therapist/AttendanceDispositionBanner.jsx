import { Link } from 'react-router-dom'

/**
 * Soft banner when past sessions still need a disposition (log / child absence / leave).
 * Connection-before-correction copy — never "invalid" / "failed".
 * Invoice submit is allowed; new leave may still be gated until these days are resolved.
 */
export function AttendanceDispositionBanner({ count, days = [], compact = false, context = 'general' }) {
  if (!count) return null
  const sample = (days || []).slice(0, 3)
  const onInvoice = context === 'invoice'
  return (
    <div
      role="status"
      className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 shadow-sm"
    >
      <p className="font-semibold">
        {count} day{count === 1 ? '' : 's'} still need a session log, child absence, or leave
      </p>
      {!compact ? (
        <p className="mt-1 text-amber-900/90">
          {onInvoice
            ? 'You can add a session for those days below (awaits review and stays out of this pay until approved), or submit this invoice now and finish them later. A new leave request may still need these days resolved first.'
            : 'Add a session from the invoice for that day, file a child absence, or request leave. You can still submit the month’s invoice while these are pending review — they simply won’t be in this pay yet. New leave requests need these days resolved first.'}
        </p>
      ) : (
        <p className="mt-1 text-xs text-amber-900/90">
          Add a session against each day below, or submit anyway — pending items stay out of this pay.
        </p>
      )}
      {sample.length ? (
        <ul className="mt-2 list-inside list-disc text-xs text-amber-900/80">
          {sample.map((d) => (
            <li key={`${d.case_id}-${d.date}-${d.session_id}`}>
              {d.case_code || `Case ${d.case_id}`}
              {d.child_name ? ` · ${d.child_name}` : ''} · {d.date}
            </li>
          ))}
          {count > sample.length ? <li>+{count - sample.length} more</li> : null}
        </ul>
      ) : null}
      {!onInvoice ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to="/therapist/invoices"
            className="inline-flex min-h-[40px] items-center rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800"
          >
            Open invoices to add a session
          </Link>
          <Link
            to="/therapist/logs"
            className="inline-flex min-h-[40px] items-center rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
          >
            Open session logs
          </Link>
          <Link
            to="/therapist/leave"
            className="inline-flex min-h-[40px] items-center rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
          >
            Request leave
          </Link>
        </div>
      ) : null}
    </div>
  )
}
