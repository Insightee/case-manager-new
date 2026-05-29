import {
  actualDurationMinsIST,
  formatSessionActualRange,
  formatTimeIST,
  isStartedLateOnSchedule,
} from '../../lib/datetime.js'

function formatScheduledTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

/**
 * Summary shown immediately after ending a visit, before the therapist submits the log.
 */
export function SessionBrief({ session, childName, caseCode }) {
  if (!session) return null

  const display = childName || session.child_name || caseCode || session.case_code || 'Client'
  const code = caseCode || session.case_code
  const actualRange = formatSessionActualRange(session)
  const duration = actualDurationMinsIST(session.actual_start_at, session.actual_end_at)
  const scheduledLine =
    session.scheduled_date && (session.start_time || session.end_time)
      ? `${session.scheduled_date} · ${formatScheduledTime(session.start_time)}–${formatScheduledTime(session.end_time)}`
      : session.scheduled_date || null
  const startedLate = isStartedLateOnSchedule(
    session.actual_start_at,
    session.scheduled_date,
    session.start_time,
  )
  const logPending = session.status === 'COMPLETED' && !session.has_daily_log

  return (
    <section className="ic-session-brief" aria-label="Session summary">
      <p className="ic-session-brief__eyebrow">Session ended</p>
      <h3 className="ic-session-brief__title">{display}</h3>
      {code ? <p className="ic-session-brief__code">{code}</p> : null}
      <dl className="ic-session-brief__grid">
        {scheduledLine ? (
          <>
            <dt>Scheduled</dt>
            <dd>
              {scheduledLine}
              {session.mode ? ` · ${session.mode}` : ''}
            </dd>
          </>
        ) : null}
        {actualRange ? (
          <>
            <dt>Actual</dt>
            <dd>
              {actualRange}
              {startedLate ? (
                <span className="ic-session-brief__late"> · Started late ({formatTimeIST(session.actual_start_at)} IST)</span>
              ) : null}
            </dd>
          </>
        ) : null}
        {duration != null ? (
          <>
            <dt>Duration</dt>
            <dd>{duration} minutes</dd>
          </>
        ) : null}
        <dt>Log</dt>
        <dd>{logPending ? <span className="ic-session-brief__pending">Required before you leave</span> : 'Submitted'}</dd>
      </dl>
      {(session.checkout_lat != null && session.checkout_lng != null) ? (
        <p className="ic-session-brief__location">
          <a
            href={`https://www.google.com/maps?q=${session.checkout_lat},${session.checkout_lng}`}
            target="_blank"
            rel="noreferrer"
          >
            View check-out location
          </a>
        </p>
      ) : null}
    </section>
  )
}
