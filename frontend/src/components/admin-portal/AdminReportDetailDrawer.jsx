import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { categoryLabel } from '../../lib/reportCategories.js'
import { reportAdminEditPath, reportViewPath } from '../../lib/reportManagementPaths.js'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../reports/report-editor.css'
import './admin-reports.css'

function statusPillClass(status) {
  const key = String(status || '').toLowerCase()
  return `admin-reports__status-pill admin-reports__status-pill--${key.replace(/_/g, '_')}`
}

function workflowHint(detail) {
  if (!detail) return null
  if (detail.status === 'UNDER_REVIEW') {
    if (detail.can_cm_publish) {
      return 'Approve publishes this report to the parent portal.'
    }
    if (detail.can_admin_override_publish) {
      return 'Approve uses admin override (CM has not published within 10 days).'
    }
    if (detail.days_until_admin_override != null) {
      return `Admin override available in ${detail.days_until_admin_override} day(s) if CM has not published.`
    }
    return 'Use the comment box for send-back or reject. Approve can include an optional note.'
  }
  if (detail.status === 'PUBLISHED' && detail.parent_review_status === 'CHANGES_REQUESTED') {
    return 'Parent requested changes — edit the report, then approve to resend.'
  }
  if (detail.status === 'REJECTED') {
    return 'Rejected — therapist may revise; you can edit and send back for review.'
  }
  if (detail.status === 'DRAFT') {
    return 'Draft — not yet in the parent-facing queue.'
  }
  return null
}

function mergeCommentHistory(detail, isMonthly) {
  const items = []
  for (const h of detail?.review_history || []) {
    items.push({
      id: `review-${h.id}`,
      kind: 'review',
      author: h.reviewer_name || 'Reviewer',
      body: h.comment || '—',
      decision: h.decision,
      at: h.created_at,
    })
  }
  if (isMonthly) {
    for (const c of detail?.comments || []) {
      items.push({
        id: `comment-${c.id}`,
        kind: 'discussion',
        author: c.author_name || 'User',
        body: c.body,
        at: c.created_at,
      })
    }
  }
  return items.sort((a, b) => new Date(b.at || 0) - new Date(a.at || 0))
}

