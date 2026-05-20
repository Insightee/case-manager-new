import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  AdminPageHeader,
  AdminStatCard,
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

  const kpis = [
    {
      title: 'Active cases',
      value: summary?.open_cases ?? '—',
      hint: `${summary?.total_cases ?? '—'} total in system`,
      tone: 'teal',
      icon: '◉',
      to: '/admin/cases',
    },
    {
      title: 'Pending allotment',
      value: summary?.pending_allotment ?? '—',
      hint: 'Needs therapist assignment',
      tone: 'amber',
      icon: '◎',
      to: can('case.create') ? '/admin/cases?allot=1' : '/admin/cases',
    },
    {
      title: 'Reports in review',
      value: summary?.reports_in_review ?? '—',
      hint: 'Awaiting approval',
      tone: 'indigo',
      icon: '▣',
      to: '/admin/reports',
    },
    {
      title: 'Invoices pending',
      value: summary?.invoices_pending ?? '—',
      hint: 'Finance queue',
      tone: 'rose',
      icon: '₹',
      to: '/admin/invoices',
    },
    {
      title: 'Open tickets',
      value: summary?.open_tickets ?? '—',
      hint: 'Support workload',
      tone: 'slate',
      icon: '✉',
      to: '/admin/tickets',
    },
    {
      title: 'Suspended',
      value: summary?.suspended_cases ?? '—',
      hint: `${summary?.closed_cases ?? '—'} closed`,
      tone: 'slate',
      icon: '⏸',
      to: '/admin/cases',
    },
  ]

  const canNavigate = can('case.read.all') || can('case.read.team')

  return (
    <div className="admin-page">
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

      <section className="admin-kpi-grid" aria-label="Key metrics">
        {loading
          ? Array.from({ length: 6 }).map((_, i) => <div key={i} className="admin-skeleton" />)
          : kpis.map((kpi) => (
              <AdminStatCard
                key={kpi.title}
                title={kpi.title}
                value={kpi.value}
                hint={kpi.hint}
                tone={kpi.tone}
                icon={kpi.icon}
                to={canNavigate ? kpi.to : undefined}
              />
            ))}
      </section>

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
