import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch, getTokens } from '../../lib/apiClient.js'
import './parent-payments.css'

const API_URL = import.meta.env.VITE_API_URL || ''

const PAYMENT_TABS = [
  { id: '', label: 'All invoices' },
  { id: 'needs_payment', label: 'Needs payment' },
  { id: 'paid', label: 'Paid' },
  { id: 'disputed', label: 'Disputed' },
]

const DISPUTE_REASONS = [
  { value: 'not_attended', label: 'Session not attended' },
  { value: 'therapist_late', label: 'Therapist was late' },
  { value: 'duplicate_billing', label: 'Duplicate billing' },
  { value: 'incorrect_amount', label: 'Incorrect amount' },
  { value: 'wrong_package_deduction', label: 'Wrong package deduction' },
  { value: 'other', label: 'Other' },
]

function formatInr(n) {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(
    n ?? 0,
  )
}

function formatMonth(key) {
  if (!key) return '—'
  const m = key.match(/^(\d{4})-(\d{2})$/)
  if (!m) return key
  const d = new Date(Number(m[1]), Number(m[2]) - 1, 1)
  return d.toLocaleDateString('en-IN', { month: 'short', year: 'numeric' })
}

function statusClass(bucket) {
  if (bucket === 'paid') return 'completed'
  if (bucket === 'disputed') return 'warning'
  if (bucket === 'partial') return 'in-progress'
  return 'pending'
}

