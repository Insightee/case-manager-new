import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { apiFetch, apiDownload, apiUpload } from '../../lib/apiClient.js'
import './parent-payments.css'
import './parent-portal-filters.css'
import { ParentFilterField, ParentFilterSelect } from './ParentFilterBar.jsx'

const DISPUTE_STATUS_LABELS = {
  open: 'Submitted — finance will review',
  under_review: 'Finance is reviewing',
  resolved: 'Resolved',
  rejected: 'Closed',
}

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

function formatSessionLineLabel(line) {
  const date = line.sessionDate
    ? new Date(line.sessionDate).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
    : 'Session'
  const status = line.sessionStatus || '—'
  const amount = formatInr(line.amountInr)
  return `${date} · ${status} · ${amount}`
}

function statusClass(bucket) {
  if (bucket === 'paid') return 'completed'
  if (bucket === 'disputed') return 'warning'
  if (bucket === 'partial') return 'in-progress'
  return 'pending'
}

function InvoiceMobileCard({ inv, onOpen }) {
  return (
    <button type="button" className="parent-pay__mobile-card" onClick={() => onOpen(inv.id)}>
      <div className="parent-pay__mobile-card-top">
        <strong>{inv.invoiceNumber}</strong>
        <span className={`status ${statusClass(inv.paymentBucket)}`}>{inv.paymentBucket}</span>
      </div>
      <p className="parent-pay__mobile-card-meta">
        {inv.childName} · {formatMonth(inv.billingMonth)}
      </p>
      <div className="parent-pay__mobile-card-row">
        <span>Balance {formatInr(inv.balanceInr)}</span>
        {inv.dueDate ? (
          <span>
            Due {new Date(inv.dueDate).toLocaleDateString('en-IN')}
            {inv.isOverdue && inv.balanceInr > 0 ? (
              <span className="parent-pay__badge parent-pay__badge--overdue" style={{ marginLeft: 6 }}>
                Overdue
              </span>
            ) : null}
          </span>
        ) : null}
      </div>
    </button>
  )
}

