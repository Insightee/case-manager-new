import { Link } from 'react-router-dom'
import { SessionBrief } from './SessionBrief.jsx'

/**
 * Scheduled or in-progress visit — start/end actions, not the log form.
 */
export function SessionVisitPanel({
  session,
  activeSessionId,
  busy,
  onStart,
  onEnd,
  onClose,
}) {
  if (!session) return null

  const isActive = activeSessionId != null && Number(activeSessionId) === Number(session.id)
  const isScheduled = session.status === 'SCHEDULED'
  const isInProgress = session.status === 'IN_PROGRESS' || isActive
  const anotherActive = activeSessionId != null && !isActive

  return (
    <div className="ic-session-visit-panel">
      <header className="ic-session-log-panel__head">
        <div>
          <p className="ic-session-log-panel__eyebrow">Scheduled visit</p>
          <h2 className="ic-session-log-panel__title">{session.child_name || session.case_code || 'Client'}</h2>
          <p className="ic-session-log-panel__meta">
            {session.scheduled_date}
            {session.start_time ? (
              <> · {formatTime(session.start_time)}–{formatTime(session.end_time)}</>
            ) : null}
            {session.mode ? <> · {session.mode}</> : null}
          </p>
        </div>
        {onClose ? (
          <button type="button" className="ic-btn ic-btn--ghost ic-session-log-panel__dismiss" onClick={onClose}>
            Close
          </button>
        ) : null}
      </header>

      {(isInProgress || session.actual_end_at) && !isScheduled ? (
        <SessionBrief session={session} childName={session.child_name} caseCode={session.case_code} />
      ) : null}

      {anotherActive ? (
        <p className="ic-session-log-panel__banner">
          You already have another session in progress. End it before starting this visit.
        </p>
      ) : null}

      {isScheduled && !anotherActive ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Start the session when you begin the visit. You will write the session log when you end the timer.
        </p>
      ) : null}

      {isInProgress && !anotherActive ? (
        <p className="ic-session-log-panel__banner">
          Session is in progress. End the visit when you are done to write the required log.
        </p>
      ) : null}

      <div className="ic-session-visit-panel__actions">
        {isScheduled && !anotherActive ? (
          <button type="button" className="ic-btn ic-btn--primary" disabled={busy} onClick={() => onStart?.(session.id)}>
            {busy ? 'Starting…' : 'Start session'}
          </button>
        ) : null}
        {isInProgress && isActive && !anotherActive ? (
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            style={{ background: '#dc2626', borderColor: '#dc2626' }}
            disabled={busy}
            onClick={() => onEnd?.(session.id)}
          >
            {busy ? 'Ending…' : 'End session & write log'}
          </button>
        ) : null}
        {session.case_id ? (
          <Link to={`/therapist/cases/${session.case_id}?tab=sessions`} className="ic-btn ic-btn--ghost">
            Open case sessions
          </Link>
        ) : null}
      </div>
    </div>
  )
}

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}
