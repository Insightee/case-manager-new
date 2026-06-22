import { NavLink } from 'react-router-dom'
import { REPORTS_HUB_SECTIONS } from './reportsHubSections.js'

function reportSectionTarget(item, caseId) {
  if (!caseId) {
    return item.id === 'dashboard' ? '/therapist/reports' : '/therapist/reports'
  }
  return {
    pathname: `/therapist/cases/${caseId}`,
    search: `?tab=reports&section=${item.id}`,
  }
}

/**
 * Nested under portal Reports — expands via sidebar + control.
 */
export function CaseReportsSidebarNav({
  caseId = null,
  activeSection = 'dashboard',
  onNavigate,
  nested = false,
}) {
  const Tag = nested ? 'div' : 'nav'

  return (
    <Tag className="app-sidebar__case-subnav" aria-label={nested ? undefined : 'Report sections'}>
      {REPORTS_HUB_SECTIONS.map((item) => {
        const to = reportSectionTarget(item, caseId)
        const isActive = activeSection === item.id
        return (
          <NavLink
            key={item.id}
            to={to}
            end={item.id === 'dashboard' && !caseId}
            onClick={onNavigate}
            className={`app-sidebar__case-subnav-link${isActive ? ' is-active' : ''}`}
          >
            {item.label}
          </NavLink>
        )
      })}
    </Tag>
  )
}
