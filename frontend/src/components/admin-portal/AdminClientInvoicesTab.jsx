import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch, getTokens } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  buildClientInvoiceQuery,
  CLIENT_INVOICE_STATUSES,
  INVOICE_TYPES,
  parseClientInvoiceFilters,
  writeClientInvoiceFiltersToParams,
} from '../../lib/invoiceFilters.js'
import { AdminEmptyState, AdminSearchInput, ServiceFilterSelect, formatCurrency } from './ui/index.js'
import { InvoiceLineItemEditor } from './InvoiceLineItemEditor.jsx'
import './admin-client-invoices.css'
import './admin-client-invoices-composer.css'

const API_URL = import.meta.env.VITE_API_URL || ''

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

async function downloadExport(path, filename) {
  const { access } = getTokens()
  const res = await fetch(`${API_URL}${path}`, {
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
  const [payMethod, setPayMethod] = useState('UPI')
  const [payRef, setPayRef] = useState('')
  const [resolveId, setResolveId] = useState(null)
  const [resolveNote, setResolveNote] = useState('')
  const [resolveAdj, setResolveAdj] = useState('')
  const [rejectPayId, setRejectPayId] = useState(null)
  const [rejectPayNote, setRejectPayNote] = useState('')
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
          method: payMethod,
          reference: payRef || null,
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
      await apiFetch(`/api/v1/admin/client-billing/payments/${paymentId}/confirm`, { method: 'POST' })
      load()
      onRefresh()
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
              <div>
                <span className={statusPillClass(displayStatus(detail))}>{displayStatus(detail)}</span>
                <div className="client-inv__amount-grid" style={{ marginTop: 16 }}>
                  <div><span style={{ color: '#64748b' }}>Total</span><br /><strong>{formatCurrency(detail.totalInr)}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Balance</span><br /><strong>{formatCurrency(detail.balanceInr)}</strong></div>
                  <div><span style={{ color: '#64748b' }}>Paid</span><br />{formatCurrency(detail.amountPaidInr)}</div>
                  <div><span style={{ color: '#64748b' }}>Due</span><br />{detail.dueDate || '—'}</div>
                </div>
                <p style={{ fontSize: '0.85rem', marginTop: 12 }}>Parent: {detail.parentName} ({detail.parentEmail})</p>
                <p style={{ fontSize: '0.85rem', marginTop: 8 }}>
                  {detail.invoiceType} · {detail.serviceType} · Tax {formatCurrency(detail.taxInr)}
                  {detail.gatewayEnabled ? ' · Payment gateway on' : ''}
                </p>
                {detail.notes ? <p style={{ fontSize: '0.85rem', color: '#64748b' }}>{detail.notes}</p> : null}
                {canWriteBilling ? (
                <div className="admin-btn-group" style={{ marginTop: 16, flexWrap: 'wrap' }}>
                  {detail.status === 'DRAFT' ? (
                    <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={acting} onClick={markGenerated}>
                      Mark ready
                    </button>
                  ) : null}
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={sendToClient}>
                    Send to client
                  </button>
                  {detail.balanceInr > 0 ? (
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setPaymentOpen(true)}>
                      Record payment
                    </button>
                  ) : null}
                </div>
                ) : (
                  <p className="admin-muted" style={{ marginTop: 12, fontSize: '0.8rem' }}>View-only billing access.</p>
                )}
              </div>
            ) : null}

            {tab === 'lines' ? (
              <InvoiceLineItemEditor
                invoiceId={invoiceId}
                lines={detail.lines || []}
                canWrite={canWriteBilling && detail.status === 'DRAFT'}
                onUpdated={load}
              />
            ) : null}

            {tab === 'payments' ? (
              <div>
                <h4 style={{ fontSize: '0.85rem', margin: '0 0 8px' }}>Payments</h4>
                {(detail.payments || []).length === 0 ? (
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No payments recorded.</p>
                ) : (
                  detail.payments.map((p) => (
                    <div key={p.id} className="client-inv__dispute-card" style={{ marginBottom: 8 }}>
                      <p style={{ fontSize: '0.85rem', margin: '4px 0' }}>
                        {formatCurrency(p.amountInr)} · {p.method} ·{' '}
                        {(p.paymentStatus || 'confirmed').replaceAll('_', ' ')}
                        {p.paidAt ? ` · ${p.paidAt.slice(0, 10)}` : ''}
                      </p>
                      {p.hasProof ? (
                        <a
                          href={`${import.meta.env.VITE_API_URL || ''}/api/v1/admin/client-billing/payments/${p.id}/proof`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ fontSize: '0.8rem' }}
                        >
                          View proof
                        </a>
                      ) : null}
                      {canWriteBilling && p.paymentStatus === 'pending_review' ? (
                        rejectPayId === p.id ? (
                          <div style={{ marginTop: 8 }}>
                            <textarea
                              className="client-inv__filter-input"
                              style={{ width: '100%', minHeight: 50 }}
                              placeholder="Reason if rejecting"
                              value={rejectPayNote}
                              onChange={(e) => setRejectPayNote(e.target.value)}
                            />
                            <div className="admin-btn-group" style={{ marginTop: 8 }}>
                              <button
                                type="button"
                                className="admin-btn admin-btn--primary admin-btn--sm"
                                disabled={acting}
                                onClick={() => confirmPaymentClaim(p.id)}
                              >
                                Confirm payment
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--sm"
                                disabled={acting || !rejectPayNote.trim()}
                                onClick={() => rejectPaymentClaim(p.id)}
                              >
                                Reject
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="admin-btn-group" style={{ marginTop: 8 }}>
                            <button
                              type="button"
                              className="admin-btn admin-btn--primary admin-btn--sm"
                              disabled={acting}
                              onClick={() => confirmPaymentClaim(p.id)}
                            >
                              Confirm
                            </button>
                            <button type="button" className="admin-btn admin-btn--sm" onClick={() => setRejectPayId(p.id)}>
                              Reject…
                            </button>
                          </div>
                        )
                      ) : null}
                      {p.rejectionNote ? (
                        <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 4 }}>{p.rejectionNote}</p>
                      ) : null}
                    </div>
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
            <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} value={payAmount} onChange={(e) => setPayAmount(e.target.value)} required />
            <select className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} value={payMethod} onChange={(e) => setPayMethod(e.target.value)}>
              {['UPI', 'BANK_TRANSFER', 'CASH', 'CHEQUE', 'GATEWAY'].map((m) => (
                <option key={m} value={m}>{m.replaceAll('_', ' ')}</option>
              ))}
            </select>
            <input className="client-inv__filter-input" style={{ width: '100%', marginBottom: 8 }} placeholder="Reference" value={payRef} onChange={(e) => setPayRef(e.target.value)} />
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
      </div>
    </div>
  )
}

