import { useEffect, useMemo, useState } from 'react'
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

function SessionCard({ log, onSaved }) {
  const [rating, setRating] = useState(log.parent_session_rating || 0)
  const [feedback, setFeedback] = useState(log.parent_feedback || '')
  const [sharePublicly, setSharePublicly] = useState(!!log.parent_feedback_public)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')

  async function saveFeedback() {
    if (!rating && !feedback.trim()) return
    setSaving(true)
    setError('')
    setSaved(false)
    try {
      await apiFetch(`/api/v1/parent/session-logs/${log.id}/feedback`, {
        method: 'PATCH',
        body: JSON.stringify({
          rating: rating || undefined,
          feedback: feedback.trim() || undefined,
          share_publicly: sharePublicly,
        }),
      })
      setSaved(true)
      onSaved?.()
    } catch (err) {
      setError(err.message || 'Could not save feedback')
    } finally {
      setSaving(false)
    }
  }

  const dateLabel = log.scheduled_date
    ? new Date(log.scheduled_date).toLocaleDateString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : ''

  return (
    <article className="session-card">
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title">{log.child_name || log.case_code}</h3>
          <p className="session-card__meta">
            {dateLabel}
            {log.therapist_name ? ` · ${log.therapist_name}` : ''}
            {log.start_time && log.end_time ? ` · ${log.start_time}–${log.end_time}` : ''}
          </p>
        </div>
        <span className="session-card__badge">{log.attendance_status}</span>
      </header>

      {log.activities_done ? (
        <p className="session-card__block">
          <strong>Activities:</strong> {log.activities_done}
        </p>
      ) : null}
      {log.goals_addressed ? (
        <p className="session-card__block">
          <strong>Goals:</strong> {log.goals_addressed}
        </p>
      ) : null}
      {log.follow_ups ? (
        <p className="session-card__block">
          <strong>Follow-ups:</strong> {log.follow_ups}
        </p>
      ) : null}
      {log.parent_notes ? (
        <div className="session-card__therapist-note">
          <strong>From your therapist</strong>
          <p style={{ margin: '6px 0 0' }}>{log.parent_notes}</p>
        </div>
      ) : null}

      <div className="session-card__feedback">
        <strong style={{ fontSize: '0.875rem' }}>Rate this session</strong>
        <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '4px 0 8px' }}>
          Give a 1–5 star rating and optional review. Your therapist sees this on their profile; you can choose to
          share it publicly later.
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
          <span>
            Share this review on the therapist&apos;s public profile (when available). Your child&apos;s name is shown
            only to the therapist and admin.
          </span>
        </label>
        {error ? <p style={{ color: '#b91c1c', fontSize: '0.8rem' }}>{error}</p> : null}
        {saved ? <p className="session-card__saved">Thank you — feedback saved.</p> : null}
        <button type="button" className="session-card__save" onClick={saveFeedback} disabled={saving}>
          {saving ? 'Saving…' : log.parent_feedback_at ? 'Update feedback' : 'Save feedback'}
        </button>
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
            <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#ede9fe', color: '#4c1d95', borderRadius: 99, padding: '1px 8px', border: '1px solid #c4b5fd' }}>
              CM Meeting
            </span>
          </h3>
          <p className="session-card__meta">
            {dateLabel}
            {meeting.scheduled_time ? ` · ${meeting.scheduled_time}` : ''}
            {meeting.case_manager_name ? ` · ${meeting.case_manager_name}` : ''}
          </p>
        </div>
        <span className="session-card__badge" style={{ background: '#ede9fe', color: '#6d28d9' }}>{meeting.status}</span>
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
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '8px 0 0' }}>Meeting notes will appear here after the meeting is completed.</p>
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

export function ClientSessionLogsPage({ cases = [] }) {
  const monthOptions = useMemo(() => buildMonthOptions(), [])
  const [selectedMonth, setSelectedMonth] = useState(monthOptions[0].value)
  const [logs, setLogs] = useState([])
  const [meetings, setMeetings] = useState([])
  const [caseId, setCaseId] = useState('')
  const [loading, setLoading] = useState(true)

  const selectedMeta = useMemo(
    () => monthOptions.find((o) => o.value === selectedMonth) || monthOptions[0],
    [selectedMonth, monthOptions],
  )

  function load() {
    setLoading(true)
    const caseQ = caseId ? `&case_id=${caseId}` : ''
    Promise.all([
      apiFetch(`/api/v1/parent/session-logs?year=${selectedMeta.year}&month=${selectedMeta.month}${caseQ}`).catch(() => []),
      apiFetch(`/api/v1/parent/cm-meetings?year=${selectedMeta.year}&month=${selectedMeta.month}`).catch(() => []),
    ]).then(([logsData, meetingsData]) => {
      setLogs(logsData || [])
      setMeetings(meetingsData || [])
    }).finally(() => setLoading(false))
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

  const monthLabel = selectedMeta.label

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
        {caseOptions.length > 0 ? (
          <label style={{ fontSize: '0.875rem', fontWeight: 500, color: '#475569' }}>
            Child
            <select
              className="session-updates__select"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              style={{ display: 'block', marginTop: 4 }}
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

        <label style={{ fontSize: '0.875rem', fontWeight: 500, color: '#475569' }}>
          Month
          <select
            className="session-updates__select"
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            style={{ display: 'block', marginTop: 4 }}
          >
            {monthOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#1e293b', marginBottom: 12 }}>{monthLabel}</h2>

      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading session updates…</p>
      ) : logs.length === 0 && meetings.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>
          No session updates for {monthLabel}. Your therapist will share approved updates after each visit.
        </p>
      ) : (
        (() => {
          const combined = [
            ...logs.map((l) => ({ type: 'log', date: l.scheduled_date, data: l })),
            ...meetings.map((m) => ({ type: 'meeting', date: m.scheduled_date, data: m })),
          ].sort((a, b) => (a.date > b.date ? -1 : a.date < b.date ? 1 : 0))

          return combined.map((item) =>
            item.type === 'log' ? (
              <SessionCard key={`log-${item.data.id}`} log={item.data} onSaved={load} />
            ) : (
              <CmMeetingCard key={`cm-${item.data.id}`} meeting={item.data} />
            ),
          )
        })()
      )}
    </div>
  )
}
