import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

function formatSessionWhen(session) {
  if (!session?.session_date) return null
  const time = session.start_time || session.scheduled_start_time || ''
  try {
    const d = new Date(`${session.session_date}T${time || '12:00'}`)
    if (Number.isNaN(d.getTime())) return `${session.session_date}${time ? ` ${time}` : ''}`
    return d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })
  } catch {
    return `${session.session_date}${time ? ` ${time}` : ''}`
  }
}

export function AdminCaseDetailQuickStats({ caseId, caseRow, onNavigateTab, visibleTabIds = [] }) {
  const visible = new Set(visibleTabIds)
  const [stats, setStats] = useState({ loading: true, nextSession: null, pendingReports: null, billing: null })

  useEffect(() => {
    if (!caseId) return
    let cancelled = false
    async function load() {
      try {
        const [sessionsRes, monthly, observation, invoicesRes] = await Promise.all([
          apiFetch(`/api/v1/sessions?case_id=${caseId}&page_size=20`).catch(() => ({ items: [] })),
          apiFetch(`/api/v1/admin/reports/monthly?case_id=${caseId}&page_size=30`).catch(() => ({ items: [] })),
          apiFetch(`/api/v1/admin/reports/observation?case_id=${caseId}&page_size=30`).catch(() => ({ items: [] })),
          apiFetch(`/api/v1/admin/client-billing/invoices?case_id=${caseId}&page_size=10`).catch(() => []),
        ])
        if (cancelled) return

        const sessions = sessionsRes?.items || sessionsRes || []
        const today = new Date().toISOString().slice(0, 10)
        const upcoming = [...sessions]
          .filter((s) => s.session_date && s.session_date >= today && s.status !== 'CANCELLED')
          .sort((a, b) => `${a.session_date}${a.start_time || ''}`.localeCompare(`${b.session_date}${b.start_time || ''}`))
        const nextSession = upcoming[0] ? formatSessionWhen(upcoming[0]) : null

        const reports = [...(monthly.items || []), ...(observation.items || [])]
        const pendingReports = reports.filter(
          (r) => r.status === 'UNDER_REVIEW' || r.parent_review_status === 'CHANGES_REQUESTED',
        ).length

        const invoices = Array.isArray(invoicesRes) ? invoicesRes : invoicesRes?.items || []
        const open = invoices.filter((inv) =>
          ['DRAFT', 'SENT', 'PARTIALLY_PAID', 'OVERDUE', 'DISPUTED', 'IN_REVIEW'].includes(
            String(inv.status || '').toUpperCase(),
          ),
        )
        let billing = null
        if (open.length > 0) {
          billing = `${open.length} open invoice${open.length === 1 ? '' : 's'}`
        } else if (caseRow?.client_billing_mode) {
          billing = caseRow.client_billing_mode.replace(/_/g, ' ')
        }

        setStats({ loading: false, nextSession, pendingReports: pendingReports || null, billing })
      } catch {
        if (!cancelled) setStats({ loading: false, nextSession: null, pendingReports: null, billing: null })
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [caseId, caseRow?.client_billing_mode])

  const itemSlots = [
    visible.has('scheduling'),
    visible.has('reports'),
    visible.has('billing'),
  ].filter(Boolean).length

  if (itemSlots === 0) return null

  if (stats.loading) {
    return (
      <div className="admin-case-detail-stats admin-case-detail__mobile-only" aria-busy="true" aria-label="Loading case summary">
        {Array.from({ length: Math.min(itemSlots, 3) }, (_, i) => (
          <div key={i} className="admin-case-detail-stat admin-case-detail-stat--empty">
            <span className="admin-case-detail-stat__label">…</span>
            <span className="admin-case-detail-stat__value">—</span>
          </div>
        ))}
      </div>
    )
  }

  const items = [
    visible.has('scheduling')
      ? {
          key: 'session',
          label: 'Next session',
          value: stats.nextSession,
          empty: 'None scheduled',
          onClick: () => onNavigateTab('scheduling'),
        }
      : null,
    visible.has('reports')
      ? {
          key: 'reports',
          label: 'Pending reports',
          value: stats.pendingReports != null && stats.pendingReports > 0 ? String(stats.pendingReports) : null,
          empty: 'None pending',
          onClick: () => onNavigateTab('reports'),
        }
      : null,
    visible.has('billing')
      ? {
          key: 'billing',
          label: 'Billing',
          value: stats.billing,
          empty: 'Up to date',
          onClick: () => onNavigateTab('billing'),
        }
      : null,
  ].filter(Boolean)

  const anyData = items.some((it) => it.value)
  if (!anyData) return null

  return (
    <div className="admin-case-detail-stats admin-case-detail__mobile-only" role="group" aria-label="Case at a glance">
      {items.map((it) => (
        <button
          key={it.key}
          type="button"
          className={`admin-case-detail-stat${it.value ? '' : ' admin-case-detail-stat--empty'}`}
          onClick={it.onClick}
          aria-label={`${it.label}: ${it.value || it.empty}`}
        >
          <span className="admin-case-detail-stat__label">{it.label}</span>
          <span className="admin-case-detail-stat__value">{it.value || it.empty}</span>
        </button>
      ))}
    </div>
  )
}
