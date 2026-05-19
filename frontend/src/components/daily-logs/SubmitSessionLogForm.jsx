import { useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const ATTENDANCE = [
  { value: 'PRESENT', label: 'Present' },
  { value: 'LATE', label: 'Late' },
  { value: 'PARTIAL', label: 'Partial' },
  { value: 'ABSENT', label: 'Absent' },
]

const emptyLogForm = {
  attendance_status: 'PRESENT',
  session_notes: '',
  activities_done: '',
  goals_addressed: '',
  observations: '',
  follow_ups: '',
  parent_notes: '',
  late_reason: '',
}

export function SubmitSessionLogForm({ session, caseCode, childName, onSuccess, onCancel }) {
  const [form, setForm] = useState(emptyLogForm)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const isLateSession = useMemo(() => {
    if (!session?.scheduled_date) return false
    const today = new Date().toISOString().slice(0, 10)
    return session.scheduled_date < today
  }, [session])

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    try {
      await apiFetch('/api/v1/daily-logs', {
        method: 'POST',
        body: JSON.stringify({
          session_id: session.id,
          ...form,
          late_reason: form.late_reason || undefined,
        }),
      })
      onSuccess?.()
    } catch (err) {
      setError(err.message || 'Could not submit log')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section style={{ background: '#fff', border: '2px solid #6366f1', borderRadius: 16, padding: 20, marginBottom: 24 }}>
      <h3 style={{ margin: '0 0 16px' }}>Submit session log</h3>
      <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 0 }}>
        {childName || session.child_name || caseCode || session.case_code} · {session.scheduled_date}
        {session.actual_start_at && session.actual_end_at
          ? ` · ${new Date(session.actual_start_at).toLocaleTimeString()} – ${new Date(session.actual_end_at).toLocaleTimeString()}`
          : ''}
      </p>
      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <label style={{ fontSize: '0.875rem', fontWeight: 500 }}>
          Attendance
          <select
            required
            value={form.attendance_status}
            onChange={(e) => setForm({ ...form, attendance_status: e.target.value })}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 8, border: '1px solid #d1d5db' }}
          >
            {ATTENDANCE.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </select>
        </label>
        {[
          ['session_notes', 'Session notes (internal)'],
          ['activities_done', 'Activities'],
          ['goals_addressed', 'Goals worked on'],
          ['observations', 'Observations (internal)'],
          ['follow_ups', 'Follow-ups'],
          ['parent_notes', 'Notes for family'],
        ].map(([key, label]) => (
          <label key={key} style={{ fontSize: '0.875rem', fontWeight: 500 }}>
            {label}
            <textarea
              value={form[key]}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
              rows={2}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 8, border: '1px solid #d1d5db' }}
            />
          </label>
        ))}
        {isLateSession ? (
          <label style={{ fontSize: '0.875rem', fontWeight: 500 }}>
            Late reason (required for past-day sessions)
            <textarea
              required
              value={form.late_reason}
              onChange={(e) => setForm({ ...form, late_reason: e.target.value })}
              rows={2}
              style={{ display: 'block', width: '100%', marginTop: 4, padding: 8, borderRadius: 8, border: '1px solid #d1d5db' }}
            />
          </label>
        ) : null}
        <div style={{ display: 'flex', gap: 8 }}>
          <button type="submit" disabled={submitting} style={{ flex: 1, padding: 12, borderRadius: 8, background: '#F97316', color: '#fff', fontWeight: 600, border: 'none' }}>
            {submitting ? 'Submitting…' : 'Submit log'}
          </button>
          <button type="button" onClick={onCancel} style={{ padding: 12, borderRadius: 8, border: '1px solid #d1d5db', background: '#fff' }}>
            Cancel
          </button>
        </div>
      </form>
    </section>
  )
}
