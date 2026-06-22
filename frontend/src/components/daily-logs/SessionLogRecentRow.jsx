import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import { formatClockRange, formatEditedRange, canEditSessionTimes } from '../../lib/sessionTimes.js'
import { isLogEditable, isLogResubmittable } from '../../lib/sessionLogUtils.js'
import { SessionLogReadOnly } from './SessionLogReadOnly.jsx'
import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'

function sessionFromLog(log) {
  return {
    id: log.session_id,
    scheduled_date: log.scheduled_date,
    actual_start_at: log.actual_start_at,
    actual_end_at: log.actual_end_at,
    edited_start_at: log.edited_start_at,
    edited_end_at: log.edited_end_at,
    actual_times_edited: log.actual_times_edited,
    actual_times_edit_reason: log.actual_times_edit_reason,
    case_code: log.case_code,
    child_name: log.child_name,
    status: 'COMPLETED',
  }
}

export function SessionLogRecentRow({
  log,
  expanded = false,
  onToggleExpand,
  allowEdit = false,
  allowResubmit = false,
  allowView = false,
  onEditLog,
  onResubmitLog,
  onEditTimes,
}) {
  const rowRef = useRef(null)
  const [detail, setDetail] = useState(null)
  const [enriching, setEnriching] = useState(false)

  const canEdit = allowEdit && isLogEditable(log)
  const canResubmit = allowResubmit && isLogResubmittable(log)
  const canExpand = allowView || canEdit || canResubmit
  const clockRange = formatClockRange(log)
  const editedRange = log.actual_times_edited ? formatEditedRange(log) : null
  const showEditTimes =
    canEditSessionTimes({ ...log, id: log.session_id, status: 'COMPLETED' }, log) && !canResubmit

  useEffect(() => {
    setDetail(null)
  }, [log.id])

  useEffect(() => {
    if (!expanded || !log?.id) return
    let cancelled = false
    setEnriching(true)
    ;(async () => {
      try {
        const fetched = await apiFetch(`/api/v1/daily-logs/${log.id}`)
        if (!cancelled) setDetail(fetched)
      } catch {
        // List payload is already DailyLogRead — use it when detail fetch is unavailable.
        if (!cancelled) setDetail(null)
      } finally {
        if (!cancelled) setEnriching(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [expanded, log])

  useEffect(() => {
    if (!expanded) return
    rowRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [expanded])

  function toggleExpand() {
    onToggleExpand?.(expanded ? null : log.id)
  }

  const displayLog = detail || log
  const session = sessionFromLog(displayLog)

  return (
    <div
      ref={rowRef}
      className={`ic-session-log-recent__row${expanded ? ' ic-session-log-recent__row--expanded' : ''}`}
    >
      <div className="ic-session-log-recent__row-main">
        <div className="ic-session-log-recent__row-body">
          <p className="ic-session-log-recent__title">
            {log.child_name || log.case_code}
            {log.scheduled_date ? <> · {formatDisplayDate(log.scheduled_date)}</> : null}
          </p>
          {clockRange ? <p className="ic-session-log-recent__times">Clock: {clockRange}</p> : null}
          {editedRange ? (
            <p className="ic-session-log-recent__times ic-session-log-recent__times--edited">
              Corrected: {editedRange}
            </p>
          ) : null}
          <div className="ic-session-log-recent__meta-row">
            {log.actual_times_edited ? (
              <span className="ic-session-log-recent__meta ic-session-log-recent__meta--purple">
                Times edited
              </span>
            ) : null}
            {log.duplicate_day_session ? (
              <span className="ic-session-log-recent__meta ic-session-log-recent__meta--warn">
                Same-day duplicate
              </span>
            ) : null}
            {!expanded && log.review_note && log.approval_status === 'REJECTED' ? (
              <span className="ic-session-log-recent__meta ic-session-log-recent__meta--reject">
                CM note available
              </span>
            ) : null}
            {log.status_label ? (
              <span className="ic-session-log-recent__meta ic-session-log-recent__meta--warn">
                {log.status_label}
              </span>
            ) : log.late_addition ? (
              <span className="ic-session-log-recent__meta">Late submission</span>
            ) : null}
            {log.case_id ? (
              <Link
                to={`/therapist/cases/${log.case_id}`}
                className="ic-session-log-recent__case-link"
                onClick={(e) => e.stopPropagation()}
              >
                Open case
              </Link>
            ) : null}
          </div>
        </div>

        <div className="ic-session-log-recent__row-aside">
          <SessionLogStatusBadge
            approvalStatus={log.approval_status}
            attendanceStatus={log.attendance_status}
            compact
          />
          {!expanded && (canResubmit || canEdit || showEditTimes) ? (
            <div className="ic-session-log-recent__inline-actions">
              {canResubmit ? (
                <button
                  type="button"
                  className="ic-session-log-recent__text-btn ic-session-log-recent__text-btn--primary"
                  onClick={() => onResubmitLog?.(log)}
                >
                  Resubmit
                </button>
              ) : null}
              {canEdit ? (
                <button
                  type="button"
                  className="ic-session-log-recent__text-btn"
                  onClick={() => onEditLog?.(log)}
                >
                  Edit
                </button>
              ) : null}
              {showEditTimes ? (
                <button
                  type="button"
                  className="ic-session-log-recent__text-btn"
                  onClick={() => onEditTimes?.(log)}
                >
                  Times
                </button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      {canExpand ? (
        <button
          type="button"
          className="ic-session-log-recent__expand"
          onClick={toggleExpand}
          aria-expanded={expanded}
          aria-label={expanded ? 'Hide log details' : 'View log details'}
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            {expanded ? 'expand_less' : 'expand_more'}
          </span>
        </button>
      ) : null}

      {expanded ? (
        <div className="ic-session-log-recent__detail">
          {enriching && !detail ? (
            <p className="ic-session-log-recent__loading">Loading details…</p>
          ) : null}
          <SessionLogReadOnly
            log={displayLog}
            session={session}
            childName={displayLog.child_name}
            caseCode={displayLog.case_code}
            embed
            hideHeader
          />
          <div className="ic-session-log-recent__detail-actions">
            {canResubmit ? (
              <button
                type="button"
                className="ic-btn ic-btn--primary"
                onClick={() => onResubmitLog?.(displayLog)}
              >
                Edit & resubmit
              </button>
            ) : null}
            {canEdit ? (
              <button type="button" className="ic-btn ic-btn--ghost" onClick={() => onEditLog?.(log)}>
                Edit log (24h)
              </button>
            ) : null}
            {showEditTimes ? (
              <button type="button" className="ic-btn ic-btn--ghost" onClick={() => onEditTimes?.(log)}>
                Edit times
              </button>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
