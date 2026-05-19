import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function ClientSessionLogsPage({ cases = [] }) {
  const [logs, setLogs] = useState([])
  const [caseId, setCaseId] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    const q = caseId ? `?case_id=${caseId}` : ''
    apiFetch(`/api/v1/parent/session-logs${q}`)
      .then(setLogs)
      .catch(() => setLogs([]))
      .finally(() => setLoading(false))
  }, [caseId])

  return (
    <div>
      {cases.length > 1 ? (
        <select
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
          style={{ marginBottom: 16, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db' }}
        >
          <option value="">All children</option>
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              {c.childName} ({c.caseId})
            </option>
          ))}
        </select>
      ) : null}
      {loading ? (
        <p style={{ color: '#9ca3af' }}>Loading session updates…</p>
      ) : logs.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No session logs yet. Your therapist will share updates after each visit.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {logs.map((log) => (
            <article key={log.id} style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                <strong>{log.child_name || log.case_code}</strong>
                <span style={{ fontSize: '0.8rem', color: '#6b7280' }}>{log.scheduled_date}</span>
              </div>
              <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: '0 0 8px' }}>
                {log.therapist_name ? `With ${log.therapist_name}` : ''}
                {log.start_time && log.end_time ? ` · ${log.start_time}–${log.end_time}` : ''}
                {' · '}
                {log.attendance_status}
              </p>
              {log.activities_done ? (
                <p style={{ fontSize: '0.875rem', margin: '4px 0' }}>
                  <strong>Activities:</strong> {log.activities_done}
                </p>
              ) : null}
              {log.goals_addressed ? (
                <p style={{ fontSize: '0.875rem', margin: '4px 0' }}>
                  <strong>Goals:</strong> {log.goals_addressed}
                </p>
              ) : null}
              {log.follow_ups ? (
                <p style={{ fontSize: '0.875rem', margin: '4px 0' }}>
                  <strong>Follow-ups:</strong> {log.follow_ups}
                </p>
              ) : null}
              {log.parent_notes ? (
                <p style={{ fontSize: '0.875rem', margin: '4px 0', color: '#374151' }}>
                  {log.parent_notes}
                </p>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
