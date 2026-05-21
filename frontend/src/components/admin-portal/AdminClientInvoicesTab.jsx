import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch, getTokens } from '../../lib/apiClient.js'
import { AdminEmptyState, AdminSearchInput, formatCurrency } from './ui/index.js'
import './admin-client-invoices.css'

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

function buildQuery(filters) {
  const p = new URLSearchParams()
  if (filters.month) p.set('month', filters.month)
  if (filters.caseId) p.set('case_id', filters.caseId)
  if (filters.status) p.set('status', filters.status)
  if (filters.module) p.set('module', filters.module)
  if (filters.search) p.set('search', filters.search)
  const qs = p.toString()
  return qs ? `?${qs}` : ''
}

// ── Raise invoice wizard ───────────────────────────────────────────────────────
function RaiseInvoiceWizard({ onClose, onDone }) {
  const [step, setStep] = useState(1)
  const [cases, setCases] = useState([])
  const [familySearch, setFamilySearch] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const [invoiceType, setInvoiceType] = useState('POSTPAID')
  const [billingMonth, setBillingMonth] = useState(() => {
    const d = new Date()
    return d.toLocaleString('en-US', { month: 'short', year: 'numeric' })
  })
  const [dueDate, setDueDate] = useState('')
  const [notes, setNotes] = useState('')
  const [discount, setDiscount] = useState('0')
  const [lines, setLines] = useState([
    { session_date: new Date().toISOString().slice(0, 10), therapist_name: '', service_label: '', amount_inr: '' },
  ])
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    apiFetch('/api/v1/cases?page_size=100')
      .then((data) => {
        const rows = data?.items ?? (Array.isArray(data) ? data : [])
        setCases(rows)
      })
      .catch(() => setCases([]))
  }, [])

  const caseOptions = useMemo(() => {
    const q = familySearch.trim().toLowerCase()
    return cases.filter((c) => {
      if (!q) return true
      return (
        c.case_code?.toLowerCase().includes(q) ||
        c.child_name?.toLowerCase().includes(q) ||
        c.service_type?.toLowerCase().includes(q)
      )
    }).map((c) => ({
      caseDbId: c.id,
      caseCode: c.case_code,
      childName: c.child_name,
      serviceType: c.service_type,
      productModule: c.product_module,
    }))
  }, [cases, familySearch])

  const lineTotal = lines.reduce((s, l) => s + (Number(l.amount_inr) || 0), 0)
  const totalAfterDiscount = Math.max(0, lineTotal - (Number(discount) || 0))

  function addLine() {
    setLines((prev) => [
      ...prev,
      { session_date: new Date().toISOString().slice(0, 10), therapist_name: '', service_label: '', amount_inr: '' },
    ])
  }

  async function submit() {
    setErr('')
    setSubmitting(true)
    try {
      const payload = {
        case_id: selectedCase.caseDbId,
        invoice_type: invoiceType,
        billing_month: billingMonth,
        due_date: dueDate || null,
        notes: notes || null,
        discount_inr: Number(discount) || 0,
        lines: lines.map((l) => ({
          session_date: l.session_date,
          therapist_name: l.therapist_name.trim(),
          service_label: l.service_label.trim() || selectedCase.serviceType,
          session_status: 'COMPLETED',
          amount_inr: Number(l.amount_inr),
        })),
      }
      await apiFetch('/api/v1/admin/client-billing/invoices', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
      onDone()
      onClose()
    } catch (e) {
      setErr(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="client-inv__overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="client-inv__wizard" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: '0 0 16px' }}>Raise client invoice</h3>
        <div className="client-inv__wizard-steps">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className={`client-inv__wizard-step ${step === n ? 'is-active' : ''} ${step > n ? 'is-done' : ''}`}
            >
              {n === 1 ? 'Case' : n === 2 ? 'Details' : 'Line items'}
            </div>
          ))}
        </div>

        {step === 1 ? (
          <>
            <AdminSearchInput value={familySearch} onChange={(e) => setFamilySearch(e.target.value)} placeholder="Search case, child, parent…" />
            <div style={{ maxHeight: 280, overflowY: 'auto', marginTop: 12 }}>
              {caseOptions.length === 0 ? (
                <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>No cases found.</p>
              ) : (
                caseOptions.map((c) => (
                  <button
                    key={c.caseDbId}
                    type="button"
                    onClick={() => setSelectedCase(c)}
                    style={{
                      display: 'block',
                      width: '100%',
                      textAlign: 'left',
                      padding: '10px 12px',
                      marginBottom: 6,
                      borderRadius: 10,
                      border: selectedCase?.caseDbId === c.caseDbId ? '2px solid #6366f1' : '1px solid #e2e8f0',
                      background: selectedCase?.caseDbId === c.caseDbId ? '#eef2ff' : '#fff',
                      cursor: 'pointer',
                    }}
                  >
                    <strong>{c.caseCode}</strong> — {c.childName}
                    <span style={{ display: 'block', fontSize: '0.78rem', color: '#64748b' }}>{c.parentName}</span>
                  </button>
                ))
              )}
            </div>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--primary" disabled={!selectedCase} onClick={() => setStep(2)}>
                Next
              </button>
              <button type="button" className="admin-btn admin-btn--ghost" onClick={onClose}>
                Cancel
              </button>
            </div>
          </>
        ) : null}

        {step === 2 ? (
          <>
            <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
              {selectedCase?.caseCode} — {selectedCase?.childName}
            </p>
            <label style={{ display: 'block', marginBottom: 10 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Invoice type</span>
              <select className="client-inv__filter-input" style={{ width: '100%', marginTop: 4 }} value={invoiceType} onChange={(e) => setInvoiceType(e.target.value)}>
                <option value="PREPAID">Prepaid (start of service)</option>
                <option value="POSTPAID">Postpaid (end of period)</option>
              </select>
            </label>
            <label style={{ display: 'block', marginBottom: 10 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Billing month</span>
              <input className="client-inv__filter-input" style={{ width: '100%', marginTop: 4 }} value={billingMonth} onChange={(e) => setBillingMonth(e.target.value)} placeholder="May 2026" />
            </label>
            <label style={{ display: 'block', marginBottom: 10 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Due date</span>
              <input type="date" className="client-inv__filter-input" style={{ width: '100%', marginTop: 4 }} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </label>
            <label style={{ display: 'block', marginBottom: 10 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Notes (optional)</span>
              <textarea className="client-inv__filter-input" style={{ width: '100%', marginTop: 4, minHeight: 60 }} value={notes} onChange={(e) => setNotes(e.target.value)} />
            </label>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="button" className="admin-btn admin-btn--primary" onClick={() => setStep(3)}>
                Next
              </button>
            </div>
          </>
        ) : null}

        {step === 3 ? (
          <>
            <p style={{ fontSize: '0.85rem', color: '#64748b' }}>Add session lines. Total: {formatCurrency(totalAfterDiscount)}</p>
            {lines.map((l, i) => (
              <div key={i} className="client-inv__line-row">
                <input type="date" className="client-inv__filter-input" value={l.session_date} onChange={(e) => setLines((prev) => prev.map((x, j) => (j === i ? { ...x, session_date: e.target.value } : x)))} />
                <input className="client-inv__filter-input" placeholder="Therapist" value={l.therapist_name} onChange={(e) => setLines((prev) => prev.map((x, j) => (j === i ? { ...x, therapist_name: e.target.value } : x)))} />
                <input className="client-inv__filter-input" placeholder="Service" value={l.service_label} onChange={(e) => setLines((prev) => prev.map((x, j) => (j === i ? { ...x, service_label: e.target.value } : x)))} />
                <input type="number" className="client-inv__filter-input" placeholder="₹" value={l.amount_inr} onChange={(e) => setLines((prev) => prev.map((x, j) => (j === i ? { ...x, amount_inr: e.target.value } : x)))} />
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setLines((prev) => prev.filter((_, j) => j !== i))} disabled={lines.length <= 1}>
                  ×
                </button>
              </div>
            ))}
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginBottom: 12 }} onClick={addLine}>
              + Add line
            </button>
            <label style={{ display: 'block', marginBottom: 12 }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Discount (INR)</span>
              <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginTop: 4 }} value={discount} onChange={(e) => setDiscount(e.target.value)} />
            </label>
            {err ? <p style={{ color: '#b91c1c', fontSize: '0.85rem' }}>{err}</p> : null}
            <div className="admin-btn-group">
              <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setStep(2)}>
                Back
              </button>
              <button type="button" className="admin-btn admin-btn--primary" disabled={submitting || lineTotal <= 0} onClick={submit}>
                {submitting ? 'Creating…' : 'Create draft invoice'}
              </button>
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

// ── View / payment drawers ───────────────────────────────────────────────────
function InvoiceDetailDrawer({ invoiceId, onClose, onRefresh }) {
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

  async function resolveDispute(disputeId, status) {
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/disputes/${disputeId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          resolution: resolveNote,
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
      <div className="client-inv__drawer" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
          <div>
            <h3 style={{ margin: 0 }}>{detail?.invoiceNumber || 'Invoice'}</h3>
            <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: '#64748b' }}>
              {detail?.childName} · {detail?.caseId}
            </p>
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
                {detail.notes ? <p style={{ fontSize: '0.85rem', color: '#64748b' }}>{detail.notes}</p> : null}
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
              </div>
            ) : null}

            {tab === 'lines' ? (
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Therapist</th>
                      <th>Service</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(detail.lines || []).map((l) => (
                      <tr key={l.id}>
                        <td>{l.sessionDate}</td>
                        <td>{l.therapistName}</td>
                        <td>{l.serviceLabel}</td>
                        <td>{formatCurrency(l.amountInr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {tab === 'payments' ? (
              <div>
                <h4 style={{ fontSize: '0.85rem', margin: '0 0 8px' }}>Payments</h4>
                {(detail.payments || []).length === 0 ? (
                  <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No payments recorded.</p>
                ) : (
                  detail.payments.map((p) => (
                    <p key={p.id} style={{ fontSize: '0.85rem', margin: '4px 0' }}>
                      {formatCurrency(p.amountInr)} · {p.method} · {p.paidAt?.slice(0, 10)}
                    </p>
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
                      {d.status === 'OPEN' || d.status === 'UNDER_REVIEW' ? (
                        resolveId === d.id ? (
                          <div style={{ marginTop: 8 }}>
                            <textarea className="client-inv__filter-input" style={{ width: '100%', minHeight: 50 }} placeholder="Resolution note" value={resolveNote} onChange={(e) => setResolveNote(e.target.value)} />
                            <input type="number" className="client-inv__filter-input" style={{ width: '100%', marginTop: 6 }} placeholder="Adjustment INR (optional)" value={resolveAdj} onChange={(e) => setResolveAdj(e.target.value)} />
                            <div className="admin-btn-group" style={{ marginTop: 8 }}>
                              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={() => resolveDispute(d.id, 'RESOLVED')}>
                                Resolve
                              </button>
                              <button type="button" className="admin-btn admin-btn--sm" disabled={acting} onClick={() => resolveDispute(d.id, 'REJECTED')}>
                                Reject
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

        {paymentOpen && detail ? (
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

// ── Main tab ─────────────────────────────────────────────────────────────────
export function AdminClientInvoicesTab() {
  const [summary, setSummary] = useState(null)
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ month: '', status: '', module: '', search: '' })
  const [viewId, setViewId] = useState(null)
  const [showWizard, setShowWizard] = useState(false)

  const load = useCallback(() => {
    const qs = buildQuery(filters)
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
  }, [filters])

  useEffect(() => {
    load()
  }, [load])

  const months = useMemo(() => {
    const set = new Set(invoices.map((i) => i.billingMonth).filter(Boolean))
    return [...set].sort().reverse()
  }, [invoices])

  return (
    <div className="client-inv">
      <div className="client-inv__kpi-grid">
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

      <div className="client-inv__filters">
        <select className="client-inv__filter-input" value={filters.month} onChange={(e) => setFilters((f) => ({ ...f, month: e.target.value }))}>
          <option value="">All months</option>
          {months.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select className="client-inv__filter-input" value={filters.status} onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}>
          <option value="">All statuses</option>
          {['DRAFT', 'GENERATED', 'SENT', 'PARTIALLY_PAID', 'PAID', 'DISPUTED', 'CANCELLED'].map((s) => (
            <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>
          ))}
        </select>
        <AdminSearchInput value={filters.search} onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))} placeholder="Search invoice, child, parent…" />
      </div>

      <div className="client-inv__toolbar">
        <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowWizard(true)}>
          + Raise invoice
        </button>
        <div className="admin-btn-group">
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadExport(`/api/v1/admin/client-billing/invoices/export/xlsx${buildQuery(filters)}`, 'client_invoices.xlsx')}>
            Export Excel
          </button>
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadExport(`/api/v1/admin/client-billing/invoices/export/pdf${buildQuery(filters)}`, 'client_invoices.pdf')}>
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
                      {inv.status === 'DRAFT' || inv.status === 'GENERATED' ? (
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

      {viewId ? <InvoiceDetailDrawer invoiceId={viewId} onClose={() => setViewId(null)} onRefresh={load} /> : null}
      {showWizard ? <RaiseInvoiceWizard onClose={() => setShowWizard(false)} onDone={load} /> : null}
    </div>
  )
}
