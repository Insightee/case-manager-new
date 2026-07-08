import { isReportsRevampActive } from '../../../lib/reportsRevampFlags.js'
import { CaseDocumentsPanel } from '../../documents/CaseDocumentsPanel.jsx'
import { CaseDocumentDriveView } from './CaseDocumentDriveView.jsx'

/** Evidence Drive — case documents grouped for clinical context. */
export function EvidenceDrivePanel({ caseId, variant = 'therapist', childName, caseCode }) {
  const monthlyReportsPath =
    variant === 'admin'
      ? `/admin/reports?case_id=${caseId}`
      : `/therapist/reports?case_id=${caseId}`

  if (isReportsRevampActive(variant === 'admin' ? 'admin' : 'therapist')) {
    return (
      <CaseDocumentDriveView
        caseId={caseId}
        variant={variant}
        childName={childName}
        caseCode={caseCode}
        monthlyReportsPath={monthlyReportsPath}
      />
    )
  }

  return (
    <CaseDocumentsPanel
      caseId={caseId}
      variant={variant}
      monthlyReportsPath={monthlyReportsPath}
    />
  )
}
