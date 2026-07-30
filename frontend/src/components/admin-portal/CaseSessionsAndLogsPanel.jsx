import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { sessionHasTimeEdit } from '../../lib/sessionTimes.js'
import {
  caseSessionLogEmptyMessage,
  defaultCaseSessionLogFilters,
  filterCaseSessionRows,
} from '../../lib/caseSessionLogFilters.js'
import { CaseSessionLogCard } from './CaseSessionLogCard.jsx'
import { CaseSessionLogsFilterBar } from './CaseSessionLogsFilterBar.jsx'
import { enrichLogsWithCommentCounts } from '../../lib/sessionLogComments.js'
import './admin-sessions-dashboard.css'

function sessionSortKey(session, logsBySessionId) {
  const log = logsBySessionId.get(session.id)
  if (log?.approval_status === 'PENDING') return 0
  if (log?.approval_status === 'REJECTED') return 1
  if (!log) return 2
  return 3
}

function sessionRecencyKey(session, logsBySessionId) {
  const log = logsBySessionId.get(session.id)
  const ts = log?.resubmitted_at || log?.submitted_at || session.scheduled_date
  return ts ? new Date(ts).getTime() : 0
}

function sessionExpandKey(sessionId) {
  return `s:${sessionId}`
}

function orphanExpandKey(logId) {
  return `o:${logId}`
}

function shouldDefaultExpand(sessionId, log, highlightSessionId) {
  if (highlightSessionId && String(sessionId) === String(highlightSessionId)) return true
  return log?.approval_status === 'PENDING'
}

function SessionLogList({ items, highlightRef, sharedExpandProps }) {
  const { expandedKeys: _ignored, ...cardProps } = sharedExpandProps
  return (
    <ul className="case-sessions-logs__list">
      {items.map(({ key, session, log, expandKey, expanded, highlight }) => (
        <li key={key} className="case-sessions-logs__list-item">
          <CaseSessionLogCard
            session={session}
            log={log}
            expandKey={expandKey}
            expanded={expanded}
            highlight={highlight}
            highlightRef={highlight ? highlightRef : null}
            {...cardProps}
          />
        </li>
      ))}
    </ul>
  )
}

