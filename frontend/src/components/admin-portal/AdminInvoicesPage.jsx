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
import { AdminReceivablesTab } from './AdminReceivablesTab.jsx'
import { AdminFinanceOverviewTab } from './AdminFinanceOverviewTab.jsx'
import { FinanceMondayBrief } from './TherapistPayoutFinance.jsx'
import { AdminFinanceReportsTab } from './AdminFinanceReportsTab.jsx'
import './admin-client-invoices.css'
import '../../styles/billing-readiness-master-sheet.css'

const PRIMARY_TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'client', label: 'Client invoices' },
  { id: 'payments', label: 'Client payments' },
  { id: 'receivables', label: 'Receivables' },
  { id: 'disputes', label: 'Disputes' },
]

const MOBILE_TAB_LABELS = {
  overview: 'Overview',
  client: 'Invoices',
  payments: 'Payments',
  receivables: 'Receivables',
  disputes: 'Disputes',
}

const FINANCE_PRIMARY_TABS = ['overview', 'client', 'payments', 'receivables', 'disputes']

const LEGACY_TAB_REDIRECTS = {
  rules: { tab: 'client', sub: 'rules' },
  ledger: { tab: 'client', sub: 'ledger' },
  reports: { tab: 'client', sub: 'reports' },
}

const BILLING_TOOLS = [
  { id: 'invoices', label: 'Invoices' },
  { id: 'rules', label: 'Rules & packages' },
  { id: 'ledger', label: 'Session ledger' },
  { id: 'reports', label: 'Reports' },
]

const PAYMENT_TOOLS = [
  { id: 'payments', label: 'Payments' },
  { id: 'rules', label: 'Rules & packages' },
  { id: 'ledger', label: 'Session ledger' },
  { id: 'reports', label: 'Reports' },
]

function defaultBillingSub(parentTab) {
  return parentTab === 'payments' ? 'payments' : 'invoices'
}

function financeWidgetFooter(widget) {
  const map = {
    billing: '/admin/invoices/compose?queue=not_invoiced_this_month',
    client_claims: '/admin/invoices?tab=payments',
  }
  return map[widget.id] || '/admin/invoices/compose?queue=not_invoiced_this_month'
}

function FinanceInlineNav({ tools, activeId, onChange }) {
  return (
    <nav className="admin-finance-inline-nav" aria-label="Invoices and payments tools">
      {tools.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`admin-finance-inline-nav__link${activeId === t.id ? ' is-active' : ''}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
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
    const legacy = LEGACY_TAB_REDIRECTS[tabParam]
    if (!legacy) return
    const next = new URLSearchParams(searchParams)
    next.set('tab', legacy.tab)
    next.set('sub', legacy.sub)
    setSearchParams(next, { replace: true })
  }, [tabParam, searchParams, setSearchParams])

  useEffect(() => {
    if (tabParam !== 'therapist') return
    const next = new URLSearchParams()
    const sub = searchParams.get('therapist_sub') || 'dashboard'
    next.set('sub', sub === 'payouts' ? 'payouts' : 'dashboard')
    const status = searchParams.get('status')
    if (status) next.set('status', status)
    navigate(`/admin/therapist-payouts?${next.toString()}`, { replace: true })
  }, [tabParam, searchParams, navigate])

  const activeTab = PRIMARY_TABS.some((t) => t.id === tabParam) ? tabParam : 'client'
  const isBillingArea = activeTab === 'client' || activeTab === 'payments'
  const billingSub = isBillingArea
    ? searchParams.get('sub') || defaultBillingSub(activeTab)
    : null
  const billingTools = activeTab === 'payments' ? PAYMENT_TOOLS : BILLING_TOOLS
  const billingMainSub = defaultBillingSub(activeTab)

  useEffect(() => {
    apiFetch('/api/v1/admin/dashboard/summary')
      .then((s) => setClaimsPending(s?.client_payments_pending_review ?? 0))
      .catch(() => setClaimsPending(0))
  }, [activeTab])

  function setTab(tab) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    next.delete('sub')
    if (tab !== 'client' && tab !== 'payments') next.delete('invoiceId')
    if (tab === 'payments') next.set('claims', 'pending')
    else next.delete('claims')
    next.delete('therapist_sub')
    setSearchParams(next)
  }

  function setBillingSub(sub) {
    const next = new URLSearchParams(searchParams)
    next.set('sub', sub)
    const mainSub = defaultBillingSub(activeTab)
    if (sub === mainSub) {
      next.delete('sub')
      if (activeTab === 'payments') next.set('claims', 'pending')
    } else {
      next.delete('invoiceId')
      next.delete('claims')
    }
    setSearchParams(next)
  }

  const rulesSubTab = searchParams.get('rules') || 'products'

  if (tabParam === 'therapist') {
    return null
  }

  return (
    <div className="admin-page admin-page--finance">
      <AdminPageHeader
        eyebrow="Finance"
        title={isFinanceHome ? 'Finance home' : 'Billing & invoices'}
        subtitle={
          isFinanceHome
            ? 'Client billing, payments, and ledger. Finance reports and therapist payouts are in the sidebar.'
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
        className="admin-page__tabs-scroll admin-page__tabs--single admin-desktop-only"
        ariaLabel="Billing sections"
        activeId={activeTab}
        onChange={setTab}
        tabs={PRIMARY_TABS.map((t) => ({
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
        overflowIds={[]}
        tabs={PRIMARY_TABS.map((t) => ({
          id: t.id,
          label: MOBILE_TAB_LABELS[t.id] || t.label,
          badge:
            t.id === 'payments' && claimsPending > 0 ? String(claimsPending) : undefined,
        }))}
      />

      {isBillingArea ? (
        <FinanceInlineNav tools={billingTools} activeId={billingSub} onChange={setBillingSub} />
      ) : null}

      {activeTab === 'overview' ? (
        <>
          <FinanceMondayBrief />
          <AdminFinanceOverviewTab />
        </>
      ) : null}
      {activeTab === 'receivables' ? (
        <AdminReceivablesTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'client' && billingSub === 'invoices' ? (
        <AdminClientInvoicesTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'payments' && billingSub === 'payments' ? (
        <AdminClientPaymentsTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {isBillingArea && billingSub === 'ledger' ? <AdminSessionLedgerTab /> : null}
      {isBillingArea && billingSub === 'rules' ? (
        <div>
          <PortalTabBar
            ariaLabel="Rules subsections"
            activeId={rulesSubTab}
            onChange={(id) => {
              const next = new URLSearchParams(searchParams)
              next.set('sub', 'rules')
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
      {isBillingArea && billingSub === 'reports' ? <AdminFinanceReportsTab /> : null}
      {activeTab === 'disputes' ? <AdminDisputesTab /> : null}
    </div>
  )
}
