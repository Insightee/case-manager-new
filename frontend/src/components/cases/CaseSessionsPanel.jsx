import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { clearLogDraft } from '../../lib/logDraftStore.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  applyLogSavedToCaseLogs,
  applyLogSavedToSessions,
  patchCachesAfterLogSave,
  patchCachesAfterPendingLogDiscarded,
  patchCachesAfterSessionCancel,
  patchCachesAfterSessionEnd,
} from '../../lib/therapistSessionLogCache.js'
import { isPendingLogBlock } from '../../lib/sessionStartRules.js'
import { formatScheduleWhen } from '../../lib/therapistSchedule.js'
import { TherapistSessionComposer } from '../therapist/TherapistSessionComposer.jsx'
import { PendingLogGate, discardPendingLogWithDraft } from '../daily-logs/PendingLogGate.jsx'
import { SubmitSessionLogForm } from '../daily-logs/SubmitSessionLogForm.jsx'
import { SessionLogHistoryRow } from '../daily-logs/SessionLogHistoryRow.jsx'
import { formatDisplayDateTimeRange } from '../../lib/datetime.js'
import { formatSessionDisplayRange } from '../../lib/sessionLogUtils.js'
import { enrichLogsWithCommentCounts } from '../../lib/sessionLogComments.js'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatSessionWhen(session) {
  return formatSessionDisplayRange(session) || `${formatTime(session.start_time)}–${formatTime(session.end_time)}`
}

