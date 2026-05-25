import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  buildSectionsFromCases,
  buildStatsFromCases,
  filterAndSortCases,
  uniqueServices,
} from '../../lib/caseWorkbench.js'
import { useTherapistHome } from '../../hooks/useTherapistHome.js'
import { QueryState } from '../shared/QueryState.jsx'
import { CasesPageHeader } from './CasesPageHeader.jsx'
import { FilterBar } from './FilterBar.jsx'
import { StatCard } from './StatCard.jsx'
import { TherapistCaseCard } from './TherapistCaseCard.jsx'
import { UpcomingSessionsPanel } from './UpcomingSessionsPanel.jsx'
import './my-cases.css'

function SectionHeader({ title, tone, count }) {
  return (
    <div className="ic-section-head">
      <h2 className="ic-section-head__title">{title}</h2>
      <span className={`ic-section-count ic-section-count--${tone}`}>{count}</span>
    </div>
  )
}

const DEFAULT_FILTERS = {
  stage: 'all',
  service: 'all',
  dueSoon: 'all',
  sort: 'urgency',
}

const VIEW_STORAGE_KEY = 'ic-my-cases-view'

export function MyCasesPage() {
  const [view, setView] = useState(() => {
    try {
      const stored = sessionStorage.getItem(VIEW_STORAGE_KEY)
      return stored === 'table' ? 'table' : 'grid'
    } catch {
      return 'grid'
    }
  })
  const { data: home, isLoading, isError, error, refetch } = useTherapistHome()
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const workbench = useMemo(() => {
    const board = home?.cases_board || {}
    return {
      stats: board.stats || [],
      sections: board.sections || [],
      allCases: board.allCases || [],
    }
  }, [home])

  const scheduleItems = useMemo(() => home?.schedule_preview || [], [home])

  const serviceOptions = useMemo(() => uniqueServices(workbench.allCases), [workbench.allCases])

  const hasActiveFilters = useMemo(
    () =>
      Boolean(search.trim()) ||
      filters.stage !== 'all' ||
      filters.service !== 'all' ||
      filters.dueSoon !== 'all' ||
      filters.sort !== 'urgency',
    [search, filters],
  )

  const displayCases = useMemo(
    () =>
      filterAndSortCases(workbench.allCases, {
        search,
        stage: filters.stage,
        service: filters.service,
        dueSoon: filters.dueSoon,
        sort: filters.sort,
      }),
    [workbench.allCases, search, filters],
  )

  const displaySections = useMemo(() => buildSectionsFromCases(displayCases), [displayCases])

  const displayStats = useMemo(() => {
    const bookingCount = scheduleItems.filter((i) => i.kind === 'booking').length
    return buildStatsFromCases(displayCases, bookingCount)
  }, [displayCases, scheduleItems])

  const resultCount = displayCases.length
  const totalCount = workbench.allCases.length

  function clearFilters() {
    setSearch('')
    setFilters(DEFAULT_FILTERS)
  }

  useEffect(() => {
    try {
      sessionStorage.setItem(VIEW_STORAGE_KEY, view)
    } catch {
      /* ignore */
    }
  }, [view])

  const viewClass = view === 'table' ? 'ic-view-table' : 'ic-view-grid'

  return (
    <div className="ic-my-cases">
      <QueryState
        isLoading={isLoading}
        isError={isError}
        error={error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && totalCount === 0}
        emptyMessage="No assigned cases yet."
      >
      <CasesPageHeader
        search={search}
        onSearchChange={setSearch}
        resultCount={resultCount}
        totalCount={totalCount}
      />

      <UpcomingSessionsPanel items={scheduleItems} loading={isLoading} />

      <section className="ic-stats" aria-label="Case summary">
        {displayStats.map((s) => (
          <StatCard key={s.id} label={s.label} value={s.value} variant={s.variant} />
        ))}
      </section>

      <FilterBar
        view={view}
        onViewChange={setView}
        stage={filters.stage}
        onStageChange={(stage) => setFilters((f) => ({ ...f, stage }))}
        service={filters.service}
        onServiceChange={(service) => setFilters((f) => ({ ...f, service }))}
        serviceOptions={serviceOptions}
        dueSoon={filters.dueSoon}
        onDueSoonChange={(dueSoon) => setFilters((f) => ({ ...f, dueSoon }))}
        sort={filters.sort}
        onSortChange={(sort) => setFilters((f) => ({ ...f, sort }))}
        hasActiveFilters={hasActiveFilters}
        onClearFilters={clearFilters}
      />

      {hasActiveFilters && resultCount < totalCount ? (
        <p className="ic-results-hint" role="status">
          Showing {resultCount} of {totalCount} cases
        </p>
      ) : null}

      <div className={viewClass}>
      {view === 'grid' ? (
        <div className="ic-board">
          {resultCount === 0 ? (
            <p className="ic-empty-hint">No cases match your search or filters.</p>
          ) : (
            displaySections.map(
              (sec) =>
                sec.cases.length > 0 && (
                  <section key={sec.id} className="ic-board__column">
                    <SectionHeader title={sec.title} tone={sec.tone} count={sec.count} />
                    <div className="ic-board__cards">
                      {sec.cases.map((c) => (
                        <TherapistCaseCard key={c.id} data={c} />
                      ))}
                    </div>
                  </section>
                ),
            )
          )}
        </div>
      ) : (
        <div className="ic-table-card">
          <div className="ic-table-head">
            <h3>All cases</h3>
          </div>
          <div className="ic-table-wrap">
            <table className="ic-table">
              <thead>
                <tr>
                  <th>Case ID</th>
                  <th>Child</th>
                  <th>Service</th>
                  <th>Visit address</th>
                  <th>Stage</th>
                  <th>Next due</th>
                </tr>
              </thead>
              <tbody>
                {displayCases.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="ic-table-empty">
                      No cases match your search or filters.
                    </td>
                  </tr>
                ) : (
                  displayCases.map((c) => (
                    <tr key={c.id}>
                      <td>
                        <Link to={`/therapist/cases/${c.id}`}>{c.caseId}</Link>
                      </td>
                      <td>{c.child}</td>
                      <td>{c.service}</td>
                      <td className="ic-table-address">
                        {c.serviceAddress?.formatted ? (
                          <>
                            <span>{c.serviceAddress.formatted}</span>
                            {c.mapsUrl ? (
                              <>
                                {' '}
                                <a href={c.mapsUrl} target="_blank" rel="noopener noreferrer">
                                  Maps
                                </a>
                              </>
                            ) : null}
                          </>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td>{c.stage}</td>
                      <td>{c.nextDue}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      </div>
      </QueryState>
    </div>
  )
}
