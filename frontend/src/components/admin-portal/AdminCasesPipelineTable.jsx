import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import {
  CASE_STATE_OPTIONS,
  OPENED_DATE_PRESETS,
  buildPipelineActions,
  countActivePipelineFilters,
  defaultCaseManagerFilterId,
  defaultPipelineFilters,
  derivePipelineFilterOptions,
  filterPipelineRows,
  flattenPipelineBoard,
  pipelineQueueCounts,
  pipelineStatusBadgeVariant,
  sortPipelineRows,
} from '../../lib/adminCasePipeline.js'
import { useClinicalProductModules } from '../../hooks/useClinicalProductModules.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  FilterDateRange,
  FilterSelect,
} from './ui/index.js'

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

const SORT_OPTIONS = [
  { value: 'priority', label: 'Priority' },
  { value: 'case', label: 'Case code' },
  { value: 'child', label: 'Child name' },
]

export function AdminCasesPipelineTable({ initialFilters = defaultPipelineFilters() }) {
  const { can, canWriteProduct, isViewOnly, user } = useAuth()
  const { options: programmeOptions } = useClinicalProductModules()
  const navigate = useNavigate()
  const [board, setBoard] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState(() => defaultPipelineFilters(initialFilters))
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [sort, setSort] = useState('priority')
  const [sortMenuOpen, setSortMenuOpen] = useState(false)
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
    if (!user?.roles?.length) return
    const cmId = defaultCaseManagerFilterId(user)
    setFilters((prev) => {
      const next = defaultPipelineFilters(initialFilters)
      if (prev.search) next.search = prev.search
      if (cmId && next.caseManagerId === 'all') next.caseManagerId = cmId
      return next
    })
  }, [initialFilters, user?.id, user?.roles])

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

  const programmeFilterOptions = useMemo(
    () => [
      { value: 'all', label: 'All programmes' },
      ...programmeOptions.filter((o) => o.value).map((o) => ({ value: o.value, label: o.label })),
    ],
    [programmeOptions],
  )

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
        <div className="admin-cases-pipeline__filter-head-main">
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
        </div>
        <FilterSelect
          id="case-pipeline-sort-desktop"
          ariaLabel="Sort cases"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          options={SORT_OPTIONS}
          className="admin-cases-pipeline__sort admin-cases-pipeline__sort--inline admin-desktop-only"
        />
        <span className="admin-cases-pipeline__result-count">
          {rows.length} case{rows.length === 1 ? '' : 's'}
          {board?.total_cases != null ? ` · ${board.total_cases} total` : ''}
        </span>
      </div>

      <AdminCollapsibleFilters
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        mobileActions={
          <div className="admin-cases-pipeline__mobile-controls">
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              aria-expanded={sortMenuOpen}
              onClick={() => setSortMenuOpen((v) => !v)}
            >
              Sort: {SORT_OPTIONS.find((o) => o.value === sort)?.label || 'Priority'}
            </button>
          </div>
        }
        quickSearch={
          <AdminSearchInput
            value={filters.search}
            onChange={(value) => patchFilters({ search: value })}
            placeholder="Search case, client, therapist…"
          />
        }
        activeCount={activeFilterCount}
        activeChips={
          activeFilterCount > 0 ? [`${activeFilterCount} filter${activeFilterCount === 1 ? '' : 's'} active`] : []
        }
      >
      <div
        className={`admin-cases-pipeline__filters${!filtersOpen ? ' admin-cases-pipeline__filters--collapsed' : ''}`}
        role="region"
        aria-label="Case filters"
      >
          <FilterSelect
            label="Queue"
            value={filters.queue}
            onChange={(e) => patchFilters({ queue: e.target.value })}
            options={QUEUE_TABS.map((tab) => ({ value: tab.id, label: tab.label }))}
          />
          <FilterSelect
            label="Case state"
            value={filters.caseState}
            onChange={(e) => patchFilters({ caseState: e.target.value })}
            options={CASE_STATE_OPTIONS}
          />
          <FilterSelect
            label="Opened"
            value={filters.openedPreset}
            onChange={(e) => patchFilters({ openedPreset: e.target.value })}
            options={OPENED_DATE_PRESETS}
          />
          {filters.openedPreset === 'custom' ? (
            <FilterDateRange
              label="Date range"
              from={filters.dateFrom}
              to={filters.dateTo}
              onFromChange={(e) => patchFilters({ dateFrom: e.target.value })}
              onToChange={(e) => patchFilters({ dateTo: e.target.value })}
              className="admin-cases-pipeline__filter-span-2"
            />
          ) : null}
          <FilterSelect
            label="Programme"
            value={filters.productModule}
            onChange={(e) => patchFilters({ productModule: e.target.value })}
            options={programmeFilterOptions}
          />
          <FilterSelect
            label="Case manager"
            value={filters.caseManagerId}
            onChange={(e) => patchFilters({ caseManagerId: e.target.value })}
            options={[
              { value: 'all', label: 'All case managers' },
              { value: 'unassigned', label: 'Unassigned CM' },
              ...filterOptions.caseManagers.map((cm) => ({ value: cm.id, label: cm.label })),
            ]}
          />
          <FilterSelect
            label="Therapist"
            value={filters.therapistId}
            onChange={(e) => patchFilters({ therapistId: e.target.value })}
            options={[
              { value: 'all', label: 'All therapists' },
              { value: 'unassigned', label: 'Unassigned therapist' },
              ...filterOptions.therapists.map((t) => ({ value: t.id, label: t.label })),
            ]}
          />
          <FilterSelect
            label="Client"
            value={filters.childId}
            onChange={(e) => patchFilters({ childId: e.target.value })}
            options={[
              { value: 'all', label: 'All clients' },
              ...filterOptions.children.map((c) => ({ value: c.id, label: c.label })),
            ]}
          />
          {filterOptions.stages.length > 0 ? (
            <FilterSelect
              label="Operational stage"
              value={filters.operationalStage}
              onChange={(e) => patchFilters({ operationalStage: e.target.value })}
              options={[
                { value: 'all', label: 'All stages' },
                ...filterOptions.stages.map((s) => ({ value: s, label: s })),
              ]}
            />
          ) : null}
      </div>
      </AdminCollapsibleFilters>

      <div className="admin-cases-pipeline__toolbar">
        <AdminToolbar className="admin-cases-pipeline__toolbar-inner admin-desktop-only">
          <AdminSearchInput
            value={filters.search}
            onChange={(value) => patchFilters({ search: value })}
            placeholder="Search case, client, therapist, CM…"
          />
          <div className="admin-cases-pipeline__toolbar-actions">
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
          </div>
        </AdminToolbar>
        <div className="admin-cases-pipeline__toolbar-mobile admin-mobile-only">
          {sortMenuOpen ? (
            <div className="admin-cases-pipeline__sort-menu" role="menu" aria-label="Sort cases">
              {SORT_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="menuitemradio"
                  aria-checked={sort === option.value}
                  className={`admin-cases-pipeline__sort-option${sort === option.value ? ' is-active' : ''}`}
                  onClick={() => {
                    setSort(option.value)
                    setSortMenuOpen(false)
                  }}
                >
                  {option.label}
                </button>
              ))}
            </div>
          ) : null}
          <div className="admin-cases-pipeline__toolbar-mobile-actions">
            {canAssign && bulkEligible && selectedIds.size > 0 ? (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setBulkOpen(true)}>
                Bulk ({selectedIds.size})
              </button>
            ) : null}
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={load}>
              Refresh
            </button>
          </div>
        </div>
      </div>

      {toast ? <p className="admin-alert admin-alert--warning admin-cases-pipeline__toast">{toast}</p> : null}

      <p className="admin-muted admin-cases-pipeline__hint admin-portal-lead">
        <strong>Needs action</strong> shows cases waiting on allotment, assignment, reviews, IEP, or compliance. Use filters to narrow by case manager, therapist, or client; row actions let you work without opening the full case file first.
      </p>

      {rows.length === 0 ? (
        <AdminEmptyState
          title="No cases match"
          description="Try another queue tab, clear filters, or switch to All cases for active caseload with no pending work."
        />
      ) : (
        <AdminDataList
          desktop={
        <div className="admin-table-wrap admin-cases-pipeline__table-wrap">
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
          }
          mobile={rows.map((row) => {
                const rowCanWrite = canWriteProduct(row.product_module)
                const actions = buildPipelineActions(row, {
                  canAssign,
                  canUpdate,
                  canWrite: rowCanWrite,
                })
                const primary = actions[0]
                return (
                  <li key={row.id}>
                    <AdminTaskCard
                      title={row.case_code}
                      meta={`${row.child_name || '—'} · ${row.next_action || row.pipeline_label}`}
                      badges={
                        <span className={`admin-badge admin-badge--${pipelineStatusBadgeVariant(row.pipeline_tone)}`}>
                          {row.pipeline_label}
                        </span>
                      }
                      actions={
                        <div className="admin-btn-group admin-cases-pipeline__actions">
                          {actions.slice(0, 3).map((action) =>
                            action.href && action.variant !== 'danger' ? (
                              <Link
                                key={action.id}
                                to={action.href}
                                className={`admin-btn admin-btn--sm ${
                                  action.variant === 'primary' ? 'admin-btn--primary' : 'admin-btn--ghost'
                                }`}
                              >
                                {action.label}
                              </Link>
                            ) : (
                              <button
                                key={action.id}
                                type="button"
                                className={`admin-btn admin-btn--sm ${
                                  action.variant === 'primary' ? 'admin-btn--primary' : 'admin-btn--ghost'
                                }`}
                                disabled={actingId === row.id}
                                onClick={() => runAction(action, row)}
                              >
                                {action.label}
                              </button>
                            ),
                          )}
                        </div>
                      }
                    >
                      <PipelineFlags row={row} />
                      {!primary ? null : (
                        <p className="admin-muted" style={{ margin: '8px 0 0', fontSize: '0.75rem' }}>
                          {row.product_module} · {row.therapist_name || 'No therapist'}
                        </p>
                      )}
                    </AdminTaskCard>
                  </li>
                )
              })}
        />
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
