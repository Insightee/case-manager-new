import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  PIPELINE_COLUMN_META,
  buildPipelineActions,
  countActivePipelineFilters,
  defaultPipelineFilters,
  derivePipelineFilterOptions,
  filterPipelineRows,
  flattenPipelineBoard,
  pipelineQueueCounts,
  pipelineStatusBadgeVariant,
  sortPipelineRows,
} from '../../lib/adminCasePipeline.js'
import { AdminEmptyState, AdminSearchInput, AdminToolbar } from './ui/index.js'
import { AdminCaseAssignDrawer } from './AdminCaseAssignDrawer.jsx'
import { AdminBulkAssignModal } from './AdminBulkAssignModal.jsx'
import './admin-cases-pipeline.css'

const QUEUE_TABS = [
  { id: 'needs_action', label: 'Needs action' },
  { id: 'allotment', label: 'Allotment' },
  { id: 'assignment', label: 'Assignment' },
  { id: 'review', label: 'Review' },
  { id: 'compliance', label: 'Compliance' },
  { id: 'all', label: 'All cases' },
]

const CASE_STATUSES = [
  { value: 'all', label: 'All case statuses' },
  { value: 'PENDING_ALLOTMENT', label: 'Pending allotment' },
  { value: 'ACTIVE', label: 'Active' },
  { value: 'SUSPENDED', label: 'Suspended' },
  { value: 'CLOSED', label: 'Closed' },
]

const PRODUCT_MODULES = [
  { value: 'all', label: 'All programmes' },
  { value: 'homecare', label: 'Homecare' },
  { value: 'shadow_support', label: 'Shadow support' },
]

