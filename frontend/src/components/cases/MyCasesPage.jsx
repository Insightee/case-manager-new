import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import {
  buildCaseWorkbench,
  buildSectionsFromCases,
  buildStatsFromCases,
  filterAndSortCases,
  uniqueServices,
} from '../../lib/caseWorkbench.js'
import { CasesPageHeader } from './CasesPageHeader.jsx'
import { FilterBar } from './FilterBar.jsx'
import { StatCard } from './StatCard.jsx'
import { TherapistCaseCard } from './TherapistCaseCard.jsx'
import { UpcomingSessionsPanel } from './UpcomingSessionsPanel.jsx'
import { mergeUpcomingSchedule } from '../../lib/therapistSchedule.js'
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

export function MyCasesPage() {
  const [view, setView] = useState('grid')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workbench, setWorkbench] = useState({
    stats: [],
    sections: [],
    allCases: [],
    upcomingBooked: [],
    upcomingSessions: [],
  })
  const [scheduleItems, setScheduleItems] = useState([])
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState(DEFAULT_FILTERS)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)
      const [cases, sessions, logs, reports, slots, upcoming] = await Promise.all([
        apiFetch('/api/v1/cases?assigned=true&page_size=100'),
        apiFetch('/api/v1/sessions?page_size=100'),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/reports/monthly?page_size=100'),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`),
        apiFetch('/api/v1/sessions/upcoming?days=90').catch(() => []),
      ])
      const sessionList = unwrapList(sessions)
      const slotList = unwrapList(slots)
      const upcomingList = Array.isArray(upcoming) ? upcoming : unwrapList(upcoming)
      setWorkbench(
        buildCaseWorkbench({
          cases: unwrapList(cases),
          sessions: sessionList,
          logs: unwrapList(logs),
          reports: unwrapList(reports),
          slots: slotList,
        }),
      )
      setScheduleItems(mergeUpcomingSchedule({ sessions: upcomingList, slots: slotList }))
    } catch (err) {
      setError(err.message || 'Could not load cases')
      setWorkbench({ stats: [], sections: [], allCases: [], upcomingBooked: [], upcomingSessions: [] })
      setScheduleItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

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
    const ids = new Set(displayCases.map((c) => c.id))
    const bookingCount = (workbench.upcomingBooked || []).filter((sl) => ids.has(sl.case_id)).length
    return buildStatsFromCases(displayCases, bookingCount)
  }, [displayCases, workbench.upcomingBooked])

  const resultCount = displayCases.length
  const totalCount = workbench.allCases.length

  function clearFilters() {
    setSearch('')
    setFilters(DEFAULT_FILTERS)
  }

  if (loading) {
    return (
      <div className="ic-my-cases" style={{ padding: 24 }}>
        <p style={{ color: '#6b7280' }}>Loading your cases…</p>
      </div>
    )
  }

  return (
    <div className="ic-my-cases">
      <CasesPageHeader
        search={search}
        onSearchChange={setSearch}
        resultCount={resultCount}
        totalCount={totalCount}
      />
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

      {error ? (
        <p style={{ color: '#b91c1c', fontSize: '0.875rem', marginBottom: 16 }}>{error}</p>
      ) : null}

      <UpcomingSessionsPanel items={scheduleItems} loading={loading} />

      <section className="ic-stats" aria-label="Case summary">
        {displayStats.map((s) => (
          <StatCard key={s.id} label={s.label} value={s.value} variant={s.variant} />
        ))}
      </section>

      {hasActiveFilters && resultCount < totalCount ? (
        <p className="ic-results-hint" role="status">
          Showing {resultCount} of {totalCount} cases
        </p>
      ) : null}

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
                  <th>Stage</th>
                  <th>Next due</th>
                </tr>
              </thead>
              <tbody>
                {displayCases.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="ic-table-empty">
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
  )
}
