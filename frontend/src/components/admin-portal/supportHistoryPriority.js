/**
 * Sort combined support history for admin triage.
 * Open and escalated items surface first (aligned with ticket/incident escalation flows).
 */
const URGENCY_RANK = {
  ESCALATED: 0,
  OPEN: 1,
  REPORTED: 1,
  IN_PROGRESS: 2,
  IN_REVIEW: 2,
  ACTION_TAKEN: 3,
  RESOLVED: 4,
  CLOSED: 5,
}

function urgencyRank(status) {
  if (!status) return 99
  return URGENCY_RANK[status] ?? 50
}

function isUrgent(row) {
  const rank = urgencyRank(row.status)
  return rank <= 2
}

export function sortSupportHistoryByUrgency(rows) {
  return [...rows].sort((a, b) => {
    const ra = urgencyRank(a.status)
    const rb = urgencyRank(b.status)
    if (ra !== rb) return ra - rb
    const ta = a.created_at ? Date.parse(a.created_at) : 0
    const tb = b.created_at ? Date.parse(b.created_at) : 0
    return tb - ta
  })
}

export { isUrgent, urgencyRank }
