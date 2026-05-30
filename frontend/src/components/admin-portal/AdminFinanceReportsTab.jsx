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
  { key: 'pending-payout-approvals', label: 'Pending payout approvals' },
  { key: 'ledger-missing', label: 'Ledger missing' },
  { key: 'manual-adjustments', label: 'Manual adjustments' },
  { key: 'revenue-by-service', label: 'Revenue by service' },
  { key: 'margin-by-case', label: 'Margin by case' },
]

export function AdminFinanceReportsTab() {
  const [reportKey, setReportKey] = useState('monthly-billing')
  const [billingMonth, setBillingMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const [preview, setPreview] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  async function loadPreview() {
    const data = await run(
      () =>
        apiFetch(
          `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}`
        ),
      { successMsg: 'Report loaded' }
    )
    setPreview(data)
  }

  async function downloadCsv() {
    await apiDownload(
      `/api/v1/admin/finance-reports/${reportKey}?billing_month=${encodeURIComponent(billingMonth)}&format=csv`,
      `${reportKey}.csv`
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
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={downloadCsv}>
          Download CSV
        </button>
      </div>
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
              {preview.rows.slice(0, 50).map((row, i) => (
                <tr key={i}>
                  {Object.values(row).map((v, j) => (
                    <td key={j}>{String(v ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {preview.rows.length > 50 ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>Showing first 50 of {preview.count} rows.</p>
          ) : null}
        </div>
      ) : preview ? (
        <p style={{ color: '#64748b' }}>No rows for this report.</p>
      ) : null}
    </AdminPanel>
  )
}
