import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { queryKeys } from '../../lib/queryClient.js'
import {
  patchCachesAfterLogSave,
  patchCachesAfterSessionCancel,
  patchCachesAfterSessionEnd,
  patchCachesAfterSessionStart,
  refreshTherapistLogDraftIds,
} from '../../lib/therapistSessionLogCache.js'
import { useTherapistSessionsWorkspace } from '../../hooks/useTherapistHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import {
  actualDurationMinsIST,
  formatDisplayDate,
  formatDisplayDateTimeRange,
  formatSessionActualRange,
  formatTimeIST,
  isStartedLateOnSchedule,
  parseApiDatetime,
} from '../../lib/datetime.js'
import { isLogEditable } from '../../lib/sessionLogUtils.js'
import { TherapistSessionComposer } from '../therapist/TherapistSessionComposer.jsx'
import { SubmitSessionLogForm } from './SubmitSessionLogForm.jsx'
import { SessionLogRecentRow } from './SessionLogRecentRow.jsx'
import { SessionVisitPanel } from './SessionVisitPanel.jsx'
import { resolveSessionDeepLink } from '../../lib/sessionDeepLink.js'
import { redirectForSessionConflict, startClinicalSession } from '../../lib/sessionApi.js'
import { todayIsoIST } from '../../lib/datetime.js'
import { canStartSessionToday, logsPathForSession } from '../../lib/sessionStartRules.js'
import { SameDaySessionDialog } from './SameDaySessionDialog.jsx'
import { EditActualTimesModal } from './EditActualTimesModal.jsx'
import '../cases/my-cases.css'
import '../../styles/goals-strategies-engine.css'
import '../../styles/session-logs-dashboard.css'

function logRecencyMs(log) {
  const ts = log?.resubmitted_at || log?.submitted_at
  return ts ? new Date(ts).getTime() : 0
}

function sortLogsByRecency(list) {
  return [...list].sort((a, b) => logRecencyMs(b) - logRecencyMs(a))
}

const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

function logMatchesMonth(log, year, monthIndex) {
  if (!log?.scheduled_date) return false
  const d = new Date(`${log.scheduled_date}T00:00:00`)
  return d.getFullYear() === year && d.getMonth() === monthIndex
}

