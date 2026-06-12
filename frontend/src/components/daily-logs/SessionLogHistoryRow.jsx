import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { SessionLogReadOnly } from './SessionLogReadOnly.jsx'
import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { formatDisplayDate } from '../../lib/datetime.js'
import { formatSessionDisplayRange } from '../../lib/sessionLogUtils.js'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatSessionWhen(session) {
  return formatSessionDisplayRange(session) || `${formatTime(session.start_time)}–${formatTime(session.end_time)}`
}

export function SessionLogHistoryRow({
  session,
  logSummary = null,
  childName = '',
  caseCode = '',
  variant = 'therapist',
  onSubmitLog,
  onEditLog,
  reviewActions = null,
}) {
  const [expanded, setExpanded] = useState(false)
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  async function toggleDetails() {
    if (expanded) {
      setExpanded(false)
      return
    }
    if (detail) {
      setExpanded(true)
      return
    }
    if (!logSummary?.id) return
    setLoading(true)
    setLoadError('')
    try {
      const fetched = await apiFetch(`/api/v1/daily-logs/${logSummary.id}`)
      setDetail(fetched)
      setExpanded(true)
    } catch (err) {
      setLoadError(err.message || 'Could not load log details')
    } finally {
      setLoading(false)
    }
  }

  const log = detail || logSummary

  return (
    <li className="ic-session-history-row">
      <div className="ic-session-history-row__main">
        <div className="ic-session-history-row__info">
          <strong>{formatDisplayDate(session.scheduled_date)}</strong>
          <span className="ic-session-history-row__time">
            {formatSessionWhen(session)} · {session.status}
          </span>
          {logSummary ? (
            <SessionLogStatusBadge
              approvalStatus={logSummary.approval_status}
              attendanceStatus={logSummary.attendance_status}
            />
          ) : null}
        </div>
        <div className="ic-session-history-row__actions">
          {session.status === 'COMPLETED' && !logSummary && onSubmitLog ? (
            <button type="button" className="ic-case-sessions__link-btn" onClick={onSubmitLog}>
              Submit log
            </button>
          ) : null}
          {logSummary?.can_edit && onEditLog ? (
            <button type="button" className="ic-case-sessions__link-btn" onClick={onEditLog}>
              Edit log
            </button>
          ) : null}
          {logSummary?.id ? (
            <button
              type="button"
              className="ic-case-sessions__link-btn ic-session-history-row__details-btn"
              onClick={() => void toggleDetails()}
              aria-expanded={expanded}
            >
              {loading ? 'Loading…' : expanded ? 'Hide details' : 'Show details'}
            </button>
          ) : null}
        </div>
      </div>
      {loadError ? <p className="ic-session-composer__error">{loadError}</p> : null}
      {expanded && log ? (
        <div className="ic-session-history-row__detail">
          <SessionLogReadOnly
            log={log}
            session={session}
            childName={childName}
            caseCode={caseCode}
            variant={variant}
            hideHeader
          />
          {reviewActions}
        </div>
      ) : null}
    </li>
  )
}
