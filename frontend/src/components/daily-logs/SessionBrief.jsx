import { formatTimeIST, isStartedLateOnSchedule } from '../../lib/datetime.js'
import {
  canEditSessionTimes,
  effectiveDurationMins,
  editedApprovalLabel,
  formatClockRange,
  formatEditedRange,
  formatScheduledRange,
} from '../../lib/sessionTimes.js'

/**
 * Summary shown immediately after ending a visit, before the therapist submits the log.
 */
export function SessionBrief({ session, childName, caseCode, log = null, onEditTimes }) {
  if (!session) return null

  const display = childName || session.child_name || caseCode || session.case_code || 'Client'
  const code = caseCode || session.case_code
  const scheduledLine = formatScheduledRange(session)
  const clockRange = formatClockRange(session)
  const editedRange = formatEditedRange(session)
  const duration = effectiveDurationMins(session, log)
  const startedLate = isStartedLateOnSchedule(
    session.actual_start_at,
    session.scheduled_date,
    session.start_time,
  )
  const logPending = session.status === 'COMPLETED' && !session.has_daily_log
  const showEdit = canEditSessionTimes(session, log) && typeof onEditTimes === 'function'
  const hasEdit = Boolean(session.actual_times_edited && editedRange)

  return (
    <section className="ic-session-brief" aria-label="Session summary">
      <div className="ic-session-brief__head">
        <div>
          <p className="ic-session-brief__eyebrow">Session ended</p>
          {session.auto_end_label ? (
            <p className="ic-session-brief__auto-end">{session.auto_end_label}</p>
          ) : null}
          <h3 className="ic-session-brief__title">{display}</h3>
          {code ? <p className="ic-session-brief__code">{code}</p> : null}
        </div>
        {showEdit ? (
          <button type="button" className="ic-btn ic-btn--ghost ic-session-brief__edit" onClick={onEditTimes}>
            Edit times
          </button>
        ) : null}
      </div>

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
        {clockRange ? (
          <>
            <dt>Actual</dt>
            <dd>
              {clockRange}
              {startedLate ? (
                <span className="ic-session-brief__late">
                  {' '}
                  · Started late ({formatTimeIST(session.actual_start_at)} IST)
                </span>
              ) : null}
              {session.overage_mins > 0 && session.auto_ended ? (
                <span className="ic-session-brief__late"> · Exceeded schedule by {session.overage_mins} min</span>
              ) : null}
            </dd>
          </>
        ) : null}
        {hasEdit ? (
          <>
            <dt>Edited</dt>
            <dd>
              {editedRange}
              <span className="ic-session-brief__edited-badge">{editedApprovalLabel(log)}</span>
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
