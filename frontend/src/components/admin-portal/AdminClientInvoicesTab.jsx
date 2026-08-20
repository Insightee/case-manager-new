import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload, getApiBaseUrl, getTokens } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  buildClientBillingScopeQuery,
  buildClientInvoiceQuery,
  CLIENT_INVOICE_STATUSES,
  INVOICE_TYPES,
  parseClientInvoiceFilters,
  writeClientInvoiceFiltersToParams,
} from '../../lib/invoiceFilters.js'
import { formatPaymentMethod, paymentStatusLabel } from '../../lib/paymentMethodLabels.js'
import { formatApiDateIN } from '../../lib/datetime.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminSearchInput,
  AdminTaskCard,
  ServiceFilterSelect,
  formatCurrency,
} from './ui/index.js'
import { InvoiceLineItemEditor } from './InvoiceLineItemEditor.jsx'
import { ClientInvoiceOverviewPanel } from './ClientInvoiceOverviewPanel.jsx'
import './admin-client-invoices.css'
import './admin-client-invoices-composer.css'

const STATUS_PILL = {
  DRAFT: 'draft',
  GENERATED: 'generated',
  SENT: 'sent',
  PARTIALLY_PAID: 'partially_paid',
  PAID: 'paid',
  OVERDUE: 'overdue',
  DISPUTED: 'disputed',
  CANCELLED: 'cancelled',
}

function statusPillClass(status) {
  const key = (status || '').toUpperCase().replace(/-/g, '_')
  return `client-inv__status-pill client-inv__status-pill--${STATUS_PILL[key] || 'draft'}`
}

function displayStatus(inv) {
  if (inv.isOverdue && inv.balanceInr > 0) return 'OVERDUE'
  return (inv.status || '').toUpperCase()
}

function formatPaidAt(iso) {
  if (!iso) return '—'
  return formatApiDateIN(String(iso).slice(0, 10)) || String(iso).slice(0, 10)
}

function PaymentClaimReviewCard({
  payment,
  invoiceNumber,
  childName,
  canWriteBilling,
  acting,
  rejectPayId,
  rejectPayNote,
  onRejectNoteChange,
  onStartReject,
  onCancelReject,
  onConfirm,
  onReject,
  onViewProof,
  onOpenInvoice,
}) {
  const isRejecting = rejectPayId === payment.id
  return (
    <article className="client-inv__claim-card">
      <div className="client-inv__claim-card-top">
        <div className="client-inv__claim-card-main">
          <p className="client-inv__claim-card-title">
            {formatCurrency(payment.amountInr)}
            {payment.tdsInr ? ` · TDS ${formatCurrency(payment.tdsInr)}` : ''}
            <span className="client-inv__claim-card-status">{paymentStatusLabel(payment.paymentStatus)}</span>
          </p>
          <p className="client-inv__claim-card-meta">
            {invoiceNumber}
            {childName ? ` · ${childName}` : ''}
          </p>
          <dl className="client-inv__claim-card-grid">
            <div>
              <dt>Payment mode</dt>
              <dd>{formatPaymentMethod(payment.method)}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd>{payment.reference || '—'}</dd>
            </div>
            <div>
              <dt>Payment date</dt>
              <dd>{formatPaidAt(payment.paidAt)}</dd>
            </div>
          </dl>
        </div>
        <div className="client-inv__claim-card-actions">
          {payment.hasProof ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => onViewProof(payment)}>
              View receipt
            </button>
          ) : null}
          {onOpenInvoice ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onOpenInvoice}>
              Open invoice
            </button>
          ) : null}
        </div>
      </div>
      {canWriteBilling && payment.paymentStatus === 'pending_review' ? (
        isRejecting ? (
          <div className="client-inv__claim-card-review">
            <textarea
              className="client-inv__filter-input"
              style={{ width: '100%', minHeight: 50 }}
              placeholder="Reason if rejecting"
              value={rejectPayNote}
              onChange={(e) => onRejectNoteChange(e.target.value)}
            />
            <div className="admin-btn-group" style={{ marginTop: 8 }}>
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={() => onConfirm(payment.id)}>
                Confirm payment
              </button>
              <button
                type="button"
                className="admin-btn admin-btn--sm"
                disabled={acting || !rejectPayNote.trim()}
                onClick={() => onReject(payment.id)}
              >
                Reject
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onCancelReject}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="admin-btn-group client-inv__claim-card-review">
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={() => onConfirm(payment.id)}>
              Confirm
            </button>
            <button type="button" className="admin-btn admin-btn--sm" disabled={acting} onClick={() => onStartReject(payment.id)}>
              Reject…
            </button>
          </div>
        )
      ) : null}
      {payment.rejectionNote ? <p className="client-inv__claim-card-note">{payment.rejectionNote}</p> : null}
    </article>
  )
}

