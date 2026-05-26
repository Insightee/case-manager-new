import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAdminHome } from '../../hooks/useAdminHome.js'
import { AdminRoleQueueSection } from './AdminRoleQueueSection.jsx'
import { AdminPageHeader } from './ui/index.js'
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

      <div className="sessions-dash__tabs" style={{ marginBottom: 12, flexWrap: 'wrap' }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`sessions-dash__tab ${activeTab === t.id ? 'is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
            {t.id === 'claims' && claimsPending > 0 ? ` (${claimsPending})` : null}
            {t.id === 'client' && claimsPending > 0 && activeTab !== 'claims' ? ' ·' : null}
          </button>
        ))}
      </div>

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
