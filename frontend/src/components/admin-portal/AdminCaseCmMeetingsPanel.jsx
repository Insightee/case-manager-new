import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { StatusBadge } from './ui/index.js'

function formatMeetingType(type) {
  if (!type) return 'Meeting'
  return String(type)
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatWhen(m) {
  if (!m.scheduled_date) return 'Date TBD'
  try {
    const d = new Date(`${m.scheduled_date}T${m.scheduled_time || '12:00'}`)
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleString(undefined, {
        weekday: 'short',
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
      })
    }
  } catch {
    /* fallback below */
  }
  return `${m.scheduled_date}${m.scheduled_time ? ` · ${m.scheduled_time}` : ''}`
}

function participantLine(m) {
  const parts = [m.case_manager_name, m.therapist_name, m.parent_name].filter(Boolean)
  if (m.attendees?.length) {
    const names = m.attendees.map((a) => a.name || a.full_name).filter(Boolean)
    if (names.length) return names.join(', ')
  }
  return parts.length ? parts.join(' · ') : null
}

function meetingHref(caseId) {
  return `/admin/cm-meetings?case_id=${caseId}`
}

export function AdminCaseCmMeetingsPanel({ caseId }) {
  const [meetings, setMeetings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!caseId) return
    setLoading(true)
    apiFetch(`/api/v1/cm-meetings?case_id=${caseId}`)
      .then(setMeetings)
      .catch(() => setMeetings([]))
      .finally(() => setLoading(false))
  }, [caseId])

  return (
    <section className="admin-case-cm-meetings" aria-labelledby="admin-case-cm-meetings-title">
      <div className="admin-case-cm-meetings__head admin-case-detail__mobile-only">
        <div>
          <h2 id="admin-case-cm-meetings-title" className="admin-case-cm-meetings__title">
            CM meetings
          </h2>
          <p className="admin-case-cm-meetings__sub">Case manager meetings for this case</p>
        </div>
        <Link
          to={meetingHref(caseId)}
          className="admin-case-cm-meetings__view-all"
          aria-label="View all case manager meetings"
        >
          View all →
        </Link>
      </div>

      <div className="admin-case-cm-meetings__desktop-head admin-case-detail__header--desktop">
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, gap: 12 }}>
          <p className="admin-muted" style={{ margin: 0 }}>
            Case manager meetings for this case.
          </p>
          <Link to={meetingHref(caseId)} className="admin-btn admin-btn--ghost admin-btn--sm">
            Open meetings hub
          </Link>
        </div>
      </div>

      {loading ? (
        <p className="admin-muted">Loading…</p>
      ) : meetings.length === 0 ? (
        <p className="admin-empty">No meetings scheduled.</p>
      ) : (
        <>
          <ul className="admin-case-cm-meetings__cards admin-case-detail__mobile-only">
            {meetings.map((m) => {
              const people = participantLine(m)
              const hasNotes =
                m.notes_concerns || m.notes_follow_up || m.notes_action || m.notes_other
              const cta = hasNotes ? 'Open notes' : 'View meeting'
              return (
                <li key={m.id}>
                  <Link
                    to={meetingHref(caseId)}
                    className="admin-case-cm-meeting-card"
                    aria-label={`${m.title || formatMeetingType(m.meeting_type)}, ${formatWhen(m)}`}
                  >
                    <span className="admin-case-cm-meeting-card__type">{formatMeetingType(m.meeting_type)}</span>
                    <h3 className="admin-case-cm-meeting-card__title">{m.title || formatMeetingType(m.meeting_type)}</h3>
                    <p className="admin-case-cm-meeting-card__when">{formatWhen(m)}</p>
                    {people ? <p className="admin-case-cm-meeting-card__people">{people}</p> : null}
                    <div className="admin-case-cm-meeting-card__foot">
                      <StatusBadge status={m.status} />
                      <span className="admin-case-cm-meeting-card__cta">{cta} →</span>
                    </div>
                  </Link>
                </li>
              )
            })}
          </ul>
          <ul className="admin-queue admin-case-cm-meetings__desktop-list">
            {meetings.map((m) => (
              <li key={m.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{m.title || m.meeting_type}</p>
                  <p className="admin-queue__meta">
                    {m.scheduled_date} {m.scheduled_time || ''} · {m.status}
                  </p>
                </div>
                <span className="admin-badge">{m.meeting_type}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
