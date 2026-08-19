import { ReportEditPage } from '../../reports/ReportEditPage.jsx'

/** Monthly rich-text editor — stays on ReportEditPage (no case-profile redirect). */
export function ReportsEditRouteGuard() {
  return <ReportEditPage />
}
