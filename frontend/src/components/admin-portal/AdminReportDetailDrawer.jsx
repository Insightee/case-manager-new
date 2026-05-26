import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { categoryLabel } from '../../lib/reportCategories.js'
import { reportEditPath, reportModuleLabel } from '../../lib/reportManagementPaths.js'
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
    return 'Open review — add comments, send to therapist or case manager, or approve for parents when ready.'
  }
  if (detail.status === 'PUBLISHED' && detail.parent_review_status === 'CHANGES_REQUESTED') {
    return 'Parent requested changes — edit in the report module, then resend when ready.'
  }
  if (detail.status === 'REJECTED') {
    return 'Rejected — therapist may revise; you can edit and send back for review.'
  }
  if (detail.status === 'DRAFT') {
    return 'Draft — not yet in the parent-facing queue.'
  }
  return null
}

export function AdminReportDetailDrawer({ reportType, reportId, onClose, onAction }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [acting, setActing] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectComment, setRejectComment] = useState('')
  const [noteComment, setNoteComment] = useState('')
  const [sendTarget, setSendTarget] = useState('case_manager')
  const [sendComment, setSendComment] = useState('')
  const [cmComment, setCmComment] = useState('')
  const { can } = useAuth()
  const { canReviewReports } = useModuleWrite()
  const canPublishToParent = can('case.read.all')
  const productModule = detail?.product_module || 'homecare'
  const canReviewThis = canReviewReports(productModule)

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

  async function approve() {
    setActing(true)
    setErr('')
    try {
      if (
        reportType === 'monthly' &&
        detail?.status === 'PUBLISHED' &&
        detail?.parent_review_status === 'CHANGES_REQUESTED'
      ) {
        await apiFetch(`/api/v1/reports/monthly/${reportId}/resend-to-parent`, { method: 'POST' })
      } else if (reportType === 'observation') {
        await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'observation',
            ids: [reportId],
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
      } else {
        await apiFetch(`/api/v1/reports/monthly/${reportId}/approve`, {
          method: 'POST',
          body: JSON.stringify({
            comment: 'Approved from report management',
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
      }
      await refreshAfterAction(true)
    } catch (e) {
      setErr(e.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function cmReview(requestChanges) {
    if (!cmComment.trim()) {
      setErr('Comment is required')
      return
    }
    setActing(true)
    setErr('')
    try {
      await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}/cm-review`, {
        method: 'POST',
        body: JSON.stringify({
          comment: cmComment.trim(),
          request_changes: requestChanges,
        }),
      })
      setCmComment('')
      await refreshAfterAction(requestChanges)
    } catch (e) {
      setErr(e.message || 'Review failed')
    } finally {
      setActing(false)
    }
  }

  async function addComment() {
    if (!noteComment.trim()) {
      setErr('Comment is required')
      return
    }
    setActing(true)
    setErr('')
    try {
      await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}/comment`, {
        method: 'POST',
        body: JSON.stringify({ comment: noteComment.trim() }),
      })
      setNoteComment('')
      await refreshAfterAction(false)
    } catch (e) {
      setErr(e.message || 'Could not save comment')
    } finally {
      setActing(false)
    }
  }

  async function sendForReview() {
    if (!sendComment.trim()) {
      setErr('Comment is required for send-for-review')
      return
    }
    setActing(true)
    setErr('')
    try {
      await apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}/send-for-review`, {
        method: 'POST',
        body: JSON.stringify({
          target: sendTarget,
          comment: sendComment.trim(),
        }),
      })
      setSendComment('')
      await refreshAfterAction(false)
    } catch (e) {
      setErr(e.message || 'Send for review failed')
    } finally {
      setActing(false)
    }
  }

  async function reject() {
    if (!rejectComment.trim()) {
      setErr('Rejection comment is required')
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
          comment: rejectComment.trim(),
        }),
      })
      setRejectOpen(false)
      await refreshAfterAction(true)
    } catch (e) {
      setErr(e.message || 'Reject failed')
    } finally {
      setActing(false)
    }
  }

  const canApprove =
    detail?.status === 'UNDER_REVIEW' ||
    (reportType === 'monthly' &&
      detail?.status === 'PUBLISHED' &&
      detail?.parent_review_status === 'CHANGES_REQUESTED')
  const canReject = canPublishToParent && detail?.status === 'UNDER_REVIEW'
  const canCmReview =
    !canPublishToParent && can('monthly_report.approve') && detail?.status === 'UNDER_REVIEW'
  const canWorkflow =
    canReviewThis &&
    detail &&
    ['UNDER_REVIEW', 'DRAFT', 'REJECTED'].includes(detail.status)
  const editPath = detail ? reportEditPath(detail, reportType) : null
  const editLabel = reportModuleLabel(detail?.category, reportType)

  const pdfPath =
    reportType === 'monthly'
      ? `/api/v1/reports/monthly/${reportId}/download`
      : `/api/v1/reports/observation/${reportId}/download`

  return (
    <>
      <div className="admin-reports__drawer-backdrop" onClick={onClose} role="presentation" />
      <aside className="admin-reports__drawer" aria-label="Report detail">
        <div className="admin-reports__drawer-header">
          <div>
            <p className="admin-reports__drawer-eyebrow">
              {reportType === 'observation' ? 'Observation report' : 'Monthly report'}
            </p>
            <h2 className="admin-reports__drawer-title">{detail?.label || '…'}</h2>
          </div>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? <p className="admin-muted">Loading…</p> : null}
        {err ? <p className="admin-alert admin-alert--error">{err}</p> : null}

        {detail ? (
          <>
            <div className="admin-reports__drawer-meta">
              <span className={statusPillClass(detail.status)}>{detail.status?.replaceAll('_', ' ')}</span>
              {detail.parent_review_status ? (
                <span className="admin-reports__parent-badge">{detail.parent_review_status}</span>
              ) : null}
              {detail.visibility_status ? (
                <span className="admin-reports__vis-badge">{detail.visibility_status.replaceAll('_', ' ')}</span>
              ) : null}
            </div>
            <p className="admin-reports__drawer-sub">
              {detail.child_name} · {detail.case_code} · {detail.therapist_name}
            </p>
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
              <Link to={`/admin/cases/${detail.case_id}?tab=reports`} className="admin-btn admin-btn--ghost admin-btn--sm">
                Case hub
              </Link>
              {editPath ? (
                <Link to={editPath} className="admin-btn admin-btn--secondary admin-btn--sm">
                  Open {editLabel}
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

            <section className="admin-reports__drawer-section">
              <h3>Report content</h3>
              <div className="admin-reports__content-preview">
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

            {detail.reviewer_comment ? (
              <section className="admin-reports__drawer-section">
                <h3>Latest review note</h3>
                <p className="admin-reports__drawer-note">{detail.reviewer_comment}</p>
              </section>
            ) : null}

            {detail.review_history?.length > 0 ? (
              <section className="admin-reports__drawer-section">
                <h3>Review history</h3>
                <ul className="admin-reports__history-list">
                  {detail.review_history.map((h) => (
                    <li key={h.id} className="admin-reports__history-item">
                      <span className="admin-reports__history-decision">{h.decision}</span>
                      <span className="admin-reports__history-who">
                        {h.reviewer_name || 'Reviewer'}
                        {h.created_at ? ` · ${new Date(h.created_at).toLocaleString()}` : ''}
                      </span>
                      <p>{h.comment || '—'}</p>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {canWorkflow ? (
              <section className="admin-reports__drawer-section admin-reports__drawer-actions-panel">
                <h3>Review actions</h3>
                <label className="admin-reports__field-label">
                  Add comment (stays under review)
                  <textarea
                    className="admin-input"
                    rows={2}
                    placeholder="Internal note visible in history…"
                    value={noteComment}
                    onChange={(e) => setNoteComment(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="admin-btn admin-btn--secondary admin-btn--sm"
                  disabled={acting}
                  onClick={addComment}
                >
                  Save comment
                </button>

                <label className="admin-reports__field-label" style={{ marginTop: 12 }}>
                  Send for review
                  <select
                    className="admin-input"
                    value={sendTarget}
                    onChange={(e) => setSendTarget(e.target.value)}
                  >
                    <option value="case_manager">Case manager</option>
                    <option value="therapist">Therapist</option>
                  </select>
                  <textarea
                    className="admin-input"
                    rows={2}
                    placeholder="What should they check or update?"
                    value={sendComment}
                    onChange={(e) => setSendComment(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  className="admin-btn admin-btn--sm"
                  disabled={acting}
                  onClick={sendForReview}
                >
                  Send for review
                </button>

                {canCmReview ? (
                  <div className="admin-reports__cm-block">
                    <p className="admin-reports__field-label">Case manager sign-off</p>
                    <textarea
                      className="admin-input"
                      rows={2}
                      placeholder="CM note (required)"
                      value={cmComment}
                      onChange={(e) => setCmComment(e.target.value)}
                    />
                    <div className="admin-btn-group">
                      <button
                        type="button"
                        className="admin-btn admin-btn--primary admin-btn--sm"
                        disabled={acting}
                        onClick={() => cmReview(false)}
                      >
                        Mark reviewed
                      </button>
                      <button
                        type="button"
                        className="admin-btn admin-btn--sm"
                        disabled={acting}
                        onClick={() => cmReview(true)}
                      >
                        Request correction
                      </button>
                    </div>
                  </div>
                ) : null}
              </section>
            ) : null}

            <div className="admin-reports__drawer-footer">
              {canApprove && canPublishToParent && canReviewThis ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--sm"
                  disabled={acting}
                  onClick={approve}
                >
                  {detail.parent_review_status === 'CHANGES_REQUESTED'
                    ? 'Resend to parent'
                    : 'Approve for parents'}
                </button>
              ) : null}
              {canReject && canReviewThis ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--sm admin-reports__reject-btn"
                  disabled={acting}
                  onClick={() => setRejectOpen((v) => !v)}
                >
                  Reject
                </button>
              ) : null}
            </div>

            {rejectOpen ? (
              <div className="admin-reports__reject-panel">
                <textarea
                  className="admin-input"
                  rows={3}
                  placeholder="Rejection reason (required)"
                  value={rejectComment}
                  onChange={(e) => setRejectComment(e.target.value)}
                />
                <div className="admin-btn-group">
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary admin-btn--sm"
                    disabled={acting}
                    onClick={reject}
                  >
                    Confirm reject
                  </button>
                  <button
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    onClick={() => setRejectOpen(false)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
          </>
        ) : null}
      </aside>
    </>
  )
}
