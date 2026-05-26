import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { isCaseManagerOnlyRole } from '../lib/adminCasePipeline.js'
import { clinicalProductModuleIds } from '../lib/moduleAccess.js'
import { usePageMeta } from '../hooks/usePageMeta.js'
import { actionIdFromPath, recordTherapistAction } from '../lib/therapistActions.js'
import { AuthenticatedAvatar } from '../components/shared/AvatarUpload.jsx'
import { NotificationBell } from '../components/shared/NotificationBell.jsx'
import { NavIcon } from '../components/shared/NavIcon.jsx'
import { SkipLink } from '../components/shared/SkipLink.jsx'
import '../components/shared/notification-bell.css'

const THERAPIST_NAV = [
  { to: '/therapist', label: 'Dashboard', end: true },
  { to: '/therapist/cases', label: 'My Cases' },
  { to: '/therapist/logs', label: 'Session Logs' },
  { to: '/therapist/reports', label: 'Monthly Reports' },
  { to: '/therapist/invoices', label: 'Invoices' },
  { to: '/therapist/support', label: 'Support & Incidents' },
  { to: '/therapist/cm-meetings', label: 'CM meetings' },
  { to: '/therapist/leave', label: 'Leave' },
  { to: '/therapist/slots', label: 'Open Slots' },
  { to: '/therapist/profile', label: 'My Profile' },
]

const THERAPIST_MOBILE_NAV = [
  { to: '/therapist/logs', label: 'Today' },
  { to: '/therapist/cases', label: 'Cases' },
  { to: '/therapist/reports', label: 'Reports' },
  { to: '/therapist', label: 'Home', end: true },
]

const PARENT_NAV = [
  { to: '/parent', label: 'Dashboard', end: true },
  { to: '/parent/session-logs', label: 'Session updates' },
  { to: '/parent/book', label: 'Session schedule' },
  { to: '/parent/reports', label: 'Reports' },
  { to: '/parent/billing', label: 'Billing' },
  { to: '/parent/profile', label: 'My profile' },
  { to: '/parent/support', label: 'Support & Incidents' },
]

/** Nav for users whose only operational role is Case Manager (not module admin / finance / HR). */
function caseManagerNav(clinicalModuleIds) {
  return [
    { to: '/admin/cm', label: 'My caseload', end: true, perm: null, feature: null, icon: 'dashboard' },
    { to: '/admin/cases', label: 'Cases', perm: 'case.read.team', feature: 'cases', moduleIds: clinicalModuleIds, icon: 'cases' },
    { to: '/admin/workbench', label: 'Review queues', perm: 'case.read.team', moduleIds: clinicalModuleIds, icon: 'workbench' },
    { to: '/admin/logs', label: 'Session Logs', perm: 'session.read', feature: 'session_logs', moduleIds: clinicalModuleIds, icon: 'grid' },
    { to: '/admin/reports', label: 'Reports', perm: 'monthly_report.approve', feature: 'reports', moduleIds: clinicalModuleIds, icon: 'reports' },
    { to: '/admin/iep', label: 'IEP', perm: 'iep.read', feature: 'iep', moduleIds: clinicalModuleIds, icon: 'iep' },
    { to: '/admin/cm-meetings', label: 'CM Meetings', perm: 'case.read.team', moduleIds: clinicalModuleIds, icon: 'meetings' },
    { to: '/admin/support', label: 'Support & Incidents', perm: 'ticket.manage', feature: 'tickets', moduleIds: clinicalModuleIds, icon: 'mail' },
  ]
}