export function AdminCasesPipelineTable({ initialFilters = defaultPipelineFilters() }) {
  const { can, canWriteProduct, isViewOnly } = useAuth()
  const navigate = useNavigate()
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(() => defaultPipelineFilters(initialFilters))
  const [filtersOpen, setFiltersOpen] = useState(true)
  const [sort, setSort] = useState('priority')
  const [assignCard, setAssignCard] = useState(null)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [toast, setToast] = useState('')
  const [actingId, setActingId] = useState(null)

  const canAssign = can('case.assign') && !isViewOnly
  const canUpdate = can('case.update') && !isViewOnly

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/v1/admin/cases/pipeline')
      setBoard(data)
    } catch (err) {
      setError(err.message || 'Could not load case queue')
      setBoard(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setFilters((prev) => ({ ...defaultPipelineFilters(initialFilters), search: prev.search }))
  }, [initialFilters])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(''), 4000)
    return () => clearTimeout(t)
  }, [toast])

  const allRows = useMemo(() => flattenPipelineBoard(board), [board])
  const filterOptions = useMemo(() => derivePipelineFilterOptions(allRows), [allRows])
  const counts = useMemo(() => pipelineQueueCounts(allRows), [allRows])
  const activeFilterCount = useMemo(() => countActivePipelineFilters(filters), [filters])

  const rows = useMemo(() => {
    const filtered = filterPipelineRows(allRows, filters)
    return sortPipelineRows(filtered, sort)
  }, [allRows, filters, sort])

  const selectedCards = useMemo(
    () => rows.filter((r) => selectedIds.has(r.id)),
    [rows, selectedIds],
  )

  const bulkEligible = filters.queue === 'assignment' || filters.queue === 'needs_action'

  function patchFilters(patch) {
    setFilters((prev) => ({ ...prev, ...patch }))
    setSelectedIds(new Set())
  }

  function clearExtraFilters() {
    setFilters((prev) =>
      defaultPipelineFilters({
        queue: prev.queue,
        search: prev.search,
      }),
    )
    setSelectedIds(new Set())
  }

  function toggleSelect(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAllVisible() {
    const eligible = rows.filter((r) =>
      ['needs_therapist', 'reassignment'].includes(r.pipeline_column),
    )
    setSelectedIds(new Set(eligible.map((r) => r.id)))
  }

  async function closeCase(card) {
    if (!window.confirm(`Close case ${card.case_code}?`)) return
    setActingId(card.id)
    try {
      await apiFetch(`/api/v1/cases/${card.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'CLOSED' }),
      })
      await load()
      setToast(`Case ${card.case_code} closed.`)
    } catch (err) {
      setToast(err.message || 'Could not close case')
    } finally {
      setActingId(null)
    }
  }

  function runAction(action, row) {
    if (action.id === 'reallot' || action.id === 'allot') {
      if (action.id === 'allot') {
        navigate(`/admin/cases/${row.id}?tab=assignments`)
        return
      }
      setAssignCard(row)
      return
    }
    if (action.id === 'close') {
      closeCase(row)
      return
    }
    if (action.href) {
      navigate(action.href)
    }
  }

  if (loading) {
    return <p className="admin-muted">Loading case board…</p>
  }

  if (error) {
    return (
      <div>
        <p className="admin-alert admin-alert--error">{error}</p>
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={load}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="admin-cases-pipeline">
      <div className="admin-cases-pipeline__tabs" role="tablist" aria-label="Work queues">
        {QUEUE_TABS.map((tab) => {
          const n = tab.id === 'all' ? counts.all : counts[tab.id] ?? 0
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={filters.queue === tab.id}
              className={`admin-cases-pipeline__tab ${filters.queue === tab.id ? 'is-active' : ''}`}
              onClick={() => patchFilters({ queue: tab.id })}
            >
              {tab.label}
              <span className="admin-cases-pipeline__tab-count">{n}</span>
            </button>
          )
        })}
      </div>

      <div className="admin-cases-pipeline__filter-head">
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          aria-expanded={filtersOpen}
          onClick={() => setFiltersOpen((v) => !v)}
        >
          {filtersOpen ? 'Hide filters' : 'Show filters'}
          {activeFilterCount > 0 ? ` (${activeFilterCount})` : ''}
        </button>
        {activeFilterCount > 0 ? (
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={clearExtraFilters}>
            Clear filters
          </button>
        ) : null}
        <span className="admin-cases-pipeline__result-count">
          {rows.length} case{rows.length === 1 ? '' : 's'}
          {board?.total_cases != null ? ` · ${board.total_cases} total` : ''}
        </span>
      </div>

      {filtersOpen ? (
        <div className="admin-cases-pipeline__filters" role="region" aria-label="Case filters">
          <label className="admin-cases-pipeline__filter-field">
            <span>Case status</span>
            <select
              className="admin-input"
              value={filters.caseStatus}
              onChange={(e) => patchFilters({ caseStatus: e.target.value })}
            >
              {CASE_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Pipeline stage</span>
            <select
              className="admin-input"
              value={filters.pipelineStage}
              onChange={(e) => patchFilters({ pipelineStage: e.target.value })}
            >
              <option value="all">All stages</option>
              {Object.entries(PIPELINE_COLUMN_META).map(([id, meta]) => (
                <option key={id} value={id}>
                  {meta.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Programme</span>
            <select
              className="admin-input"
              value={filters.productModule}
              onChange={(e) => patchFilters({ productModule: e.target.value })}
            >
              {PRODUCT_MODULES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Case manager</span>
            <select
              className="admin-input"
              value={filters.caseManagerId}
              onChange={(e) => patchFilters({ caseManagerId: e.target.value })}
            >
              <option value="all">All case managers</option>
              <option value="unassigned">Unassigned CM</option>
              {filterOptions.caseManagers.map((cm) => (
                <option key={cm.id} value={cm.id}>
                  {cm.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Therapist</span>
            <select
              className="admin-input"
              value={filters.therapistId}
              onChange={(e) => patchFilters({ therapistId: e.target.value })}
            >
              <option value="all">All therapists</option>
              <option value="unassigned">Unassigned therapist</option>
              {filterOptions.therapists.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Client</span>
            <select
              className="admin-input"
              value={filters.childId}
              onChange={(e) => patchFilters({ childId: e.target.value })}
            >
              <option value="all">All clients</option>
              {filterOptions.children.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Opened month</span>
            <select
              className="admin-input"
              value={filters.month}
              onChange={(e) => patchFilters({ month: e.target.value })}
            >
              <option value="all">Any month</option>
              {filterOptions.months.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Opened from</span>
            <input
              type="date"
              className="admin-input"
              value={filters.dateFrom}
              onChange={(e) => patchFilters({ dateFrom: e.target.value })}
            />
          </label>
          <label className="admin-cases-pipeline__filter-field">
            <span>Opened to</span>
            <input
              type="date"
              className="admin-input"
              value={filters.dateTo}
              onChange={(e) => patchFilters({ dateTo: e.target.value })}
            />
          </label>
          {filterOptions.stages.length > 0 ? (
            <label className="admin-cases-pipeline__filter-field">
              <span>Operational stage</span>
              <select
                className="admin-input"
                value={filters.operationalStage}
                onChange={(e) => patchFilters({ operationalStage: e.target.value })}
              >
                <option value="all">All stages</option>
                {filterOptions.stages.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      ) : null}

      <AdminToolbar>
        <AdminSearchInput
          value={filters.search}
          onChange={(e) => patchFilters({ search: e.target.value })}
          placeholder="Search case, client, therapist, CM…"
        />
        <select
          className="admin-input"
          style={{ width: 'auto', minWidth: 140 }}
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          aria-label="Sort order"
        >
          <option value="priority">Sort: action priority</option>
          <option value="case">Sort: case code</option>
          <option value="child">Sort: child name</option>
        </select>
        {canAssign && bulkEligible && selectedIds.size > 0 ? (
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setBulkOpen(true)}>
            Bulk assign ({selectedIds.size})
          </button>
        ) : null}
        {canAssign && bulkEligible && rows.some((r) => ['needs_therapist', 'reassignment'].includes(r.pipeline_column)) ? (
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={selectAllVisible}>
            Select assignable
          </button>
        ) : null}
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={load}>
          Refresh
        </button>
      </AdminToolbar>

      {toast ? <p className="admin-alert admin-alert--warning admin-cases-pipeline__toast">{toast}</p> : null}

      <p className="admin-muted admin-cases-pipeline__hint">
        <strong>Needs action</strong> shows cases waiting on allotment, assignment, reviews, IEP, or compliance. Use filters to narrow by case manager, therapist, or client; row actions let you work without opening the full case file first.
      </p>

      {rows.length === 0 ? (
        <AdminEmptyState
          title="No cases match"
          description="Try another queue tab, clear filters, or switch to All cases for active caseload with no pending work."
        />
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table admin-cases-pipeline__table">
            <thead>
              <tr>
                {canAssign && bulkEligible ? <th style={{ width: 36 }} aria-label="Select" /> : null}
                <th>Case</th>
                <th>Client</th>
                <th>Programme</th>
                <th>Case manager</th>
                <th>Stage</th>
                <th>Pending action</th>
                <th>Therapist</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const rowCanWrite = canWriteProduct(row.product_module)
                const actions = buildPipelineActions(row, {
                  canAssign,
                  canUpdate,
                  canWrite: rowCanWrite,
                })
                const selectable =
                  canAssign && rowCanWrite && ['needs_therapist', 'reassignment'].includes(row.pipeline_column)
                return (
                  <tr key={row.id} className="admin-cases-pipeline__row">
                    {canAssign && bulkEligible ? (
                      <td>
                        {selectable ? (
                          <input
                            type="checkbox"
                            checked={selectedIds.has(row.id)}
                            onChange={() => toggleSelect(row.id)}
                            aria-label={`Select ${row.case_code}`}
                          />
                        ) : null}
                      </td>
                    ) : null}
                    <td>
                      <span className="admin-table__primary">{row.case_code}</span>
                      <span className="admin-table__meta">{row.status?.replaceAll('_', ' ')}</span>
                    </td>
                    <td>{row.child_name || '—'}</td>
                    <td>
                      <span className="admin-chip">{row.product_module}</span>
                      <span className="admin-table__meta">{row.service_type}</span>
                    </td>
                    <td>
                      {row.case_manager_name || (
                        <span className="admin-muted">Unassigned</span>
                      )}
                    </td>
                    <td>
                      <span
                        className={`admin-badge admin-badge--${pipelineStatusBadgeVariant(row.pipeline_tone)}`}
                      >
                        {row.pipeline_label}
                      </span>
                    </td>
                    <td className="admin-cases-pipeline__action-cell">
                      {row.next_action ? (
                        <span className="admin-cases-pipeline__next">{row.next_action}</span>
                      ) : (
                        <span className="admin-muted">—</span>
                      )}
                      <PipelineFlags row={row} />
                    </td>
                    <td>
                      {row.therapist_name || '—'}
                      {row.assignment_end_date ? (
                        <span className="admin-table__meta">ends {row.assignment_end_date}</span>
                      ) : null}
                    </td>
                    <td>
                      <div className="admin-btn-group admin-cases-pipeline__actions">
                        {actions.map((action) =>
                          action.href && action.variant !== 'danger' ? (
                            <Link
                              key={action.id}
                              to={action.href}
                              className={`admin-btn admin-btn--sm ${
                                action.variant === 'primary'
                                  ? 'admin-btn--primary'
                                  : action.variant === 'ghost'
                                    ? 'admin-btn--ghost'
                                    : 'admin-btn--secondary'
                              }`}
                            >
                              {action.label}
                            </Link>
                          ) : (
                            <button
                              key={action.id}
                              type="button"
                              className={`admin-btn admin-btn--sm ${
                                action.variant === 'primary'
                                  ? 'admin-btn--primary'
                                  : action.variant === 'danger'
                                    ? 'admin-btn--danger'
                                    : action.variant === 'ghost'
                                      ? 'admin-btn--ghost'
                                      : 'admin-btn--secondary'
                              }`}
                              disabled={actingId === row.id}
                              onClick={() => runAction(action, row)}
                            >
                              {action.label}
                            </button>
                          ),
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <AdminCaseAssignDrawer
        open={!!assignCard}
        caseCard={assignCard}
        onClose={() => setAssignCard(null)}
        onDone={() => {
          setAssignCard(null)
          load()
        }}
      />

      <AdminBulkAssignModal
        open={bulkOpen}
        caseCards={selectedCards}
        onClose={() => setBulkOpen(false)}
        onDone={() => {
          setSelectedIds(new Set())
          setBulkOpen(false)
          load()
        }}
      />
    </div>
  )
}

function PipelineFlags({ row }) {
  const flags = []
  if (row.missing_logs > 0) flags.push(`${row.missing_logs} log`)
  if (row.reports_under_review > 0) flags.push(`${row.reports_under_review} report`)
  if (!row.has_iep) flags.push('no IEP')
  if (row.open_tickets > 0) flags.push(`${row.open_tickets} ticket`)
  if (row.open_incidents > 0) flags.push(`${row.open_incidents} incident`)
  if (!flags.length) return null
  return (
    <div className="admin-cases-pipeline__flags">
      {flags.map((f) => (
        <span key={f} className="admin-case-card__flag admin-case-card__flag--warn">
          {f}
        </span>
      ))}
    </div>
  )
}
