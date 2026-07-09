/** Report-type sections only — goals/strategies/documents live on case tabs. */

export const REPORTS_HUB_SECTIONS = [
  { id: 'dashboard', label: 'Reports' },
  { id: 'observation', label: 'Observation Report' },
  { id: 'iep', label: 'IEP' },
  { id: 'monthly', label: 'Monthly Report' },
  { id: 'progress', label: 'Progress Report' },
  { id: 'history', label: 'Report History' },
]

const LEGACY_SECTION_MAP = {
  home: 'dashboard',
  drive: 'documents',
}

const CLIENT_TAB_SECTIONS = new Set(['goals-strategies', 'documents'])

export function normalizeReportsSection(raw) {
  if (!raw) return 'dashboard'
  const mapped = LEGACY_SECTION_MAP[raw] || raw
  if (CLIENT_TAB_SECTIONS.has(mapped)) return 'dashboard'
  return mapped
}

/** Old bookmarks that pointed goals/docs into the reports hub. */
export function resolveLegacyReportsSection(searchParams) {
  const tab = searchParams.get('tab')
  const section = searchParams.get('section')
  if (tab !== 'reports' || !section) return null
  if (section === 'goals-strategies') {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'goals')
    next.delete('section')
    next.delete('sub')
    return next
  }
  if (section === 'documents' || section === 'drive') {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'documents')
    next.delete('section')
    next.delete('sub')
    return next
  }
  return null
}
