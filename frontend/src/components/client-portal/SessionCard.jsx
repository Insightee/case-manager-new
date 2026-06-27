import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDate, formatDisplayDateLabel } from '../../lib/datetime.js'
import { formatParentLogClockFootnote, formatParentLogSessionTime } from '../../lib/parentSessionLogDisplay.js'
import { SessionLogParentBody } from './SessionLogParentBody.jsx'

function formatSubmittedAt(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}

function LogCommentsSection({ logId }) {
  const [comments, setComments] = useState([])
  const [newComment, setNewComment] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function loadComments() {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/parent/session-logs/${logId}/comments`)
      setComments(data || [])
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
      const posted = await apiFetch(`/api/v1/parent/session-logs/${logId}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: newComment.trim() }),
      })
      setComments((prev) => [...prev, posted])
      setNewComment('')
    } catch (err) {
      setError(err.message || 'Could not post comment')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="log-comments-section" style={{ marginTop: 16, borderTop: '1px solid #e2e8f0', paddingTop: 12 }}>
      <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#334155', margin: '0 0 8px' }}>Comments & Updates</h4>
      
      {loading && comments.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: '0.8125rem', margin: '0 0 8px' }}>Loading comments...</p>
      ) : null}

      {comments.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
          {comments.map((c) => (
            <div key={c.id} style={{ background: '#f8fafc', padding: 8, borderRadius: 8, border: '1px solid #f1f5f9' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#475569' }}>{c.author_name || 'User'}</span>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                  {c.created_at ? new Date(c.created_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }) : ''}
                </span>
              </div>
              <p style={{ margin: 0, fontSize: '0.8125rem', color: '#334155', whiteSpace: 'pre-wrap' }}>{c.body}</p>
            </div>
          ))}
        </div>
      ) : (
        !loading && <p style={{ color: '#94a3b8', fontSize: '0.8125rem', fontStyle: 'italic', margin: '0 0 12px' }}>No comments yet.</p>
      )}

      {error && <p style={{ color: '#dc2626', fontSize: '0.8125rem', marginBottom: 8 }}>{error}</p>}

      <form onSubmit={handlePostComment} style={{ display: 'flex', gap: 8 }}>
        <input
          type="text"
          placeholder="Add a comment..."
          value={newComment}
          onChange={(e) => setNewComment(e.target.value)}
          disabled={submitting}
          style={{
            flex: 1,
            padding: '6px 10px',
            fontSize: '0.8125rem',
            borderRadius: 6,
            border: '1px solid #cbd5e1',
            outline: 'none',
            background: '#fff'
          }}
        />
        <button
          type="submit"
          disabled={submitting || !newComment.trim()}
          className="ic-btn ic-btn--primary"
          style={{ padding: '6px 12px', fontSize: '0.8125rem' }}
        >
          {submitting ? '...' : 'Send'}
        </button>
      </form>
    </div>
  )
}

