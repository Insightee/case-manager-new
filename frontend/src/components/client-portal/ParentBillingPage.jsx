import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { apiFetch, apiDownload, apiUpload } from '../../lib/apiClient.js'
import './parent-payments.css'
import './parent-portal-filters.css'
import '../../styles/finance-stage2.css'
import '../../styles/finance-dashboard-modern.css'
import { formatApiDateIN, formatTimestampDateIN } from '../../lib/datetime.js'
import { formatPaymentMethod } from '../../lib/paymentMethodLabels.js'
import { ParentFilterBar, ParentFilterField, ParentFilterSelect } from './ParentFilterBar.jsx'
import { ParentComingSoon } from './ParentComingSoon.jsx'
import { PARENT_BILLING_COMING_SOON } from '../../lib/parentPortalFeatureFlags.js'

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

function formatBillingDate(value) {
  if (!value) return null
  return formatApiDateIN(String(value).slice(0, 10)) || formatTimestampDateIN(value)
}

function formatSessionLineLabel(line) {
  const date = formatBillingDate(line.sessionDate) || 'Session'
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
            Due {formatBillingDate(inv.dueDate) || '—'}
            {inv.isOverdue && inv.balanceInr > 0 ? (
              <span className="parent-pay__badge parent-pay__badge--overdue parent-pay__badge--gap">
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
  const preview = pkg.renewalPreview
  return (
    <article className="parent-pay__mobile-card parent-pay__mobile-card--package">
      <div className="parent-pay__mobile-card-top">
        <strong>{pkg.name}</strong>
        <span className="parent-pay__badge parent-pay__pkg-left">
          {pkg.remainingSessions} left
        </span>
      </div>
      <p className="parent-pay__mobile-card-meta">{pkg.childName}</p>
      <div className="parent-pay__mobile-card-row">
        <span>Total {pkg.totalSessions}</span>
        <span>Used {pkg.usedSessions}</span>
        <span>
          Expires {pkg.validityEnd ? formatBillingDate(pkg.validityEnd) : '—'}
        </span>
      </div>
      {preview?.nextCyclePreview ? (
        <p className="parent-pay__muted parent-pay__mt-4">{preview.nextCyclePreview}</p>
      ) : null}
      {preview?.topUpRecommended ? (
        <p className="parent-pay__alert parent-pay__alert--info parent-pay__mt-4">
          Sessions running low — contact finance to top up your package.
        </p>
      ) : null}
      {preview?.needsReview ? (
        <p className="parent-pay__muted parent-pay__mt-4">{preview.message}</p>
      ) : null}
    </article>
  )
}

function ParentBillingPageFull() {
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
  const [payDate, setPayDate] = useState(() => new Date().toISOString().slice(0, 10))
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

  async function submitGatewayPayment() {
    if (!selected) return
    setActing(true)
    setError('')
    setMessage('')
    try {
      const result = await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}/pay-gateway`, {
        method: 'POST',
      })
      if (!result.success) {
        setError(result.message || 'Online payment did not complete. You can retry or pay offline.')
        return
      }
      setMessage('Payment received. Your receipt is ready to download.')
      const detail = await apiFetch(`/api/v1/parent/billing/invoices/${selected.id}`)
      setSelected(detail)
      await load()
    } catch (err) {
      setError(err.message || 'Online payment did not complete')
    } finally {
      setActing(false)
    }
  }

  async function downloadReceipt(paymentId, reference) {
    setError('')
    try {
      const safe = (reference || paymentId).toString().replace(/\//g, '-')
      await apiDownload(`/api/v1/parent/billing/payments/${paymentId}/receipt`, `receipt_${safe}.pdf`)
    } catch (err) {
      setError(err.message || 'Could not download receipt')
    }
  }

  async function submitPaymentClaim(e) {
    e?.preventDefault?.()
    if (!selected || !payAmount) return
    const ref = payRef.trim()
    if (!ref) {
      setError('Please add the payment reference or UPI transaction ID.')
      return
    }
    if (!payDate) {
      setError('Please select the date you made the payment.')
      return
    }
    if (!payProof) {
      setError('Please upload a payment screenshot or receipt.')
      return
    }
    setActing(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('amount_inr', payAmount)
      fd.append('method', payMethod)
      fd.append('reference', ref)
      fd.append('payment_date', payDate)
      if (payNotes) fd.append('notes', payNotes)
      fd.append('proof', payProof)
      await apiUpload(`/api/v1/parent/billing/invoices/${selected.id}/payment-claims`, fd)
      setMessage('Payment submitted for review. Finance will confirm once verified.')
      setPaymentOpen(false)
      setPayProof(null)
      setPayRef('')
      setPayDate(new Date().toISOString().slice(0, 10))
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
          ? `Dispute submitted for ${count} sessions. We’ll review and update you here.`
          : 'Dispute submitted. We’ll review and update you here or by email.',
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
    <div className="parent-pay finance-stage2 finance-dash">
      <header className="parent-pay__hero finance-dash__hero">
        <h1>Your statements</h1>
        <p>Review session charges, pay offline or online, and track dispute updates in one place.</p>
      </header>

      {error ? (
        <p className="parent-pay__alert parent-pay__alert--error" role="alert">
          {error} Try refreshing, or contact support if it continues.
        </p>
      ) : null}
      {message ? <p className="parent-pay__alert parent-pay__alert--success">{message}</p> : null}

      {dashboard?.summary ? (
        <section className="parent-pay__summary" aria-label="Billing overview">
          {(summary.needsPaymentCount || 0) > 0 && (summary.dueTotalInr || 0) > 0 ? (
            <article
              className={`parent-pay__summary-feature ${urgentBanner ? 'parent-pay__summary-feature--urgent' : 'parent-pay__summary-feature--due'}`}
            >
              <div className="parent-pay__summary-feature-icon" aria-hidden>
                {urgentBanner ? '!' : '₹'}
              </div>
              <div className="parent-pay__summary-feature-body">
                <p className="parent-pay__summary-feature-kicker">
                  {urgentBanner ? 'Action needed' : 'Payment due'}
                </p>
                <h2>{urgentBanner ? 'Payment overdue' : 'Balance outstanding'}</h2>
                <p>
                  {urgentBanner
                    ? `${summary.overdueCount} overdue · ${summary.needsPaymentCount} open invoice${summary.needsPaymentCount === 1 ? '' : 's'}`
                    : `${summary.needsPaymentCount} invoice${summary.needsPaymentCount === 1 ? '' : 's'} awaiting payment`}
                </p>
              </div>
              <div className="parent-pay__summary-feature-amount-wrap">
                <span className="parent-pay__summary-feature-amount-label">Total due</span>
                <strong className="parent-pay__summary-feature-amount">{formatInr(summary.dueTotalInr)}</strong>
              </div>
            </article>
          ) : null}

          <ul className="parent-pay__summary-grid finance-dash__grid">
            {!((summary.needsPaymentCount || 0) > 0 && (summary.dueTotalInr || 0) > 0) ? (
              <li className="finance-dash__card finance-dash__card--accent">
                <span className="finance-dash__card-k">Balance due</span>
                <strong>{formatInr(summary.dueTotalInr)}</strong>
                <span className="finance-dash__card-meta">Across open invoices</span>
              </li>
            ) : null}
            <li className="finance-dash__card">
              <span className="finance-dash__card-k">Needs payment</span>
              <strong>{summary.needsPaymentCount ?? 0}</strong>
              <span className="finance-dash__card-meta">Open balances</span>
            </li>
            <li className={`finance-dash__card ${(summary.overdueCount ?? 0) > 0 ? 'finance-dash__card--warn' : ''}`}>
              <span className="finance-dash__card-k">Overdue</span>
              <strong>{summary.overdueCount ?? 0}</strong>
              <span className="finance-dash__card-meta">
                {(summary.overdueCount ?? 0) > 0 ? 'Past due date' : 'All current'}
              </span>
            </li>
            <li className="finance-dash__card">
              <span className="finance-dash__card-k">All invoices</span>
              <strong>{summary.invoiceCount ?? 0}</strong>
              <span className="finance-dash__card-meta">Statement history</span>
            </li>
            <li className="finance-dash__card">
              <span className="finance-dash__card-k">Active packages</span>
              <strong>{summary.activePackages ?? 0}</strong>
              <span className="finance-dash__card-meta">Session packs</span>
            </li>
          </ul>
        </section>
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
                  <p className="parent-pay__due-meta">Due {formatBillingDate(inv.dueDate) || '—'}</p>
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
                    <td>{p.validityEnd ? formatBillingDate(p.validityEnd) : '—'}</td>
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
          <p className="parent-pay__inline-pad" aria-busy="true">
            Loading your statements…
          </p>
        ) : invoices.length === 0 ? (
          <p className="parent-pay__inline-pad">
            No invoices yet for these filters. When a statement is ready, it will show up here.
          </p>
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
                      {inv.dueDate ? formatBillingDate(inv.dueDate) : '—'}
                      {inv.isOverdue && inv.balanceInr > 0 ? (
                        <span className="parent-pay__badge parent-pay__badge--overdue parent-pay__badge--gap">
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
            <div className="parent-pay__dialog-head">
              <div>
                <h2 className="parent-pay__dialog-title">{selected.invoiceNumber}</h2>
                <p className="parent-pay__dialog-sub">
                  {selected.childName} · {formatMonth(selected.billingMonth)}
                </p>
                <p className="parent-pay__dialog-meta">
                  <strong>Statement</strong>
                  {selected.dueDate ? (
                    <span>
                      Due {formatBillingDate(selected.dueDate) || '—'}
                      {selected.isOverdue && selected.balanceInr > 0 ? (
                        <span className="parent-pay__badge parent-pay__badge--overdue parent-pay__badge--gap">
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

            <div className="parent-pay__dialog-body">
              <p className="parent-pay__help">
                Here&apos;s your {formatMonth(selected.billingMonth)} statement. Payments are usually coordinated with
                your case coordinator (UPI, bank transfer, or as agreed). Use Download PDF for your records.
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
                        <td>{formatBillingDate(line.sessionDate) || '—'}</td>
                        <td>{line.therapistName}</td>
                        <td>{line.serviceLabel}</td>
                        <td>
                          {line.sessionStatus}
                          {line.packageDeducted ? ' · Pack' : ''}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="parent-pay__linkish"
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

              <dl className="parent-pay__totals">
                <div>
                  <dt>Subtotal</dt>
                  <dd>{formatInr(selected.subtotalInr)}</dd>
                </div>
                <div>
                  <dt>Tax</dt>
                  <dd>{formatInr(selected.taxInr)}</dd>
                </div>
                <div>
                  <dt>Discount</dt>
                  <dd>−{formatInr(selected.discountInr)}</dd>
                </div>
                <div>
                  <dt>Package deduction</dt>
                  <dd>−{formatInr(selected.packageDeductionInr)}</dd>
                </div>
                <div>
                  <dt>Adjustments</dt>
                  <dd>{formatInr(selected.adjustmentInr)}</dd>
                </div>
                <div>
                  <dt>Total payable</dt>
                  <dd className="is-strong">{formatInr(selected.totalInr)}</dd>
                </div>
                <div>
                  <dt>Paid</dt>
                  <dd>{formatInr(selected.amountPaidInr)}</dd>
                </div>
                <div>
                  <dt>Balance</dt>
                  <dd className="is-strong">{formatInr(selected.balanceInr)}</dd>
                </div>
              </dl>

              {lineDetail ? (
                <section className="parent-pay__session-detail">
                  <h3>Session detail</h3>
                  <p className="parent-pay__pay-line">
                    <strong>{lineDetail.therapistName}</strong> · {lineDetail.sessionStatus}
                  </p>
                  {lineDetail.attendance ? (
                    <p className="parent-pay__pay-line">Attendance: {lineDetail.attendance}</p>
                  ) : null}
                  {lineDetail.activitiesSummary ? (
                    <p className="parent-pay__mt-8 parent-pay__prewrap">
                      {lineDetail.activitiesSummary}
                    </p>
                  ) : null}
                  <button
                    type="button"
                    className="parent-pay__btn parent-pay__btn--ghost parent-pay__btn--sm parent-pay__mt-8"
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
                <section className="parent-pay__mt-16">
                  <h3 className="parent-pay__section-title">Payment history</h3>
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
                        <p className="parent-pay__pay-line finance-stage2-mono">
                          ₹{p.amountInr?.toLocaleString('en-IN')} · {formatPaymentMethod(p.method)}
                          {p.reference ? ` · ${p.reference}` : ''}
                          {p.paidAt ? ` · ${formatApiDateIN(String(p.paidAt).slice(0, 10)) || p.paidAt.slice(0, 10)}` : ''}
                        </p>
                        {p.rejectionNote ? <p className="parent-pay__muted">{p.rejectionNote}</p> : null}
                        {p.paymentStatus === 'confirmed' ? (
                          <button
                            type="button"
                            className="parent-pay__btn parent-pay__btn--ghost parent-pay__btn--sm parent-pay__mt-4"
                            onClick={() => downloadReceipt(p.id, p.reference)}
                          >
                            Download receipt
                          </button>
                        ) : null}
                        {p.hasProof ? (
                          <button
                            type="button"
                            className="parent-pay__btn parent-pay__btn--ghost parent-pay__btn--sm parent-pay__mt-4"
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
                <section className="parent-pay__payment-form">
                  <h3>I paid offline</h3>
                  <p className="parent-pay__help">
                    Upload your payment proof so finance can verify and confirm the receipt.
                  </p>
                  <form onSubmit={submitPaymentClaim}>
                    <label className="parent-pay__field">
                      Amount (INR)
                      <input
                        type="number"
                        required
                        min="1"
                        value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                      />
                    </label>
                    <label className="parent-pay__field">
                      Payment mode
                      <select value={payMethod} onChange={(e) => setPayMethod(e.target.value)} required>
                        <option value="UPI">UPI</option>
                        <option value="BANK_TRANSFER">Bank transfer</option>
                        <option value="CASH">Cash</option>
                        <option value="CHEQUE">Cheque</option>
                      </select>
                    </label>
                    <label className="parent-pay__field">
                      Payment date
                      <input
                        type="date"
                        required
                        max={new Date().toISOString().slice(0, 10)}
                        value={payDate}
                        onChange={(e) => setPayDate(e.target.value)}
                      />
                    </label>
                    <label className="parent-pay__field">
                      Reference / transaction ID
                      <input value={payRef} onChange={(e) => setPayRef(e.target.value)} required />
                    </label>
                    <label className="parent-pay__field">
                      Payment screenshot
                      <input
                        type="file"
                        accept="image/*,application/pdf"
                        required
                        onChange={(e) => setPayProof(e.target.files?.[0] || null)}
                      />
                    </label>
                    <label className="parent-pay__field">
                      Notes (optional)
                      <textarea value={payNotes} onChange={(e) => setPayNotes(e.target.value)} rows={2} />
                    </label>
                    <div className="parent-pay__form-actions">
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
                <section className="parent-pay__dispute-next parent-pay__mt-16">
                  <h3 className="parent-pay__section-title">Dispute status</h3>
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
                        <p className="parent-pay__pay-line">{d.message}</p>
                        {d.adminResolution ? (
                          <p className="parent-pay__muted">Response: {d.adminResolution}</p>
                        ) : d.status === 'open' || d.status === 'under_review' ? (
                          <p className="parent-pay__muted">
                            No response yet — we’ll update this statement when it’s reviewed.
                          </p>
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
              {selected.paymentBucket !== 'paid' && (selected.balanceInr ?? 0) > 0 ? (
                <>
                  <button
                    type="button"
                    className="parent-pay__btn parent-pay__btn--primary"
                    disabled={acting}
                    onClick={submitGatewayPayment}
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

export function ParentBillingPage() {
  if (PARENT_BILLING_COMING_SOON) {
    return (
      <ParentComingSoon
        title="Your statements"
        subtitle="Statements, payments, and session packages for your care plans — coming soon."
      />
    )
  }
  return <ParentBillingPageFull />
}
