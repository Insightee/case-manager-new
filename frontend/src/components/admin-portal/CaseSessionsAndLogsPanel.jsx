import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'
import { AdminDataList, AdminTaskCard, RejectWithComment, StatusBadge } from './ui/index.js'

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

function SessionLogCard({
  session,
  log,
  caseId,
  highlightSessionId,
  highlightRef,
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

  const actions = (
    <>
      {!log ? (
        <span className="admin-muted" style={{ fontSize: '0.8125rem' }}>
          {session.status === 'IN_PROGRESS' || session.status === 'SCHEDULED'
            ? 'Log not submitted yet'
            : 'No therapist log'}
        </span>
      ) : null}
      {log?.approval_status === 'PENDING' && canReview ? (
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
      ) : null}
      <Link
        to={`/admin/logs?tab=sessions&case_id=${caseId}&session_id=${session.id}`}
        className="admin-btn admin-btn--ghost admin-btn--sm"
      >
        Sessions board
      </Link>
    </>
  )

  const detailBody = log ? (
    <>
      {log.session_notes ? (
        <p>
          <strong>Internal:</strong> {log.session_notes}
        </p>
      ) : null}
      {log.parent_notes ? (
        <p>
          <strong>For family:</strong> {log.parent_notes}
        </p>
      ) : null}
      {log.approval_status === 'REJECTED' && log.review_note ? (
        <p>
          <strong>Rejection:</strong> {log.review_note}
        </p>
      ) : null}
    </>
  ) : null

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

export function CaseSessionsAndLogsPanel({
  caseId,
  highlightSessionId,
  canReview,
  onReviewLog,
  actingLogId,
}) {
  const [sessions, setSessions] = useState([])
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [rejectingLogId, setRejectingLogId] = useState(null)
  const [rejectComment, setRejectComment] = useState('')
  const highlightRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    Promise.all([
      apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=100`),
      apiFetch(`/api/v1/daily-logs?case_id=${caseId}`),
    ])
      .then(([sessData, logData]) => {
        if (cancelled) return
        setSessions(unwrapList(sessData))
        setLogs(Array.isArray(logData) ? logData : unwrapList(logData))
      })
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
  }, [caseId])

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

  useEffect(() => {
    if (!highlightSessionId || loading) return
    const t = setTimeout(() => {
      highlightRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 120)
    return () => clearTimeout(t)
  }, [highlightSessionId, loading, sessions.length])

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

  const cardProps = {
    caseId,
    highlightSessionId,
    highlightRef,
    canReview,
    onReviewLog,
    actingLogId,
    rejectingLogId,
    setRejectingLogId,
    rejectComment,
    setRejectComment,
  }

  return (
    <>
      <p className="case-sessions-logs__intro admin-portal-lead" style={{ margin: '0 0 12px', fontSize: '0.8125rem', color: '#64748b' }}>
        Sessions appear when scheduled. Daily logs appear after the therapist submits notes.
      </p>
      <AdminDataList
        desktop={
          <ul className="admin-queue case-sessions-logs">
            {sortedSessions.map((session) => {
              const log = logsBySessionId.get(session.id)
              const isHighlight = highlightSessionId && String(session.id) === String(highlightSessionId)
              const timeRange = formatSessionTimeRange(session)
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

                  {log?.approval_status === 'PENDING' && canReview ? (
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
                  ) : null}

                  {!log ? (
                    <p className="case-sessions-logs__pending">
                      {session.status === 'IN_PROGRESS' || session.status === 'SCHEDULED'
                        ? 'Session in progress — log not submitted yet.'
                        : 'No therapist log submitted for this session.'}
                    </p>
                  ) : (
                    <>
                      {log.session_notes ? (
                        <p style={{ fontSize: '0.8rem', margin: '8px 0 0' }}>
                          <strong>Internal:</strong> {log.session_notes}
                        </p>
                      ) : null}
                      {log.parent_notes ? (
                        <p style={{ fontSize: '0.8rem', margin: '4px 0 0' }}>
                          <strong>For family:</strong> {log.parent_notes}
                        </p>
                      ) : null}
                      {log.approval_status === 'REJECTED' && log.review_note ? (
                        <p className="admin-muted" style={{ fontSize: '0.8rem', marginTop: 8 }}>
                          <strong>Rejection:</strong> {log.review_note}
                        </p>
                      ) : null}
                    </>
                  )}

                  <Link
                    to={`/admin/logs?tab=sessions&case_id=${caseId}&session_id=${session.id}`}
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    style={{ marginTop: 8, alignSelf: 'flex-start' }}
                  >
                    Open in sessions board
                  </Link>
                </li>
              )
            })}
          </ul>
        }
        mobile={sortedSessions.map((session) => (
          <SessionLogCard
            key={session.id}
            session={session}
            log={logsBySessionId.get(session.id)}
            {...cardProps}
          />
        ))}
      />

      {logs.filter((l) => !sessions.some((s) => s.id === l.session_id)).length > 0 ? (
        <div style={{ marginTop: 16 }}>
          <p className="admin-queue__meta" style={{ marginBottom: 8 }}>
            Orphan logs (session record missing)
          </p>
          <ul className="admin-queue">
            {logs
              .filter((l) => !sessions.some((s) => s.id === l.session_id))
              .map((log) => (
                <li key={log.id} className="admin-queue__item">
                  <p className="admin-queue__title">Log #{log.id}</p>
                  <StatusBadge status={log.approval_status} />
                </li>
              ))}
          </ul>
        </div>
      ) : null}
    </>
  )
}
