import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
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
import './admin-client-invoices.css'
import '../../styles/billing-readiness-master-sheet.css'

const PRIMARY_TABS = [
  { id: 'invoices', label: 'Invoices' },
  { id: 'payments', label: 'Payments' },
  { id: 'tools', label: 'Tools' },
]

const TOOL_SUBS = [
  { id: 'snapshot', label: 'Snapshot' },
  { id: 'ledger', label: 'Ledger' },
  { id: 'rules', label: 'Rules' },
  { id: 'disputes', label: 'Disputes' },
  { id: 'receivables', label: 'Receivables' },
]

const LEGACY_TAB_REDIRECTS = {
  client: { tab: 'invoices' },
  overview: { tab: 'tools', sub: 'snapshot' },
  receivables: { tab: 'tools', sub: 'receivables' },
  disputes: { tab: 'tools', sub: 'disputes' },
  rules: { tab: 'tools', sub: 'rules' },
  ledger: { tab: 'tools', sub: 'ledger' },
  reports: { tab: 'tools', sub: 'snapshot' },
}

export function AdminInvoicesPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab') || 'invoices'
  const [claimsPending, setClaimsPending] = useState(0)

  useEffect(() => {
    const legacy = LEGACY_TAB_REDIRECTS[tabParam]
    if (!legacy) return
    const next = new URLSearchParams(searchParams)
    next.set('tab', legacy.tab)
    if (legacy.sub) next.set('sub', legacy.sub)
    else next.delete('sub')
    setSearchParams(next, { replace: true })
  }, [tabParam, searchParams, setSearchParams])

  useEffect(() => {
    if (tabParam !== 'therapist') return
    const next = new URLSearchParams()
    const sub = searchParams.get('therapist_sub') || 'queue'
    next.set('sub', sub === 'payouts' ? 'records' : 'queue')
    const status = searchParams.get('status')
    if (status) next.set('status', status)
    navigate(`/admin/therapist-payouts?${next.toString()}`, { replace: true })
  }, [tabParam, searchParams, navigate])

  const activeTab = PRIMARY_TABS.some((t) => t.id === tabParam) ? tabParam : 'invoices'
  const toolSub = TOOL_SUBS.some((t) => t.id === searchParams.get('sub'))
    ? searchParams.get('sub')
    : 'snapshot'

  useEffect(() => {
    apiFetch('/api/v1/admin/dashboard/summary')
      .then((s) => setClaimsPending(s?.client_payments_pending_review ?? 0))
      .catch(() => setClaimsPending(0))
  }, [activeTab])

  function setTab(tab) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', tab)
    next.delete('sub')
    next.delete('invoiceId')
    next.delete('therapist_sub')
    if (tab === 'payments') next.set('claims', 'pending')
    else next.delete('claims')
    if (tab === 'tools') next.set('sub', 'snapshot')
    setSearchParams(next)
  }

  function setToolSub(sub) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', 'tools')
    next.set('sub', sub)
    next.delete('invoiceId')
    next.delete('claims')
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
        title="Client invoices"
        subtitle="System amount due → verify → send to the parent → record or confirm payment. Optional TDS is what the payer withheld, not an extra charge."
      />

      {claimsPending > 0 && activeTab !== 'payments' ? (
        <div className="admin-alert admin-alert--warning" style={{ marginBottom: 16 }}>
          <strong>{claimsPending} payment claim{claimsPending === 1 ? '' : 's'}</strong> waiting for review.{' '}
          <Link to="/admin/invoices?tab=payments">Open payments →</Link>
        </div>
      ) : null}

      <PortalTabBar
        className="admin-page__tabs-scroll admin-page__tabs--single admin-desktop-only"
        ariaLabel="Client invoice sections"
        activeId={activeTab}
        onChange={setTab}
        tabs={PRIMARY_TABS.map((t) => ({
          id: t.id,
          label: t.label,
          badge: t.id === 'payments' && claimsPending > 0 ? String(claimsPending) : undefined,
        }))}
      />

      <AdminMobilePillTabs
        ariaLabel="Client invoice sections"
        activeId={activeTab}
        onChange={setTab}
        primaryIds={PRIMARY_TABS.map((t) => t.id)}
        overflowIds={[]}
        tabs={PRIMARY_TABS.map((t) => ({
          id: t.id,
          label: t.label,
          badge: t.id === 'payments' && claimsPending > 0 ? String(claimsPending) : undefined,
        }))}
      />

      {activeTab === 'invoices' ? (
        <AdminClientInvoicesTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'payments' ? (
        <AdminClientPaymentsTab openInvoiceId={searchParams.get('invoiceId')} />
      ) : null}
      {activeTab === 'tools' ? (
        <>
          <PortalTabBar
            className="admin-page__tabs-scroll admin-page__subtabs"
            ariaLabel="Finance tools"
            activeId={toolSub}
            onChange={setToolSub}
            tabs={TOOL_SUBS}
          />
          {toolSub === 'snapshot' ? (
            <>
              <FinanceMondayBrief />
              <AdminFinanceOverviewTab />
            </>
          ) : null}
          {toolSub === 'ledger' ? <AdminSessionLedgerTab /> : null}
          {toolSub === 'rules' ? (
            <div>
              <PortalTabBar
                ariaLabel="Rules subsections"
                activeId={rulesSubTab}
                onChange={(id) => {
                  const next = new URLSearchParams(searchParams)
                  next.set('tab', 'tools')
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
          {toolSub === 'disputes' ? <AdminDisputesTab /> : null}
          {toolSub === 'receivables' ? (
            <AdminReceivablesTab openInvoiceId={searchParams.get('invoiceId')} />
          ) : null}
        </>
      ) : null}
    </div>
  )
}
