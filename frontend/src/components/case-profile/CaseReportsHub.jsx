import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { isReportsEngineActive, isClinicalReportBuilderActive, isMonthlyClinicalEngineActive, isCaseReportsTabV2Active } from '../../lib/reportsRevampFlags.js'
import { CaseReportsPanel } from '../cases/CaseReportsPanel.jsx'
import { normalizeReportsSection } from './reportsHubSections.js'
import { ObservationChecklistPanel } from '../cases/ObservationChecklistPanel.jsx'
import { CaseIepSection } from './sections/CaseIepSection.jsx'
import { CaseProgressReportsSection } from './sections/CaseProgressReportsSection.jsx'
import { CaseReportHistorySection } from './sections/CaseReportHistorySection.jsx'
import { CaseReportsTab } from '../clinical/reports-tab/CaseReportsTab.jsx'
import { MonthlyReportRoute } from '../reports-engine/monthly/MonthlyReportRoute.jsx'
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
  const builderOn = isClinicalReportBuilderActive()

  if (section === 'dashboard') {
    return (
      <div className="cp-reports-hub forest-light">
        {isCaseReportsTabV2Active() ? (
          <CaseReportsTab caseId={caseId} variant={variant} />
        ) : (
          <CaseReportsPanel
            caseId={Number(caseId)}
            caseCode={caseCode}
            childName={childName}
            onUpdated={onUpdated}
            editBase={variant === 'admin' ? '/admin/reports/edit' : `/therapist/cases/${caseId}/reports/monthly`}
          />
        )}
      </div>
    )
  }

  if (builderOn) {
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
    if (section === 'monthly' && isMonthlyClinicalEngineActive()) {
      return (
        <div className="cp-reports-hub forest-light">
          <MonthlyReportRoute
            caseId={caseId}
            caseCode={caseCode}
            childName={childName}
            variant={variant}
            onUpdated={onUpdated}
          />
        </div>
      )
    }
    if (PLACEHOLDER_TITLES[section] && engineOn && section !== 'monthly') {
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
        <MonthlyReportRoute
          caseId={caseId}
          caseCode={caseCode}
          childName={childName}
          variant={variant}
          onUpdated={onUpdated}
        />
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
