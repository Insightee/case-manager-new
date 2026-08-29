/**
 * Canonical support status buckets for tickets + incidents.
 * Mirrors backend/app/core/support_status.py — keep in sync.
 *
 * open        ← ticket OPEN (not escalated), incident REPORTED
 * in_progress ← ticket IN_PROGRESS (not escalated) only
 * escalated   ← incident IN_REVIEW + ESCALATED; tickets with escalated_to_department
 * closed      ← ticket RESOLVED + CLOSED; incident ACTION_TAKEN + CLOSED
 */

export const CANONICAL_OPEN = 'open'
export const CANONICAL_IN_PROGRESS = 'in_progress'
export const CANONICAL_CLOSED = 'closed'
export const CANONICAL_ESCALATED = 'escalated'

export const CANONICAL_STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  { value: CANONICAL_OPEN, label: 'Open' },
  { value: CANONICAL_IN_PROGRESS, label: 'In progress' },
  { value: CANONICAL_CLOSED, label: 'Closed' },
  { value: CANONICAL_ESCALATED, label: 'Escalated' },
]

export const CANONICAL_LABELS = {
  [CANONICAL_OPEN]: 'Open',
  [CANONICAL_IN_PROGRESS]: 'In progress',
  [CANONICAL_CLOSED]: 'Closed',
  [CANONICAL_ESCALATED]: 'Escalated',
}

/** Urgency rank for triage sort — lower = more urgent. */
const URGENCY_RANK = {
  [CANONICAL_ESCALATED]: 0,
  [CANONICAL_OPEN]: 1,
  [CANONICAL_IN_PROGRESS]: 2,
  [CANONICAL_CLOSED]: 4,
}

export function normalizeCanonical(value) {
  if (value == null || value === '') return null
  const raw = String(value).trim().toLowerCase().replace(/[-\s]/g, '_')
  const aliases = {
    reported: CANONICAL_OPEN,
    resolved: CANONICAL_CLOSED,
    action_taken: CANONICAL_CLOSED,
    in_review: CANONICAL_ESCALATED,
    investigating: CANONICAL_ESCALATED,
    open: CANONICAL_OPEN,
    in_progress: CANONICAL_IN_PROGRESS,
    closed: CANONICAL_CLOSED,
    escalated: CANONICAL_ESCALATED,
  }
  if (aliases[raw]) return aliases[raw]
  const upper = String(value).trim().toUpperCase()
  if (upper === 'OPEN' || upper === 'REPORTED') return CANONICAL_OPEN
  if (upper === 'IN_PROGRESS') return CANONICAL_IN_PROGRESS
  if (upper === 'CLOSED' || upper === 'RESOLVED' || upper === 'ACTION_TAKEN') return CANONICAL_CLOSED
  if (upper === 'ESCALATED' || upper === 'IN_REVIEW') return CANONICAL_ESCALATED
  return null
}

export function ticketIsEscalated({ status, escalated_to_department: dept }) {
  if (!dept) return false
  const st = String(status || '').toUpperCase()
  if (st === 'RESOLVED' || st === 'CLOSED') return false
  return true
}

export function canonicalTicketStatus(status, { escalated_to_department } = {}) {
  if (ticketIsEscalated({ status, escalated_to_department })) return CANONICAL_ESCALATED
  const raw = String(status || '').toUpperCase()
  if (raw === 'OPEN') return CANONICAL_OPEN
  if (raw === 'IN_PROGRESS') return CANONICAL_IN_PROGRESS
  if (raw === 'RESOLVED' || raw === 'CLOSED') return CANONICAL_CLOSED
  return CANONICAL_OPEN
}

export function canonicalIncidentStatus(status) {
  let raw = String(status || '').trim().toUpperCase()
  const legacy = { OPEN: 'REPORTED', INVESTIGATING: 'IN_REVIEW', RESOLVED: 'ACTION_TAKEN' }
  raw = legacy[raw] || raw
  if (raw === 'REPORTED') return CANONICAL_OPEN
  if (raw === 'IN_REVIEW' || raw === 'ESCALATED') return CANONICAL_ESCALATED
  if (raw === 'ACTION_TAKEN' || raw === 'CLOSED') return CANONICAL_CLOSED
  return CANONICAL_OPEN
}

export function canonicalStatus(recordType, status, extras = {}) {
  const rt = String(recordType || '').toLowerCase()
  if (rt === 'ticket' || rt === 'tickets') {
    return canonicalTicketStatus(status, extras)
  }
  return canonicalIncidentStatus(status)
}

/** Prefer server-provided canonical_status when present. */
export function rowCanonicalStatus(row) {
  if (!row) return CANONICAL_OPEN
  if (row.canonical_status) {
    return normalizeCanonical(row.canonical_status) || CANONICAL_OPEN
  }
  return canonicalStatus(row.record_type, row.status, {
    escalated_to_department: row.escalated_to_department,
  })
}

export function canonicalLabel(value) {
  const key = normalizeCanonical(value) || value
  return CANONICAL_LABELS[key] || (key ? String(key).replace(/_/g, ' ') : '')
}

export function urgencyRank(canonicalOrRaw) {
  const key = normalizeCanonical(canonicalOrRaw) || canonicalOrRaw
  return URGENCY_RANK[key] ?? 50
}

export function isUrgentCanonical(canonicalOrRaw) {
  return urgencyRank(canonicalOrRaw) <= 2
}

/** Ticket write menu → underlying enum. */
export function writeTicketStatus(canonical) {
  const key = normalizeCanonical(canonical) || CANONICAL_OPEN
  if (key === CANONICAL_IN_PROGRESS || key === CANONICAL_ESCALATED) return 'IN_PROGRESS'
  if (key === CANONICAL_CLOSED) return 'CLOSED'
  return 'OPEN'
}

/** Incident write menu → underlying enum. */
export function writeIncidentStatus(canonical) {
  const key = normalizeCanonical(canonical) || CANONICAL_OPEN
  if (key === CANONICAL_ESCALATED || key === CANONICAL_IN_PROGRESS) return 'ESCALATED'
  if (key === CANONICAL_CLOSED) return 'CLOSED'
  return 'REPORTED'
}
