import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../lib/apiClient.js'
import { clearLogDraft } from '../../lib/logDraftStore.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { focusRefetchLive, queryKeys } from '../../lib/queryClient.js'
import {
  patchCachesAfterLogSave,
  patchCachesAfterPendingLogDiscarded,
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
} from '../../lib/datetime.js'
import { isLogEditable, isLogResubmittable } from '../../lib/sessionLogUtils.js'
import { SessionLogStatusBadge } from './SessionLogStatusBadge.jsx'
import { DownloadApprovedLogButton } from '../shared/DownloadApprovedLogButton.jsx'
import { TherapistSessionComposer } from '../therapist/TherapistSessionComposer.jsx'
import { SubmitSessionLogForm } from './SubmitSessionLogForm.jsx'
import { SessionLogReadOnly } from './SessionLogReadOnly.jsx'
import { SessionVisitPanel } from './SessionVisitPanel.jsx'
import { resolveSessionDeepLink } from '../../lib/sessionDeepLink.js'
import { existingVisitForDay, sessionToLogShape } from '../../lib/sessionDayConflict.js'
import { redirectForSessionConflict, startClinicalSession } from '../../lib/sessionApi.js'
import { todayIsoIST } from '../../lib/datetime.js'
import { canStartSessionToday, getBlockingLogForCase, isAbsenceConflict, isPendingLogBlock, resolveBlockingLogSession } from '../../lib/sessionStartRules.js'
import { PendingLogGate, discardPendingLogWithDraft } from './PendingLogGate.jsx'
import { EditActualTimesModal } from './EditActualTimesModal.jsx'
import { ActiveSessionCard } from './ActiveSessionCard.jsx'
import { canEditSessionTimes, formatClockRange, formatEditedRange } from '../../lib/sessionTimes.js'
import {
  filterSessionsWithoutAbsence,
  isChildAbsentLog,
  isLeaveLog,
  sortLogsBySessionDate,
} from '../../lib/sessionLogFilters.js'
import { formatLogCommentCount, enrichLogsWithCommentCounts } from '../../lib/sessionLogComments.js'
import { LogCommentCountPill } from '../shared/LogCommentCountBadge.jsx'
import '../cases/my-cases.css'

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
  { id: 'child_absent', label: 'Child absent' },
  { id: 'leave', label: 'Leave' },
  { id: 'pending', label: 'Pending review' },
  { id: 'approved', label: 'Approved' },
  { id: 'rejected', label: 'Rejected' },
]

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
    queryFn: async () => {
      const data = await apiFetch(
        therapistId
          ? `/api/v1/daily-logs?therapist_user_id=${therapistId}`
          : '/api/v1/daily-logs',
      )
      const rows = Array.isArray(data) ? data : unwrapList(data || [])
      return enrichLogsWithCommentCounts(rows, apiFetch)
    },
    enabled: therapistId != null,
    refetchOnWindowFocus: focusRefetchLive,
  })
  const upcomingRaw = workspace?.upcoming || []
  const active = workspace?.active_session || null
  const activeInProgress = active?.status === 'IN_PROGRESS' ? active : null
  const stalePrevious = workspace?.stale_previous_sessions || []
  const needsLogRaw = workspace?.needs_log || []
  const logs = Array.isArray(logsQuery.data) ? logsQuery.data : unwrapList(logsQuery.data || [])
  const needsLog = useMemo(
    () => filterSessionsWithoutAbsence(needsLogRaw, logs),
    [needsLogRaw, logs],
  )
  const upcoming = useMemo(
    () => filterSessionsWithoutAbsence(upcomingRaw, logs),
    [upcomingRaw, logs],
  )
  const loading = wsLoading || logsQuery.isLoading
  const logsReady = !wsLoading && !logsQuery.isLoading
  const [tick, setTick] = useState(Date.now())
  const [draftIds, setDraftIds] = useState(new Set())
  const [logSession, setLogSession] = useState(null)
  const [visitSession, setVisitSession] = useState(null)
  const [visitBusy, setVisitBusy] = useState(false)
  const [endBusy, setEndBusy] = useState(false)
  const [cancelBusy, setCancelBusy] = useState(false)
  const [editingLog, setEditingLog] = useState(null)
  const [logRequired, setLogRequired] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [discardBusy, setDiscardBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const handleRetry = () => {
    setError('')
    queryClient.invalidateQueries({ queryKey: queryKeys.therapistWorkspace })
    if (therapistId) {
      queryClient.invalidateQueries({ queryKey: queryKeys.therapistDailyLogs(therapistId) })
    }
  }
  const [logTab, setLogTab] = useState('all')
  const [viewingLog, setViewingLog] = useState(null)
  const [editTimesSession, setEditTimesSession] = useState(null)
  const [composerCaseId, setComposerCaseId] = useState(null)
  const [existingSessionConflict, setExistingSessionConflict] = useState(null)
  const [walkInConflict, setWalkInConflict] = useState(null)
  const [scheduledSessionHint, setScheduledSessionHint] = useState('')
  const logPanelRef = useRef(null)
  const activeSessionCardRef = useRef(null)
  const upcomingSectionRef = useRef(null)
  const deepLinkResolvedRef = useRef(null)
  const logDeepLinkResolvedRef = useRef(null)

  function handleLogCommentCountChange(logId, commentCount, openParentCommentCount = 0) {
    if (therapistId) {
      queryClient.setQueryData(queryKeys.therapistDailyLogs(therapistId), (prev) => {
        const rows = Array.isArray(prev) ? prev : []
        return rows.map((entry) =>
          entry.id === logId
            ? {
                ...entry,
                comment_count: commentCount,
                open_parent_comment_count: openParentCommentCount,
              }
            : entry,
        )
      })
    }
    setViewingLog((prev) =>
      prev && prev.log?.id === logId
        ? {
            ...prev,
            log: {
              ...prev.log,
              comment_count: commentCount,
              open_parent_comment_count: openParentCommentCount,
            },
          }
        : prev,
    )
  }

  const pendingLogs = useMemo(
    () => sortLogsBySessionDate(logs.filter((l) => l.approval_status === 'PENDING')),
    [logs],
  )
  const approvedLogs = useMemo(
    () => sortLogsBySessionDate(logs.filter((l) => l.approval_status === 'APPROVED')),
    [logs],
  )
  const rejectedLogs = useMemo(
    () => sortLogsBySessionDate(logs.filter((l) => l.approval_status === 'REJECTED')),
    [logs],
  )
  const childAbsentLogs = useMemo(() => logs.filter(isChildAbsentLog), [logs])
  const leaveLogs = useMemo(() => logs.filter(isLeaveLog), [logs])

  const filterByMonth = useCallback(
    (list) => list.filter((l) => logMatchesMonth(l, logYear, logMonth)),
    [logYear, logMonth],
  )

  const filteredPending = useMemo(() => filterByMonth(pendingLogs), [filterByMonth, pendingLogs])
  const filteredApproved = useMemo(() => filterByMonth(approvedLogs), [filterByMonth, approvedLogs])
  const filteredRejected = useMemo(() => filterByMonth(rejectedLogs), [filterByMonth, rejectedLogs])
  const filteredChildAbsent = useMemo(
    () => sortLogsBySessionDate(filterByMonth(childAbsentLogs)),
    [filterByMonth, childAbsentLogs],
  )
  const filteredLeave = useMemo(
    () => sortLogsBySessionDate(filterByMonth(leaveLogs)),
    [filterByMonth, leaveLogs],
  )
  const filteredAll = useMemo(
    () => sortLogsBySessionDate(filterByMonth(logs)),
    [filterByMonth, logs],
  )
  const filteredNeedsLog = useMemo(
    () => needsLog.filter((s) => logMatchesMonth(s, logYear, logMonth)),
    [needsLog, logYear, logMonth],
  )

  const displayUpcoming = useMemo(() => {
    if (!composerCaseId) return upcoming
    return upcoming.filter((s) => s.case_id === composerCaseId)
  }, [upcoming, composerCaseId])

  const composerBlockingSession = useMemo(
    () => (composerCaseId ? getBlockingLogForCase(needsLog, composerCaseId) : null),
    [needsLog, composerCaseId],
  )
  const pendingLogBlockedForComposer =
    Boolean(composerBlockingSession) && !activeInProgress

  useEffect(() => {
    setScheduledSessionHint('')
  }, [composerCaseId])

  function scrollToUpcomingSessions() {
    requestAnimationFrame(() => {
      upcomingSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    })
  }

  function handleScheduledSessionExists(info) {
    setWalkInConflict(null)
    setScheduledSessionHint(
      info?.message || 'A scheduled session already exists for this client today.',
    )
    void loadAll({ silent: true }).then(() => scrollToUpcomingSessions())
  }

  function handleWalkInSessionConflict(detail) {
    setScheduledSessionHint('')
    setWalkInConflict(detail)
  }

  function dismissWalkInConflict() {
    setWalkInConflict(null)
  }

  const logYears = useMemo(() => {
    const years = new Set([now.getFullYear()])
    logs.forEach((l) => {
      if (l.scheduled_date) years.add(Number(l.scheduled_date.slice(0, 4)))
    })
    return [...years].filter(Number.isFinite).sort((a, b) => b - a)
  }, [logs, now])

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
    if (!activeInProgress?.actual_start_at) return undefined
    const id = setInterval(() => setTick(Date.now()), 1000)
    return () => clearInterval(id)
  }, [activeInProgress?.actual_start_at, activeInProgress?.id])

  useEffect(() => {
    if ((logSession || visitSession) && logPanelRef.current) {
      // Prefer nearest so we don't scroll the document past #root padding / shell chrome
      // (block: 'start' squashes the therapist portal top when opening from notifications).
      logPanelRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }
  }, [logSession?.id, editingLog?.id, visitSession?.id])

  function clearSessionQueryParam() {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.delete('session')
        next.delete('log_id')
        return next
      },
      { replace: true },
    )
  }

  const deepLinkContext = useMemo(
    () => ({ active: activeInProgress, needsLog, logs }),
    [activeInProgress, needsLog, logs],
  )

  function openSessionFromDeepLink(session) {
    setError('')
    const action = resolveSessionDeepLink(session, logs, deepLinkContext)
    if (action.type === 'error') {
      setError(action.message || 'Could not open session')
      return
    }
    if (action.type === 'log') {
      setVisitSession(null)
      if (action.fetchLog && action.session?.has_daily_log) {
        void (async () => {
          try {
            const match = logs.find((l) => Number(l.session_id) === Number(action.session.id) && l.id > 0)
            if (match) {
              openLogForm(action.session, { required: action.required, log: match })
              return
            }
            await loadAll({ silent: true })
            const refreshed = queryClient.getQueryData(queryKeys.therapistDailyLogs(therapistId))
            const list = Array.isArray(refreshed) ? refreshed : []
            const found = list.find((l) => Number(l.session_id) === Number(action.session.id) && l.id > 0)
            openLogForm(action.session, { required: action.required, log: found || null })
          } catch (err) {
            setError(err.message || 'Could not open session log')
          }
        })()
        return
      }
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
    setViewingLog(null)
    setVisitSession(action.session)
  }

  function openLogForm(session, { required = false, log = null, readOnly = false } = {}) {
    setVisitSession(null)
    setError('')
    setViewingLog(null)
    if (readOnly && log) {
      setLogSession(null)
      setEditingLog(null)
      setLogRequired(false)
      setViewingLog({ log, session })
      setSuccess('')
      return
    }
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
      (activeInProgress?.id === sid ? activeInProgress : null)

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
  }, [searchParams, logsReady, needsLog, upcoming, activeInProgress, logs])

  useEffect(() => {
    if (!searchParams.get('session')) {
      deepLinkResolvedRef.current = null
    }
  }, [searchParams])

  useEffect(() => {
    const logIdParam = searchParams.get('log_id')
    if (!logIdParam || !logsReady) return
    const lid = Number(logIdParam)
    if (!Number.isFinite(lid)) return
    if (logDeepLinkResolvedRef.current === lid) return

    let cancelled = false
    ;(async () => {
      try {
        let log = logs.find((l) => Number(l.id) === lid)
        if (!log) {
          log = await apiFetch(`/api/v1/daily-logs/${lid}`)
        }
        if (cancelled || !log) return
        let session = null
        if (log.session_id) {
          session = await apiFetch(`/api/v1/sessions/${log.session_id}`).catch(() => ({
            id: log.session_id,
            case_code: log.case_code,
            child_name: log.child_name,
            scheduled_date: log.scheduled_date,
          }))
        }
        logDeepLinkResolvedRef.current = lid
        openLogForm(session || { id: log.session_id }, { readOnly: true, log })
        setTimeout(() => {
          logPanelRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        }, 120)
      } catch (err) {
        if (!cancelled) {
          setError(err.message || `Could not open session log ${lid}`)
        }
      }
    })()

    return () => {
      cancelled = true
    }
  }, [searchParams, logsReady, logs])

  useEffect(() => {
    if (!searchParams.get('log_id')) {
      logDeepLinkResolvedRef.current = null
    }
  }, [searchParams])

  function closeLogForm() {
    setLogSession(null)
    setEditingLog(null)
    setLogRequired(false)
    setViewingLog(null)
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

  function renderLogRow(l, { allowEdit = false, allowResubmit = false, allowView = false } = {}) {
    const isVirtual = l.id < 0
    const isAbsenceRecord =
      isVirtual ||
      l.attendance_status === 'THERAPIST_LEAVE' ||
      l.attendance_status === 'CLIENT_ABSENT' ||
      l.attendance_status === 'CLIENT_LEAVE'
    const isTherapistLeave = l.attendance_status === 'THERAPIST_LEAVE'
    const canEdit = !isVirtual && allowEdit && isLogEditable(l)
    const canResubmit = !isVirtual && allowResubmit && isLogResubmittable(l)
    const clockRange = isVirtual ? null : formatClockRange(l)
    const editedRange = !isVirtual && l.actual_times_edited ? formatEditedRange(l) : null
    return (
      <div key={l.id} className="ic-session-log-recent__row">
        <div style={{ flex: 1, minWidth: 0 }}>
          <p className="ic-session-log-recent__title">
            {l.child_name || l.case_code}
            {l.scheduled_date ? <> · {formatDisplayDate(l.scheduled_date)}</> : null}
            {formatLogCommentCount(l.comment_count) ? (
              <span className="ic-session-log-recent__comment-count"> · {formatLogCommentCount(l.comment_count)}</span>
            ) : null}
          </p>
          {clockRange ? <p className="ic-session-log-recent__times">Clock: {clockRange}</p> : null}
          {editedRange ? (
            <p className="ic-session-log-recent__times" style={{ color: '#6d28d9' }}>
              Corrected: {editedRange}
            </p>
          ) : null}
          {!isTherapistLeave ? (
            <div className="ic-log-badge-row" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              <SessionLogStatusBadge
                approvalStatus={l.approval_status}
                attendanceStatus={l.attendance_status}
                isAbsenceRecord={isAbsenceRecord}
              />
              {!isVirtual && (l.mentor_reviewed || l.mentor_reviewed_at) ? (
                <span className="ic-badge ic-badge--neutral" style={{ background: '#e0f2fe', color: '#0369a1' }}>
                  Reviewed by mentor
                </span>
              ) : null}
              {formatLogCommentCount(l.comment_count) ? (
                <LogCommentCountPill count={l.comment_count} className="log-comment-count-pill--inline" />
              ) : null}
            </div>
          ) : (
            <div className="ic-log-badge-row">
              <span className="ic-badge ic-badge--neutral" style={{ background: '#f3f4f6', color: '#374151' }}>
                Therapist Leave
              </span>
              <span className={`ic-log-badge ${l.approval_status === 'PENDING' ? 'ic-log-badge--pending' : 'ic-log-badge--approved'}`}>
                {l.approval_status === 'PENDING' ? 'Pending review' : 'Approved'}
              </span>
            </div>
          )}
          {!isVirtual && l.actual_times_edited ? (
            <span className="ic-session-log-recent__meta" style={{ color: '#7c3aed', fontWeight: 600 }}>
              Times edited
            </span>
          ) : null}
          {!isVirtual && l.duplicate_day_session ? (
            <span className="ic-session-log-recent__meta" style={{ color: '#b45309', fontWeight: 600 }}>
              Same-day duplicate
            </span>
          ) : null}
          {!isVirtual && l.review_note && l.approval_status === 'REJECTED' ? (
            <p className="ic-session-log-recent__meta" style={{ color: '#b91c1c' }}>
              Rejection: {l.review_note}
            </p>
          ) : null}
          {l.status_label && !isAbsenceRecord ? (
            <span className="ic-session-log-recent__meta" style={{ color: '#b45309', fontWeight: 600 }}>
              {l.status_label}
            </span>
          ) : (!isVirtual && l.late_addition) ? (
            <span className="ic-session-log-recent__meta">Late submission</span>
          ) : null}
          {isVirtual && l.absence_reason ? (
            <p className="ic-session-log-recent__meta" style={{ color: '#4b5563', fontStyle: 'italic' }}>
              Reason: {l.absence_reason}
            </p>
          ) : null}
          {l.case_id ? (
            <span className="ic-session-log-recent__meta">
              <Link to={`/therapist/cases/${l.case_id}`}>Open case</Link>
            </span>
          ) : null}
        </div>
        {isTherapistLeave ? (
          <button
            type="button"
            className="ic-btn ic-btn--ghost ic-session-log-recent__edit"
            onClick={() => navigate('/therapist/leave')}
          >
            View leave
          </button>
        ) : null}
        {!isVirtual && canEditSessionTimes({ ...l, id: l.session_id, status: 'COMPLETED' }, l) && !canResubmit ? (
          <button
            type="button"
            className="ic-btn ic-btn--ghost ic-session-log-recent__edit"
            onClick={() =>
              setEditTimesSession({
                id: l.session_id,
                actual_start_at: l.actual_start_at,
                actual_end_at: l.actual_end_at,
                edited_start_at: l.edited_start_at,
                edited_end_at: l.edited_end_at,
                child_name: l.child_name,
                case_code: l.case_code,
                status: 'COMPLETED',
              })
            }
          >
            Edit times
          </button>
        ) : null}
        {canResubmit ? (
          <button
            type="button"
            className="ic-btn ic-btn--primary ic-session-log-recent__edit"
            onClick={() =>
              openLogForm(
                {
                  id: l.session_id,
                  scheduled_date: l.scheduled_date,
                  actual_start_at: l.actual_start_at,
                  actual_end_at: l.actual_end_at,
                  edited_start_at: l.edited_start_at,
                  edited_end_at: l.edited_end_at,
                  actual_times_edited: l.actual_times_edited,
                  case_code: l.case_code,
                  child_name: l.child_name,
                  status: 'COMPLETED',
                },
                { log: l },
              )
            }
          >
            Edit & resubmit
          </button>
        ) : null}
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
            {(() => {
              if (!l.editable_until) return 'Edit log'
              const hoursLeft = Math.max(0, Math.ceil((new Date(l.editable_until) - Date.now()) / 3600000))
              return hoursLeft > 0 ? `Edit log (${hoursLeft}h left)` : 'Edit log'
            })()}
          </button>
        ) : null}
        {allowView && !canEdit && !canResubmit && !isVirtual ? (
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
                { log: l, readOnly: true },
              )
            }
          >
            View log
          </button>
        ) : null}
        {!isVirtual ? <DownloadApprovedLogButton log={l} variant="therapist" /> : null}
      </div>
    )
  }

  async function handleDiscardPendingLog(session) {
    if (!session?.id || discardBusy) return
    const displayName = session.child_name || session.case_code || 'this visit'
    const when = session.scheduled_date ? formatDisplayDate(session.scheduled_date) : 'that day'
    const ok = window.confirm(
      `Remove the unfinished visit for ${displayName} on ${when}? You can start a new session after this — the visit record will be cleared.`,
    )
    if (!ok) return
    setDiscardBusy(true)
    setError('')
    try {
      const updated = await discardPendingLogWithDraft(session.id)
      patchCachesAfterPendingLogDiscarded(updated)
      setSuccess('Draft visit removed — you can start a new session now.')
      void syncDraftIds()
      void loadAll({ silent: true })
    } catch (err) {
      setError(err.message || 'Could not remove the draft visit')
    } finally {
      setDiscardBusy(false)
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
    const caseBlocking = getBlockingLogForCase(needsLog, meta.case_id)
    if (caseBlocking && caseBlocking.id !== sessionId && !activeInProgress) {
      openLogForm(caseBlocking, { required: true })
      return
    }
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
        if (result.pendingLog) {
          const blocked = resolveBlockingLogSession(needsLog, result.pendingLog, meta.case_id)
          if (blocked) {
            openLogForm(blocked, { required: true })
            return
          }
          setError(
            result.pendingLog.message ||
              'This client’s previous visit still needs a log before starting a new session.',
          )
          return
        }
        if (result.absenceBlock?.message) {
          setError(result.absenceBlock.message)
          return
        }
        if (result.conflict?.recommendedAction === 'CONTINUE_SESSION') {
          setSuccess('A session is in progress — end it above to start another visit.')
          activeSessionCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
          return
        }
        if (result.conflict?.existingSessionId) {
          redirectForSessionConflict(result.conflict, navigate)
          return
        }
        setSuccess(result.message)
        return
      }
      const started = result.session
      if (started?.status !== 'IN_PROGRESS') {
        setError('Could not start session — please refresh and try again.')
        void loadAll({ silent: true })
        return
      }
      patchCachesAfterSessionStart(started)
      if (started?.invite_sent && started?.invite_email) {
        setSuccess(`Invite sent to ${started.invite_email} — they will join the Client portal.`)
      }
    } catch (err) {
      setError(err.message || 'Could not start session')
    }
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
    setEndBusy(true)
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
    } finally {
      setEndBusy(false)
    }
  }

  async function handleCancel(sessionId, sessionStatus) {
    setCancelBusy(true)
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
      if (visitSession?.id === sessionId) setVisitSession(null)
      if (logSession?.id === sessionId) {
        void clearLogDraft(sessionId)
        closeLogForm()
      }
      setSuccess(
        sessionStatus === 'COMPLETED'
          ? 'Session removed — you can start again, mark absent, or update the schedule.'
          : 'Session cancelled — you can start again when ready.',
      )
    } catch (err) {
      setError(err.message || 'Could not cancel session')
    } finally {
      setCancelBusy(false)
    }
  }

  async function handleManualSession(payload) {
    setSubmitting(true)
    setError('')
    setExistingSessionConflict(null)
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
      if (err?.status === 409 && isPendingLogBlock(err.detail)) {
        setError(
          err.detail.message ||
            'This client\'s previous visit still needs a log before adding another session.',
        )
        return
      }
      if (err?.status === 409 && isAbsenceConflict(err.detail)) {
        setExistingSessionConflict({ ...err.detail, pending_payload: payload })
        return
      }
      if (err?.status === 409 && err.detail?.code === 'EXISTING_SESSION_FOR_DATE') {
        setExistingSessionConflict({ ...err.detail, pending_payload: payload })
        return
      }
      setError(err.message || 'Could not add session')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleExistingSessionAction(conflict) {
    if (conflict?.recommended_action === 'blocked_absence' || conflict?.code === 'PENDING_CHILD_ABSENCE' || conflict?.code === 'CHILD_MARKED_ABSENT') {
      setExistingSessionConflict(null)
      setError(conflict.message || 'This day is recorded as child absent.')
      return
    }
    setExistingSessionConflict(null)
    setWalkInConflict(null)
    setScheduledSessionHint('')
    setError('')
    try {
      if (conflict.recommended_action === 'resume_session') {
        void loadAll({ silent: true })
        setVisitSession(null)
        closeLogForm()
        setSuccess('Session in progress — end it above when you are finished.')
        activeSessionCardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        return
      }

      if (conflict.recommended_action === 'complete_forgotten') {
        const pending = conflict.pending_payload
        if (!pending?.actual_start_at || !pending?.actual_end_at) {
          setExistingSessionConflict(conflict)
          setError('Enter when the visit happened in Forgot to log, then tap Record visit & write log.')
          return
        }
        const completed = await apiFetch(
          `/api/v1/sessions/${conflict.existing_session_id}/complete-forgotten`,
          {
            method: 'POST',
            body: JSON.stringify({
              actual_start_at: pending.actual_start_at,
              actual_end_at: pending.actual_end_at,
              mode: pending.mode,
            }),
          },
        )
        patchCachesAfterSessionEnd(completed)
        openLogForm(sessionToLogShape(completed), { required: true })
        setSuccess(
          pending.isPastDay
            ? 'Visit recorded — submit the log and include a late reason for admin review.'
            : 'Visit recorded — complete the session log below.',
        )
        void loadAll({ silent: true })
        return
      }

      const session = await apiFetch(`/api/v1/sessions/${conflict.existing_session_id}`)
      const sessionShape = sessionToLogShape(session)

      if (conflict.daily_log_id) {
        let log = logs.find((l) => Number(l.id) === Number(conflict.daily_log_id))
        if (!log) {
          log = await apiFetch(`/api/v1/daily-logs/${conflict.daily_log_id}`)
        }
        const readOnly = conflict.recommended_action === 'view_log' && log?.approval_status === 'APPROVED'
        openLogForm(sessionShape, { log, required: false, readOnly })
        return
      }

      if (conflict.recommended_action === 'edit_log' || session.status === 'COMPLETED') {
        if (session.status !== 'COMPLETED') {
          openSessionFromDeepLink(session)
          return
        }
        const log = logs.find((l) => Number(l.session_id) === Number(session.id) && l.id > 0)
        openLogForm(sessionShape, { log: log || null, required: !session.has_daily_log })
        return
      }

      openSessionFromDeepLink(session)
    } catch (err) {
      setError(err.message || 'Could not open existing session')
    }
  }

  const showComposerShell = !logSession && !viewingLog && !visitSession
  const handleComposerError = (msg) => {
    if (!error) setError(msg)
  }

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

      {error && String(error).includes('Connection unstable') ? (
        <div className="ic-alert ic-alert--warn" style={{ borderLeft: '4px solid #f59e0b', backgroundColor: '#fffbeb', color: '#b45309', padding: '12px', marginBottom: 20, borderRadius: '4px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <strong>Connection Unstable</strong> — You are still logged in, but we cannot reach the server. Your drafts are saved on this device.
          </div>
          <button type="button" className="ic-btn ic-btn--secondary" onClick={handleRetry} style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
            Retry now
          </button>
        </div>
      ) : error && String(error).toLowerCase().includes('offline') ? (
        <div className="ic-alert ic-alert--warn" style={{ marginBottom: 20 }}>
          {error}
        </div>
      ) : error ? (
        <div className="ic-alert ic-alert--error">{error}</div>
      ) : null}
      {success ? (
        <div className="ic-alert ic-alert--success">{success}</div>
      ) : null}

      {composerCaseId && composerBlockingSession && !logSession ? (
        <PendingLogGate
          session={composerBlockingSession}
          draftSaved={draftIds.has(composerBlockingSession.id)}
          busy={discardBusy}
          onCompleteLog={(s) => openLogForm(s, { required: true })}
          onDiscard={handleDiscardPendingLog}
        />
      ) : null}

      {activeInProgress ? (
        <ActiveSessionCard
          ref={activeSessionCardRef}
          session={activeInProgress}
          tick={tick}
          endBusy={endBusy}
          onEnd={handleEnd}
        />
      ) : null}

      {stalePrevious.length > 0 ? (
        <section
          className="ic-case-stale"
          style={{
            marginBottom: 24,
            border: '1px solid #fbbf24',
            backgroundColor: '#fffbeb',
            borderRadius: '8px',
            padding: '16px',
          }}
        >
          <p style={{ color: '#b45309', fontWeight: 600, margin: '0 0 8px' }}>
            Previous session was not closed
          </p>
          {stalePrevious.map((s) => (
            <p key={s.id} style={{ margin: '0 0 6px', fontSize: '0.875rem' }}>
              <strong>{s.child_name || s.case_code}</strong> · {formatDisplayDate(s.scheduled_date)}
              {s.actual_start_at ? (
                <span style={{ color: '#6b7280' }}> · started {formatTimeIST(s.actual_start_at)}</span>
              ) : null}
            </p>
          ))}
          <p style={{ margin: 0, fontSize: '0.8125rem', color: '#92400e' }}>
            Open sessions auto-close at 10 PM IST. You can still start today&apos;s visits and log child absence.
          </p>
        </section>
      ) : null}

      {visitSession ? (
        <section ref={logPanelRef} className="ic-session-log-panel-wrap" style={{ marginBottom: 24 }}>
          <SessionVisitPanel
            session={visitSession}
            activeSessionId={activeInProgress?.id}
            busy={visitBusy || endBusy}
            dayBlocker={existingVisitForDay(visitSession, deepLinkContext)}
            onStart={handleVisitStart}
            onEnd={handleVisitEnd}
            onOpenExisting={openSessionFromDeepLink}
            onClose={closeVisitFocus}
          />
        </section>
      ) : null}

      {viewingLog ? (
        <section ref={logPanelRef} style={{ marginBottom: 24 }}>
          <SessionLogReadOnly
            log={viewingLog.log}
            session={viewingLog.session}
            childName={viewingLog.log.child_name}
            caseCode={viewingLog.log.case_code}
            onClose={closeLogForm}
            onCommentCountChange={handleLogCommentCountChange}
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
            onCancelSession={
              logRequired && !editingLog && logSession?.id
                ? () => handleCancel(logSession.id, logSession.status)
                : undefined
            }
            cancelSessionBusy={cancelBusy}
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

      {showComposerShell ? (
        <TherapistSessionComposer
          upcomingSessions={upcoming}
          liveBlocked={!!activeInProgress}
          pendingLogBlocked={pendingLogBlockedForComposer}
          onPendingLogRequired={(pending) => {
            const blocked =
              resolveBlockingLogSession(needsLog, pending, composerCaseId) || composerBlockingSession
            if (blocked) {
              openLogForm(blocked, { required: true })
              return
            }
            setError(
              pending?.message ||
                'This client’s previous visit still needs a log before starting a new session.',
            )
          }}
          selectedCaseId={composerCaseId}
          onSelectedCaseChange={setComposerCaseId}
          existingSessionConflict={existingSessionConflict}
          walkInConflict={walkInConflict}
          onExistingSessionAction={handleExistingSessionAction}
          onDismissExistingSessionConflict={() => setExistingSessionConflict(null)}
          onDismissWalkInConflict={dismissWalkInConflict}
          onScheduledSessionExists={handleScheduledSessionExists}
          onWalkInSessionConflict={handleWalkInSessionConflict}
          onSessionStarted={(info) => {
            setWalkInConflict(null)
            setScheduledSessionHint('')
            if (info?.message) setSuccess(info.message)
            void loadAll({ silent: true })
          }}
          onManualSession={handleManualSession}
          onError={handleComposerError}
        />
      ) : null}

      {!activeInProgress && needsLog.length > 0 && !logSession ? (
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
                onClick={() => openSessionFromDeepLink(s)}
              >
                <span>
                  <strong>{s.child_name || s.case_code}</strong> · {formatDisplayDate(s.scheduled_date)}
                  {draftIds.has(s.id) ? (
                    <span className="ic-session-log-needs__draft"> · Draft saved</span>
                  ) : null}
                </span>
                <span className="ic-session-log-needs__cta">{draftIds.has(s.id) ? 'Continue log' : 'Edit session log'}</span>
              </button>
            ))}
          </div>
        </section>
      ) : null}

      {!logSession ? (
        <section ref={upcomingSectionRef} style={{ marginBottom: 24 }}>
          {scheduledSessionHint ? (
            <p
              className="ic-alert ic-alert--success"
              role="status"
              style={{ marginBottom: 12 }}
            >
              {scheduledSessionHint}
            </p>
          ) : null}
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 8,
              marginBottom: 12,
            }}
          >
            <h3 className="ic-section-head__title" style={{ margin: 0 }}>
              Upcoming sessions
            </h3>
            {composerCaseId ? (
              <button
                type="button"
                className="ic-btn ic-btn--ghost"
                style={{ padding: '6px 12px', fontSize: '0.8125rem' }}
                onClick={() => setComposerCaseId(null)}
              >
                Show all clients
              </button>
            ) : null}
          </div>
          {displayUpcoming.length === 0 ? (
            <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>
              {composerCaseId
                ? 'No upcoming sessions for this client.'
                : 'No scheduled sessions in the next two weeks.'}
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {displayUpcoming.map((s) => {
                const startedLate = isStartedLateOnSchedule(s.actual_start_at, s.scheduled_date, s.start_time)
                const actualStart = formatTimeIST(s.actual_start_at)
                const actualEnd = formatTimeIST(s.actual_end_at)
                const durMins = actualDurationMinsIST(s.actual_start_at, s.actual_end_at)
                const isInProgress = s.status === 'IN_PROGRESS'
                const dayExisting = existingVisitForDay(s, deepLinkContext)
                const canStartFresh =
                  !activeInProgress && !dayExisting && canStartSessionToday(s).ok
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
                    {!activeInProgress && dayExisting ? (
                      <button
                        type="button"
                        onClick={() => openSessionFromDeepLink(dayExisting)}
                        className="ic-btn ic-btn--primary"
                      >
                        {dayExisting.status === 'IN_PROGRESS' ? 'Go to active session' : 'Edit session log'}
                      </button>
                    ) : canStartFresh ? (
                      <button
                        type="button"
                        onClick={() => handleStart(s.id, s)}
                        className="ic-btn ic-btn--primary"
                      >
                        Start session
                      </button>
                    ) : !activeInProgress && s.scheduled_date > todayIsoIST() ? (
                      <span className="ic-session-log-recent__meta">Opens on visit day</span>
                    ) : null}
                  </article>
                )
              })}
            </div>
          )}
        </section>
      ) : null}

      <section className="ic-session-log-tabs-section">
        <div className="ic-case-history-filters" style={{ marginBottom: 12 }}>
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
        <div className="ic-session-log-tabs" role="tablist" aria-label="Session log lists">
          {LOG_TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={logTab === t.id}
              className={`ic-session-log-tabs__btn${logTab === t.id ? ' is-active' : ''}`}
              onClick={() => setLogTab(t.id)}
            >
              {t.label}
              {t.id === 'needs' && filteredNeedsLog.length > 0 ? (
                <span className="ic-session-log-tabs__count">{filteredNeedsLog.length}</span>
              ) : null}
              {t.id === 'child_absent' && filteredChildAbsent.length > 0 ? (
                <span className="ic-session-log-tabs__count">{filteredChildAbsent.length}</span>
              ) : null}
              {t.id === 'leave' && filteredLeave.length > 0 ? (
                <span className="ic-session-log-tabs__count">{filteredLeave.length}</span>
              ) : null}
              {t.id === 'pending' && filteredPending.length > 0 ? (
                <span className="ic-session-log-tabs__count">{filteredPending.length}</span>
              ) : null}
            </button>
          ))}
        </div>

        <div className="ic-session-log-tab-panel" role="tabpanel">
          {logTab === 'needs' ? (
            filteredNeedsLog.length === 0 ? (
              <p className="ic-empty-hint">No sessions waiting for a log in {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredNeedsLog.map((s) => (
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

          {logTab === 'child_absent' ? (
            filteredChildAbsent.length === 0 ? (
              <p className="ic-empty-hint">No child absence records for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredChildAbsent.map((l) => renderLogRow(l))}
              </div>
            )
          ) : null}

          {logTab === 'leave' ? (
            filteredLeave.length === 0 ? (
              <p className="ic-empty-hint">No therapist leave records for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredLeave.map((l) => renderLogRow(l))}
              </div>
            )
          ) : null}

          {logTab === 'pending' ? (
            filteredPending.length === 0 ? (
              <p className="ic-empty-hint">No logs pending admin review for {MONTHS[logMonth]} {logYear}.</p>
            ) : (
              <div className="ic-session-log-recent">
                {filteredPending.map((l) => renderLogRow(l, { allowEdit: true }))}
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

      <EditActualTimesModal
        open={Boolean(editTimesSession)}
        session={editTimesSession}
        onClose={() => setEditTimesSession(null)}
        onSaved={handleActualTimesSaved}
      />
    </div>
  )
}
