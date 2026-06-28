import { Navigate, useLocation, useParams } from 'react-router-dom'
import { isReportsEngineActive } from '../../../lib/reportsRevampFlags.js'
import { isReportBuilderEnabled } from '../../../lib/productFeatureFlags.js'
import { PortalComingSoon } from '../../shared/PortalComingSoon.jsx'
import { ReportEditPage } from '../../reports/ReportEditPage.jsx'

/**
 * When reports engine v1 is on, monthly rich-text editor routes redirect to case reports hub.
 * Legacy editor remains available when VITE_REPORTS_REVAMP=false.
 */
export function ReportsEditRouteGuard() {
  const { caseId } = useParams()
  const location = useLocation()
  const engineOn = isReportsEngineActive()
  const isAdmin = location.pathname.startsWith('/admin')

  if (!isReportBuilderEnabled()) {
    return <PortalComingSoon variant={isAdmin ? 'adminReports' : 'therapistReports'} />
  }

  if (engineOn) {
    if (caseId) {
      const base = isAdmin ? '/admin/cases' : '/therapist/cases'
      return (
        <Navigate
          to={`${base}/${caseId}?tab=reports&section=monthly`}
          replace
        />
      )
    }
    return <Navigate to={isAdmin ? '/admin/cases' : '/therapist/reports?section=dashboard'} replace />
  }

  return <ReportEditPage />
}
