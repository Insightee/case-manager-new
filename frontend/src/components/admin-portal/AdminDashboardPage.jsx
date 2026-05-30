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
import { AdminRoleQueueSection } from './AdminRoleQueueSection.jsx'
import './admin-dashboard.css'

const DASHBOARD_COPY = {
  module_admin: {
    eyebrow: 'Programme operations',
    subtitle: 'Cross-module queues, billing, and case lifecycle — configured per your grants.',
  },
  legacy_admin: {
    eyebrow: 'Operations (legacy admin role)',
    subtitle: 'This account uses the retired ADMIN role. Prefer MODULE_ADMIN for new staff.',
  },
  operations: {
    eyebrow: 'Operations',
    subtitle: 'Case lifecycle, reviews, billing, and support — at a glance.',
  },
  hr: {
    eyebrow: 'People & HR',
    subtitle: 'Leave, therapist records, memos, and your support items — at a glance.',
  },
}

export function AdminDashboardPage({ dashboardVariant = 'operations', primaryRole }) {
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
  const { data: roleHome, isLoading: roleHomeLoading } = useAdminHome()
  const role = primaryRole || roleHome?.role || user?.roles?.[0]
  const copy = DASHBOARD_COPY[dashboardVariant] || DASHBOARD_COPY.operations

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
      leave: '/admin/leave',
      memos: '/admin/memos',
      therapist_hr: '/admin/therapist-profiles',
      people: '/admin/people',
      hr_reports: '/admin/hr-reports',
      observations: '/admin/workbench?section=observations',
      status_requests: '/admin/workbench?section=status_requests',
      client_claims: '/admin/invoices?tab=client&claims=pending',
    }
    return map[w.id] || w.section?.href || '/admin/workbench'
  }

  return (
    <div className="admin-page admin-dashboard">
      {dashboardVariant === 'legacy_admin' ? (
        <p className="admin-alert admin-alert--warning" style={{ marginBottom: 16 }}>
          Legacy ADMIN role detected. New staff should use <strong>Module Admin</strong> with programme grants in People → Staff.
        </p>
      ) : null}

      <AdminPageHeader
        eyebrow={copy.eyebrow}
        title={`Welcome back${user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}`}
        subtitle={copy.subtitle}
        actions={
          canNavigate ? (
            <div className="admin-btn-group">
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

      {roleHome?.alerts?.length ? (
        <section className="admin-home-alerts" aria-label="Alerts">
          {roleHome.alerts.map((alert) => (
            <Link
              key={alert.id}
              to={alert.href || '/admin/workbench'}
              className={`admin-alert admin-alert--${alert.severity || 'warning'}`}
            >
              <strong>{alert.title}</strong>
              {alert.message ? <span> — {alert.message}</span> : null}
            </Link>
          ))}
        </section>
      ) : null}

      <AdminRoleQueueSection
        roleHome={roleHome}
        loading={roleHomeLoading}
        widgetFooter={widgetFooter}
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
                      <Link to="/admin/therapist-payouts?sub=payouts" className="admin-btn admin-btn--ghost admin-btn--sm">
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
