import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatDisplayDate } from '../../lib/datetime.js'
import { buildSessionLogMeta } from '../../lib/sessionLogComments.js'
import { formatSessionLogRowTitle, sessionHasTimeEdit } from '../../lib/sessionTimes.js'
import { SessionLogReadOnly } from '../daily-logs/SessionLogReadOnly.jsx'
import {
  AdminEmptyState,
  AdminPageHeader,
  RejectWithComment,
  StatusBadge,
} from './ui/index.js'
import './admin-cm-log-review.css'

function fmtDate(s) {
  if (!s) return '—'
  const [y, m, d] = String(s).slice(0, 10).split('-')
  return `${d}/${m}/${String(y).slice(2)}`
}

function logSortKey(log) {
  const ts = log.resubmitted_at || log.submitted_at
  return ts ? new Date(ts).getTime() : 0
}

function LogStackItem({ log, session, active, onSelect }) {
  const title = session
    ? formatSessionLogRowTitle(session, { fmtDate })
    : `Log #${log.id}`
  return (
    <button
      type="button"
      className={`admin-cm-log-review__stack-item${active ? ' is-active' : ''}`}
      onClick={() => onSelect(log.id)}
    >
      <span className="admin-cm-log-review__stack-title">{title}</span>
      <span className="admin-cm-log-review__stack-meta">
        {buildSessionLogMeta(session, log)}
        {log.resubmitted_at ? ' · Resubmitted' : ''}
      </span>
    </button>
  )
}

