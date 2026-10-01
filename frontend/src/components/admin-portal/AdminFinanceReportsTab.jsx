import { useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { currentBillingMonthIST } from '../../lib/datetime.js'
import { AdminPanel, ServiceFilterSelect } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import './admin-hr-reports.css'

const REPORT_KEY = 'therapist-payout-preview'
const REPORT_LABEL = 'Therapist payout preview'
const PREVIEW_PAGE_SIZE = 50

function buildQuery(params) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) qs.set(key, String(value))
  })
  return qs.toString()
}

export function AdminFinanceReportsTab() {
  const [billingMonth, setBillingMonth] = useState(currentBillingMonthIST)
  const [productModule, setProductModule] = useState('')
  const [caseId, setCaseId] = useState('')
  const [therapistUserId, setTherapistUserId] = useState('')
  const [page, setPage] = useState(1)
  const [preview, setPreview] = useState(null)
  const [monthClose, setMonthClose] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  function filterParams(extra = {}) {
    return {
      billing_month: billingMonth,
      product_module: productModule,
      case_id: caseId,
      therapist_user_id: therapistUserId,
      ...extra,
    }
  }

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

  async function loadPreview(nextPage = 1) {
    const data = await run(
      () =>
        apiFetch(
          `/api/v1/admin/finance-reports/${REPORT_KEY}?${buildQuery({
            ...filterParams({ page: nextPage, page_size: PREVIEW_PAGE_SIZE }),
          })}`,
        ),
      { successMsg: 'Report loaded' },
    )
    if (data) {
      setPreview(data)
      setPage(nextPage)
    }
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
    await loadPreview(1)
  }

  async function downloadCsv() {
    await run(
      () =>
        apiDownload(
          `/api/v1/admin/finance-reports/${REPORT_KEY}?${buildQuery({
            ...filterParams({ format: 'csv' }),
          })}`,
          `${REPORT_KEY}.csv`,
        ),
      { successMsg: 'CSV downloaded' },
    )
  }

  async function downloadExcel() {
    await run(
      () =>
        apiDownload(
          `/api/v1/admin/finance-reports/${REPORT_KEY}?${buildQuery({
            ...filterParams({ format: 'xlsx' }),
          })}`,
          `${REPORT_KEY}.xlsx`,
        ),
      { successMsg: 'Excel downloaded' },
    )
  }

  const total = preview?.count ?? 0
  const pageRows = preview?.rows || []
  const totalPages = Math.max(1, Math.ceil(total / PREVIEW_PAGE_SIZE))

  return (
    <div className="admin-hr-reports">
      <AdminPanel title={REPORT_LABEL} padded>
        <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
        <p className="admin-muted admin-hr-reports__hint">
          Projected therapist payout for the billing month (Asia/Kolkata). Set filters, then generate a
          preview. Close month freezes payout preview snapshots. This is not collections or receivables.
        </p>
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
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Service</span>
            <ServiceFilterSelect
              id="finance-payout-service"
              value={productModule}
              onChange={setProductModule}
              className="client-inv__filter-input"
            />
          </label>
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Case ID (optional)</span>
            <input
              type="number"
              className="client-inv__filter-input"
              value={caseId}
              onChange={(e) => setCaseId(e.target.value)}
              placeholder="All cases"
              min="1"
            />
          </label>
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Therapist user ID (optional)</span>
            <input
              type="number"
              className="client-inv__filter-input"
              value={therapistUserId}
              onChange={(e) => setTherapistUserId(e.target.value)}
              placeholder="All therapists"
              min="1"
            />
          </label>
        </div>
        <div className="admin-hr-reports__actions admin-btn-group">
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={loading}
            onClick={() => loadPreview(1)}
          >
            {loading ? 'Generating…' : 'Generate preview'}
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
            title="Freeze payout preview data for this billing month"
          >
            {monthClose?.closed ? 'Month closed' : 'Close month'}
          </button>
        </div>

        {monthClose?.closed ? (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            {billingMonth} is closed — payout preview reads frozen snapshots.
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
            Generated by <strong>{preview.generatedBy}</strong> on {preview.generatedAt} (IST)
          </p>
        ) : null}

        {preview?.rows?.length ? (
          <div className="admin-table-wrap" style={{ marginTop: 16 }}>
            <p className="admin-muted">
              Showing {pageRows.length} of {total} matching rows
              {preview.previewLimited ? ' — preview page, export includes the full generate.' : '.'}
            </p>
            <table className="admin-table">
              <thead>
                <tr>
                  {Object.keys(pageRows[0]).map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pageRows.map((row, i) => (
                  <tr key={row.caseId ? `${row.caseId}-${i}` : i}>
                    {Object.values(row).map((v, j) => (
                      <td key={j}>{typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {totalPages > 1 ? (
              <div className="admin-btn-group" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={loading || page <= 1}
                  onClick={() => loadPreview(page - 1)}
                >
                  Previous
                </button>
                <span className="admin-muted">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  disabled={loading || page >= totalPages}
                  onClick={() => loadPreview(page + 1)}
                >
                  Next
                </button>
              </div>
            ) : null}
          </div>
        ) : preview ? (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            No rows for these filters. Try another month or confirm billing data exists for these cases.
          </p>
        ) : (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            Filters are ready. Generate a preview when you want to run the payout calculation.
          </p>
        )}
      </AdminPanel>
    </div>
  )
}
