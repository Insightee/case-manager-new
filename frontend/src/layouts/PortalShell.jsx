import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { actionIdFromPath, recordTherapistAction } from '../lib/therapistActions.js'
import { avatarSrc } from '../components/shared/AvatarUpload.jsx'
import { NotificationBell } from '../components/shared/NotificationBell.jsx'
import '../components/shared/notification-bell.css'

const THERAPIST_NAV = [
  { to: '/therapist', label: 'Dashboard', end: true },
  { to: '/therapist/cases', label: 'My Cases' },
  { to: '/therapist/logs', label: 'Session Logs' },
  { to: '/therapist/reports', label: 'Monthly Reports' },
  { to: '/therapist/invoices', label: 'Invoices' },
  { to: '/therapist/tickets', label: 'Support Tickets' },
  { to: '/therapist/leave', label: 'Leave' },
  { to: '/therapist/slots', label: 'Open Slots' },
  { to: '/therapist/profile', label: 'My Profile' },
]

const HR_NAV = [
  { to: '/hr', label: 'Dashboard', end: true, icon: '▦' },
  { to: '/hr/therapists', label: 'Therapists', icon: '👤' },
  { to: '/hr/cases', label: 'Cases', icon: '◉' },
  { to: '/hr/leave', label: 'Leave Management', icon: '📅' },
  { to: '/hr/memos', label: 'Memos', icon: '✉' },
  { to: '/hr/tickets', label: 'Tickets', icon: '🎫' },
]

const PARENT_NAV = [
  { to: '/parent', label: 'Dashboard', end: true },
  { to: '/parent/session-logs', label: 'Session updates' },
  { to: '/parent/book', label: 'Session schedule' },
  { to: '/parent/reports', label: 'Reports' },
  { to: '/parent/billing', label: 'Billing' },
  { to: '/parent/profile', label: 'My profile' },
  { to: '/parent/support', label: 'Support' },
]

const ADMIN_NAV = [
  { to: '/admin', label: 'Dashboard', end: true, perm: null, feature: null, icon: '▦' },
  { to: '/admin/cases', label: 'Cases', perm: 'case.read.all', feature: 'cases', icon: '◉' },
  { to: '/admin/logs', label: 'Session Logs', perm: 'session.read', feature: 'session_logs', icon: '☰' },
  { to: '/admin/reports', label: 'Report Review', perm: 'monthly_report.approve', feature: 'reports', icon: '▣' },
  { to: '/admin/invoices', label: 'Invoices', perm: 'invoice.approve', feature: 'invoices', icon: '₹' },
  { to: '/admin/iep', label: 'IEP', perm: 'attachment.manage', feature: 'iep', icon: '📎' },
  { to: '/admin/tickets', label: 'Tickets', perm: 'ticket.manage', feature: 'tickets', icon: '✉' },
  { to: '/admin/incidents', label: 'Incidents', perm: 'incident.read_sensitive', feature: 'incidents', icon: '⚠' },
  { to: '/admin/people', label: 'People', perm: 'user.manage', feature: null, icon: '👥' },
  { to: '/admin/therapist-profiles', label: 'Therapist profiles', perm: 'user.manage', feature: null, icon: '🩺' },
  { to: '/admin/cm-meetings', label: 'CM Meetings', perm: 'case.read.team', feature: null, icon: '🗓' },
]

function NavLinks({ items, portal, className, linkClassName, onNavigate }) {
  return (
    <nav className={className}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          onClick={onNavigate}
          className={({ isActive }) =>
            `${linkClassName}${isActive ? ' is-active' : ''}`
          }
        >
          {(portal === 'admin' || portal === 'hr') && item.icon ? (
            <span className="app-sidebar__link-icon" aria-hidden>
              {item.icon}
            </span>
          ) : null}
          {item.label}
        </NavLink>
      ))}
    </nav>
  )
}

export function PortalShell({ portal }) {
  const { user, logout, can, hasFeature } = useAuth()
  const location = useLocation()
  const [accountOpen, setAccountOpen] = useState(false)

  useEffect(() => {
    setAccountOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (portal !== 'therapist' || !user?.id) return
    const actionId = actionIdFromPath(location.pathname)
    if (actionId) recordTherapistAction(user.id, actionId)
  }, [portal, user?.id, location.pathname])

  const PORTAL_LABELS = {
    parent: 'Client Portal',
    admin: 'Admin Portal',
    therapist: 'Therapist Portal',
    hr: 'HR Portal',
  }
  const subtitle = PORTAL_LABELS[portal] || 'Portal'

  let nav = THERAPIST_NAV
  if (portal === 'parent') nav = PARENT_NAV
  if (portal === 'hr') nav = HR_NAV
  if (portal === 'admin') {
    nav = ADMIN_NAV.filter((item) => {
      if (item.perm && !can(item.perm)) return false
      if (item.feature && !hasFeature(item.feature)) return false
      return true
    })
  }

  const portalTitle = PORTAL_LABELS[portal] || 'Portal'
  useDocumentTitle(`InsightCase — ${portalTitle}`)

  const shellClass = portal === 'admin' || portal === 'hr' ? 'app-shell app-shell--admin' : 'app-shell'
  const firstName = user?.full_name?.split(/\s+/)[0] || 'Account'
  const profilePath =
    portal === 'parent'
      ? '/parent/profile'
      : portal === 'therapist'
        ? '/therapist/profile'
        : null

  return (
    <div className={shellClass}>
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
            onClick={() => setAccountOpen((o) => !o)}
          >
            {avatarSrc(user) ? (
              <img src={avatarSrc(user)} alt="" className="app-mobile-topbar__avatar" />
            ) : (
              <span className="app-mobile-topbar__avatar app-mobile-topbar__avatar--initial">
                {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
              </span>
            )}
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

      <NavLinks
        items={nav}
        portal={portal}
        className="app-mobile-tabs"
        linkClassName="app-mobile-tabs__link"
      />

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
          portal={portal}
          className="app-sidebar__nav"
          linkClassName="app-sidebar__link"
        />
        <div className="app-sidebar__footer">
          <div className="app-sidebar__user">
            {avatarSrc(user) ? (
              <img src={avatarSrc(user)} alt="" className="app-sidebar__user-avatar" />
            ) : (
              <span className="app-sidebar__user-avatar app-sidebar__user-avatar--initial">
                {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
              </span>
            )}
            <p className="app-sidebar__help">{user?.full_name}</p>
          </div>
          <button type="button" className="app-sidebar__logout" onClick={logout}>
            Logout
          </button>
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
