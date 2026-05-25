import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'

const FIELDS = [
  { key: 'attendance_status', label: 'Attendance' },
  { key: 'activities_done', label: 'What you did today' },
  { key: 'goals_addressed', label: 'Goals worked on' },
  { key: 'parent_notes', label: 'Update for family' },
  { key: 'session_notes', label: 'Session notes (internal)' },
  { key: 'observations', label: 'Clinical observations' },
  { key: 'follow_ups', label: 'Follow-ups' },
  { key: 'late_reason', label: 'Late reason' },
]

export function SessionLogReadOnly({ log, session, childName, caseCode, onClose }) {
  const displayName = childName || log?.child_name || caseCode || log?.case_code || 'Client'
  const timeRange = formatSessionTimeRange(session || log)

  return (
    <section className="ic-session-log-readonly" aria-label="Session log details">
      <div className="ic-session-log-readonly__head">
        <div>
          <h3>{displayName}</h3>
          {log?.scheduled_date ? (
            <p className="ic-session-log-readonly__meta">
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
      {log?.approval_status === 'APPROVED' ? (
        <p className="ic-session-log-readonly__notice" role="status">
          Approved logs cannot be edited. Contact your case manager if something needs to change.
        </p>
      ) : null}
      {log?.approval_status === 'REJECTED' ? (
        <p className="ic-session-log-readonly__notice ic-session-log-readonly__notice--warn" role="status">
          This log was rejected. Contact your case manager to discuss next steps.
        </p>
      ) : null}
      <dl className="ic-session-log-readonly__dl">
        {FIELDS.map(({ key, label }) => {
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
