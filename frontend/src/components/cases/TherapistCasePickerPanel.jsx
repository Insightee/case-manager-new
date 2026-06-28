import { useMemo, useState } from 'react'
import { loadRecentCaseIds } from '../../lib/therapistActiveCase.js'

function CasePickRow({ row, onSelect }) {
  const pending = row.critical || (row.needsLogCount ?? 0) > 0
  return (
    <button type="button" className="therapist-case-picker__row" onClick={() => onSelect(row)}>
      <span className="therapist-case-picker__avatar" aria-hidden="true">
        {(row.child || '?').slice(0, 1).toUpperCase()}
      </span>
      <span className="therapist-case-picker__meta">
        <strong>{row.child || 'Client'}</strong>
        <span>{row.caseId || row.case_code}</span>
      </span>
      {pending ? (
        <span className="therapist-case-picker__badge therapist-case-picker__badge--warn">Needs attention</span>
      ) : (
        <span className="therapist-case-picker__badge">{row.stage || row.service || 'Active'}</span>
      )}
    </button>
  )
}

/**
 * Prompt therapist to pick a client before opening a case-scoped sub-tab.
 */
export function TherapistCasePickerPanel({
  title = 'Choose a client first',
  subtitle = 'Pick a case to continue. Pending items are listed at the top.',
  cases = [],
  onSelect,
  onCancel,
}) {
  const [query, setQuery] = useState('')

  const { pending, recent, other } = useMemo(() => {
    const q = query.trim().toLowerCase()
    const filtered = cases.filter((c) => {
      if (!q) return true
      return (
        String(c.child || '').toLowerCase().includes(q) ||
        String(c.caseId || c.case_code || '').toLowerCase().includes(q)
      )
    })
    const pendingRows = filtered.filter((c) => c.critical || (c.needsLogCount ?? 0) > 0)
    const pendingIds = new Set(pendingRows.map((c) => c.id))
    const recentIds = loadRecentCaseIds()
    const recentRows = recentIds
      .map((id) => filtered.find((c) => c.id === id))
      .filter(Boolean)
      .filter((c) => !pendingIds.has(c.id))
    const recentIdSet = new Set(recentRows.map((c) => c.id))
    const rest = filtered.filter((c) => !pendingIds.has(c.id) && !recentIdSet.has(c.id))
    return { pending: pendingRows, recent: recentRows, other: rest }
  }, [cases, query])

  return (
    <section className="therapist-case-picker cp-card" aria-labelledby="therapist-case-picker-title">
      <div className="therapist-case-picker__head">
        <div>
          <h2 id="therapist-case-picker-title" className="therapist-case-picker__title">
            {title}
          </h2>
          {subtitle ? <p className="therapist-case-picker__subtitle">{subtitle}</p> : null}
        </div>
        {onCancel ? (
          <button type="button" className="reports-hub-btn reports-hub-btn--secondary" onClick={onCancel}>
            Cancel
          </button>
        ) : null}
      </div>

      <label className="therapist-case-picker__search">
        <span className="sr-only">Search clients</span>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by child name or case ID…"
        />
      </label>

      {pending.length > 0 ? (
        <div className="therapist-case-picker__section">
          <p className="therapist-case-picker__section-label">Pending attention</p>
          <div className="therapist-case-picker__list">
            {pending.map((row) => (
              <CasePickRow key={row.id} row={row} onSelect={onSelect} />
            ))}
          </div>
        </div>
      ) : null}

      {recent.length > 0 ? (
        <div className="therapist-case-picker__section">
          <p className="therapist-case-picker__section-label">Recent</p>
          <div className="therapist-case-picker__list">
            {recent.map((row) => (
              <CasePickRow key={row.id} row={row} onSelect={onSelect} />
            ))}
          </div>
        </div>
      ) : null}

      <div className="therapist-case-picker__section">
        <p className="therapist-case-picker__section-label">
          {pending.length || recent.length ? 'All clients' : 'Your clients'}
        </p>
        <div className="therapist-case-picker__list">
          {other.length === 0 && pending.length === 0 && recent.length === 0 ? (
            <p className="therapist-case-picker__empty">No assigned cases match your search.</p>
          ) : (
            other.map((row) => <CasePickRow key={row.id} row={row} onSelect={onSelect} />)
          )}
        </div>
      </div>
    </section>
  )
}
