import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
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
import { SubmitSessionLogForm } from '../daily-logs/SubmitSessionLogForm.jsx'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import { SessionLogStatusBadge } from '../daily-logs/SessionLogStatusBadge.jsx'
import { AiPreviewButton } from '../clinical/AiPreviewButton.jsx'
import { AI_ENABLED } from '../../lib/reportsRevampFlags.js'
import { formatSessionDisplayRange } from '../../lib/sessionLogUtils.js'

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
  if (log.approval_status === 'PENDING' || log.approval_status === 'REJECTED') return 'needs_review'
  return 'submitted'
}

function goalProgressPct(sessionCount) {
  return Math.min(100, Math.round(((sessionCount || 0) / 4) * 100))
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
}) {
  const timelineRef = useRef(null)
  const goalSnapshotRef = useRef(null)
  const suppressAutoExpandRef = useRef(false)
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
  const [selectedMonthKey, setSelectedMonthKey] = useState(() => {
    const n = new Date()
    return `${n.getFullYear()}-${n.getMonth()}`
  })
  const [searchQuery, setSearchQuery] = useState('')
  const [filterChip, setFilterChip] = useState('all')
  const [viewMode, setViewMode] = useState('grid')
  const [expandedDate, setExpandedDate] = useState(null)
  const [evidenceGoals, setEvidenceGoals] = useState([])
  const [qualitySummary, setQualitySummary] = useState(null)
  const [insightDraft, setInsightDraft] = useState('')
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
      const [sess, caseLogs, act, upcoming, evidence, quality] = await Promise.all([
        apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
        apiFetch(`/api/v1/daily-logs?${logParams}`),
        apiFetch('/api/v1/sessions/active').catch(() => null),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
        apiFetch(`/api/v1/cases/${caseId}/goals/evidence-summary`).catch(() => ({ goals: [] })),
        apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`).catch(() => null),
      ])
      setSessions(unwrapList(sess))
      setLogs(Array.isArray(caseLogs) ? caseLogs : unwrapList(caseLogs))
      setUpcomingAll(Array.isArray(upcoming) ? upcoming : unwrapList(upcoming))
      setEvidenceGoals(evidence?.goals || [])
      setQualitySummary(quality)
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
    const avgProgress = evidenceGoals.length
      ? Math.round(
          evidenceGoals.reduce((sum, g) => sum + goalProgressPct(g.session_count), 0) / evidenceGoals.length,
        )
      : total > 0
        ? Math.round((submitted / Math.max(completed.length, 1)) * 100)
        : 0
    return { total, submitted, missing, avgProgress }
  }, [monthSessions, logs, evidenceGoals])

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
      const needsReview = entry.logs.some(
        (l) => l.log.approval_status === 'PENDING' || l.log.approval_status === 'REJECTED',
      )
      const primaryStatus = hasMissing
        ? 'missing'
        : needsReview
          ? 'needs_review'
          : entry.logs.some((l) => l.log.approval_status === 'APPROVED')
            ? 'approved'
            : entry.logs.length
              ? 'submitted'
              : 'scheduled'
      return { ...entry, missingSessions, hasMissing, needsReview, primaryStatus }
    })

    if (filterChip === 'missing') entries = entries.filter((e) => e.hasMissing)
    if (filterChip === 'submitted') entries = entries.filter((e) => e.logs.length > 0)
    if (filterChip === 'needs_review') entries = entries.filter((e) => e.needsReview)

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
  }, [monthSessions, logs, selectedMonth, filterChip, searchQuery])

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

  const topGoals = useMemo(
    () => [...evidenceGoals].sort((a, b) => (b.session_count || 0) - (a.session_count || 0)).slice(0, 2),
    [evidenceGoals],
  )

  const ruleInsight = useMemo(() => {
    const action = qualitySummary?.recommended_next_actions?.[0]
    if (action) return action
    const stale = (qualitySummary?.goal_coverage || []).filter((g) => g.stale)
    if (stale.length) {
      return `${stale[0].label} could use fresh session evidence this month.`
    }
    return null
  }, [qualitySummary])

  function scrollToTimeline() {
    timelineRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function scrollToGoalSnapshot() {
    goalSnapshotRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function applySummaryFilter(chip) {
    setFilterChip(chip)
    if (viewMode === 'grid' && chip !== 'all') setViewMode('list')
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
    if (kind === 'needs_review') {
      return (
        <span className="clinical-logs-tile__chip clinical-logs-tile__chip--review">
          <span className="clinical-logs-tile__chip-dot" aria-hidden="true" />
          Needs Review
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
                {entry.logs.length} Log{entry.logs.length === 1 ? '' : 's'} Completed · {therapistName}
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
          {logCount} Log{logCount === 1 ? '' : 's'} Completed
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
      <div className="clinical-page-header">
        <h2 className="clinical-section-heading">Client Logs</h2>
        <p className="clinical-section-subtitle">
          Review session notes, goal evidence, strategy use and patterns for {childName}.
        </p>
      </div>

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
            className={`clinical-logs-stat${filterChip === 'all' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('all')}
          >
            <span className="clinical-logs-stat__label">Total Sessions</span>
            <span className="clinical-logs-stat__value">{monthSummary.total}</span>
          </button>
          <button
            type="button"
            className={`clinical-logs-stat clinical-logs-stat--success${filterChip === 'submitted' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('submitted')}
          >
            <span className="clinical-logs-stat__label">Logs Submitted</span>
            <span className="clinical-logs-stat__value">{monthSummary.submitted}</span>
          </button>
          <button
            type="button"
            className={`clinical-logs-stat clinical-logs-stat--danger${filterChip === 'missing' ? ' clinical-logs-stat--active' : ''}`}
            onClick={() => applySummaryFilter('missing')}
          >
            <span className="clinical-logs-stat__label">Missing Logs</span>
            <span className="clinical-logs-stat__value">{monthSummary.missing}</span>
          </button>
          <button
            type="button"
            className="clinical-logs-stat clinical-logs-stat--accent"
            onClick={scrollToGoalSnapshot}
          >
            <span className="clinical-logs-stat__label">Avg Progress</span>
            <span className="clinical-logs-stat__value">{monthSummary.avgProgress}%</span>
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
        <div className="clinical-logs-toolbar__chips" role="group" aria-label="Log filters">
          {[
            { id: 'all', label: 'All' },
            { id: 'missing', label: 'Missing' },
            { id: 'needs_review', label: 'Needs Review' },
          ].map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={`clinical-logs-chip${filterChip === chip.id ? ' clinical-logs-chip--active' : ''}`}
              onClick={() => setFilterChip(chip.id)}
            >
              {chip.label}
            </button>
          ))}
        </div>
      </div>

      <section className="clinical-logs-insights" aria-label="Clinical insights">
        <div className="clinical-logs-insights__head">
          <div className="clinical-logs-insights__title-row">
            <span className="clinical-logs-insights__spark" aria-hidden="true">✦</span>
            <h3>Clinical Insights</h3>
          </div>
          <Link
            to={`/therapist/cases/${caseId}?tab=insights`}
            className="clinical-logs-insights__generate"
          >
            Open Insights tab
          </Link>
        </div>
        <div className="clinical-logs-insights__grid">
          {(insightDraft || ruleInsight) ? (
            <div className="clinical-logs-insights__pattern">
              <span className="clinical-logs-insights__pattern-label">Key Pattern</span>
              <p>{insightDraft || ruleInsight}</p>
            </div>
          ) : (
            <div className="clinical-logs-insights__pattern">
              <span className="clinical-logs-insights__pattern-label">Key Pattern</span>
              <p className="clinical-logs-insights__empty">Patterns appear after more session evidence is logged.</p>
            </div>
          )}
          <div className="clinical-logs-insights__placeholder">
            <p>Generate monthly snapshots on the Insights tab when you need AI-assisted review.</p>
          </div>
        </div>
      </section>

      <section className="clinical-logs-goal-snapshot" aria-label="Goal evidence snapshot" ref={goalSnapshotRef}>
        <div className="clinical-logs-goal-snapshot__head">
          <h3>Goal Evidence Snapshot</h3>
          <Link to={`/therapist/cases/${caseId}?tab=goals`} className="clinical-logs-goal-snapshot__link">
            View goal tracking details
          </Link>
        </div>
        {topGoals.length === 0 ? (
          <p className="clinical-logs-panel__empty">Log sessions with goal evidence to see snapshots here.</p>
        ) : (
          <div className="clinical-logs-goal-snapshot__grid">
            {topGoals.map((goal) => {
              const pct = goalProgressPct(goal.session_count)
              return (
                <div key={goal.label} className="clinical-logs-goal-card">
                  <div>
                    <div className="clinical-logs-goal-card__title">{goal.label}</div>
                    <div className="clinical-logs-goal-card__meta">
                      {goal.session_count || 0} instance{(goal.session_count || 0) === 1 ? '' : 's'} recorded
                    </div>
                  </div>
                  <div className="clinical-logs-goal-card__progress">
                    <span className="clinical-logs-goal-card__pct">+{pct}%</span>
                    <div className="clinical-logs-goal-card__bar" aria-hidden="true">
                      <div className="clinical-logs-goal-card__bar-fill" style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

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
        </LogComposerModal>
      ) : null}
    </div>
  )
}
