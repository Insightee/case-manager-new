import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, MultiSelect, ServiceFilterSelect } from './ui/index.js'
import { ExpandableTextCell } from './ui/ExpandableTextCell.jsx'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import { formatApiDateIN, formatTimestampDateIN, todayIsoIST } from '../../lib/datetime.js'
import './admin-hr-reports.css'

function currentMonth() {
  return todayIsoIST().slice(0, 7)
}

function monthStartIso() {
  const today = todayIsoIST()
  return `${today.slice(0, 8)}01`
}

function todayIso() {
  return todayIsoIST()
}

/** IST calendar date for download filenames (matches backend export stamp). */
function downloadDateStamp() {
  try {
    const parts = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    }).formatToParts(new Date())
    const get = (type) => parts.find((p) => p.type === type)?.value
    return `${get('year')}-${get('month')}-${get('day')}`
  } catch {
    return todayIso()
  }
}

function formatPreviewCell(column, value) {
  if (value == null || value === '') return ''
  const str = String(value)
  if (/date|raised|resolution|created|reported|incident date|last /i.test(column)) {
    return formatTimestampDateIN(str) || formatApiDateIN(str) || str
  }
  return str
}

function buildQuery(params) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) qs.set(key, String(value))
  })
  return qs.toString()
}

function reportUsesMonth(report) {
  return report?.filters?.includes('month')
}

function reportUsesDateRange(report) {
  return report?.filters?.includes('date_from') || report?.filters?.includes('date_to')
}

