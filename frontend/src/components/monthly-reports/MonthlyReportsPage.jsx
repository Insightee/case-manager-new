import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { TherapistReportsHomeView } from './TherapistReportsHomeView.jsx'
import '../../styles/case-profile-v2.css'

export function MonthlyReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const caseFilterId = searchParams.get('case_id')
  const openCreate = searchParams.get('create') === '1'
  const { data: homeData } = useTherapistHome()

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
