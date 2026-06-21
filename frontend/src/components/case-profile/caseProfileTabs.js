/** Top-level case profile tabs by portal role. */

export const THERAPIST_CASE_TABS = [
  { id: 'overview', label: 'Overview', shortLabel: 'Overview' },
  { id: 'reports', label: 'Reports', shortLabel: 'Reports' },
  { id: 'goals', label: 'Goals', shortLabel: 'Goals' },
  { id: 'strategies', label: 'Strategies', shortLabel: 'Strat.' },
  { id: 'logs', label: 'Logs', shortLabel: 'Logs' },
  { id: 'insights', label: 'Insights', shortLabel: 'Insights' },
  { id: 'documents', label: 'Documents', shortLabel: 'Docs' },
]

export const ADMIN_CASE_TABS_REVAMP = [
  { id: 'overview', label: 'Overview' },
  { id: 'reports', label: 'Reports' },
  { id: 'goals', label: 'Goals' },
  { id: 'strategies', label: 'Strategies' },
  { id: 'logs', label: 'Logs' },
  { id: 'insights', label: 'Insights' },
  { id: 'documents', label: 'Documents' },
  { id: 'activity', label: 'Activity' },
  { id: 'incidents', label: 'Incidents', perm: 'incident.read_sensitive' },
  { id: 'billing', label: 'Billing', perm: 'case.update' },
  { id: 'scheduling', label: 'Assign & Schedule', perm: 'slot.book_any' },
]

export const REPORTS_SUB_TABS = [
  { id: 'home', label: 'Overview' },
  { id: 'observation', label: 'Observation' },
  { id: 'iep', label: 'IEP' },
  { id: 'monthly', label: 'Monthly' },
  { id: 'progress', label: 'Progress' },
  { id: 'drive', label: 'Document Drive' },
]
