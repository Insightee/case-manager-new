import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { TransitionLogBadge } from './TransitionLogBadge.jsx'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import {
  formatClockRange,
  formatEditedRange,
  formatScheduledRange,
  sessionHasTimeEdit,
} from '../../lib/sessionTimes.js'
import { logCommentFieldStyle, logCommentSendButtonStyle } from '../../lib/logCommentComposerStyles.js'

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

function TeamLogCommentsSection({ logId, variant, onCountChange }) {
  const isAdminVariant = variant === 'admin' || variant === 'case_manager'
  const sendButtonClass = isAdminVariant
    ? 'admin-btn admin-btn--primary admin-btn--sm'
    : 'ic-btn ic-btn--primary'
  const [comments, setComments] = useState([])
  const [newComment, setNewComment] = useState('')
  const [visibility, setVisibility] = useState('parent_team')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function loadComments() {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/daily-logs/${logId}/comments`)
      const rows = Array.isArray(data) ? data : []
      setComments(rows)
      onCountChange?.(
        rows.length,
        rows.filter(
          (c) => c.author_role === 'parent' && c.status === 'open' && c.visibility === 'parent_team',
        ).length,
      )
    } catch (err) {
      setError(err.message || 'Could not load comments')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadComments()
  }, [logId])

  async function handlePostComment(e) {
    e.preventDefault()
    if (!newComment.trim()) return
    setSubmitting(true)
    setError('')
    try {
      const posted = await apiFetch(`/api/v1/daily-logs/${logId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: newComment.trim(), visibility }),
      })
      setComments((prev) => [...prev, posted])
      setNewComment('')
      await loadComments()
    } catch (err) {
      setError(err.message || 'Could not post comment')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleUpdateStatus(commentId, newStatus) {
    try {
      await apiFetch(`/api/v1/daily-logs/comments/${commentId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus }),
      })
      setComments((prev) =>
        prev.map((c) => (c.id === commentId ? { ...c, status: newStatus } : c))
      )
    } catch (err) {
      alert(err.message || 'Could not update comment status')
    }
  }

  return (
    <div className="session-log-comments" style={{ marginTop: 16, borderTop: '1px solid #e2e8f0', paddingTop: 12, paddingBottom: 8 }}>
      <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#334155', margin: '0 0 10px' }}>
        Comments & Updates
      </h4>

      {loading && comments.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.8125rem' }}>Loading comments...</p>
      ) : null}

      {comments.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
          {comments.map((c) => {
            const isParent = c.author_role === 'parent'
            const isInternal = c.visibility === 'internal_only'
            const statusLabel =
              c.status === 'resolved'
                ? 'Closed'
                : c.status === 'acknowledged'
                ? 'Reviewed by team'
                : 'Open'
            const statusColor =
              c.status === 'resolved'
                ? '#64748b'
                : c.status === 'acknowledged'
                ? '#16a34a'
                : '#d97706'

            return (
              <div
                key={c.id}
                style={{
                  background: isInternal ? '#fef2f2' : isParent ? '#f0f9ff' : '#f8fafc',
                  padding: 10,
                  borderRadius: 8,
                  border: isInternal ? '1px solid #fecaca' : isParent ? '1px solid #bae6fd' : '1px solid #e2e8f0',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                  <div>
                    <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: '#1e293b' }}>
                      {c.author_name || 'User'}
                    </span>
                    <span style={{ fontSize: '0.75rem', color: '#64748b', marginLeft: 6, textTransform: 'capitalize' }}>
                      ({c.author_role || 'staff'})
                    </span>
                    {isInternal && (
                      <span style={{ fontSize: '0.7rem', background: '#fee2e2', color: '#991b1b', padding: '1px 4px', borderRadius: 4, marginLeft: 6, fontWeight: 600 }}>
                        Internal Note
                      </span>
                    )}
                  </div>
                  <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                    {c.created_at ? new Date(c.created_at).toLocaleString() : ''}
                  </span>
                </div>
                
                <p style={{ margin: '4px 0 8px', fontSize: '0.8125rem', color: '#334155', whiteSpace: 'pre-wrap' }}>
                  {c.body}
                </p>

                {isParent && (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#fff', padding: '4px 8px', borderRadius: 6, border: '1px solid #e2e8f0' }}>
                    <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                      Status: <strong style={{ color: statusColor }}>{statusLabel}</strong>
                    </span>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {c.status === 'open' && (
                        <button
                          type="button"
                          onClick={() => handleUpdateStatus(c.id, 'acknowledged')}
                          style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#dcfce7', color: '#16a34a', border: '1px solid #bbf7d0', borderRadius: 4, cursor: 'pointer' }}
                        >
                          Acknowledge
                        </button>
                      )}
                      {c.status !== 'resolved' && (variant === 'admin' || variant === 'case_manager') && (
                        <button
                          type="button"
                          onClick={() => handleUpdateStatus(c.id, 'resolved')}
                          style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1', borderRadius: 4, cursor: 'pointer' }}
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        !loading && <p style={{ color: '#94a3b8', fontSize: '0.8125rem', fontStyle: 'italic', margin: '0 0 10px' }}>No comments yet.</p>
      )}

      {error && <p style={{ color: '#dc2626', fontSize: '0.8125rem', marginBottom: 8 }}>{error}</p>}

      <form onSubmit={handlePostComment} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <textarea
          placeholder="Reply to parent or add note..."
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          disabled={submitting}
          rows={2}
          style={{
            ...logCommentFieldStyle,
            resize: 'vertical',
            minHeight: 64,
          }}
        />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center' }}>
          <label style={{ fontSize: '0.75rem', color: '#475569', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input
              type="radio"
              name={`visibility-${logId}`}
              value="parent_team"
              checked={visibility === 'parent_team'}
              onChange={() => setVisibility('parent_team')}
            />
            Reply to parent
          </label>
          <label style={{ fontSize: '0.75rem', color: '#475569', display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
            <input
              type="radio"
              name={`visibility-${logId}`}
              value="internal_only"
              checked={visibility === 'internal_only'}
              onChange={() => setVisibility('internal_only')}
            />
            Internal note
          </label>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="submit"
            disabled={submitting || !newComment.trim()}
            className={sendButtonClass}
            style={logCommentSendButtonStyle(submitting || !newComment.trim())}
          >
            {submitting ? 'Sending...' : 'Send'}
          </button>
        </div>
      </form>
    </div>
  )
}

export function SessionLogReadOnly({
  log,
  session,
  childName,
  caseCode,
  onClose,
  variant = 'therapist',
  hideHeader = false,
  hideTimesSummary = false,
  className = '',
  onCommentCountChange,
}) {
  const isAdmin = variant === 'admin'
  const displayName = childName || log?.child_name || caseCode || log?.case_code || 'Client'
  const timeRange = formatSessionTimeRange(session || log)
  const rootClass = [isAdmin ? 'admin-session-log-detail' : 'ic-session-log-readonly', className]
    .filter(Boolean)
    .join(' ')
  const dlClass = isAdmin ? 'admin-session-log-detail__dl' : 'ic-session-log-readonly__dl'
  const timesSource = session || log
  const hasTimeEdit = sessionHasTimeEdit(session, log)
  const editReason = session?.actual_times_edit_reason || log?.actual_times_edit_reason

  return (
    <section className={rootClass} aria-label="Session log details">
      {!hideHeader ? (
        <div className={isAdmin ? 'admin-session-log-detail__head' : 'ic-session-log-readonly__head'}>
          <div>
            <h3>{displayName}</h3>
            {log?.scheduled_date ? (
              <p className={isAdmin ? 'admin-session-log-detail__meta' : 'ic-session-log-readonly__meta'}>
                {formatDisplayDate(log.scheduled_date)}
                {timeRange ? ` · ${timeRange}` : ''}
              </p>
            ) : null}
            <SessionLogStatusBadge
              approvalStatus={log?.approval_status}
              attendanceStatus={log?.attendance_status}
            />
            <TransitionLogBadge log={log} />
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
      {isAdmin && log?.approval_status === 'PENDING' && log?.resubmitted_at ? (
        <p className="admin-session-log-detail__notice admin-session-log-detail__notice--info" role="status">
          Resubmitted after changes — therapist updated this log following a rejection. Review the corrections before approving.
        </p>
      ) : null}
      {isAdmin && log?.approval_status === 'REJECTED' ? (
        <p className="admin-session-log-detail__notice admin-session-log-detail__notice--warn" role="status">
          Rejected
          {log.review_note ? `: ${log.review_note}` : '.'}
        </p>
      ) : null}
      {isAdmin && hasTimeEdit && log?.approval_status === 'PENDING' ? (
        <p className="admin-session-log-detail__notice" role="status">
          Therapist corrected session times. Approving this log accepts the corrected clock for billing.
        </p>
      ) : null}
      {isAdmin && timesSource && !hideTimesSummary ? (
        <dl className="admin-session-log-detail__times" style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '4px 12px', margin: '0 0 12px', fontSize: '0.8125rem' }}>
          {formatScheduledRange(timesSource) ? (
            <>
              <dt style={{ color: '#64748b' }}>Scheduled</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>{formatScheduledRange(timesSource)}</dd>
            </>
          ) : null}
          {formatClockRange(timesSource) ? (
            <>
              <dt style={{ color: '#64748b' }}>Clock</dt>
              <dd style={{ margin: 0, fontWeight: 600 }}>{formatClockRange(timesSource)}</dd>
            </>
          ) : null}
          {formatEditedRange(timesSource) ? (
            <>
              <dt style={{ color: '#64748b' }}>Corrected</dt>
              <dd style={{ margin: 0, fontWeight: 600, color: '#6d28d9' }}>{formatEditedRange(timesSource)}</dd>
            </>
          ) : null}
          {editReason ? (
            <>
              <dt style={{ color: '#64748b' }}>Edit reason</dt>
              <dd style={{ margin: 0 }}>{editReason}</dd>
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
      {log?.id != null && log.id !== 0 ? (
        <TeamLogCommentsSection
          logId={log.id}
          variant={variant}
          onCountChange={(count, openParentCount) =>
            onCommentCountChange?.(log.id, count, openParentCount)
          }
        />
      ) : null}
    </section>
  )
}
