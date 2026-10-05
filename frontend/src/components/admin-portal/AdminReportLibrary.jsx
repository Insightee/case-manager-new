import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  currentBillingMonthIST,
  formatApiDateIN,
  formatDisplayDateRange,
  formatTimestampDateIN,
  isoMonthDateBounds,
  isoMonthToLongLabel,
  todayIsoIST,
} from '../../lib/datetime.js'
import { FINANCE_CATEGORY, FINANCE_REPORTS, PAGE_REPORTS } from '../../lib/financeReportsCatalog.js'
import { useClinicalProductModules } from '../../hooks/useClinicalProductModules.js'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import {
  AdminEmptyState,
  AdminFilterGrid,
  AdminPageHeader,
  AdminPanel,
  FilterDateRange,
  FilterMonth,
  FilterSelect,
  MultiSelect,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'
import { ExpandableTextCell } from './ui/ExpandableTextCell.jsx'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import './admin-report-library.css'

const PREVIEW_PAGE_SIZE = 50
const EXTRA_CATEGORIES = [
  { id: 'support', label: 'Support' },
  { id: 'quality', label: 'Data quality' },
  { id: 'clinical', label: 'Clinical review' },
]
const GENERIC_STATUS_OPTIONS = [{ value: '', label: 'All statuses' }]

function buildQuery(params) {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value != null) qs.set(key, String(value))
  })
  return qs.toString()
}

function usesFilter(report, name) {
  return Boolean(report?.filters?.includes(name))
}

function moneyKey(key) {
  return /inr|amount|total|balance|pay|margin/i.test(key)
}

function statusKey(key) {
  return /status/i.test(key)
}

function dateKey(key) {
  return /date|raised|generated|created|reported|paid at|last /i.test(key)
}

