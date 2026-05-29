import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import { AdminDataList, AdminTaskCard, RejectWithComment, StatusBadge } from './ui/index.js'
import { CaseSessionMonthlyReportBar } from './CaseSessionMonthlyReportBar.jsx'
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
}) {
  if (!log) return null

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
          <SessionLogReadOnly log={log} session={session} variant="admin" hideHeader />
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
}) {
  const isHighlight = highlightSessionId && String(session.id) === String(highlightSessionId)
  const timeRange = formatSessionTimeRange(session)
  const title = `${fmtDate(session.scheduled_date)}${timeRange ? ` · ${timeRange}` : ''}`

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
        />
      )}
    </>
  )

  return (
    <li ref={isHighlight ? highlightRef : null}>
      <AdminTaskCard
        highlight={isHighlight}
        title={title}
        meta={`Session #${session.id}${session.therapist_user_id ? ` · Therapist #${session.therapist_user_id}` : ''}`}
        badges={
          <>
            <StatusBadge status={session.status} />
            {log ? <StatusBadge status={log.approval_status} /> : null}
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
}) {
  return (
    <li className="admin-queue__item case-sessions-logs__item" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <p className="admin-queue__title">Log #{log.id}</p>
          <p className="admin-queue__meta">
            Session #{log.session_id ?? '—'}
            {log.scheduled_date ? ` · ${fmtDate(log.scheduled_date)}` : ''}
          </p>
        </div>
        <StatusBadge status={log.approval_status} />
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
  const highlightRef = useRef(null)
  const autoExpandDoneRef = useRef('')

  const fetchSessionsAndLogs = useCallback(async () => {
    const [sessData, logData] = await Promise.all([
      apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
      apiFetch(`/api/v1/daily-logs?case_id=${caseId}`),
    ])
    const nextSessions = unwrapList(sessData)
    const nextLogs = Array.isArray(logData) ? logData : unwrapList(logData)
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
    return [...sessions].sort(
      (a, b) => sessionSortKey(a, logsBySessionId) - sessionSortKey(b, logsBySessionId),
    )
  }, [sessions, logsBySessionId])

  const orphanLogs = useMemo(
    () => logs.filter((l) => !sessions.some((s) => s.id === l.session_id)),
    [logs, sessions],
  )

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
  }

  return (
    <>
      <CaseSessionMonthlyReportBar caseId={caseId} />
      <p className="case-sessions-logs__intro admin-portal-lead" style={{ margin: '0 0 12px', fontSize: '0.8125rem', color: '#64748b' }}>
        Sessions appear when scheduled. Daily logs appear after the therapist submits notes. Use View full log to
        review and approve or reject.
      </p>
      <AdminDataList
        desktop={
          <ul className="admin-queue case-sessions-logs">
            {sortedSessions.map((session) => {
              const log = logsBySessionId.get(session.id)
              const isHighlight = highlightSessionId && String(session.id) === String(highlightSessionId)
              const timeRange = formatSessionTimeRange(session)
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
                        {fmtDate(session.scheduled_date)}
                        {timeRange ? ` · ${timeRange}` : ''}
                      </p>
                      <p className="admin-queue__meta">
                        Session #{session.id}
                        {session.therapist_user_id ? ` · Therapist #${session.therapist_user_id}` : ''}
                      </p>
                    </div>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                      <StatusBadge status={session.status} />
                      {log ? <StatusBadge status={log.approval_status} /> : null}
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
        mobile={sortedSessions.map((session) => {
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

      {orphanLogs.length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <p className="admin-queue__meta" style={{ marginBottom: 8 }}>
            Orphan logs (session record missing)
          </p>
          <ul className="admin-queue case-sessions-logs">
            {orphanLogs.map((log) => {
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
