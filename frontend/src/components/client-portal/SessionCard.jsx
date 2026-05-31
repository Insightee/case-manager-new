import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatParentLogSessionTime } from '../../lib/parentSessionLogDisplay.js'
import { SessionLogParentBody } from './SessionLogParentBody.jsx'

function StarRating({ value, onChange, disabled }) {
  return (
    <div className="session-card__stars" role="group" aria-label="Rate this session">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          className={`session-card__star ${value >= n ? 'is-active' : ''}`}
          onClick={() => !disabled && onChange(n)}
          disabled={disabled}
          aria-label={`${n} stars`}
        >
          ★
        </button>
      ))}
    </div>
  )
}

function formatSubmittedAt(iso) {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export function SessionCard({ log, onSaved, onDispute }) {
  const [rating, setRating] = useState(log.parent_session_rating || 0)
  const [feedback, setFeedback] = useState(log.parent_feedback || '')
  const [sharePublicly, setSharePublicly] = useState(!!log.parent_feedback_public)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [localLog, setLocalLog] = useState(log)
  const [commentsExpanded, setCommentsExpanded] = useState(false)

  useEffect(() => {
    setLocalLog(log)
    setRating(log.parent_session_rating || 0)
    setFeedback(log.parent_feedback || '')
    setSharePublicly(!!log.parent_feedback_public)
  }, [log])

  const hasLongComment = (feedback || '').trim().length > 80

  async function saveFeedback() {
    if (!rating && !feedback.trim()) return
    setSaving(true)
    setError('')
    try {
      const updated = await apiFetch(`/api/v1/parent/session-logs/${localLog.id}/feedback`, {
        method: 'PATCH',
        body: JSON.stringify({
          rating: rating || undefined,
          feedback: feedback.trim() || undefined,
          share_publicly: sharePublicly,
        }),
      })
      setLocalLog((prev) => ({ ...prev, ...updated }))
      setCommentsExpanded(false)
      onSaved?.(updated)
    } catch (err) {
      setError(err.message || 'Could not save feedback')
    } finally {
      setSaving(false)
    }
  }

  const dateLabel = localLog.scheduled_date
    ? new Date(localLog.scheduled_date).toLocaleDateString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : ''
  const timeLabel = formatParentLogSessionTime(localLog)
  const submittedAt = localLog.parent_feedback_at ? formatSubmittedAt(localLog.parent_feedback_at) : ''

  return (
    <article className="session-card">
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title">{localLog.child_name || localLog.case_code}</h3>
          <p className="session-card__meta">
            {dateLabel}
            {localLog.therapist_name ? ` · ${localLog.therapist_name}` : ''}
            {timeLabel ? ` · ${timeLabel}` : ''}
          </p>
        </div>
        <span className="session-card__badge">
          {localLog.attendance_label || localLog.attendance_status}
        </span>
      </header>

      <SessionLogParentBody log={localLog} collapsible />

      <div className="session-card__feedback">
        <StarRating value={rating} onChange={setRating} disabled={saving} />
        <div className="session-card__comments-wrap">
          <label className="session-card__comments-label" htmlFor={`session-comment-${localLog.id}`}>
            Your comments
          </label>
          <textarea
            id={`session-comment-${localLog.id}`}
            className="session-card__textarea"
            placeholder="Optional review"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={saving}
            rows={commentsExpanded ? 4 : 2}
            onFocus={() => {
              if (hasLongComment && !commentsExpanded) setCommentsExpanded(true)
            }}
          />
          {hasLongComment ? (
            <button
              type="button"
              className="session-card__notes-toggle"
              onClick={() => setCommentsExpanded((v) => !v)}
            >
              {commentsExpanded ? 'Show less' : 'Show full comment'}
            </button>
          ) : null}
        </div>
        <label className="session-card__share">
          <input
            type="checkbox"
            checked={sharePublicly}
            onChange={(e) => setSharePublicly(e.target.checked)}
            disabled={saving}
          />
          <span>Share on therapist public profile</span>
        </label>
        {submittedAt ? (
          <p className="session-card__submitted">
            Last saved {submittedAt}
            {localLog.parent_feedback_public ? ' · Public' : ''}
          </p>
        ) : null}
        {error ? <p className="session-card__error">{error}</p> : null}
        <div className="session-card__action-row">
          <button
            type="button"
            className="session-card__save"
            onClick={saveFeedback}
            disabled={saving || (!rating && !feedback.trim())}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
          <button type="button" className="session-card__dispute" onClick={() => onDispute(localLog)} disabled={saving}>
            Dispute
          </button>
        </div>
      </div>
    </article>
  )
}

export function buildSessionDisputeState(log) {
  const dateLabel = log.scheduled_date
    ? new Date(log.scheduled_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
    : 'session'
  return {
    topic: 'THERAPIST',
    case_id: log.case_id,
    subject: `Session dispute — ${dateLabel} (${log.child_name || log.case_code})`,
    message: [
      'I would like to dispute or raise a concern about the following session.',
      '',
      `Session log ID: ${log.id}`,
      `Date: ${log.scheduled_date || '—'}`,
      `Therapist: ${log.therapist_name || '—'}`,
      `Attendance: ${log.attendance_status || '—'}`,
      '',
      'Please describe your concern below:',
    ].join('\n'),
  }
}
