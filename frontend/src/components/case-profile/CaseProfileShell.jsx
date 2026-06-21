import { ClinicalCaseHeader } from '../clinical-ui/ClinicalCaseHeader.jsx'
import { ClinicalTabs } from '../clinical-ui/ClinicalTabBar.jsx'

/**
 * Shared case profile chrome: header + horizontal top tabs.
 */
export function CaseProfileShell({
  caseCode,
  childName,
  focusLine,
  serviceType,
  status,
  statusPill,
  headerActions,
  onRequestChange,
  supportHref,
  tabs,
  activeTab,
  onTabChange,
  children,
  className = '',
}) {
  const serviceLine = serviceType || focusLine

  return (
    <div className={`cp-shell ic-my-cases ic-case-detail ${className}`.trim()}>
      <ClinicalCaseHeader
        childName={childName}
        caseCode={caseCode}
        serviceType={serviceLine}
        status={status}
        onStatusClick={onRequestChange}
        supportHref={supportHref}
        headerActions={headerActions}
      />

      {statusPill ? (
        <div className="cp-shell__legacy-meta">{statusPill}</div>
      ) : null}

      <ClinicalTabs tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} />

      <div className="cp-shell__body">{children}</div>
    </div>
  )
}