export function SessionCard({ log, onSaved, onDispute }) {
  const [localLog, setLocalLog] = useState(log)
  const [showReason, setShowReason] = useState(false)
  const [showDisputeForm, setShowDisputeForm] = useState(false)
  const [disputeComment, setDisputeComment] = useState('')
  const [disputeError, setDisputeError] = useState('')
  const [disputeBusy, setDisputeBusy] = useState(false)

  useEffect(() => {
    setLocalLog(log)
  }, [log])

  const isVirtual = localLog.id < 0
  const isTherapistLeave = localLog.attendance_status === 'THERAPIST_LEAVE'
  const isClientAbsentOrLeave = localLog.attendance_status === 'CLIENT_ABSENT' || localLog.attendance_status === 'CLIENT_LEAVE'
  const isDisputed = localLog.dispute_status === 'DISPUTED'

  const dateLabel = localLog.scheduled_date ? formatDisplayDateLabel(localLog.scheduled_date) : ''
  const timeLabel = isTherapistLeave ? '' : formatParentLogSessionTime(localLog)
  const clockFootnote = isVirtual ? null : formatParentLogClockFootnote(localLog)

  async function submitDispute() {
    setDisputeBusy(true)
    setDisputeError('')
    try {
      const session_id = Math.abs(localLog.id)
      await apiFetch(`/api/v1/parent/session-logs/${session_id}/dispute`, {
        method: 'POST',
        body: JSON.stringify({ comment: disputeComment }),
      })
      setLocalLog((prev) => ({ ...prev, dispute_status: 'DISPUTED' }))
      setShowDisputeForm(false)
      setDisputeComment('')
      onSaved?.()
    } catch (err) {
      setDisputeError(err.message || 'Could not submit dispute')
    } finally {
      setDisputeBusy(false)
    }
  }

  let badgeLabel = localLog.attendance_label || localLog.attendance_status
  if (isTherapistLeave) badgeLabel = 'Therapist unavailable'
  else if (localLog.attendance_status === 'CLIENT_ABSENT') badgeLabel = 'Child on leave'
  else if (localLog.attendance_status === 'CLIENT_LEAVE') badgeLabel = 'Child on leave'

  return (
    <article className="session-card">
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title">
            {isTherapistLeave ? 'Therapist Leave' : (localLog.child_name || localLog.case_code)}
          </h3>
          <p className="session-card__meta">
            {dateLabel}
            {!isTherapistLeave && localLog.therapist_name ? ` · ${localLog.therapist_name}` : ''}
            {timeLabel ? ` · ${timeLabel}` : ''}
          </p>
          {clockFootnote ? (
            <p className="session-card__meta" style={{ color: '#94a3b8', fontSize: '0.78rem' }}>
              {clockFootnote}
            </p>
          ) : null}
        </div>
        <span className={`session-card__badge ${isTherapistLeave ? 'session-card__badge--neutral' : ''}`}>
          {badgeLabel}
        </span>
      </header>

      {!isVirtual ? (
        <SessionLogParentBody log={localLog} collapsible />
      ) : (
        <div className="session-card__body">
          <p className="session-card__section-text" style={{ color: '#475569' }}>
            {isTherapistLeave 
              ? 'Therapist was on leave.' 
              : `Session was marked as ${localLog.attendance_status === 'CLIENT_LEAVE' ? 'Client Leave' : 'Client Absent'}.`
            }
          </p>
        </div>
      )}

      <div className="session-card__feedback" style={{ borderTop: 'none', paddingTop: 0 }}>
        {isClientAbsentOrLeave && localLog.absence_reason ? (
          <div style={{ marginTop: 8, marginBottom: 8 }}>
            <button
              type="button"
              className="session-card__notes-toggle"
              onClick={() => setShowReason((prev) => !prev)}
              style={{ fontSize: '0.78rem', color: '#4f46e5', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
            >
              {showReason ? 'Hide reason' : 'Show reason'}
            </button>
            {showReason && (
              <p style={{ marginTop: 6, padding: '8px 12px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: 6, fontSize: '0.8125rem', color: '#4b5563', fontStyle: 'italic' }}>
                Reason: {localLog.absence_reason}
              </p>
            )}
          </div>
        ) : null}

        <div className="session-card__action-row" style={{ marginTop: 12, justifyContent: 'flex-start', alignItems: 'center', gap: 12 }}>
          {isDisputed ? (
            <span style={{ color: '#dc2626', fontWeight: 600, fontSize: '0.8125rem', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              ⚠️ Disputed
            </span>
          ) : isClientAbsentOrLeave ? (
            <button
              type="button"
              className="ic-btn ic-btn--primary"
              style={{ background: '#dc2626', borderColor: '#dc2626', padding: '6px 12px', fontSize: '0.8125rem' }}
              onClick={() => setShowDisputeForm(true)}
            >
              Dispute
            </button>
          ) : null}
        </div>

        {showDisputeForm && (
          <div className="session-card__dispute-form" style={{ marginTop: 12, padding: 12, background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8 }}>
            <p style={{ margin: '0 0 8px', fontSize: '0.875rem', fontWeight: 600, color: '#991b1b' }}>Dispute Attendance Status</p>
            <textarea
              style={{ width: '100%', padding: 8, fontSize: '0.875rem', borderRadius: 6, border: '1px solid #d1d5db', marginBottom: 8, background: '#fff' }}
              placeholder="Describe why you dispute this status..."
              value={disputeComment}
              onChange={(e) => setDisputeComment(e.target.value)}
              rows={3}
            />
            {disputeError && <p style={{ color: '#dc2626', fontSize: '0.8125rem', margin: '0 0 8px' }}>{disputeError}</p>}
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                type="button"
                className="ic-btn ic-btn--primary"
                style={{ background: '#dc2626', borderColor: '#dc2626', padding: '4px 10px', fontSize: '0.78rem' }}
                onClick={submitDispute}
                disabled={disputeBusy || !disputeComment.trim()}
              >
                {disputeBusy ? 'Submitting...' : 'Submit Dispute'}
              </button>
              <button
                type="button"
                className="ic-btn ic-btn--ghost"
                style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                onClick={() => {
                  setShowDisputeForm(false)
                  setDisputeComment('')
                  setDisputeError('')
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        <LogCommentsSection logId={localLog.id} />
      </div>
    </article>
  )
}

export function buildSessionDisputeState(log) {
  const dateLabel = log.scheduled_date ? formatDisplayDate(log.scheduled_date) : 'session'
  return {
    topic: 'THERAPIST',
    case_id: log.case_id,
    subject: `Session dispute — ${dateLabel} (${log.child_name || log.case_code})`,
    message: [
      'I would like to dispute or raise a concern about the following session.',
      '',
      `Session log ID: ${log.id}`,
      `Date: ${formatDisplayDate(log.scheduled_date)}`,
      `Therapist: ${log.therapist_name || '—'}`,
      `Attendance: ${log.attendance_status || '—'}`,
      '',
      'Please describe your concern below:',
    ].join('\n'),
  }
}
