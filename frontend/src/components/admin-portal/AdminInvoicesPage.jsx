import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { AdminRoleQueueSection } from './AdminRoleQueueSection.jsx'
import { AdminMobilePillTabs, AdminPageHeader, PortalTabBar } from './ui/index.js'
import { AdminClientInvoicesTab } from './AdminClientInvoicesTab.jsx'
import { AdminProductRulesTab } from './AdminProductRulesTab.jsx'
import { AdminSessionLedgerTab } from './AdminSessionLedgerTab.jsx'
import { AdminPackagesTab } from './AdminPackagesTab.jsx'
import { AdminDisputesTab } from './AdminDisputesTab.jsx'
import { TherapistPayoutsTab } from './TherapistPayoutsTab.jsx'
import './admin-client-invoices.css'

const TABS = [
  { id: 'client', label: 'Client invoices' },
  { id: 'therapist', label: 'Therapist payouts' },
  { id: 'ledger', label: 'Session ledger' },
  { id: 'products', label: 'Products & rules' },
  { id: 'packages', label: 'Packages' },
  { id: 'claims', label: 'Payment claims' },
  { id: 'disputes', label: 'Disputes' },
]

const MOBILE_TAB_LABELS = {
  client: 'Invoices',
  therapist: 'Payouts',
  ledger: 'Ledger',
  products: 'Products & rules',
  packages: 'Packages',
  claims: 'Claims',
  disputes: 'Disputes',
}

const FINANCE_PRIMARY_TABS = ['client', 'therapist', 'ledger', 'claims', 'disputes']
const FINANCE_OVERFLOW_TABS = ['products', 'packages']

function financeWidgetFooter(widget) {
  const map = {
    billing: '/admin/invoices?tab=therapist',
    client_claims: '/admin/invoices?tab=claims',
  }
  return map[widget.id] || '/admin/invoices'
}

export function AdminInvoicesPage() {
  const { data: roleHome, isLoading: roleHomeLoading } = useAdminHome()
  const isFinanceHome = roleHome?.role === 'FINANCE' || roleHome?.dashboard_variant === 'finance'
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') || 'client'
  const activeTab = TABS.some((t) => t.id === tabParam) ? tabParam : 'client'
  const [claimsPending, setClaimsPending] = useState(0)

  useEffect(() => {
    apiFetch('/api/v1/admin/dashboard/summary')
      .then((s) => setClaimsPending(s?.client_payments_pending_review ?? 0))
      .catch(() => setClaimsPending(0))
  }, [])

  function setTab(tab) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    if (tab === 'claims') {
      next.set('claims', 'pending')
    } else if (tab !== 'client') {
      next.delete('claims')
    }
    if (tab !== 'client') next.delete('invoiceId')
    setSearchParams(next)
  }

  const highlightClaims = activeTab === 'claims' || searchParams.get('claims') === 'pending'

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title={isFinanceHome ? 'Finance home' : 'Billing & invoices'}
        subtitle={
          isFinanceHome
            ? 'Client ledger, invoices, packages, and therapist payouts in one hub.'
            : 'Ledger-first client billing with finance review before invoices are sent.'
        }
      />

      {isFinanceHome ? (
        <AdminRoleQueueSection
          roleHome={roleHome}
          loading={roleHomeLoading}
          widgetFooter={financeWidgetFooter}
        />
      ) : null}

      {claimsPending > 0 && activeTab !== 'claims' ? (
        <div className="admin-alert admin-alert--warning" style={{ marginBottom: 16 }}>
          <strong>{claimsPending} client payment claim{claimsPending === 1 ? '' : 's'}</strong> awaiting review.{' '}
          <Link to="/admin/invoices?tab=claims">Review payment claims →</Link>
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
            t.id === 'claims' && claimsPending > 0
              ? String(claimsPending)
              : undefined,
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
            t.id === 'claims' && claimsPending > 0
              ? String(claimsPending)
              : undefined,
        }))}
      />

      {activeTab === 'client' ? (
        <AdminClientInvoicesTab
          highlightClaimsPending={highlightClaims && activeTab === 'client'}
          openInvoiceId={searchParams.get('invoiceId')}
        />
      ) : null}
      {activeTab === 'therapist' ? <TherapistPayoutsTab /> : null}
      {activeTab === 'ledger' ? <AdminSessionLedgerTab /> : null}
      {activeTab === 'products' ? <AdminProductRulesTab /> : null}
      {activeTab === 'packages' ? <AdminPackagesTab /> : null}
      {activeTab === 'claims' ? (
        <AdminClientInvoicesTab highlightClaimsPending claimsOnly openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'disputes' ? <AdminDisputesTab /> : null}
    </div>
  )
}
