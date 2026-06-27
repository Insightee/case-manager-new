import { forwardRef } from 'react'
import {
  formatDisplayDate,
  formatTimeIST,
  isStartedLateOnSchedule,
  parseApiDatetime,
} from '../../lib/datetime.js'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatDuration(startIso, tick) {
  if (!startIso) return '00:00:00'
  const start = parseApiDatetime(startIso)?.getTime()
  if (start == null) return '00:00:00'
  const secs = Math.max(0, Math.floor((tick - start) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * Same-day IN_PROGRESS session — calm timer card with End Session only.
 */
export const ActiveSessionCard = forwardRef(function ActiveSessionCard(
  { session, tick, endBusy, onEnd },
  ref,
) {
  if (!session) return null

  const startedLabel = session.actual_start_at ? formatTimeIST(session.actual_start_at) : null
  const startedLate =
    session.actual_start_at &&
    isStartedLateOnSchedule(session.actual_start_at, session.scheduled_date, session.start_time)

  return (
    <section ref={ref} className="ic-active-session" aria-label="Session in progress">
      <h2 className="ic-active-session__title">Session in Progress</h2>
      <p className="ic-active-session__client">
        <strong>{session.child_name || session.case_code}</strong>
        {' · '}
        {formatDisplayDate(session.scheduled_date)}
      </p>
      {session.start_time ? (
        <p className="ic-active-session__schedule">
          Scheduled: {formatTime(session.start_time)}–{formatTime(session.end_time)}
        </p>
      ) : null}
      {startedLabel ? (
        <p className="ic-active-session__started">
          {startedLate ? (
            <>
              Started late at <strong>{startedLabel}</strong>
            </>
          ) : (
            <>
              Started at: <strong>{startedLabel}</strong>
            </>
          )}
        </p>
      ) : null}
      <p className="ic-active-session__elapsed-label">Elapsed time:</p>
      <p className="ic-active-session__timer" aria-live="polite">
        {formatDuration(session.actual_start_at, tick)}
      </p>
      <button
        type="button"
        className="ic-btn ic-btn--danger ic-active-session__end"
        disabled={endBusy}
        onClick={() => onEnd?.(session.id)}
      >
        {endBusy ? 'Ending…' : 'End Session'}
      </button>
    </section>
  )
})
