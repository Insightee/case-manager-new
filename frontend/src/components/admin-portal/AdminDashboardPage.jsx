import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { AdminOpsKpiGrid, buildAdminKpis } from './AdminOpsKpiGrid.jsx'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'

export function AdminDashboardPage() {
  const { user, can } = useAuth()
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('/api/v1/admin/dashboard/summary')
      .then((data) => {
        setSummary(data)
        setError('')
      })
      .catch((err) => {
        setSummary(null)
        setError(err.message || 'Could not load dashboard')
      })
      .finally(() => setLoading(false))
  }, [])

  const breakdown = summary?.status_breakdown ?? {}
  const totalForBars = useMemo(() => {
    const vals = Object.values(breakdown)
    return Math.max(vals.reduce((a, b) => a + b, 0), 1)
  }, [breakdown])

  const canNavigate = can('case.read.all') || can('case.read.team')
  const { data: roleHome } = useAdminHome()
  const role = roleHome?.role || user?.roles?.[0]

  const kpis = useMemo(
    () => buildAdminKpis({ summary, role, canNavigate, can }),
    [summary, role, canNavigate, can],
  )

  const widgetFooter = (w) => {
    const map = {
      billing: '/admin/invoices',
      reschedules: '/admin/workbench?section=reschedules',
      reports: '/admin/reports?tab=queue',
      logs: '/admin/workbench?section=logs',
      tickets: '/admin/support?tab=tickets',
      observations: '/admin/workbench?section=observations',
      status_requests: '/admin/workbench?section=status_requests',
      client_claims: '/admin/invoices?tab=client&claims=pending',
    }
    return map[w.id] || w.section?.href || '/admin/workbench'
  }

  return (
    <div className="admin-page">
      {roleHome?.alerts?.length ? (
        <section className="admin-alerts-strip" style={{ marginBottom: 16 }}>
          {roleHome.alerts.map((alert) => (
            <Link
              key={alert.id}
              to={alert.href || '/admin/workbench'}
              className={`admin-alert admin-alert--${alert.severity || 'warning'}`}
              style={{ display: 'block', marginBottom: 8, textDecoration: 'none' }}
            >
              <strong>{alert.title}</strong>
              {alert.message ? ` — ${alert.message}` : ''}
            </Link>
          ))}
        </section>
      ) : null}

      {roleHome?.widgets?.length ? (
        <section className="admin-role-widgets" style={{ marginBottom: 24 }}>
          <p className="admin-page__eyebrow">Your queue · {roleHome.role?.replace('_', ' ')}</p>
          <div className="admin-role-widgets__grid">
            {roleHome.widgets.map((w) => (
              <AdminPanel key={w.id} title={w.title}>
                {w.section?.items?.length ? (
                  <ul className="admin-queue-list">
                    {w.section.items.slice(0, 5).map((item) => (
                      <li key={item.id || item.href}>
                        <Link to={item.href || '/admin'}>
                          {item.child_name || item.label || item.case_code}
                          {item.case_code ? ` · ${item.case_code}` : ''}
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <AdminEmptyState message="Nothing in this queue right now." />
                )}
                {w.section?.count > 5 ? (
                  <Link to={widgetFooter(w)} className="admin-btn admin-btn--ghost admin-btn--sm">
                    View all ({w.section.count})
                  </Link>
                ) : null}
              </AdminPanel>
            ))}
          </div>
          {roleHome.landing_route && roleHome.landing_route !== '/admin' ? (
            <p style={{ marginTop: 12, fontSize: '0.875rem' }}>
              <Link to={roleHome.landing_route}>Go to your primary workspace →</Link>
            </p>
          ) : null}
        </section>
      ) : null}

      <AdminPageHeader
        eyebrow="Operations"
        title={`Welcome back${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        subtitle="Case lifecycle, reviews, billing, and support — at a glance."
        actions={
          canNavigate ? (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {can('case.create') ? (
                <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary">
                  Allot new case
                </Link>
              ) : null}
              <Link to="/admin/cases" className="admin-btn admin-btn--secondary">
                Manage cases
              </Link>
            </div>
          ) : null
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      <AdminOpsKpiGrid kpis={kpis} loading={loading} />

      <div className="admin-layout">
        <div className="admin-layout admin-layout--stack" style={{ gap: 16 }}>
          <AdminPanel
            title="Pending allotment"
            subtitle="Cases waiting for therapist assignment"
            actions={
              canNavigate ? (
                <Link to="/admin/cases?status=PENDING_ALLOTMENT" className="admin-btn admin-btn--ghost admin-btn--sm">
                  View all
                </Link>
              ) : null
            }
          >
            {!loading && (summary?.pending_allotment_queue?.length ?? 0) === 0 ? (
              <AdminEmptyState title="Queue clear" description="No cases pending allotment right now." />
            ) : (
              <ul className="admin-queue">
                {(summary?.pending_allotment_queue ?? []).map((c) => (
                  <li key={c.id} className="admin-queue__item">
                    <div>
                      <p className="admin-queue__title">{c.child_name}</p>
                      <p className="admin-queue__meta">
                        {c.case_code} · {c.service_type}
                      </p>
                    </div>
                    <div className="admin-btn-group">
                      <StatusBadge status={c.status} />
                      <Link to={`/admin/cases/${c.id}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                        Open case
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </AdminPanel>

          <AdminPanel title="Reports awaiting review" subtitle="Approve to publish for parents">
            {!loading && (summary?.reports_queue?.length ?? 0) === 0 ? (
              <AdminEmptyState title="No reports in queue" description="All monthly reports are processed." />
            ) : (
              <ul className="admin-queue">
                {(summary?.reports_queue ?? []).map((r) => (
                  <li key={r.id} className="admin-queue__item">
                    <div>
                      <p className="admin-queue__title">
                        {r.child_name} — {r.month}
                      </p>
                      <p className="admin-queue__meta">{r.case_code}</p>
                    </div>
                    <div className="admin-btn-group">
                      <Link to="/admin/reports" className="admin-btn admin-btn--ghost admin-btn--sm">
                        Review
                      </Link>
                      {r.case_id ? (
                        <Link to={`/admin/cases/${r.case_id}?tab=reports`} className="admin-btn admin-btn--ghost admin-btn--sm">
                          Case
                        </Link>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </AdminPanel>
        </div>

        <div className="admin-layout admin-layout--stack" style={{ gap: 16 }}>
          <AdminPanel title="Case status mix" subtitle="Distribution across lifecycle">
            <div className="admin-breakdown">
              {[
                ['Active', breakdown.ACTIVE, 0],
                ['Pending', breakdown.PENDING_ALLOTMENT, 1],
                ['Suspended', breakdown.SUSPENDED, 2],
                ['Closed', breakdown.CLOSED, 3],
              ].map(([label, count]) => (
                <div key={label} className="admin-breakdown__row">
                  <span className="admin-breakdown__label">{label}</span>
                  <div className="admin-breakdown__bar">
                    <div
                      className="admin-breakdown__fill"
                      style={{ width: `${((count || 0) / totalForBars) * 100}%` }}
                    />
                  </div>
                  <span className="admin-breakdown__value">{count ?? 0}</span>
                </div>
              ))}
            </div>
          </AdminPanel>

          <AdminPanel title="Invoices in review">
            {!loading && (summary?.invoices_queue?.length ?? 0) === 0 ? (
              <AdminEmptyState title="Billing clear" description="No invoices awaiting approval." />
            ) : (
              <ul className="admin-queue">
                {(summary?.invoices_queue ?? []).map((inv) => (
                  <li key={inv.id} className="admin-queue__item">
                    <div>
                      <p className="admin-queue__title">
                        Therapist #{inv.therapist_user_id} · {inv.month}
                      </p>
                      <p className="admin-queue__meta">{formatCurrency(inv.amount_inr)}</p>
                    </div>
                    <div className="admin-btn-group">
                      <StatusBadge status={inv.status} />
                      <Link to="/admin/invoices" className="admin-btn admin-btn--ghost admin-btn--sm">
                        Review
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </AdminPanel>

          <AdminPanel
            title="Open support tickets"
            actions={
              <Link to="/admin/tickets" className="admin-btn admin-btn--ghost admin-btn--sm">
                Tickets
              </Link>
            }
          >
            {!loading && (summary?.tickets_queue?.length ?? 0) === 0 ? (
              <AdminEmptyState title="No open tickets" description="Support queue is empty." />
            ) : (
              <ul className="admin-queue">
                {(summary?.tickets_queue ?? []).map((t) => (
                  <li key={t.id} className="admin-queue__item">
                    <div>
                      <p className="admin-queue__title">{t.subject}</p>
                      <p className="admin-queue__meta">
                        {t.product_module ? `${t.product_module} · ` : ''}#{t.id}
                      </p>
                    </div>
                    <StatusBadge status={t.status} />
                  </li>
                ))}
              </ul>
            )}
          </AdminPanel>
        </div>
      </div>
    </div>
  )
}
