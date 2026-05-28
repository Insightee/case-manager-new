import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, getTokens } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  IEP_CATEGORY_ID,
  REPORT_KIND_OPTIONS,
  reportCategoryOptions,
  reportKindLabel,
} from '../../lib/reportFilters.js'
import { AdminCollapsibleFilters, AdminPageHeader, AdminSearchInput, ServiceFilterSelect } from './ui/index.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminReportDetailDrawer } from './AdminReportDetailDrawer.jsx'
import { AdminReportsTable } from './AdminReportsTable.jsx'
import './admin-reports.css'

const API_URL = import.meta.env.VITE_API_URL || ''

async function downloadExport(path, filename) {
  const { access } = getTokens()
  const res = await fetch(`${API_URL}${path}`, {
    headers: access ? { Authorization: `Bearer ${access}` } : {},
  })
  if (!res.ok) throw new Error('Export failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function buildListQuery(filters, page, pageSize) {
  const p = new URLSearchParams()
  p.set('page', String(page))
  p.set('page_size', String(pageSize))
  if (filters.search) p.set('search', filters.search)
  if (filters.status) p.set('status', filters.status)
  if (filters.module) p.set('product_module', filters.module)
  if (filters.month) p.set('month', filters.month)
  if (filters.category) p.set('category', filters.category)
  if (filters.parentReview) p.set('parent_review_status', filters.parentReview)
  if (filters.caseId) p.set('case_id', filters.caseId)
  return `?${p.toString()}`
}

const CATEGORY_OPTIONS = reportCategoryOptions()

const VIEW_TAB_OPTIONS = [
  { value: 'queue', label: 'Review queue' },
  { value: 'all', label: 'All reports' },
  { value: 'missing', label: 'Missing monthly' },
  { value: 'iep', label: 'Pending IEP' },
]

function viewTabLabel(tab) {
  return VIEW_TAB_OPTIONS.find((o) => o.value === tab)?.label || 'Review queue'
}

export function AdminReportsPage() {
  const { canReviewReports } = useModuleWrite()
  const { can } = useAuth()
  const seesAllCases = can('case.read.all')
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'queue'
  const typeFilter = searchParams.get('type') || searchParams.get('kind') || 'all'
  const showReportFilters = tab === 'queue' || tab === 'all'
  const drawerType = searchParams.get('type') === 'observation' ? 'observation' : searchParams.get('type') === 'monthly' ? 'monthly' : null
  const drawerId = searchParams.get('reportId') ? Number(searchParams.get('reportId')) : null

  const [summary, setSummary] = useState(null)
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [selected, setSelected] = useState(() => new Set())
  const [bulkRejectOpen, setBulkRejectOpen] = useState(false)
  const [bulkComment, setBulkComment] = useState('')
  const [acting, setActing] = useState(false)

  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [status, setStatus] = useState(searchParams.get('status') || '')
  const [module, setModule] = useState(searchParams.get('module') || '')
  const [month, setMonth] = useState(searchParams.get('month') || '')
  const [category, setCategory] = useState(searchParams.get('category') || '')
  const [missingMonth, setMissingMonth] = useState(
    () => new Date().toLocaleString('en-US', { month: 'long', year: 'numeric' }),
  )
  const [missingRows, setMissingRows] = useState([])
  const [iepRows, setIepRows] = useState([])
  const [iepSummary, setIepSummary] = useState(null)
  const [filtersOpen, setFiltersOpen] = useState(false)

  const filters = useMemo(
    () => ({
      search,
      status,
      module,
      month,
      category,
      parentReview: '',
      caseId: searchParams.get('case_id') || '',
    }),
    [search, status, module, month, category, searchParams],
  )

  const loadSummary = useCallback(async () => {
    try {
      const data = await apiFetch('/api/v1/admin/reports/summary')
      setSummary(data)
    } catch {
      setSummary(null)
    }
  }, [])

  const loadList = useCallback(async () => {
    setLoading(true)
    setMessage('')
    try {
      const qs = buildListQuery(filters, page, pageSize)
      let data
      if (tab === 'queue') {
        const q = new URLSearchParams(qs.slice(1))
        if (typeFilter && typeFilter !== 'all') q.set('type', typeFilter)
        data = await apiFetch(`/api/v1/admin/reports/queue?${q.toString()}`)
      } else if (typeFilter === 'observation') {
        data = await apiFetch(`/api/v1/admin/reports/observation${qs}`)
      } else if (typeFilter === 'monthly') {
        data = await apiFetch(`/api/v1/admin/reports/monthly${qs}`)
      } else {
        const [m, o] = await Promise.all([
          apiFetch(`/api/v1/admin/reports/monthly${qs}&page_size=${Math.ceil(pageSize / 2)}`),
          apiFetch(`/api/v1/admin/reports/observation${qs}&page_size=${Math.ceil(pageSize / 2)}`),
        ])
        const merged = [...(m.items || []), ...(o.items || [])].sort(
          (a, b) => new Date(b.updated_at || 0) - new Date(a.updated_at || 0),
        )
        data = {
          items: merged.slice(0, pageSize),
          total: (m.total || 0) + (o.total || 0),
          page,
          page_size: pageSize,
          pages: Math.max(m.pages || 1, o.pages || 1),
        }
      }
      setRows(data.items || [])
      setTotal(data.total ?? 0)
    } catch (err) {
      setRows([])
      setMessage(err.message || 'Could not load reports')
    } finally {
      setLoading(false)
    }
  }, [tab, typeFilter, filters, page, pageSize])

  useEffect(() => {
    loadSummary()
  }, [loadSummary])

  const loadIepPending = useCallback(async () => {
    if (tab !== 'iep') return
    setLoading(true)
    try {
      const q = new URLSearchParams()
      if (module) q.set('product_module', module)
      if (search) q.set('search', search)
      const data = await apiFetch(`/api/v1/admin/iep/dashboard?${q}`)
      const pending = (data.rows || []).filter((r) => r.iep_status !== 'ACKNOWLEDGED')
      setIepRows(pending)
      setIepSummary(data.summary || null)
      setMessage('')
    } catch (err) {
      setIepRows([])
      setMessage(err.message || 'Could not load pending IEP')
    } finally {
      setLoading(false)
    }
  }, [tab, module, search])

  const loadMissing = useCallback(async () => {
    if (tab !== 'missing') return
    setLoading(true)
    try {
      const q = new URLSearchParams({ month: missingMonth })
      if (module) q.set('product_module', module)
      const rows = await apiFetch(`/api/v1/admin/reports/missing-monthly?${q}`)
      setMissingRows(rows || [])
      setMessage('')
    } catch (err) {
      setMissingRows([])
      setMessage(err.message || 'Could not load missing reports')
    } finally {
      setLoading(false)
    }
  }, [tab, missingMonth, module])

  useEffect(() => {
    if (tab === 'missing') loadMissing()
    else if (tab === 'iep') loadIepPending()
    else loadList()
  }, [tab, loadList, loadMissing, loadIepPending])

  useEffect(() => {
    setPage(1)
  }, [tab, typeFilter, search, status, module, month, category])

  function openDrawer(row) {
    const next = new URLSearchParams(searchParams)
    next.set('reportId', String(row.id))
    next.set('type', row.report_type)
    setSearchParams(next, { replace: true })
  }

  function closeDrawer() {
    const next = new URLSearchParams(searchParams)
    next.delete('reportId')
    if (next.get('type') && !typeFilter) next.delete('type')
    setSearchParams(next, { replace: true })
  }

  function setTab(nextTab) {
    const next = new URLSearchParams(searchParams)
    next.set('tab', nextTab)
    setSearchParams(next, { replace: true })
  }

  function setKindFilter(kind) {
    const next = new URLSearchParams(searchParams)
    if (kind === 'all') {
      next.delete('type')
      next.delete('kind')
    } else {
      next.set('type', kind)
    }
    setSearchParams(next, { replace: true })
  }

  function setCategoryFilter(cat) {
    if (cat === IEP_CATEGORY_ID) {
      const next = new URLSearchParams(searchParams)
      next.set('tab', 'iep')
      next.delete('category')
      setSearchParams(next, { replace: true })
      setCategory('')
      return
    }
    setCategory(cat)
    const next = new URLSearchParams(searchParams)
    if (cat) next.set('category', cat)
    else next.delete('category')
    setSearchParams(next, { replace: true })
  }

  function toggleSelect(key) {
    setSelected((prev) => {
      const n = new Set(prev)
      if (n.has(key)) n.delete(key)
      else n.add(key)
      return n
    })
  }

  function toggleAll(checked) {
    if (!checked) setSelected(new Set())
    else setSelected(new Set(rows.map((r) => `${r.report_type}:${r.id}`)))
  }

  function selectedByType() {
    const monthly = []
    const observation = []
    for (const key of selected) {
      const [t, id] = key.split(':')
      if (t === 'monthly') monthly.push(Number(id))
      else observation.push(Number(id))
    }
    return { monthly, observation }
  }

  const selectedRows = useMemo(
    () =>
      rows.filter((r) => selected.has(`${r.report_type}:${r.id}`)),
    [rows, selected],
  )

  const canBulkReview = useMemo(
    () =>
      selectedRows.length > 0 &&
      selectedRows.every((r) => canReviewReports(r.product_module || 'homecare')),
    [selectedRows, canReviewReports],
  )

  function assertBulkResult(result, label) {
    if (!result) return
    if (result.failed > 0) {
      const detail = result.errors?.[0] || `${result.failed} item(s) failed`
      throw new Error(`${label}: ${detail}`)
    }
  }

  async function bulkApprove() {
    const { monthly, observation } = selectedByType()
    setActing(true)
    setMessage('')
    try {
      if (monthly.length) {
        const result = await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'monthly',
            ids: monthly,
            visibility_status: 'APPROVED_FOR_PARENT',
            comment: 'Approved from report management',
          }),
        })
        assertBulkResult(result, 'Monthly approve')
      }
      if (observation.length) {
        const result = await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'observation',
            ids: observation,
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
        assertBulkResult(result, 'Observation approve')
      }
      setSelected(new Set())
      setMessage('Bulk approve completed.')
      loadList()
      loadSummary()
    } catch (err) {
      setMessage(err.message || 'Bulk approve failed')
    } finally {
      setActing(false)
    }
  }

  async function bulkReject() {
    if (!bulkComment.trim()) {
      setMessage('Comment required for bulk reject')
      return
    }
    const { monthly, observation } = selectedByType()
    setActing(true)
    try {
      if (monthly.length) {
        await apiFetch('/api/v1/admin/reports/bulk/reject', {
          method: 'POST',
          body: JSON.stringify({ report_type: 'monthly', ids: monthly, comment: bulkComment }),
        })
      }
      if (observation.length) {
        await apiFetch('/api/v1/admin/reports/bulk/reject', {
          method: 'POST',
          body: JSON.stringify({ report_type: 'observation', ids: observation, comment: bulkComment }),
        })
      }
      setBulkRejectOpen(false)
      setBulkComment('')
      setSelected(new Set())
      setMessage('Bulk reject completed.')
      loadList()
      loadSummary()
    } catch (err) {
      setMessage(err.message || 'Bulk reject failed')
    } finally {
      setActing(false)
    }
  }

  async function quickApprove(row) {
    setActing(true)
    setMessage('')
    try {
      if (row.report_type === 'monthly') {
        if (row.parent_review_status === 'CHANGES_REQUESTED') {
          await apiFetch(`/api/v1/reports/monthly/${row.id}/resend-to-parent`, { method: 'POST' })
        } else {
          if (!row.can_cm_publish && !row.can_admin_override_publish) {
            const days = row.days_until_admin_override
            throw new Error(
              days != null
                ? `Publish for parents is available in ${days} day(s) after submit (case manager publishes first).`
                : 'This report is not ready to publish for parents yet.',
            )
          }
          await apiFetch(`/api/v1/admin/reports/monthly/${row.id}/publish-to-parent`, {
            method: 'POST',
            body: JSON.stringify({ comment: 'Published from report list' }),
          })
        }
        setMessage('Report published for parents.')
      } else {
        const result = await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'observation',
            ids: [row.id],
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
        assertBulkResult(result, 'Approve')
        setMessage('Report approved for parents.')
      }
      loadList()
      loadSummary()
    } catch (err) {
      setMessage(err.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  function quickReject(row) {
    setSelected(new Set([`${row.report_type}:${row.id}`]))
    setBulkRejectOpen(true)
  }

  function exportPath(fmt) {
    const p = new URLSearchParams()
    if (typeFilter !== 'all') p.set('type', typeFilter)
    if (tab === 'queue') p.set('queue_only', 'true')
    if (filters.search) p.set('search', filters.search)
    if (filters.status) p.set('status', filters.status)
    if (filters.module) p.set('product_module', filters.module)
    if (filters.month) p.set('month', filters.month)
    if (filters.category) p.set('category', filters.category)
    if (filters.caseId) p.set('case_id', filters.caseId)
    const qs = p.toString()
    return `/api/v1/admin/reports/export/${fmt}${qs ? `?${qs}` : ''}`
  }

  const effectiveDrawerType =
    drawerType || (drawerId && rows.find((r) => r.id === drawerId)?.report_type) || 'monthly'

  return (
    <div>
      <AdminPageHeader
        title="Report management"
        subtitle={
          seesAllCases
            ? 'Review and approve reports across all cases in your programmes.'
            : 'Review and approve reports for cases assigned to you as case manager.'
        }
      />

      <p
        className={`admin-reports__scope ${seesAllCases ? 'admin-reports__scope--all' : 'admin-reports__scope--team'}`}
        role="status"
      >
        {seesAllCases ? 'Showing all cases' : 'Showing your assigned caseload only'}
      </p>

      {summary ? (
        <div className="admin-reports__kpis">
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.queue_total}</div>
            <div className="admin-reports__kpi-label">In review queue</div>
          </div>
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.monthly.under_review}</div>
            <div className="admin-reports__kpi-label">Monthly under review</div>
          </div>
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.monthly.parent_changes_requested}</div>
            <div className="admin-reports__kpi-label">Parent changes requested</div>
          </div>
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.observation.under_review}</div>
            <div className="admin-reports__kpi-label">Observation under review</div>
          </div>
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.monthly.published + summary.observation.published}</div>
            <div className="admin-reports__kpi-label">Published (combined)</div>
          </div>
          <div className="admin-reports__kpi">
            <div className="admin-reports__kpi-value">{summary.iep_pending ?? 0}</div>
            <div className="admin-reports__kpi-label">Pending IEP</div>
          </div>
        </div>
      ) : null}

      <div className="admin-reports__tabs admin-desktop-only" role="tablist" aria-label="Report views">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'queue'}
          className={`admin-btn admin-btn--sm ${tab === 'queue' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('queue')}
        >
          Review queue
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'all'}
          className={`admin-btn admin-btn--sm ${tab === 'all' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('all')}
        >
          All reports
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'missing'}
          className={`admin-btn admin-btn--sm ${tab === 'missing' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('missing')}
        >
          Missing monthly
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'iep'}
          className={`admin-btn admin-btn--sm ${tab === 'iep' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('iep')}
        >
          Pending IEP
          {summary?.iep_pending != null ? ` (${summary.iep_pending})` : ''}
        </button>
      </div>

      {showReportFilters ? (
        <div className="admin-reports__filters admin-desktop-only" role="group" aria-label="Report filters">
          <label className="admin-reports__filter">
            <span className="admin-reports__filter-label">Report type</span>
            <select
              className="admin-select admin-reports__filter-select"
              value={typeFilter}
              onChange={(e) => setKindFilter(e.target.value)}
              aria-label="Report type"
            >
              {REPORT_KIND_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-reports__filter">
            <span className="admin-reports__filter-label">Category</span>
            <select
              className="admin-select admin-reports__filter-select"
              value={category}
              onChange={(e) => setCategoryFilter(e.target.value)}
              aria-label="Report category"
            >
              {CATEGORY_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <p className="admin-reports__filter-hint admin-muted">
            Incident documents and IEP plans are managed under Support and Case IEP — not in this hub.
          </p>
        </div>
      ) : null}

      <AdminCollapsibleFilters
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        quickSearch={
          <AdminSearchInput value={search} onChange={setSearch} placeholder="Child, case, month, therapist…" />
        }
        activeChips={[
          tab !== 'queue' ? viewTabLabel(tab) : null,
          typeFilter !== 'all' && showReportFilters ? reportKindLabel(typeFilter) : null,
          category && showReportFilters ? `Category: ${category}` : null,
          status && `Status: ${status}`,
          module && `Service: ${module}`,
          month && `Month: ${month}`,
          filters.caseId && `Case #${filters.caseId}`,
        ].filter(Boolean)}
        activeCount={
          [
            tab !== 'queue' ? 1 : 0,
            typeFilter !== 'all' && showReportFilters ? 1 : 0,
            category && showReportFilters ? 1 : 0,
            status,
            module,
            month,
            filters.caseId,
          ].filter(Boolean).length
        }
      >
        <div className="admin-reports__filters admin-reports__filters--panel admin-mobile-only" role="group" aria-label="Report filters">
          <label className="admin-reports__filter">
            <span className="admin-reports__filter-label">View</span>
            <select
              className="admin-select admin-reports__filter-select"
              value={tab}
              onChange={(e) => setTab(e.target.value)}
              aria-label="Report view"
            >
              {VIEW_TAB_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                  {o.value === 'iep' && summary?.iep_pending != null ? ` (${summary.iep_pending})` : ''}
                </option>
              ))}
            </select>
          </label>
          {showReportFilters ? (
            <>
              <label className="admin-reports__filter">
                <span className="admin-reports__filter-label">Report type</span>
                <select
                  className="admin-select admin-reports__filter-select"
                  value={typeFilter}
                  onChange={(e) => setKindFilter(e.target.value)}
                  aria-label="Report type"
                >
                  {REPORT_KIND_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="admin-reports__filter">
                <span className="admin-reports__filter-label">Category</span>
                <select
                  className="admin-select admin-reports__filter-select"
                  value={category}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  aria-label="Report category"
                >
                  {CATEGORY_OPTIONS.map((o) => (
                    <option key={o.value || 'all'} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : null}
          {tab === 'missing' ? (
            <label className="admin-reports__filter">
              <span className="admin-reports__filter-label">Month</span>
              <input
                className="admin-input admin-reports__filter-select"
                value={missingMonth}
                onChange={(e) => setMissingMonth(e.target.value)}
                aria-label="Missing reports month"
              />
            </label>
          ) : null}
        </div>
      <div className="admin-reports__toolbar">
        <AdminSearchInput
          className="admin-desktop-only"
          value={search}
          onChange={setSearch}
          placeholder="Child, case, month, therapist…"
        />
        {tab === 'all' ? (
          <select className="admin-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="UNDER_REVIEW">Under review</option>
            <option value="PUBLISHED">Published</option>
            <option value="REJECTED">Rejected</option>
          </select>
        ) : null}
        <ServiceFilterSelect value={module} onChange={setModule} />
        {(typeFilter === 'all' || typeFilter === 'monthly') && tab === 'all' ? (
          <input
            className="admin-input"
            placeholder="Month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            style={{ maxWidth: 120 }}
          />
        ) : null}
        <select
          className="admin-select"
          value={pageSize}
          onChange={(e) => {
            setPageSize(Number(e.target.value))
            setPage(1)
          }}
        >
          <option value={25}>25 / page</option>
          <option value={50}>50 / page</option>
          <option value={100}>100 / page</option>
        </select>
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() => downloadExport(exportPath('xlsx'), 'reports-export.xlsx').catch((e) => setMessage(e.message))}
        >
          Export Excel
        </button>
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() => downloadExport(exportPath('pdf'), 'reports-export.pdf').catch((e) => setMessage(e.message))}
        >
          Export PDF
        </button>
      </div>
      </AdminCollapsibleFilters>

      {message ? <p className="admin-alert" style={{ marginBottom: 12 }}>{message}</p> : null}

      {selected.size > 0 ? (
        <div className="admin-reports__bulk-bar">
          <span>{selected.size} selected</span>
          {canBulkReview ? (
            <>
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={bulkApprove}>
            Approve for parents
          </button>
          <button type="button" className="admin-btn admin-btn--sm" disabled={acting} onClick={() => setBulkRejectOpen(true)}>
            Reject…
          </button>
            </>
          ) : (
            <span className="admin-muted" style={{ fontSize: '0.8rem' }}>
              View-only for one or more selected programme modules.
            </span>
          )}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setSelected(new Set())}>
            Clear
          </button>
        </div>
      ) : null}

      {bulkRejectOpen ? (
        <div style={{ marginBottom: 12 }}>
          <textarea
            className="admin-input"
            rows={2}
            placeholder="Rejection comment (required)"
            value={bulkComment}
            onChange={(e) => setBulkComment(e.target.value)}
          />
          <div className="admin-btn-group" style={{ marginTop: 8 }}>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={bulkReject}>
              Confirm bulk reject
            </button>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setBulkRejectOpen(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {tab === 'iep' ? (
        <div style={{ marginBottom: 16 }}>
          <p className="admin-muted" style={{ marginBottom: 12, fontSize: '0.8125rem' }}>
            IEP plans are managed in the IEP module — this tab lists cases that still need upload, internal review, or parent acknowledgement.
          </p>
          {iepSummary ? (
            <p style={{ fontSize: '0.8125rem', marginBottom: 12 }}>
              Missing {iepSummary.missing} · Internal {iepSummary.internal_only} · Awaiting ack {iepSummary.awaiting_ack}
            </p>
          ) : null}
          {loading ? (
            <p>Loading…</p>
          ) : iepRows.length === 0 ? (
            <p className="admin-muted">No pending IEP work for your caseload.</p>
          ) : (
            <div className="admin-table-wrap admin-reports__iep-table">
              <table className="admin-table admin-table--compact">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Child</th>
                    <th>Programme</th>
                    <th>IEP status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {iepRows.map((r) => (
                    <tr key={r.case_id}>
                      <td>
                        <span className="admin-table__primary">{r.case_code}</span>
                      </td>
                      <td>{r.child_name || '—'}</td>
                      <td>
                        <span className="admin-chip admin-chip--sm">{r.product_module}</span>
                      </td>
                      <td>
                        <span
                          className={`admin-reports__iep-pill ${
                            r.iep_status === 'MISSING'
                              ? 'admin-reports__iep-pill--missing'
                              : r.iep_status === 'INTERNAL_ONLY'
                                ? 'admin-reports__iep-pill--internal'
                                : 'admin-reports__iep-pill--awaiting'
                          }`}
                        >
                          {r.iep_status.replaceAll('_', ' ')}
                        </span>
                      </td>
                      <td>
                        <div className="admin-btn-group">
                          <Link
                            to={`/admin/cases/${r.case_id}?tab=iep`}
                            className="admin-btn admin-btn--primary admin-btn--sm"
                          >
                            Open IEP
                          </Link>
                          <Link to="/admin/iep" className="admin-btn admin-btn--ghost admin-btn--sm">
                            IEP hub
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : tab === 'missing' ? (
        <div style={{ marginBottom: 16 }}>
          <div className="admin-reports__missing-actions admin-desktop-only" style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 12 }}>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 13, fontWeight: 600 }}>Month</span>
              <input
                className="admin-input"
                value={missingMonth}
                onChange={(e) => setMissingMonth(e.target.value)}
                style={{ maxWidth: 200 }}
              />
            </label>
            <button type="button" className="admin-btn admin-btn--sm" onClick={loadMissing}>
              Refresh
            </button>
          </div>
          <div className="admin-reports__missing-actions admin-mobile-only" style={{ marginBottom: 12 }}>
            <button type="button" className="admin-btn admin-btn--sm" onClick={loadMissing}>
              Refresh list
            </button>
          </div>
          {loading ? (
            <p>Loading…</p>
          ) : missingRows.length === 0 ? (
            <p className="admin-muted">All active cases have a client monthly report for this month.</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Child</th>
                  <th>Therapist</th>
                  <th>Module</th>
                </tr>
              </thead>
              <tbody>
                {missingRows.map((r) => (
                  <tr key={r.case_id}>
                    <td>
                      <Link to={`/admin/cases/${r.case_id}?tab=reports`}>{r.case_code}</Link>
                    </td>
                    <td>{r.child_name}</td>
                    <td>{r.therapist_name || '—'}</td>
                    <td>{r.product_module || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <AdminReportsTable
          rows={rows}
          loading={loading}
          selected={selected}
          onToggle={toggleSelect}
          onToggleAll={toggleAll}
          onView={openDrawer}
          onApprove={quickApprove}
          onReject={quickReject}
          canReviewRow={(r) => canReviewReports(r.product_module || 'homecare')}
        />
      )}

      {tab !== 'missing' && tab !== 'iep' ? (
      <div className="admin-reports__pagination">
        <button
          type="button"
          className="admin-btn admin-btn--sm"
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
        >
          Previous
        </button>
        <span>
          Page {page} · {total} total
        </span>
        <button
          type="button"
          className="admin-btn admin-btn--sm"
          disabled={rows.length < pageSize}
          onClick={() => setPage((p) => p + 1)}
        >
          Next
        </button>
      </div>
      ) : null}

      {drawerId ? (
        <AdminReportDetailDrawer
          reportType={effectiveDrawerType}
          reportId={drawerId}
          onClose={closeDrawer}
          onAction={() => {
            loadList()
            loadSummary()
          }}
        />
      ) : null}
    </div>
  )
}
