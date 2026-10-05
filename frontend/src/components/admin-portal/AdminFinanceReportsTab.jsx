import { useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import './admin-hr-reports.css'

const REPORT_TIMEOUT_MS = 120_000

function currentBillingMonth() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function money(value) {
  const amount = Number(value)
  if (!Number.isFinite(amount)) return '—'
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(amount)
}

function previewSummary(rows) {
  if (!rows?.length) return null
  const num = (value) => {
    const amount = Number(value)
    return Number.isFinite(amount) ? amount : 0
  }
  return {
    count: rows.length,
    predicted: rows.reduce((sum, row) => sum + num(row['Predicted Total']), 0),
    therapist: rows.reduce((sum, row) => sum + num(row['Therapist Total']), 0),
  }
}

const REPORTS = [
  { key: 'monthly-billing', label: 'Monthly billing', description: 'Invoiced amounts by case for the billing month.' },
  { key: 'outstanding', label: 'Outstanding balances', description: 'Open client balances still due.' },
  { key: 'collections', label: 'Collections', description: 'Payments received in the billing month.' },
  { key: 'therapist-payouts', label: 'Therapist payouts', description: 'Paid and queued therapist payouts.' },
  { key: 'therapist-payout-preview', label: 'Therapist payout preview', description: 'Sessions, leave, child absence, and calculated pay for shadow, homecare, active cases, and cases stopped this month or next.' },
  { key: 'client-invoice-vs-calculation', label: 'Client invoice vs calculation', description: 'Client invoice submitted for the month against the calculated client amount, one row per case.' },
  { key: 'therapist-invoice-vs-calculation', label: 'Therapist invoice vs calculation', description: 'Therapist payout invoice submitted for the month against the calculated pay.' },
  { key: 'pending-payout-approvals', label: 'Pending payout approvals', description: 'Payouts waiting on finance approval.' },
  { key: 'ledger-missing', label: 'Ledger missing', description: 'Cases or sessions missing ledger rows.' },
  { key: 'manual-adjustments', label: 'Manual adjustments', description: 'Finance corrections posted in the month.' },
  { key: 'revenue-by-service', label: 'Revenue by service', description: 'Revenue rollup by programme / service.' },
  { key: 'margin-by-case', label: 'Margin by case', description: 'Client vs therapist margin; flags under 30%.' },
]

export function AdminFinanceReportsTab({ defaultReportKey = 'monthly-billing' }) {
  const [reportKey, setReportKey] = useState(defaultReportKey)
  const [billingMonth, setBillingMonth] = useState(currentBillingMonth)
  const [preview, setPreview] = useState(null)
  const [monthClose, setMonthClose] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  const selected = REPORTS.find((r) => r.key === reportKey) || REPORTS[0]
  const summary = previewSummary(reportKey === 'therapist-payout-preview' ? preview?.rows : null)

  async function loadMonthCloseStatus(ym) {
    try {
      const data = await apiFetch(
        `/api/v1/admin/finance-reports/billing-month-close?billing_month=${encodeURIComponent(ym)}`,
      )
      setMonthClose(data)
    } catch {
      setMonthClose(null)
    }
  }

  async function loadPreview() {
    try {
      const data = await run(
        () =>
          apiFetch(
            `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}`,
            { timeoutMs: REPORT_TIMEOUT_MS },
          ),
        { successMsg: 'Report ready' },
      )
      setPreview(data)
      await loadMonthCloseStatus(billingMonth)
    } catch {
      setPreview(null)
    }
  }

  async function closeBillingMonth() {
    await run(
      () =>
        apiFetch('/api/v1/admin/finance-reports/close-billing-month', {
          method: 'POST',
          body: JSON.stringify({ billing_month: billingMonth }),
        }),
      { successMsg: `Billing month ${billingMonth} closed and snapshotted` },
    )
    await loadMonthCloseStatus(billingMonth)
    await loadPreview()
  }

  async function downloadCsv() {
    await run(
      () =>
        apiDownload(
          `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}&format=csv`,
          `${reportKey}-${billingMonth}.csv`,
          { timeoutMs: REPORT_TIMEOUT_MS },
        ),
      { successMsg: 'CSV downloaded' },
    )
  }

  async function downloadExcel() {
    await run(
      () =>
        apiDownload(
          `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}&format=xlsx`,
          `${reportKey}-${billingMonth}.xlsx`,
          { timeoutMs: REPORT_TIMEOUT_MS },
        ),
      { successMsg: 'Excel downloaded' },
    )
  }

  return (
    <div className="admin-hr-reports">
      <AdminPanel title="Finance report catalog" padded>
        <p className="admin-muted admin-hr-reports__hint">
          All finance reports are wired for Preview, CSV, and Excel. Pick a report, set the billing month, then
          preview or download. Session counts include visits that were logged in and logged out even when the log
          is still pending or not submitted. Close month freezes payout preview and margin snapshots.
        </p>
        <div className="admin-hr-reports__cards">
          {REPORTS.map((report) => (
            <button
              key={report.key}
              type="button"
              className={`admin-hr-reports__card${reportKey === report.key ? ' is-selected' : ''}`}
              onClick={() => {
                setReportKey(report.key)
                setPreview(null)
              }}
            >
              <span className="admin-hr-reports__card-title">{report.label}</span>
              <span className="admin-hr-reports__card-desc">{report.description}</span>
            </button>
          ))}
        </div>
      </AdminPanel>

      <AdminPanel title={selected.label} padded>
        <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
        <div className="admin-hr-reports__filters">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Billing month</span>
            <input
              type="month"
              className="client-inv__filter-input"
              value={billingMonth}
              onChange={(e) => setBillingMonth(e.target.value)}
            />
          </label>
        </div>
        <div className="admin-hr-reports__actions admin-btn-group">
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={loading}
            onClick={loadPreview}
          >
            {loading ? 'Loading…' : 'Preview'}
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--secondary admin-btn--sm"
            disabled={loading}
            onClick={downloadCsv}
          >
            CSV
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--secondary admin-btn--sm"
            disabled={loading}
            onClick={downloadExcel}
          >
            Excel
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={loading || monthClose?.closed}
            onClick={closeBillingMonth}
            title="Freeze payout preview and margin data for this billing month"
          >
            {monthClose?.closed ? 'Month closed' : 'Close month'}
          </button>
        </div>

        {monthClose?.closed ? (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            {billingMonth} is closed — payout preview and margin reports read frozen snapshots.
            {monthClose.closedAt ? ` Closed ${new Date(monthClose.closedAt).toLocaleString()}.` : ''}
          </p>
        ) : null}
        {preview?.dataSource === 'snapshot' ? (
          <p className="admin-muted" style={{ marginTop: 8 }}>
            Data source: frozen snapshot (not live case rates).
          </p>
        ) : null}
        {preview?.generatedAt ? (
          <p className="admin-muted" style={{ marginTop: 8 }}>
            Generated by <strong>{preview.generatedBy}</strong> on {preview.generatedAt}
          </p>
        ) : null}
        {summary ? (
          <p className="admin-muted" style={{ marginTop: 8 }}>
            {summary.count} case rows · predicted payout {money(summary.predicted)} · therapist totals{' '}
            {money(summary.therapist)}
          </p>
        ) : null}

        {preview?.rows?.length ? (
          <div className="admin-table-wrap" style={{ marginTop: 16 }}>
            <table className="admin-table">
              <thead>
                <tr>
                  {Object.keys(preview.rows[0]).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 50).map((row, i) => {
                  const lowMargin =
                    reportKey === 'margin-by-case' &&
                    (row.lowMargin === true || row.marginFlag === 'LOW_MARGIN_BELOW_30')
                  return (
                    <tr
                      key={i}
                      style={lowMargin ? { background: '#fef3c7' } : undefined}
                      title={lowMargin ? 'Insighte margin under 30%' : undefined}
                    >
                      {Object.values(row).map((v, j) => (
                        <td key={j}>{typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v ?? '')}</td>
                      ))}
                    </tr>
                  )
                })}
              </tbody>
            </table>
            {preview.rows.length > 50 ? (
              <p className="admin-muted">Showing first 50 of {preview.count} rows.</p>
            ) : null}
            {reportKey === 'margin-by-case' ? (
              <p className="admin-muted" style={{ marginTop: 8, color: '#92400e' }}>
                Highlighted rows: Insighte margin (client − therapist) under 30% of client total.
              </p>
            ) : null}
          </div>
        ) : preview ? (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            {reportKey === 'therapist-payout-preview'
              ? 'No payout rows for this billing month yet. Active shadow cases are included from the assigned therapist even before logs are approved. Homecare rows appear once sessions are recorded.'
              : 'No rows for this report and billing month. Try another month, or confirm billing data exists for these cases.'}
          </p>
        ) : null}
      </AdminPanel>
    </div>
  )
}
