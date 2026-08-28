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
import { useBillingAction } from '../../hooks/useBillingAction.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminPanel,
  AdminEmptyState,
  AdminToolbar,
  AdminSearchInput,
  AdminTaskCard,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { InvoiceBreakdownModal } from '../invoices/InvoiceBreakdownModal.jsx'

function employmentWarning(inv) {
  if (inv.therapist_is_active === false) return 'Therapist account is inactive'
  const st = inv.therapist_employment_status
  if (st && st !== 'ACTIVE') return `Employment status: ${st.replace(/_/g, ' ')}`
  return null
}

export function TherapistPayoutsTab() {
  const { can } = useAuth()
  const { canWriteBilling } = useModuleWrite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [invoices, setInvoices] = useState([])
  const [filters, setFilters] = useState(() => {
    const parsed = parseTherapistInvoiceFilters(searchParams)
    if (!searchParams.get('status') && !parsed.status) {
      return { ...parsed, status: 'IN_REVIEW' }
    }
    return parsed
  })
  const [loading, setLoading] = useState(true)
  const [breakdownId, setBreakdownId] = useState(null)
  const [breakdownStatus, setBreakdownStatus] = useState(null)
  const [paymentTarget, setPaymentTarget] = useState(null)
  const [paidAmount, setPaidAmount] = useState('')
  const [tdsAmount, setTdsAmount] = useState('')
  const [financeNote, setFinanceNote] = useState('')
  const [settlement, setSettlement] = useState(null)
  const [manualDesc, setManualDesc] = useState('')
  const [manualAmount, setManualAmount] = useState('')
  const [manualShare, setManualShare] = useState('')
  const { loading: acting, error, successMessage, run, clearMessages } = useBillingAction()

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
    await run(
      () =>
        apiFetch(`/api/v1/invoices/${id}/${action}`, {
          method: 'POST',
          body: JSON.stringify({ comment: action === 'reject' ? 'Please revise' : null }),
        }),
      { successMsg: action === 'approve' ? 'Payout approved' : 'Sent back to therapist' }
    )
    load()
  }

  function openPayment(inv) {
    setPaymentTarget(inv)
    setFinanceNote('')
    setSettlement(null)
    setPaidAmount(String(inv.net_payable_inr ?? inv.amount_inr ?? ''))
    setTdsAmount(inv.tds_inr != null ? String(inv.tds_inr) : '')
    apiFetch(`/api/v1/admin/therapist-payouts/settlement-preview?invoice_id=${inv.id}`)
      .then((s) => {
        setSettlement(s)
        if (s?.netInr != null) setPaidAmount(String(s.netInr))
        if (s?.tdsInr != null) setTdsAmount(String(s.tdsInr))
      })
      .catch(() => setSettlement(null))
  }

  async function submitPayment() {
    if (!paymentTarget) return
    try {
      await run(
        () =>
          apiFetch(`/api/v1/invoices/${paymentTarget.id}/payment`, {
            method: 'PATCH',
            body: JSON.stringify({
              paid_amount_inr: Number(paidAmount),
              status: 'PAID',
              tds_inr: tdsAmount === '' ? null : Number(tdsAmount),
              finance_note: financeNote.trim() || null,
            }),
          }),
        { successMsg: 'Marked paid' }
      )
      setPaymentTarget(null)
      load()
    } catch {
      /* shown in alert */
    }
  }

  async function addManualLine() {
    if (!breakdownId) return
    await run(
      () =>
        apiFetch(`/api/v1/invoices/${breakdownId}/manual-lines`, {
          method: 'POST',
          body: JSON.stringify({
            description: manualDesc,
            amount_inr: Number(manualAmount),
            pay_share_inr: Number(manualShare || manualAmount),
          }),
        }),
      { successMsg: 'Manual line added' }
    )
    setManualDesc('')
    setManualAmount('')
    setManualShare('')
    load()
  }

  function openBreakdown(inv) {
    setBreakdownId(inv.id)
    setBreakdownStatus(inv.status)
  }

  return (
    <>
      <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
      <InvoiceBreakdownModal
        invoiceId={breakdownId}
        invoiceStatus={breakdownStatus}
        open={Boolean(breakdownId)}
        onClose={() => setBreakdownId(null)}
        onAmended={load}
      />
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span className="admin-chip" style={{ background: '#fef3c7', color: '#b45309' }}>
          {pendingCount} therapist invoices in review
        </span>
      </div>

      {breakdownId && canWriteBilling ? (
        <AdminPanel title="Add manual payout line" padded style={{ marginBottom: 16 }}>
          <div className="admin-form-grid" style={{ gridTemplateColumns: '1fr 120px 120px auto' }}>
            <input
              className="admin-input"
              placeholder="Description"
              value={manualDesc}
              onChange={(e) => setManualDesc(e.target.value)}
            />
            <input
              className="admin-input"
              type="number"
              placeholder="Amount INR"
              value={manualAmount}
              onChange={(e) => setManualAmount(e.target.value)}
            />
            <input
              className="admin-input"
              type="number"
              placeholder="Therapist pay INR"
              value={manualShare}
              onChange={(e) => setManualShare(e.target.value)}
            />
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={addManualLine}>
              Add
            </button>
          </div>
        </AdminPanel>
      ) : null}

      <AdminPanel title={`${invoices.length} therapist payout invoices`} padded={false}>
        <div className="admin-panel__body">
          <AdminCollapsibleFilters
            quickSearch={
              <AdminSearchInput
                value={filters.search}
                onChange={(value) => patchFilters({ search: value })}
                placeholder="Therapist name or month…"
              />
            }
            activeChips={[
              filters.year && `Year ${filters.year}`,
              filters.month && filters.month,
              filters.status && filters.status !== 'ALL' ? filters.status : null,
            ].filter(Boolean)}
            activeCount={[filters.year, filters.month, filters.status !== 'ALL' && filters.status, filters.dateFrom, filters.dateTo].filter(Boolean).length}
          >
            <AdminToolbar className="admin-toolbar--mobile-compact">
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
          </AdminCollapsibleFilters>

          {loading ? (
            <div className="admin-skeleton" />
          ) : invoices.length === 0 ? (
            <AdminEmptyState title="No invoices" description="Therapist submissions appear here. You can also raise a payout invoice from This month." />
          ) : (
            <AdminDataList
              desktop={
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Therapist</th>
                        <th>Month</th>
                        <th>Sessions</th>
                        <th>Gross</th>
                        <th>TDS</th>
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {invoices.map((inv) => {
                        const warn = employmentWarning(inv)
                        return (
                          <tr key={inv.id}>
                            <td>
                              <span className="admin-table__primary">
                                {inv.therapist_name || `Therapist #${inv.therapist_user_id}`}
                              </span>
                              <span className="admin-table__meta">Invoice {inv.id}</span>
                              {inv.therapist_payout_flagged ? (
                                <span className="admin-chip admin-chip--warn" style={{ marginTop: 4 }}>
                                  This therapist was flagged
                                </span>
                              ) : null}
                              {warn ? (
                                <span className="admin-table__meta" style={{ color: '#b45309' }}>
                                  {warn}
                                </span>
                              ) : null}
                              {inv.notes ? (
                                <span className="admin-table__meta">Therapist note: {inv.notes}</span>
                              ) : null}
                              {inv.reviewer_comment ? (
                                <span className="admin-table__meta">Finance: {inv.reviewer_comment}</span>
                              ) : null}
                            </td>
                            <td>{inv.month}</td>
                            <td>{inv.sessions_count ?? '—'}</td>
                            <td>{formatCurrency(inv.amount_inr)}</td>
                            <td>{inv.tds_inr != null ? formatCurrency(inv.tds_inr) : '—'}</td>
                            <td>
                              <StatusBadge status={inv.status} />
                            </td>
                            <td>
                              <div className="admin-btn-group">
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--ghost admin-btn--sm"
                                  onClick={() => openBreakdown(inv)}
                                >
                                  Breakdown
                                </button>
                                {canWriteBilling && inv.status === 'IN_REVIEW' ? (
                                  <>
                                    <button
                                      type="button"
                                      className="admin-btn admin-btn--primary admin-btn--sm"
                                      disabled={acting}
                                      onClick={() => review(inv.id, 'approve')}
                                    >
                                      Approve
                                    </button>
                                    <button
                                      type="button"
                                      className="admin-btn admin-btn--danger admin-btn--sm"
                                      disabled={acting}
                                      onClick={() => review(inv.id, 'reject')}
                                    >
                                      Reject
                                    </button>
                                  </>
                                ) : null}
                                {can('payout.override') && canWriteBilling && inv.status === 'APPROVED' ? (
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
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              }
              mobile={invoices.map((inv) => (
                <li key={inv.id}>
                  <AdminTaskCard
                    title={inv.therapist_name || `Therapist #${inv.therapist_user_id}`}
                    meta={`${inv.month} · ${inv.sessions_count ?? 0} sessions · ${formatCurrency(inv.amount_inr)}`}
                    badges={
                      <>
                        <StatusBadge status={inv.status} />
                        {inv.therapist_payout_flagged ? (
                          <span className="admin-chip admin-chip--warn">This therapist was flagged</span>
                        ) : null}
                      </>
                    }
                    actions={
                      <div className="admin-btn-group">
                        {canWriteBilling && inv.status === 'IN_REVIEW' ? (
                          <>
                            <button
                              type="button"
                              className="admin-btn admin-btn--primary admin-btn--sm"
                              disabled={acting}
                              onClick={() => review(inv.id, 'approve')}
                            >
                              Approve
                            </button>
                            <button
                              type="button"
                              className="admin-btn admin-btn--danger admin-btn--sm"
                              disabled={acting}
                              onClick={() => review(inv.id, 'reject')}
                            >
                              Reject
                            </button>
                          </>
                        ) : null}
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          onClick={() => openBreakdown(inv)}
                        >
                          Breakdown
                        </button>
                      </div>
                    }
                  />
                </li>
              ))}
            />
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
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 440, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>Mark paid</h2>
            {employmentWarning(paymentTarget) ? (
              <p className="admin-alert admin-alert--warning">{employmentWarning(paymentTarget)}</p>
            ) : null}
            {paymentTarget.therapist_payout_flagged ? (
              <p className="admin-alert admin-alert--warning">
                <strong>This therapist was flagged.</strong> Review the payout before recording final payment. The flag clears after this payment is processed.
              </p>
            ) : null}
            <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
              {paymentTarget.therapist_name || `#${paymentTarget.therapist_user_id}`} · {paymentTarget.month}
            </p>
            {paymentTarget.notes ? (
              <p style={{ fontSize: '0.85rem', background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                Therapist note: {paymentTarget.notes}
              </p>
            ) : null}
            {settlement ? (
              <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
                {settlement.tdsPending
                  ? `Gross ${formatCurrency(settlement.grossInr)} · TDS not entered yet · net ${formatCurrency(settlement.netInr)}`
                  : `Gross ${formatCurrency(settlement.grossInr)} · TDS ${formatCurrency(settlement.tdsInr)}${settlement.tdsRatePercent != null ? ` (${settlement.tdsRatePercent}%)` : ''} · net ${formatCurrency(settlement.netInr)}`}
              </p>
            ) : null}
            <label style={{ display: 'block', marginTop: 12 }}>
              TDS withheld (INR)
              <input
                className="admin-input"
                type="number"
                value={tdsAmount}
                onChange={(e) => setTdsAmount(e.target.value)}
                style={{ width: '100%', marginTop: 6 }}
              />
            </label>
            <label style={{ display: 'block', marginTop: 12 }}>
              Amount paid to therapist (INR)
              <input
                className="admin-input"
                type="number"
                value={paidAmount}
                onChange={(e) => setPaidAmount(e.target.value)}
                style={{ width: '100%', marginTop: 6 }}
              />
            </label>
            <label style={{ display: 'block', marginTop: 12 }}>
              Finance note (optional)
              <textarea
                className="admin-input"
                rows={2}
                value={financeNote}
                onChange={(e) => setFinanceNote(e.target.value)}
                style={{ width: '100%', marginTop: 6 }}
              />
            </label>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={submitPayment}>
                Mark paid
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
