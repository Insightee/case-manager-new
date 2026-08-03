import { useSearchParams } from 'react-router-dom'
import { ProgressLandingPage } from './ProgressLandingPage.jsx'
import { ProgressReportBuilderPage } from './ProgressReportBuilderPage.jsx'
import { ProgressReportPreviewPage } from './ProgressReportPreviewPage.jsx'

/** Progress Report — clinical_reports engine, Forest Light builder pattern (matches Observation/IEP). */
export function ProgressReportRoute({ caseId, caseCode, childName, variant = 'therapist' }) {
  const [searchParams] = useSearchParams()
  const view = searchParams.get('view') || 'landing'

  let page = null
  if (view === 'builder') {
    page = <ProgressReportBuilderPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else if (view === 'preview') {
    page = <ProgressReportPreviewPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else {
    page = <ProgressLandingPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  }

  return <div className="progress-report-workspace forest-light clinical-report-ui">{page}</div>
}
