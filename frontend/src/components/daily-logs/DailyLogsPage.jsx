import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import {
  actualDurationMinsIST,
  formatSessionActualRange,
  formatTimeIST,
  isStartedLateOnSchedule,
  parseApiDatetime,
} from '../../lib/datetime.js'
import { isLogEditable } from '../../lib/sessionLogUtils.js'
import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { TherapistSessionComposer } from '../therapist/TherapistSessionComposer.jsx'
import { SubmitSessionLogForm } from './SubmitSessionLogForm.jsx'
import '../cases/my-cases.css'

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatDuration(startIso, tick) {
  if (!startIso) return '00:00:00'
  const start = parseApiDatetime(startIso)?.getTime()
  if (start == null) return '00:00:00'
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
  const [editingLog, setEditingLog] = useState(null)
  const [logRequired, setLogRequired] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [bookedSlots, setBookedSlots] = useState([])
  const logPanelRef = useRef(null)

  const loadAll = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
      setError('')
    }
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)

      const [up, act, allLogs, allSessions, slots] = await Promise.all([
        apiFetch('/api/v1/sessions/upcoming?days=14'),
        apiFetch('/api/v1/sessions/active').catch(() => null),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/sessions?page_size=100'),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`),
      ])
      setUpcoming(Array.isArray(up) ? up : unwrapList(up))
      setBookedSlots(unwrapList(slots))
      setActive(act || null)
      setLogs(Array.isArray(allLogs) ? allLogs : unwrapList(allLogs))
      const completedNoLog = unwrapList(allSessions).filter(
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

  useEffect(() => {
    if (logSession && logPanelRef.current) {
      logPanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [logSession?.id, editingLog?.id])

  function openLogForm(session, { required = false, log = null } = {}) {
    setError('')
    setLogSession(session)
    setEditingLog(log)
    setLogRequired(required)
    setSuccess('')
  }

  function closeLogForm() {
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
  }

  async function getGeoCoords() {
    return new Promise((resolve) => {
      if (!navigator.geolocation) { resolve(null); return }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
        () => resolve(null),
        { timeout: 6000 },
      )
    })
  }

  async function handleStart(sessionId) {
    setError('')
    try {
      const pos = await getGeoCoords()
      await apiFetch(`/api/v1/sessions/${sessionId}/start`, {
        method: 'POST',
        body: JSON.stringify(pos ? { lat: pos.lat, lng: pos.lng } : {}),
      })
      await loadAll({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not start session')
    }
  }

  async function handleEnd(sessionId) {
    setError('')
    try {
      const pos = await getGeoCoords()
      const ended = await apiFetch(`/api/v1/sessions/${sessionId}/end`, {
        method: 'POST',
        body: JSON.stringify(pos ? { lat: pos.lat, lng: pos.lng } : {}),
      })
      openLogForm(ended, { required: true })
      await loadAll({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not end session')
    }
  }

  async function handleManualSession(payload) {
    setSubmitting(true)
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
            ? `Invite sent to ${payload.client_email}. Case ${result.case_code} is pending admin allotment — complete the log below.`
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
        if (payload.isPastDay) {
          setSuccess('Session added. Submit the log and include a late reason for admin review.')
        }
      }
      openLogForm(session, { required: true })
      await loadAll({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not add session')
    } finally {
      setSubmitting(false)
    }
  }

  const showComposer = !logSession && !active

  if (loading && !logSession) {
    return <p style={{ padding: 24, color: '#6b7280' }}>Loading session logs…</p>
  }

  return (
    <div className="daily-logs-page ic-my-cases">
      <header className="ic-page-head">
        <div>
          <h1 className="ic-page-head__title">Session Logs</h1>
          <p className="ic-page-head__sub">
            End each visit with a log so admin can review and families get timely updates. Edit pending logs for 24 hours.
          </p>
        </div>
      </header>

      {error ? (
        <div className="ic-alert ic-alert--error">{error}</div>
      ) : null}
      {success ? (
        <div className="ic-alert ic-alert--success">{success}</div>
      ) : null}

      {active ? (
        <section className="ic-case-active" style={{ marginBottom: 24 }}>
          <p className="ic-case-active__title">Session in progress</p>
          <p style={{ margin: '0 0 4px', fontSize: '0.875rem' }}>
            {active.child_name || active.case_code} · {active.scheduled_date}
            {active.auto_ended ? ' (auto-ended — start a new session to continue)' : ''}
            {active.case_id ? (
              <>
                {' · '}
                <Link to={`/therapist/cases/${active.case_id}`}>Open case</Link>
              </>
            ) : null}
          </p>
          {active.start_time ? (
            <p style={{ margin: '0 0 10px', fontSize: '0.78rem', color: '#6b7280' }}>
              Scheduled: {formatTime(active.start_time)}–{formatTime(active.end_time)}
              {active.actual_start_at ? (
                <>
                  {isStartedLateOnSchedule(active.actual_start_at, active.scheduled_date, active.start_time) ? (
                    <span style={{ color: '#b45309', fontWeight: 600 }}> · Started late at {formatTimeIST(active.actual_start_at)} IST</span>
                  ) : (
                    <span> · Started at {formatTimeIST(active.actual_start_at)} IST</span>
                  )}
                </>
              ) : null}
            </p>
          ) : null}
          <p className="attendance-timer" style={{ fontSize: '2rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', margin: '0 0 16px' }}>
            {formatDuration(active.actual_start_at, tick)}
          </p>
          <button
            type="button"
            className="ic-btn ic-btn--primary"
            style={{ background: '#dc2626', borderColor: '#dc2626' }}
            onClick={() => handleEnd(active.id)}
          >
            End session & write log
          </button>
        </section>
      ) : null}

      {logSession ? (
        <section ref={logPanelRef} style={{ marginBottom: 24 }}>
          <SubmitSessionLogForm
            session={logSession}
            existingLog={editingLog}
            caseCode={logSession.case_code}
            childName={logSession.child_name}
            required={logRequired && !editingLog}
            onSuccess={async () => {
              setSuccess(editingLog ? 'Session log updated.' : 'Session log submitted — pending admin review.')
              closeLogForm()
              await loadAll({ silent: true })
            }}
            onCancel={closeLogForm}
          />
        </section>
      ) : null}

      {showComposer ? (
        <TherapistSessionComposer
          upcomingSessions={upcoming}
          bookedSlots={bookedSlots}
          disabled={!!active}
          onSessionStarted={() => loadAll({ silent: true })}
          onManualSession={handleManualSession}
          onError={setError}
        />
      ) : null}

      {!active && needsLog.length > 0 && !logSession ? (
        <section className="ic-session-log-needs" style={{ marginBottom: 24 }}>
          <h3 className="ic-section-head__title">Needs log</h3>
          <p className="ic-session-log-needs__sub">
            These visits ended without a log. Submit now so billing and family updates are not delayed.
          </p>
          <div className="ic-session-log-needs__list">
            {needsLog.map((s) => (
              <button
                key={s.id}
                type="button"
                className="ic-session-log-needs__item"
                onClick={() => openLogForm(s, { required: false })}
              >
                <span>
                  <strong>{s.child_name || s.case_code}</strong> · {s.scheduled_date}
                </span>
                <span className="ic-session-log-needs__cta">Complete log</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {!logSession ? (
        <section style={{ marginBottom: 24 }}>
          <h3 className="ic-section-head__title" style={{ marginBottom: 12 }}>
            Upcoming sessions
          </h3>
          {upcoming.length === 0 ? (
            <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>No scheduled sessions in the next two weeks.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {upcoming.map((s) => {
                const startedLate = isStartedLateOnSchedule(s.actual_start_at, s.scheduled_date, s.start_time)
                const actualStart = formatTimeIST(s.actual_start_at)
                const actualEnd = formatTimeIST(s.actual_end_at)
                const durMins = actualDurationMinsIST(s.actual_start_at, s.actual_end_at)
                const isInProgress = s.status === 'IN_PROGRESS'
                const isCompleted = s.status === 'COMPLETED'
                return (
                  <article
                    key={s.id}
                    style={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      alignItems: 'flex-start',
                      gap: 12,
                      padding: 14,
                      background: isInProgress ? '#fffbeb' : '#fff',
                      border: `1px solid ${isInProgress ? '#fcd34d' : '#e5e7eb'}`,
                      borderRadius: 12,
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 160 }}>
                      <strong>{s.child_name || s.case_code}</strong>
                      {/* Scheduled reference */}
                      <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>
                        Scheduled: {s.scheduled_date} · {formatTime(s.start_time)}–{formatTime(s.end_time)} · {s.mode}
                        {s.case_id ? (
                          <>
                            {' · '}
                            <Link to={`/therapist/cases/${s.case_id}`}>View case</Link>
                          </>
                        ) : null}
                      </p>
                      {/* Actual times */}
                      {actualStart ? (
                        <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: startedLate ? '#b45309' : '#059669', fontWeight: 500 }}>
                          {startedLate ? '⚠ Started late: ' : 'Started: '}
                          {actualStart}
                          {actualEnd ? ` · Ended: ${actualEnd}` : ' · In progress…'}
                          {durMins ? ` · ${durMins} min` : ''}
                        </p>
                      ) : null}
                      {/* Location badges */}
                      {(s.checkin_lat || s.checkout_lat) ? (
                        <p style={{ margin: '4px 0 0', fontSize: '0.75rem', color: '#6b7280' }}>
                          {s.checkin_lat ? (
                            <a
                              href={`https://www.google.com/maps?q=${s.checkin_lat},${s.checkin_lng}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: '#2563eb', marginRight: 8 }}
                            >
                              📍 Check-in location
                            </a>
                          ) : null}
                          {s.checkout_lat ? (
                            <a
                              href={`https://www.google.com/maps?q=${s.checkout_lat},${s.checkout_lng}`}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: '#2563eb' }}
                            >
                              📍 Check-out location
                            </a>
                          ) : null}
                        </p>
                      ) : null}
                    </div>
                    {!active ? (
                      <button
                        type="button"
                        onClick={() => handleStart(s.id)}
                        className="ic-btn ic-btn--primary"
                      >
                        Start session
                      </button>
                    ) : null}
                  </article>
                )
              })}
            </div>
          )}
        </section>
      ) : null}

      <section>
        <h3 className="ic-section-head__title">Recent logs</h3>
        {logs.length === 0 ? (
          <p style={{ color: '#9ca3af' }}>No logs submitted yet.</p>
        ) : (
          <div className="ic-session-log-recent">
            {logs.slice(0, 10).map((l) => {
              const canEdit = isLogEditable(l)
              const timeRange = formatSessionActualRange({
                actual_start_at: l.actual_start_at,
                actual_end_at: l.actual_end_at,
              })
              return (
                <div key={l.id} className="ic-session-log-recent__row">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p className="ic-session-log-recent__title">
                      {l.child_name || l.case_code}
                      {l.scheduled_date ? <> · {l.scheduled_date}</> : null}
                    </p>
                    {timeRange ? <p className="ic-session-log-recent__times">Actual: {timeRange}</p> : null}
                    <SessionLogStatusBadge
                      approvalStatus={l.approval_status}
                      attendanceStatus={l.attendance_status}
                    />
                    {l.late_addition ? (
                      <span className="ic-session-log-recent__meta">Late submission</span>
                    ) : null}
                    {l.case_id ? (
                      <span className="ic-session-log-recent__meta">
                        <Link to={`/therapist/cases/${l.case_id}`}>Open case</Link>
                      </span>
                    ) : null}
                  </div>
                  {canEdit ? (
                    <button
                      type="button"
                      className="ic-btn ic-btn--ghost ic-session-log-recent__edit"
                      onClick={() =>
                        openLogForm(
                          {
                            id: l.session_id,
                            scheduled_date: l.scheduled_date,
                            actual_start_at: l.actual_start_at,
                            actual_end_at: l.actual_end_at,
                            case_code: l.case_code,
                            child_name: l.child_name,
                          },
                          { log: l },
                        )
                      }
                    >
                      Edit (24h)
                    </button>
                  ) : null}
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}
