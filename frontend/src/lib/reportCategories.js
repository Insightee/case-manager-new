export const REPORT_CATEGORIES = [
  { id: 'CLIENT_MONTHLY', label: 'Client monthly report' },
  { id: 'OBSERVATION', label: 'Observation report' },
  { id: 'CM_MEETING', label: 'Case manager meeting report' },
  { id: 'IEP_PLAN', label: 'IEP plan' },
  { id: 'INCIDENT_DOCUMENT', label: 'Incident document' },
  { id: 'PROGRESS', label: 'Progress / milestone report' },
]

export const PROGRESS_SUB_CATEGORIES = [
  { id: 'TERMINATION', label: 'Termination report' },
  { id: 'ANNUAL', label: 'Annual progress report' },
  { id: 'MILESTONE', label: 'Milestone review' },
]

export function categoryLabel(id) {
  return REPORT_CATEGORIES.find((c) => c.id === id)?.label || id?.replace(/_/g, ' ') || 'Report'
}