function adminNav(clinicalModuleIds) {
  return [
    { to: '/admin', label: 'Dashboard', end: true, perm: null, feature: null, icon: 'dashboard', section: 'Operations' },
    { to: '/admin/workbench', label: 'Workbench', perm: 'case.read.team', moduleIds: clinicalModuleIds, icon: 'workbench', section: 'Operations' },
    { to: '/admin/cases', label: 'Cases', perm: 'case.read.all', feature: 'cases', moduleIds: clinicalModuleIds, icon: 'cases', section: 'Operations' },
    { to: '/admin/logs', label: 'Session Logs', perm: 'session.read', feature: 'session_logs', moduleIds: clinicalModuleIds, icon: 'grid', section: 'Operations' },
    { to: '/admin/reports', label: 'Reports', perm: 'monthly_report.approve', feature: 'reports', moduleIds: clinicalModuleIds, icon: 'reports', section: 'Operations' },
    { to: '/admin/iep', label: 'IEP', perm: 'iep.read', feature: 'iep', moduleIds: clinicalModuleIds, icon: 'iep', section: 'Operations' },
    { to: '/admin/support', label: 'Support & Incidents', perm: 'ticket.manage', feature: 'tickets', moduleIds: clinicalModuleIds, icon: 'mail', section: 'Operations' },
    { to: '/admin/cm-meetings', label: 'CM Meetings', perm: 'case.read.team', feature: null, icon: 'meetings', section: 'Operations' },
    { to: '/admin/invoices', label: 'Invoices & payments', perm: 'invoice.approve', feature: 'invoices', moduleIds: ['billing'], icon: 'invoices', section: 'Finance' },
    { to: '/admin/people', label: 'People', perm: 'user.manage', feature: null, icon: 'people', section: 'People & HR' },
    { to: '/admin/therapist-profiles', label: 'Therapist profiles', perm: 'user.manage', feature: null, icon: 'stethoscope', section: 'People & HR' },
    { to: '/admin/leave', label: 'Leave', perm: 'leave.manage', feature: null, icon: 'leave', section: 'People & HR' },
    { to: '/admin/memos', label: 'Memos', perm: 'memo.send', feature: null, icon: 'mail', section: 'People & HR' },
    { to: '/admin/hr-cases', label: 'HR case view', perm: 'case.read.team', feature: 'cases', moduleIds: clinicalModuleIds, icon: 'cases', section: 'People & HR' },
    { to: '/admin/settings/services', label: 'Service categories', perm: 'user.manage', feature: null, icon: 'settings', section: 'Settings' },
  ]
}

const PORTAL_LABELS = {
  parent: 'Client Portal',
  admin: 'Staff Portal',
  therapist: 'Therapist Portal',
}

function NavLinks({ items, className, linkClassName, onNavigate, showIcons }) {
  let lastSection = null
  return (
    <nav className={className} aria-label="Portal navigation">
      {items.map((item) => {
        if (item.isMore) {
          return null
        }
        const sectionHeader =
          item.section && item.section !== lastSection ? (
            <p key={`section-${item.section}`} className="app-sidebar__nav-section">
              {item.section}
            </p>
          ) : null
        if (item.section) lastSection = item.section
        return (
          <span key={item.to} className="app-sidebar__nav-item-wrap">
            {sectionHeader}
            <NavLink
              to={item.to}
              end={item.end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `${linkClassName}${isActive ? ' is-active' : ''}`
              }
            >
              {showIcons && item.icon ? <NavIcon name={item.icon} /> : null}
              <span>{item.label}</span>
            </NavLink>
          </span>
        )
      })}
    </nav>
  )
}

function buildMobileTabs(fullNav, portal) {
  if (portal === 'therapist') {
    return { tabs: THERAPIST_MOBILE_NAV, useMenu: false }
  }
  if (fullNav.length <= 4) {
    return { tabs: fullNav, useMenu: false }
  }
  const home = fullNav.find((n) => n.end) ?? fullNav[0]
  const cases =
    fullNav.find((n) => n.to.includes('/cases')) ??
    fullNav.find((n) => n.to.includes('/workbench')) ??
    fullNav[1]
  const reports =
    fullNav.find((n) => n.to.includes('/reports')) ??
    fullNav.find((n) => n.to.includes('/logs')) ??
    fullNav[2]
  const tabs = [home, cases, reports].filter(Boolean)
  const seen = new Set()
  const unique = tabs.filter((t) => {
    if (seen.has(t.to)) return false
    seen.add(t.to)
    return true
  })
  return { tabs: unique.slice(0, 3), useMenu: true }
}

function filterAdminNavItem(item, { roles, navVisible, can, hasFeature }) {
  if (item.to === '/admin/cm') {
    return roles.includes('CASE_MANAGER') && can('case.read.team')
  }
  if (item.to === '/admin/workbench') {
    return (
      navVisible(item)
      && (can('monthly_report.approve') || can('daily_log.review'))
    )
  }
  if (item.to === '/admin/cases') {
    return (
      navVisible(item)
      && (can('case.read.all') || can('case.read.team') || can('case.read.scoped'))
    )
  }
  if (item.to === '/admin/iep') {
    return navVisible(item) && (can('attachment.manage') || can('iep.read'))
  }
  if (item.to === '/admin/support') {
    const ticketsOk = can('ticket.manage') && hasFeature('tickets')
    const incidentsOk = can('incident.read_sensitive') && hasFeature('incidents')
    if (!ticketsOk && !incidentsOk) return false
    return !item.moduleIds?.length || navVisible(item)
  }
  if (item.perm || item.feature || item.moduleIds?.length) {
    return navVisible(item)
  }
  return true
}

