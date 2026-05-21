import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import './parent-session-updates.css'

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

function SessionCard({ log, onSaved, onDispute }) {
  const hasSubmitted = !!(log.parent_feedback_at && (log.parent_session_rating || log.parent_feedback))
  const [editing, setEditing] = useState(!hasSubmitted)
  const [rating, setRating] = useState(log.parent_session_rating || 0)
  const [feedback, setFeedback] = useState(log.parent_feedback || '')
  const [sharePublicly, setSharePublicly] = useState(!!log.parent_feedback_public)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [localLog, setLocalLog] = useState(log)

  useEffect(() => {
    setLocalLog(log)
    if (log.parent_feedback_at && (log.parent_session_rating || log.parent_feedback)) {
      setEditing(false)
    }
  }, [log])

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
      setEditing(false)
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

  const showClosed = hasSubmitted || (localLog.parent_feedback_at && !editing)

  return (
    <article className="session-card">
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title">{localLog.child_name || localLog.case_code}</h3>
          <p className="session-card__meta">
            {dateLabel}
            {localLog.therapist_name ? ` · Therapist: ${localLog.therapist_name}` : ''}
            {localLog.start_time && localLog.end_time ? ` · ${localLog.start_time}–${localLog.end_time}` : ''}
          </p>
        </div>
        <span className="session-card__badge">{localLog.attendance_status}</span>
      </header>

      {localLog.activities_done ? (
        <p className="session-card__block">
          <strong>Activities:</strong> {localLog.activities_done}
        </p>
      ) : null}
      {localLog.goals_addressed ? (
        <p className="session-card__block">
          <strong>Goals:</strong> {localLog.goals_addressed}
        </p>
      ) : null}
      {localLog.follow_ups ? (
        <p className="session-card__block">
          <strong>Follow-ups:</strong> {localLog.follow_ups}
        </p>
      ) : null}
      {localLog.parent_notes ? (
        <div className="session-card__therapist-note">
          <strong>From your therapist</strong>
          <p style={{ margin: '6px 0 0' }}>{localLog.parent_notes}</p>
        </div>
      ) : null}

      {showClosed && !editing ? (
        <div className="session-card__feedback session-card__feedback--closed">
          <strong style={{ fontSize: '0.875rem' }}>Your feedback</strong>
          <div style={{ marginTop: 8 }}>
            <StarRating value={localLog.parent_session_rating || 0} onChange={() => {}} disabled />
          </div>
          {localLog.parent_feedback ? (
            <p style={{ fontSize: '0.85rem', color: '#475569', margin: '8px 0' }}>{localLog.parent_feedback}</p>
          ) : null}
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: 0 }}>
            Submitted {formatSubmittedAt(localLog.parent_feedback_at)}
            {localLog.parent_feedback_public ? ' · Shared on therapist profile' : ''}
          </p>
          <button type="button" className="session-card__edit-link" onClick={() => setEditing(true)}>
            Edit feedback
          </button>
        </div>
      ) : (
        <div className="session-card__feedback">
          <strong style={{ fontSize: '0.875rem' }}>Rate this session</strong>
          <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '4px 0 8px' }}>
            Give a 1–5 star rating and optional review. Your therapist sees this on their profile.
          </p>
          <StarRating value={rating} onChange={setRating} disabled={saving} />
          <textarea
            className="session-card__textarea"
            placeholder="Your review (optional)"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={saving}
          />
          <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 10, fontSize: '0.8rem', color: '#475569' }}>
            <input
              type="checkbox"
              checked={sharePublicly}
              onChange={(e) => setSharePublicly(e.target.checked)}
              disabled={saving}
              style={{ marginTop: 3 }}
            />
            <span>Share this review on the therapist&apos;s public profile when available.</span>
          </label>
          {error ? <p style={{ color: '#b91c1c', fontSize: '0.8rem' }}>{error}</p> : null}
          <div className="session-card__feedback-actions">
            <button type="button" className="session-card__save" onClick={saveFeedback} disabled={saving}>
              {saving ? 'Saving…' : 'Save feedback'}
            </button>
            {hasSubmitted ? (
              <button type="button" className="session-card__ghost" onClick={() => setEditing(false)} disabled={saving}>
                Cancel
              </button>
            ) : null}
          </div>
        </div>
      )}

      <div className="session-card__footer-actions">
        <button type="button" className="session-card__dispute" onClick={() => onDispute(localLog)}>
          Raise a dispute
        </button>
        <Link to="/parent/book" className="session-card__link-schedule">
          Session schedule →
        </Link>
      </div>
    </article>
  )
}

function CmMeetingCard({ meeting }) {
  const dateLabel = meeting.scheduled_date
    ? new Date(meeting.scheduled_date + 'T00:00:00').toLocaleDateString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : ''

  return (
    <article className="session-card" style={{ borderLeft: '3px solid #7c3aed' }}>
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {meeting.child_name || 'Case manager meeting'}
            <span className="session-card__cm-pill">CM Meeting</span>
          </h3>
          <p className="session-card__meta">
            {dateLabel}
            {meeting.scheduled_time ? ` · ${meeting.scheduled_time}` : ''}
            {meeting.case_manager_name ? ` · Case manager: ${meeting.case_manager_name}` : ''}
          </p>
        </div>
        <span className="session-card__badge session-card__badge--cm">{meeting.status}</span>
      </header>

      {meeting.notes_concerns ? (
        <p className="session-card__block">
          <strong>Concerns addressed:</strong> {meeting.notes_concerns}
        </p>
      ) : null}
      {meeting.notes_follow_up ? (
        <p className="session-card__block">
          <strong>Follow-up steps:</strong> {meeting.notes_follow_up}
        </p>
      ) : null}
      {meeting.notes_action ? (
        <p className="session-card__block">
          <strong>Actions taken:</strong> {meeting.notes_action}
        </p>
      ) : null}
      {meeting.notes_other ? (
        <p className="session-card__block">
          <strong>Additional notes:</strong> {meeting.notes_other}
        </p>
      ) : null}
      {!meeting.notes_concerns && !meeting.notes_follow_up && !meeting.notes_action && !meeting.notes_other ? (
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '8px 0 0' }}>
          Meeting notes will appear here after your case manager completes the meeting.
        </p>
      ) : null}
    </article>
  )
}

