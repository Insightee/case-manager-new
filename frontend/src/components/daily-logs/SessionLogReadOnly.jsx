import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'
import { formatClockRange, formatEditedRange, formatScheduledRange } from '../../lib/sessionTimes.js'

export const SESSION_LOG_READONLY_FIELDS = [
  { key: 'attendance_status', label: 'Attendance' },
  { key: 'activities_done', label: 'What you did today' },
  { key: 'goals_addressed', label: 'Goals worked on' },
  { key: 'parent_notes', label: 'Update for family' },
  { key: 'session_notes', label: 'Session notes (internal)' },
  { key: 'observations', label: 'Clinical observations' },
  { key: 'follow_ups', label: 'Follow-ups' },
  { key: 'late_reason', label: 'Late reason' },
]

export function SessionLogReadOnly({
  log,
  session,
  childName,
  caseCode,
  onClose,
  variant = 'therapist',
  hideHeader = false,
  className = '',
}) {
  const isAdmin = variant === 'admin'
  const displayName = childName || log?.child_name || caseCode || log?.case_code || 'Client'
  const timeRange = formatSessionTimeRange(session || log)
  const rootClass = [isAdmin ? 'admin-session-log-detail' : 'ic-session-log-readonly', className]
    .filter(Boolean)
    .join(' ')
  const dlClass = isAdmin ? 'admin-session-log-detail__dl' : 'ic-session-log-readonly__dl'

  return (
    <section className={rootClass} aria-label="Session log details">
      {!hideHeader ? (
        <div className={isAdmin ? 'admin-session-log-detail__head' : 'ic-session-log-readonly__head'}>
          <div>
            <h3>{displayName}</h3>
            {log?.scheduled_date ? (
              <p className={isAdmin ? 'admin-session-log-detail__meta' : 'ic-session-log-readonly__meta'}>
                {log.scheduled_date}
                {timeRange ? ` · ${timeRange}` : ''}
              </p>
            ) : null}
            <SessionLogStatusBadge
              approvalStatus={log?.approval_status}
              attendanceStatus={log?.attendance_status}
            />
          </div>
          {onClose ? (
            <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose}>
              Close
            </button>
          ) : null}
        </div>
      ) : null}
      {!isAdmin && log?.approval_status === 'APPROVED' ? (
        <p className="ic-session-log-readonly__notice" role="status">
          Approved logs cannot be edited. Contact your case manager if something needs to change.
        </p>
      ) : null}
      {!isAdmin && log?.approval_status === 'REJECTED' ? (
        <p className="ic-session-log-readonly__notice ic-session-log-readonly__notice--warn" role="status">
          This log was rejected.
          {log.review_note ? ` Note: ${log.review_note}` : ' Contact your case manager to discuss next steps.'}
        </p>
      ) : null}
      {isAdmin && log?.approval_status === 'REJECTED' ? (
        <p className="admin-session-log-detail__notice admin-session-log-detail__notice--warn" role="status">
          Rejected
          {log.review_note ? `: ${log.review_note}` : '.'}
        </p>
      ) : null}
      {isAdmin && session ? (
        <dl className="admin-session-log-detail__times" style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', margin: '0 0 12px', fontSize: '0.8125rem' }}>
          {formatScheduledRange(session) ? (
            <>
              <dt style={{ color: '#64748b' }}>Scheduled</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>{formatScheduledRange(session)}</dd>
            </>
          ) : null}
          {formatClockRange(session) ? (
            <>
              <dt style={{ color: '#64748b' }}>Clock</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>{formatClockRange(session)}</dd>
            </>
          ) : null}
          {formatEditedRange(session) ? (
            <>
              <dt style={{ color: '#64748b' }}>Corrected</dt>
              <dd style={{ margin: 0, fontWeight: 600, color: '#6d28d9' }}>{formatEditedRange(session)}</dd>
            </>
          ) : null}
          {session.actual_times_edit_reason || log?.actual_times_edit_reason ? (
            <>
              <dt style={{ color: '#64748b' }}>Edit reason</dt>
              <dd style={{ margin: 0 }}>{session.actual_times_edit_reason || log.actual_times_edit_reason}</dd>
            </>
          ) : null}
        </dl>
      ) : null}
      <dl className={dlClass}>
        {SESSION_LOG_READONLY_FIELDS.map(({ key, label }) => {
          const val = log?.[key]
          if (!val) return null
          return (
            <div key={key}>
              <dt>{label}</dt>
              <dd>{val}</dd>
            </div>
          )
        })}
      </dl>
    </section>
  )
}
