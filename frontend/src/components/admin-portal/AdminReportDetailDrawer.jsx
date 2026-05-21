import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, apiDownload } from '../../lib/apiClient.js'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../reports/report-editor.css'
import './admin-reports.css'

function statusPillClass(status) {
  const key = String(status || '').toLowerCase()
  return `admin-reports__status-pill admin-reports__status-pill--${key.replace(/_/g, '_')}`
}

export function AdminReportDetailDrawer({ reportType, reportId, onClose, onAction }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [acting, setActing] = useState(false)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectComment, setRejectComment] = useState('')

  useEffect(() => {
    if (!reportId || !reportType) return
    setLoading(true)
    setErr('')
    apiFetch(`/api/v1/admin/reports/${reportType}/${reportId}`)
      .then(setDetail)
      .catch((e) => {
        setErr(e.message || 'Could not load report')
        setDetail(null)
      })
      .finally(() => setLoading(false))
  }, [reportId, reportType])

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
      } else {
        await apiFetch(`/api/v1/reports/monthly/${reportId}/approve`, {
          method: 'POST',
          body: JSON.stringify({
            comment: 'Approved from report management',
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
      }
      onAction?.()
      onClose()
    } catch (e) {
      setErr(e.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function approveObservation() {
    setActing(true)
    setErr('')
    try {
      await apiFetch(`/api/v1/admin/reports/bulk/approve`, {
        method: 'POST',
        body: JSON.stringify({
          report_type: 'observation',
          ids: [reportId],
          visibility_status: 'APPROVED_FOR_PARENT',
        }),
      })
      onAction?.()
      onClose()
    } catch (e) {
      setErr(e.message || 'Approve failed')
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
      await apiFetch(`/api/v1/admin/reports/bulk/reject`, {
        method: 'POST',
        body: JSON.stringify({
          report_type: reportType,
          ids: [reportId],
          comment: rejectComment.trim(),
        }),
      })
      setRejectOpen(false)
      onAction?.()
      onClose()
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
  const canReject = detail?.status === 'UNDER_REVIEW'

  return (
    <>
      <div className="admin-reports__drawer-backdrop" onClick={onClose} role="presentation" />
      <aside className="admin-reports__drawer" aria-label="Report detail">
        <div className="admin-reports__drawer-header">
          <div>
            <p style={{ fontSize: '0.75rem', color: '#64748b', margin: 0 }}>
              {reportType === 'observation' ? 'Observation' : 'Monthly'} report
            </p>
            <h2 style={{ margin: '4px 0 0', fontSize: '1.15rem' }}>{detail?.label || '…'}</h2>
          </div>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? <p>Loading…</p> : null}
        {err ? <p className="admin-alert admin-alert--error">{err}</p> : null}

        {detail ? (
          <>
            <p style={{ margin: '0 0 8px' }}>
              <span className={statusPillClass(detail.status)}>{detail.status}</span>
              {detail.parent_review_status ? (
                <span className="admin-reports__parent-badge">{detail.parent_review_status}</span>
              ) : null}
            </p>
            <p style={{ fontSize: '0.85rem', color: '#475569' }}>
              {detail.child_name} · {detail.case_code} · {detail.therapist_name}
            </p>
            <p style={{ fontSize: '0.85rem', marginTop: 12 }}>
              <Link to={`/admin/cases/${detail.case_id}?tab=reports`}>Open case</Link>
            </p>

            {detail.category ? (
              <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 8 }}>
                Category: {detail.category.replace(/_/g, ' ')}
              </p>
            ) : null}

            <div style={{ marginTop: 16 }}>
              <h3 style={{ fontSize: '0.9rem' }}>Content</h3>
              <ReportHtmlView html={detail.body_html || detail.content || detail.summary} />
            </div>

            {detail.plan_next_month ? (
              <div className="report-plan-block" style={{ marginTop: 12 }}>
                <strong>Plan for next month</strong>
                <p style={{ margin: 0, whiteSpace: 'pre-wrap', fontSize: '0.85rem' }}>{detail.plan_next_month}</p>
              </div>
            ) : null}

            {reportType === 'monthly' ? (
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                style={{ marginTop: 12 }}
                onClick={() =>
                  apiDownload(`/api/v1/reports/monthly/${reportId}/download`, `report_${detail.label}.pdf`)
                }
              >
                Download PDF
              </button>
            ) : null}

            {detail.parent_feedback ? (
              <div style={{ marginTop: 12 }}>
                <h3 style={{ fontSize: '0.9rem' }}>Parent feedback</h3>
                <p style={{ fontSize: '0.85rem' }}>{detail.parent_feedback}</p>
              </div>
            ) : null}

            {detail.reviewer_comment ? (
              <div style={{ marginTop: 12 }}>
                <h3 style={{ fontSize: '0.9rem' }}>Reviewer comment</h3>
                <p style={{ fontSize: '0.85rem' }}>{detail.reviewer_comment}</p>
              </div>
            ) : null}

            {detail.review_history?.length > 0 ? (
              <div style={{ marginTop: 16 }}>
                <h3 style={{ fontSize: '0.9rem' }}>Review history</h3>
                {detail.review_history.map((h) => (
                  <div key={h.id} className="admin-reports__history-item">
                    <strong>{h.decision}</strong> · {h.reviewer_name || 'Reviewer'}
                    <br />
                    {h.comment || '—'}
                    <br />
                    <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>
                      {h.created_at ? new Date(h.created_at).toLocaleString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="admin-btn-group" style={{ marginTop: 20 }}>
              {canApprove ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--sm"
                  disabled={acting}
                  onClick={reportType === 'observation' ? approveObservation : approve}
                >
                  {detail.parent_review_status === 'CHANGES_REQUESTED'
                    ? 'Resend to parent'
                    : 'Approve for parents'}
                </button>
              ) : null}
              {canReject ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--sm"
                  disabled={acting}
                  onClick={() => setRejectOpen(true)}
                >
                  Reject
                </button>
              ) : null}
            </div>

            {rejectOpen ? (
              <div style={{ marginTop: 12 }}>
                <textarea
                  className="admin-input"
                  rows={3}
                  placeholder="Rejection reason (required)"
                  value={rejectComment}
                  onChange={(e) => setRejectComment(e.target.value)}
                />
                <div className="admin-btn-group" style={{ marginTop: 8 }}>
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
