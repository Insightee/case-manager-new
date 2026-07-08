import { useMemo, useState } from 'react'
import {
  collectBoardCases,
  filterAndSortCases,
  uniqueServices,
} from '../../lib/caseWorkbench.js'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import { TherapistCaseCard } from './TherapistCaseCard.jsx'
import '../../styles/my-cases-modern.css'

const DEFAULT_FILTERS = {
  stage: 'all',
  service: 'all',
}

const STAGE_PILLS = [
  { value: 'all', label: 'All' },
  { value: 'attention', label: 'Attention' },
  { value: 'log_due', label: 'Log due' },
  { value: 'in_progress', label: 'Active' },
  { value: 'closed', label: 'Closed' },
]

export function MyCasesPage() {
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const allCases = useMemo(() => collectBoardCases(home?.cases_board || {}), [home])
  const serviceOptions = useMemo(() => uniqueServices(allCases), [allCases])

  const hasActiveFilters = useMemo(
    () =>
      Boolean(search.trim()) ||
      filters.stage !== 'all' ||
      filters.service !== 'all',
    [search, filters],
  )

  const displayCases = useMemo(
    () =>
      filterAndSortCases(allCases, {
        search,
        stage: filters.stage,
        service: filters.service,
        sort: 'urgency',
      }),
    [allCases, search, filters],
  )

  const resultCount = displayCases.length
  const totalCount = allCases.length

  const pendingSummary = useMemo(() => {
    const logsDue = allCases.reduce((n, c) => n + (c.needsLogCount || 0), 0)
    const reportsDue = allCases.filter((c) => {
      const due = String(c.nextDue || '').toLowerCase()
      const stage = String(c.stage || '').toLowerCase()
      return due.includes('report') || stage.includes('report')
    }).length
    return { logsDue, reportsDue }
  }, [allCases])

  function clearFilters() {
    setSearch('')
    setFilters(DEFAULT_FILTERS)
  }

  return (
    <div className="mc-page forest-light">
      <header className="mc-header">
        <div className="mc-header__intro">
          <h1 className="mc-header__title">My Cases</h1>
          <p className="mc-header__sub">
            {totalCount} client{totalCount === 1 ? '' : 's'}
            {pendingSummary.logsDue || pendingSummary.reportsDue
              ? ` · ${pendingSummary.logsDue} log${pendingSummary.logsDue === 1 ? '' : 's'} · ${pendingSummary.reportsDue} report${pendingSummary.reportsDue === 1 ? '' : 's'}`
              : ''}
          </p>
        </div>
        <label className="mc-search">
          <span className="material-symbols-outlined mc-search__icon" aria-hidden="true">search</span>
          <input
            type="search"
            placeholder="Search child, case ID, service…"
            aria-label="Search cases"
            autoComplete="off"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </header>

      <div className="mc-toolbar">
        <div className="mc-pills" role="tablist" aria-label="Filter by status">
          {STAGE_PILLS.map((pill) => (
            <button
              key={pill.value}
              type="button"
              role="tab"
              aria-selected={filters.stage === pill.value}
              className={`mc-pill${filters.stage === pill.value ? ' is-active' : ''}`}
              onClick={() => setFilters((f) => ({ ...f, stage: pill.value }))}
            >
              {pill.label}
            </button>
          ))}
        </div>

        {serviceOptions.length > 1 ? (
          <label className="mc-service-filter">
            <span className="sr-only">Service</span>
            <select
              value={filters.service}
              onChange={(e) => setFilters((f) => ({ ...f, service: e.target.value }))}
              aria-label="Filter by service"
            >
              <option value="all">All services</option>
              {serviceOptions.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        ) : null}

        {hasActiveFilters ? (
          <button type="button" className="mc-clear" onClick={clearFilters}>
            Clear
          </button>
        ) : null}
      </div>

      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && totalCount === 0}
        emptyMessage="No assigned cases yet."
      >
        {resultCount === 0 ? (
          <div className="mc-empty">
            <p className="mc-empty__title">No cases match your search or filters</p>
            <p className="mc-empty__body">Try clearing filters or widening your search.</p>
            {hasActiveFilters ? (
              <button type="button" className="mc-clear mc-clear--button" onClick={clearFilters}>
                Clear filters
              </button>
            ) : null}
          </div>
        ) : (
          <section className="mc-rail-section" aria-label="Your case cards">
            <div className="mc-rail-section__head">
              <h2 className="mc-rail-section__title">Your clients</h2>
              {hasActiveFilters && resultCount < totalCount ? (
                <p className="mc-rail-section__hint">Showing {resultCount} of {totalCount}</p>
              ) : null}
            </div>
            <div className="mc-rail">
              {displayCases.map((c) => (
                <TherapistCaseCard key={c.id} data={c} />
              ))}
            </div>
          </section>
        )}
      </QueryState>
    </div>
  )
}
