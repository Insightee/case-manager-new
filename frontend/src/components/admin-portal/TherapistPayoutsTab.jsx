import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import {
  buildTherapistInvoiceQuery,
  parseTherapistInvoiceFilters,
  writeTherapistInvoiceFiltersToParams,
} from '../../lib/invoiceFilters.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'
import { InvoiceBreakdownModal } from '../invoices/InvoiceBreakdownModal.jsx'

export function TherapistPayoutsTab() {
  const { can } = useAuth()
  const { canWriteBilling } = useModuleWrite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [invoices, setInvoices] = useState([])
  const [filters, setFilters] = useState(() => parseTherapistInvoiceFilters(searchParams))
  const [loading, setLoading] = useState(true)
  const [breakdownId, setBreakdownId] = useState(null)
  const [paymentTarget, setPaymentTarget] = useState(null)
  const [paidAmount, setPaidAmount] = useState('')
  const [acting, setActing] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const qs = buildTherapistInvoiceQuery({
        ...filters,
        status: filters.status === 'ALL' ? '' : filters.status,
      })
      setInvoices(await apiFetch(`/api/v1/invoices${qs}`))
    } catch {
      setInvoices([])
    } finally {
      setLoading(false)
    }
  }, [filters])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const next = writeTherapistInvoiceFiltersToParams(searchParams, filters)
    if (searchParams.toString() !== next.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [filters, searchParams, setSearchParams])

  useEffect(() => {
    setFilters((prev) => {
      const parsed = parseTherapistInvoiceFilters(searchParams)
      const same = Object.keys(parsed).every((k) => prev[k] === parsed[k])
      return same ? prev : parsed
    })
  }, [searchParams])

  function patchFilters(patch) {
    setFilters((f) => ({ ...f, ...patch }))
  }

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
    <>
      <InvoiceBreakdownModal invoiceId={breakdownId} open={Boolean(breakdownId)} onClose={() => setBreakdownId(null)} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span className="admin-chip" style={{ background: '#fef3c7', color: '#b45309' }}>
          {pendingCount} therapist invoices in review
        </span>
      </div>

      <AdminPanel title={`${invoices.length} therapist payout invoices`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <select
              className="admin-select"
              style={{ width: 'auto', minWidth: 100 }}
              value={filters.year}
              onChange={(e) => patchFilters({ year: e.target.value })}
            >
              <option value="">All years</option>
              {[new Date().getFullYear(), new Date().getFullYear() - 1].map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
            <input
              className="admin-input"
              placeholder="Month label"
              style={{ maxWidth: 140 }}
              value={filters.month}
              onChange={(e) => patchFilters({ month: e.target.value })}
            />
            <input
              type="date"
              className="admin-input"
              value={filters.dateFrom}
              onChange={(e) => patchFilters({ dateFrom: e.target.value })}
              aria-label="From date"
            />
            <input
              type="date"
              className="admin-input"
              value={filters.dateTo}
              onChange={(e) => patchFilters({ dateTo: e.target.value })}
              aria-label="To date"
            />
            <select
              className="admin-select"
              style={{ width: 'auto', minWidth: 140 }}
              value={filters.status}
              onChange={(e) => patchFilters({ status: e.target.value })}
            >
              <option value="ALL">All statuses</option>
              <option value="IN_REVIEW">In review</option>
              <option value="APPROVED">Approved</option>
              <option value="PAID">Paid</option>
              <option value="REJECTED">Rejected</option>
            </select>
            <AdminSearchInput
              value={filters.search}
              onChange={(value) => patchFilters({ search: value })}
              placeholder="Therapist name or month…"
            />
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : invoices.length === 0 ? (
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
                  {invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td>
                        <span className="admin-table__primary">
                          {inv.therapist_name || `Therapist #${inv.therapist_user_id}`}
                        </span>
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
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => setBreakdownId(inv.id)}
                          >
                            Breakdown
                          </button>
                          {canWriteBilling ? (
                            <>
                              <button
                                type="button"
                                className="admin-btn admin-btn--primary admin-btn--sm"
                                onClick={() => review(inv.id, 'approve')}
                              >
                                Approve
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--danger admin-btn--sm"
                                onClick={() => review(inv.id, 'reject')}
                              >
                                Reject
                              </button>
                            </>
                          ) : null}
                          {can('payout.override') && canWriteBilling ? (
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              onClick={() => openPayment(inv)}
                            >
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
    </>
  )
}
