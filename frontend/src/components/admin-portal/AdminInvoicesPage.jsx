import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { AdminRoleQueueSection } from './AdminRoleQueueSection.jsx'
import { AdminMobilePillTabs, AdminPageHeader, PortalTabBar } from './ui/index.js'
import { AdminClientInvoicesTab } from './AdminClientInvoicesTab.jsx'
import { AdminClientPaymentsTab } from './AdminClientPaymentsTab.jsx'
import { AdminProductRulesTab } from './AdminProductRulesTab.jsx'
import { AdminSessionLedgerTab } from './AdminSessionLedgerTab.jsx'
import { AdminPackagesTab } from './AdminPackagesTab.jsx'
import { AdminDisputesTab } from './AdminDisputesTab.jsx'
import { AdminFinanceOverviewTab } from './AdminFinanceOverviewTab.jsx'
import { AdminFinanceReportsTab } from './AdminFinanceReportsTab.jsx'
import './admin-client-invoices.css'

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'client', label: 'Client invoices' },
  { id: 'payments', label: 'Client payments' },
  { id: 'rules', label: 'Rules & packages' },
  { id: 'ledger', label: 'Session ledger' },
  { id: 'reports', label: 'Reports' },
  { id: 'disputes', label: 'Disputes' },
]

const MOBILE_TAB_LABELS = {
  overview: 'Overview',
  client: 'Invoices',
  payments: 'Payments',
  rules: 'Rules',
  ledger: 'Ledger',
  reports: 'Reports',
  disputes: 'Disputes',
}

const FINANCE_PRIMARY_TABS = ['overview', 'client', 'payments', 'disputes']
const FINANCE_OVERFLOW_TABS = ['rules', 'ledger', 'reports']

function financeWidgetFooter(widget) {
  const map = {
    billing: '/admin/invoices/compose?queue=not_invoiced_this_month',
    client_claims: '/admin/invoices?tab=payments',
  }
  return map[widget.id] || '/admin/invoices/compose?queue=not_invoiced_this_month'
}

export function AdminInvoicesPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { data: roleHome, isLoading: roleHomeLoading } = useAdminHome()
  const isFinanceHome = roleHome?.role === 'FINANCE' || roleHome?.dashboard_variant === 'finance'
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') || (isFinanceHome ? 'overview' : 'client')
  const [claimsPending, setClaimsPending] = useState(0)
  const onComposeRoute = location.pathname.includes('/invoices/compose')

  useEffect(() => {
    if (tabParam !== 'therapist') return
    const next = new URLSearchParams()
    const sub = searchParams.get('therapist_sub') || 'dashboard'
    next.set('sub', sub === 'payouts' ? 'payouts' : 'dashboard')
    const status = searchParams.get('status')
    if (status) next.set('status', status)
    // #region agent log
    fetch('http://127.0.0.1:7284/ingest/6bb4b18a-59b3-4583-8388-f541aa2607d1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '3264f0' },
      body: JSON.stringify({
        sessionId: '3264f0',
        hypothesisId: 'A',
        location: 'AdminInvoicesPage.jsx:redirect',
        message: 'legacy tab=therapist redirect',
        data: { sub: next.get('sub'), status: next.get('status') },
        timestamp: Date.now(),
        runId: 'browser',
      }),
    }).catch(() => {})
    // #endregion
    navigate(`/admin/therapist-payouts?${next.toString()}`, { replace: true })
  }, [tabParam, searchParams, navigate])

  const activeTab = TABS.some((t) => t.id === tabParam) ? tabParam : 'client'

  useEffect(() => {
    apiFetch('/api/v1/admin/dashboard/summary')
      .then((s) => setClaimsPending(s?.client_payments_pending_review ?? 0))
      .catch(() => setClaimsPending(0))
  }, [activeTab])

  function setTab(tab) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    if (tab !== 'client' && tab !== 'payments') next.delete('invoiceId')
    if (tab === 'payments') next.set('claims', 'pending')
    else next.delete('claims')
    next.delete('therapist_sub')
    setSearchParams(next)
  }

  const rulesSubTab = searchParams.get('rules') || 'products'

  if (tabParam === 'therapist') {
    return null
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title={isFinanceHome ? 'Finance home' : 'Billing & invoices'}
        subtitle={
          isFinanceHome
            ? 'Client billing, payments, ledger, and reports. Therapist payouts live in the sidebar.'
            : 'Ledger-first client billing with finance review before invoices are sent.'
        }
      />

      {isFinanceHome ? (
        <AdminRoleQueueSection
          roleHome={roleHome}
          loading={roleHomeLoading}
          widgetFooter={financeWidgetFooter}
          landingHref={onComposeRoute ? null : '/admin/invoices/compose?queue=not_invoiced_this_month'}
          landingLabel="Open billing composer"
        />
      ) : null}

      {claimsPending > 0 && activeTab !== 'payments' ? (
        <div className="admin-alert admin-alert--warning" style={{ marginBottom: 16 }}>
          <strong>{claimsPending} client payment claim{claimsPending === 1 ? '' : 's'}</strong> awaiting review.{' '}
          <Link to="/admin/invoices?tab=payments">Review payments →</Link>
        </div>
      ) : null}

      <PortalTabBar
        className="admin-page__tabs-scroll admin-desktop-only"
        ariaLabel="Billing sections"
        activeId={activeTab}
        onChange={setTab}
        tabs={TABS.map((t) => ({
          id: t.id,
          label: t.label,
          badge:
            t.id === 'payments' && claimsPending > 0 ? String(claimsPending) : undefined,
        }))}
      />

      <AdminMobilePillTabs
        ariaLabel="Billing sections"
        activeId={activeTab}
        onChange={setTab}
        primaryIds={FINANCE_PRIMARY_TABS}
        overflowIds={FINANCE_OVERFLOW_TABS}
        tabs={TABS.map((t) => ({
          id: t.id,
          label: MOBILE_TAB_LABELS[t.id] || t.label,
          badge:
            t.id === 'payments' && claimsPending > 0 ? String(claimsPending) : undefined,
        }))}
      />

      {activeTab === 'overview' ? <AdminFinanceOverviewTab /> : null}
      {activeTab === 'client' ? (
        <AdminClientInvoicesTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'payments' ? (
        <AdminClientPaymentsTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'ledger' ? <AdminSessionLedgerTab /> : null}
      {activeTab === 'rules' ? (
        <div>
          <PortalTabBar
            ariaLabel="Rules subsections"
            activeId={rulesSubTab}
            onChange={(id) => {
              const next = new URLSearchParams(searchParams)
              next.set('tab', 'rules')
              next.set('rules', id)
              setSearchParams(next)
            }}
            tabs={[
              { id: 'products', label: 'Products & rules' },
              { id: 'packages', label: 'Packages' },
            ]}
          />
          {rulesSubTab === 'packages' ? <AdminPackagesTab /> : <AdminProductRulesTab />}
        </div>
      ) : null}
      {activeTab === 'reports' ? <AdminFinanceReportsTab /> : null}
      {activeTab === 'disputes' ? <AdminDisputesTab /> : null}
    </div>
  )
}
