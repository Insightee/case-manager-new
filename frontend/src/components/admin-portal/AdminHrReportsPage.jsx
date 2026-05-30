import { useMemo, useState } from 'react'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { REPORTS_HUB_CATEGORIES } from '../../lib/reportCategories.js'
import { AdminPageHeader, AdminPanel } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'

const REPORT_TYPES = [
  { id: 'clinical', label: 'Clinical' },
  { id: 'operations', label: 'Operations' },
  { id: 'people', label: 'People & status' },
]

const CLINICAL_KEYS = [
  { key: 'observation', label: 'Observation reports', category: 'OBSERVATION' },
  { key: 'client-monthly', label: 'Client monthly reports', category: 'CLIENT_MONTHLY' },
  { key: 'cm-meeting', label: 'Case manager meetings', category: 'CM_MEETING' },
  { key: 'progress', label: 'Progress / milestone', category: 'PROGRESS' },
]

const OPERATIONS_KEYS = [
  { key: 'session-logs', label: 'Session logs' },
  { key: 'cases-roster', label: 'Cases & client names' },
]

const PEOPLE_KEYS = [
  { key: 'staff-status', label: 'Staff status' },
  { key: 'therapist-status', label: 'Therapist status' },
]

export function AdminHrReportsPage() {
  const [reportType, setReportType] = useState('clinical')
  const [reportKey, setReportKey] = useState('observation')
  const [category, setCategory] = useState('OBSERVATION')
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const [productModule, setProductModule] = useState('')
  const [preview, setPreview] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  const reportOptions = useMemo(() => {
    if (reportType === 'clinical') return CLINICAL_KEYS
    if (reportType === 'operations') return OPERATIONS_KEYS
    return PEOPLE_KEYS
  }, [reportType])

  const categoryOptions = useMemo(
    () => [{ value: '', label: 'All categories' }, ...REPORTS_HUB_CATEGORIES.map((c) => ({ value: c.id, label: c.label }))],
    [],
  )

  function onTypeChange(nextType) {
    setReportType(nextType)
    const first =
      nextType === 'clinical' ? CLINICAL_KEYS[0] : nextType === 'operations' ? OPERATIONS_KEYS[0] : PEOPLE_KEYS[0]
    setReportKey(first.key)
    if (first.category) setCategory(first.category)
  }

  function onReportChange(key) {
    setReportKey(key)
    const match = CLINICAL_KEYS.find((r) => r.key === key)
    if (match?.category) setCategory(match.category)
  }

  async function loadPreview() {
    const qs = new URLSearchParams()
    if (category && reportType === 'clinical') qs.set('category', category)
    if (month && (reportType === 'clinical' || reportKey === 'session-logs')) qs.set('month', month)
    if (productModule) qs.set('product_module', productModule)
    const data = await run(
      () => apiFetch(`/api/v1/admin/hr-reports/${reportKey}?${qs.toString()}`),
      { successMsg: 'Report loaded' },
    )
    setPreview(data)
  }

  async function downloadCsv() {
    const qs = new URLSearchParams({ format: 'csv' })
    if (category && reportType === 'clinical') qs.set('category', category)
    if (month && (reportType === 'clinical' || reportKey === 'session-logs')) qs.set('month', month)
    if (productModule) qs.set('product_module', productModule)
    await apiDownload(`/api/v1/admin/hr-reports/${reportKey}?${qs.toString()}`, `${reportKey}.csv`)
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="HR"
        title="Reports"
        subtitle="Export clinical summaries, operational rosters, and people status for HR operations."
      />

      <AdminPanel title="Generate report" padded>
        <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Report type</span>
            <select className="client-inv__filter-input" value={reportType} onChange={(e) => onTypeChange(e.target.value)}>
              {REPORT_TYPES.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Report</span>
            <select className="client-inv__filter-input" value={reportKey} onChange={(e) => onReportChange(e.target.value)}>
              {reportOptions.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          {reportType === 'clinical' ? (
            <label className="client-inv__filter-field">
              <span className="client-inv__filter-label">Category</span>
              <select className="client-inv__filter-input" value={category} onChange={(e) => setCategory(e.target.value)}>
                {categoryOptions.map((o) => (
                  <option key={o.value || 'all'} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {reportType === 'clinical' || reportKey === 'session-logs' ? (
            <label className="client-inv__filter-field">
              <span className="client-inv__filter-label">Month</span>
              <input
                type="month"
                className="client-inv__filter-input"
                value={month}
                onChange={(e) => setMonth(e.target.value)}
              />
            </label>
          ) : null}
          {reportType !== 'people' ? (
            <label className="client-inv__filter-field">
              <span className="client-inv__filter-label">Programme</span>
              <input
                className="client-inv__filter-input"
                placeholder="e.g. homecare"
                value={productModule}
                onChange={(e) => setProductModule(e.target.value)}
              />
            </label>
          ) : null}
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
                {preview.rows.slice(0, 50).map((row, idx) => (
                  <tr key={idx}>
                    {Object.keys(preview.rows[0]).map((k) => (
                      <td key={k}>{String(row[k] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.count > 50 ? <p className="admin-muted">Showing first 50 of {preview.count} rows.</p> : null}
          </div>
        ) : preview ? (
          <p className="admin-muted">No rows for this report.</p>
        ) : null}
      </AdminPanel>
    </div>
  )
}