export function AdminHrReportsPage() {
  const [catalog, setCatalog] = useState({ categories: [], reports: [] })
  const [categoryId, setCategoryId] = useState('hr_attendance')
  const [reportKey, setReportKey] = useState('bulk-attendance')
  const [month, setMonth] = useState(currentMonth)
  const [dateFrom, setDateFrom] = useState(monthStartIso)
  const [dateTo, setDateTo] = useState(todayIso)
  const [productModule, setProductModule] = useState('')
  const [caseManagerUserIds, setCaseManagerUserIds] = useState([])
  const [preview, setPreview] = useState(null)
  const [cms, setCms] = useState([])
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  useEffect(() => {
    apiFetch('/api/v1/admin/hr-reports/catalog')
      .then(setCatalog)
      .catch(() => setCatalog({ categories: [], reports: [] }))
  }, [])

  useEffect(() => {
    apiFetch('/api/v1/admin/users/directory?roles=CASE_MANAGER')
      .then((rows) => setCms(rows || []))
      .catch(() => setCms([]))
  }, [])

  const visibleCategories = useMemo(() => {
    const nonLegacy = catalog.categories?.filter((c) => c.id !== 'legacy') || []
    return nonLegacy.length ? nonLegacy : catalog.categories || []
  }, [catalog.categories])

  const reportsInCategory = useMemo(() => {
    return (catalog.reports || []).filter((r) => r.category === categoryId && r.category !== 'legacy')
  }, [catalog.reports, categoryId])

  const selectedReport = useMemo(
    () => (catalog.reports || []).find((r) => r.key === reportKey),
    [catalog.reports, reportKey],
  )

  useEffect(() => {
    if (!reportsInCategory.length) return
    if (!reportsInCategory.some((r) => r.key === reportKey)) {
      setReportKey(reportsInCategory[0].key)
    }
  }, [reportsInCategory, reportKey])

  const filterParams = useMemo(() => {
    const params = {}
    if (reportUsesMonth(selectedReport)) params.month = month
    if (reportUsesDateRange(selectedReport)) {
      params.date_from = dateFrom
      params.date_to = dateTo
    }
    if (selectedReport?.filters?.includes('product_module') && productModule) {
      params.product_module = productModule
    }
    if (selectedReport?.filters?.includes('case_manager_user_id') && caseManagerUserIds.length) {
      params.case_manager_user_id = caseManagerUserIds.join(',')
    }
    return params
  }, [selectedReport, month, dateFrom, dateTo, productModule, caseManagerUserIds])

  const cmOptions = useMemo(
    () => cms.map((cm) => ({ value: String(cm.id), label: cm.full_name || cm.email || `CM #${cm.id}` })),
    [cms],
  )

  const loadPreview = useCallback(async () => {
    const qs = buildQuery(filterParams)
    const data = await run(() => apiFetch(`/api/v1/admin/hr-reports/${reportKey}?${qs}`), {
      successMsg: 'Report preview loaded',
    })
    setPreview(data)
  }, [filterParams, reportKey, run])

  const downloadReport = useCallback(
    async (format) => {
      const qs = buildQuery({ ...filterParams, format })
      const ext = format === 'xlsx' ? 'xlsx' : format
      const stamp = downloadDateStamp()
      await run(
        () => apiDownload(`/api/v1/admin/hr-reports/${reportKey}?${qs}`, `${reportKey}-${stamp}.${ext}`),
        { successMsg: `${format.toUpperCase()} download started` },
      )
    },
    [filterParams, reportKey, run],
  )

  const previewRows = preview?.rows || []
  const summaryRows = preview?.summaryRows || []
  const previewColumns = previewRows[0] ? Object.keys(previewRows[0]) : []

  return (
    <div className="admin-page admin-hr-reports">
      <AdminPageHeader
        eyebrow="People & HR"
        title="Reports"
        subtitle="Download operational, attendance, and compliance exports for HR and admin review."
      />

      <AdminPanel title="Report catalog" padded>
        <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
        <p className="admin-muted admin-hr-reports__hint">
          Exports use <strong>Case ID</strong> and therapist external IDs. For full therapist and case Excel rosters,
          use{' '}
          <Link to="/admin/reports?tab=operations">Operations exports</Link>.
        </p>

        <div className="admin-hr-reports__categories" role="tablist" aria-label="Report categories">
          {visibleCategories.map((cat) => (
            <button
              key={cat.id}
              type="button"
              role="tab"
              aria-selected={categoryId === cat.id}
              className={`admin-hr-reports__category${categoryId === cat.id ? ' is-active' : ''}`}
              onClick={() => setCategoryId(cat.id)}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="admin-hr-reports__cards">
          {reportsInCategory.map((report) => (
            <button
              key={report.key}
              type="button"
              className={`admin-hr-reports__card${reportKey === report.key ? ' is-selected' : ''}`}
              onClick={() => setReportKey(report.key)}
            >
              <span className="admin-hr-reports__card-title">{report.label}</span>
              {report.description ? (
                <span className="admin-hr-reports__card-desc">{report.description}</span>
              ) : null}
            </button>
          ))}
        </div>
      </AdminPanel>

      <AdminPanel title={selectedReport?.label || 'Generate report'} padded>
        <div className="admin-hr-reports__filters">
          {reportUsesMonth(selectedReport) ? (
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
          {reportUsesDateRange(selectedReport) ? (
            <>
              <label className="client-inv__filter-field">
                <span className="client-inv__filter-label">From</span>
                <input
                  type="date"
                  className="client-inv__filter-input"
                  value={dateFrom}
                  onChange={(e) => setDateFrom(e.target.value)}
                />
              </label>
              <label className="client-inv__filter-field">
                <span className="client-inv__filter-label">To</span>
                <input
                  type="date"
                  className="client-inv__filter-input"
                  value={dateTo}
                  onChange={(e) => setDateTo(e.target.value)}
                />
              </label>
            </>
          ) : null}
          {selectedReport?.filters?.includes('product_module') ? (
            <label className="client-inv__filter-field">
              <span className="client-inv__filter-label">Programme</span>
              <ServiceFilterSelect
                className="client-inv__filter-input"
                value={productModule}
                onChange={setProductModule}
                id="hr-report-programme"
              />
            </label>
          ) : null}
          {selectedReport?.filters?.includes('case_manager_user_id') ? (
            <MultiSelect
              label="Case manager"
              values={caseManagerUserIds}
              onChange={setCaseManagerUserIds}
              options={cmOptions}
              placeholder="All case managers"
              id="hr-report-case-managers"
            />
          ) : null}
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
          {(selectedReport?.formats || ['csv']).includes('csv') ? (
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              disabled={loading}
              onClick={() => downloadReport('csv')}
            >
              CSV
            </button>
          ) : null}
          {(selectedReport?.formats || []).includes('xlsx') ? (
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              disabled={loading}
              onClick={() => downloadReport('xlsx')}
            >
              Excel
            </button>
          ) : null}
          {(selectedReport?.formats || []).includes('pdf') ? (
            <button
              type="button"
              className="admin-btn admin-btn--secondary admin-btn--sm"
              disabled={loading}
              onClick={() => downloadReport('pdf')}
            >
              PDF
            </button>
          ) : null}
        </div>

        {previewRows.length ? (
          <div className="admin-table-wrap admin-hr-reports__preview-wrap" style={{ marginTop: 16 }}>
            <table className="admin-table admin-hr-reports__preview-table">
              <thead>
                <tr>
                  {previewColumns.map((k) => (
                    <th key={k}>{k}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {previewRows.slice(0, 50).map((row, idx) => (
                  <tr key={idx}>
                    {previewColumns.map((k) => (
                      <td key={k} className={k === 'Description' ? 'admin-hr-reports__td-desc' : undefined}>
                        <ExpandableTextCell column={k} value={formatPreviewCell(k, row[k])} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.count > 50 ? (
              <p className="admin-muted">Showing first 50 of {preview.count} rows. Download for the full export.</p>
            ) : null}
          </div>
        ) : preview ? (
          <p className="admin-muted" style={{ marginTop: 12 }}>
            No rows for this report and filter set.
          </p>
        ) : null}

        {summaryRows.length ? (
          <div style={{ marginTop: 20 }}>
            <h3 style={{ fontSize: '0.9375rem', marginBottom: 8 }}>Summary</h3>
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    {Object.keys(summaryRows[0]).map((k) => (
                      <th key={k}>{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {summaryRows.slice(0, 20).map((row, idx) => (
                    <tr key={idx}>
                      {Object.keys(summaryRows[0]).map((k) => (
                        <td key={k}>{String(row[k] ?? '')}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </AdminPanel>
    </div>
  )
}
