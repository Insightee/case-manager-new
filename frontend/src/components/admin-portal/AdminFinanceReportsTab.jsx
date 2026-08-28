import { useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'

const REPORTS = [
  { key: 'monthly-billing', label: 'Monthly billing' },
  { key: 'outstanding', label: 'Outstanding balances' },
  { key: 'collections', label: 'Collections' },
  { key: 'therapist-payouts', label: 'Therapist payouts' },
  { key: 'therapist-payout-preview', label: 'Therapist payout preview' },
  { key: 'pending-payout-approvals', label: 'Pending payout approvals' },
  { key: 'ledger-missing', label: 'Ledger missing' },
  { key: 'manual-adjustments', label: 'Manual adjustments' },
  { key: 'revenue-by-service', label: 'Revenue by service' },
  { key: 'margin-by-case', label: 'Margin by case' },
]

export function AdminFinanceReportsTab({ defaultReportKey = 'monthly-billing' }) {
  const [reportKey, setReportKey] = useState(defaultReportKey)
  const [billingMonth, setBillingMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const [preview, setPreview] = useState(null)
  const [monthClose, setMonthClose] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

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
    const data = await run(
      () =>
        apiFetch(
          `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}`
        ),
      { successMsg: 'Report loaded' }
    )
    setPreview(data)
    await loadMonthCloseStatus(billingMonth)
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
          `${reportKey}.csv`
        ),
      { successMsg: 'CSV downloaded' }
    )
  }

  async function downloadExcel() {
    await run(
      () =>
        apiDownload(
          `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}&format=xlsx`,
          `${reportKey}.xlsx`
        ),
      { successMsg: 'Excel downloaded' }
    )
  }

  return (
    <AdminPanel title="Finance reports" padded>
      <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Report</span>
          <select className="client-inv__filter-input" value={reportKey} onChange={(e) => setReportKey(e.target.value)}>
            {REPORTS.map((r) => (
              <option key={r.key} value={r.key}>
                {r.label}
              </option>
            ))}
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Billing month</span>
          <input
            type="month"
            className="client-inv__filter-input"
            value={billingMonth}
            onChange={(e) => setBillingMonth(e.target.value)}
          />
        </label>
        <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={loading} onClick={loadPreview}>
          {loading ? 'Loading…' : 'Preview'}
        </button>
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={loading} onClick={downloadCsv}>
          Download CSV
        </button>
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={loading} onClick={downloadExcel}>
          Download Excel
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
        <p style={{ fontSize: '0.85rem', color: '#0d9488', marginBottom: 12 }}>
          {billingMonth} is closed — payout preview and margin reports read frozen snapshots.
          {monthClose.closedAt ? ` Closed ${new Date(monthClose.closedAt).toLocaleString()}.` : ''}
        </p>
      ) : null}
      {preview?.dataSource === 'snapshot' ? (
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
          Data source: frozen snapshot (not live case rates).
        </p>
      ) : null}
      {preview?.generatedAt ? (
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: 12 }}>
          Generated by <strong>{preview.generatedBy}</strong> on {preview.generatedAt}
        </p>
      ) : null}
      {preview?.rows?.length ? (
        <div className="admin-table-wrap">
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
                      <td key={j}>
                        {typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v ?? '')}
                      </td>
                    ))}
                  </tr>
                )
              })}
            </tbody>
          </table>
          {preview.rows.length > 50 ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Showing first 50 of {preview.count} rows.</p>
          ) : null}
          {reportKey === 'margin-by-case' ? (
            <p style={{ fontSize: '0.8rem', color: '#92400e', marginTop: 8 }}>
              Highlighted rows: Insighte margin (client − therapist) under 30% of client total.
            </p>
          ) : null}
        </div>
      ) : preview ? (
        <p style={{ color: '#64748b' }}>No rows for this report.</p>
      ) : null}
    </AdminPanel>
  )
}
