import { useMemo } from 'react'
import { Navigate, useSearchParams } from 'react-router-dom'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { TherapistReportsHomeView } from './TherapistReportsHomeView.jsx'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'
import { normalizeReportsSection } from '../case-profile/reportsHubSections.js'
import { useTherapistActiveCase } from '../../context/TherapistActiveCaseContext.jsx'
import { isReportsModuleEnabled, isReportBuilderEnabled } from '../../lib/productFeatureFlags.js'
import { isCaseReportsTabV2Active } from '../../lib/reportsRevampFlags.js'
import '../../styles/case-profile-v2.css'

/**
 * Global /therapist/reports entry.
 * When VITE_CASE_REPORTS_TAB_V2=true, redirect to case Reports tab.
 * Otherwise keep the stable pipeline dashboard (TherapistReportsHomeView).
 */
function MonthlyReportsPageContent() {
  const [searchParams, setSearchParams] = useSearchParams()
  const caseFilterId = searchParams.get('case_id')
  const openCreate = searchParams.get('create') === '1'
  const section = normalizeReportsSection(searchParams.get('section'))
  const { data: homeData, isLoading: homeLoading } = useTherapistHome()
  const { activeCase } = useTherapistActiveCase()

  const assignedCases = useMemo(() => {
    if (!homeData?.cases_board?.allCases) return []
    return homeData.cases_board.allCases.map((c) => ({
      id: c.id,
      case_code: c.caseId,
      child_name: c.child,
    }))
  }, [homeData])

  const filteredCase = useMemo(() => {
    if (!caseFilterId) return null
    const id = Number(caseFilterId)
    if (!Number.isFinite(id)) return null
    return assignedCases.find((c) => c.id === id) || {
      id,
      child_name: 'Client',
      case_code: `Case #${id}`,
    }
  }, [assignedCases, caseFilterId])

  const resolvedCaseId = useMemo(() => {
    if (caseFilterId) return caseFilterId
    if (activeCase?.id) return String(activeCase.id)
    const first = assignedCases[0]
    return first ? String(first.id) : null
  }, [caseFilterId, activeCase, assignedCases])

  if (isCaseReportsTabV2Active()) {
    if (homeLoading && !resolvedCaseId) {
      return <p className="reports-dashboard-loading">Loading reports…</p>
    }
    if (resolvedCaseId) {
      const targetSection = openCreate ? 'monthly' : section === 'dashboard' ? 'dashboard' : section
      const qs = new URLSearchParams({ tab: 'reports', section: targetSection })
      if (openCreate) qs.set('create', '1')
      return <Navigate to={`/therapist/cases/${resolvedCaseId}?${qs.toString()}`} replace />
    }
    return (
      <p className="reports-dashboard-loading" role="status">
        Open a case from My Cases to view reports for that client.
      </p>
    )
  }

  return (
    <TherapistReportsHomeView
      fixedCaseId={caseFilterId}
      caseCode={filteredCase?.case_code}
      childName={filteredCase?.child_name}
      openCreateOnMount={openCreate}
      onCreateConsumed={() => {
        const params = new URLSearchParams(searchParams)
        params.delete('create')
        setSearchParams(params, { replace: true })
      }}
      onClearCaseFilter={() => setSearchParams({}, { replace: true })}
    />
  )
}

export function MonthlyReportsPage() {
  if (!isReportsModuleEnabled() && !isReportBuilderEnabled()) {
    return <PortalComingSoon variant="therapistReports" />
  }
  return <MonthlyReportsPageContent />
}
