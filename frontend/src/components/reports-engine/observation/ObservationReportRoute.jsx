// Visual source: docs/design/stitch/observation-report/observation_report_comprehensive_clinical_workspace/
import { useSearchParams } from 'react-router-dom'
import '../../../styles/clinical-report-ui.css'
import '../../../styles/forest-light-observation.css'
import { ObservationLandingPage } from './ObservationLandingPage.jsx'
import { ObservationBuilderPage } from './ObservationBuilderPage.jsx'
import { ObservationPreviewPage } from './ObservationPreviewPage.jsx'

export function ObservationReportRoute({ caseId, caseCode, childName, variant = 'therapist' }) {
  const [searchParams] = useSearchParams()
  let view = searchParams.get('view') || 'landing'
  if (variant === 'parent' && view === 'builder') view = 'preview'

  let page = null
  if (view === 'builder') {
    page = <ObservationBuilderPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else if (view === 'preview') {
    page = <ObservationPreviewPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else {
    page = <ObservationLandingPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  }

  return (
    <div className="observation-workspace forest-light clinical-report-ui">
      {page}
    </div>
  )
}
