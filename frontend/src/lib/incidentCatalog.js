/** Display labels collapse to the four canonical buckets (open / escalated / closed). */
export const INCIDENT_STATUS_META = {
  REPORTED: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  IN_REVIEW: { label: 'Escalated', bg: '#fee2e2', color: '#b91c1c' },
  ACTION_TAKEN: { label: 'Closed', bg: '#d1fae5', color: '#047857' },
  ESCALATED: { label: 'Escalated', bg: '#fee2e2', color: '#b91c1c' },
  CLOSED: { label: 'Closed', bg: '#f1f5f9', color: '#64748b' },
  OPEN: { label: 'Open', bg: '#fef3c7', color: '#b45309' },
  INVESTIGATING: { label: 'Escalated', bg: '#fee2e2', color: '#b91c1c' },
  RESOLVED: { label: 'Closed', bg: '#d1fae5', color: '#047857' },
}

export const PRIORITY_META = {
  NORMAL: { label: 'Normal', bg: '#f1f5f9', color: '#475569' },
  URGENT: { label: 'Urgent', bg: '#ffedd5', color: '#c2410c' },
  CRITICAL: { label: 'Critical', bg: '#fee2e2', color: '#991b1b' },
}

export const OPEN_INCIDENT_STATUSES = new Set(['REPORTED', 'IN_REVIEW', 'ACTION_TAKEN', 'ESCALATED', 'OPEN', 'INVESTIGATING', 'RESOLVED'])

export function isOpenIncidentStatus(status) {
  return OPEN_INCIDENT_STATUSES.has(status)
}

export function defaultPriorityForSubcategory(subcategory) {
  const critical = new Set([
    'medical_emergency', 'seizure_breathing', 'elopement', 'suspected_abuse', 'child_disclosure',
    'pocso_concern', 'posh_concern', 'cpp_concern', 'police_involvement', 'legal_notice',
  ])
  const urgent = new Set([
    'injury_fall', 'self_injury', 'parent_complaint', 'school_complaint', 'aggression',
    'boundary_concern', 'unprofessional_behaviour', 'confidentiality_breach', 'serious_boundary',
  ])
  if (critical.has(subcategory)) return 'CRITICAL'
  if (urgent.has(subcategory)) return 'URGENT'
  return 'NORMAL'
}
