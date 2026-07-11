import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  applyLogSavedToCaseLogs,
  applyLogSavedToSessions,
  patchCachesAfterLogSave,
  patchCachesAfterSessionCancel,
  patchCachesAfterSessionEnd,
} from '../../lib/therapistSessionLogCache.js'
import { VoiceSessionLogFlow } from '../daily-logs/voice/VoiceSessionLogFlow.jsx'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import { SessionLogStatusBadge } from '../daily-logs/SessionLogStatusBadge.jsx'
import { formatSessionDisplayRange } from '../../lib/sessionLogUtils.js'
import { enrichLogsWithCommentCounts } from '../../lib/sessionLogComments.js'

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const MONTHS_SHORT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatTime(t) {
  if (!t) return '—'
  return String(t).slice(0, 5)
}

function formatSessionWhen(session) {
  return formatSessionDisplayRange(session) || `${formatTime(session.start_time)}–${formatTime(session.end_time)}`
}

function dayOfMonth(dateStr) {
  return Number(dateStr?.slice(8, 10)) || 0
}

function monthShort(dateStr) {
  const m = Number(dateStr?.slice(5, 7)) - 1
  return MONTHS_SHORT[m] || ''
}

function weekdayLong(dateStr) {
  const d = new Date(`${dateStr}T12:00:00`)
  return d.toLocaleDateString('en-IN', { weekday: 'long' })
}

function sessionPeriodLabel(session) {
  const t = session.start_time || session.actual_start_at
  if (!t) return 'Session'
  const hour = typeof t === 'string' && t.includes('T')
    ? new Date(t).getHours()
    : Number(String(t).slice(0, 2))
  if (hour < 12) return 'Morning Session'
  if (hour < 17) return 'Afternoon Session'
  return 'Evening Session'
}

function logStatusKind(log) {
  if (!log) return null
  if (log.approval_status === 'APPROVED') return 'approved'
  if (log.approval_status === 'REJECTED') return 'rejected'
  if (log.approval_status === 'PENDING') return 'submitted'
  return 'submitted'
}

function logMatchesStatusFilter(log, filter) {
  if (!log || filter === 'all') return true
  if (filter === 'missing') return false
  if (filter === 'submitted') return Boolean(log.submitted_at || log.approval_status)
  if (filter === 'pending') return log.approval_status === 'PENDING'
  if (filter === 'approved') return log.approval_status === 'APPROVED'
  if (filter === 'rejected') return log.approval_status === 'REJECTED'
  return true
}

function buildMonthOptions(sessions) {
  const keys = new Set()
  const now = new Date()
  keys.add(`${now.getFullYear()}-${now.getMonth()}`)
  sessions.forEach((s) => {
    if (!s.scheduled_date) return
    const d = new Date(`${s.scheduled_date}T00:00:00`)
    keys.add(`${d.getFullYear()}-${d.getMonth()}`)
  })
  return Array.from(keys)
    .map((k) => {
      const [y, m] = k.split('-').map(Number)
      return { year: y, month: m, label: `${MONTHS[m]} ${y}` }
    })
    .sort((a, b) => b.year - a.year || b.month - a.month)
}

const LOG_STATUS_FILTERS = [
  { value: 'all', label: 'All statuses' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'pending', label: 'Pending review' },
  { value: 'approved', label: 'Approved' },
  { value: 'rejected', label: 'Rejected' },
]

function monthRangeLabel(month, year) {
  const today = new Date()
  const isCurrent = today.getFullYear() === year && today.getMonth() === month
  const lastDay = isCurrent ? today.getDate() : new Date(year, month + 1, 0).getDate()
  return `${MONTHS[month]} 1 – ${MONTHS[month]} ${lastDay}`
}

function LogComposerModal({ title, onClose, children, dismissible = true }) {
  const canDismiss = dismissible && typeof onClose === 'function'
  return (
    <div className="clinical-logs-modal" role="dialog" aria-modal="true" aria-labelledby="clinical-logs-modal-title">
      {canDismiss ? (
        <button type="button" className="clinical-logs-modal__backdrop" aria-label="Close" onClick={onClose} />
      ) : (
        <div className="clinical-logs-modal__backdrop clinical-logs-modal__backdrop--locked" aria-hidden="true" />
      )}
      <div className="clinical-logs-modal__sheet">
        <div className="clinical-logs-modal__head">
          <h2 id="clinical-logs-modal-title">{title}</h2>
          {canDismiss ? (
            <button type="button" className="clinical-logs-modal__close" onClick={onClose} aria-label="Close">
              ×
            </button>
          ) : null}
        </div>
        <div className="clinical-logs-modal__body">{children}</div>
      </div>
    </div>
  )
}

