import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { ForgotSessionForm } from './ForgotSessionForm.jsx'
import { SubmitSessionLogForm } from './SubmitSessionLogForm.jsx'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatDuration(startIso, tick) {
  if (!startIso) return '00:00:00'
  const start = new Date(startIso).getTime()
  const secs = Math.max(0, Math.floor((tick - start) / 1000))
  const h = Math.floor(secs / 3600)
  const m = Math.floor((secs % 3600) / 60)
  const s = secs % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function DailyLogsPage() {
  const [upcoming, setUpcoming] = useState([])
  const [active, setActive] = useState(null)
  const [logs, setLogs] = useState([])
  const [needsLog, setNeedsLog] = useState([])
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(Date.now())
  const [logSession, setLogSession] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showManual, setShowManual] = useState(false)

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [up, act, allLogs, allSessions] = await Promise.all([
        apiFetch('/api/v1/sessions/upcoming?days=14'),
        apiFetch('/api/v1/sessions/active').catch(() => null),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/sessions'),
      ])
      setUpcoming(up || [])
      setActive(act || null)
      setLogs(allLogs || [])
      const completedNoLog = (allSessions || []).filter(
        (s) => s.status === 'COMPLETED' && !s.has_daily_log,
      )
      setNeedsLog(completedNoLog)
    } catch (err) {
      setError(err.message || 'Could not load sessions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  useEffect(() => {
    if (!active?.actual_start_at) return undefined
    const id = setInterval(() => setTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active?.actual_start_at, active?.id])

  async function handleStart(sessionId) {
    setError('')
    try {
      await apiFetch(`/api/v1/sessions/${sessionId}/start`, { method: 'POST' })
      await loadAll()
    } catch (err) {
      setError(err.message || 'Could not start session')
    }
  }

  async function handleEnd(sessionId) {
    setError('')
    try {
      const ended = await apiFetch(`/api/v1/sessions/${sessionId}/end`, { method: 'POST' })
      await loadAll()
      setLogSession(ended)
    } catch (err) {
      setError(err.message || 'Could not end session')
    }
  }

  async function handleManualSession(payload) {
    setSubmitting(true)
    setError('')
    try {
      const session = await apiFetch('/api/v1/sessions/manual', {
        method: 'POST',
        body: JSON.stringify({
          case_id: payload.case_id,
          scheduled_date: payload.scheduled_date,
          actual_start_at: payload.actual_start_at,
          actual_end_at: payload.actual_end_at,
          mode: payload.mode,
        }),
      })
      setShowManual(false)
      setLogSession(session)
      if (payload.isPastDay) {
        setSuccess('Session added. Submit the log and include a late reason for admin review.')
      }
      await loadAll()
    } catch (err) {
      setError(err.message || 'Could not add session')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return <p style={{ padding: 24, color: '#6b7280' }}>Loading session logs…</p>
  }

  return (
    <div className="daily-logs-page" style={{ maxWidth: 960, margin: '0 auto', padding: '1rem' }}>
      <header style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>Session Logs</h2>
        <p style={{ color: '#6b7280', marginTop: 4 }}>Start sessions, track time, and submit comprehensive logs.</p>
      </header>

      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: 12, marginBottom: 16, color: '#b91c1c' }}>
          {error}
        </div>
      ) : null}
      {success ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: 12, marginBottom: 16, color: '#15803d' }}>
          {success}
        </div>
      ) : null}

      {active ? (
        <section className="attendance-card" style={{ background: '#eef2ff', border: '2px solid #6366f1', borderRadius: 16, padding: 20, marginBottom: 24 }}>
          <p style={{ fontWeight: 600, margin: '0 0 4px', color: '#3730a3' }}>Session in progress</p>
          <p style={{ margin: '0 0 12px', fontSize: '0.875rem' }}>
            {active.child_name || active.case_code} · {active.scheduled_date}
            {active.auto_ended ? ' (auto-ended at 2h — start a new session to continue)' : ''}
            {active.case_id ? (
              <>
                {' · '}
                <Link to={`/therapist/cases/${active.case_id}`}>Open case</Link>
              </>
            ) : null}
          </p>
          <p className="attendance-timer" style={{ fontSize: '2rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', margin: '0 0 16px' }}>
            {formatDuration(active.actual_start_at, tick)}
          </p>
          <button
            type="button"
            onClick={() => handleEnd(active.id)}
            style={{ padding: '10px 20px', borderRadius: 8, background: '#dc2626', color: '#fff', fontWeight: 600, border: 'none', cursor: 'pointer' }}
          >
            End session
          </button>
        </section>
      ) : null}

      {!active && needsLog.length > 0 ? (
        <section style={{ marginBottom: 24 }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Submit log for completed session</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
            {needsLog.map((s) => (
              <button
                key={s.id}
                type="button"
                onClick={() => setLogSession(s)}
                style={{ textAlign: 'left', padding: 12, borderRadius: 8, border: '1px solid #fde047', background: '#fefce8', cursor: 'pointer' }}
              >
                {s.child_name || s.case_code} — {s.scheduled_date} · needs log
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <section style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, margin: 0 }}>Upcoming sessions</h3>
          {!active ? (
            <button
              type="button"
              onClick={() => setShowManual((v) => !v)}
              style={{ fontSize: '0.8rem', color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
            >
              + Log a session I missed
            </button>
          ) : null}
        </div>
        {showManual && !active ? (
          <ForgotSessionForm
            fallbackCases={[...upcoming, ...needsLog]}
            submitting={submitting}
            onSubmit={handleManualSession}
            onCancel={() => setShowManual(false)}
          />
        ) : null}
        {upcoming.length === 0 ? (
          <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>No scheduled sessions in the next two weeks.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {upcoming.map((s) => (
              <article key={s.id} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12, padding: 14, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12 }}>
                <div style={{ flex: 1, minWidth: 160 }}>
                  <strong>{s.child_name || s.case_code}</strong>
                  <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: '#6b7280' }}>
                    {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.mode}
                    {s.case_id ? (
                      <>
                        {' · '}
                        <Link to={`/therapist/cases/${s.case_id}`}>Open case</Link>
                      </>
                    ) : null}
                  </p>
                </div>
                {!active ? (
                  <button
                    type="button"
                    onClick={() => handleStart(s.id)}
                    style={{ padding: '8px 16px', borderRadius: 8, background: '#6366f1', color: '#fff', fontWeight: 600, border: 'none', cursor: 'pointer' }}
                  >
                    Start session
                  </button>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </section>

      {logSession ? (
        <section style={{ background: '#fff', border: '2px solid #6366f1', borderRadius: 16, padding: 20, marginBottom: 24 }}>
          <SubmitSessionLogForm
            session={logSession}
            caseCode={logSession.case_code}
            childName={logSession.child_name}
            onSuccess={async () => {
              setSuccess('Session log submitted for review.')
              setLogSession(null)
              await loadAll()
            }}
            onCancel={() => setLogSession(null)}
          />
        </section>
      ) : null}

      <section>
        <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Recent logs</h3>
        {logs.length === 0 ? (
          <p style={{ color: '#9ca3af' }}>No logs submitted yet.</p>
        ) : (
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {logs.slice(0, 10).map((l) => (
              <div key={l.id} style={{ padding: 12, background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: '0.875rem' }}>
                <strong>{l.case_code}</strong> · {l.attendance_status} · <span style={{ color: '#6b7280' }}>{l.approval_status}</span>
                {l.late_addition ? <span style={{ marginLeft: 8, color: '#a16207' }}>Late</span> : null}
                {l.case_id ? (
                  <>
                    {' · '}
                    <Link to={`/therapist/cases/${l.case_id}`}>Open case</Link>
                  </>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
