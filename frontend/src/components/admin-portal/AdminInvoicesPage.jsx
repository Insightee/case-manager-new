import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  AdminPageHeader,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'
import { InvoiceBreakdownModal } from '../invoices/InvoiceBreakdownModal.jsx'

export function AdminInvoicesPage() {
  const { can } = useAuth()
  const [invoices, setInvoices] = useState([])
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [loading, setLoading] = useState(true)
  const [breakdownId, setBreakdownId] = useState(null)
  const [paymentTarget, setPaymentTarget] = useState(null)
  const [paidAmount, setPaidAmount] = useState('')
  const [acting, setActing] = useState(false)

  async function load() {
    setLoading(true)
    try {
      setInvoices(await apiFetch('/api/v1/invoices'))
    } catch {
      setInvoices([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    return invoices.filter((inv) => {
      if (statusFilter !== 'ALL' && inv.status !== statusFilter) return false
      if (!q) return true
      const name = (inv.therapist_name || '').toLowerCase()
      return (
        name.includes(q) ||
        String(inv.therapist_user_id).includes(q) ||
        inv.month?.toLowerCase().includes(q)
      )
    })
  }, [invoices, search, statusFilter])

  const pendingCount = invoices.filter((i) => i.status === 'IN_REVIEW').length

  async function review(id, action) {
    await apiFetch(`/api/v1/invoices/${id}/${action}`, {
      method: 'POST',
      body: JSON.stringify({ comment: action === 'reject' ? 'Please revise' : null }),
    })
    load()
  }

  function openPayment(inv) {
    setPaymentTarget(inv)
    setPaidAmount(String(inv.amount_inr ?? ''))
  }

  async function submitPayment() {
    if (!paymentTarget) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/invoices/${paymentTarget.id}/payment`, {
        method: 'PATCH',
        body: JSON.stringify({ paid_amount_inr: Number(paidAmount), status: 'PAID' }),
      })
      setPaymentTarget(null)
      load()
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="admin-page">
      <InvoiceBreakdownModal invoiceId={breakdownId} open={Boolean(breakdownId)} onClose={() => setBreakdownId(null)} />
      <AdminPageHeader
        eyebrow="Finance"
        title="Invoice review"
        subtitle="Approve therapist invoices and record payment overrides."
        actions={
          <span className="admin-chip" style={{ background: '#fef3c7', color: '#b45309' }}>
            {pendingCount} in review
          </span>
        }
      />

      <AdminPanel title={`${filtered.length} invoices`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Therapist name or month…" />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All statuses</option>
              <option value="IN_REVIEW">In review</option>
              <option value="APPROVED">Approved</option>
              <option value="PAID">Paid</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No invoices" description="Invoices appear when therapists submit billing." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Therapist</th>
                    <th>Month</th>
                    <th>Sessions</th>
                    <th>Amount</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((inv) => (
                    <tr key={inv.id}>
                      <td>
                        <span className="admin-table__primary">{inv.therapist_name || `Therapist #${inv.therapist_user_id}`}</span>
                        <span className="admin-table__meta">Invoice {inv.id}</span>
                      </td>
                      <td>{inv.month}</td>
                      <td>{inv.sessions_count ?? '—'}</td>
                      <td>{formatCurrency(inv.amount_inr)}</td>
                      <td>
                        <StatusBadge status={inv.status} />
                      </td>
                      <td>
                        <div className="admin-btn-group">
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setBreakdownId(inv.id)}>
                            Breakdown
                          </button>
                          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => review(inv.id, 'approve')}>
                            Approve
                          </button>
                          <button type="button" className="admin-btn admin-btn--danger admin-btn--sm" onClick={() => review(inv.id, 'reject')}>
                            Reject
                          </button>
                          {can('payout.override') ? (
                            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => openPayment(inv)}>
                              Record payment
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>

      {paymentTarget ? (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 400, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>Record payment</h2>
            <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
              {paymentTarget.therapist_name || `#${paymentTarget.therapist_user_id}`} · {paymentTarget.month}
            </p>
            <label style={{ display: 'block', marginTop: 12 }}>
              Paid amount (INR)
              <input
                className="admin-input"
                type="number"
                value={paidAmount}
                onChange={(e) => setPaidAmount(e.target.value)}
                style={{ width: '100%', marginTop: 6 }}
              />
            </label>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={submitPayment}>
                Save
              </button>
              <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setPaymentTarget(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
