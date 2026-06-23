import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { isReportsEngineActive } from '../../lib/reportsRevampFlags.js'
import { normalizeReportsSection } from './reportsHubSections.js'
import { CaseReportsPanel } from '../cases/CaseReportsPanel.jsx'
import { ObservationChecklistPanel } from '../cases/ObservationChecklistPanel.jsx'
import { CaseIepSection } from './sections/CaseIepSection.jsx'
import { CaseProgressReportsSection } from './sections/CaseProgressReportsSection.jsx'
import { CaseReportHistorySection } from './sections/CaseReportHistorySection.jsx'
import { TherapistReportsHomeView } from '../monthly-reports/TherapistReportsHomeView.jsx'
import { ReportTypePlaceholder } from '../reports-engine/shell/ReportTypePlaceholder.jsx'
import { ObservationReportRoute } from '../reports-engine/observation/ObservationReportRoute.jsx'
import { IepReportRoute } from '../reports-engine/iep/IepReportRoute.jsx'
import '../../styles/reports-engine.css'

const PLACEHOLDER_TITLES = {
  monthly: 'Monthly Report',
  progress: 'Progress Report',
  history: 'Report History',
}

export function CaseReportsHub({
  caseId,
  caseCode,
  childName,
  variant = 'therapist',
  canManageIep = false,
  onUpdated,
}) {
  const [searchParams] = useSearchParams()
  const section = useMemo(
    () => normalizeReportsSection(searchParams.get('section')),
    [searchParams],
  )
  const engineOn = isReportsEngineActive()

  if (section === 'dashboard') {
    return (
      <TherapistReportsHomeView
        embedded
        fixedCaseId={caseId}
        caseCode={caseCode}
        childName={childName}
        onUpdated={onUpdated}
      />
    )
  }

  if (engineOn) {
    if (section === 'observation') {
      return (
        <div className="cp-reports-hub forest-light">
          <ObservationReportRoute caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
        </div>
      )
    }
    if (section === 'iep') {
      return (
        <div className="cp-reports-hub forest-light">
          <IepReportRoute caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} />
        </div>
      )
    }
    if (PLACEHOLDER_TITLES[section]) {
      return (
        <div className="cp-reports-hub forest-light">
          <ReportTypePlaceholder reportType={section} title={PLACEHOLDER_TITLES[section]} />
        </div>
      )
    }
  }

  return (
    <div className="cp-reports-hub forest-light">
      {section === 'observation' ? (
        <ObservationChecklistPanel caseId={caseId} childName={childName} />
      ) : null}

      {section === 'iep' ? (
        <CaseIepSection caseId={caseId} canManage={canManageIep} variant={variant} />
      ) : null}

      {section === 'monthly' ? (
        <>
          <p className="clinical-page-header__subtitle cp-reports-hub__section-intro">
            Monthly progress for <strong>{childName}</strong> ({caseCode}). Submit drafts for admin review before families can read them.
          </p>
          <CaseReportsPanel
            caseId={Number(caseId)}
            caseCode={caseCode}
            childName={childName}
            onUpdated={onUpdated}
            editBase={variant === 'admin' ? `/admin/reports/edit` : `/therapist/cases/${caseId}/reports/monthly`}
          />
        </>
      ) : null}

      {section === 'progress' ? (
        <CaseProgressReportsSection
          caseId={caseId}
          caseCode={caseCode}
          childName={childName}
          variant={variant}
        />
      ) : null}

      {section === 'history' ? (
        <CaseReportHistorySection
          caseId={caseId}
          caseCode={caseCode}
          childName={childName}
          variant={variant}
        />
      ) : null}
    </div>
  )
}
