import { ClinicalStatusBadge } from '../../clinical-ui/ClinicalStatusBadge.jsx'

const COPY =
  'This report type will be configured in the next build phase using the uploaded Stitch report UI. The report engine, status flow, evidence linking, and permissions are already prepared.'

export function ReportTypePlaceholder({ reportType, title }) {
  const label = title || reportType || 'Report'
  return (
    <div className="re-placeholder cp-card">
      <div className="re-placeholder__head">
        <h2 className="re-placeholder__title">{label}</h2>
        <ClinicalStatusBadge status="DRAFT" customLabel="Coming next" />
      </div>
      <p className="re-placeholder__body">{COPY}</p>
      <ul className="re-placeholder__list">
        <li>Shared report engine status flow is ready</li>
        <li>Evidence linking hooks are in place</li>
        <li>Role permissions are wired for therapist and case manager</li>
      </ul>
    </div>
  )
}
