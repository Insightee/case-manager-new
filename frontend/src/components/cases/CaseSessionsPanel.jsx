import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { ForgotSessionForm } from '../daily-logs/ForgotSessionForm.jsx'
import { SubmitSessionLogForm } from '../daily-logs/SubmitSessionLogForm.jsx'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

export function CaseSessionsPanel({ caseId, caseCode, childName }) {
  const [sessions, setSessions] = useState([])
  const [logs, setLogs] = useState([])
  const [active, setActive] = useState(null)
  const [loading, setLoading] = useState(true)
  const [logSession, setLogSession] = useState(null)
  const [showForgot, setShowForgot] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [sess, allLogs, act] = await Promise.all([
        apiFetch(`/api/v1/sessions?case_id=${caseId}`),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/sessions/active').catch(() => null),
      ])
      setSessions(sess || [])
      setLogs((allLogs || []).filter((l) => l.case_id === Number(caseId)))
      if (act?.case_id === Number(caseId)) setActive(act)
      else setActive(null)
    } catch (err) {
      setError(err.message || 'Could not load sessions')
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const today = new Date().toISOString().slice(0, 10)
  const upcoming = useMemo(
    () => sessions.filter((s) => s.status === 'SCHEDULED' && s.scheduled_date >= today),
    [sessions, today],
  )
  const needsLog = useMemo(
    () => sessions.filter((s) => s.status === 'COMPLETED' && !s.has_daily_log),
    [sessions],
  )
  const past = useMemo(
    () =>
      sessions
        .filter((s) => s.status === 'COMPLETED' || s.status === 'IN_PROGRESS')
        .sort((a, b) => b.scheduled_date.localeCompare(a.scheduled_date)),
    [sessions],
  )

  async function handleStart(sessionId) {
    setError('')
    try {
      await apiFetch(`/api/v1/sessions/${sessionId}/start`, { method: 'POST' })
      await load()
    } catch (err) {
      setError(err.message || 'Could not start session')
    }
  }

  async function handleEnd(sessionId) {
    setError('')
    try {
      const ended = await apiFetch(`/api/v1/sessions/${sessionId}/end`, { method: 'POST' })
      setLogSession(ended)
      await load()
    } catch (err) {
      setError(err.message || 'Could not end session')
    }
  }

  async function handleManual(payload) {
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
      setShowForgot(false)
      setLogSession(session)
      setSuccess(payload.isPastDay ? 'Session added — include a late reason when submitting the log.' : 'Session added.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not add session')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) return <p style={{ color: '#6b7280' }}>Loading sessions…</p>

  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 0 }}>
        Manage sessions for this client. For today&apos;s timer across all clients, use{' '}
        <Link to="/therapist/logs">Session Logs</Link>.
      </p>

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem' }}>{success}</p> : null}

      {active ? (
        <div style={{ background: '#eef2ff', border: '2px solid #6366f1', borderRadius: 12, padding: 16, marginBottom: 16 }}>
          <p style={{ fontWeight: 600, margin: '0 0 8px' }}>Session in progress</p>
          <button
            type="button"
            onClick={() => handleEnd(active.id)}
            style={{ padding: '8px 16px', borderRadius: 8, background: '#dc2626', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}
          >
            End session
          </button>
        </div>
      ) : null}

      {logSession ? (
        <SubmitSessionLogForm
          session={logSession}
          childName={childName}
          caseCode={caseCode}
          onSuccess={() => {
            setLogSession(null)
            setSuccess('Log submitted.')
            load()
          }}
          onCancel={() => setLogSession(null)}
        />
      ) : null}

      {!logSession && !active ? (
        <div style={{ marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => setShowForgot((v) => !v)}
            style={{ fontSize: '0.875rem', color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
          >
            + Log a session I missed
          </button>
          {showForgot ? (
            <ForgotSessionForm
              fallbackCases={[{ case_id: Number(caseId), child_name: childName, case_code: caseCode }]}
              submitting={submitting}
              initialCaseId={String(caseId)}
              onSubmit={handleManual}
              onCancel={() => setShowForgot(false)}
            />
          ) : null}
        </div>
      ) : null}

      {needsLog.length > 0 && !logSession ? (
        <section style={{ marginBottom: 20 }}>
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Needs log</h4>
          {needsLog.map((s) => (
            <button
              key={s.id}
              type="button"
              onClick={() => setLogSession(s)}
              style={{ display: 'block', width: '100%', textAlign: 'left', marginTop: 8, padding: 12, borderRadius: 8, border: '1px solid #fde047', background: '#fefce8', cursor: 'pointer' }}
            >
              {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)}
            </button>
          ))}
        </section>
      ) : null}

      {upcoming.length > 0 && !active ? (
        <section style={{ marginBottom: 20 }}>
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Upcoming</h4>
          {upcoming.map((s) => (
            <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, marginTop: 8, border: '1px solid #e5e7eb', borderRadius: 8 }}>
              <span style={{ fontSize: '0.875rem' }}>
                {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.mode}
              </span>
              <button type="button" onClick={() => handleStart(s.id)} style={{ padding: '6px 12px', borderRadius: 8, background: '#6366f1', color: '#fff', border: 'none', fontWeight: 600, cursor: 'pointer' }}>
                Start
              </button>
            </div>
          ))}
        </section>
      ) : null}

      <section>
        <h4 style={{ fontSize: '0.9375rem', fontWeight: 600 }}>Session history</h4>
        {past.length === 0 ? (
          <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>No completed sessions yet.</p>
        ) : (
          <ul style={{ listStyle: 'none', padding: 0, margin: '8px 0 0' }}>
            {past.map((s) => {
              const log = logs.find((l) => l.session_id === s.id)
              return (
                <li key={s.id} style={{ padding: '10px 0', borderBottom: '1px solid #f3f4f6', fontSize: '0.875rem' }}>
                  <strong>{s.scheduled_date}</strong> · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.status}
                  {log ? (
                    <span style={{ marginLeft: 8, color: '#6b7280' }}>
                      Log: {log.approval_status}
                      {log.late_addition ? ' (late)' : ''}
                    </span>
                  ) : s.status === 'COMPLETED' ? (
                    <button type="button" onClick={() => setLogSession(s)} style={{ marginLeft: 8, color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
                      Submit log
                    </button>
                  ) : null}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
