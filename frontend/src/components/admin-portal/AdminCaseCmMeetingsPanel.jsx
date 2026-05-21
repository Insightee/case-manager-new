import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

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
    <section>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <p className="admin-muted" style={{ margin: 0 }}>Case manager meetings for this case.</p>
        <Link to={`/admin/cm-meetings?case_id=${caseId}`} className="admin-btn admin-btn--ghost admin-btn--sm">
          Open meetings hub
        </Link>
      </div>
      {loading ? (
        <p>Loading…</p>
      ) : meetings.length === 0 ? (
        <p className="admin-empty">No meetings scheduled.</p>
      ) : (
        <ul className="admin-queue">
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
      )}
    </section>
  )
}