async function downloadExport(path, filename) {
  const { access } = getTokens()
  const res = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  })
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ── View / payment drawers ───────────────────────────────────────────────────
export function InvoiceDetailDrawer({ invoiceId, onClose, onRefresh, canWriteBilling }) {
  const [detail, setDetail] = useState(null)
  const [tab, setTab] = useState('overview')
  const [loading, setLoading] = useState(true)
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [payAmount, setPayAmount] = useState('')
  const [payTds, setPayTds] = useState('0')
  const [payNote, setPayNote] = useState('')
  const [payMethod, setPayMethod] = useState('UPI')
  const [payRef, setPayRef] = useState('')
  const [resolveId, setResolveId] = useState(null)
  const [resolveNote, setResolveNote] = useState('')
  const [resolveAdj, setResolveAdj] = useState('')
  const [rejectPayId, setRejectPayId] = useState(null)
  const [rejectPayNote, setRejectPayNote] = useState('')
  const [lateFeeOpen, setLateFeeOpen] = useState(false)
  const [lateFeeAmount, setLateFeeAmount] = useState('')
  const [lateFeeNote, setLateFeeNote] = useState('')
  const [zohoStatus, setZohoStatus] = useState('')
  const [acting, setActing] = useState(false)

  const load = useCallback(() => {
    if (!invoiceId) return
    setLoading(true)
    apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}`)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setLoading(false))
  }, [invoiceId])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (detail?.balanceInr != null) setPayAmount(String(detail.balanceInr))
  }, [detail])

  useEffect(() => {
    if (tab === 'overview' && invoiceId) load()
  }, [tab, invoiceId, load])

  async function sendToClient() {
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/notify-parent?resend=true`, { method: 'POST' })
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  async function markGenerated() {
    await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'GENERATED' }),
    })
    load()
    onRefresh()
  }

  async function recordPayment(e) {
    e.preventDefault()
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/payments`, {
        method: 'POST',
        body: JSON.stringify({
          amount_inr: Number(payAmount),
          tds_inr: Number(payTds || 0),
          method: payMethod,
          reference: payRef || null,
          notes: payNote.trim() || null,
        }),
      })
      setPaymentOpen(false)
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  async function confirmPaymentClaim(paymentId) {
    setActing(true)
    try {
      const result = await apiFetch(`/api/v1/admin/client-billing/payments/${paymentId}/confirm`, { method: 'POST' })
      if (result?.status === 'already_confirmed') {
        setZohoStatus('Payment was already confirmed.')
      }
      load()
      onRefresh()
    } catch (err) {
      alert(err?.message || 'Could not confirm payment — check collectible balance and disputes.')
    } finally {
      setActing(false)
    }
  }

  async function rejectPaymentClaim(paymentId) {
    if (!rejectPayNote.trim()) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/payments/${paymentId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ note: rejectPayNote.trim() }),
      })
      setRejectPayId(null)
      setRejectPayNote('')
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  async function viewPaymentProof(payment) {
    try {
      await apiDownload(
        `/api/v1/admin/client-billing/payments/${payment.id}/proof`,
        payment.proofFileName || `payment-proof-${payment.id}`,
      )
    } catch (err) {
      alert(err?.message || 'Could not open payment receipt')
    }
  }

  async function resolveDispute(disputeId, status) {
    const resolution = resolveNote.trim()
    if (status === 'REJECTED' && !resolution) {
      return
    }
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/disputes/${disputeId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          resolution,
          adjustment_inr: resolveAdj ? Number(resolveAdj) : null,
        }),
      })
      setResolveId(null)
      setResolveNote('')
      setResolveAdj('')
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  async function sendPaymentReminder() {
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/payment-reminder`, { method: 'POST' })
      setZohoStatus('Payment reminder sent to parent.')
      load()
    } finally {
      setActing(false)
    }
  }

  async function pushToZoho() {
    setActing(true)
    try {
      const result = await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/push-zoho`, { method: 'POST' })
      setZohoStatus(result?.externalId ? `Zoho: ${result.externalId} (${result.status})` : result?.message || result?.status || 'Push attempted')
      load()
    } finally {
      setActing(false)
    }
  }

  async function addLateFee(e) {
    e.preventDefault()
    const amount = Number(lateFeeAmount)
    if (!amount || amount <= 0) return
    setActing(true)
    try {
      const note = lateFeeNote.trim()
      const qs = new URLSearchParams({ amount_inr: String(amount) })
      if (note) qs.set('finance_note', note)
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/late-fee?${qs}`, { method: 'POST' })
      setLateFeeOpen(false)
      setLateFeeAmount('')
      setLateFeeNote('')
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  async function removeLateFeeLine(lineId) {
    if (!window.confirm('Remove this late fee line?')) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines/${lineId}/late-fee`, { method: 'DELETE' })
      load()
      onRefresh()
    } finally {
      setActing(false)
    }
  }

  if (!invoiceId) return null

  return (
    <div className="client-inv__overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="client-inv__drawer client-inv__drawer--wide" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0 }}>{detail?.invoiceNumber || 'Invoice'}</h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#64748b' }}>
              {detail?.childName} · {detail?.caseId}
            </p>
            {detail?.id ? (
              <Link to={`/admin/invoices/client/${detail.id}`} style={{ fontSize: '0.8rem' }}>
                Open full view
              </Link>
            ) : null}
          </div>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
            Close
          </button>
        </div>

        {loading ? (
          <div className="admin-skeleton" />
        ) : !detail ? (
          <p>Could not load invoice.</p>
        ) : (
          <>
            <div className="client-inv__drawer-tabs">
              {['overview', 'lines', 'payments'].map((t) => (
                <button key={t} type="button" className={`client-inv__drawer-tab ${tab === t ? 'is-active' : ''}`} onClick={() => setTab(t)}>
                  {t === 'overview' ? 'Overview' : t === 'lines' ? 'Line items' : 'Payments & disputes'}
                </button>
              ))}
            </div>

            {tab === 'overview' ? (
              <ClientInvoiceOverviewPanel
                detail={detail}
                canWriteBilling={canWriteBilling}
                acting={acting}
                onSendToClient={sendToClient}
                onMarkGenerated={markGenerated}
                onOpenPayment={detail.balanceInr > 0 ? () => setPaymentOpen(true) : null}
                onSendReminder={detail.balanceInr > 0 ? sendPaymentReminder : null}
                onAddLateFee={canWriteBilling ? () => setLateFeeOpen(true) : null}
                onPushZoho={canWriteBilling ? pushToZoho : null}
                zohoStatus={zohoStatus}
              />
            ) : null}

            {tab === 'lines' ? (
              <InvoiceLineItemEditor
                invoiceId={invoiceId}
                lines={detail.lines || []}
                detail={detail}
                canWrite={canWriteBilling && detail.status === 'DRAFT'}
                onUpdated={load}
                onRemoveLateFee={canWriteBilling ? removeLateFeeLine : null}
              />
            ) : null}

            {tab === 'payments' ? (
              <div>
                <h4 style={{ fontSize: '0.85rem', margin: '0 0 8px' }}>Payments</h4>
                {(detail.payments || []).length === 0 ? (
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No payments recorded.</p>
                ) : (
                  detail.payments.map((p) => (
                    <PaymentClaimReviewCard
                      key={p.id}
                      payment={p}
                      invoiceNumber={detail.invoiceNumber}
                      childName={detail.childName}
                      canWriteBilling={canWriteBilling}
                      acting={acting}
                      rejectPayId={rejectPayId}
                      rejectPayNote={rejectPayNote}
                      onRejectNoteChange={setRejectPayNote}
                      onStartReject={setRejectPayId}
                      onCancelReject={() => {
                        setRejectPayId(null)
                        setRejectPayNote('')
                      }}
                      onConfirm={confirmPaymentClaim}
                      onReject={rejectPaymentClaim}
                      onViewProof={viewPaymentProof}
                    />
                  ))
                )}
                <h4 style={{ fontSize: '0.85rem', margin: '16px 0 8px' }}>Disputes</h4>
                {(detail.disputes || []).length === 0 ? (
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No disputes.</p>
                ) : (
                  detail.disputes.map((d) => (
                    <div key={d.id} className="client-inv__dispute-card">
                      <strong>{d.reasonCode}</strong> — {d.status}
                      <p style={{ margin: '6px 0', fontSize: '0.85rem' }}>{d.message}</p>
                      {canWriteBilling && (d.status === 'OPEN' || d.status === 'UNDER_REVIEW') ? (
                        resolveId === d.id ? (
                          <div style={{ marginTop: 8 }}>
                            <textarea className="client-inv__filter-input" style={{ width: '100%', minHeight: 50 }} placeholder="Resolution or rejection note (required if rejecting)" value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} />
                            <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginTop: 6 }} placeholder="Adjustment INR (optional)" value={resolveAdj} onChange={(e) => setResolveAdj(e.target.value)} />
                            <div className="admin-btn-group" style={{ marginTop: 8 }}>
                              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={() => resolveDispute(d.id, 'RESOLVED')}>
                                Resolve
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--sm"
                                disabled={acting || !resolveNote.trim()}
                                onClick={() => resolveDispute(d.id, 'REJECTED')}
                              >
                                Confirm reject
                              </button>
                            </div>
                          </div>
                        ) : (
                          <button type="button" className="admin-btn admin-btn--sm" onClick={() => setResolveId(d.id)}>
                            Review dispute
                          </button>
                        )
                      ) : (
                        d.adminResolution && <p style={{ fontSize: '0.8rem', color: '#64748b' }}>{d.adminResolution}</p>
                      )}
                    </div>
                  ))
                )}
              </div>
            ) : null}
          </>
        )}

        {canWriteBilling && paymentOpen && detail ? (
          <form onSubmit={recordPayment} style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid #e2e8f0' }}>
            <h4 style={{ margin: '0 0 10px' }}>Record payment</h4>
            <p className="admin-muted" style={{ marginTop: 0, fontSize: '0.8rem' }}>
              Amount received is what hit the bank. TDS is optional (usually B2B). Together they close the invoice.
            </p>
            <label className="client-inv__filter-label">Amount received (INR)</label>
            <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} value={payAmount} onChange={(e) => setPayAmount(e.target.value)} required />
            <label className="client-inv__filter-label">TDS withheld by payer (INR)</label>
            <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} value={payTds} onChange={(e) => setPayTds(e.target.value)} min="0" />
            <select className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
              {['UPI', 'BANK_TRANSFER', 'CASH', 'CHEQUE', 'GATEWAY'].map((m) => (
                <option key={m} value={m}>{m.replaceAll('_', ' ')}</option>
              ))}
            </select>
            <input className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} placeholder="Reference" value={payRef} onChange={(e) => setPayRef(e.target.value)} />
            <textarea className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8, minHeight: 48 }} placeholder="Note (optional)" value={payNote} onChange={(e) => setPayNote(e.target.value)} />
            <p className="admin-muted" style={{ fontSize: '0.8rem' }}>
              Applied to invoice: {formatCurrency(Number(payAmount || 0) + Number(payTds || 0))}
            </p>
            <div className="admin-btn-group">
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting}>
                Save payment
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setPaymentOpen(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : null}

        {canWriteBilling && lateFeeOpen && detail ? (
          <form onSubmit={addLateFee} style={{ marginTop: 20, paddingTop: 16, borderTop: '1px solid #e2e8f0' }}>
            <h4 style={{ margin: '0 0 10px' }}>Add late fee</h4>
            <input
              type="number"
              className="client-inv__filter-input"
              style={{ width: '100%', marginBottom: 8 }}
              placeholder="Amount INR"
              value={lateFeeAmount}
              onChange={(e) => setLateFeeAmount(e.target.value)}
              required
            />
            <input
              className="client-inv__filter-input"
              style={{ width: '100%', marginBottom: 8 }}
              placeholder="Finance note (optional)"
              value={lateFeeNote}
              onChange={(e) => setLateFeeNote(e.target.value)}
            />
            <div className="admin-btn-group">
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting}>
                Add fee line
              </button>
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setLateFeeOpen(false)}>
                Cancel
              </button>
            </div>
          </form>
        ) : null}
      </div>
    </div>
  )
}

export function AdminClientInvoicesTab({
  highlightClaimsPending = false,
  claimsOnly = false,
  paymentsMode = false,
  openInvoiceId = null,
}) {
  const navigate = useNavigate()
  const { canWriteBilling } = useModuleWrite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [summary, setSummary] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(() => parseClientInvoiceFilters(searchParams))
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [filterOptions, setFilterOptions] = useState(null)
  const [viewId, setViewId] = useState(openInvoiceId ? Number(openInvoiceId) : null)
  const [loadError, setLoadError] = useState(null)
  const [pendingClaims, setPendingClaims] = useState([])
  const [claimsLoading, setClaimsLoading] = useState(false)
  const [claimRejectId, setClaimRejectId] = useState(null)
  const [claimRejectNote, setClaimRejectNote] = useState('')
  const [claimActing, setClaimActing] = useState(false)

  useEffect(() => {
    apiFetch('/api/v1/admin/client-billing/invoices/filter-options')
      .then(setFilterOptions)
      .catch(() => setFilterOptions(null))
  }, [])

  const load = useCallback(() => {
    const scopeQs = buildClientBillingScopeQuery(filters)
    const qs = buildClientInvoiceQuery({
      ...filters,
      claimsPending: claimsOnly || filters.claimsPending,
    })
    setLoading(true)
    setLoadError(null)
    Promise.all([
      apiFetch(`/api/v1/admin/client-billing/summary${scopeQs}`),
      apiFetch(`/api/v1/admin/client-billing/invoices${qs}`),
    ])
      .then(([s, list]) => {
        setSummary(s)
        setInvoices(Array.isArray(list) ? list : [])
      })
      .catch((err) => {
        setSummary(null)
        setInvoices([])
        setLoadError(err?.message || 'Client billing data is unavailable right now.')
      })
      .finally(() => setLoading(false))
  }, [filters, claimsOnly])

  useEffect(() => {
    load()
  }, [load])

  const loadPendingClaims = useCallback(() => {
    if (!paymentsMode) return
    setClaimsLoading(true)
    apiFetch('/api/v1/admin/client-billing/payment-claims')
      .then((rows) => setPendingClaims(Array.isArray(rows) ? rows : []))
      .catch(() => setPendingClaims([]))
      .finally(() => setClaimsLoading(false))
  }, [paymentsMode])

  useEffect(() => {
    loadPendingClaims()
  }, [loadPendingClaims, invoices])

  async function confirmQueuedClaim(paymentId) {
    setClaimActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/payments/${paymentId}/confirm`, { method: 'POST' })
      load()
      loadPendingClaims()
    } catch (err) {
      alert(err?.message || 'Could not confirm payment claim')
    } finally {
      setClaimActing(false)
    }
  }

  async function rejectQueuedClaim(paymentId) {
    if (!claimRejectNote.trim()) return
    setClaimActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/payments/${paymentId}/reject`, {
        method: 'POST',
        body: JSON.stringify({ note: claimRejectNote.trim() }),
      })
      setClaimRejectId(null)
      setClaimRejectNote('')
      load()
      loadPendingClaims()
    } finally {
      setClaimActing(false)
    }
  }

  async function viewQueuedProof(payment) {
    try {
      await apiDownload(
        `/api/v1/admin/client-billing/payments/${payment.id}/proof`,
        payment.proofFileName || `payment-proof-${payment.id}`,
      )
    } catch (err) {
      alert(err?.message || 'Could not open payment receipt')
    }
  }

  useEffect(() => {
    const next = writeClientInvoiceFiltersToParams(searchParams, filters)
    if (searchParams.toString() !== next.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [filters])

  useEffect(() => {
    setFilters((prev) => {
      const parsed = parseClientInvoiceFilters(searchParams)
      const same = Object.keys(parsed).every((k) => prev[k] === parsed[k])
      return same ? prev : parsed
    })
  }, [searchParams])

  useEffect(() => {
    if (openInvoiceId) setViewId(Number(openInvoiceId))
  }, [openInvoiceId])

  function patchFilters(patch) {
    setFilters((f) => ({ ...f, ...patch }))
  }

  const pendingClaimsCount = useMemo(() => {
    let n = 0
    for (const inv of invoices) {
      for (const p of inv.payments || []) {
        if (p.paymentStatus === 'pending_review') n += 1
      }
    }
    return n
  }, [invoices])

  const monthOptions = filterOptions?.billingMonths?.length
    ? filterOptions.billingMonths
    : [...new Set(invoices.map((i) => i.billingMonth).filter(Boolean))].sort().reverse()

  const activeFilterCount = [
    filters.year,
    filters.month,
    filters.module,
    filters.status,
    filters.invoiceType,
    filters.dateFrom,
    filters.dateTo,
  ].filter(Boolean).length

  function clearFilters() {
    setFilters((prev) => ({
      ...prev,
      year: '',
      month: '',
      module: '',
      status: '',
      invoiceType: '',
      dateFrom: '',
      dateTo: '',
    }))
  }

  return (
    <div className="client-inv">
      {paymentsMode ? (
        <p className="admin-muted" style={{ marginBottom: 12 }}>
          Record and verify client payments. Open an invoice to confirm or reject payment claims.
        </p>
      ) : null}
      {highlightClaimsPending && pendingClaimsCount > 0 ? (
        <p className="admin-alert admin-alert--warning" style={{ marginBottom: 12 }}>
          Showing invoices with payment claims awaiting review. Open an invoice to confirm or reject each claim.
        </p>
      ) : null}

      {loadError ? (
        <div className="admin-alert admin-alert--warning" style={{ marginBottom: 12 }}>
          {loadError}
        </div>
      ) : null}

      {paymentsMode ? (
        <section className="client-inv__claims-queue" aria-label="Offline payment claims awaiting review">
          <div className="client-inv__claims-queue-head">
            <h3>Offline payment claims</h3>
            <p>Review parent-submitted receipts with payment mode, reference, and payment date before confirming.</p>
          </div>
          {claimsLoading ? (
            <p className="admin-muted">Loading payment claims…</p>
          ) : pendingClaims.length === 0 ? (
            <p className="admin-muted">No offline payment claims awaiting review.</p>
          ) : (
            pendingClaims.map((claim) => (
              <PaymentClaimReviewCard
                key={claim.id}
                payment={claim}
                invoiceNumber={claim.invoiceNumber}
                childName={claim.childName}
                canWriteBilling={canWriteBilling}
                acting={claimActing}
                rejectPayId={claimRejectId}
                rejectPayNote={claimRejectNote}
                onRejectNoteChange={setClaimRejectNote}
                onStartReject={setClaimRejectId}
                onCancelReject={() => {
                  setClaimRejectId(null)
                  setClaimRejectNote('')
                }}
                onConfirm={confirmQueuedClaim}
                onReject={rejectQueuedClaim}
                onViewProof={viewQueuedProof}
                onOpenInvoice={() => setViewId(claim.invoiceId)}
              />
            ))
          )}
        </section>
      ) : null}

      <div className="client-inv__kpi-grid">
        {pendingClaimsCount > 0 ? (
          <div className="client-inv__kpi client-inv__kpi--amber">
            <p className="client-inv__kpi-label">Claims pending review</p>
            <p className="client-inv__kpi-value">{pendingClaimsCount}</p>
          </div>
        ) : null}
        <div className="client-inv__kpi client-inv__kpi--amber">
          <p className="client-inv__kpi-label">Outstanding</p>
          <p className="client-inv__kpi-value">{formatCurrency(summary?.totalOutstandingInr ?? 0)}</p>
        </div>
        <div className="client-inv__kpi client-inv__kpi--red">
          <p className="client-inv__kpi-label">Overdue</p>
          <p className="client-inv__kpi-value">{summary?.overdueCount ?? 0}</p>
        </div>
        <div className="client-inv__kpi client-inv__kpi--orange">
          <p className="client-inv__kpi-label">Disputed</p>
          <p className="client-inv__kpi-value">{summary?.disputedCount ?? 0}</p>
        </div>
        <div className="client-inv__kpi client-inv__kpi--green">
          <p className="client-inv__kpi-label">Paid this month</p>
          <p className="client-inv__kpi-value">{summary?.paidThisMonthCount ?? 0}</p>
        </div>
      </div>

      <div className="client-inv__filter-head admin-desktop-only">
        <AdminSearchInput
          value={filters.search}
          onChange={(value) => patchFilters({ search: value })}
          placeholder="Search invoice, child, parent…"
        />
        <div className="client-inv__filter-head-actions">
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            aria-expanded={filtersOpen}
            onClick={() => setFiltersOpen((v) => !v)}
          >
            {filtersOpen ? 'Hide filters' : 'Show filters'}
            {activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
          </button>
          {activeFilterCount > 0 ? (
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={clearFilters}>
              Clear filters
            </button>
          ) : null}
        </div>
      </div>

      <AdminCollapsibleFilters
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        collapseOnDesktop
        quickSearch={
          <AdminSearchInput
            value={filters.search}
            onChange={(value) => patchFilters({ search: value })}
            placeholder="Search invoice, child, parent…"
          />
        }
        activeChips={[
          filters.year && `Year ${filters.year}`,
          filters.month && filters.month,
          filters.module && filters.module,
          filters.status && filters.status.replaceAll('_', ' '),
          filters.invoiceType && filters.invoiceType,
        ].filter(Boolean)}
        activeCount={activeFilterCount}
      >
      <div
        className={`client-inv__filters client-inv__filters--grid${!filtersOpen ? ' client-inv__filters--collapsed' : ''}`}
        role="region"
        aria-label="Invoice filters"
      >
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Year</span>
          <select
            className="client-inv__filter-input"
            value={filters.year}
            onChange={(e) => patchFilters({ year: e.target.value, month: '' })}
          >
            <option value="">All years</option>
            {(filterOptions?.years || [new Date().getFullYear()]).map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Month</span>
          <select
            className="client-inv__filter-input"
            value={filters.month}
            onChange={(e) => patchFilters({ month: e.target.value, year: '' })}
          >
            <option value="">All months</option>
            {monthOptions.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">From</span>
          <input
            type="date"
            className="client-inv__filter-input"
            value={filters.dateFrom}
            onChange={(e) => patchFilters({ dateFrom: e.target.value })}
          />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">To</span>
          <input
            type="date"
            className="client-inv__filter-input"
            value={filters.dateTo}
            onChange={(e) => patchFilters({ dateTo: e.target.value })}
          />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Service</span>
          <ServiceFilterSelect
            className="client-inv__filter-input"
            value={filters.module}
            onChange={(v) => patchFilters({ module: v })}
          />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Invoice type</span>
          <select
            className="client-inv__filter-input"
            value={filters.invoiceType}
            onChange={(e) => patchFilters({ invoiceType: e.target.value })}
          >
            {INVOICE_TYPES.map((o) => (
              <option key={o.value || 'all'} value={o.value}>{o.label}</option>
            ))}
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Status</span>
          <select
            className="client-inv__filter-input"
            value={filters.status}
            onChange={(e) => patchFilters({ status: e.target.value })}
          >
            <option value="">All statuses</option>
            {CLIENT_INVOICE_STATUSES.map((s) => (
              <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>
            ))}
          </select>
        </label>
        <div className="client-inv__filter-field client-inv__filter-field--search client-inv__filter-field--search-compact admin-mobile-only">
          <AdminSearchInput
            value={filters.search}
            onChange={(value) => patchFilters({ search: value })}
            placeholder="Search invoice, child, parent…"
          />
        </div>
      </div>
      </AdminCollapsibleFilters>

      <div className="client-inv__toolbar">
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={!canWriteBilling}
          onClick={() => navigate('/admin/invoices/compose')}
        >
          Compose invoice
        </button>
        <Link to="/admin/invoices/compose?queue=not_invoiced_this_month" className="admin-btn admin-btn--ghost admin-btn--sm">
          Not invoiced this month
        </Link>
        <div className="admin-btn-group">
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadExport(`/api/v1/admin/client-billing/invoices/export/xlsx${buildClientInvoiceQuery(filters)}`, 'client_invoices.xlsx')}>
            Export Excel
          </button>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadExport(`/api/v1/admin/client-billing/invoices/export/pdf${buildClientInvoiceQuery(filters)}`, 'client_invoices.pdf')}>
            Export PDF
          </button>
        </div>
      </div>

      {loading ? (
        <div className="admin-skeleton" />
      ) : invoices.length === 0 ? (
        <AdminEmptyState title="No client invoices" description="Raise an invoice for a family case to get started." />
      ) : (
        <AdminDataList
          desktop={
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Client</th>
                    <th>Case</th>
                    <th>Month</th>
                    <th>Type</th>
                    <th>Total</th>
                    <th>Balance</th>
                    <th>Due</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((inv) => (
                    <tr key={inv.id}>
                      <td>
                        <span className="admin-table__primary">{inv.invoiceNumber}</span>
                      </td>
                      <td>
                        <span className="admin-table__primary">{inv.childName}</span>
                        <span className="admin-table__meta">{inv.parentName}</span>
                      </td>
                      <td>{inv.caseId}</td>
                      <td>{inv.billingMonth}</td>
                      <td>
                        <span className="admin-chip">{inv.invoiceType}</span>
                      </td>
                      <td>{formatCurrency(inv.totalInr)}</td>
                      <td>
                        <strong style={{ color: inv.balanceInr > 0 ? '#b45309' : '#047857' }}>
                          {formatCurrency(inv.balanceInr)}
                        </strong>
                      </td>
                      <td>{inv.dueDate || '—'}</td>
                      <td>
                        <span className={statusPillClass(displayStatus(inv))}>{displayStatus(inv)}</span>
                      </td>
                      <td>
                        <div className="admin-table__actions">
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setViewId(inv.id)}>
                            View
                          </button>
                          {canWriteBilling && (inv.status === 'DRAFT' || inv.status === 'GENERATED') ? (
                            <button
                              type="button"
                              className="admin-btn admin-btn--primary admin-btn--sm"
                              onClick={async () => {
                                await apiFetch(`/api/v1/admin/client-billing/invoices/${inv.id}/notify-parent`, { method: 'POST' })
                                load()
                              }}
                            >
                              Send
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          mobile={invoices.map((inv) => (
            <li key={inv.id}>
              <AdminTaskCard
                title={inv.invoiceNumber}
                meta={`${inv.childName} · ${inv.billingMonth || '—'}`}
                badges={<span className={statusPillClass(displayStatus(inv))}>{displayStatus(inv)}</span>}
                actions={
                  <>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setViewId(inv.id)}>
                      View
                    </button>
                    {canWriteBilling && (inv.status === 'DRAFT' || inv.status === 'GENERATED') ? (
                      <button
                        type="button"
                        className="admin-btn admin-btn--primary admin-btn--sm"
                        onClick={async () => {
                          await apiFetch(`/api/v1/admin/client-billing/invoices/${inv.id}/notify-parent`, { method: 'POST' })
                          load()
                        }}
                      >
                        Send
                      </button>
                    ) : null}
                  </>
                }
              >
                <p style={{ margin: 0 }}>
                  Balance{' '}
                  <strong style={{ color: inv.balanceInr > 0 ? '#b45309' : '#047857' }}>
                    {formatCurrency(inv.balanceInr)}
                  </strong>
                  {' '}
                  of {formatCurrency(inv.totalInr)}
                  {inv.dueDate ? ` · Due ${inv.dueDate}` : ''}
                </p>
              </AdminTaskCard>
            </li>
          ))}
        />
      )}

      {viewId ? (
        <InvoiceDetailDrawer
          invoiceId={viewId}
          onClose={() => setViewId(null)}
          onRefresh={load}
          canWriteBilling={canWriteBilling}
        />
      ) : null}
    </div>
  )
}
