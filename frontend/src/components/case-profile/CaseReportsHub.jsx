import { useSearchParams } from 'react-router-dom'
import { REPORTS_SUB_TABS } from './caseProfileTabs.js'
import { CaseReportsTabHome } from './CaseReportsTabHome.jsx'
import { ObservationChecklistPanel } from '../cases/ObservationChecklistPanel.jsx'
import { CaseReportsPanel } from '../cases/CaseReportsPanel.jsx'
import { CaseIepSection } from './sections/CaseIepSection.jsx'
import { CaseProgressReportsSection } from './sections/CaseProgressReportsSection.jsx'
import { EvidenceDrivePanel } from './sections/EvidenceDrivePanel.jsx'
import { ClinicalSubTabs } from '../clinical-ui/ClinicalSubTabBar.jsx'

export function CaseReportsHub({
  caseId,
  caseCode,
  childName,
  variant = 'therapist',
  canManageIep = false,
  onUpdated,
}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const section = searchParams.get('section') || 'home'

  function setSection(id) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'reports')
    next.set('section', id)
    setSearchParams(next, { replace: true })
  }

  return (
    <div className="cp-reports-hub">
      <ClinicalSubTabs tabs={REPORTS_SUB_TABS} activeTab={section} onTabChange={setSection} ariaLabel="Report types" />

      {section === 'home' ? (
        <CaseReportsTabHome caseId={caseId} childName={childName} onOpenSection={setSection} />
      ) : null}

      {section === 'monthly' ? (
        <p className="clinical-page-header__subtitle cp-reports-hub__section-intro">
          Monthly progress for <strong>{childName}</strong> ({caseCode}). Submit drafts for admin review before families can read them.
        </p>
      ) : null}

      {section === 'observation' ? <ObservationChecklistPanel caseId={caseId} childName={childName} /> : null}
      {section === 'iep' ? <CaseIepSection caseId={caseId} canManage={canManageIep} variant={variant} /> : null}
      {section === 'monthly' ? (
        <CaseReportsPanel
          caseId={Number(caseId)}
          caseCode={caseCode}
          childName={childName}
          onUpdated={onUpdated}
          editBase={variant === 'admin' ? `/admin/reports/edit` : `/therapist/cases/${caseId}/reports/monthly`}
        />
      ) : null}
      {section === 'progress' ? <CaseProgressReportsSection caseId={caseId} caseCode={caseCode} childName={childName} variant={variant} /> : null}
      {section === 'drive' ? <EvidenceDrivePanel caseId={Number(caseId)} variant={variant} /> : null}
    </div>
  )
}