export function AdminReportDetailDrawer({ reportType, reportId, onClose, onAction }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [acting, setActing] = useState(false)
  const [reviewComment, setReviewComment] = useState('')
  const [sendTarget, setSendTarget] = useState('case_manager')
  const { can } = useAuth()
  const { canReviewReports } = useModuleWrite()
  const isSuperAdmin = can('case.read.all')
  const productModule = detail?.product_module || 'homecare'
  const canReviewThis = canReviewReports(productModule)
  const isMonthly = reportType === 'monthly'

  const loadDetail = useCallback(async () => {
    if (!reportId || !reportType) return
    setLoading(true)
    setErr('')
    try {
      const row = await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}`)
      setDetail(row)
    } catch (e) {
      setErr(e.message || 'Could not load report')
      setDetail(null)
    } finally {
      setLoading(false)
    }
  }, [reportId, reportType])

  useEffect(() => {
    loadDetail()
  }, [loadDetail])

  async function refreshAfterAction(closeAfter = false) {
    await loadDetail()
    onAction?.()
    if (closeAfter) onClose()
  }

  const commentHistory = useMemo(() => (detail ? mergeCommentHistory(detail, isMonthly) : []), [detail, isMonthly])

  async function handleApprove() {
    setActing(true)
    setErr('')
    try {
      if (isMonthly) {
        if (detail?.status === 'PUBLISHED' && detail?.parent_review_status === 'CHANGES_REQUESTED') {
          await apiFetch(`/api/v1/reports/monthly/${reportId}/resend-to-parent`, { method: 'POST' })
        } else if (detail?.can_cm_publish || detail?.can_admin_override_publish) {
          await apiFetch(`/api/v1/admin/reports/monthly/${reportId}/publish-to-parent`, {
            method: 'POST',
            body: JSON.stringify({ comment: reviewComment.trim() || undefined }),
          })
        } else if (canCmReviewPath) {
          if (!reviewComment.trim()) {
            setErr('Comment is required to approve')
            setActing(false)
            return
          }
          await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}/cm-review`, {
            method: 'POST',
            body: JSON.stringify({ comment: reviewComment.trim(), request_changes: false }),
          })
        } else {
          setErr('You cannot approve this report in its current state')
          setActing(false)
          return
        }
      } else if (detail?.status === 'UNDER_REVIEW') {
        await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'observation',
            ids: [reportId],
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
      }
      setReviewComment('')
      await refreshAfterAction(true)
    } catch (e) {
      setErr(e.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function handleSendForReview() {
    if (!reviewComment.trim()) {
      setErr('Add a comment explaining what to change before sending for review')
      return
    }
    setActing(true)
    setErr('')
    try {
      await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}/send-for-review`, {
        method: 'POST',
        body: JSON.stringify({
          target: sendTarget,
          comment: reviewComment.trim(),
        }),
      })
      setReviewComment('')
      await refreshAfterAction(false)
    } catch (e) {
      setErr(e.message || 'Send for review failed')
    } finally {
      setActing(false)
    }
  }

  async function handleReject() {
    if (!reviewComment.trim()) {
      setErr('Add a comment with the rejection reason')
      return
    }
    setActing(true)
    setErr('')
    try {
      await apiFetch('/api/v1/admin/reports/bulk/reject', {
        method: 'POST',
        body: JSON.stringify({
          report_type: reportType,
          ids: [reportId],
          comment: reviewComment.trim(),
        }),
      })
      setReviewComment('')
      await refreshAfterAction(true)
    } catch (e) {
      setErr(e.message || 'Reject failed')
    } finally {
      setActing(false)
    }
  }

  const canResend =
    isMonthly &&
    detail?.status === 'PUBLISHED' &&
    detail?.parent_review_status === 'CHANGES_REQUESTED'
  const canCmPublish = isMonthly && detail?.can_cm_publish && canReviewThis
  const canAdminOverride = isMonthly && detail?.can_admin_override_publish && canReviewThis
  const canCmReviewPath =
    !isSuperAdmin && can('monthly_report.approve') && detail?.status === 'UNDER_REVIEW' && isMonthly
  const canWorkflow =
    canReviewThis && detail && ['UNDER_REVIEW', 'DRAFT', 'REJECTED'].includes(detail.status)

  const showApprove =
    canReviewThis &&
    (canResend ||
      canCmPublish ||
      canAdminOverride ||
      canCmReviewPath ||
      (!isMonthly && detail?.status === 'UNDER_REVIEW' && isSuperAdmin))

  const showSendForReview = canWorkflow && detail?.status === 'UNDER_REVIEW'
  const showReject =
    canReviewThis &&
    detail?.status === 'UNDER_REVIEW' &&
    (isSuperAdmin || can('monthly_report.approve'))

  const approveLabel = canResend
    ? 'Approve & resend'
    : canAdminOverride
      ? 'Approve (override)'
      : canCmPublish
        ? 'Approve'
        : canCmReviewPath
          ? 'Approve (CM sign-off)'
          : 'Approve for parents'

  const viewPath = detail && isMonthly ? reportViewPath(detail) : null
  const pdfPath = isMonthly
    ? `/api/v1/reports/monthly/${reportId}/download`
    : `/api/v1/reports/observation/${reportId}/download`

  return (
    <>
      <div className="admin-reports__drawer-backdrop" onClick={onClose} role="presentation" />
      <aside className="admin-reports__drawer" aria-label="Report detail">
        <div className="admin-reports__drawer-header">
          <div className="admin-reports__drawer-header-main">
            <p className="admin-reports__drawer-eyebrow">
              {reportType === 'observation' ? 'Observation report' : 'Monthly report'}
            </p>
            <h2 className="admin-reports__drawer-title">{detail?.label || '…'}</h2>
            {detail ? (
              <p className="admin-reports__drawer-sub admin-reports__drawer-sub--header">
                {detail.child_name} · {detail.case_code} · Therapist {detail.therapist_name || '—'}
              </p>
            ) : null}
          </div>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? <p className="admin-muted admin-reports__drawer-pad">Loading…</p> : null}
        {err ? <p className="admin-alert admin-alert--error admin-reports__drawer-pad">{err}</p> : null}

        {detail ? (
          <>
            <div className="admin-reports__drawer-body">
              <div className="admin-reports__drawer-meta">
                <span className={statusPillClass(detail.status)}>{detail.status?.replaceAll('_', ' ')}</span>
                {detail.parent_review_status ? (
                  <span className="admin-reports__parent-badge">{detail.parent_review_status}</span>
                ) : null}
                {detail.visibility_status ? (
                  <span className="admin-reports__vis-badge">{detail.visibility_status.replaceAll('_', ' ')}</span>
                ) : null}
              </div>
              {detail.category ? (
                <p className="admin-reports__drawer-sub">
                  {categoryLabel(detail.category)}
                  {detail.sub_category ? ` · ${detail.sub_category}` : ''}
                </p>
              ) : null}
              {workflowHint(detail) ? (
                <p className="admin-reports__workflow-hint">{workflowHint(detail)}</p>
              ) : null}

              <div className="admin-reports__drawer-links">
                {viewPath ? (
                  <Link to={viewPath} className="admin-btn admin-btn--secondary admin-btn--sm">
                    View full report
                  </Link>
                ) : null}
                {isMonthly && detail.status !== 'PUBLISHED' ? (
                  <Link to={reportAdminEditPath(reportId)} className="admin-btn admin-btn--ghost admin-btn--sm">
                    Edit report
                  </Link>
                ) : null}
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  onClick={() => apiDownload(pdfPath, `report_${detail.label || reportId}.pdf`)}
                >
                  PDF
                </button>
              </div>

              <section className="admin-reports__drawer-section admin-reports__preview-section">
                <h3>Report preview</h3>
                <div className="admin-reports__content-preview admin-reports__content-preview--tall">
                  <ReportHtmlView html={detail.body_html || detail.content || detail.summary} />
                </div>
                {detail.plan_next_month ? (
                  <div className="admin-reports__plan-block">
                    <strong>Plan for next month</strong>
                    <p>{detail.plan_next_month}</p>
                  </div>
                ) : null}
              </section>

              {detail.parent_feedback ? (
                <section className="admin-reports__drawer-section">
                  <h3>Parent feedback</h3>
                  <p className="admin-reports__drawer-note">{detail.parent_feedback}</p>
                </section>
              ) : null}

              <section className="admin-reports__drawer-section">
                <h3>Comment history</h3>
                {commentHistory.length === 0 ? (
                  <p className="admin-muted" style={{ fontSize: '0.8125rem', margin: 0 }}>
                    No comments yet. They appear when you send back, approve, or reject.
                  </p>
                ) : (
                  <ul className="admin-reports__history-list admin-reports__comment-history">
                    {commentHistory.map((item) => (
                      <li key={item.id} className="admin-reports__history-item">
                        {item.decision ? (
                          <span className="admin-reports__history-decision">{item.decision}</span>
                        ) : (
                          <span className="admin-reports__history-decision admin-reports__history-decision--discussion">
                            Discussion
                          </span>
                        )}
                        <span className="admin-reports__history-who">
                          {item.author}
                          {item.at ? ` · ${new Date(item.at).toLocaleString()}` : ''}
                        </span>
                        <p>{item.body}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {canWorkflow ? (
                <section className="admin-reports__drawer-section admin-reports__review-panel">
                  <h3>Review</h3>
                  <p className="admin-reports__card-help">
                    One comment field for all actions. Send for review and reject require a note; it is saved to
                    comment history automatically.
                  </p>
                  <label className="admin-reports__field-label" htmlFor="report-review-comment">
                    Comment
                  </label>
                  <textarea
                    id="report-review-comment"
                    className="admin-input admin-reports__review-comment"
                    rows={3}
                    placeholder="Required for send back or reject. Optional for approve."
                    value={reviewComment}
                    onChange={(e) => setReviewComment(e.target.value)}
                  />
                </section>
              ) : null}
            </div>

            {canWorkflow && (showApprove || showSendForReview || showReject) ? (
              <div className="admin-reports__drawer-footer-wrap">
                {showSendForReview ? (
                  <div className="admin-reports__drawer-send-row">
                    <label className="admin-reports__field-label" htmlFor="report-send-target">
                      Send for review to
                    </label>
                    <select
                      id="report-send-target"
                      className="admin-input"
                      value={sendTarget}
                      onChange={(e) => setSendTarget(e.target.value)}
                      disabled={acting}
                    >
                      <option value="case_manager">Case manager</option>
                      <option value="therapist">Therapist</option>
                    </select>
                  </div>
                ) : null}
                <div className="admin-reports__drawer-footer admin-reports__drawer-footer--review">
                {showApprove ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={acting}
                    onClick={handleApprove}
                  >
                    {acting ? '…' : approveLabel}
                  </button>
                ) : null}
                {showSendForReview ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary admin-btn--sm"
                    disabled={acting || !reviewComment.trim()}
                    onClick={handleSendForReview}
                  >
                    Send for review
                  </button>
                ) : null}
                {showReject ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--sm admin-reports__reject-btn"
                    disabled={acting || !reviewComment.trim()}
                    onClick={handleReject}
                  >
                    Reject
                  </button>
                ) : null}
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </aside>
    </>
  )
}