export function CaseSessionsPanel({
  caseId,
  caseCode,
  childName,
  childLabel = '',
  scheduleItems = [],
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
  const [historyMonth, setHistoryMonth] = useState('ALL')
  const [historyYear, setHistoryYear] = useState(() => String(new Date().getFullYear()))
  const [cancelSessionBusy, setCancelSessionBusy] = useState(false)
  const [discardBusy, setDiscardBusy] = useState(false)

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
      const rawLogs = Array.isArray(caseLogs) ? caseLogs : unwrapList(caseLogs)
      setLogs(await enrichLogsWithCommentCounts(rawLogs, apiFetch))
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
  const blockingLogSession = useMemo(() => {
    if (!needsLog.length) return null
    return [...needsLog].sort((a, b) =>
      String(b.scheduled_date || '').localeCompare(String(a.scheduled_date || '')),
    )[0]
  }, [needsLog])
  const pendingLogBlocked = Boolean(blockingLogSession) && !active
  const past = useMemo(
    () =>
      sessions
        .filter((s) => s.status === 'COMPLETED' || s.status === 'IN_PROGRESS')
        .sort((a, b) => b.scheduled_date.localeCompare(a.scheduled_date)),
    [sessions],
  )

  const historyYears = useMemo(() => {
    const years = new Set([new Date().getFullYear()])
    past.forEach((s) => {
      if (s.scheduled_date) years.add(Number(s.scheduled_date.slice(0, 4)))
    })
    return Array.from(years).filter(Number.isFinite).sort((a, b) => b - a).map(String)
  }, [past])

  const filteredPast = useMemo(() => {
    return past.filter((s) => {
      if (!s.scheduled_date) return false
      const d = new Date(`${s.scheduled_date}T00:00:00`)
      if (String(d.getFullYear()) !== historyYear) return false
      if (historyMonth === 'ALL') return true
      return d.getMonth() === Number(historyMonth)
    })
  }, [past, historyMonth, historyYear])

  const historyFilterLabel = useMemo(() => {
    if (historyMonth === 'ALL') return historyYear
    return `${MONTHS[Number(historyMonth)]} ${historyYear}`
  }, [historyMonth, historyYear])

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

  async function handleCancelSession(sessionId, sessionStatus) {
    setCancelSessionBusy(true)
    setError('')
    const endpoint =
      sessionStatus === 'COMPLETED'
        ? `/api/v1/sessions/${sessionId}/void-before-log`
        : `/api/v1/sessions/${sessionId}/cancel`
    try {
      const cancelled = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      patchCachesAfterSessionCancel(cancelled)
      void clearLogDraft(sessionId)
      closeLogForm()
      setActive(null)
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? { ...s, ...cancelled, status: cancelled.status, has_daily_log: false }
            : s,
        ),
      )
      setSuccess(
        sessionStatus === 'COMPLETED'
          ? 'Session removed — you can start again, mark absent, or update the schedule.'
          : 'Session cancelled.',
      )
      onScheduleChange?.()
      void load({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not cancel session')
    } finally {
      setCancelSessionBusy(false)
    }
  }

  async function handleCancel(sessionId) {
    if (!window.confirm('Cancel this session? The timer will stop and no log will be created.')) return
    await handleCancelSession(sessionId, 'IN_PROGRESS')
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
      if (err?.status === 409 && isPendingLogBlock(err.detail)) {
        setError(
          err.detail.message ||
            'This client\'s previous visit still needs a log before adding another session.',
        )
        return
      }
      setError(err.message || 'Could not add session')
    }
  }

  async function handleDiscardPendingLog(session) {
    if (!session?.id) return
    setDiscardBusy(true)
    setError('')
    try {
      const cancelled = await discardPendingLogWithDraft(session.id)
      patchCachesAfterPendingLogDiscarded(cancelled)
      setSuccess('Draft visit removed — you can start a new session for this client.')
      void load({ silent: true })
      onScheduleChange?.()
    } catch (err) {
      setError(err.message || 'Could not remove the draft visit')
    } finally {
      setDiscardBusy(false)
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

      {blockingLogSession && !logSession ? (
        <PendingLogGate
          session={blockingLogSession}
          busy={discardBusy}
          onCompleteLog={(s) => openLogForm(s, { required: true })}
          onDiscard={handleDiscardPendingLog}
        />
      ) : null}

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
            Scheduling
          </Link>
        </section>
      )}

      {active ? (
        <div className="ic-case-active">
          <p className="ic-case-active__title">Session in progress</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <button type="button" className="ic-btn ic-btn--primary" style={{ background: '#dc2626', borderColor: '#dc2626' }} onClick={() => handleEnd(active.id)}>
              End session & write log
            </button>
            <button type="button" className="ic-btn ic-btn--ghost" onClick={() => handleCancel(active.id)}>
              Cancel session
            </button>
          </div>
        </div>
      ) : null}

      {logSession ? (
        <SubmitSessionLogForm
          session={logSession}
          existingLog={editingLog}
          childName={childName}
          caseCode={caseCode}
          required={logRequired && !editingLog}
          onCancelSession={
            logRequired && !editingLog && logSession?.id
              ? () => handleCancelSession(logSession.id, logSession.status || 'COMPLETED')
              : undefined
          }
          cancelSessionBusy={cancelSessionBusy}
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
          disabled={!!active}
          pendingLogBlocked={pendingLogBlocked}
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
                  {formatDisplayDateTimeRange(s.scheduled_date, s.start_time, s.end_time) || formatSessionWhen(s)}
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
                  {formatDisplayDateTimeRange(s.scheduled_date, s.start_time, s.end_time)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="ic-case-sessions__block">
        {past.length > 0 ? (
          <div className="ic-case-history-head">
            <h4>History</h4>
            <div className="ic-case-history-filters">
              <label>
                <span className="sr-only">Month</span>
                <select
                  value={historyMonth}
                  onChange={(e) => setHistoryMonth(e.target.value)}
                  aria-label="Filter history by month"
                >
                  <option value="ALL">All months</option>
                  {MONTHS.map((m, idx) => (
                    <option key={m} value={idx}>
                      {m}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span className="sr-only">Year</span>
                <select
                  value={historyYear}
                  onChange={(e) => setHistoryYear(e.target.value)}
                  aria-label="Filter history by year"
                >
                  {historyYears.map((y) => (
                    <option key={y} value={y}>
                      {y}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>
        ) : (
          <h4>History</h4>
        )}
        {filteredPast.length === 0 ? (
          <p className="ic-case-panel__muted">
            {past.length === 0 ? 'No completed sessions yet.' : `No sessions in ${historyFilterLabel}.`}
          </p>
        ) : (
          <ul className="ic-case-sessions__list ic-case-sessions__list--history">
            {filteredPast.map((s) => {
              const log = logs.find((l) => l.session_id === s.id)
              return (
                <SessionLogHistoryRow
                  key={s.id}
                  session={s}
                  logSummary={log || null}
                  childName={childName}
                  caseCode={caseCode}
                  onSubmitLog={
                    s.status === 'COMPLETED' && !log
                      ? () => openLogForm(s)
                      : undefined
                  }
                  onEditLog={
                    log?.can_edit
                      ? () =>
                          openLogForm(
                            {
                              id: s.id,
                              scheduled_date: s.scheduled_date,
                              actual_start_at: s.actual_start_at,
                              actual_end_at: s.actual_end_at,
                            },
                            { log },
                          )
                      : undefined
                  }
                />
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