export function AdminClientInvoicesTab({
  highlightClaimsPending = false,
  claimsOnly = false,
  openInvoiceId = null,
}) {
  const navigate = useNavigate()
  const { canWriteBilling } = useModuleWrite()
  const [searchParams, setSearchParams] = useSearchParams()
  const [summary, setSummary] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(() => parseClientInvoiceFilters(searchParams))
  const [filterOptions, setFilterOptions] = useState(null)
  const [viewId, setViewId] = useState(openInvoiceId ? Number(openInvoiceId) : null)

  useEffect(() => {
    apiFetch('/api/v1/admin/client-billing/invoices/filter-options')
      .then(setFilterOptions)
      .catch(() => setFilterOptions(null))
  }, [])

  const load = useCallback(() => {
    const qs = buildClientInvoiceQuery({
      ...filters,
      claimsPending: claimsOnly || filters.claimsPending,
    })
    setLoading(true)
    Promise.all([
      apiFetch('/api/v1/admin/client-billing/summary'),
      apiFetch(`/api/v1/admin/client-billing/invoices${qs}`),
    ])
      .then(([s, list]) => {
        setSummary(s)
        setInvoices(Array.isArray(list) ? list : [])
      })
      .catch(() => {
        setSummary(null)
        setInvoices([])
      })
      .finally(() => setLoading(false))
  }, [filters, claimsOnly])

  useEffect(() => {
    load()
  }, [load])

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

  return (
    <div className="client-inv">
      {highlightClaimsPending && pendingClaimsCount > 0 ? (
        <p className="admin-alert admin-alert--warning" style={{ marginBottom: 12 }}>
          Showing invoices with payment claims awaiting review. Open an invoice to confirm or reject each claim.
        </p>
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

      <div className="client-inv__filters client-inv__filters--grid">
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
        <div className="client-inv__filter-field client-inv__filter-field--search client-inv__filter-field--search-compact">
          <AdminSearchInput
            value={filters.search}
            onChange={(value) => patchFilters({ search: value })}
            placeholder="Search invoice, child, parent…"
          />
        </div>
      </div>

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
                    <strong style={{ color: inv.balanceInr > 0 ? '#b45309' : '#047857' }}>{formatCurrency(inv.balanceInr)}</strong>
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
