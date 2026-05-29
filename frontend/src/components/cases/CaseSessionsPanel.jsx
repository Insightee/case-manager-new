import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  applyLogSavedToCaseLogs,
  applyLogSavedToSessions,
  patchCachesAfterLogSave,
  patchCachesAfterSessionEnd,
} from '../../lib/therapistSessionLogCache.js'
import { formatScheduleWhen } from '../../lib/therapistSchedule.js'
import { TherapistSessionComposer } from '../therapist/TherapistSessionComposer.jsx'
import { SubmitSessionLogForm } from '../daily-logs/SubmitSessionLogForm.jsx'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

export function CaseSessionsPanel({
  caseId,
  caseCode,
  childName,
  childLabel = '',
  scheduleItems = [],
  bookedSlots = [],
  onScheduleChange,
}) {
  const { user } = useAuth()
  const therapistId = user?.id
  const [sessions, setSessions] = useState([])
  const [logs, setLogs] = useState([])
  const [upcomingAll, setUpcomingAll] = useState([])
  const [active, setActive] = useState(null)
  const [loading, setLoading] = useState(true)
  const [logSession, setLogSession] = useState(null)
  const [editingLog, setEditingLog] = useState(null)
  const [logRequired, setLogRequired] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
      setError('')
    }
    try {
      const logParams = new URLSearchParams({ case_id: String(caseId) })
      if (therapistId) logParams.set('therapist_user_id', String(therapistId))
      const [sess, caseLogs, act, upcoming] = await Promise.all([
        apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
        apiFetch(`/api/v1/daily-logs?${logParams}`),
        apiFetch('/api/v1/sessions/active').catch(() => null),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
      ])
      setSessions(unwrapList(sess))
      setLogs(Array.isArray(caseLogs) ? caseLogs : unwrapList(caseLogs))
      setUpcomingAll(Array.isArray(upcoming) ? upcoming : unwrapList(upcoming))
      if (act?.case_id === Number(caseId)) setActive(act)
      else setActive(null)
    } catch (err) {
      setError(err.message || 'Could not load sessions')
    } finally {
      setLoading(false)
    }
  }, [caseId, therapistId])

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

  function openLogForm(session, { required = false, log = null } = {}) {
    setError('')
    setLogSession(session)
    setEditingLog(log)
    setLogRequired(required)
  }

  function closeLogForm() {
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
  }

  async function handleEnd(sessionId) {
    setError('')
    try {
      const ended = await apiFetch(`/api/v1/sessions/${sessionId}/end`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      patchCachesAfterSessionEnd(ended)
      openLogForm(ended, { required: true })
      setActive(null)
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId ? { ...s, ...ended, status: 'COMPLETED', has_daily_log: false } : s,
        ),
      )
      onScheduleChange?.()
    } catch (err) {
      setError(err.message || 'Could not end session')
    }
  }

  async function handleManual(payload) {
    setError('')
    try {
      let session
      if (payload.walkIn) {
        const result = await apiFetch('/api/v1/sessions/manual-walk-in', {
          method: 'POST',
          body: JSON.stringify({
            client_name: payload.client_name,
            client_email: payload.client_email,
            child_name: payload.child_name,
            client_phone: payload.client_phone || undefined,
            scheduled_date: payload.scheduled_date,
            actual_start_at: payload.actual_start_at,
            actual_end_at: payload.actual_end_at,
            mode: payload.mode,
            product_module: payload.product_module || 'homecare',
          }),
        })
        session = result.session
        setSuccess(
          result.invite_sent
            ? `Invite sent. Case ${result.case_code} pending admin allotment — complete the log below.`
            : `Case ${result.case_code} created — complete the log below.`,
        )
      } else {
        session = await apiFetch('/api/v1/sessions/manual', {
          method: 'POST',
          body: JSON.stringify({
            case_id: payload.case_id,
            scheduled_date: payload.scheduled_date,
            actual_start_at: payload.actual_start_at,
            actual_end_at: payload.actual_end_at,
            mode: payload.mode,
          }),
        })
        setSuccess(
          payload.isPastDay
            ? 'Session added — include a late reason when submitting the log for client approval.'
            : 'Session added — complete the log below.',
        )
      }
      openLogForm(session, { required: true })
      setSessions((prev) => {
        const exists = prev.some((s) => s.id === session.id)
        if (exists) return prev
        return [{ ...session, has_daily_log: false }, ...prev]
      })
      void load({ silent: true })
      onScheduleChange?.()
    } catch (err) {
      setError(err.message || 'Could not add session')
    }
  }

  if (loading && !logSession) return <p className="ic-case-panel__loading">Loading sessions…</p>

  return (
    <div className="ic-case-sessions">
      <p className="ic-case-sessions__intro">
        Log work for <strong>{childName}</strong>. For a timer across all clients, use{' '}
        <Link to="/therapist/logs">Session Logs</Link>.
      </p>

      {error ? <p className="ic-session-composer__error">{error}</p> : null}
      {success ? <p className="ic-case-sessions__success">{success}</p> : null}

      {scheduleItems.length > 0 ? (
        <section className="ic-case-sessions__block ic-case-sessions__block--upcoming">
          <h4>Upcoming for this client</h4>
          <ul className="ic-case-schedule-list">
            {scheduleItems.map((item) => (
              <li key={item.key}>
                <span className="ic-case-schedule-list__when">{formatScheduleWhen(item)}</span>
                <span className="ic-case-schedule-list__sub">{item.subtitle}</span>
              </li>
            ))}
          </ul>
          <Link to="/therapist/slots" className="ic-btn ic-btn--ghost" style={{ marginTop: 8 }}>
            Open calendar
          </Link>
        </section>
      ) : (
        <section className="ic-case-sessions__block ic-case-sessions__block--upcoming">
          <h4>Upcoming for this client</h4>
          <p className="ic-case-panel__hint">No upcoming sessions or bookings. Add availability in your calendar.</p>
          <Link to="/therapist/slots" className="ic-btn ic-btn--primary" style={{ marginTop: 8 }}>
            Open slots
          </Link>
        </section>
      )}

      {active ? (
        <div className="ic-case-active">
          <p className="ic-case-active__title">Session in progress</p>
          <button type="button" className="ic-btn ic-btn--primary" style={{ background: '#dc2626', borderColor: '#dc2626' }} onClick={() => handleEnd(active.id)}>
            End session & write log
          </button>
        </div>
      ) : null}

      {logSession ? (
        <SubmitSessionLogForm
          session={logSession}
          existingLog={editingLog}
          childName={childName}
          caseCode={caseCode}
          required={logRequired && !editingLog}
          onSuccess={(savedLog) => {
            const sessionId = logSession?.id ?? savedLog?.session_id
            closeLogForm()
            setSuccess(editingLog ? 'Log updated.' : 'Log submitted for review.')
            patchCachesAfterLogSave({
              userId: therapistId,
              sessionId,
              savedLog,
              isEdit: Boolean(editingLog),
            })
            setSessions((prev) => applyLogSavedToSessions(prev, sessionId))
            setLogs((prev) => applyLogSavedToCaseLogs(prev, savedLog, caseId, { isEdit: Boolean(editingLog) }))
            if (active?.id === sessionId) setActive(null)
            void load({ silent: true })
          }}
          onCancel={logRequired && !editingLog ? undefined : closeLogForm}
        />
      ) : (
        <TherapistSessionComposer
          lockCaseId={caseId}
          lockCaseLabel={childLabel || `${childName} · ${caseCode}`}
          upcomingSessions={upcomingAll}
          bookedSlots={bookedSlots}
          disabled={!!active}
          onSessionStarted={() => void load({ silent: true })}
          onManualSession={handleManual}
          onError={setError}
        />
      )}

      {needsLog.length > 0 && !logSession ? (
        <section className="ic-case-sessions__block">
          <h4>Needs log</h4>
          <ul className="ic-case-sessions__list">
            {needsLog.map((s) => (
              <li key={s.id}>
                <button type="button" className="ic-case-sessions__row ic-case-sessions__row--warn" onClick={() => openLogForm(s)}>
                  {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)}
                  <span>Submit log</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {upcoming.length > 0 && !active ? (
        <section className="ic-case-sessions__block">
          <h4>Scheduled</h4>
          <ul className="ic-case-sessions__list">
            {upcoming.map((s) => (
              <li key={s.id} className="ic-case-sessions__row">
                <span>
                  {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.mode}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="ic-case-sessions__block">
        <h4>History</h4>
        {past.length === 0 ? (
          <p className="ic-case-panel__muted">No completed sessions yet.</p>
        ) : (
          <ul className="ic-case-sessions__list">
            {past.map((s) => {
              const log = logs.find((l) => l.session_id === s.id)
              return (
                <li key={s.id} className="ic-case-sessions__row">
                  <span>
                    <strong>{s.scheduled_date}</strong> · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.status}
                    {log ? (
                      <span className="ic-case-sessions__log-meta">
                        Log: {log.approval_status}
                        {log.late_addition ? ' (late)' : ''}
                      </span>
                    ) : null}
                  </span>
                  {s.status === 'COMPLETED' && !log ? (
                    <button type="button" className="ic-case-sessions__link-btn" onClick={() => openLogForm(s)}>
                      Submit log
                    </button>
                  ) : log && log.can_edit ? (
                    <button
                      type="button"
                      className="ic-case-sessions__link-btn"
                      onClick={() =>
                        openLogForm(
                          {
                            id: s.id,
                            scheduled_date: s.scheduled_date,
                            actual_start_at: s.actual_start_at,
                            actual_end_at: s.actual_end_at,
                          },
                          { log },
                        )
                      }
                    >
                      Edit log
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
