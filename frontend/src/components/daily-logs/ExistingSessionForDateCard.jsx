import { formatDisplayDate, formatTimeIST } from '../../lib/datetime.js'

function formatClock(t) {
  if (!t) return null
  return String(t).slice(0, 5)
}

function primaryLabel(conflict) {
  const action = conflict?.recommended_action
  if (action === 'resume_session') return 'Resume / End session'
  if (action === 'end_session') return 'End session'
  if (action === 'view_log') {
    return conflict?.log_status === 'approved' ? 'View approved log' : 'View / Edit log'
  }
  return 'Complete session log'
}

/**
 * Shown when forgot-to-log hits an existing session for the same case + date.
 */
export function ExistingSessionForDateCard({ conflict, onAction, onDismiss }) {
  if (!conflict) return null

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
      <h3 className="ic-existing-session-card__title">Existing session found for this day</h3>
      <p className="ic-existing-session-card__name">
        <strong>{conflict.child_name || conflict.case_code}</strong>
        {conflict.scheduled_date ? <> · {formatDisplayDate(conflict.scheduled_date)}</> : null}
      </p>
      {scheduled ? <p className="ic-existing-session-card__meta">Scheduled: {scheduled}</p> : null}
      {actual ? <p className="ic-existing-session-card__meta">Actual: {actual}</p> : null}
      <p className="ic-existing-session-card__meta">
        Status: <strong>{conflict.session_status?.replace(/_/g, ' ')}</strong>
        {conflict.log_status ? (
          <>
            {' '}
            · Log: <strong>{conflict.log_status.replace(/_/g, ' ')}</strong>
          </>
        ) : null}
      </p>
      <p className="ic-existing-session-card__hint">
        A session already exists for this child on this date. Please update the existing session log instead of
        creating another one.
      </p>
      <div className="ic-existing-session-card__actions">
        <button type="button" className="ic-btn ic-btn--primary" onClick={() => onAction?.(conflict)}>
          {primaryLabel(conflict)}
        </button>
        {onDismiss ? (
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onDismiss}>
            Back
          </button>
        ) : null}
      </div>
    </section>
  )
}
