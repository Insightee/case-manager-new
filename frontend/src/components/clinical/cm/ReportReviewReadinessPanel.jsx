import { Link } from 'react-router-dom'

export function ReportReviewReadinessPanel({ summary, caseId }) {
  const rs = summary?.report_statuses || {}
  return (
    <section className="cp-quality-card cp-quality-card--timeline" aria-labelledby="report-readiness-title">
      <h3 id="report-readiness-title">Report review readiness</h3>
      <p>
        Current month: <strong>{rs.current_month_status || 'Not started'}</strong>
        {rs.pending_review_count ? ` · ${rs.pending_review_count} in review` : ''}
        {rs.rejected_count ? ` · ${rs.rejected_count} rejected` : ''}
      </p>
      <Link to={`/admin/cases/${caseId}?tab=reports&section=monthly`} className="ic-btn ic-btn--ghost ic-btn--sm">
        Review case reports
      </Link>
    </section>
  )
}