export function CaseSessionsPanel({
  caseId,
  caseCode,
  childName,
  childLabel = '',
  onScheduleChange,
  initialSessionId = null,
  initialLogId = null,
}) {
  const timelineRef = useRef(null)
  const suppressAutoExpandRef = useRef(false)
  const deepLinkResolvedRef = useRef(null)
  const { user } = useAuth()
  const therapistId = user?.id
  const [sessions, setSessions] = useState([])
  const [logs, setLogs] = useState([])
  const [active, setActive] = useState(null)
  const [loading, setLoading] = useState(true)
  const [logSession, setLogSession] = useState(null)
  const [editingLog, setEditingLog] = useState(null)
  const [logRequired, setLogRequired] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selectedMonthKey, setSelectedMonthKey] = useState(() => {
    const n = new Date()
    return `${n.getFullYear()}-${n.getMonth()}`
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [viewMode, setViewMode] = useState('grid')
  const [expandedDate, setExpandedDate] = useState(null)
  const [expandedLogCache, setExpandedLogCache] = useState({})
  const [expandedLogLoading, setExpandedLogLoading] = useState(false)
  const [pdfBusy, setPdfBusy] = useState(false)

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) {
      setLoading(true)
      setError('')
    }
    try {
      const logParams = new URLSearchParams({ case_id: String(caseId) })
      if (therapistId) logParams.set('therapist_user_id', String(therapistId))
      const [sess, caseLogs, act] = await Promise.all([
        apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
        apiFetch(`/api/v1/daily-logs?${logParams}`),
        apiFetch('/api/v1/sessions/active').catch(() => null),
      ])
      setSessions(unwrapList(sess))
      const rawLogs = Array.isArray(caseLogs) ? caseLogs : unwrapList(caseLogs)
      setLogs(await enrichLogsWithCommentCounts(rawLogs, apiFetch))
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

  useEffect(() => {
    if (loading || logSession) return

    const lid = initialLogId ? Number(initialLogId) : null
    if (lid && Number.isFinite(lid) && deepLinkResolvedRef.current !== `log-${lid}`) {
      const log = logs.find((entry) => Number(entry.id) === lid)
      if (log) {
        const session = sessions.find((s) => s.id === log.session_id)
        if (session) {
          deepLinkResolvedRef.current = `log-${lid}`
          if (session.scheduled_date) {
            const d = new Date(`${session.scheduled_date}T00:00:00`)
            setSelectedMonthKey(`${d.getFullYear()}-${d.getMonth()}`)
          }
          setExpandedDate(session.scheduled_date)
          openLogForm(session, { log })
        }
      }
      return
    }

    const sid = initialSessionId ? Number(initialSessionId) : null
    if (!sid || !Number.isFinite(sid) || deepLinkResolvedRef.current === `session-${sid}`) return

    const session = sessions.find((s) => s.id === sid)
    if (!session) return

    deepLinkResolvedRef.current = `session-${sid}`
    if (session.scheduled_date) {
      const d = new Date(`${session.scheduled_date}T00:00:00`)
      setSelectedMonthKey(`${d.getFullYear()}-${d.getMonth()}`)
      setExpandedDate(session.scheduled_date)
    }
    const existingLog = logs.find((l) => l.session_id === session.id)
    if (existingLog) {
      openLogForm(session, { log: existingLog })
    } else if (session.status === 'COMPLETED') {
      openLogForm(session, { required: true })
    }
  }, [loading, logSession, initialSessionId, initialLogId, logs, sessions])

  const monthOptions = useMemo(() => buildMonthOptions(sessions), [sessions])
  const selectedMonth = useMemo(() => {
    const [y, m] = selectedMonthKey.split('-').map(Number)
    return { year: y, month: m }
  }, [selectedMonthKey])

  const monthSessions = useMemo(() => {
    const { year, month } = selectedMonth
    return sessions.filter((s) => {
      if (!s.scheduled_date) return false
      const d = new Date(`${s.scheduled_date}T00:00:00`)
      return d.getFullYear() === year && d.getMonth() === month
    })
  }, [sessions, selectedMonth])

  const monthSummary = useMemo(() => {
    const total = monthSessions.filter((s) => s.status === 'COMPLETED' || s.status === 'IN_PROGRESS' || s.status === 'SCHEDULED').length
    const completed = monthSessions.filter((s) => s.status === 'COMPLETED')
    const submitted = completed.filter((s) => logs.some((l) => l.session_id === s.id)).length
    const missing = completed.filter((s) => !logs.some((l) => l.session_id === s.id)).length
    return { total, submitted, missing }
  }, [monthSessions, logs])

  const dayGroups = useMemo(() => {
    const { year, month } = selectedMonth
    const byDate = new Map()

    monthSessions.forEach((session) => {
      const date = session.scheduled_date
      if (!byDate.has(date)) {
        byDate.set(date, { date, sessions: [], logs: [] })
      }
      const group = byDate.get(date)
      group.sessions.push(session)
      const log = logs.find((l) => l.session_id === session.id)
      if (log) group.logs.push({ session, log })
    })

    let entries = Array.from(byDate.values()).sort((a, b) => b.date.localeCompare(a.date))

    entries = entries.map((entry) => {
      const completed = entry.sessions.filter((s) => s.status === 'COMPLETED')
      const missingSessions = completed.filter((s) => !entry.logs.some((l) => l.session.id === s.id))
      const hasMissing = missingSessions.length > 0
      const primaryStatus = hasMissing
        ? 'missing'
        : entry.logs.some((l) => l.log.approval_status === 'REJECTED')
          ? 'rejected'
          : entry.logs.some((l) => l.log.approval_status === 'PENDING')
            ? 'submitted'
            : entry.logs.some((l) => l.log.approval_status === 'APPROVED')
              ? 'approved'
              : entry.logs.length
                ? 'submitted'
                : 'scheduled'
      return { ...entry, missingSessions, hasMissing, primaryStatus }
    })

    if (statusFilter === 'missing') entries = entries.filter((e) => e.hasMissing)
    if (statusFilter === 'submitted') entries = entries.filter((e) => e.logs.length > 0)
    if (statusFilter !== 'all' && statusFilter !== 'missing' && statusFilter !== 'submitted') {
      entries = entries.filter((e) => e.logs.some(({ log }) => logMatchesStatusFilter(log, statusFilter)))
    }

    const q = searchQuery.trim().toLowerCase()
    if (q) {
      entries = entries.filter((e) => {
        if (e.date.includes(q)) return true
        if (weekdayLong(e.date).toLowerCase().includes(q)) return true
        return e.logs.some(({ log }) =>
          [log.activities_done, log.goals_addressed, log.session_notes, log.parent_notes]
            .filter(Boolean)
            .some((text) => String(text).toLowerCase().includes(q)),
        )
      })
    }

    return entries
  }, [monthSessions, logs, selectedMonth, statusFilter, searchQuery])

  useEffect(() => {
    suppressAutoExpandRef.current = false
    setExpandedDate(null)
  }, [selectedMonthKey])

  useEffect(() => {
    if (suppressAutoExpandRef.current) return
    if (expandedDate || !dayGroups.length) return
    const firstWithLog = dayGroups.find((d) => d.logs.length > 0)
    if (firstWithLog) setExpandedDate(firstWithLog.date)
  }, [dayGroups, expandedDate])

  useEffect(() => {
    if (!expandedDate) return
    const entry = dayGroups.find((d) => d.date === expandedDate)
    if (!entry?.logs?.length) return

    let cancelled = false
    async function fetchExpandedLogs() {
      setExpandedLogLoading(true)
      try {
        const pairs = await Promise.all(
          entry.logs
            .filter(({ log }) => log?.id)
            .map(async ({ log }) => {
              const data = await apiFetch(`/api/v1/daily-logs/${log.id}`)
              return [log.id, data]
            }),
        )
        if (cancelled) return
        setExpandedLogCache((prev) => {
          const next = { ...prev }
          pairs.forEach(([id, data]) => {
            next[id] = data
          })
          return next
        })
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not load log details')
      } finally {
        if (!cancelled) setExpandedLogLoading(false)
      }
    }
    void fetchExpandedLogs()
    return () => {
      cancelled = true
    }
  }, [expandedDate, dayGroups])

  function scrollToTimeline() {
    timelineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function applySummaryFilter(next) {
    setStatusFilter(next)
    if (viewMode === 'grid' && next !== 'all') setViewMode('list')
    scrollToTimeline()
  }

  function toggleExpandedDay(date) {
    if (expandedDate === date) {
      suppressAutoExpandRef.current = true
      setExpandedDate(null)
      return
    }
    suppressAutoExpandRef.current = false
    setExpandedDate(date)
  }

  async function downloadSessionLogsPdf() {
    setPdfBusy(true)
    setError('')
    try {
      const monthParam = `${year}-${String(month + 1).padStart(2, '0')}`
      await apiDownload(
        `/api/v1/cases/${caseId}/session-logs/export/pdf?month=${monthParam}`,
        `${caseCode}_session_logs_${monthParam}.pdf`,
      )
    } catch (err) {
      setError(err.message || 'Could not download session logs PDF')
    } finally {
      setPdfBusy(false)
    }
  }

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

  async function handleCancel(sessionId) {
    if (!window.confirm('Cancel this session? The timer will stop and no log will be created.')) return
    setError('')
    try {
      const cancelled = await apiFetch(`/api/v1/sessions/${sessionId}/cancel`, {
        method: 'POST',
        body: JSON.stringify({}),
      })
      patchCachesAfterSessionCancel(cancelled)
      setActive(null)
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, ...cancelled, status: 'SCHEDULED' } : s)),
      )
      setSuccess('Session cancelled.')
      onScheduleChange?.()
    } catch (err) {
      setError(err.message || 'Could not cancel session')
    }
  }

  function renderStatusChip(kind) {
    if (kind === 'submitted') {
      return (
        <span className="clinical-logs-tile__chip clinical-logs-tile__chip--submitted">
          <span className="clinical-logs-tile__chip-dot" aria-hidden="true" />
          Submitted
        </span>
      )
    }
    if (kind === 'approved') {
      return (
        <span className="clinical-logs-tile__chip clinical-logs-tile__chip--approved">
          <span className="clinical-logs-tile__chip-dot" aria-hidden="true" />
          Approved
        </span>
      )
    }
    if (kind === 'rejected') {
      return (
        <span className="clinical-logs-tile__chip clinical-logs-tile__chip--rejected">
          <span className="clinical-logs-tile__chip-dot" aria-hidden="true" />
          Rejected
        </span>
      )
    }
    if (kind === 'pending') {
      return (
        <span className="clinical-logs-tile__chip clinical-logs-tile__chip--pending">
          <span className="clinical-logs-tile__chip-dot" aria-hidden="true" />
          Pending review
        </span>
      )
    }
    return null
  }

  function renderExpandedDay(entry) {
    const therapistName = user?.name || user?.email || 'Therapist'

    return (
      <article
        key={`expanded-${entry.date}`}
        className="clinical-logs-tile clinical-logs-tile--expanded"
      >
        {entry.logs[0]?.log ? renderStatusChip(logStatusKind(entry.logs[0].log)) : null}
        <button
          type="button"
          className="clinical-logs-tile__expand-toggle"
          onClick={() => toggleExpandedDay(entry.date)}
          aria-expanded={expandedDate === entry.date}
        >
          <div className="clinical-logs-tile__head">
            <div className="clinical-logs-tile__date-badge clinical-logs-tile__date-badge--active">
              <span className="clinical-logs-tile__date-num">{dayOfMonth(entry.date)}</span>
              <span className="clinical-logs-tile__date-mon">{monthShort(entry.date)}</span>
            </div>
            <div>
              <h4 className="clinical-logs-tile__title">{weekdayLong(entry.date)} Sessions</h4>
              <p className="clinical-logs-tile__meta">
                {entry.logs.length} Log{entry.logs.length === 1 ? '' : 's'} Submitted · {therapistName}
              </p>
            </div>
          </div>
          <span className="clinical-logs-tile__chevron" aria-hidden="true">▾</span>
        </button>
        <div className="clinical-logs-tile__body">
          {expandedLogLoading ? (
            <p className="clinical-logs-panel__loading">Loading session log…</p>
          ) : (
            entry.logs.map(({ session, log }) => {
              const fullLog = expandedLogCache[log.id] || log
              return (
                <div key={log.id} className="clinical-logs-tile__log-block">
                  <div className="clinical-logs-tile__log-head">
                    <div className="clinical-logs-tile__log-head-main">
                      <span className="clinical-logs-tile__session-label">{sessionPeriodLabel(session)}</span>
                      <span className="clinical-logs-tile__session-time">{formatSessionWhen(session)}</span>
                    </div>
                    <SessionLogStatusBadge
                      compact
                      approvalStatus={fullLog.approval_status}
                      attendanceStatus={fullLog.attendance_status}
                    />
                  </div>
                  <SessionLogReadOnly
                    log={fullLog}
                    session={session}
                    childName={childName}
                    caseCode={caseCode}
                    hideHeader
                    embed
                    className="clinical-logs-tile__readonly"
                  />
                  {fullLog.can_edit ? (
                    <div className="clinical-logs-tile__footer">
                      <button
                        type="button"
                        className="clinical-logs-tile__details-link"
                        onClick={() =>
                          openLogForm(
                            {
                              id: session.id,
                              scheduled_date: session.scheduled_date,
                              actual_start_at: session.actual_start_at,
                              actual_end_at: session.actual_end_at,
                            },
                            { log: fullLog },
                          )
                        }
                      >
                        Edit log
                      </button>
                    </div>
                  ) : null}
                </div>
              )
            })
          )}
          {entry.missingSessions?.length ? (
            <div className="clinical-logs-tile__missing-inline">
              {entry.missingSessions.map((session) => (
                <button
                  key={session.id}
                  type="button"
                  className="clinical-logs-tile__missing-cta"
                  onClick={() => openLogForm(session, { required: true })}
                >
                  Log missing {sessionPeriodLabel(session).toLowerCase()} ({formatSessionWhen(session)})
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </article>
    )
  }

  function renderMissingDay(entry) {
    const session = entry.missingSessions[0]
    return (
      <button
        key={`missing-${entry.date}`}
        type="button"
        className="clinical-logs-tile clinical-logs-tile--missing"
        onClick={() => openLogForm(session, { required: true })}
      >
        <div className="clinical-logs-tile__date-badge clinical-logs-tile__date-badge--missing">
          <span className="clinical-logs-tile__date-num">{dayOfMonth(entry.date)}</span>
          <span className="clinical-logs-tile__date-mon">{monthShort(entry.date)}</span>
        </div>
        <h4 className="clinical-logs-tile__missing-title">Missing Log</h4>
        <p className="clinical-logs-tile__missing-sub">{sessionPeriodLabel(session)}</p>
        <span className="clinical-logs-tile__log-now">Log now</span>
      </button>
    )
  }

  function renderCompactDay(entry) {
    const logCount = entry.logs.length
    const title = weekdayLong(entry.date)
    return (
      <button
        key={entry.date}
        type="button"
        className="clinical-logs-tile clinical-logs-tile--compact"
        onClick={() => toggleExpandedDay(entry.date)}
      >
        <div className="clinical-logs-tile__date-badge">
          <span className="clinical-logs-tile__date-num">{dayOfMonth(entry.date)}</span>
          <span className="clinical-logs-tile__date-mon">{monthShort(entry.date)}</span>
        </div>
        <h4 className="clinical-logs-tile__compact-title">{title}</h4>
        <p className="clinical-logs-tile__compact-sub">
          {logCount} Log{logCount === 1 ? '' : 's'} Submitted
        </p>
        {renderStatusChip(entry.primaryStatus === 'missing' ? null : entry.primaryStatus)}
      </button>
    )
  }

  if (loading && !logSession) {
    return <p className="clinical-logs-panel__loading">Loading client logs…</p>
  }

  const { month, year } = selectedMonth

  return (
    <div className="clinical-logs-panel ic-case-sessions">
      {error ? <p className="clinical-logs-panel__alert clinical-logs-panel__alert--error" role="alert">{error}</p> : null}
      {success ? <p className="clinical-logs-panel__alert clinical-logs-panel__alert--success" role="status">{success}</p> : null}

      {active ? (
        <div className="clinical-logs-active" role="status">
          <p className="clinical-logs-active__title">Session in progress</p>
          <p className="clinical-logs-active__hint">End the visit here, then complete the session log.</p>
          <div className="clinical-logs-active__actions">
            <button type="button" className="clinical-logs-active__end clinical-btn-primary" onClick={() => handleEnd(active.id)}>
              End session &amp; write log
            </button>
            <button type="button" className="clinical-btn-ghost" onClick={() => handleCancel(active.id)}>
              Cancel session
            </button>
          </div>
        </div>
      ) : null}

      <section className="clinical-logs-month-summary" aria-label="Month summary">
        <div className="clinical-logs-month-summary__head">
          <h3 className="clinical-logs-month-summary__title">Month Summary: {MONTHS[month]}</h3>
          <span className="clinical-logs-month-summary__range">{monthRangeLabel(month, year)}</span>
        </div>
        <div className="clinical-logs-month-summary__grid">
          <button
            type="button"
            className={`clinical-logs-stat${statusFilter === 'all' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('all')}
          >
            <span className="clinical-logs-stat__label">Total Sessions</span>
            <span className="clinical-logs-stat__value">{monthSummary.total}</span>
          </button>
          <button
            type="button"
            className={`clinical-logs-stat clinical-logs-stat--success${statusFilter === 'submitted' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('submitted')}
          >
            <span className="clinical-logs-stat__label">Logs Submitted</span>
            <span className="clinical-logs-stat__value">{monthSummary.submitted}</span>
          </button>
          <button
            type="button"
            className={`clinical-logs-stat clinical-logs-stat--danger${statusFilter === 'missing' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('missing')}
          >
            <span className="clinical-logs-stat__label">Missing Logs</span>
            <span className="clinical-logs-stat__value">{monthSummary.missing}</span>
          </button>
        </div>
      </section>

      <div className="clinical-logs-toolbar">
        <div className="clinical-logs-toolbar__filters">
          <label className="clinical-logs-toolbar__month">
            <span className="sr-only">Month</span>
            <select
              value={selectedMonthKey}
              onChange={(e) => setSelectedMonthKey(e.target.value)}
              className="clinical-logs-toolbar__month-select"
            >
              {monthOptions.map((opt) => (
                <option key={`${opt.year}-${opt.month}`} value={`${opt.year}-${opt.month}`}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="clinical-logs-toolbar__status">
            <span className="sr-only">Status</span>
            <select
              value={LOG_STATUS_FILTERS.some((f) => f.value === statusFilter) ? statusFilter : 'all'}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="clinical-logs-toolbar__status-select"
            >
              {LOG_STATUS_FILTERS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="clinical-logs-toolbar__search">
            <span className="clinical-logs-toolbar__search-icon" aria-hidden="true">⌕</span>
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search logs…"
              className="clinical-logs-toolbar__search-input"
            />
          </label>
        </div>
      </div>

      <section className="clinical-logs-timeline" aria-label="Recent logs" ref={timelineRef}>
        <div className="clinical-logs-timeline__head">
          <div className="clinical-logs-timeline__head-text">
            <h3>Logs for {MONTHS[month]} {year}</h3>
            <p className="clinical-logs-timeline__subtitle">
              {dayGroups.length} day{dayGroups.length === 1 ? '' : 's'} · {monthSummary.submitted} submitted
              {monthSummary.missing > 0 ? ` · ${monthSummary.missing} missing` : ''}
            </p>
          </div>
          <div className="clinical-logs-timeline__actions">
            <button
              type="button"
              className="clinical-logs-download-btn"
              onClick={() => void downloadSessionLogsPdf()}
              disabled={pdfBusy}
            >
              {pdfBusy ? 'Preparing PDF…' : 'Download PDF'}
            </button>
            <div className="clinical-logs-timeline__views" role="group" aria-label="View mode">
            <button
              type="button"
              className={`clinical-logs-view-btn${viewMode === 'grid' ? ' clinical-logs-view-btn--active' : ''}`}
              onClick={() => setViewMode('grid')}
              aria-pressed={viewMode === 'grid'}
              title="Grid view"
            >
              ⊞
            </button>
            <button
              type="button"
              className={`clinical-logs-view-btn${viewMode === 'list' ? ' clinical-logs-view-btn--active' : ''}`}
              onClick={() => {
                suppressAutoExpandRef.current = true
                setViewMode('list')
                setExpandedDate(null)
              }}
              aria-pressed={viewMode === 'list'}
              title="List view"
            >
              ☰
            </button>
            </div>
          </div>
        </div>

        {dayGroups.length === 0 ? (
          <p className="clinical-logs-panel__empty">
            {monthSessions.length === 0
              ? `No sessions in ${MONTHS[month]} ${year} yet.`
              : 'No logs match this filter.'}
          </p>
        ) : (
          <div className={`clinical-logs-timeline__grid${viewMode === 'list' ? ' clinical-logs-timeline__grid--list' : ''}`}>
            {dayGroups.map((entry) => {
              if (entry.logs.length === 0 && entry.hasMissing) return renderMissingDay(entry)
              if (expandedDate === entry.date && entry.logs.length > 0) return renderExpandedDay(entry)
              return renderCompactDay(entry)
            })}
          </div>
        )}
      </section>

      {logSession ? (
        <LogComposerModal
          title={editingLog ? 'Edit session log' : 'Session log'}
          onClose={closeLogForm}
          dismissible={!(logRequired && !editingLog)}
        >
          <VoiceSessionLogFlow
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
        </LogComposerModal>
      ) : null}
    </div>
  )
}
