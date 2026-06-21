import { isReportsRevampActive } from '../../lib/reportsRevampFlags.js'
import { CaseDetailPage } from './CaseDetailPage.jsx'
import { CaseDetailRevamp } from './CaseDetailRevamp.jsx'

export function CaseDetailRoute() {
  if (isReportsRevampActive('therapist')) {
    return <CaseDetailRevamp />
  }
  return <CaseDetailPage />
}
