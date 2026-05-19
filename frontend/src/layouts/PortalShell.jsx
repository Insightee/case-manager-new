import { useEffect } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useDocumentTitle } from '../hooks/useDocumentTitle.js'
import { actionIdFromPath, recordTherapistAction } from '../lib/therapistActions.js'

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

import { avatarSrc } from '../components/shared/AvatarUpload.jsx'

const PARENT_NAV = [
  { to: '/parent', label: 'Dashboard', end: true },
  { to: '/parent/session-logs', label: 'Session updates' },
  { to: '/parent/profile', label: 'My profile' },
  { to: '/parent/address', label: 'Service address' },
  { to: '/parent/book', label: 'Book appointment' },
  { to: '/parent/reports', label: 'Approved Reports' },
  { to: '/parent/iep', label: 'IEP Acknowledgement' },
  { to: '/parent/billing', label: 'Billing' },
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
  { to: '/admin/users', label: 'Users', perm: 'user.manage', feature: null, icon: '👤' },
  { to: '/admin/therapist-profiles', label: 'Therapist profiles', perm: 'user.manage', feature: null, icon: '🩺' },
]

export function PortalShell({ portal }) {
  const { user, logout, can, hasFeature } = useAuth()
  const location = useLocation()

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

  return (
    <div className={shellClass}>
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <span className="app-sidebar__logo" aria-hidden />
          <div>
            <h1 className="app-sidebar__title">InsightCase</h1>
            <p className="app-sidebar__sub">{subtitle}</p>
          </div>
        </div>
        <nav className="app-sidebar__nav">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                isActive ? 'app-sidebar__link is-active' : 'app-sidebar__link'
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
        <div className="app-sidebar__footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            {avatarSrc(user) ? (
              <img src={avatarSrc(user)} alt="" style={{ width: 32, height: 32, borderRadius: '50%', objectFit: 'cover' }} />
            ) : (
              <span style={{ width: 32, height: 32, borderRadius: '50%', background: '#6366f1', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700 }}>
                {user?.full_name?.charAt(0)?.toUpperCase() || '?'}
              </span>
            )}
            <p className="app-sidebar__help" style={{ margin: 0 }}>{user?.full_name}</p>
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
