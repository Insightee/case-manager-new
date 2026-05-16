const THERAPIST_NAV = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'cases', label: 'My Cases' },
  { key: 'logs', label: 'Daily Logs' },
  { key: 'reports', label: 'Monthly Reports' },
  { key: 'invoices', label: 'Invoices' },
  { key: 'notifications', label: 'Notifications' },
  { key: 'settings', label: 'Settings' },
]

const PARENT_NAV = [
  { key: 'client-dashboard', label: 'Dashboard' },
  { key: 'client-reports', label: 'Approved Reports' },
  { key: 'client-iep', label: 'IEP Acknowledgement' },
  { key: 'client-billing', label: 'Billing Snapshot' },
  { key: 'client-support', label: 'Support' },
]

export function Sidebar({ activePage, onNavigate, role = 'therapist', onLogout }) {
  const isParent = role === 'parent'
  const navItems = isParent ? PARENT_NAV : THERAPIST_NAV

  return (
    <aside className="app-sidebar">
      <div className="app-sidebar__brand">
        <span className="app-sidebar__logo" aria-hidden />
        <div>
          <h1 className="app-sidebar__title">InsightCase</h1>
          <p className="app-sidebar__sub">{isParent ? 'Client Portal' : 'Therapist Portal'}</p>
        </div>
      </div>

      <nav className="app-sidebar__nav" aria-label="Main navigation">
        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            className={item.key === activePage ? 'app-sidebar__link is-active' : 'app-sidebar__link'}
            onClick={() => onNavigate(item.key)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="app-sidebar__footer">
        <p className="app-sidebar__help">Need help?</p>
        <button type="button" className="app-sidebar__cta">
          {isParent ? 'Contact Support Team' : 'Contact Case Manager'}
        </button>
        {onLogout ? (
          <button type="button" className="app-sidebar__logout" onClick={onLogout}>
            Logout
          </button>
        ) : null}
      </div>
    </aside>
  )
}
