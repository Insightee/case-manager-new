import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch, getTokens } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminSearchInput } from './ui/index.js'
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
  if (filters.parentReview) p.set('parent_review_status', filters.parentReview)
  if (filters.caseId) p.set('case_id', filters.caseId)
  return `?${p.toString()}`
}

export function AdminReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = searchParams.get('tab') || 'queue'
  const typeFilter = searchParams.get('type') || 'all'
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

  const filters = useMemo(
    () => ({ search, status, module, month, parentReview: '', caseId: searchParams.get('case_id') || '' }),
    [search, status, module, month, searchParams],
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

  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    setPage(1)
  }, [tab, typeFilter, search, status, module, month])

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

  function setTypeFilter(t) {
    const next = new URLSearchParams(searchParams)
    if (t === 'all') next.delete('type')
    else next.set('type', t)
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

  async function bulkApprove() {
    const { monthly, observation } = selectedByType()
    setActing(true)
    setMessage('')
    try {
      if (monthly.length) {
        await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'monthly',
            ids: monthly,
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
      }
      if (observation.length) {
        await apiFetch('/api/v1/admin/reports/bulk/approve', {
          method: 'POST',
          body: JSON.stringify({
            report_type: 'observation',
            ids: observation,
            visibility_status: 'APPROVED_FOR_PARENT',
          }),
        })
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
    try {
      await apiFetch('/api/v1/admin/reports/bulk/approve', {
        method: 'POST',
        body: JSON.stringify({
          report_type: row.report_type,
          ids: [row.id],
          visibility_status: 'APPROVED_FOR_PARENT',
        }),
      })
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
        subtitle="Review monthly and observation reports, approve for parents, and export filtered lists."
      />

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
        </div>
      ) : null}

      <div className="admin-reports__tabs">
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${tab === 'queue' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('queue')}
        >
          Review queue
        </button>
        <button
          type="button"
          className={`admin-btn admin-btn--sm ${tab === 'all' ? 'admin-btn--primary' : ''}`}
          onClick={() => setTab('all')}
        >
          All reports
        </button>
        <span style={{ marginLeft: 8 }} />
        {['all', 'monthly', 'observation'].map((t) => (
          <button
            key={t}
            type="button"
            className={`admin-btn admin-btn--sm ${typeFilter === t ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => setTypeFilter(t)}
          >
            {t === 'all' ? 'All types' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      <div className="admin-reports__toolbar">
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Child, case, month, therapist…" />
        {tab === 'all' ? (
          <select className="admin-select" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="UNDER_REVIEW">Under review</option>
            <option value="PUBLISHED">Published</option>
            <option value="REJECTED">Rejected</option>
          </select>
        ) : null}
        <select className="admin-select" value={module} onChange={(e) => setModule(e.target.value)}>
          <option value="">All modules</option>
          <option value="homecare">Homecare</option>
          <option value="shadow_support">Shadow support</option>
        </select>
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

      {message ? <p className="admin-alert" style={{ marginBottom: 12 }}>{message}</p> : null}

      {selected.size > 0 ? (
        <div className="admin-reports__bulk-bar">
          <span>{selected.size} selected</span>
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={bulkApprove}>
            Approve for parents
          </button>
          <button type="button" className="admin-btn admin-btn--sm" disabled={acting} onClick={() => setBulkRejectOpen(true)}>
            Reject…
          </button>
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

      <AdminReportsTable
        rows={rows}
        loading={loading}
        selected={selected}
        onToggle={toggleSelect}
        onToggleAll={toggleAll}
        onView={openDrawer}
        onApprove={quickApprove}
        onReject={quickReject}
      />

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
