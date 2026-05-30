import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'

const QUEUE_CARDS = [
  { key: 'notInvoicedThisMonth', label: 'Not invoiced (month)', tone: 'rose' },
  { key: 'ledgerReady', label: 'Ledger ready', tone: 'teal' },
  { key: 'therapistPending', label: 'Therapist pending', tone: 'amber' },
  { key: 'therapistSubmitted', label: 'Therapist submitted', tone: 'indigo' },
  { key: 'draftInvoices', label: 'Draft invoices', tone: 'slate' },
  { key: 'payoutsInReview', label: 'Payouts in review', tone: 'amber' },
  { key: 'paymentClaimsPending', label: 'Payment claims', tone: 'rose' },
  { key: 'openDisputes', label: 'Open disputes', tone: 'rose' },
  { key: 'unpaidClientInvoices', label: 'Unpaid client invoices', tone: 'amber' },
  { key: 'ledgerPendingReview', label: 'Ledger pending review', tone: 'slate' },
]

const LINK_MAP = {
  notInvoicedThisMonth: 'composerNotInvoiced',
  ledgerReady: 'composerLedgerReady',
  therapistPending: 'composerTherapistPending',
  draftInvoices: 'composerNotInvoiced',
  payoutsInReview: 'therapistPayouts',
  paymentClaimsPending: 'clientPayments',
  openDisputes: 'disputes',
  unpaidClientInvoices: 'clientInvoices',
}

export function AdminFinanceOverviewTab() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [billingMonth, setBillingMonth] = useState(() => new Date().toISOString().slice(0, 7))

  useEffect(() => {
    setLoading(true)
    apiFetch(`/api/v1/admin/finance-overview/summary?billing_month=${encodeURIComponent(billingMonth)}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [billingMonth])

  const queues = data?.queues || {}
  const links = data?.links || {}

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'flex-end', marginBottom: 16 }}>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Billing month</span>
          <input
            type="month"
            className="client-inv__filter-input"
            value={billingMonth}
            onChange={(e) => setBillingMonth(e.target.value)}
          />
        </label>
        <Link to="/admin/invoices/compose?queue=not_invoiced_this_month" className="admin-btn admin-btn--primary admin-btn--sm">
          Open composer
        </Link>
      </div>

      {loading ? <div className="admin-skeleton" style={{ minHeight: 120 }} /> : null}

      {!loading && data ? (
        <>
          <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
            {data.activeCases ?? 0} active cases · overview for {data.billingMonth}
          </p>
          <div className="admin-home-queue__grid">
            {QUEUE_CARDS.map((card) => {
              const count = queues[card.key] ?? 0
              const linkKey = LINK_MAP[card.key]
              const href = linkKey ? links[linkKey] : null
              return (
                <AdminPanel key={card.key} title={card.label} padded>
                  <p style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 8px' }}>{count}</p>
                  {href && count > 0 ? (
                    <Link to={href.startsWith('/') ? href : `/admin${href}`} className="admin-btn admin-btn--ghost admin-btn--sm">
                      Open queue →
                    </Link>
                  ) : (
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{count === 0 ? 'All clear' : '—'}</span>
                  )}
                </AdminPanel>
              )
            })}
          </div>
        </>
      ) : null}
    </div>
  )
}
