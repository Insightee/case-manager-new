/**
 * Sort combined support history for admin triage.
 * Uses canonical status buckets (open / in_progress / closed / escalated).
 */
import {
  isUrgentCanonical,
  rowCanonicalStatus,
  urgencyRank as canonicalUrgencyRank,
} from '../../lib/supportStatus.js'

function urgencyRank(rowOrStatus) {
  if (rowOrStatus && typeof rowOrStatus === 'object') {
    return canonicalUrgencyRank(rowCanonicalStatus(rowOrStatus))
  }
  return canonicalUrgencyRank(rowOrStatus)
}

function isUrgent(row) {
  return isUrgentCanonical(rowCanonicalStatus(row))
}

export function sortSupportHistoryByUrgency(rows) {
  return [...rows].sort((a, b) => {
    const ra = urgencyRank(a)
    const rb = urgencyRank(b)
    if (ra !== rb) return ra - rb
    const ta = a.created_at ? Date.parse(a.created_at) : 0
    const tb = b.created_at ? Date.parse(b.created_at) : 0
    return tb - ta
  })
}

export { isUrgent, urgencyRank }
