import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { isReportsEngineActive } from '../../lib/reportsRevampFlags.js'
import { apiFetch } from '../../lib/apiClient.js'
import { useTherapistHome, useTherapistReportsPipeline } from '../../hooks/useTherapistHome.js'
import { CreateDraftModal } from './CreateDraftModal.jsx'
import { ReportsSectionHeader } from '../reports-hub/ReportsSectionHeader.jsx'
import { ReportsDashboardSummary } from '../reports-hub/ReportsDashboardSummary.jsx'
import { ReportsDashboardFilters } from '../reports-hub/ReportsDashboardFilters.jsx'
import { ReportsDashboardCard } from '../reports-hub/ReportsDashboardCard.jsx'
import { ReportsDashboardBottomRow } from '../reports-hub/ReportsDashboardBottomRow.jsx'
import '../../styles/reports-dashboard.css'

const DEFAULT_FILTERS = { status: 'all', type: 'all', case: 'all' }

function matchesSearch(item, q, scopedToCase = false) {
  if (!q.trim()) return true
  const s = q.toLowerCase()
  if (scopedToCase) {
    return item.month.toLowerCase().includes(s) || item.caseId.toLowerCase().includes(s)
  }
  return (
    item.caseId.toLowerCase().includes(s) ||
    item.child.toLowerCase().includes(s) ||
    item.month.toLowerCase().includes(s)
  )
}

function matchesCaseFilter(item, caseDbId) {
  if (!caseDbId) return true
  return item.caseDbId === Number(caseDbId)
}

function buildDashboardItems(attention, inProgress, published) {
  const items = []
  for (const r of attention) items.push({ ...r, bucket: 'attention', reportTypeLabel: 'MONTHLY REPORT' })
  for (const r of inProgress) items.push({ ...r, bucket: 'progress', reportTypeLabel: 'MONTHLY REPORT' })
  for (const r of published) items.push({ ...r, bucket: 'published', reportTypeLabel: 'MONTHLY REPORT' })
  return items
}

function bucketPriority(item) {
  if (item.bucket === 'attention') return 0
  if (item.bucket === 'progress') return 1
  return 2
}

function matchesStatusFilter(item, status) {
  if (status === 'all') return true
  if (status === 'attention') return item.bucket === 'attention'
  if (status === 'draft') return item.status === 'draft'
  if (status === 'under_review') return item.status === 'under_review'
  if (status === 'published') return item.bucket === 'published' || item.status === 'published'
  return true
}

function matchesTypeFilter(item, type) {
  if (type === 'all') return true
  if (type === 'monthly') return (item.reportTypeLabel || '').toLowerCase().includes('monthly')
  if (type === 'progress') return (item.reportTypeLabel || '').toLowerCase().includes('progress')
  return true
}

function matchesCaseSelectFilter(item, caseFilter) {
  if (caseFilter === 'all') return true
  return String(item.caseDbId) === String(caseFilter)
}

function Toast({ message, visible, onDismiss }) {
  if (!visible) return null
  return (
    <div className="reports-dashboard-toast" role="status">
      <span className="reports-dashboard-toast__icon" aria-hidden="true">✓</span>
      <div>
        <p className="reports-dashboard-toast__title">Done</p>
        <p className="reports-dashboard-toast__body">{message}</p>
      </div>
      <button type="button" onClick={onDismiss} aria-label="Dismiss" className="reports-dashboard-toast__close">×</button>
    </div>
  )
}

/**
 * Shared therapist reports pipeline UI (caseload or single-case).
 */
