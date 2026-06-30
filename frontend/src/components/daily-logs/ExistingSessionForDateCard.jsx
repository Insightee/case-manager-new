import { formatDisplayDate, formatTimeIST } from '../../lib/datetime.js'
import { isAbsenceConflict } from '../../lib/sessionStartRules.js'

function formatClock(t) {
  if (!t) return null
  return String(t).slice(0, 5)
}

function primaryLabel(conflict) {
  const action = conflict?.recommended_action
  if (action === 'resume_session') return 'Go to active session'
  if (action === 'complete_forgotten') return 'Record visit & write log'
  if (action === 'view_log' && conflict?.log_status === 'approved') return 'View approved log'
  if (action === 'edit_log' || action === 'view_log') return 'Edit session log'
  return 'Edit session log'
}

function logStatusLabel(status) {
  if (!status) return null
  if (status === 'not_started') return 'Not started'
  if (status === 'incomplete') return 'Needs log'
  if (status === 'submitted') return 'Submitted'
  if (status === 'approved') return 'Approved'
  return status.replace(/_/g, ' ')
}

/**
 * Shown when forgot-to-log hits an existing session for the same case + date.
 */
export function ExistingSessionForDateCard({ conflict, onAction, onDismiss }) {
  if (!conflict) return null

  const absenceBlocked = isAbsenceConflict(conflict)
  const scheduled =
    conflict.start_time && conflict.end_time
      ? `${formatClock(conflict.start_time)}–${formatClock(conflict.end_time)}`
      : conflict.start_time
        ? formatClock(conflict.start_time)
        : null
  const actual =
    conflict.actual_start_at || conflict.actual_end_at
      ? [
          conflict.actual_start_at ? formatTimeIST(conflict.actual_start_at) : null,
          conflict.actual_end_at ? formatTimeIST(conflict.actual_end_at) : null,
        ]
          .filter(Boolean)
          .join(' – ')
      : null

  return (
    <section className="ic-existing-session-card" aria-label="Existing session for this day">
      <h3 className="ic-existing-session-card__title">
        {absenceBlocked ? 'Child absence on this day' : 'Existing session found for this day'}
      </h3>
      <p className="ic-existing-session-card__name">
        <strong>{conflict.child_name || conflict.case_code}</strong>
        {conflict.scheduled_date ? <> · {formatDisplayDate(conflict.scheduled_date)}</> : null}
      </p>
      {!absenceBlocked && scheduled ? (
        <p className="ic-existing-session-card__meta">Scheduled: {scheduled}</p>
      ) : null}
      {!absenceBlocked && actual ? (
        <p className="ic-existing-session-card__meta">
          Session time: <strong>{actual}</strong>
        </p>
      ) : !absenceBlocked && scheduled ? (
        <p className="ic-existing-session-card__meta">Session time not recorded yet</p>
      ) : null}
      {!absenceBlocked ? (
        <p className="ic-existing-session-card__meta">
          Status: <strong>{conflict.session_status?.replace(/_/g, ' ')}</strong>
          {conflict.log_status ? (
            <>
              {' '}
              · Log: <strong>{logStatusLabel(conflict.log_status)}</strong>
            </>
          ) : null}
        </p>
      ) : null}
      <p className="ic-existing-session-card__hint">
        {conflict.message ||
          (absenceBlocked
            ? 'This day is recorded as child absent — a session log cannot be added.'
            : 'A session already exists for this child on this date. Please update the existing session log instead of creating another one.')}
      </p>
      <div className="ic-existing-session-card__actions">
        {!absenceBlocked ? (
          <button type="button" className="ic-btn ic-btn--primary" onClick={() => onAction?.(conflict)}>
            {primaryLabel(conflict)}
          </button>
        ) : null}
        {onDismiss ? (
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onDismiss}>
            Back
          </button>
        ) : null}
      </div>
    </section>
  )
}
