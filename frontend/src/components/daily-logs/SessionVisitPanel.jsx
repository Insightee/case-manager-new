import { Link } from 'react-router-dom'
import { formatDisplayDate } from '../../lib/datetime.js'
import { canStartSessionToday } from '../../lib/sessionStartRules.js'
import { SessionBrief } from './SessionBrief.jsx'

/**
 * Scheduled or in-progress visit — start/end actions, not the log form.
 */
const ACCIDENTAL_START_WINDOW_MINUTES = 5

function elapsedMinutes(startAt) {
  if (!startAt) return Infinity
  return (Date.now() - new Date(startAt).getTime()) / 60000
}

export function SessionVisitPanel({
  session,
  activeSessionId,
  busy,
  onStart,
  onEnd,
  onClose,
  onOpenExisting,
  onCancelAccidental,
  dayBlocker,
}) {
  if (!session) return null

  const isActive = activeSessionId != null && Number(activeSessionId) === Number(session.id)
  const isScheduled = session.status === 'SCHEDULED'
  const isInProgress = session.status === 'IN_PROGRESS' || isActive
  const isCompleted = session.status === 'COMPLETED'
  const anotherActive = activeSessionId != null && !isActive
  const startGuard = canStartSessionToday(session)
  const blockedByDayVisit = Boolean(dayBlocker && dayBlocker.id !== session.id)
  const canStart = isScheduled && !anotherActive && !blockedByDayVisit && startGuard.ok
  const withinAccidentalWindow =
    isInProgress && isActive && elapsedMinutes(session.actual_start_at) < ACCIDENTAL_START_WINDOW_MINUTES

  return (
    <div className="ic-session-visit-panel">
      <header className="ic-session-log-panel__head">
        <div>
          <p className="ic-session-log-panel__eyebrow">Scheduled visit</p>
          <h2 className="ic-session-log-panel__title">{session.child_name || session.case_code || 'Client'}</h2>
          <p className="ic-session-log-panel__meta">
            {formatDisplayDate(session.scheduled_date)}
            {session.start_time ? (
              <> · {formatTime(session.start_time)}–{formatTime(session.end_time)}</>
            ) : null}
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

      {blockedByDayVisit ? (
        <p className="ic-session-log-panel__banner" role="status">
          A session already exists for this client today. Open the existing visit to edit the log or end an active
          session — you cannot start another one from this slot.
        </p>
      ) : null}

      {anotherActive ? (
        <p className="ic-session-log-panel__banner">
          You already have another session in progress. End it before starting this visit.
        </p>
      ) : null}

      {isScheduled && !anotherActive && !startGuard.ok ? (
        <p className="ic-session-log-panel__banner" role="alert">
          {startGuard.message}{' '}
          <Link to="/therapist/logs#forgot">Use Forgot to log</Link>
        </p>
      ) : null}
      {isScheduled && !anotherActive && !blockedByDayVisit && startGuard.ok ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          Start the session when you begin the visit. You will write the session log when you end the timer.
        </p>
      ) : null}

      {isInProgress && !anotherActive && !withinAccidentalWindow ? (
        <p className="ic-session-log-panel__banner">
          Session is in progress. End the visit when you are done to write the required log.
        </p>
      ) : null}

      {withinAccidentalWindow ? (
        <p className="ic-session-log-panel__banner ic-session-log-panel__banner--muted">
          This session was just started.
        </p>
      ) : null}

      <div className="ic-session-visit-panel__actions">
        {blockedByDayVisit ? (
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            onClick={() => onOpenExisting?.(dayBlocker)}
          >
            {dayBlocker?.status === 'IN_PROGRESS' ? 'Go to active session' : 'Edit session log'}
          </button>
        ) : null}
        {canStart ? (
          <button type="button" className="ic-btn ic-btn--primary" disabled={busy} onClick={() => onStart?.(session.id)}>
            {busy ? 'Starting…' : 'Start session'}
          </button>
        ) : null}
        {isInProgress && isActive && !anotherActive && !withinAccidentalWindow ? (
          <button
            type="button"
            className="ic-btn ic-btn--danger"
            disabled={busy}
            onClick={() => onEnd?.(session.id)}
          >
            {busy ? 'Ending…' : 'End session & write log'}
          </button>
        ) : null}
        {withinAccidentalWindow ? (
          <>
            <button
              type="button"
              className="ic-btn ic-btn--primary"
              disabled={busy}
              onClick={() => onEnd?.(session.id)}
            >
              Continue session
            </button>
            <button
              type="button"
              className="ic-btn ic-btn--ghost ic-btn--destructive"
              disabled={busy}
              onClick={() => onCancelAccidental?.(session.id)}
            >
              Cancel accidentally started session
            </button>
          </>
        ) : null}
        {isCompleted && !blockedByDayVisit ? (
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            disabled={busy}
            onClick={() => onOpenExisting?.(session)}
          >
            Edit session log
          </button>
        ) : null}
        {session.case_id ? (
          <Link to="/therapist/logs" className="ic-btn ic-btn--ghost">
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