function headerLabel(key) {
  return String(key)
    .replace(/([A-Z])/g, ' $1')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function formatCell(column, value) {
  if (value == null || value === '') return ''
  const str = String(value)
  if (dateKey(column)) {
    return formatTimestampDateIN(str) || formatApiDateIN(str) || str
  }
  return str
}

function CaseTypeFilter({ value, onChange }) {
  const { options } = useClinicalProductModules()
  const mapped = options.map((o) => ({
    value: o.value,
    label: o.value ? o.label : 'All case types',
  }))
  return (
    <FilterSelect
      label="Case type"
      id="report-lib-case-type"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      options={mapped}
    />
  )
}

export function AdminReportLibrary({
  defaultCategory = 'finance',
  defaultReportKey = '',
  eyebrow = 'Reports',
  title = 'Reports',
  subtitle = 'Pick a report, set month, case type, period, and status, then generate or download.',
  embedded = false,
}) {
  const { can, hasFeature } = useAuth()
  const canFinance = can('invoice.approve')
  const canHr = hasFeature('hr_reports') || can('hr_report.export') || can('user.manage')
  const canTickets = can('ticket.manage')
  const canPeople = can('user.manage') || can('therapist.read')
  const canClinical = can('monthly_report.approve')

  const [searchParams, setSearchParams] = useSearchParams()
  const [hrCatalog, setHrCatalog] = useState({ categories: [], reports: [] })
  const [hrReady, setHrReady] = useState(!canHr)
  const [cms, setCms] = useState([])
  const [query, setQuery] = useState('')
  const [categoryId, setCategoryId] = useState(searchParams.get('group') || defaultCategory)
  const [reportKey, setReportKey] = useState(searchParams.get('report') || defaultReportKey)
  const [month, setMonth] = useState(searchParams.get('month') || currentBillingMonthIST())
  const [dateFrom, setDateFrom] = useState(searchParams.get('from') || isoMonthDateBounds(currentBillingMonthIST()).dateFrom)
  const [dateTo, setDateTo] = useState(searchParams.get('to') || isoMonthDateBounds(currentBillingMonthIST()).dateTo)
  const [productModule, setProductModule] = useState(searchParams.get('type') || '')
  const [status, setStatus] = useState(searchParams.get('status') || '')
  const [caseId, setCaseId] = useState(searchParams.get('case') || '')
  const [therapistUserId, setTherapistUserId] = useState('')
  const [caseManagerUserIds, setCaseManagerUserIds] = useState([])
  const [caseStatuses, setCaseStatuses] = useState('ACTIVE')
  const [page, setPage] = useState(1)
  const [preview, setPreview] = useState(null)
  const [monthClose, setMonthClose] = useState(null)
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  useEffect(() => {
    if (!canHr) return undefined
    let cancelled = false
    apiFetch('/api/v1/admin/hr-reports/catalog')
      .then((data) => {
        if (cancelled) return
        setHrCatalog({ categories: data.categories || [], reports: data.reports || [] })
      })
      .catch(() => {
        if (!cancelled) setHrCatalog({ categories: [], reports: [] })
      })
      .finally(() => {
        if (!cancelled) setHrReady(true)
      })
    apiFetch('/api/v1/admin/users/directory?roles=CASE_MANAGER')
      .then((rows) => {
        if (!cancelled) setCms(rows || [])
      })
      .catch(() => {
        if (!cancelled) setCms([])
      })
    return () => {
      cancelled = true
    }
  }, [canHr])

  const reports = useMemo(() => {
    const hr = (hrCatalog.reports || [])
      .filter((r) => r.category !== 'legacy')
      .map((r) => ({ ...r, source: 'hr' }))
    const finance = canFinance ? FINANCE_REPORTS : []
    const pages = PAGE_REPORTS.filter((r) => {
      if (r.key === 'ticket-report') return canTickets
      if (r.key === 'therapist-attention' || r.key === 'data-exceptions') return canPeople
      if (r.key === 'clinical-review') return canClinical
      return true
    })
    return [...finance, ...hr, ...pages]
  }, [hrCatalog.reports, canFinance, canTickets, canPeople, canClinical])

  const categories = useMemo(() => {
    const fromHr = (hrCatalog.categories || []).filter((c) => c.id !== 'legacy')
    const list = []
    if (canFinance) list.push(FINANCE_CATEGORY)
    list.push(...fromHr)
    EXTRA_CATEGORIES.forEach((cat) => {
      if (reports.some((r) => r.category === cat.id) && !list.some((c) => c.id === cat.id)) list.push(cat)
    })
    return list
  }, [hrCatalog.categories, canFinance, reports])

  const visibleReports = useMemo(() => {
    const q = query.trim().toLowerCase()
    return reports.filter((r) => {
      if (categoryId && r.category !== categoryId) return false
      if (!q) return true
      return `${r.label} ${r.description || ''}`.toLowerCase().includes(q)
    })
  }, [reports, categoryId, query])

  const selected = useMemo(() => {
    const match = reports.find((r) => r.key === reportKey)
    if (match) return match
    if (!hrReady && defaultReportKey) return null
    return visibleReports[0] || reports[0] || null
  }, [reports, reportKey, visibleReports, hrReady, defaultReportKey])

  useEffect(() => {
    if (!selected) return
    if (selected.key !== reportKey) setReportKey(selected.key)
  }, [selected, reportKey])

  useEffect(() => {
    const allowed = new Set((selected?.statusOptions || []).map((o) => o.value))
    if (status && allowed.size && !allowed.has(status)) setStatus('')
  }, [selected?.key, selected?.statusOptions, status])

  useEffect(() => {
    setSearchParams((prev) => {
      const next = embedded ? new URLSearchParams(prev) : new URLSearchParams()
      if (embedded) {
        if (selected?.key) next.set('report', selected.key)
        else next.delete('report')
        if (categoryId) next.set('group', categoryId)
        else next.delete('group')
        return next
      }
      if (selected?.key) next.set('report', selected.key)
      if (categoryId) next.set('group', categoryId)
      if (month) next.set('month', month)
      if (dateFrom) next.set('from', dateFrom)
      if (dateTo) next.set('to', dateTo)
      if (productModule) next.set('type', productModule)
      if (status) next.set('status', status)
      if (caseId) next.set('case', caseId)
      return next
    }, { replace: true })
  }, [selected?.key, categoryId, month, dateFrom, dateTo, productModule, status, caseId, embedded, setSearchParams])

  function selectReport(report) {
    setReportKey(report.key)
    setCategoryId(report.category)
    setPreview(null)
    setPage(1)
    clearMessages()
  }

  function applyMonth(nextMonth) {
    setMonth(nextMonth)
    const bounds = isoMonthDateBounds(nextMonth)
    setDateFrom(bounds.dateFrom)
    setDateTo(bounds.dateTo)
  }

  const filterParams = useMemo(() => {
    if (!selected || selected.kind === 'page') return {}
    const params = {
      month,
      billing_month: month,
      date_from: dateFrom,
      date_to: dateTo,
    }
    if (productModule) params.product_module = productModule
    if (status) params.status = status
    if (usesFilter(selected, 'case_id') && caseId) params.case_id = caseId
    if (usesFilter(selected, 'therapist_user_id') && therapistUserId) params.therapist_user_id = therapistUserId
    if (usesFilter(selected, 'case_manager_user_id') && caseManagerUserIds.length) {
      params.case_manager_user_id = caseManagerUserIds.join(',')
    }
    if (usesFilter(selected, 'case_statuses') && caseStatuses.trim()) {
      params.case_statuses = caseStatuses.trim()
    }
    if (selected.source !== 'finance') delete params.billing_month
    if (selected.source === 'finance' && !usesFilter(selected, 'month')) delete params.month
    return params
  }, [selected, month, dateFrom, dateTo, productModule, status, caseId, therapistUserId, caseManagerUserIds, caseStatuses])

  const endpoint = selected?.source === 'finance'
    ? `/api/v1/admin/finance-reports/${selected.key}`
    : selected?.source === 'hr'
      ? `/api/v1/admin/hr-reports/${selected.key}`
      : null

  const loadMonthClose = useCallback(async (ym) => {
    if (!canFinance) return
    try {
      const data = await apiFetch(
        `/api/v1/admin/finance-reports/billing-month-close?billing_month=${encodeURIComponent(ym)}`,
      )
      setMonthClose(data)
    } catch {
      setMonthClose(null)
    }
  }, [canFinance])

  async function loadPreview(nextPage = 1) {
    if (!endpoint) return
    const extra = selected.source === 'finance' ? { page: nextPage, page_size: PREVIEW_PAGE_SIZE } : {}
    try {
      const data = await run(
        () => apiFetch(`${endpoint}?${buildQuery({ ...filterParams, ...extra })}`),
        { successMsg: 'Preview ready' },
      )
      if (data) {
        setPreview(data)
        setPage(nextPage)
      }
      if (selected.closeMonth) await loadMonthClose(month)
    } catch {
      setPreview(null)
    }
  }

  async function download(format) {
    if (!endpoint) return
    try {
      await run(
        () =>
          apiDownload(
            `${endpoint}?${buildQuery({ ...filterParams, format })}`,
            `${selected.key}-${todayIsoIST()}.${format === 'xlsx' ? 'xlsx' : format}`,
          ),
        { successMsg: `${format.toUpperCase()} download started` },
      )
    } catch {
      /* error already surfaced */
    }
  }

  async function closeBillingMonth() {
    try {
      await run(
        () =>
          apiFetch('/api/v1/admin/finance-reports/close-billing-month', {
            method: 'POST',
            body: JSON.stringify({ billing_month: month }),
          }),
        { successMsg: `Billing month ${month} closed` },
      )
      await loadMonthClose(month)
    } catch {
      /* error already surfaced */
    }
  }

  const rows = preview?.rows || []
  const summaryRows = preview?.summaryRows || []
  const columns = rows[0] ? Object.keys(rows[0]) : []
  const summaryColumns = summaryRows[0] ? Object.keys(summaryRows[0]) : []
  const total = preview?.count ?? rows.length
  const totalPages = Math.max(1, Math.ceil((preview?.count || 0) / PREVIEW_PAGE_SIZE))
  const statusOptions = selected?.statusOptions?.length ? selected.statusOptions : GENERIC_STATUS_OPTIONS
  const generateable = selected && selected.kind !== 'page'
  const cmOptions = useMemo(
    () => cms.map((cm) => ({ value: String(cm.id), label: cm.full_name || cm.email || `CM #${cm.id}` })),
    [cms],
  )
  const caseTypeLabel = productModule
    ? productModule.replace(/_/g, ' ')
    : 'All case types'
  const statusLabel = statusOptions.find((o) => o.value === status)?.label || 'All statuses'
  const periodLabel = formatDisplayDateRange(dateFrom, dateTo) || 'Period not set'

  function renderLedger(tableRows, tableColumns, caption) {
    if (!tableRows.length) return null
    return (
      <div className="report-lib__ledger">
        {caption ? <p className="admin-muted report-lib__meta">{caption}</p> : null}
        <table>
          <thead>
            <tr>
              {tableColumns.map((k) => (
                <th key={k}>{headerLabel(k)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row, i) => (
              <tr key={row.caseId ? `${row.caseId}-${i}` : i}>
                {tableColumns.map((k) => {
                  const value = row[k]
                  if (moneyKey(k) && value !== '' && value != null && !Number.isNaN(Number(value))) {
                    return (
                      <td key={k} className="report-lib__money">
                        {formatCurrency(Number(value))}
                      </td>
                    )
                  }
                  if (statusKey(k) && value) {
                    return (
                      <td key={k}>
                        <StatusBadge status={String(value)} />
                      </td>
                    )
                  }
                  return (
                    <td key={k}>
                      <ExpandableTextCell column={k} value={formatCell(k, value)} />
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className={embedded ? 'report-lib' : 'admin-page report-lib'}>
      {embedded ? null : (
        <AdminPageHeader eyebrow={eyebrow} title={title} subtitle={subtitle} />
      )}

      <div className="report-lib__layout">
        <aside className="report-lib__picker" aria-label="Report list">
          <input
            className="report-lib__search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search reports"
            aria-label="Search reports"
          />
          <div className="report-lib__cats" role="tablist" aria-label="Report groups">
            {categories.map((cat) => (
              <button
                key={cat.id}
                type="button"
                role="tab"
                aria-selected={categoryId === cat.id}
                className={`report-lib__cat${categoryId === cat.id ? ' is-active' : ''}`}
                onClick={() => {
                  setCategoryId(cat.id)
                  const first = reports.find((r) => r.category === cat.id)
                  if (first) selectReport(first)
                }}
              >
                {cat.label}
              </button>
            ))}
          </div>
          <label className="report-lib__mobile-pick">
            <span className="admin-filter-field__label">Report</span>
            <select
              className="admin-filter-select__input"
              value={selected?.key || ''}
              onChange={(e) => {
                const report = reports.find((r) => r.key === e.target.value)
                if (report) selectReport(report)
              }}
              aria-label="Choose report"
            >
              {visibleReports.map((report) => (
                <option key={`${report.source}-${report.key}`} value={report.key}>
                  {report.label}
                </option>
              ))}
            </select>
          </label>
          <div className="report-lib__list">
            {visibleReports.map((report) => (
              <button
                key={`${report.source}-${report.key}`}
                type="button"
                className={`report-lib__item${selected?.key === report.key ? ' is-selected' : ''}`}
                onClick={() => selectReport(report)}
              >
                <span className="report-lib__item-title">{report.label}</span>
                {report.description ? <span className="report-lib__item-desc">{report.description}</span> : null}
                <span className="report-lib__item-meta">
                  {(report.formats || []).join(' · ') || 'Open in page'}
                </span>
              </button>
            ))}
            {!visibleReports.length ? <p className="admin-muted">No reports in this group.</p> : null}
          </div>
        </aside>

        <div className="report-lib__workspace">
          <AdminPanel title={selected?.label || 'Choose a report'} padded>
            <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
            <div className="report-lib__hero">
              <p className="report-lib__hint">
                {selected?.description || 'Choose a report from the list.'}
                {' '}
                Dates use Asia/Kolkata. Month sets the billing cohort; period dates apply to collections and ranged reports.
              </p>
              {generateable ? (
                <div className="report-lib__chips" aria-label="Active period">
                  <span className="report-lib__chip">{isoMonthToLongLabel(month) || month}</span>
                  <span className="report-lib__chip report-lib__chip--muted">{periodLabel}</span>
                  <span className="report-lib__chip report-lib__chip--muted">{caseTypeLabel}</span>
                  <span className="report-lib__chip report-lib__chip--muted">{statusLabel}</span>
                </div>
              ) : null}
            </div>

            {selected?.kind === 'page' ? (
              <p>
                <Link to={selected.href} className="admin-btn admin-btn--primary">
                  Open {selected.label}
                </Link>
              </p>
            ) : (
              <>
                <AdminFilterGrid ariaLabel="Report filters">
                  <FilterMonth
                    label="Month"
                    id="report-lib-month"
                    value={month}
                    onChange={(e) => applyMonth(e.target.value)}
                  />
                  <CaseTypeFilter value={productModule} onChange={setProductModule} />
                  <FilterDateRange
                    label="Period"
                    from={dateFrom}
                    to={dateTo}
                    onFromChange={(e) => setDateFrom(e.target.value)}
                    onToChange={(e) => setDateTo(e.target.value)}
                  />
                  <FilterSelect
                    label="Report status"
                    id="report-lib-status"
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    options={statusOptions}
                  />
                  {usesFilter(selected, 'case_id') ? (
                    <label className="admin-filter-field">
                      <span className="admin-filter-field__label">Case ID</span>
                      <input
                        type="number"
                        min="1"
                        className="admin-filter-select__input admin-input"
                        value={caseId}
                        onChange={(e) => setCaseId(e.target.value)}
                        placeholder="All cases"
                        aria-label="Case ID"
                      />
                    </label>
                  ) : null}
                  {usesFilter(selected, 'therapist_user_id') ? (
                    <label className="admin-filter-field">
                      <span className="admin-filter-field__label">Therapist ID</span>
                      <input
                        type="number"
                        min="1"
                        className="admin-filter-select__input admin-input"
                        value={therapistUserId}
                        onChange={(e) => setTherapistUserId(e.target.value)}
                        placeholder="All therapists"
                        aria-label="Therapist user ID"
                      />
                    </label>
                  ) : null}
                  {usesFilter(selected, 'case_manager_user_id') ? (
                    <MultiSelect
                      label="Case manager"
                      values={caseManagerUserIds}
                      onChange={setCaseManagerUserIds}
                      options={cmOptions}
                      placeholder="All case managers"
                      id="report-lib-case-managers"
                    />
                  ) : null}
                  {usesFilter(selected, 'case_statuses') ? (
                    <label className="admin-filter-field">
                      <span className="admin-filter-field__label">Case statuses</span>
                      <input
                        type="text"
                        className="admin-filter-select__input admin-input"
                        value={caseStatuses}
                        placeholder="ACTIVE"
                        onChange={(e) => setCaseStatuses(e.target.value)}
                        aria-label="Case statuses"
                      />
                    </label>
                  ) : null}
                </AdminFilterGrid>

                <div className="admin-btn-group report-lib__actions">
                  <button
                    type="button"
                    className="admin-btn admin-btn--primary"
                    disabled={loading}
                    onClick={() => loadPreview(1)}
                  >
                    {loading ? 'Generating…' : 'Generate'}
                  </button>
                  {(selected?.formats || []).includes('csv') ? (
                    <button type="button" className="admin-btn admin-btn--secondary" disabled={loading} onClick={() => download('csv')}>
                      CSV
                    </button>
                  ) : null}
                  {(selected?.formats || []).includes('xlsx') ? (
                    <button type="button" className="admin-btn admin-btn--secondary" disabled={loading} onClick={() => download('xlsx')}>
                      Excel
                    </button>
                  ) : null}
                  {(selected?.formats || []).includes('pdf') ? (
                    <button type="button" className="admin-btn admin-btn--secondary" disabled={loading} onClick={() => download('pdf')}>
                      PDF
                    </button>
                  ) : null}
                  {selected?.closeMonth ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost"
                      disabled={loading || monthClose?.closed}
                      onClick={closeBillingMonth}
                    >
                      {monthClose?.closed ? 'Month closed' : 'Close month'}
                    </button>
                  ) : null}
                </div>
              </>
            )}

            {monthClose?.closed && selected?.closeMonth ? (
              <p className="admin-muted report-lib__meta">
                {month} is closed — payout preview reads frozen snapshots.
              </p>
            ) : null}
            {preview?.generatedAt ? (
              <p className="admin-muted report-lib__meta">
                Generated {preview.generatedAt}
                {preview.generatedBy ? ` by ${preview.generatedBy}` : ''}
                {preview.dataSource ? ` · ${preview.dataSource}` : ''}
                {preview.dateBasis ? ` · ${preview.dateBasis}` : ''}
                {preview.confirmedTotalInr != null ? ` · confirmed ${formatCurrency(preview.confirmedTotalInr)}` : ''}
              </p>
            ) : null}

            {rows.length || summaryRows.length ? (
              <>
                <p className="admin-muted report-lib__meta">
                  Showing {rows.length} of {total} matching rows
                  {preview?.previewLimited ? ' — this page is a preview; export includes the full generate.' : '.'}
                </p>
                {renderLedger(summaryRows, summaryColumns, summaryRows.length ? 'Summary' : '')}
                {renderLedger(rows, columns)}
                {selected?.source === 'finance' && totalPages > 1 ? (
                  <div className="admin-btn-group" style={{ marginTop: 12 }}>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={loading || page <= 1} onClick={() => loadPreview(page - 1)}>
                      Previous
                    </button>
                    <span className="admin-muted">Page {page} of {totalPages}</span>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={loading || page >= totalPages} onClick={() => loadPreview(page + 1)}>
                      Next
                    </button>
                  </div>
                ) : null}
              </>
            ) : preview ? (
              <div className="report-lib__empty">
                <AdminEmptyState
                  title="No rows for these filters"
                  description="Would you like to continue from a different month, case type, period, or status?"
                />
              </div>
            ) : generateable ? (
              <div className="report-lib__empty">
                <AdminEmptyState
                  title="Set the period, then generate"
                  description="Month, case type, start date, end date, and report status all apply to Generate, CSV, and Excel."
                  action={(
                    <button type="button" className="admin-btn admin-btn--primary" disabled={loading} onClick={() => loadPreview(1)}>
                      Generate preview
                    </button>
                  )}
                />
              </div>
            ) : null}
          </AdminPanel>
        </div>
      </div>
    </div>
  )
}
