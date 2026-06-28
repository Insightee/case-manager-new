import { NavLink, useLocation } from 'react-router-dom'
import { THERAPIST_CASE_TABS } from './caseProfileTabs.js'

function caseTabTarget(tab, caseId) {
  if (!caseId) {
    if (tab.id === 'overview') return '/therapist/cases'
    if (tab.id === 'reports') return '/therapist/reports'
    if (tab.id === 'logs') return '/therapist/logs'
    return '/therapist/cases'
  }

  const base = `/therapist/cases/${caseId}`
  if (tab.id === 'overview') return base
  if (tab.id === 'logs') return '/therapist/logs'
  if (tab.id === 'reports') return { pathname: base, search: '?tab=reports&section=dashboard' }
  return { pathname: base, search: `?tab=${tab.id}` }
}

/**
 * Nested under My Cases — expands via sidebar + control.
 */
export function CaseProfileSidebarNav({ caseId = null, activeTab = 'overview', onNavigate, nested = false }) {
  const location = useLocation()
  const Tag = nested ? 'div' : 'nav'

  return (
    <Tag className="app-sidebar__case-subnav" aria-label={nested ? undefined : 'Case sections'}>
      {THERAPIST_CASE_TABS.map((tab) => {
        const to = caseTabTarget(tab, caseId)
        const isActive =
          tab.id === 'logs'
            ? location.pathname === '/therapist/logs'
            : activeTab === tab.id
        return (
          <NavLink
            key={tab.id}
            to={to}
            end={tab.id === 'overview' && !caseId}
            onClick={onNavigate}
            className={`app-sidebar__case-subnav-link${isActive ? ' is-active' : ''}`}
          >
            {tab.label}
          </NavLink>
        )
      })}
    </Tag>
  )
}