export function AdminCmLogReviewPage() {
  const { can, isViewOnly } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [queue, setQueue] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actingLogId, setActingLogId] = useState(null)
  const [rejecting, setRejecting] = useState(false)
  const [rejectComment, setRejectComment] = useState('')

  const canReview = can('daily_log.review') && !isViewOnly

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/v1/admin/cm/logs/review-queue')
      setQueue(data)
    } catch (err) {
      setError(err.message || 'Could not load pending logs')
      setQueue(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const cases = queue?.cases || []
  const totalPending = queue?.total_pending ?? 0

  const caseIdParam = searchParams.get('case_id')
  const logIdParam = searchParams.get('log_id')

  const selectedCase = useMemo(() => {
    if (!cases.length) return null
    if (caseIdParam) {
      return cases.find((c) => String(c.case_id) === caseIdParam) || cases[0]
    }
    if (logIdParam) {
      return cases.find((c) => c.logs.some((l) => String(l.id) === logIdParam)) || cases[0]
    }
    return cases[0]
  }, [cases, caseIdParam, logIdParam])

  const sortedLogs = useMemo(() => {
    if (!selectedCase?.logs?.length) return []
    return [...selectedCase.logs].sort((a, b) => logSortKey(b) - logSortKey(a))
  }, [selectedCase])

  const activeLogId = useMemo(() => {
    if (!sortedLogs.length) return null
    if (logIdParam && sortedLogs.some((l) => String(l.id) === logIdParam)) {
      return Number(logIdParam)
    }
    return sortedLogs[0].id
  }, [sortedLogs, logIdParam])

  const activeIndex = sortedLogs.findIndex((l) => l.id === activeLogId)
  const activeLog = activeIndex >= 0 ? sortedLogs[activeIndex] : null
  const logsAbove = activeIndex > 0 ? sortedLogs.slice(0, activeIndex) : []
  const logsBelow = activeIndex >= 0 ? sortedLogs.slice(activeIndex + 1) : []

  useEffect(() => {
    if (!selectedCase || !activeLogId) return
    const next = new URLSearchParams(searchParams)
    let changed = false
    if (next.get('case_id') !== String(selectedCase.case_id)) {
      next.set('case_id', String(selectedCase.case_id))
      changed = true
    }
    if (next.get('log_id') !== String(activeLogId)) {
      next.set('log_id', String(activeLogId))
      changed = true
    }
    if (changed) setSearchParams(next, { replace: true })
  }, [selectedCase, activeLogId, searchParams, setSearchParams])

  function selectCase(caseId) {
    const target = cases.find((c) => c.case_id === caseId)
    const sorted = [...(target?.logs || [])].sort((a, b) => logSortKey(b) - logSortKey(a))
    const firstLog = sorted[0]
    const next = new URLSearchParams()
    next.set('case_id', String(caseId))
    if (firstLog) next.set('log_id', String(firstLog.id))
    setSearchParams(next, { replace: true })
  }

  function selectLog(logId) {
    const next = new URLSearchParams(searchParams)
    next.set('log_id', String(logId))
    setSearchParams(next, { replace: true })
  }

  async function handleReview(action, comment = null) {
    if (!activeLog || !canReview) return
    setActingLogId(activeLog.id)
    try {
      const opts = { method: 'POST' }
      if (action === 'reject') {
        opts.body = JSON.stringify({ comment: comment || '' })
      }
      await apiFetch(`/api/v1/daily-logs/${activeLog.id}/${action}`, opts)
      const data = await apiFetch('/api/v1/admin/cm/logs/review-queue')
      setQueue(data)
      const remaining = data?.cases || []
      if (!remaining.length) {
        setSearchParams({}, { replace: true })
        return
      }
      const sameCase = remaining.find((c) => c.case_id === selectedCase?.case_id)
      if (sameCase?.logs?.length) {
        selectCase(sameCase.case_id)
        return
      }
      const nextCase = remaining[0]
      const next = new URLSearchParams()
      next.set('case_id', String(nextCase.case_id))
      if (nextCase.logs?.[0]) next.set('log_id', String(nextCase.logs[0].id))
      setSearchParams(next, { replace: true })
    } catch (err) {
      setError(err.message || 'Could not update log')
    } finally {
      setActingLogId(null)
      setRejecting(false)
      setRejectComment('')
    }
  }

  const activeSession = activeLog?.session || null
  const hasTimeEdit = activeSession && activeLog ? sessionHasTimeEdit(activeSession, activeLog) : false

  return (
    <div className="admin-page admin-cm-log-review">
      <AdminPageHeader
        eyebrow="Case management"
        title="Session log review"
        subtitle="Approve or reject pending therapist logs — one at a time, scoped to your caseload."
        actions={
          <div className="admin-btn-group">
            <Link to="/admin/cm" className="admin-btn admin-btn--ghost admin-btn--sm">
              ← Dashboard
            </Link>
            <Link to="/admin/cases" className="admin-btn admin-btn--secondary admin-btn--sm">
              All cases
            </Link>
          </div>
        }
      />

      {error ? (
        <p className="admin-alert admin-alert--error">
          {error}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginLeft: 8 }} onClick={load}>
            Retry
          </button>
        </p>
      ) : null}

      {loading ? (
        <p className="admin-muted">Loading pending logs…</p>
      ) : totalPending === 0 ? (
        <AdminEmptyState
          title="No pending logs"
          description="You're all caught up. New therapist submissions will appear here for review."
          action={
            <Link to="/admin/cm" className="admin-btn admin-btn--primary admin-btn--sm">
              Back to dashboard
            </Link>
          }
        />
      ) : (
        <div className="admin-cm-log-review__layout">
          <aside className="admin-cm-log-review__cases" aria-label="Cases with pending logs">
            <p className="admin-cm-log-review__cases-head">
              Pending cases
              <span className="admin-cm-log-review__cases-count">{cases.length}</span>
            </p>
            <ul className="admin-cm-log-review__case-list">
              {cases.map((c) => (
                <li key={c.case_id}>
                  <button
                    type="button"
                    className={`admin-cm-log-review__case-btn${
                      selectedCase?.case_id === c.case_id ? ' is-active' : ''
                    }`}
                    onClick={() => selectCase(c.case_id)}
                  >
                    <span className="admin-cm-log-review__case-code">{c.case_code}</span>
                    <span className="admin-cm-log-review__case-child">{c.child_name || '—'}</span>
                    <span className="admin-cm-log-review__case-meta">
                      {c.therapist_name || 'No therapist'}
                      {' · '}
                      {c.pending_count} log{c.pending_count === 1 ? '' : 's'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section className="admin-cm-log-review__main" aria-label="Log review">
            {selectedCase && activeLog ? (
              <>
                <header className="admin-cm-log-review__case-detail">
                  <div>
                    <h2 className="admin-cm-log-review__case-title">
                      {selectedCase.child_name || selectedCase.case_code}
                    </h2>
                    <p className="admin-cm-log-review__case-sub">
                      {selectedCase.case_code}
                      {' · '}
                      {selectedCase.service_type}
                      {selectedCase.therapist_name ? ` · ${selectedCase.therapist_name}` : ''}
                    </p>
                  </div>
                  <div className="admin-cm-log-review__case-badges">
                    <StatusBadge status={selectedCase.status} />
                    <span className="admin-muted" style={{ fontSize: '0.8125rem' }}>
                      {totalPending} pending overall
                    </span>
                  </div>
                </header>

                {logsAbove.length > 0 ? (
                  <div className="admin-cm-log-review__stack admin-cm-log-review__stack--above">
                    <p className="admin-cm-log-review__stack-label">Earlier in queue</p>
                    {logsAbove.map((log) => (
                      <LogStackItem
                        key={log.id}
                        log={log}
                        session={log.session}
                        active={false}
                        onSelect={selectLog}
                      />
                    ))}
                  </div>
                ) : null}

                <article className="admin-cm-log-review__focus">
                  <div className="admin-cm-log-review__focus-head">
                    <div>
                      <h3 className="admin-cm-log-review__focus-title">
                        {activeSession
                          ? formatSessionLogRowTitle(activeSession, { fmtDate })
                          : `Log #${activeLog.id}`}
                      </h3>
                      <p className="admin-cm-log-review__focus-meta">
                        Submitted {formatDisplayDate(activeLog.submitted_at?.slice?.(0, 10) || activeLog.submitted_at)}
                        {activeLog.resubmitted_at ? ' · Resubmitted after changes' : ''}
                      </p>
                    </div>
                    <div className="admin-cm-log-review__focus-badges">
                      <StatusBadge status={activeLog.approval_status} />
                      {hasTimeEdit ? (
                        <span className="admin-badge admin-badge--warning">Times edited</span>
                      ) : null}
                    </div>
                  </div>

                  {activeLog.resubmitted_at ? (
                    <p className="admin-cm-log-review__notice" role="status">
                      Resubmitted after changes — review corrections before approving.
                    </p>
                  ) : null}

                  <SessionLogReadOnly
                    log={activeLog}
                    session={activeSession}
                    variant="admin"
                    hideHeader
                  />

                  {canReview ? (
                    <div className="admin-cm-log-review__actions">
                      <RejectWithComment
                        rejecting={rejecting}
                        comment={rejectComment}
                        onCommentChange={setRejectComment}
                        onStartReject={() => {
                          setRejecting(true)
                          setRejectComment('')
                        }}
                        onCancelReject={() => {
                          setRejecting(false)
                          setRejectComment('')
                        }}
                        onConfirmReject={() => {
                          const note = rejectComment.trim()
                          if (!note) return
                          handleReview('reject', note)
                        }}
                        onApprove={() => handleReview('approve')}
                        processing={actingLogId === activeLog.id}
                        approveLabel={hasTimeEdit ? 'Approve log & times' : 'Approve'}
                        placeholder="Why is this log rejected? (required)"
                      />
                    </div>
                  ) : (
                    <p className="admin-muted">View-only — you cannot approve or reject logs.</p>
                  )}
                </article>

                {logsBelow.length > 0 ? (
                  <div className="admin-cm-log-review__stack admin-cm-log-review__stack--below">
                    <p className="admin-cm-log-review__stack-label">Next in queue</p>
                    {logsBelow.map((log) => (
                      <LogStackItem
                        key={log.id}
                        log={log}
                        session={log.session}
                        active={false}
                        onSelect={selectLog}
                      />
                    ))}
                  </div>
                ) : null}
              </>
            ) : (
              <AdminEmptyState title="Select a case" description="Choose a case on the left to review its pending logs." />
            )}
          </section>
        </div>
      )}
    </div>
  )
}