export function PortalShell({ portal }) {
  const { user, logout, can, hasFeature, isViewOnly, navVisible } = useAuth()
  const location = useLocation()
  const [accountOpen, setAccountOpen] = useState(false)
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- close overlays on route change
    setAccountOpen(false)
    setMobileNavOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!mobileNavOpen) return undefined
    const onKey = (e) => {
      if (e.key === 'Escape') setMobileNavOpen(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [mobileNavOpen])

  useEffect(() => {
    if (portal !== 'therapist' || !user?.id) return
    const actionId = actionIdFromPath(location.pathname)
    if (actionId) recordTherapistAction(user.id, actionId)
  }, [portal, user?.id, location.pathname])

  const subtitle = PORTAL_LABELS[portal] || 'Portal'

  let nav = THERAPIST_NAV
  if (portal === 'parent') nav = PARENT_NAV
  if (portal === 'admin') {
    const roles = user?.roles || []
    const cmFocused = isCaseManagerOnlyRole(roles)
    const clinicalIds = clinicalProductModuleIds(user)
    const baseNav = cmFocused ? caseManagerNav(clinicalIds) : adminNav(clinicalIds)
    nav = baseNav.filter((item) =>
      filterAdminNavItem(item, { roles, navVisible, can, hasFeature }),
    )
  }

  const portalTitle = PORTAL_LABELS[portal] || 'Portal'
  usePageMeta({ title: portalTitle })

  const { tabs: mobileTabs, useMenu } = useMemo(
    () => buildMobileTabs(nav, portal),
    [nav, portal],
  )

  const showNavIcons = portal === 'admin'
  const shellClass = portal === 'admin' ? 'app-shell app-shell--admin' : 'app-shell'
  const firstName = user?.full_name?.split(/\s+/)[0] || 'Account'
  const profilePath =
    portal === 'parent'
      ? '/parent/profile'
      : portal === 'therapist'
        ? '/therapist/profile'
        : null

  return (
    <div className={shellClass}>
      <SkipLink />
      <header className="app-mobile-topbar">
        <div className="app-mobile-topbar__brand">
          <span className="app-mobile-topbar__logo" aria-hidden />
          <div>
            <span className="app-mobile-topbar__title">InsightCase</span>
            <span className="app-mobile-topbar__sub">{subtitle}</span>
          </div>
        </div>
        <div className="app-mobile-topbar__account" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <NotificationBell portal={portal} />
          <button
            type="button"
            className="app-mobile-topbar__profile"
            aria-expanded={accountOpen}
            aria-controls="mobile-account-menu"
            aria-haspopup="menu"
            onClick={() => setAccountOpen((o) => !o)}
          >
            <AuthenticatedAvatar user={user} className="app-mobile-topbar__avatar" size={36} />
            <span className="app-mobile-topbar__name">{firstName}</span>
            <span className="app-mobile-topbar__chevron" aria-hidden>
              {accountOpen ? '▲' : '▼'}
            </span>
          </button>
          {accountOpen ? (
            <div id="mobile-account-menu" className="app-mobile-account-menu" role="menu">
              <p className="app-mobile-account-menu__name">{user?.full_name}</p>
              {profilePath ? (
                <NavLink
                  to={profilePath}
                  className="app-mobile-account-menu__link"
                  role="menuitem"
                  onClick={() => setAccountOpen(false)}
                >
                  My profile
                </NavLink>
              ) : null}
              <button
                type="button"
                className="app-mobile-account-menu__logout"
                role="menuitem"
                onClick={logout}
              >
                Logout
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <nav
        className="app-mobile-tabs app-mobile-tabs--bottom app-mobile-tabs--compact"
        aria-label="Quick navigation"
      >
        {mobileTabs.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            className={({ isActive }) =>
              `app-mobile-tabs__link${isActive ? ' is-active' : ''}`
            }
          >
            {item.label}
          </NavLink>
        ))}
        {useMenu ? (
          <button
            type="button"
            className={`app-mobile-tabs__link app-mobile-tabs__link--menu${mobileNavOpen ? ' is-active' : ''}`}
            aria-expanded={mobileNavOpen}
            aria-controls="portal-nav-drawer"
            onClick={() => setMobileNavOpen((o) => !o)}
          >
            Menu
          </button>
        ) : null}
      </nav>

      {useMenu ? (
        <>
          <button
            type="button"
            className={`app-shell__backdrop${mobileNavOpen ? ' is-visible' : ''}`}
            aria-label="Close navigation menu"
            tabIndex={mobileNavOpen ? 0 : -1}
            onClick={() => setMobileNavOpen(false)}
          />
          <aside
            id="portal-nav-drawer"
            className={`app-sidebar app-sidebar--drawer${mobileNavOpen ? ' is-open' : ''}`}
            aria-hidden={!mobileNavOpen}
          >
            <div className="app-sidebar__brand">
              <span className="app-sidebar__logo" aria-hidden />
              <div>
                <p className="app-sidebar__title">InsightCase</p>
                <p className="app-sidebar__sub">{subtitle}</p>
              </div>
            </div>
            <NavLinks
              items={nav}
              className="app-sidebar__nav"
              linkClassName="app-sidebar__link"
              showIcons={showNavIcons}
              onNavigate={() => setMobileNavOpen(false)}
            />
          </aside>
        </>
      ) : null}

      <aside className="app-sidebar app-sidebar--desktop">
        <div className="app-sidebar__brand" style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <span className="app-sidebar__logo" aria-hidden />
            <div>
              <h1 className="app-sidebar__title">InsightCase</h1>
              <p className="app-sidebar__sub">{subtitle}</p>
            </div>
          </div>
          <NotificationBell portal={portal} />
        </div>
        <NavLinks
          items={nav}
          className="app-sidebar__nav"
          linkClassName="app-sidebar__link"
          showIcons={showNavIcons}
        />
        <div className="app-sidebar__footer">
          {profilePath ? (
            <NavLink to={profilePath} className="app-sidebar__user-card" title="Go to profile">
              <AuthenticatedAvatar user={user} className="app-sidebar__user-avatar" size={40} />
              <div className="app-sidebar__user-info">
                <span className="app-sidebar__user-name">{user?.full_name || 'Account'}</span>
                <span className="app-sidebar__user-role">{subtitle}</span>
              </div>
              <span className="app-sidebar__user-chevron" aria-hidden>
                ›
              </span>
            </NavLink>
          ) : (
            <div className="app-sidebar__user-card app-sidebar__user-card--static">
              <AuthenticatedAvatar user={user} className="app-sidebar__user-avatar" size={40} />
              <div className="app-sidebar__user-info">
                <span className="app-sidebar__user-name">{user?.full_name || 'Account'}</span>
                <span className="app-sidebar__user-role">{subtitle}</span>
              </div>
            </div>
          )}

          <button type="button" className="app-sidebar__logout" onClick={logout}>
            <svg
              className="app-sidebar__logout-icon"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              aria-hidden
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13 7l3 3m0 0l-3 3m3-3H8m5-7H5a2 2 0 00-2 2v10a2 2 0 002 2h8"
              />
            </svg>
            Sign out
          </button>
        </div>
      </aside>

      <main id="main-content" className="content" tabIndex={-1}>
        {portal === 'admin' && isViewOnly ? (
          <div
            role="status"
            className="admin-view-only-banner"
            style={{
              margin: '0 0 16px',
              padding: '10px 14px',
              background: '#fffbeb',
              border: '1px solid #fcd34d',
              borderRadius: 8,
              fontSize: '0.875rem',
              color: '#92400e',
            }}
          >
            View-only access — you can browse enabled modules but cannot create or update records.
            {(user?.modules || [])
              .filter((m) => m.access === 'view')
              .map((m) => m.label)
              .join(', ')
              ? ` (${(user.modules || []).filter((m) => m.access === 'view').map((m) => m.label).join(', ')}: view only)`
              : null}
          </div>
        ) : null}
        {portal === 'admin' && !isViewOnly && (user?.modules || []).some((m) => m.access === 'view') ? (
          <div
            role="status"
            style={{
              margin: '0 0 16px',
              padding: '10px 14px',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              fontSize: '0.8125rem',
              color: '#475569',
            }}
          >
            Some modules are view-only:{' '}
            {(user.modules || [])
              .filter((m) => m.access === 'view')
              .map((m) => m.label)
              .join(', ')}
            . Edit actions are disabled for those programmes.
          </div>
        ) : null}
        <Outlet />
      </main>
    </div>
  )
}
