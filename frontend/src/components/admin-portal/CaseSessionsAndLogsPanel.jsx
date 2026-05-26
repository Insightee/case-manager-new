import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { formatSessionTimeRange } from '../../lib/sessionLogUtils.js'
import { StatusBadge } from './ui/index.js'

function fmtDate(s) {
  if (!s) return '—'
  const [y, m, d] = String(s).slice(0, 10).split('-')
  return `${d}/${m}/${String(y).slice(2)}`
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

  return (
    <>
      <p style={{ margin: '0 0 12px', fontSize: '0.8125rem', color: '#64748b' }}>
        Sessions appear as soon as they are scheduled. A daily log only exists after the therapist submits notes
        (usually after the session ends).
      </p>
      <ul className="admin-queue case-sessions-logs">
        {sessions.map((session) => {
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
                  {log.approval_status === 'PENDING' && canReview ? (
                    <div className="admin-btn-group" style={{ marginTop: 8 }}>
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm admin-btn--primary"
                        disabled={actingLogId === log.id}
                        onClick={() => onReviewLog(log.id, 'approve')}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm"
                        disabled={actingLogId === log.id}
                        onClick={() => onReviewLog(log.id, 'reject')}
                      >
                        Reject
                      </button>
                    </div>
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
