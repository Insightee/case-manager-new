import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { buildCaseWorkbench } from '../../lib/caseWorkbench.js'
import { CasesPageHeader } from './CasesPageHeader.jsx'
import { FilterBar } from './FilterBar.jsx'
import { StatCard } from './StatCard.jsx'
import { TherapistCaseCard } from './TherapistCaseCard.jsx'
import './my-cases.css'

function SectionHeader({ title, tone, count }) {
  return (
    <div className="ic-section-head">
      <h2 className="ic-section-head__title">{title}</h2>
      <span className={`ic-section-count ic-section-count--${tone}`}>{count}</span>
    </div>
  )
}

export function MyCasesPage() {
  const [view, setView] = useState('grid')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workbench, setWorkbench] = useState({ stats: [], sections: [], allCases: [] })
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 90)
      const to = toDate.toISOString().slice(0, 10)
      const [cases, sessions, logs, reports, slots] = await Promise.all([
        apiFetch('/api/v1/cases?assigned=true'),
        apiFetch('/api/v1/sessions'),
        apiFetch('/api/v1/daily-logs'),
        apiFetch('/api/v1/reports/monthly'),
        apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`),
      ])
      setWorkbench(buildCaseWorkbench({ cases, sessions, logs, reports, slots }))
    } catch (err) {
      setError(err.message || 'Could not load cases')
      setWorkbench({ stats: [], sections: [], allCases: [] })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filteredSections = useMemo(() => {
    const q = search.trim().toLowerCase()
    const match = (c) =>
      !q ||
      c.caseId.toLowerCase().includes(q) ||
      c.child.toLowerCase().includes(q) ||
      c.service.toLowerCase().includes(q)
    return workbench.sections.map((sec) => {
      const cases = sec.cases.filter(match)
      return { ...sec, cases, count: cases.length }
    })
  }, [workbench.sections, search])

  const tableRows = useMemo(() => {
    const q = search.trim().toLowerCase()
    return workbench.allCases
      .filter(
        (c) =>
          !q ||
          c.caseId.toLowerCase().includes(q) ||
          c.child.toLowerCase().includes(q) ||
          c.service.toLowerCase().includes(q),
      )
      .map((c) => ({
        id: c.id,
        caseId: c.caseId,
        child: c.child,
        service: c.service,
        stage: c.stage,
        next: c.nextDue,
      }))
  }, [workbench.allCases, search])

  if (loading) {
    return (
      <div className="ic-my-cases" style={{ padding: 24 }}>
        <p style={{ color: '#6b7280' }}>Loading your cases…</p>
      </div>
    )
  }

  return (
    <div className="ic-my-cases">
      <CasesPageHeader search={search} onSearchChange={setSearch} />
      <FilterBar view={view} onViewChange={setView} />

      {error ? (
        <p style={{ color: '#b91c1c', fontSize: '0.875rem', marginBottom: 16 }}>{error}</p>
      ) : null}

      <section className="ic-stats" aria-label="Case summary">
        {workbench.stats.map((s) => (
          <StatCard key={s.id} label={s.label} value={s.value} variant={s.variant} />
        ))}
      </section>

      {view === 'grid' ? (
        <div className="ic-board">
          {filteredSections.every((s) => s.cases.length === 0) ? (
            <p style={{ color: '#9ca3af' }}>No assigned cases match your search.</p>
          ) : (
            filteredSections.map(
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
                {tableRows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link to={`/therapist/cases/${r.id}`}>{r.caseId}</Link>
                    </td>
                    <td>{r.child}</td>
                    <td>{r.service}</td>
                    <td>{r.stage}</td>
                    <td>{r.next}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
