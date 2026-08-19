import { useSearchParams } from 'react-router-dom'
import '../../../styles/clinical-report-ui.css'
import '../../../styles/forest-light-iep.css'
import { IepLandingPage } from './IepLandingPage.jsx'
import { IepBuilderPage } from './IepBuilderPage.jsx'
import { IepPreviewPage } from './IepPreviewPage.jsx'

export function IepReportRoute({ caseId, caseCode, childName, variant = 'therapist' }) {
  const [searchParams] = useSearchParams()
  let view = searchParams.get('view') || 'landing'
  if (variant === 'parent' && view === 'builder') view = 'preview'

  let page = null
  if (view === 'builder') {
    page = <IepBuilderPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else if (view === 'preview') {
    page = <IepPreviewPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  } else {
    page = <IepLandingPage caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
  }

  return <div className="iep-workspace forest-light clinical-report-ui">{page}</div>
}
