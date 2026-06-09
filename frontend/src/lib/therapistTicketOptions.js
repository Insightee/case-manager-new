/** Request types for therapist support tickets — maps UI selection to API category + topic. */
export const THERAPIST_REQUEST_TYPES = [
  { value: 'CASE_MANAGER', label: 'Case manager', topic: 'CASE_MANAGER', category: 'SERVICE' },
  { value: 'FINANCE', label: 'Finance / billing', topic: 'BILLING_PAYMENT', category: 'FINANCE' },
  { value: 'HR', label: 'HR', topic: 'OTHER', category: 'HR' },
  { value: 'SERVICE', label: 'Service delivery', topic: 'OTHER', category: 'SERVICE' },
  { value: 'POSH', label: 'POSH', topic: 'OTHER', category: 'POSH' },
  { value: 'CPP', label: 'CPP', topic: 'OTHER', category: 'CPP' },
  { value: 'OTHER', label: 'General / other', topic: 'OTHER', category: 'OTHER' },
]

export function requestTypeByValue(value) {
  return THERAPIST_REQUEST_TYPES.find((t) => t.value === value) || THERAPIST_REQUEST_TYPES.at(-1)
}

export function therapistTicketsUrl({ topic, caseId, openForm = true } = {}) {
  const params = new URLSearchParams()
  if (openForm) params.set('new', '1')
  if (topic) params.set('topic', topic)
  if (caseId != null && caseId !== '') params.set('case_id', String(caseId))
  const qs = params.toString()
  return `/therapist/tickets${qs ? `?${qs}` : ''}`
}
