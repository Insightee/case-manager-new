import { useSearchParams } from 'react-router-dom'
import { CaseReportsPanel } from '../../cases/CaseReportsPanel.jsx'
import { isMonthlyClinicalEngineActive } from '../../../lib/reportsRevampFlags.js'

/**
 * Monthly report section — uses CaseReportsPanel with monthlyReportApi bridge.
 * Engine path active when VITE_MONTHLY_REPORTS_USE_CLINICAL_ENGINE=true.
 */
export function MonthlyReportRoute({
  caseId,
  caseCode,
  childName,
  variant = 'therapist',
  onUpdated,
}) {
  const [searchParams] = useSearchParams()
  const monthParam = searchParams.get('month')
  const editBase =
    variant === 'admin'
      ? '/admin/reports/edit'
      : `/therapist/cases/${caseId}/reports/monthly`

  return (
    <div className="monthly-report-route forest-light clinical-report-ui">
      {isMonthlyClinicalEngineActive() ? (
        <p className="clinical-page-header__subtitle cp-reports-hub__section-intro">
          Monthly progress for <strong>{childName}</strong> ({caseCode}).
          {monthParam ? ` — ${monthParam}` : ''}
        </p>
      ) : null}
      <CaseReportsPanel
        caseId={Number(caseId)}
        caseCode={caseCode}
        childName={childName}
        onUpdated={onUpdated}
        editBase={editBase}
      />
    </div>
  )
}
