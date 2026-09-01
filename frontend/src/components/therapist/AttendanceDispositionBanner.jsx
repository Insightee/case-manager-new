import { Link } from 'react-router-dom'

/**
 * Soft banner when past sessions still need a disposition (log / child absence / leave).
 * Connection-before-correction copy — never "invalid" / "failed".
 */
export function AttendanceDispositionBanner({ count, days = [], compact = false }) {
  if (!count) return null
  const sample = (days || []).slice(0, 3)
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
          Looks like we still need a few details before a new leave or this month&apos;s invoice can
          move forward. Would you like to continue from where you left off?
        </p>
      ) : null}
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
      <div className="mt-3 flex flex-wrap gap-2">
        <Link
          to="/therapist/logs"
          className="inline-flex min-h-[40px] items-center rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800"
        >
          Open session logs
        </Link>
        <Link
          to="/therapist/leave"
          className="inline-flex min-h-[40px] items-center rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
        >
          Request leave
        </Link>
        <Link
          to="/therapist/invoices"
          className="inline-flex min-h-[40px] items-center rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
        >
          Review invoices
        </Link>
      </div>
    </div>
  )
}