export function TherapistReportsHomeView({
  embedded = false,
  fixedCaseId = null,
  caseCode = null,
  childName = null,
  onUpdated,
  onClearCaseFilter,
  openCreateOnMount = false,
  onCreateConsumed,
}) {
  const navigate = useNavigate()
  const [, setSearchParams] = useSearchParams()
  const caseFilterId = fixedCaseId != null ? String(fixedCaseId) : null
  const scopedToCase = Boolean(caseFilterId)

  const [search, setSearch] = useState('')
  const [filterDraft, setFilterDraft] = useState(DEFAULT_FILTERS)
  const [appliedFilters, setAppliedFilters] = useState(DEFAULT_FILTERS)
  const [draftOpen, setDraftOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workbench, setWorkbench] = useState({
    attention: [],
    inProgress: [],
    published: [],
    pipeline: { draft: 0, underReview: 0, published: 0, overdue: 0 },
    monthLabel: '',
  })
  const [toast, setToast] = useState({ visible: false, message: '' })
  const [changeCaseOpen, setChangeCaseOpen] = useState(false)

  const showToast = useCallback((message) => {
    setToast({ visible: true, message })
    window.setTimeout(() => setToast((t) => ({ ...t, visible: false })), 3800)
  }, [])

  const { data: pipelineData, isLoading: pipeLoading, isError, error: fetchError, refetch } =
    useTherapistReportsPipeline()
  const { data: homeData } = useTherapistHome()

  const caseMetaById = useMemo(() => {
    const map = new Map()
    for (const c of homeData?.cases_board?.allCases || []) {
      map.set(c.id, {
        caseManagerName: c.caseManagerName,
        productModule: c.productModule,
        service: c.service,
      })
    }
    return map
  }, [homeData])

  const assignedCases = useMemo(() => homeData?.cases_board?.allCases || [], [homeData])

  const selectedCase = useMemo(() => {
    if (!caseFilterId) return null
    return assignedCases.find((c) => String(c.id) === String(caseFilterId)) || null
  }, [assignedCases, caseFilterId])

  const caseFilterOptions = useMemo(
    () =>
      assignedCases.map((c) => ({
        value: String(c.id),
        label: `${c.child} (${c.caseId})`,
      })),
    [assignedCases],
  )

  useEffect(() => {
    if (pipelineData) {
      setWorkbench({
        attention: pipelineData.attention || [],
        inProgress: pipelineData.in_progress || [],
        published: pipelineData.published || [],
        pipeline: pipelineData.pipeline || { draft: 0, underReview: 0, published: 0, overdue: 0 },
        monthLabel: pipelineData.month_label || '',
      })
    }
    setLoading(pipeLoading)
    if (isError) setError(fetchError?.message || 'Could not load reports')
    else setError('')
  }, [pipelineData, pipeLoading, isError, fetchError])

  const load = useCallback(async () => {
    await refetch()
    onUpdated?.()
  }, [refetch, onUpdated])

  useEffect(() => {
    if (openCreateOnMount && caseFilterId) {
      setDraftOpen(true)
      onCreateConsumed?.()
    }
  }, [openCreateOnMount, caseFilterId, onCreateConsumed])

  const q = search.trim()

  const allItems = useMemo(
    () => buildDashboardItems(workbench.attention, workbench.inProgress, workbench.published),
    [workbench],
  )

  const upcomingReports = useMemo(
    () =>
      allItems
        .filter((item) => item.bucket === 'attention' || item.status === 'draft' || item.status === 'under_review')
        .slice(0, 6)
        .map((item) => ({
          id: item.id,
          child: item.child,
          label: item.reportTypeLabel || 'Monthly Report',
          meta: item.dueInfo || item.lastUpdated || item.month || 'Due soon',
          tone: item.bucket === 'attention' ? 'warn' : 'ok',
        })),
    [allItems],
  )

  const scopedItems = useMemo(
    () => allItems.filter((item) => matchesSearch(item, q, scopedToCase) && matchesCaseFilter(item, caseFilterId)),
    [allItems, q, scopedToCase, caseFilterId],
  )

  const filteredItems = useMemo(() => {
    return scopedItems
      .filter((item) => matchesStatusFilter(item, appliedFilters.status))
      .filter((item) => matchesTypeFilter(item, appliedFilters.type))
      .filter((item) => matchesCaseSelectFilter(item, appliedFilters.case))
      .sort((a, b) => {
        const p = bucketPriority(a) - bucketPriority(b)
        if (p !== 0) return p
        return String(a.child).localeCompare(String(b.child))
      })
  }, [scopedItems, appliedFilters])

  const summaryCounts = useMemo(() => {
    const base = scopedToCase
      ? {
          draft: scopedItems.filter((i) => i.status === 'draft').length,
          underReview: scopedItems.filter((i) => i.status === 'under_review').length,
          published: scopedItems.filter((i) => i.bucket === 'published').length,
          overdue: scopedItems.filter((i) => i.bucket === 'attention').length,
        }
      : {
          draft: workbench.pipeline.draft,
          underReview: workbench.pipeline.underReview,
          published: workbench.pipeline.published,
          total: new Set(allItems.map((i) => i.caseDbId)).size,
        }
    return base
  }, [scopedToCase, scopedItems, workbench.pipeline, allItems])

  const hasActiveFilters =
    appliedFilters.status !== 'all' ||
    appliedFilters.type !== 'all' ||
    appliedFilters.case !== 'all' ||
    Boolean(q)

  function openReportItem(item) {
    const caseDbId = item.caseDbId
    if (!caseDbId) return

    const reportId = item.id
    const hasRealReport =
      reportId &&
      !String(reportId).startsWith('missing-') &&
      !item.isPlaceholder

    if (hasRealReport) {
      navigate(`/therapist/reports/edit/${reportId}`)
      return
    }

    if (item.isPlaceholder || item.attentionType === 'not_started') {
      navigate(`/therapist/reports?case_id=${caseDbId}&create=1`)
      return
    }

    if (embedded && String(caseDbId) === String(caseFilterId)) {
      setSearchParams({ tab: 'reports', section: 'monthly' }, { replace: false })
      return
    }

    navigate(`/therapist/reports?case_id=${caseDbId}`)
  }

  function applySummaryFilter(key) {
    const map = {
      draft: 'draft',
      underReview: 'under_review',
      published: 'published',
      overdue: 'attention',
      total: 'all',
    }
    const status = map[key] || 'all'
    const next = { ...DEFAULT_FILTERS, status }
    setFilterDraft(next)
    setAppliedFilters(next)
  }

  function navigateToCase(caseRow) {
    if (!caseRow?.id) return
    setSearchParams({ case_id: String(caseRow.id) }, { replace: true })
  }

  function handlePickCase(caseRow) {
    navigateToCase(caseRow)
    setChangeCaseOpen(false)
  }

  function handleViewAllClients() {
    onClearCaseFilter?.()
    setChangeCaseOpen(false)
  }

  async function handleDeleteDraft(item) {
    const reportId = item.id
    if (!reportId || String(reportId).startsWith('missing-')) return
    const ok = window.confirm(
      `Remove this draft for ${item.child}${item.month ? ` (${item.month})` : ''}? You can start fresh afterward.`,
    )
    if (!ok) return
    try {
      await apiFetch(`/api/v1/reports/monthly/${reportId}`, { method: 'DELETE' })
      showToast('Draft removed — you can start a new one when ready.')
      await load()
    } catch (err) {
      const msg =
        err.status === 404 || err.status === 405
          ? 'Remove draft is not available on this API yet — deploy the latest backend or use a local server.'
          : err.message || 'Could not remove this draft'
      showToast(msg)
    }
  }

  const displayChild = childName || selectedCase?.child || 'Client'
  const displayCode = caseCode || selectedCase?.caseId || (caseFilterId ? `Case #${caseFilterId}` : '')

  if (loading) {
    return <p className="reports-dashboard-loading">Loading reports…</p>
  }

  const content = (
    <>
      <Toast
        message={toast.message}
        visible={toast.visible}
        onDismiss={() => setToast((t) => ({ ...t, visible: false }))}
      />

      <CreateDraftModal
        open={draftOpen}
        onClose={() => setDraftOpen(false)}
        defaultMonth={workbench.monthLabel}
        defaultCaseId={caseFilterId ? Number(caseFilterId) : null}
        onCreated={() => {
          showToast('Draft saved — continue editing or submit for review.')
          load()
        }}
      />

      <ReportsSectionHeader
        title={scopedToCase ? (embedded ? 'Reports Dashboard' : `Reports · ${displayChild}`) : 'Reports Dashboard'}
        subtitle={
          scopedToCase
            ? `Draft, submit, and track monthly progress for ${displayChild}${displayCode ? ` (${displayCode})` : ''}.`
            : 'Monitor and manage clinical documentation across all active cases.'
        }
        action={(
          <button type="button" className="reports-dashboard-create-btn reports-dashboard-create-btn--header" onClick={() => setDraftOpen(true)}>
            + Create draft
          </button>
        )}
      />

      {!embedded ? (
        <div className="reports-dashboard-case-header">
          <div className="reports-dashboard-case-header__inner">
            <div>
              <p className="reports-dashboard-case-header__label">
                {scopedToCase ? 'Focused client' : 'Caseload'}
              </p>
              <h2 className="reports-dashboard-case-header__title">
                {scopedToCase ? displayChild : 'All clients'}
              </h2>
              {scopedToCase && displayCode ? (
                <p className="reports-dashboard-case-header__meta">{displayCode}</p>
              ) : (
                <p className="reports-dashboard-case-header__meta">
                  Pick a client to focus reports — or browse all cases below.
                </p>
              )}
            </div>
            <div className="reports-dashboard-case-header__actions">
              <button
                type="button"
                className="reports-dashboard-create-btn reports-dashboard-create-btn--ghost"
                onClick={() => setChangeCaseOpen((open) => !open)}
              >
                {scopedToCase ? 'Change case' : 'Pick client'}
              </button>
              {scopedToCase && onClearCaseFilter ? (
                <button
                  type="button"
                  className="reports-dashboard-create-btn reports-dashboard-create-btn--ghost"
                  onClick={handleViewAllClients}
                >
                  View all
                </button>
              ) : null}
            </div>
          </div>
          {changeCaseOpen ? (
            <div className="reports-dashboard-case-picker">
              <label className="reports-dashboard-case-picker__label" htmlFor="reports-case-picker">
                Select client
              </label>
              <select
                id="reports-case-picker"
                className="reports-dashboard-case-picker__select"
                value={caseFilterId || ''}
                onChange={(e) => {
                  const value = e.target.value
                  if (!value) {
                    handleViewAllClients()
                    return
                  }
                  const row = assignedCases.find((c) => String(c.id) === value)
                  if (row) handlePickCase(row)
                }}
              >
                <option value="">All clients</option>
                {assignedCases.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.child} ({c.caseId})
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          {scopedToCase && isReportsEngineActive() ? (
            <div className="reports-dashboard-builder-links">
              <Link
                to={`/therapist/reports/cases/${caseFilterId}/observation`}
                className="reports-dashboard-builder-links__link"
              >
                Observation report
              </Link>
              <Link
                to={`/therapist/reports/cases/${caseFilterId}/iep`}
                className="reports-dashboard-builder-links__link"
              >
                IEP report
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}

      <ReportsDashboardSummary counts={summaryCounts} embedded={scopedToCase} onFilter={applySummaryFilter} />

      <label className="reports-dashboard-search">
        <span className="material-symbols-outlined reports-dashboard-search__icon" aria-hidden="true">search</span>
        <input
          className="reports-dashboard-search__input"
          type="search"
          placeholder={scopedToCase ? 'Search month or case ID…' : 'Search client, case ID, or month…'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search reports"
        />
      </label>

      <ReportsDashboardFilters
        draft={filterDraft}
        onDraftChange={setFilterDraft}
        onApply={() => setAppliedFilters({ ...filterDraft })}
        caseOptions={caseFilterOptions}
      />

      {error ? <p className="reports-dashboard-error" role="alert">{error}</p> : null}

      <section className="reports-dashboard-grid-section" aria-labelledby="reports-dashboard-grid-title">
        <div className="reports-dashboard-grid-section__head">
          <h2 id="reports-dashboard-grid-title" className="reports-dashboard-grid-section__title">
            Active Cases &amp; Reports
          </h2>
          <div className="reports-dashboard-grid-section__views" aria-hidden="true">
            <span className="reports-dashboard-grid-section__view-btn is-active">
              <span className="material-symbols-outlined">grid_view</span>
            </span>
            <span className="reports-dashboard-grid-section__view-btn">
              <span className="material-symbols-outlined">view_list</span>
            </span>
          </div>
        </div>

        {filteredItems.length === 0 ? (
          <div className="reports-dashboard-empty">
            <p className="reports-dashboard-empty__title">
              {hasActiveFilters
                ? 'No reports match your search or filters'
                : scopedToCase
                  ? 'No reports yet for this client'
                  : 'No reports yet'}
            </p>
            <p className="reports-dashboard-empty__body">
              {hasActiveFilters
                ? 'Try clearing filters or widening your search.'
                : scopedToCase
                  ? "Create a draft to start this month's monthly report."
                  : 'Create a draft to start your first monthly report, or open a case from My Cases.'}
            </p>
            {!hasActiveFilters ? (
              <button type="button" className="reports-dashboard-create-btn" onClick={() => setDraftOpen(true)} style={{ marginTop: '0.75rem' }}>
                + Create New Draft
              </button>
            ) : null}
          </div>
        ) : (
          <div className="reports-dashboard-grid">
            {filteredItems.map((item) => (
              <ReportsDashboardCard
                key={item.id}
                item={item}
                caseMeta={caseMetaById.get(item.caseDbId)}
                onViewReports={openReportItem}
                onDeleteDraft={handleDeleteDraft}
              />
            ))}
          </div>
        )}
      </section>

      {!scopedToCase ? <ReportsDashboardBottomRow upcomingReports={upcomingReports} /> : null}

      {!embedded ? (
        <div className="reports-dashboard-mobile-footer">
          <button type="button" className="reports-dashboard-create-btn reports-dashboard-create-btn--block" onClick={() => setDraftOpen(true)}>
            + Create draft
          </button>
        </div>
      ) : null}
    </>
  )

  if (embedded) {
    return <div className="cp-reports-hub forest-light reports-dashboard-page">{content}</div>
  }

  return (
    <div className="reports-home-page forest-light reports-dashboard-page">
      <div className="clinical-reports-home__main">{content}</div>
    </div>
  )
}
