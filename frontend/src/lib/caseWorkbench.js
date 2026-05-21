/** Build therapist My Cases board from API aggregates. */

const todayIso = () => new Date().toISOString().slice(0, 10)

/** Safe text for search/filter matching. */
function norm(value) {
  return String(value ?? '').toLowerCase().trim()
}

export function matchesCaseSearch(caseRow, query) {
  const q = norm(query)
  if (!q) return true
  const hay = [
    caseRow.caseId,
    caseRow.child,
    caseRow.service,
    caseRow.productModule,
    caseRow.stage,
    caseRow.nextDue,
    caseRow.status,
  ]
    .map(norm)
    .join(' ')
  return hay.includes(q)
}

function isDueSoon(caseRow) {
  if (caseRow.critical || caseRow.needsLogCount > 0) return true
  const next = norm(caseRow.nextDue)
  if (!next || next === '—') return false
  return (
    next.includes('log') ||
    next.includes('report') ||
    next.includes('booking') ||
    next.includes('due')
  )
}

function urgencyRank(caseRow) {
  if (caseRow.critical) return 0
  if (caseRow.needsLogCount > 0) return 1
  if (isDueSoon(caseRow)) return 2
  if (caseRow.status === 'CLOSED') return 4
  return 3
}

/**
 * @param {object} opts
 * @param {string} [opts.search]
 * @param {string} [opts.stage] - all | attention | in_progress | closed | log_due
 * @param {string} [opts.service] - all or exact service string
 * @param {string} [opts.dueSoon] - all | yes
 * @param {string} [opts.sort] - urgency | child | case_id
 */
export function filterAndSortCases(cases, opts = {}) {
  const { search = '', stage = 'all', service = 'all', dueSoon = 'all', sort = 'urgency' } = opts
  let list = cases.filter((c) => matchesCaseSearch(c, search))

  if (stage === 'attention') {
    list = list.filter((c) => c.critical || c.needsLogCount > 0)
  } else if (stage === 'in_progress') {
    list = list.filter((c) => c.status !== 'CLOSED' && !c.critical && c.needsLogCount === 0)
  } else if (stage === 'closed') {
    list = list.filter((c) => c.status === 'CLOSED')
  } else if (stage === 'log_due') {
    list = list.filter((c) => c.needsLogCount > 0)
  }

  if (service !== 'all') {
    const s = norm(service)
    list = list.filter((c) => norm(c.service) === s || norm(c.productModule) === s)
  }

  if (dueSoon === 'yes') {
    list = list.filter(isDueSoon)
  }

  if (sort === 'child') {
    list = [...list].sort((a, b) => norm(a.child).localeCompare(norm(b.child)))
  } else if (sort === 'case_id') {
    list = [...list].sort((a, b) => norm(a.caseId).localeCompare(norm(b.caseId)))
  } else {
    list = [...list].sort((a, b) => {
      const d = urgencyRank(a) - urgencyRank(b)
      if (d !== 0) return d
      return norm(a.child).localeCompare(norm(b.child))
    })
  }

  return list
}

export function buildSectionsFromCases(enriched) {
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

  return [
    { id: 'attention', title: 'Attention required', tone: 'danger', count: attention.length, cases: attention },
    { id: 'in_progress', title: 'In progress', tone: 'warning', count: inProgress.length, cases: inProgress },
    { id: 'completed', title: 'Closed', tone: 'success', count: completed.length, cases: completed },
  ]
}

export function buildStatsFromCases(enriched, bookedSlotsToday = 0) {
  const attention = enriched.filter((c) => c.critical || c.needsLogCount > 0)
  return [
    { id: 'total', label: 'Total cases', value: enriched.length, variant: 'indigo' },
    { id: 'attention', label: 'Needs attention', value: attention.length, variant: 'yellow' },
    {
      id: 'logs',
      label: 'Logs due',
      value: enriched.reduce((n, c) => n + c.needsLogCount, 0),
      variant: 'purple',
    },
    { id: 'bookings', label: 'Upcoming bookings', value: bookedSlotsToday, variant: 'teal' },
  ]
}

export function uniqueServices(cases) {
  const set = new Set()
  for (const c of cases) {
    if (c.service) set.add(c.service)
    else if (c.productModule) set.add(c.productModule)
  }
  return [...set].sort((a, b) => a.localeCompare(b))
}

function stageBadge(caseRow, needsLogCount, reportPending) {
  if (needsLogCount > 0) return { variant: 'observation', label: 'Log due' }
  if (reportPending) return { variant: 'iep', label: 'Report pending' }
  const stage = (caseRow.operational_stage || caseRow.status || 'ACTIVE').toLowerCase()
  if (stage.includes('observation')) return { variant: 'observation', label: 'Observation' }
  if (stage.includes('iep')) return { variant: 'iep', label: 'IEP' }
  if (caseRow.status === 'CLOSED') return { variant: 'completed', label: 'Closed' }
  return { variant: 'active', label: caseRow.operational_stage || 'Active' }
}

export function buildCaseWorkbench({ cases = [], sessions = [], logs: _logs = [], reports = [], slots = [] }) {
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
      nextBooking: nextBooking
        ? {
            date: nextBooking.slot_date,
            startTime: String(nextBooking.start_time).slice(0, 5),
            endTime: String(nextBooking.end_time).slice(0, 5),
          }
        : null,
      critical,
      needsLogCount: needsLog.length,
      upcomingCount: upcoming.length,
      status: c.status,
      mapsUrl: c.maps_url,
      serviceAddress: c.service_address,
      borderAccent: critical ? 'yellow' : needsLog.length ? 'yellow' : nextBooking ? 'teal' : 'blue',
      showSubmitReport: !!draftReport || caseReports.length === 0,
      reportStatus: draftReport?.status || (caseReports[0]?.status ?? null),
    }
  })

  const upcomingBooked = bookedSlots.filter(
    (sl) => sl.status === 'BOOKED' && sl.case_id && sl.slot_date >= today,
  )
  const bookingCount = upcomingBooked.length

  return {
    stats: buildStatsFromCases(enriched, bookingCount),
    sections: buildSectionsFromCases(enriched),
    allCases: enriched,
    upcomingBooked,
  }
}
