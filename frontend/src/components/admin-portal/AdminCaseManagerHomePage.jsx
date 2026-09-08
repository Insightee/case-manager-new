import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { useAdminCmHome } from '../../hooks/useAdminCmHome.js'
import { apiFetch } from '../../lib/apiClient.js'
import { formatApiDateIN } from '../../lib/datetime.js'
import { UpcomingMeetingsPanel } from '../shared/UpcomingMeetingsPanel.jsx'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminStatCard, StatusBadge } from './ui/index.js'
import './admin-cm-home.css'
import './admin-dashboard.css'

const CM_WIDGET_META = {
  logs: { icon: '◫', tone: 'indigo', hint: 'Pending therapist logs', title: 'Session queue' },
  reports: { icon: '▣', tone: 'indigo', hint: 'Awaiting your review', title: 'Reports queue' },
  tickets: { icon: '✉', tone: 'slate', hint: 'Open support threads', title: 'Support tickets' },
  incidents: { icon: '⚠', tone: 'amber', hint: 'Active incident reports', title: 'Incidents' },
  observations: { icon: '☑', tone: 'teal', hint: 'Submitted checklists', title: 'Observations' },
  status_requests: { icon: '↔', tone: 'amber', hint: 'Pause or close requests', title: 'Status requests' },
  reschedules: { icon: '↻', tone: 'amber', hint: 'Therapist approval needed', title: 'Reschedules' },
  iep: { icon: '📋', tone: 'purple', hint: 'IEP attention needed', title: 'IEP' },
  meetings: { icon: '📅', tone: 'slate', hint: 'Upcoming CM meetings', title: 'Meetings' },
}

const PRIMARY_WIDGET_IDS = ['logs', 'reports', 'tickets']
const SECONDARY_WIDGET_IDS = ['incidents', 'observations', 'status_requests', 'reschedules', 'iep', 'meetings']

const WIDGET_FOOTER = {
  logs: '/admin/cm/logs',
  reports: '/admin/reports?tab=queue',
  tickets: '/admin/support?tab=tickets',
  incidents: '/admin/support?tab=incidents',
  observations: '/admin/workbench?section=observations',
  status_requests: '/admin/workbench?section=status_requests',
  reschedules: '/admin/workbench?section=reschedules',
  iep: '/admin/iep',
  meetings: '/admin/meetings',
}

function itemPrimary(item) {
  return item.child_name || item.label || item.subject || item.title || item.case_code || 'View item'
}

function itemSecondary(item) {
  if (item.resubmitted) return 'Resubmitted after changes'
  if (item.child_name && item.case_code) return item.case_code
  if (item.status) return String(item.status).replace(/_/g, ' ')
  return null
}

