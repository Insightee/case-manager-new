import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { useTherapistActiveCase } from '../../context/TherapistActiveCaseContext.jsx'
import { ClinicalCaseHeader } from '../clinical-ui/ClinicalCaseHeader.jsx'
import { ClinicalTabs } from '../clinical-ui/ClinicalTabBar.jsx'
import { ChangeCaseSheet } from './ChangeCaseSheet.jsx'

/**
 * Shared case profile chrome: header + horizontal top tabs.
 */
export function CaseProfileShell({
  caseId,
  enableChangeCase = false,
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
  const [changeCaseOpen, setChangeCaseOpen] = useState(false)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { setActiveCase, touchRecentCase } = useTherapistActiveCase()
  const { data: home } = useTherapistHome()

  const assignedCases = useMemo(
    () => home?.cases_board?.allCases || [],
    [home],
  )

  function handleSelectCase(row) {
    setActiveCase(row)
    touchRecentCase(row.id)

    const next = new URLSearchParams()
    const tab = activeTab || searchParams.get('tab') || 'overview'
    if (tab && tab !== 'overview') next.set('tab', tab)
    if (tab === 'reports') {
      const section = searchParams.get('section') || 'dashboard'
      next.set('section', section)
    }

    const qs = next.toString()
    navigate(`/therapist/cases/${row.id}${qs ? `?${qs}` : ''}`)
    setChangeCaseOpen(false)
  }

  return (
    <div className={`cp-shell ic-my-cases ic-case-detail forest-light ${className}`.trim()}>
      <ClinicalCaseHeader
        childName={childName}
        caseCode={caseCode}
        serviceType={serviceLine}
        status={status}
        onStatusClick={onRequestChange}
        onChangeCase={enableChangeCase ? () => setChangeCaseOpen(true) : undefined}
        supportHref={supportHref}
        headerActions={headerActions}
      />

      {statusPill ? (
        <div className="cp-shell__legacy-meta">{statusPill}</div>
      ) : null}

      <ClinicalTabs tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} />

      <div className="cp-shell__body">{children}</div>

      {enableChangeCase ? (
        <ChangeCaseSheet
          open={changeCaseOpen}
          cases={assignedCases}
          currentCaseId={caseId}
          onSelect={handleSelectCase}
          onClose={() => setChangeCaseOpen(false)}
        />
      ) : null}
    </div>
  )
}