export function CaseSessionsAndLogsPanel({ caseId, highlightSessionId, canReview }) {
  const [sessions, setSessions] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [actingLogId, setActingLogId] = useState(null)
  const [rejectingLogId, setRejectingLogId] = useState(null)
  const [rejectComment, setRejectComment] = useState('')
  const [expandedKeys, setExpandedKeys] = useState(() => new Set())
  const [viewMode, setViewMode] = useState(() => defaultCaseSessionLogFilters().viewMode)
  const [selectedMonth, setSelectedMonth] = useState(() => defaultCaseSessionLogFilters().selectedMonth)
  const [selectedDate, setSelectedDate] = useState(() => defaultCaseSessionLogFilters().selectedDate)
  const [statusFilter, setStatusFilter] = useState(() => defaultCaseSessionLogFilters().statusFilter)
  const highlightRef = useRef(null)
  const autoExpandDoneRef = useRef('')

  const fetchSessionsAndLogs = useCallback(async () => {
    const [sessData, logData] = await Promise.all([
      apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
      apiFetch(`/api/v1/daily-logs?case_id=${caseId}`),
    ])
    const nextSessions = unwrapList(sessData)
    const rawLogs = Array.isArray(logData) ? logData : unwrapList(logData)
    const nextLogs = await enrichLogsWithCommentCounts(rawLogs, apiFetch)
    setSessions(nextSessions)
    setLogs(nextLogs)
    return { sessions: nextSessions, logs: nextLogs }
  }, [caseId])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchSessionsAndLogs()
      .catch(() => {
        if (!cancelled) {
          setSessions([])
          setLogs([])
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchSessionsAndLogs])

  const logsBySessionId = useMemo(() => {
    const map = new Map()
    for (const log of logs) {
      if (log.session_id != null) map.set(log.session_id, log)
    }
    return map
  }, [logs])

  const sortedSessions = useMemo(() => {
    return [...sessions].sort((a, b) => {
      const priority = sessionSortKey(a, logsBySessionId) - sessionSortKey(b, logsBySessionId)
      if (priority !== 0) return priority
      return sessionRecencyKey(b, logsBySessionId) - sessionRecencyKey(a, logsBySessionId)
    })
  }, [sessions, logsBySessionId])

  const orphanLogs = useMemo(
    () => logs.filter((l) => !sessions.some((s) => s.id === l.session_id)),
    [logs, sessions],
  )

  const { filteredSessions, filteredOrphanLogs } = useMemo(
    () =>
      filterCaseSessionRows({
        sessions: sortedSessions,
        logsBySessionId,
        orphanLogs,
        viewMode,
        selectedDate,
        selectedMonth,
        statusFilter,
        highlightSessionId,
        sessionHasTimeEdit,
      }),
    [
      sortedSessions,
      logsBySessionId,
      orphanLogs,
      viewMode,
      selectedDate,
      selectedMonth,
      statusFilter,
      highlightSessionId,
    ],
  )

  function handleViewModeChange(nextMode) {
    setViewMode(nextMode)
    if (nextMode === 'day') {
      setSelectedDate((prev) => (prev.startsWith(selectedMonth) ? prev : `${selectedMonth}-01`))
    }
    if (nextMode === 'month') {
      setSelectedMonth(selectedDate.slice(0, 7))
    }
  }

  function handleSelectedDateChange(nextDate) {
    setSelectedDate(nextDate)
    if (nextDate) setSelectedMonth(nextDate.slice(0, 7))
  }

  useEffect(() => {
    if (loading) return
    const signature = `${caseId}:${highlightSessionId || ''}:${sessions.length}:${logs.length}`
    if (autoExpandDoneRef.current === signature) return
    autoExpandDoneRef.current = signature

    setExpandedKeys((prev) => {
      const next = new Set(prev)
      for (const session of sessions) {
        const log = logsBySessionId.get(session.id)
        if (shouldDefaultExpand(session.id, log, highlightSessionId)) {
          next.add(sessionExpandKey(session.id))
        }
      }
      for (const log of orphanLogs) {
        if (log.approval_status === 'PENDING') {
          next.add(orphanExpandKey(log.id))
        }
      }
      return next
    })
  }, [loading, caseId, highlightSessionId, sessions, logs.length, logsBySessionId, orphanLogs])

  useEffect(() => {
    if (!highlightSessionId || loading) return
    const t = setTimeout(() => {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 120)
    return () => clearTimeout(t)
  }, [highlightSessionId, loading, sessions.length])

  function toggleExpand(key) {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  async function handleReviewLog(logId, action, comment = null) {
    setActingLogId(logId)
    try {
      const opts = { method: 'POST' }
      if (action === 'reject') {
        opts.body = JSON.stringify({ comment: comment || '' })
      }
      await apiFetch(`/api/v1/daily-logs/${logId}/${action}`, opts)
      await fetchSessionsAndLogs()
    } finally {
      setActingLogId(null)
    }
  }

  function handleLogCommentCountChange(logId, commentCount, openParentCommentCount = 0) {
    setLogs((prev) =>
      prev.map((entry) =>
        entry.id === logId
          ? {
              ...entry,
              comment_count: commentCount,
              open_parent_comment_count: openParentCommentCount,
            }
          : entry,
      ),
    )
  }

  if (loading) {
    return <p className="admin-muted">Loading sessions…</p>
  }

  if (sessions.length === 0 && logs.length === 0) {
    return (
      <p className="admin-muted" style={{ margin: 0 }}>
        No scheduled sessions or submitted logs for this case yet.
      </p>
    )
  }

  const sharedExpandProps = {
    caseId,
    canReview,
    onReviewLog: handleReviewLog,
    actingLogId,
    rejectingLogId,
    setRejectingLogId,
    rejectComment,
    setRejectComment,
    onToggleExpand: toggleExpand,
    onCommentCountChange: handleLogCommentCountChange,
  }

  const sessionItems = filteredSessions.map((session) => {
    const log = logsBySessionId.get(session.id)
    const expandKey = sessionExpandKey(session.id)
    return {
      key: `session-${session.id}`,
      session,
      log,
      expandKey,
      expanded: expandedKeys.has(expandKey),
      highlight: Boolean(highlightSessionId && String(session.id) === String(highlightSessionId)),
    }
  })

  const orphanItems = filteredOrphanLogs.map((log) => {
    const expandKey = orphanExpandKey(log.id)
    return {
      key: `orphan-${log.id}`,
      session: null,
      log,
      expandKey,
      expanded: expandedKeys.has(expandKey),
      highlight: false,
    }
  })

  const emptyMessage = caseSessionLogEmptyMessage({
    viewMode,
    selectedDate,
    selectedMonth,
    statusFilter,
  })

  return (
    <>
      <CaseSessionLogsFilterBar
        viewMode={viewMode}
        selectedMonth={selectedMonth}
        selectedDate={selectedDate}
        statusFilter={statusFilter}
        onViewModeChange={handleViewModeChange}
        onSelectedMonthChange={setSelectedMonth}
        onSelectedDateChange={handleSelectedDateChange}
        onStatusFilterChange={setStatusFilter}
      />
      <p className="case-sessions-logs__intro admin-portal-lead" style={{ margin: '0 0 12px', fontSize: '0.8125rem', color: '#64748b' }}>
        Sessions appear when scheduled. Daily logs appear after the therapist submits notes. When times were
        corrected, approving the log also approves the corrected clock for billing.
      </p>
      {sessionItems.length === 0 && orphanItems.length === 0 ? (
        <p className="admin-muted" style={{ margin: 0 }}>
          {emptyMessage}
        </p>
      ) : (
        <SessionLogList items={sessionItems} highlightRef={highlightRef} sharedExpandProps={sharedExpandProps} />
      )}

      {orphanItems.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <p className="admin-queue__meta" style={{ marginBottom: 8 }}>
            Orphan logs (session record missing)
          </p>
          <SessionLogList items={orphanItems} highlightRef={highlightRef} sharedExpandProps={sharedExpandProps} />
        </div>
      ) : null}
    </>
  )
}
