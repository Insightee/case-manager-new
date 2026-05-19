/** Build therapist My Cases board from API aggregates. */

const todayIso = () => new Date().toISOString().slice(0, 10)

function stageBadge(caseRow, needsLogCount, reportPending) {
  if (needsLogCount > 0) return { variant: 'observation', label: 'Log due' }
  if (reportPending) return { variant: 'iep', label: 'Report pending' }
  const stage = (caseRow.operational_stage || caseRow.status || 'ACTIVE').toLowerCase()
  if (stage.includes('observation')) return { variant: 'observation', label: 'Observation' }
  if (stage.includes('iep')) return { variant: 'iep', label: 'IEP' }
  if (caseRow.status === 'CLOSED') return { variant: 'completed', label: 'Closed' }
  return { variant: 'active', label: caseRow.operational_stage || 'Active' }
}

export function buildCaseWorkbench({ cases = [], sessions = [], logs = [], reports = [], slots = [] }) {
  const today = todayIso()
  const sessionsByCase = new Map()
  for (const s of sessions) {
    if (!sessionsByCase.has(s.case_id)) sessionsByCase.set(s.case_id, [])
    sessionsByCase.get(s.case_id).push(s)
  }
  const reportsByCase = new Map()
  for (const r of reports) {
    if (!reportsByCase.has(r.case_id)) reportsByCase.set(r.case_id, [])
    reportsByCase.get(r.case_id).push(r)
  }
  const bookedSlots = slots.filter((sl) => sl.status === 'BOOKED' && sl.case_id)

  const enriched = cases.map((c) => {
    const caseSessions = sessionsByCase.get(c.id) || []
    const needsLog = caseSessions.filter((s) => s.status === 'COMPLETED' && !s.has_daily_log)
    const upcoming = caseSessions.filter((s) => s.status === 'SCHEDULED' && s.scheduled_date >= today)
    const caseReports = reportsByCase.get(c.id) || []
    const draftReport = caseReports.find((r) => r.status === 'DRAFT' || r.status === 'UNDER_REVIEW')
    const nextBooking = bookedSlots
      .filter((sl) => sl.case_id === c.id && sl.slot_date >= today)
      .sort((a, b) => `${a.slot_date}${a.start_time}`.localeCompare(`${b.slot_date}${b.start_time}`))[0]

    let nextDue = '—'
    if (needsLog.length) nextDue = `${needsLog.length} log${needsLog.length > 1 ? 's' : ''} due`
    else if (draftReport) nextDue = `Report: ${draftReport.month}`
    else if (nextBooking) nextDue = `Booking ${nextBooking.slot_date}`

    const badge = stageBadge(c, needsLog.length, !!draftReport)
    const critical = needsLog.length > 0 || draftReport?.status === 'UNDER_REVIEW'

    return {
      id: c.id,
      caseId: c.case_code,
      child: c.child_name || '—',
      service: c.service_type || c.product_module,
      productModule: c.product_module,
      stage: badge.label,
      badgeVariant: badge.variant,
      nextDue,
      critical,
      needsLogCount: needsLog.length,
      upcomingCount: upcoming.length,
      status: c.status,
      mapsUrl: c.maps_url,
      serviceAddress: c.service_address,
      borderAccent: critical ? 'yellow' : needsLog.length ? 'yellow' : 'blue',
      showSubmitReport: !!draftReport || caseReports.length === 0,
    }
  })

  const attentionIds = new Set()
  const attention = enriched.filter((c) => {
    if (c.critical || c.needsLogCount > 0) {
      attentionIds.add(c.id)
      return true
    }
    return false
  })
  const inProgress = enriched.filter((c) => !attentionIds.has(c.id) && c.status !== 'CLOSED')
  const completed = enriched.filter((c) => c.status === 'CLOSED')

  const stats = [
    { id: 'total', label: 'Total cases', value: enriched.length, variant: 'indigo' },
    { id: 'attention', label: 'Needs attention', value: attention.length, variant: 'yellow' },
    { id: 'logs', label: 'Logs due', value: enriched.reduce((n, c) => n + c.needsLogCount, 0), variant: 'purple' },
    {
      id: 'bookings',
      label: 'Upcoming bookings',
      value: bookedSlots.filter((sl) => sl.slot_date >= today).length,
      variant: 'teal',
    },
  ]

  return {
    stats,
    sections: [
      { id: 'attention', title: 'Attention required', tone: 'danger', count: attention.length, cases: attention },
      { id: 'in_progress', title: 'In progress', tone: 'warning', count: inProgress.length, cases: inProgress },
      { id: 'completed', title: 'Closed', tone: 'success', count: completed.length, cases: completed },
    ],
    allCases: enriched,
  }
}
