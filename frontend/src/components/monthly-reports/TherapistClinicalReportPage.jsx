import { Link, useParams } from 'react-router-dom'
import { useMemo } from 'react'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { ObservationReportRoute } from '../reports-engine/observation/ObservationReportRoute.jsx'
import { IepReportRoute } from '../reports-engine/iep/IepReportRoute.jsx'
import { isReportsEngineActive } from '../../lib/reportsRevampFlags.js'
import { PortalComingSoon } from '../shared/PortalComingSoon.jsx'

export function TherapistClinicalReportPage({ reportKind }) {
  const { caseId } = useParams()
  const numericCaseId = Number(caseId)
  const { data: homeData } = useTherapistHome()

  const caseRow = useMemo(() => {
    if (!Number.isFinite(numericCaseId)) return null
    return homeData?.cases_board?.allCases?.find((c) => c.id === numericCaseId) || null
  }, [homeData, numericCaseId])

  if (!isReportsEngineActive()) {
    return <PortalComingSoon variant="therapistReports" />
  }

  if (!Number.isFinite(numericCaseId)) {
    return <p className="text-slate-600">Pick a client from Reports to open this builder.</p>
  }

  const routeProps = {
    caseId: numericCaseId,
    caseCode: caseRow?.caseId || `Case #${numericCaseId}`,
    childName: caseRow?.child || 'Client',
    variant: 'therapist',
  }

  const title = reportKind === 'observation' ? 'Observation report' : 'IEP report'

  return (
    <div className="relative flex min-h-full flex-col gap-4 px-1 py-2 pb-28 sm:px-3 sm:py-4 lg:pb-8">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to={`/therapist/reports?case_id=${numericCaseId}`}
          className="text-sm font-medium text-emerald-700 hover:text-emerald-900"
        >
          ← Back to reports
        </Link>
        <span className="text-sm text-slate-500">{title}</span>
      </div>
      {reportKind === 'observation' ? (
        <ObservationReportRoute {...routeProps} />
      ) : (
        <IepReportRoute {...routeProps} />
      )}
    </div>
  )
}
