import { Link } from 'react-router-dom'
import { AdminEmptyState } from './ui/index.js'

const WIDGET_META = {
  logs: { icon: '◫', tone: 'indigo', hint: 'Pending therapist logs' },
  reports: { icon: '▣', tone: 'indigo', hint: 'Awaiting your review' },
  observations: { icon: '☑', tone: 'teal', hint: 'Submitted checklists' },
  reschedules: { icon: '↻', tone: 'amber', hint: 'Therapist approval needed' },
  status_requests: { icon: '↔', tone: 'amber', hint: 'Pause or close requests' },
  billing: { icon: '₹', tone: 'rose', hint: 'Invoices & payouts' },
  client_claims: { icon: '◎', tone: 'rose', hint: 'Payment verification' },
  tickets: { icon: '✉', tone: 'slate', hint: 'Open support threads' },
}

const ROLE_LABELS = {
  SUPER_ADMIN: 'Super admin',
  MODULE_ADMIN: 'Module admin',
  ADMIN: 'Operations admin',
  CASE_MANAGER: 'Case manager',
  SUPERVISOR: 'Supervisor',
  FINANCE: 'Finance',
  HR: 'HR',
  VIEWER: 'View only',
}

function formatRole(role) {
  if (!role) return 'Admin'
  return ROLE_LABELS[role] || role.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function itemPrimary(item) {
  return item.child_name || item.label || item.subject || item.case_code || 'View item'
}

function itemSecondary(item) {
  if (item.child_name && item.case_code) return item.case_code
  if (item.label && item.case_code) return item.case_code
  if (item.status) return String(item.status).replace(/_/g, ' ')
  return null
}

function widgetHref(widget, widgetFooter) {
  return widgetFooter(widget)
}

export function AdminRoleQueueSection({ roleHome, loading, widgetFooter }) {
  if (loading) {
    return (
      <section className="admin-home-queue" aria-busy="true" aria-label="Loading your queues">
        <div className="admin-home-queue__header">
          <div className="admin-skeleton" style={{ height: 48, borderRadius: 12, maxWidth: 420 }} />
        </div>
        <div className="admin-home-queue__grid">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className="admin-skeleton" style={{ height: 200, borderRadius: 14 }} />
          ))}
        </div>
      </section>
    )
  }

  if (!roleHome?.widgets?.length) return null

  const landing = roleHome.landing_route && roleHome.landing_route !== '/admin' ? roleHome.landing_route : null

  return (
    <section className="admin-home-queue" aria-labelledby="admin-home-queue-title">
      <div className="admin-home-queue__header">
        <div className="admin-home-queue__intro">
          <p className="admin-home-queue__eyebrow" id="admin-home-queue-title">
            Your work queues
          </p>
          <h2 className="admin-home-queue__title">
            {formatRole(roleHome.role)}
            <span className="admin-home-queue__role-pill">{roleHome.role?.replace(/_/g, ' ')}</span>
          </h2>
          <p className="admin-home-queue__sub">
            Prioritized items for your role — open a case or jump to the full queue.
          </p>
        </div>
        {landing ? (
          <Link to={landing} className="admin-btn admin-btn--primary admin-home-queue__cta">
            {landing === '/admin/cm' ? 'Open my caseload' : 'Open workbench'}
          </Link>
        ) : null}
      </div>

      <div className="admin-home-queue__grid">
        {roleHome.widgets.map((widget) => {
          const meta = WIDGET_META[widget.id] || { icon: '•', tone: 'slate', hint: '' }
          const count = widget.section?.count ?? 0
          const items = widget.section?.items ?? []
          const href = widgetHref(widget, widgetFooter)
          const hasMore = count > items.length

          return (
            <article
              key={widget.id}
              className={`admin-home-queue-card admin-home-queue-card--${meta.tone}`}
            >
              <header className="admin-home-queue-card__head">
                <span className="admin-home-queue-card__icon" aria-hidden>
                  {meta.icon}
                </span>
                <div className="admin-home-queue-card__titles">
                  <h3 className="admin-home-queue-card__title">{widget.title}</h3>
                  {meta.hint ? <p className="admin-home-queue-card__hint">{meta.hint}</p> : null}
                </div>
                <span
                  className={`admin-home-queue-card__count${count === 0 ? ' admin-home-queue-card__count--zero' : ''}`}
                  aria-label={`${count} in queue`}
                >
                  {count}
                </span>
              </header>

              <div className="admin-home-queue-card__body">
                {items.length === 0 ? (
                  <AdminEmptyState
                    title="All clear"
                    description="Nothing waiting in this queue."
                  />
                ) : (
                  <ul className="admin-home-queue-card__list">
                    {items.slice(0, 5).map((item) => {
                      const primary = itemPrimary(item)
                      const secondary = itemSecondary(item)
                      const to = item.href || href
                      return (
                        <li key={item.id || `${widget.id}-${primary}`}>
                          <Link to={to} className="admin-home-queue-item">
                            <span className="admin-home-queue-item__main">{primary}</span>
                            {secondary ? (
                              <span className="admin-home-queue-item__meta">{secondary}</span>
                            ) : null}
                          </Link>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>

              <footer className="admin-home-queue-card__foot">
                <Link to={href} className="admin-home-queue-card__link">
                  {hasMore ? `View all ${count}` : 'Open queue'}
                  <span aria-hidden> →</span>
                </Link>
              </footer>
            </article>
          )
        })}
      </div>
    </section>
  )
}