function CmWidgetCard({ id, section }) {
  const meta = CM_WIDGET_META[id] || { icon: '•', tone: 'slate', hint: '', title: id }
  const count = section?.count ?? 0
  const items = section?.items || []
  const href = WIDGET_FOOTER[id] || '/admin/workbench'
  const hasMore = count > items.length

  return (
    <article className={`admin-home-queue-card admin-home-queue-card--${meta.tone}`}>
      <header className="admin-home-queue-card__head">
        <span className="admin-home-queue-card__icon" aria-hidden>
          {meta.icon}
        </span>
        <div className="admin-home-queue-card__titles">
          <h3 className="admin-home-queue-card__title">{meta.title}</h3>
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
          <AdminEmptyState title="All clear" description="Nothing waiting in this queue." />
        ) : (
          <ul className="admin-home-queue-card__list">
            {items.slice(0, 5).map((item) => {
              const primary = itemPrimary(item)
              const secondary = itemSecondary(item)
              const to = item.href || href
              return (
                <li key={item.id || `${id}-${primary}`}>
                  <Link to={to} className="admin-home-queue-item">
                    <span className="admin-home-queue-item__main">{primary}</span>
                    {secondary ? <span className="admin-home-queue-item__meta">{secondary}</span> : null}
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
}

export function AdminCaseManagerHomePage() {
  const { user, can, isViewOnly } = useAuth()
  const { data, isLoading, error, refetch } = useAdminCmHome()
  const [pendingMeetings, setPendingMeetings] = useState([])

  useEffect(() => {
    apiFetch('/api/v1/meetings/pending-completion')
      .then((rows) => setPendingMeetings(Array.isArray(rows) ? rows : []))
      .catch(() => setPendingMeetings([]))
  }, [])

  const summary = data?.caseload_summary
  const sections = data?.sections || {}

  const primaryWidgets = PRIMARY_WIDGET_IDS
  const secondaryWidgets = useMemo(
    () => SECONDARY_WIDGET_IDS.filter((id) => sections[id]?.items?.length),
    [sections],
  )

  return (
    <div className="admin-page admin-cm-home admin-dashboard">
      <AdminPageHeader
        eyebrow="Case management"
        title="Dashboard"
        subtitle={`Good day${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''} — review queues first, then open cases when you need more context.`}
        actions={
          <div className="admin-btn-group">
            {can('case.create') && !isViewOnly ? (
              <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary admin-btn--sm">
                Allot case
              </Link>
            ) : null}
            <Link to="/admin/cases" className="admin-btn admin-btn--secondary admin-btn--sm">
              All cases
            </Link>
            <Link to="/admin/cm/therapists" className="admin-btn admin-btn--ghost admin-btn--sm">
              My therapists
            </Link>
          </div>
        }
      />

      {error ? (
        <p className="admin-alert admin-alert--error">
          {error.message || 'Could not load dashboard'}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginLeft: 8 }} onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : null}

      {isLoading ? (
        <p className="admin-muted">Loading dashboard…</p>
      ) : (
        <>
          <section className="admin-cm-stats" aria-label="Caseload summary">
            <AdminStatCard title="All cases" value={summary?.total ?? 0} tone="indigo" />
            <AdminStatCard title="Needs action" value={summary?.needs_action ?? 0} tone="yellow" />
            <AdminStatCard title="Pending allotment" value={summary?.pending_allotment ?? 0} tone="slate" />
            <AdminStatCard title="Active" value={summary?.active ?? 0} tone="teal" />
          </section>

          <UpcomingMeetingsPanel
            title="Upcoming meetings"
            subtitle="Next 7 days"
            href="/admin/meetings"
            variant="admin"
            className="admin-cm-home__upcoming-meetings"
          />

          <section className="admin-home-queue" aria-labelledby="admin-cm-queue-title">
            <div className="admin-home-queue__header">
              <div className="admin-home-queue__intro">
                <p className="admin-home-queue__eyebrow" id="admin-cm-queue-title">
                  Your work queues
                </p>
                <h2 className="admin-home-queue__title">
                  Case manager
                  <span className="admin-home-queue__role-pill">dashboard</span>
                </h2>
                <p className="admin-home-queue__sub">
                  Session logs, reports, and support — scoped to your assigned and mentored caseload.
                </p>
              </div>
              <Link to="/admin/cm/logs" className="admin-btn admin-btn--primary admin-home-queue__cta">
                Review session logs
              </Link>
            </div>

            <div className="admin-home-queue__grid">
              {primaryWidgets.map((id) => (
                <CmWidgetCard key={id} id={id} section={sections[id] || { count: 0, items: [] }} />
              ))}
            </div>
          </section>

          {secondaryWidgets.length > 0 ? (
            <section className="admin-cm-queues" aria-label="Additional queues">
              <h2 className="admin-cm-queues__title">More queues</h2>
              <div className="admin-home-queue__grid">
                {secondaryWidgets.map((id) => (
                  <CmWidgetCard key={id} id={id} section={sections[id]} />
                ))}
              </div>
            </section>
          ) : null}

          {pendingMeetings.length > 0 ? (
            <AdminPanel
              title="Meetings pending completion"
              subtitle="Scheduled meetings that passed without completion notes"
              padded={false}
            >
              <ul className="admin-cm-queue-list" style={{ margin: 0, padding: '8px 16px 16px', listStyle: 'none' }}>
                {pendingMeetings.slice(0, 8).map((m) => (
                  <li key={m.id} style={{ padding: '10px 0', borderBottom: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                      <div>
                        <p style={{ margin: 0, fontWeight: 600 }}>
                          {m.title || m.child_name || m.case_code || 'CM meeting'}
                        </p>
                        <p style={{ margin: '4px 0 0', fontSize: '0.8125rem', color: '#64748b' }}>
                          {formatApiDateIN(m.scheduled_date?.slice(0, 10))}
                          {m.scheduled_time ? ` · ${m.scheduled_time}` : ''}
                          {' · '}
                          <StatusBadge tone="amber">Overdue</StatusBadge>
                        </p>
                      </div>
                      <Link to="/admin/meetings" className="admin-btn admin-btn--secondary admin-btn--sm">
                        Mark completed
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            </AdminPanel>
          ) : null}

          {primaryWidgets.length === 0 && secondaryWidgets.length === 0 ? (
            <AdminPanel title="Queues">
              <p className="admin-muted">No pending reviews right now. Check back after therapists submit logs or reports.</p>
            </AdminPanel>
          ) : null}
        </>
      )}
    </div>
  )
}