const LOG_TABS = [
  { id: 'all', label: 'All logs' },
  { id: 'needs', label: 'Needs log' },
  { id: 'pending', label: 'Pending review' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Rejected' },
]

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
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const now = new Date()
  const [logYear, setLogYear] = useState(now.getFullYear())
  const [logMonth, setLogMonth] = useState(now.getMonth())
  const queryClient = useQueryClient()
  const therapistId = user?.id
  const { data: workspace, isLoading: wsLoading } = useTherapistSessionsWorkspace()
  const logsQuery = useQuery({
    queryKey: queryKeys.therapistDailyLogs(therapistId),
    queryFn: () =>
      apiFetch(
        therapistId
          ? `/api/v1/daily-logs?therapist_user_id=${therapistId}`
          : '/api/v1/daily-logs',
      ),
    enabled: therapistId != null,
  })
  const upcoming = workspace?.upcoming || []
  const active = workspace?.active_session || null
  const needsLog = workspace?.needs_log || []
  const logs = Array.isArray(logsQuery.data) ? logsQuery.data : unwrapList(logsQuery.data || [])
  const caseFilterId = searchParams.get('case_id')
  const scopedToCase = Boolean(caseFilterId)

  const displayLogs = useMemo(() => {
    if (!caseFilterId) return logs
    const id = Number(caseFilterId)
    return logs.filter((l) => l.case_id === id)
  }, [logs, caseFilterId])

  const displayNeedsLog = useMemo(() => {
    if (!caseFilterId) return needsLog
    const id = Number(caseFilterId)
    return needsLog.filter((s) => s.case_id === id)
  }, [needsLog, caseFilterId])

  const loading = wsLoading || logsQuery.isLoading
  const logsReady = !wsLoading && !logsQuery.isLoading
  const [tick, setTick] = useState(Date.now())
  const [draftIds, setDraftIds] = useState(new Set())
  const [logSession, setLogSession] = useState(null)
  const [visitSession, setVisitSession] = useState(null)
  const [visitBusy, setVisitBusy] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [editingLog, setEditingLog] = useState(null)
  const [logRequired, setLogRequired] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [logTab, setLogTab] = useState('all')
  const [expandedLogId, setExpandedLogId] = useState(null)
  const [sameDayConflict, setSameDayConflict] = useState(null)
  const [sameDayPending, setSameDayPending] = useState(null)
  const [editTimesSession, setEditTimesSession] = useState(null)
  const [composerCaseId, setComposerCaseId] = useState(null)
  const logPanelRef = useRef(null)
  const deepLinkResolvedRef = useRef(null)

  const pendingLogs = useMemo(
    () => sortLogsByRecency(displayLogs.filter((l) => l.approval_status === 'PENDING')),
    [displayLogs],
  )
  const approvedLogs = useMemo(
    () => displayLogs.filter((l) => l.approval_status === 'APPROVED'),
    [displayLogs],
  )
  const rejectedLogs = useMemo(
    () => displayLogs.filter((l) => l.approval_status === 'REJECTED'),
    [displayLogs],
  )

  const filterByMonth = useCallback(
    (list) => list.filter((l) => logMatchesMonth(l, logYear, logMonth)),
    [logYear, logMonth],
  )

  const filteredPending = useMemo(() => filterByMonth(pendingLogs), [filterByMonth, pendingLogs])
  const filteredApproved = useMemo(() => filterByMonth(approvedLogs), [filterByMonth, approvedLogs])
  const filteredRejected = useMemo(() => filterByMonth(rejectedLogs), [filterByMonth, rejectedLogs])
  const filteredAll = useMemo(
    () => sortLogsByRecency(filterByMonth(displayLogs)),
    [filterByMonth, displayLogs],
  )

  const displayUpcoming = useMemo(() => {
    const caseId = composerCaseId || (caseFilterId ? Number(caseFilterId) : null)
    if (!caseId) return upcoming
    return upcoming.filter((s) => s.case_id === caseId)
  }, [upcoming, composerCaseId, caseFilterId])

  const scopedCaseLabel = useMemo(() => {
    if (!caseFilterId) return ''
    const id = Number(caseFilterId)
    const fromLog = logs.find((l) => l.case_id === id)
    if (fromLog?.child_name || fromLog?.case_code) {
      return fromLog.child_name || fromLog.case_code
    }
    const fromNeed = needsLog.find((s) => s.case_id === id)
    if (fromNeed?.child_name || fromNeed?.case_code) {
      return fromNeed.child_name || fromNeed.case_code
    }
    const fromUpcoming = upcoming.find((s) => s.case_id === id)
    if (fromUpcoming?.child_name || fromUpcoming?.case_code) {
      return fromUpcoming.child_name || fromUpcoming.case_code
    }
    return `Case #${caseFilterId}`
  }, [caseFilterId, logs, needsLog, upcoming])

  const logYears = useMemo(() => {
    const years = new Set([now.getFullYear()])
    displayLogs.forEach((l) => {
      if (l.scheduled_date) years.add(Number(l.scheduled_date.slice(0, 4)))
    })
    return [...years].filter(Number.isFinite).sort((a, b) => b - a)
  }, [displayLogs, now])

  useEffect(() => {
    if (caseFilterId) setComposerCaseId(Number(caseFilterId))
  }, [caseFilterId])

  const syncDraftIds = useCallback(async () => {
    const ids = await refreshTherapistLogDraftIds()
    setDraftIds(ids)
  }, [])

  const loadAll = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setError('')
    try {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.therapistWorkspace }),
        queryClient.invalidateQueries({ queryKey: queryKeys.therapistDailyLogs(therapistId) }),
      ])
      await syncDraftIds()
    } catch (err) {
      setError(err.message || 'Could not load sessions')
    }
  }, [queryClient, therapistId, syncDraftIds])

  useEffect(() => {
    loadAll({ silent: true })
  }, [loadAll])

  useEffect(() => {
    if (!active?.actual_start_at) return undefined
    const id = setInterval(() => setTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [active?.actual_start_at, active?.id])

  useEffect(() => {
    if ((logSession || visitSession) && logPanelRef.current) {
      logPanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [logSession?.id, editingLog?.id, visitSession?.id])

  function clearSessionQueryParam() {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('session')
        return next
      },
      { replace: true },
    )
  }

  function openSessionFromDeepLink(session) {
    setError('')
    const action = resolveSessionDeepLink(session, logs)
    if (action.type === 'error') {
      setError(action.message || 'Could not open session')
      return
    }
    if (action.type === 'log') {
      setVisitSession(null)
      openLogForm(action.session, { required: action.required, log: action.log || null })
      return
    }
    if (action.type === 'readonly') {
      setVisitSession(null)
      openLogForm(action.session, { log: action.log, readOnly: true })
      return
    }
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
    setExpandedLogId(null)
    setVisitSession(action.session)
  }

  function openViewLog(log) {
    setVisitSession(null)
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
    setError('')
    setSuccess('')
    setExpandedLogId(log.id)
  }

  function logSessionPayload(log) {
    return {
      id: log.session_id,
      scheduled_date: log.scheduled_date,
      actual_start_at: log.actual_start_at,
      actual_end_at: log.actual_end_at,
      edited_start_at: log.edited_start_at,
      edited_end_at: log.edited_end_at,
      actual_times_edited: log.actual_times_edited,
      case_code: log.case_code,
      child_name: log.child_name,
      status: 'COMPLETED',
    }
  }

  function openResubmitFromRow(log) {
    setExpandedLogId(null)
    openLogForm(logSessionPayload(log), { log })
  }

  function openEditLogFromRow(log) {
    setExpandedLogId(null)
    openLogForm(logSessionPayload(log), { log })
  }

  function openEditTimesFromRow(log) {
    setEditTimesSession({
      id: log.session_id,
      actual_start_at: log.actual_start_at,
      actual_end_at: log.actual_end_at,
      edited_start_at: log.edited_start_at,
      edited_end_at: log.edited_end_at,
      child_name: log.child_name,
      case_code: log.case_code,
      status: 'COMPLETED',
    })
  }

  function renderLogRow(l, options = {}) {
    return (
      <SessionLogRecentRow
        key={l.id}
        log={l}
        expanded={expandedLogId === l.id}
        onToggleExpand={(id) => setExpandedLogId(id)}
        onEditLog={openEditLogFromRow}
        onResubmitLog={openResubmitFromRow}
        onEditTimes={openEditTimesFromRow}
        {...options}
      />
    )
  }

  function openLogForm(session, { required = false, log = null, readOnly = false } = {}) {
    setVisitSession(null)
    setError('')
    if (readOnly && log) {
      openViewLog(log)
      return
    }
    setExpandedLogId(null)
    setLogSession(session)
    setEditingLog(log)
    setLogRequired(required)
    setSuccess('')
  }

  useEffect(() => {
    const sessionId = searchParams.get('session')
    if (!sessionId || !logsReady) return
    const sid = Number(sessionId)
    if (!Number.isFinite(sid)) return
    if (deepLinkResolvedRef.current === sid) return

    const match =
      needsLog.find((s) => s.id === sid) ||
      upcoming.find((s) => s.id === sid) ||
      (active?.id === sid ? active : null)

    if (match) {
      deepLinkResolvedRef.current = sid
      openSessionFromDeepLink(match)
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const session = await apiFetch(`/api/v1/sessions/${sid}`)
        if (cancelled) return
        deepLinkResolvedRef.current = sid
        openSessionFromDeepLink(session)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || `Could not open session ${sid}`)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [searchParams, logsReady, needsLog, upcoming, active, logs])

  useEffect(() => {
    if (!searchParams.get('session')) {
      deepLinkResolvedRef.current = null
    }
  }, [searchParams])

  function closeLogForm() {
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
    setExpandedLogId(null)
    clearSessionQueryParam()
  }

  function closeVisitFocus() {
    setVisitSession(null)
    clearSessionQueryParam()
  }

  async function handleVisitStart(sessionId) {
    setVisitBusy(true)
    setError('')
    try {
      await handleStart(sessionId)
      closeVisitFocus()
    } finally {
      setVisitBusy(false)
    }
  }

  async function handleVisitEnd(sessionId) {
    setVisitBusy(true)
    try {
      await handleEnd(sessionId)
      setVisitSession(null)
    } finally {
      setVisitBusy(false)
    }
  }

  async function handleStart(sessionId, sessionMeta = null, { allowDuplicate = false } = {}) {
    setError('')
    setSuccess('')
    const meta =
      sessionMeta ||
      upcoming.find((s) => s.id === sessionId) ||
      needsLog.find((s) => s.id === sessionId) ||
      { id: sessionId, scheduled_date: todayIsoIST() }
    const guard = canStartSessionToday(meta)
    if (!guard.ok) {
      setError(guard.message)
      return
    }
    try {
      const result = await startClinicalSession(
        sessionId,
        meta,
        therapistId,
        allowDuplicate ? { allow_duplicate: true } : {},
      )
      if (!result.ok) {
        if (result.conflict?.recommendedAction === 'DUPLICATE_SAME_DAY') {
          setSameDayConflict(result.conflict)
          setSameDayPending({ sessionId, meta })
          return
        }
        setSuccess(result.message)
        redirectForSessionConflict(result.conflict, navigate)
        return
      }
      setSameDayConflict(null)
      setSameDayPending(null)
      const started = result.session
      patchCachesAfterSessionStart(started)
      if (started?.invite_sent && started?.invite_email) {
        setSuccess(`Invite sent to ${started.invite_email} — they will join the Client portal.`)
      }
    } catch (err) {
      setError(err.message || 'Could not start session')
    }
  }

  async function handleSameDayStartAnother() {
    if (!sameDayPending) return
    setVisitBusy(true)
    try {
      await handleStart(sameDayPending.sessionId, sameDayPending.meta, { allowDuplicate: true })
      setSameDayConflict(null)
      setSameDayPending(null)
    } finally {
      setVisitBusy(false)
    }
  }

  function handleEditExistingSession(existingId) {
    setSameDayConflict(null)
    setSameDayPending(null)
    navigate(logsPathForSession(existingId))
  }

  function handleActualTimesSaved(updated) {
    queryClient.invalidateQueries({ queryKey: queryKeys.therapistDailyLogs(therapistId) })
    if (updated?.id && logSession?.id === updated.id) {
      setLogSession((prev) => (prev ? { ...prev, ...updated } : updated))
    }
    if (editingLog?.approval_status === 'REJECTED') {
      setSuccess('Times updated — resubmit the log when you are ready.')
    } else {
      setSuccess('Times corrected — log is pending review again.')
    }
  }

  function openEditTimesForSession(session) {
    setEditTimesSession({
      id: session.id,
      actual_start_at: session.actual_start_at,
      actual_end_at: session.actual_end_at,
      edited_start_at: session.edited_start_at,
      edited_end_at: session.edited_end_at,
      child_name: session.child_name,
      case_code: session.case_code,
      status: session.status,
    })
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
    } catch (err) {
      setError(err.message || 'Could not end session')
    }
  }

  async function handleCancel(sessionId) {
    if (!window.confirm('Cancel this session? The timer will stop and no log will be created.')) return
    setCancelBusy(true)
    setError('')
    try {
      const cancelled = await apiFetch(`/api/v1/sessions/${sessionId}/cancel`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      patchCachesAfterSessionCancel(cancelled)
      if (visitSession?.id === sessionId) setVisitSession(null)
      setSuccess('Session cancelled — you can start again when ready.')
    } catch (err) {
      setError(err.message || 'Could not cancel session')
    } finally {
      setCancelBusy(false)
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
      void loadAll({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not add session')
    } finally {
      setSubmitting(false)
    }
  }

  const showComposer = !logSession && !visitSession && !active

  if (loading && !logSession && !visitSession) {
    return <p style={{ padding: 24, color: '#6b7280' }}>Loading session logs…</p>
  }

  return (
    <div className="daily-logs-page session-logs-page forest-light ic-my-cases">
      <header className="session-logs-header">
        <div>
          <h1 className="session-logs-header__title">Session Logs</h1>
          <p className="session-logs-header__subtitle">
            End each visit with a log so admin can review and families get timely updates. Edit pending logs for 24 hours.
          </p>
        </div>
      </header>

      {scopedToCase ? (
        <div className="session-logs-scope-banner">
          <p style={{ margin: 0 }}>
            Showing logs for <strong>{scopedCaseLabel}</strong>
          </p>
          <button
            type="button"
            className="reports-hub-btn reports-hub-btn--secondary"
            onClick={() => setSearchParams({}, { replace: true })}
          >
            All clients
          </button>
        </div>
      ) : null}

      {error ? (
        <div className="ic-alert ic-alert--error">{error}</div>
      ) : null}
      {success ? (
        <div className="ic-alert ic-alert--success">{success}</div>
      ) : null}

      {active ? (
        <section className="session-logs-active-card">
          <p className="session-logs-active-card__title">Session in progress</p>
          <p style={{ margin: '0 0 4px', fontSize: '0.875rem' }}>
            {active.child_name || active.case_code} · {formatDisplayDate(active.scheduled_date)}
            {active.auto_end_label ? (
              <span style={{ display: 'block', marginTop: 4, fontSize: '0.8125rem', fontWeight: 600, color: '#b45309' }}>
                {active.auto_end_label}
              </span>
            ) : active.auto_ended ? (
              <span style={{ color: '#b45309' }}> (auto-ended)</span>
            ) : null}
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
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            <button
              type="button"
              className="ic-btn ic-btn--primary"
              style={{ background: '#dc2626', borderColor: '#dc2626' }}
              onClick={() => handleEnd(active.id)}
            >
              End session & write log
            </button>
            <button
              type="button"
              className="ic-btn ic-btn--ghost"
              disabled={cancelBusy}
              onClick={() => handleCancel(active.id)}
            >
              {cancelBusy ? 'Cancelling…' : 'Cancel session'}
            </button>
          </div>
        </section>
      ) : null}

      {visitSession ? (
        <section ref={logPanelRef} className="ic-session-log-panel-wrap" style={{ marginBottom: 24 }}>
          <SessionVisitPanel
            session={visitSession}
            activeSessionId={active?.id}
            busy={visitBusy}
            onStart={handleVisitStart}
            onEnd={handleVisitEnd}
            onCancel={handleCancel}
            onClose={closeVisitFocus}
          />
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
            onEditTimes={() => openEditTimesForSession(logSession)}
            onSuccess={(savedLog) => {
              const wasResubmit = editingLog?.approval_status === 'REJECTED' && savedLog?.approval_status === 'PENDING'
              setSuccess(
                wasResubmit
                  ? 'Log resubmitted — pending admin review.'
                  : editingLog
                    ? 'Session log updated.'
                    : 'Session log submitted — pending admin review.',
              )
              closeLogForm()
              patchCachesAfterLogSave({
                userId: therapistId,
                sessionId: logSession?.id,
                savedLog,
                isEdit: Boolean(editingLog),
              })
              void syncDraftIds()
            }}
            onCancel={logRequired && !editingLog ? undefined : closeLogForm}
          />
        </section>
      ) : null}

      {showComposer ? (
        <TherapistSessionComposer
          lockCaseId={caseFilterId ? Number(caseFilterId) : null}
          lockCaseLabel={scopedCaseLabel}
          caseProfileMode={false}
          upcomingSessions={upcoming}
          disabled={!!active}
          onSelectedCaseChange={setComposerCaseId}
          onSessionStarted={(info) => {
            if (info?.message) setSuccess(info.message)
            void loadAll({ silent: true })
          }}
          onManualSession={handleManualSession}
          onError={setError}
        />
      ) : null}

      {!active && displayNeedsLog.length > 0 && !logSession ? (
        <section className="session-logs-needs">
          <h3 className="session-logs-needs__title">Needs log</h3>
          <p className="session-logs-needs__sub">
            These visits ended without a log. Submit now so billing and family updates are not delayed.
          </p>
          <div className="session-logs-needs__list">
            {displayNeedsLog.map((s) => (
              <button
                key={s.id}
                type="button"
                className="session-logs-needs__item"
                onClick={() => openSessionFromDeepLink(s)}
              >
                <span>
                  <strong>{s.child_name || s.case_code}</strong> · {formatDisplayDate(s.scheduled_date)}
                  {draftIds.has(s.id) ? (
                    <span className="ic-session-log-needs__draft"> · Draft saved</span>
                  ) : null}
                </span>
                <span className="session-logs-needs__cta">{draftIds.has(s.id) ? 'Continue log' : 'Complete log'}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {!logSession ? (
        <section className="session-logs-upcoming">
          <h3 className="session-logs-upcoming__title">Upcoming sessions</h3>
          {displayUpcoming.length === 0 ? (
            <p className="session-logs-upcoming__empty">
              {caseFilterId || composerCaseId
                ? 'No upcoming sessions for this client.'
                : 'No scheduled sessions in the next two weeks.'}
            </p>
          ) : (
            <div className="session-logs-upcoming__list">
              {displayUpcoming.map((s) => {
                const startedLate = isStartedLateOnSchedule(s.actual_start_at, s.scheduled_date, s.start_time)
                const actualStart = formatTimeIST(s.actual_start_at)
                const actualEnd = formatTimeIST(s.actual_end_at)
                const durMins = actualDurationMinsIST(s.actual_start_at, s.actual_end_at)
                const isInProgress = s.status === 'IN_PROGRESS'
                const isCompleted = s.status === 'COMPLETED'
                return (
                  <article
                    key={s.id}
                    className={`session-logs-upcoming__card${isInProgress ? ' session-logs-upcoming__card--live' : ''}`}
                  >
                    <div style={{ flex: 1, minWidth: 160 }}>
                      <strong>
                        {composerCaseId
                          ? formatDisplayDate(s.scheduled_date)
                          : s.child_name || s.case_code}
                      </strong>
                      <p style={{ margin: '4px 0 0', fontSize: '0.78rem', color: '#9ca3af' }}>
                        {composerCaseId ? (
                          <>
                            {String(s.start_time || '').slice(0, 5)}–{String(s.end_time || '').slice(0, 5)}
                            {s.case_id ? (
                              <>
                                {' · '}
                                <Link to={`/therapist/cases/${s.case_id}`}>View case</Link>
                              </>
                            ) : null}
                          </>
                        ) : (
                          <>
                            Scheduled: {formatDisplayDateTimeRange(s.scheduled_date, s.start_time, s.end_time)}
                            {s.case_id ? (
                              <>
                                {' · '}
                                <Link to={`/therapist/cases/${s.case_id}`}>View case</Link>
                              </>
                            ) : null}
                          </>
                        )}
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
                    {!active && canStartSessionToday(s).ok ? (
                      <button
                        type="button"
                        onClick={() => handleStart(s.id, s)}
                        className="ic-btn ic-btn--primary"
                      >
                        Start session
                      </button>
                    ) : !active && s.scheduled_date > todayIsoIST() ? (
                      <span className="ic-session-log-recent__meta">Opens on visit day</span>
                    ) : null}
                  </article>
                )
              })}
            </div>
          )}
        </section>
      ) : null}

      <section className="session-logs-history">
        <div className="session-logs-history__filters">
          <label>
            <span className="sr-only">Month</span>
            <select
              value={logMonth}
              onChange={(e) => setLogMonth(Number(e.target.value))}
              aria-label="Filter logs by month"
              className="ic-case-panel__select"
            >
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
              value={logYear}
              onChange={(e) => setLogYear(Number(e.target.value))}
              aria-label="Filter logs by year"
              className="ic-case-panel__select"
            >
              {logYears.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="session-logs-tabs" role="tablist" aria-label="Session log lists">
          {LOG_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={logTab === t.id}
              className={`session-logs-tabs__btn${logTab === t.id ? ' is-active' : ''}`}
              onClick={() => setLogTab(t.id)}
            >
              {t.label}
              {t.id === 'needs' && displayNeedsLog.length > 0 ? (
                <span className="session-logs-tabs__count">{displayNeedsLog.length}</span>
              ) : null}
              {t.id === 'pending' && pendingLogs.length > 0 ? (
                <span className="session-logs-tabs__count session-logs-tabs__count--amber">{pendingLogs.length}</span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="ic-session-log-tab-panel" role="tabpanel">
          {logTab === 'needs' ? (
            displayNeedsLog.length === 0 ? (
              <p className="ic-empty-hint">No sessions waiting for a log.</p>
            ) : (
              <div className="ic-session-log-recent">
                {displayNeedsLog.map((s) => (
                  <div key={s.id} className="ic-session-log-recent__row">
                    <div style={{ flex: 1 }}>
                      <p className="ic-session-log-recent__title">
                        {s.child_name || s.case_code} · {formatDisplayDate(s.scheduled_date)}
                      </p>
                      <span className="ic-session-log-recent__meta">
                        Completed — log required
                        {draftIds.has(s.id) ? (
                          <span className="ic-session-log-recent__draft"> · Draft saved</span>
                        ) : null}
                      </span>
                    </div>
                    <button
                      type="button"
                      className="ic-btn ic-btn--primary"
                      onClick={() => openSessionFromDeepLink(s)}
                    >
                      {draftIds.has(s.id) ? 'Continue log' : 'Write log'}
                    </button>
                  </div>
                ))}
              </div>
            )
          ) : null}

          {logTab === 'pending' ? (
            filteredPending.length === 0 ? (
              <p className="ic-empty-hint">No logs pending admin review for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredPending.map((l) =>
                  renderLogRow(l, {
                    allowEdit: isLogEditable(l),
                    allowView: !isLogEditable(l),
                  }),
                )}
              </div>
            )
          ) : null}

          {logTab === 'approved' ? (
            filteredApproved.length === 0 ? (
              <p className="ic-empty-hint">No approved logs for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredApproved.map((l) => renderLogRow(l, { allowView: true }))}
              </div>
            )
          ) : null}

          {logTab === 'rejected' ? (
            filteredRejected.length === 0 ? (
              <p className="ic-empty-hint">No rejected logs for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredRejected.map((l) => renderLogRow(l, { allowResubmit: true, allowView: true }))}
              </div>
            )
          ) : null}

          {logTab === 'all' ? (
            filteredAll.length === 0 ? (
              <p className="ic-empty-hint">No logs for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredAll.map((l) =>
                  renderLogRow(l, {
                    allowEdit: l.approval_status === 'PENDING',
                    allowResubmit: l.approval_status === 'REJECTED',
                    allowView: l.approval_status === 'APPROVED' || (l.approval_status === 'PENDING' && !isLogEditable(l)),
                  }),
                )}
              </div>
            )
          ) : null}
        </div>
      </section>

      <SameDaySessionDialog
        open={Boolean(sameDayConflict)}
        conflict={sameDayConflict}
        busy={visitBusy}
        onEditExisting={handleEditExistingSession}
        onStartAnother={handleSameDayStartAnother}
        onClose={() => {
          setSameDayConflict(null)
          setSameDayPending(null)
        }}
      />
      <EditActualTimesModal
        open={Boolean(editTimesSession)}
        session={editTimesSession}
        onClose={() => setEditTimesSession(null)}
        onSaved={handleActualTimesSaved}
      />
    </div>
  )
}
