/** Top-level case profile tabs by portal role. */

export const THERAPIST_CASE_TABS = [
  { id: 'overview', label: 'Overview', shortLabel: 'Overview' },
  { id: 'reports', label: 'Reports', shortLabel: 'Reports' },
  { id: 'goals', label: 'Goals & Strategies', shortLabel: 'Goals' },
  { id: 'logs', label: 'Logs', shortLabel: 'Logs' },
  { id: 'insights', label: 'Insights', shortLabel: 'Insights' },
  { id: 'documents', label: 'Documents', shortLabel: 'Docs' },
]

export const ADMIN_CASE_TABS_REVAMP = [
  { id: 'overview', label: 'Overview' },
  { id: 'reports', label: 'Reports' },
  { id: 'goals', label: 'Goals & Strategies' },
  { id: 'logs', label: 'Logs' },
  { id: 'insights', label: 'Insights' },
  { id: 'documents', label: 'Documents' },
  { id: 'activity', label: 'Activity' },
  { id: 'incidents', label: 'Incidents', perm: 'incident.read_sensitive' },
  { id: 'billing', label: 'Billing', perm: 'case.update' },
  { id: 'scheduling', label: 'Assign & Schedule', perm: 'slot.book_any' },
]

/** @deprecated Use REPORTS_HUB_SECTIONS */
export const REPORTS_SUB_TABS = [
  { id: 'observation', label: 'Observation Report' },
  { id: 'iep', label: 'IEP Report' },
  { id: 'monthly', label: 'Monthly Report' },
  { id: 'progress', label: 'Progress Report' },
  { id: 'history', label: 'Report History' },
]

/** Build a case profile URL for a Reports hub section. */
export function caseReportsSectionUrl(basePath, section) {
  const params = new URLSearchParams({ tab: 'reports', section })
  return `${basePath}?${params.toString()}`
}
