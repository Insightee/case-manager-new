import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { categoryLabel } from '../../lib/reportCategories.js'
import { reportAdminEditPath } from '../../lib/reportManagementPaths.js'
import { ReportCommentsThread } from '../reports/ReportCommentsThread.jsx'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../reports/report-editor.css'
import './admin-reports.css'

export function AdminReportViewPage() {
  const { reportId } = useParams()
  const navigate = useNavigate()
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setErr('')
    try {
      const row = await apiFetch(`/api/v1/admin/reports/monthly/${reportId}`)
      setDetail(row)
    } catch (e) {
      setErr(e.message || 'Report not found')
      setDetail(null)
    } finally {
      setLoading(false)
    }
  }, [reportId])

  useEffect(() => {
    load()
  }, [load])

  const html = detail?.body_html || detail?.content || detail?.summary

  return (
    <div className="admin-page admin-reports-view">
      <header className="admin-reports-view__header">
        <div>
          <p className="admin-reports__drawer-eyebrow">Monthly report</p>
          <h1>{detail?.label || 'Report'}</h1>
          {detail ? (
            <p className="admin-muted">
              {detail.child_name} · {detail.case_code} · {detail.therapist_name}
              {detail.category ? ` · ${categoryLabel(detail.category)}` : ''}
            </p>
          ) : null}
        </div>
        <div className="admin-btn-group">
          <button type="button" className="admin-btn admin-btn--ghost" onClick={() => navigate('/admin/reports')}>
            Back to reports
          </button>
          {detail ? (
            <>
              <button
                type="button"
                className="admin-btn admin-btn--ghost"
                onClick={() =>
                  apiDownload(`/api/v1/reports/monthly/${reportId}/download`, `report_${detail.label || reportId}.pdf`)
                }
              >
                PDF
              </button>
              <Link to={reportAdminEditPath(reportId)} className="admin-btn admin-btn--secondary">
                Edit report
              </Link>
            </>
          ) : null}
        </div>
      </header>

      {loading ? <p className="admin-muted">Loading…</p> : null}
      {err ? <p className="admin-alert admin-alert--error">{err}</p> : null}

      {detail ? (
        <>
          <section className="admin-reports__drawer-section">
            <div className="admin-reports__content-preview">
              <ReportHtmlView html={html} />
            </div>
            {detail.plan_next_month ? (
              <div className="admin-reports__plan-block">
                <strong>Plan for next month</strong>
                <p>{detail.plan_next_month}</p>
              </div>
            ) : null}
          </section>

          <ReportCommentsThread
            title="Comments"
            commentsPath={`/api/v1/admin/reports/monthly/${reportId}/comments`}
            postPath={`/api/v1/admin/reports/monthly/${reportId}/comments`}
            canPost
          />

          {detail.review_history?.length > 0 ? (
            <section className="admin-reports__drawer-section">
              <h3>Decision history</h3>
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

          <p className="admin-muted admin-reports-view__case-link">
            <Link to={`/admin/cases/${detail.case_id}?tab=reports`}>Open case reports tab</Link>
          </p>
        </>
      ) : null}
    </div>
  )
}