export function ParentBillingPage() {
  const [dashboard, setDashboard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [month, setMonth] = useState('')
  const [caseId, setCaseId] = useState('')
  const [service, setService] = useState('')
  const [paymentTab, setPaymentTab] = useState('')
  const [selected, setSelected] = useState(null)
  const [lineDetail, setLineDetail] = useState(null)
  const [disputeOpen, setDisputeOpen] = useState(false)
  const [disputeReason, setDisputeReason] = useState('incorrect_amount')
  const [disputeMessage, setDisputeMessage] = useState('')
  const [disputeLineId, setDisputeLineId] = useState(null)
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (month) params.set('month', month)
      if (caseId) params.set('case_id', caseId)
      if (service) params.set('service', service)
      if (paymentTab) params.set('payment_bucket', paymentTab)
      const qs = params.toString()
      const data = await apiFetch(`/api/v1/parent/billing/dashboard${qs ? `?${qs}` : ''}`)
      setDashboard(data)
    } catch (err) {
      setError(err.message || 'Could not load billing')
      setDashboard(null)
    } finally {
      setLoading(false)
    }
  }, [month, caseId, service, paymentTab])

  useEffect(() => {
    load()
  }, [load])

  const invoices = dashboard?.invoices || []
  const dueInvoices = useMemo(
    () => invoices.filter((i) => ['unpaid', 'partial'].includes(i.paymentBucket)),
    [invoices],
  )

  async function openInvoice(id) {
    setLineDetail(null)
    setDisputeOpen(false)
    try {
      const detail = await apiFetch(`/api/v1/parent/billing/invoices/${id}`)
      setSelected(detail)
    } catch (err) {
      setError(err.message || 'Could not load invoice')
    }
  }

  async function openLine(lineId) {
    try {
      const detail = await apiFetch(`/api/v1/parent/billing/lines/${lineId}/session`)
      setLineDetail(detail)
    } catch (err) {
      setError(err.message || 'Could not load session')
    }
  }

  async function downloadPdf(invoiceId) {
    const { access } = getTokens()
    const url = `${API_URL}/api/v1/parent/billing/invoices/${invoiceId}/print`
    const res = await fetch(url, { headers: access ? { Authorization: `Bearer ${access}` } : {} })
    if (!res.ok) {
      setError('Could not download invoice')
      return
    }
    const html = await res.text()
    const w = window.open('', '_blank')
    if (w) {
      w.document.write(html)
      w.document.close()
      w.print()
    }
  }

  async function submitDispute() {
    if (!selected || disputeMessage.trim().length < 10) return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}/disputes`, {
        method: 'POST',
        body: JSON.stringify({
          reason_code: disputeReason,
          message: disputeMessage.trim(),
          line_id: disputeLineId,
        }),
      })
      setMessage('Dispute submitted. Finance will review and update you.')
      setDisputeOpen(false)
      setSelected(null)
      await load()
    } catch (err) {
      setError(err.message || 'Could not submit dispute')
    } finally {
      setActing(false)
    }
  }

  const opts = dashboard?.filterOptions || {}
  const summary = dashboard?.summary || {}
  const showDueStrip = dueInvoices.length > 0 && (paymentTab === '' || paymentTab === 'needs_payment')
  const urgentBanner = (summary.overdueCount || 0) > 0

  return (
    <div className="parent-pay">
      <header className="parent-pay__hero">
        <h1>Payments</h1>
        <p>Review invoices raised by your care team, download statements, and keep track of what is due.</p>
      </header>

      {error ? (
        <p className="parent-pay__alert parent-pay__alert--error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="parent-pay__alert parent-pay__alert--success">{message}</p> : null}

      {(summary.needsPaymentCount || 0) > 0 && (summary.dueTotalInr || 0) > 0 ? (
        <section className={`parent-pay__banner ${urgentBanner ? 'parent-pay__banner--urgent' : ''}`}>
          <div>
            <h2>{urgentBanner ? 'Payment overdue' : 'Payment required'}</h2>
            <p>
              {urgentBanner
                ? `You have ${summary.overdueCount} invoice(s) past the due date. Please arrange payment or contact your coordinator if you need help.`
                : `You have ${summary.needsPaymentCount} invoice(s) with an outstanding balance. Open an invoice below to review line items and payment options.`}
            </p>
          </div>
          <div className="parent-pay__banner-actions">
            <span style={{ fontSize: '0.7rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>
              Total due
            </span>
            <strong>{formatInr(summary.dueTotalInr)}</strong>
          </div>
        </section>
      ) : null}

      {dashboard?.summary ? (
        <ul className="parent-pay__stats" aria-label="Payment summary">
          <li className="parent-pay__stat parent-pay__stat--due">
            <strong>{formatInr(summary.dueTotalInr)}</strong>
            <span>Balance due</span>
          </li>
          <li className="parent-pay__stat">
            <strong>{summary.needsPaymentCount ?? 0}</strong>
            <span>Needs payment</span>
          </li>
          <li className="parent-pay__stat parent-pay__stat--overdue">
            <strong>{summary.overdueCount ?? 0}</strong>
            <span>Overdue</span>
          </li>
          <li className="parent-pay__stat">
            <strong>{summary.invoiceCount ?? 0}</strong>
            <span>All invoices</span>
          </li>
          <li className="parent-pay__stat">
            <strong>{summary.activePackages ?? 0}</strong>
            <span>Active packages</span>
          </li>
        </ul>
      ) : null}

      {dashboard?.packages?.length > 0 ? (
        <section className="parent-pay__packages parent-pay__table-card">
          <div className="parent-pay__table-head">
            <h3>Session packages</h3>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Package</th>
                  <th>Child</th>
                  <th>Total</th>
                  <th>Used</th>
                  <th>Remaining</th>
                  <th>Expiry</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.packages.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.childName}</td>
                    <td>{p.totalSessions}</td>
                    <td>{p.usedSessions}</td>
                    <td>
                      <strong>{p.remainingSessions}</strong>
                    </td>
                    <td>{p.validityEnd ? new Date(p.validityEnd).toLocaleDateString('en-IN') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <nav className="parent-pay__tabs" aria-label="Invoice payment status">
        {PAYMENT_TABS.map((t) => (
          <button
            key={t.id || 'all'}
            type="button"
            className={`parent-pay__tab ${paymentTab === t.id ? 'is-active' : ''}`}
            onClick={() => setPaymentTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="parent-pay__refine" aria-label="Refine invoice list">
        <label>
          Month
          <select value={month} onChange={(e) => setMonth(e.target.value)}>
            <option value="">All months</option>
            {(opts.months || []).map((m) => (
              <option key={m} value={m}>
                {formatMonth(m)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Child / case
          <select value={caseId} onChange={(e) => setCaseId(e.target.value)}>
            <option value="">All</option>
            {(opts.children || []).map((c) => (
              <option key={c.caseDbId} value={String(c.caseDbId)}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Service
          <select value={service} onChange={(e) => setService(e.target.value)}>
            <option value="">All services</option>
            {(opts.services || []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {showDueStrip ? (
        <section className="parent-pay__due-section" aria-label="Invoices that need payment">
          <h3>Pay first</h3>
          <div className="parent-pay__due-grid">
            {dueInvoices.map((inv) => (
              <article key={inv.id} className={`parent-pay__due-card ${inv.isOverdue ? 'is-overdue' : ''}`}>
                <div className="parent-pay__due-card-top">
                  <div>
                    <h4>{inv.invoiceNumber}</h4>
                    <p className="parent-pay__due-meta">
                      {inv.childName} · {formatMonth(inv.billingMonth)}
                    </p>
                  </div>
                  {inv.isOverdue ? (
                    <span className="parent-pay__badge parent-pay__badge--overdue">Overdue</span>
                  ) : inv.paymentBucket === 'partial' ? (
                    <span className="parent-pay__badge parent-pay__badge--partial">Partial</span>
                  ) : null}
                </div>
                {inv.dueDate ? (
                  <p className="parent-pay__due-meta">Due {new Date(inv.dueDate).toLocaleDateString('en-IN')}</p>
                ) : null}
                <div className="parent-pay__due-balance">{formatInr(inv.balanceInr)} due</div>
                <div className="parent-pay__due-actions">
                  <button type="button" onClick={() => openInvoice(inv.id)}>
                    View &amp; pay
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="parent-pay__table-card">
        <div className="parent-pay__table-head">
          <h3>Invoice list</h3>
          <span>{loading ? 'Loading…' : `${invoices.length} shown`}</span>
        </div>
        {loading && !dashboard ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>Loading…</p>
        ) : invoices.length === 0 ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>No invoices match these filters.</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Invoice</th>
                  <th>Month</th>
                  <th>Child</th>
                  <th>Total</th>
                  <th>Balance</th>
                  <th>Due</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.invoiceNumber}</td>
                    <td>{formatMonth(inv.billingMonth)}</td>
                    <td>{inv.childName}</td>
                    <td>{formatInr(inv.totalInr)}</td>
                    <td>{formatInr(inv.balanceInr)}</td>
                    <td>
                      {inv.dueDate ? new Date(inv.dueDate).toLocaleDateString('en-IN') : '—'}
                      {inv.isOverdue && inv.balanceInr > 0 ? (
                        <span className="parent-pay__badge parent-pay__badge--overdue" style={{ marginLeft: 6 }}>
                          Overdue
                        </span>
                      ) : null}
                    </td>
                    <td>
                      <span className={`status ${statusClass(inv.paymentBucket)}`}>{inv.paymentBucket}</span>
                    </td>
                    <td>
                      <button type="button" onClick={() => openInvoice(inv.id)}>
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {selected ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Invoice detail"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.45)',
            zIndex: 60,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              marginTop: 'auto',
              maxHeight: '94vh',
              background: '#fff',
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>{selected.invoiceNumber}</h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7280' }}>
                  {selected.childName} · {selected.caseId} · {formatMonth(selected.billingMonth)}
                </p>
                <p style={{ margin: '8px 0 0', fontSize: 13, display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                  <strong>{selected.invoiceType}</strong>
                  {selected.dueDate ? (
                    <span>
                      Due {new Date(selected.dueDate).toLocaleDateString('en-IN')}
                      {selected.isOverdue && selected.balanceInr > 0 ? (
                        <span className="parent-pay__badge parent-pay__badge--overdue" style={{ marginLeft: 6 }}>
                          Overdue
                        </span>
                      ) : null}
                    </span>
                  ) : null}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setSelected(null)
                  setLineDetail(null)
                  setDisputeOpen(false)
                }}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              <p style={{ margin: '0 0 12px', fontSize: 13, color: '#475569' }}>
                Payments are usually coordinated with your case coordinator (UPI, bank transfer, or as agreed). Use
                &quot;Download PDF&quot; for your records.
              </p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Therapist</th>
                      <th>Service</th>
                      <th>Status</th>
                      <th>Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(selected.lines || []).map((line) => (
                      <tr key={line.id}>
                        <td>{new Date(line.sessionDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</td>
                        <td>{line.therapistName}</td>
                        <td>{line.serviceLabel}</td>
                        <td>
                          {line.sessionStatus}
                          {line.packageDeducted ? ' · Pack' : ''}
                        </td>
                        <td>
                          <button
                            type="button"
                            style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline' }}
                            onClick={() => openLine(line.id)}
                          >
                            {formatInr(line.amountInr)}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <dl style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 14 }}>
                <div>
                  <dt style={{ color: '#6b7280' }}>Subtotal</dt>
                  <dd style={{ margin: 0 }}>{formatInr(selected.subtotalInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Tax</dt>
                  <dd style={{ margin: 0 }}>{formatInr(selected.taxInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Discount</dt>
                  <dd style={{ margin: 0 }}>−{formatInr(selected.discountInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Package deduction</dt>
                  <dd style={{ margin: 0 }}>−{formatInr(selected.packageDeductionInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Adjustments</dt>
                  <dd style={{ margin: 0 }}>{formatInr(selected.adjustmentInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Total payable</dt>
                  <dd style={{ margin: 0, fontWeight: 700 }}>{formatInr(selected.totalInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Paid</dt>
                  <dd style={{ margin: 0 }}>{formatInr(selected.amountPaidInr)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#6b7280' }}>Balance</dt>
                  <dd style={{ margin: 0, fontWeight: 700 }}>{formatInr(selected.balanceInr)}</dd>
                </div>
              </dl>

              {lineDetail ? (
                <section style={{ marginTop: 16, padding: 12, background: '#f9fafb', borderRadius: 8 }}>
                  <h3 style={{ marginTop: 0, fontSize: 15 }}>Session detail</h3>
                  <p style={{ margin: '4px 0' }}>
                    <strong>{lineDetail.therapistName}</strong> · {lineDetail.sessionStatus}
                  </p>
                  {lineDetail.attendance ? <p style={{ margin: '4px 0' }}>Attendance: {lineDetail.attendance}</p> : null}
                  {lineDetail.activitiesSummary ? (
                    <p style={{ margin: '8px 0 0', whiteSpace: 'pre-wrap' }}>{lineDetail.activitiesSummary}</p>
                  ) : null}
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginTop: 8 }} onClick={() => setLineDetail(null)}>
                    Close session
                  </button>
                </section>
              ) : null}

              {disputeOpen ? (
                <section style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Raise a dispute</h3>
                  <select value={disputeReason} onChange={(e) => setDisputeReason(e.target.value)} style={{ width: '100%', marginBottom: 8, padding: 8 }}>
                    {DISPUTE_REASONS.map((r) => (
                      <option key={r.value} value={r.value}>
                        {r.label}
                      </option>
                    ))}
                  </select>
                  <select
                    value={disputeLineId ?? ''}
                    onChange={(e) => setDisputeLineId(e.target.value ? Number(e.target.value) : null)}
                    style={{ width: '100%', marginBottom: 8, padding: 8 }}
                  >
                    <option value="">Whole invoice</option>
                    {(selected.lines || []).map((l) => (
                      <option key={l.id} value={l.id}>
                        Line: {l.sessionDate} — {l.sessionStatus}
                      </option>
                    ))}
                  </select>
                  <textarea
                    value={disputeMessage}
                    onChange={(e) => setDisputeMessage(e.target.value)}
                    rows={4}
                    placeholder="Describe the issue (min 10 characters)"
                    style={{ width: '100%', padding: 8 }}
                  />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button type="button" className="admin-btn admin-btn--primary" disabled={acting || disputeMessage.trim().length < 10} onClick={submitDispute}>
                      Submit dispute
                    </button>
                    <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setDisputeOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </section>
              ) : null}

              {(selected.disputes || []).length > 0 ? (
                <section style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Dispute history</h3>
                  <ul className="log-list">
                    {selected.disputes.map((d) => (
                      <li key={d.id}>
                        <span className={`status ${d.status === 'resolved' ? 'completed' : 'pending'}`}>{d.status}</span>
                        <p style={{ margin: '4px 0' }}>{d.message}</p>
                        {d.adminResolution ? <p style={{ fontSize: 13, color: '#6b7280' }}>Response: {d.adminResolution}</p> : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>

            <div style={{ padding: 12, borderTop: '1px solid #e5e7eb', display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              <button type="button" className="admin-btn admin-btn--secondary" onClick={() => downloadPdf(selected.id)}>
                Download PDF
              </button>
              {selected.paymentBucket !== 'paid' && selected.paymentBucket !== 'disputed' ? (
                <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setDisputeOpen(true)}>
                  Dispute invoice
                </button>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
