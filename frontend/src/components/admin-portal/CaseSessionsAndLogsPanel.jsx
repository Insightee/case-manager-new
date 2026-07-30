import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import {
  formatSessionLogRowTitle,
  sessionHasTimeEdit,
} from '../../lib/sessionTimes.js'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import {
  caseSessionLogEmptyMessage,
  defaultCaseSessionLogFilters,
  filterCaseSessionRows,
} from '../../lib/caseSessionLogFilters.js'
import { AdminDataList, AdminTaskCard, RejectWithComment, StatusBadge } from './ui/index.js'
import { CaseSessionLogsFilterBar } from './CaseSessionLogsFilterBar.jsx'
import { LogCommentCountPill, LogOpenParentCommentBadge } from '../shared/LogCommentCountBadge.jsx'
import { buildSessionLogMeta, enrichLogsWithCommentCounts, logCommentMetaSuffix } from '../../lib/sessionLogComments.js'
import './admin-sessions-dashboard.css'

function fmtDate(s) {
  if (!s) return '—'
  const [y, m, d] = String(s).slice(0, 10).split('-')
  return `${d}/${m}/${String(y).slice(2)}`
}

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

function SessionLogExpandableBody({
  expandKey,
  log,
  session,
  caseId,
  expanded,
  onToggleExpand,
  canReview,
  onReviewLog,
  actingLogId,
  rejectingLogId,
  setRejectingLogId,
  rejectComment,
  setRejectComment,
  analyticsSessionId,
  onCommentCountChange,
}) {
  if (!log) return null

  const hasTimeEdit = sessionHasTimeEdit(session, log)
  const analyticsHref = analyticsSessionId
    ? `/admin/logs?tab=sessions&case_id=${caseId}&session_id=${analyticsSessionId}`
    : `/admin/logs?tab=sessions&case_id=${caseId}`

  return (
    <div className="case-sessions-logs__expand-row">
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        onClick={() => onToggleExpand(expandKey)}
        aria-expanded={expanded}
      >
        {expanded ? 'Hide full log' : 'View full log'}
      </button>
      <Link to={analyticsHref} className="case-sessions-logs__analytics-link">
        Sessions analytics
      </Link>
      {expanded ? (
        <div style={{ flexBasis: '100%', width: '100%' }}>
          {log.approval_status === 'PENDING' && log.resubmitted_at ? (
            <p className="admin-session-log-detail__notice admin-session-log-detail__notice--info" role="status" style={{ marginBottom: 12 }}>
              Resubmitted after changes — review the therapist&apos;s corrections before approving.
            </p>
          ) : null}
          <SessionLogReadOnly
            log={log}
            session={session}
            variant="admin"
            hideHeader
            onCommentCountChange={onCommentCountChange}
          />
          {log.approval_status === 'PENDING' && canReview ? (
            <div style={{ marginTop: 12 }}>
              <RejectWithComment
                rejecting={rejectingLogId === log.id}
                comment={rejectingLogId === log.id ? rejectComment : ''}
                onCommentChange={setRejectComment}
                onStartReject={() => {
                  setRejectingLogId(log.id)
                  setRejectComment('')
                }}
                onCancelReject={() => {
                  setRejectingLogId(null)
                  setRejectComment('')
                }}
                onConfirmReject={() => {
                  const note = rejectComment.trim()
                  if (!note) return
                  onReviewLog(log.id, 'reject', note)
                  setRejectingLogId(null)
                  setRejectComment('')
                }}
                onApprove={() => onReviewLog(log.id, 'approve')}
                processing={actingLogId === log.id}
                approveLabel={hasTimeEdit ? 'Approve log & times' : 'Approve'}
                placeholder="Why is this log rejected? (required)"
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function SessionLogCard({
  session,
  log,
  caseId,
  highlightSessionId,
  highlightRef,
  expandKey,
  expanded,
  onToggleExpand,
  canReview,
  onReviewLog,
  actingLogId,
  rejectingLogId,
  setRejectingLogId,
  rejectComment,
  setRejectComment,
  onCommentCountChange,
}) {
  const isHighlight = highlightSessionId && String(session.id) === String(highlightSessionId)
  const title = formatSessionLogRowTitle(session, { fmtDate })

  const actions = !log ? (
    <span className="admin-muted" style={{ fontSize: '0.8125rem' }}>
      {session.status === 'IN_PROGRESS' || session.status === 'SCHEDULED'
        ? 'Log not submitted yet'
        : 'No therapist log'}
    </span>
  ) : null

  const detailBody = (
    <>
      {!log ? (
        <p className="case-sessions-logs__pending">
          {session.status === 'IN_PROGRESS' || session.status === 'SCHEDULED'
            ? 'Session in progress — log not submitted yet.'
            : 'No therapist log submitted for this session.'}
        </p>
      ) : (
        <SessionLogExpandableBody
          expandKey={expandKey}
          log={log}
          session={session}
          caseId={caseId}
          expanded={expanded}
          onToggleExpand={onToggleExpand}
          canReview={canReview}
          onReviewLog={onReviewLog}
          actingLogId={actingLogId}
          rejectingLogId={rejectingLogId}
          setRejectingLogId={setRejectingLogId}
          rejectComment={rejectComment}
          setRejectComment={setRejectComment}
          analyticsSessionId={session.id}
          onCommentCountChange={onCommentCountChange}
        />
      )}
    </>
  )

  return (
    <li ref={isHighlight ? highlightRef : null}>
      <AdminTaskCard
        highlight={isHighlight}
        title={title}
        meta={buildSessionLogMeta(session, log)}
        badges={
          <>
            <StatusBadge status={session.status} />
            {log ? <StatusBadge status={log.approval_status} /> : null}
            {log?.comment_count > 0 ? <LogCommentCountPill count={log.comment_count} /> : null}
            {log?.resubmitted_at ? (
              <span className="admin-badge admin-badge--info sessions-dash__pill">Resubmitted</span>
            ) : null}
            <LogOpenParentCommentBadge log={log} />
            {sessionHasTimeEdit(session, log) ? (
              <span className="admin-badge admin-badge--warning sessions-dash__pill">Times edited</span>
            ) : null}
            {session.duplicate_day_session || log?.duplicate_day_session ? (
              <span className="admin-badge admin-badge--warning sessions-dash__pill">Same-day duplicate</span>
            ) : null}
          </>
        }
        actions={actions}
      >
        {detailBody}
      </AdminTaskCard>
    </li>
  )
}

function OrphanLogRow({
  log,
  caseId,
  expandKey,
  expanded,
  onToggleExpand,
  canReview,
  onReviewLog,
  actingLogId,
  rejectingLogId,
  setRejectingLogId,
  rejectComment,
  setRejectComment,
  onCommentCountChange,
}) {
  return (
    <li className="admin-queue__item case-sessions-logs__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <p className="admin-queue__title">Log #{log.id}</p>
          <p className="admin-queue__meta">
            Session #{log.session_id ?? '—'}
            {log.scheduled_date ? ` · ${fmtDate(log.scheduled_date)}` : ''}
            {logCommentMetaSuffix(log)}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <StatusBadge status={log.approval_status} />
          {log?.comment_count > 0 ? <LogCommentCountPill count={log.comment_count} /> : null}
          {log.resubmitted_at ? (
            <span className="admin-badge admin-badge--info sessions-dash__pill">Resubmitted</span>
          ) : null}
          <LogOpenParentCommentBadge log={log} />
        </div>
      </div>
      <SessionLogExpandableBody
        expandKey={expandKey}
        log={log}
        session={null}
        caseId={caseId}
        expanded={expanded}
        onToggleExpand={onToggleExpand}
        canReview={canReview}
        onReviewLog={onReviewLog}
        actingLogId={actingLogId}
        rejectingLogId={rejectingLogId}
        setRejectingLogId={setRejectingLogId}
        rejectComment={rejectComment}
        setRejectComment={setRejectComment}
        analyticsSessionId={log.session_id}
        onCommentCountChange={onCommentCountChange}
      />
    </li>
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
      {filteredSessions.length === 0 && filteredOrphanLogs.length === 0 ? (
        <p className="admin-muted" style={{ margin: 0 }}>
          {emptyMessage}
        </p>
      ) : (
      <AdminDataList
        desktop={
          <ul className="admin-queue case-sessions-logs">
            {filteredSessions.map((session) => {
              const log = logsBySessionId.get(session.id)
              const isHighlight = highlightSessionId && String(session.id) === String(highlightSessionId)
              const rowTitle = formatSessionLogRowTitle(session, { fmtDate })
              const expandKey = sessionExpandKey(session.id)
              const expanded = expandedKeys.has(expandKey)

              return (
                <li
                  key={session.id}
                  ref={isHighlight ? highlightRef : null}
                  className={`admin-queue__item case-sessions-logs__item ${isHighlight ? 'is-highlight' : ''}`}
                  style={{ flexDirection: 'column', alignItems: 'stretch' }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
                    <div>
                      <p className="admin-queue__title">
                        {rowTitle}
                      </p>
                      <p className="admin-queue__meta">
                        {buildSessionLogMeta(session, log)}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <StatusBadge status={session.status} />
                      {log ? <StatusBadge status={log.approval_status} /> : null}
                      {log?.comment_count > 0 ? <LogCommentCountPill count={log.comment_count} /> : null}
                      {log?.resubmitted_at ? (
                        <span className="admin-badge admin-badge--info sessions-dash__pill">Resubmitted</span>
                      ) : null}
                      <LogOpenParentCommentBadge log={log} />
                      {sessionHasTimeEdit(session, log) ? (
                        <span className="admin-badge admin-badge--warning sessions-dash__pill">Times edited</span>
                      ) : null}
                      {session.duplicate_day_session || log?.duplicate_day_session ? (
                        <span className="admin-badge admin-badge--warning sessions-dash__pill">Same-day duplicate</span>
                      ) : null}
                    </div>
                  </div>

                  {!log ? (
                    <p className="case-sessions-logs__pending">
                      {session.status === 'IN_PROGRESS' || session.status === 'SCHEDULED'
                        ? 'Session in progress — log not submitted yet.'
                        : 'No therapist log submitted for this session.'}
                    </p>
                  ) : (
                    <SessionLogExpandableBody
                      expandKey={expandKey}
                      log={log}
                      session={session}
                      caseId={caseId}
                      expanded={expanded}
                      analyticsSessionId={session.id}
                      {...sharedExpandProps}
                    />
                  )}
                </li>
              )
            })}
          </ul>
        }
        mobile={filteredSessions.map((session) => {
          const log = logsBySessionId.get(session.id)
          const expandKey = sessionExpandKey(session.id)
          return (
            <SessionLogCard
              key={session.id}
              session={session}
              log={log}
              caseId={caseId}
              highlightSessionId={highlightSessionId}
              highlightRef={highlightRef}
              expandKey={expandKey}
              expanded={expandedKeys.has(expandKey)}
              {...sharedExpandProps}
            />
          )
        })}
      />
      )}

      {filteredOrphanLogs.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <p className="admin-queue__meta" style={{ marginBottom: 8 }}>
            Orphan logs (session record missing)
          </p>
          <ul className="admin-queue case-sessions-logs">
            {filteredOrphanLogs.map((log) => {
              const expandKey = orphanExpandKey(log.id)
              return (
                <OrphanLogRow
                  key={log.id}
                  log={log}
                  caseId={caseId}
                  expandKey={expandKey}
                  expanded={expandedKeys.has(expandKey)}
                  {...sharedExpandProps}
                />
              )
            })}
          </ul>
        </div>
      ) : null}
    </>
  )
}