function buildMonthOptions() {
  const opts = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    opts.push({
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      label: d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
      year: d.getFullYear(),
      month: d.getMonth() + 1,
    })
  }
  return opts
}

const ATTENDANCE_FILTERS = [
  { value: '', label: 'All attendance' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'PARTIAL', label: 'Partial' },
  { value: 'NO_SHOW', label: 'No show' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

export function ClientSessionLogsPage({ cases = [] }) {
  const navigate = useNavigate()
  const monthOptions = useMemo(() => buildMonthOptions(), [])
  const [selectedMonth, setSelectedMonth] = useState(monthOptions[0].value)
  const [logs, setLogs] = useState([])
  const [meetings, setMeetings] = useState([])
  const [caseId, setCaseId] = useState('')
  const [attendanceFilter, setAttendanceFilter] = useState('')
  const [loading, setLoading] = useState(true)

  const selectedMeta = useMemo(
    () => monthOptions.find((o) => o.value === selectedMonth) || monthOptions[0],
    [selectedMonth, monthOptions],
  )

  function load() {
    setLoading(true)
    const caseQ = caseId ? `&case_id=${caseId}` : ''
    Promise.all([
      apiFetch(`/api/v1/parent/session-logs?year=${selectedMeta.year}&month=${selectedMeta.month}${caseQ}`).catch(
        () => [],
      ),
      apiFetch(`/api/v1/parent/cm-meetings?year=${selectedMeta.year}&month=${selectedMeta.month}`).catch(() => []),
    ])
      .then(([logsData, meetingsData]) => {
        setLogs(logsData || [])
        setMeetings(meetingsData || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [caseId, selectedMonth])

  const caseOptions = useMemo(() => {
    const byChild = new Map()
    for (const c of cases) {
      if (!byChild.has(c.childName)) byChild.set(c.childName, c)
    }
    return [...byChild.values()]
  }, [cases])

  const filteredLogs = useMemo(() => {
    if (!attendanceFilter) return logs
    return logs.filter((l) => (l.attendance_status || '').toUpperCase() === attendanceFilter)
  }, [logs, attendanceFilter])

  function handleDispute(log) {
    const dateLabel = log.scheduled_date
      ? new Date(log.scheduled_date).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
      : 'session'
    navigate('/parent/support?tab=support', {
      state: {
        topic: 'THERAPIST',
        case_id: log.case_id,
        subject: `Session dispute — ${dateLabel} (${log.child_name || log.case_code})`,
        message: [
          `I would like to dispute or raise a concern about the following session.`,
          ``,
          `Session log ID: ${log.id}`,
          `Date: ${log.scheduled_date || '—'}`,
          `Therapist: ${log.therapist_name || '—'}`,
          `Attendance: ${log.attendance_status || '—'}`,
          ``,
          `Please describe your concern below:`,
        ].join('\n'),
      },
    })
  }

  const monthLabel = selectedMeta.label

  return (
    <div>
      <p className="session-updates__intro">
        Approved session notes from your therapist and case manager meeting summaries. Your case manager is assigned by
        the clinic on your child&apos;s case; your therapist is assigned separately for visits.
      </p>

      <div className="session-updates__filters">
        {caseOptions.length > 0 ? (
          <label className="session-updates__filter-label">
            Child
            <select
              className="session-updates__select"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
            >
              <option value="">All children</option>
              {caseOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.childName} · {c.serviceType}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="session-updates__filter-label">
          Month
          <select
            className="session-updates__select"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
          >
            {monthOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>

        <label className="session-updates__filter-label">
          Attendance
          <select
            className="session-updates__select"
            value={attendanceFilter}
            onChange={(e) => setAttendanceFilter(e.target.value)}
          >
            {ATTENDANCE_FILTERS.map((f) => (
              <option key={f.value || 'all'} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>

        <Link to="/parent/book" className="session-updates__schedule-link">
          Session schedule →
        </Link>
      </div>

      <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>{monthLabel}</h2>

      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading session updates…</p>
      ) : filteredLogs.length === 0 && meetings.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>
          No session updates for {monthLabel}. Your therapist will share approved updates after each visit.
        </p>
      ) : (
        (() => {
          const combined = [
            ...filteredLogs.map((l) => ({ type: 'log', date: l.scheduled_date, data: l })),
            ...meetings.map((m) => ({ type: 'meeting', date: m.scheduled_date, data: m })),
          ].sort((a, b) => (a.date > b.date ? -1 : a.date < b.date ? 1 : 0))

          return combined.map((item) =>
            item.type === 'log' ? (
              <SessionCard key={`log-${item.data.id}`} log={item.data} onSaved={load} onDispute={handleDispute} />
            ) : (
              <CmMeetingCard key={`cm-${item.data.id}`} meeting={item.data} />
            ),
          )
        })()
      )}
    </div>
  )
}