function PackageMobileCard({ pkg }) {
  return (
    <article className="parent-pay__mobile-card parent-pay__mobile-card--package">
      <div className="parent-pay__mobile-card-top">
        <strong>{pkg.name}</strong>
        <span className="parent-pay__badge" style={{ background: '#eef2ff', color: '#3730a3' }}>
          {pkg.remainingSessions} left
        </span>
      </div>
      <p className="parent-pay__mobile-card-meta">{pkg.childName}</p>
      <div className="parent-pay__mobile-card-row">
        <span>Total {pkg.totalSessions}</span>
        <span>Used {pkg.usedSessions}</span>
        <span>
          Expires {pkg.validityEnd ? new Date(pkg.validityEnd).toLocaleDateString('en-IN') : '—'}
        </span>
      </div>
    </article>
  )
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
  const [disputeEntireInvoice, setDisputeEntireInvoice] = useState(true)
  const [disputeLineIds, setDisputeLineIds] = useState([])
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [payAmount, setPayAmount] = useState('')
  const [payMethod, setPayMethod] = useState('UPI')
  const [payRef, setPayRef] = useState('')
  const [payNotes, setPayNotes] = useState('')
  const [payProof, setPayProof] = useState(null)

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
      // #region agent log
      fetch('http://127.0.0.1:7284/ingest/6bb4b18a-59b3-4583-8388-f541aa2607d1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '3264f0' },
        body: JSON.stringify({
          sessionId: '3264f0',
          hypothesisId: 'C',
          location: 'ParentBillingPage.jsx:load',
          message: 'parent billing dashboard ok',
          data: { invoiceCount: data?.invoices?.length ?? 0 },
          timestamp: Date.now(),
          runId: 'browser',
        }),
      }).catch(() => {})
      // #endregion
      setDashboard(data)
    } catch (err) {
      // #region agent log
      fetch('http://127.0.0.1:7284/ingest/6bb4b18a-59b3-4583-8388-f541aa2607d1', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '3264f0' },
        body: JSON.stringify({
          sessionId: '3264f0',
          hypothesisId: 'C',
          location: 'ParentBillingPage.jsx:load',
          message: 'parent billing dashboard failed',
          data: { error: err?.message?.slice(0, 120) },
          timestamp: Date.now(),
          runId: 'browser',
        }),
      }).catch(() => {})
      // #endregion
      setError(err.message || 'Could not load billing')
      setDashboard(null)
    } finally {
      setLoading(false)
    }
  }, [month, caseId, service, paymentTab])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (!selected) return undefined
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [selected])

  const invoices = dashboard?.invoices || []
  const dueInvoices = useMemo(
    () => invoices.filter((i) => ['unpaid', 'partial'].includes(i.paymentBucket)),
    [invoices],
  )

  function resetDisputeForm() {
    setDisputeReason('incorrect_amount')
    setDisputeMessage('')
    setDisputeEntireInvoice(true)
    setDisputeLineIds([])
  }

  function closeInvoiceDialog() {
    setSelected(null)
    setLineDetail(null)
    setDisputeOpen(false)
    setPaymentOpen(false)
    resetDisputeForm()
  }

  function openDisputeForm() {
    resetDisputeForm()
    setPaymentOpen(false)
    setDisputeOpen(true)
  }

  async function openInvoice(id) {
    setLineDetail(null)
    setDisputeOpen(false)
    setPaymentOpen(false)
    resetDisputeForm()
    try {
      const detail = await apiFetch(`/api/v1/parent/billing/invoices/${id}`)
      setSelected(detail)
      setPayAmount(String(detail.balanceInr ?? ''))
    } catch (err) {
      setError(err.message || 'Could not load invoice')
    }
  }

  async function submitPaymentClaim(e) {
    e?.preventDefault?.()
    if (!selected || !payAmount) return
    setActing(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('amount_inr', payAmount)
      fd.append('method', payMethod)
      if (payRef) fd.append('reference', payRef)
      if (payNotes) fd.append('notes', payNotes)
      if (payProof) fd.append('proof', payProof)
      await apiUpload(`/api/v1/parent/billing/invoices/${selected.id}/payment-claims`, fd)
      setMessage('Payment submitted for review. Finance will confirm once verified.')
      setPaymentOpen(false)
      setPayProof(null)
      const detail = await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}`)
      setSelected(detail)
      await load()
    } catch (err) {
      setError(err.message || 'Could not submit payment')
    } finally {
      setActing(false)
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

  async function downloadPdf(invoiceId, invoiceNumber) {
    setError('')
    try {
      const safe = (invoiceNumber || invoiceId).toString().replace(/\//g, '-')
      await apiDownload(`/api/v1/parent/billing/invoices/${invoiceId}/pdf`, `invoice_${safe}.pdf`)
    } catch (err) {
      setError(err.message || 'Could not download invoice PDF')
    }
  }

  function toggleDisputeLine(lineId) {
    setDisputeLineIds((prev) => {
      const next = prev.includes(lineId) ? prev.filter((id) => id !== lineId) : [...prev, lineId]
      return next
    })
    setDisputeEntireInvoice(false)
  }

  async function submitDispute(e) {
    e?.preventDefault?.()
    if (!selected) return
    const message = disputeMessage.trim()
    if (message.length < 10) {
      setError('Please describe the issue in at least 10 characters.')
      return
    }
    if (!disputeEntireInvoice && disputeLineIds.length === 0) {
      setError('Select at least one session, or choose entire invoice.')
      return
    }
    setActing(true)
    setError('')
    setMessage('')
    try {
      const result = await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}/disputes`, {
        method: 'POST',
        body: JSON.stringify({
          reason_code: disputeReason,
          message,
          line_ids: disputeEntireInvoice ? [] : disputeLineIds,
        }),
      })
      const count = result?.count ?? 1
      setMessage(
        count > 1
          ? `${count} disputes submitted. Finance will review and update you in this portal.`
          : 'Dispute submitted. Finance will review and update you by email or in this portal.',
      )
      setDisputeOpen(false)
      resetDisputeForm()
      setPaymentTab('disputed')
      const detail = await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}`)
      setSelected(detail)
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
        <p className="parent-portal-lead">
          Review invoices raised by your care team, download statements, and keep track of what is due.
        </p>
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

      {showDueStrip ? (
        <section className="parent-pay__due-section" aria-label="Invoices that need payment">
          <h3>Action required — pay now</h3>
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

      {dashboard?.packages?.length > 0 ? (
        <section className="parent-pay__packages parent-pay__table-card">
          <div className="parent-pay__table-head">
            <h3>Session packages</h3>
          </div>
          <div className="parent-pay__mobile-list" aria-label="Session packages">
            {dashboard.packages.map((p) => (
              <PackageMobileCard key={p.id} pkg={p} />
            ))}
          </div>
          <div className="parent-pay__table-desktop table-wrap">
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

      <nav className="parent-portal-tabs parent-pay__tabs-sync" aria-label="Invoice payment status">
        {PAYMENT_TABS.map((t) => (
          <button
            key={t.id || 'all'}
            type="button"
            className={`parent-portal-tabs__tab ${paymentTab === t.id ? 'is-active' : ''}`}
            onClick={() => setPaymentTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <ParentFilterBar
        ariaLabel="Refine invoice list"
        gridClass="parent-portal-filters__grid--tablet-2 parent-portal-filters__grid--desktop-3"
      >
        <ParentFilterField label="Month">
          <ParentFilterSelect value={month} onChange={(e) => setMonth(e.target.value)}>
            <option value="">All months</option>
            {(opts.months || []).map((m) => (
              <option key={m} value={m}>
                {formatMonth(m)}
              </option>
            ))}
          </ParentFilterSelect>
        </ParentFilterField>
        <ParentFilterField label="Child / case">
          <ParentFilterSelect value={caseId} onChange={(e) => setCaseId(e.target.value)}>
            <option value="">All</option>
            {(opts.children || []).map((c) => (
              <option key={c.caseDbId} value={String(c.caseDbId)}>
                {c.label}
              </option>
            ))}
          </ParentFilterSelect>
        </ParentFilterField>
        <ParentFilterField label="Service">
          <ParentFilterSelect value={service} onChange={(e) => setService(e.target.value)}>
            <option value="">All services</option>
            {(opts.services || []).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </ParentFilterSelect>
        </ParentFilterField>
      </ParentFilterBar>

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
          <>
            <div className="parent-pay__mobile-list" aria-label="Invoice list">
              {invoices.map((inv) => (
                <InvoiceMobileCard key={inv.id} inv={inv} onOpen={openInvoice} />
              ))}
            </div>
            <div className="parent-pay__table-desktop table-wrap">
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
          </>
        )}
      </section>

      {selected
        ? createPortal(
            <div
              role="dialog"
              aria-modal="true"
              aria-label="Invoice detail"
              className="parent-pay__dialog"
            >
              <button
                type="button"
                className="parent-pay__dialog-backdrop"
                aria-label="Close invoice"
                onClick={closeInvoiceDialog}
              />
              <div className="parent-pay__dialog-sheet">
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
              <button type="button" className="parent-pay__dialog-close" onClick={closeInvoiceDialog} aria-label="Close">
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
                  <button
                    type="button"
                    className="parent-pay__btn parent-pay__btn--ghost parent-pay__btn--sm"
                    style={{ marginTop: 8 }}
                    onClick={() => setLineDetail(null)}
                  >
                    Close session
                  </button>
                </section>
              ) : null}

              {disputeOpen ? (
                <form className="parent-pay__dispute-form" onSubmit={submitDispute}>
                  <h3 className="parent-pay__dispute-title">Raise a dispute</h3>
                  <ParentFilterField label="Reason">
                    <ParentFilterSelect
                      value={disputeReason}
                      onChange={(e) => setDisputeReason(e.target.value)}
                      aria-label="Dispute reason"
                    >
                      {DISPUTE_REASONS.map((r) => (
                        <option key={r.value} value={r.value}>
                          {r.label}
                        </option>
                      ))}
                    </ParentFilterSelect>
                  </ParentFilterField>

                  <fieldset className="parent-pay__dispute-sessions">
                    <legend className="parent-portal-filters__label">Sessions</legend>
                    <label className="parent-pay__dispute-check parent-pay__dispute-check--whole">
                      <input
                        type="checkbox"
                        checked={disputeEntireInvoice}
                        onChange={(e) => {
                          setDisputeEntireInvoice(e.target.checked)
                          if (e.target.checked) setDisputeLineIds([])
                        }}
                      />
                      <span>Entire invoice</span>
                    </label>
                    {(selected.lines || []).length > 0 ? (
                      <ul className="parent-pay__dispute-session-list">
                        {(selected.lines || []).map((l) => (
                          <li key={l.id}>
                            <label className="parent-pay__dispute-check">
                              <input
                                type="checkbox"
                                checked={!disputeEntireInvoice && disputeLineIds.includes(l.id)}
                                disabled={disputeEntireInvoice}
                                onChange={() => toggleDisputeLine(l.id)}
                              />
                              <span>{formatSessionLineLabel(l)}</span>
                            </label>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="parent-pay__dispute-empty">No session lines on this invoice.</p>
                    )}
                  </fieldset>

                  <ParentFilterField label="Details">
                    <textarea
                      className="parent-pay__dispute-textarea"
                      value={disputeMessage}
                      onChange={(e) => setDisputeMessage(e.target.value)}
                      rows={4}
                      placeholder="Describe the issue (at least 10 characters)"
                      aria-label="Dispute details"
                    />
                  </ParentFilterField>

                  <div className="parent-pay__dispute-actions">
                    <button
                      type="submit"
                      className="parent-pay__btn parent-pay__btn--primary"
                      disabled={
                        acting ||
                        disputeMessage.trim().length < 10 ||
                        (!disputeEntireInvoice && disputeLineIds.length === 0)
                      }
                    >
                      {acting ? 'Submitting…' : 'Submit dispute'}
                    </button>
                    <button
                      type="button"
                      className="parent-pay__btn parent-pay__btn--ghost"
                      onClick={() => {
                        setDisputeOpen(false)
                        resetDisputeForm()
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              ) : null}

              {(selected.payments || []).length > 0 ? (
                <section style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Payment history</h3>
                  <ul className="log-list">
                    {selected.payments.map((p) => (
                      <li key={p.id}>
                        <span
                          className={`status ${
                            p.paymentStatus === 'confirmed'
                              ? 'completed'
                              : p.paymentStatus === 'rejected'
                                ? 'warning'
                                : 'pending'
                          }`}
                        >
                          {p.paymentStatus === 'pending_review'
                            ? 'Pending review'
                            : p.paymentStatus === 'confirmed'
                              ? 'Confirmed'
                              : p.paymentStatus === 'rejected'
                                ? 'Not accepted'
                                : p.paymentStatus}
                        </span>
                        <p style={{ margin: '4px 0' }}>
                          ₹{p.amountInr?.toLocaleString('en-IN')} · {p.method}
                          {p.reference ? ` · ${p.reference}` : ''}
                        </p>
                        {p.rejectionNote ? (
                          <p style={{ fontSize: 13, color: '#6b7280' }}>{p.rejectionNote}</p>
                        ) : null}
                        {p.hasProof ? (
                          <button
                            type="button"
                            className="parent-pay__btn parent-pay__btn--ghost parent-pay__btn--sm"
                            style={{ marginTop: 4 }}
                            onClick={() =>
                              apiDownload(
                                `/api/v1/parent/billing/payments/${p.id}/proof`,
                                p.proofFileName || 'payment-proof',
                              ).catch((err) => setError(err.message))
                            }
                          >
                            View screenshot
                          </button>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {paymentOpen ? (
                <section style={{ marginTop: 16, padding: 12, background: '#f8fafc', borderRadius: 8 }}>
                  <h3 style={{ fontSize: 15, marginTop: 0 }}>Record offline payment</h3>
                  <form onSubmit={submitPaymentClaim}>
                    <label style={{ display: 'block', marginBottom: 8 }}>
                      Amount (INR)
                      <input
                        type="number"
                        required
                        min="1"
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                        style={{ width: '100%', marginTop: 4, padding: 8 }}
                      />
                    </label>
                    <label style={{ display: 'block', marginBottom: 8 }}>
                      Method
                      <select
                        value={payMethod}
                        onChange={(e) => setPayMethod(e.target.value)}
                        style={{ width: '100%', marginTop: 4, padding: 8 }}
                      >
                        <option value="UPI">UPI</option>
                        <option value="BANK_TRANSFER">Bank transfer</option>
                        <option value="CASH">Cash</option>
                        <option value="CHEQUE">Cheque</option>
                      </select>
                    </label>
                    <label style={{ display: 'block', marginBottom: 8 }}>
                      Reference (optional)
                      <input
                        value={payRef}
                        onChange={(e) => setPayRef(e.target.value)}
                        style={{ width: '100%', marginTop: 4, padding: 8 }}
                      />
                    </label>
                    <label style={{ display: 'block', marginBottom: 8 }}>
                      Payment screenshot (optional)
                      <input
                        type="file"
                        accept="image/*,application/pdf"
                        onChange={(e) => setPayProof(e.target.files?.[0] || null)}
                        style={{ width: '100%', marginTop: 4 }}
                      />
                    </label>
                    <label style={{ display: 'block', marginBottom: 8 }}>
                      Notes (optional)
                      <textarea
                        value={payNotes}
                        onChange={(e) => setPayNotes(e.target.value)}
                        rows={2}
                        style={{ width: '100%', marginTop: 4, padding: 8 }}
                      />
                    </label>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <button type="submit" className="parent-pay__btn parent-pay__btn--primary" disabled={acting}>
                        {acting ? 'Submitting…' : 'Submit for review'}
                      </button>
                      <button
                        type="button"
                        className="parent-pay__btn parent-pay__btn--ghost"
                        onClick={() => setPaymentOpen(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                </section>
              ) : null}

              {(selected.disputes || []).length > 0 ? (
                <section style={{ marginTop: 16 }} className="parent-pay__dispute-next">
                  <h3 style={{ fontSize: 15 }}>Dispute status</h3>
                  <p className="parent-pay__dispute-hint">
                    We typically respond within a few business days. You can track updates here and under the{' '}
                    <button
                      type="button"
                      className="parent-pay__inline-link"
                      onClick={() => {
                        setPaymentTab('disputed')
                        setSelected(null)
                      }}
                    >
                      Disputed
                    </button>{' '}
                    tab. Questions?{' '}
                    <Link to="/parent/support">Contact support</Link>.
                  </p>
                  <ul className="log-list">
                    {selected.disputes.map((d) => (
                      <li key={d.id}>
                        <span
                          className={`status ${
                            d.status === 'resolved' ? 'completed' : d.status === 'rejected' ? 'warning' : 'pending'
                          }`}
                        >
                          {DISPUTE_STATUS_LABELS[d.status] || d.status}
                        </span>
                        <p style={{ margin: '4px 0' }}>{d.message}</p>
                        {d.adminResolution ? (
                          <p style={{ fontSize: 13, color: '#6b7280' }}>Response: {d.adminResolution}</p>
                        ) : d.status === 'open' || d.status === 'under_review' ? (
                          <p style={{ fontSize: 13, color: '#6b7280' }}>No response yet — our finance team will update this invoice when reviewed.</p>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </div>

            <div className="parent-pay__dialog-footer">
              <button
                type="button"
                className="parent-pay__btn parent-pay__btn--secondary"
                onClick={() => downloadPdf(selected.id, selected.invoiceNumber)}
              >
                Download PDF
              </button>
              {selected.paymentBucket !== 'paid' && selected.paymentBucket !== 'disputed' ? (
                <>
                  <button
                    type="button"
                    className="parent-pay__btn parent-pay__btn--primary"
                    disabled
                    title="Online payment gateway coming soon"
                  >
                    Pay online
                  </button>
                  <button
                    type="button"
                    className="parent-pay__btn parent-pay__btn--secondary"
                    onClick={() => {
                      setPaymentOpen(true)
                      setDisputeOpen(false)
                    }}
                  >
                    I paid offline
                  </button>
                  <button type="button" className="parent-pay__btn parent-pay__btn--ghost" onClick={openDisputeForm}>
                    Dispute invoice
                  </button>
                </>
              ) : null}
            </div>
              </div>
            </div>,
            document.body,
          )
        : null}
    </div>
  )
}
