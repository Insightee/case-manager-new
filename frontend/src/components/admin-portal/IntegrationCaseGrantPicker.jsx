import { useEffect, useMemo, useState } from 'react'
import { formatCaseLabel, formatCaseMeta, loadCasePool } from '../shared/CaseCombobox.jsx'
import {
  CASE_GRANT_SCOPE_FILTERS,
  CASE_GRANT_STATUS_FILTERS,
  caseIdsToText,
  filterGrantCases,
  parseCaseIds,
  toggleGrantedCaseId,
} from '../../lib/integrationDesk.js'

function statusLabel(status) {
  const match = CASE_GRANT_STATUS_FILTERS.find((row) => row.id === status)
  return match?.label || String(status || '').replaceAll('_', ' ')
}

export function IntegrationCaseGrantPicker({ value, onChange, allCases = false, onGrantEvery, onChooseSpecific }) {
  const selectedIds = parseCaseIds(value).ids
  const [scope, setScope] = useState('all')
  const [status, setStatus] = useState('')
  const [query, setQuery] = useState('')
  const [pool, setPool] = useState([])
  const [assignedPool, setAssignedPool] = useState([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError('')
    const assignedOnly = scope === 'assigned'
    loadCasePool(assignedOnly)
      .then((items) => {
        if (cancelled) return
        if (assignedOnly) setAssignedPool(items)
        else setPool(items)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message || 'Could not load cases just now.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [scope])

  const source = scope === 'assigned' ? assignedPool : pool
  const visible = useMemo(
    () => filterGrantCases(source, { query, status }),
    [source, query, status],
  )
  const lookup = useMemo(() => {
    const map = new Map()
    for (const row of [...pool, ...assignedPool]) map.set(Number(row.id), row)
    return map
  }, [pool, assignedPool])

  function setIds(ids) {
    onChange(caseIdsToText(ids))
  }

  function toggle(id) {
    setIds(toggleGrantedCaseId(selectedIds, id))
  }

  function addVisible() {
    const fullList = scope === 'all' && !query.trim() && !status && visible.length === source.length && source.length > 0
    if (fullList && onGrantEvery) {
      onGrantEvery()
      return
    }
    const next = [...selectedIds]
    for (const row of visible) {
      if (!next.includes(row.id)) next.push(row.id)
    }
    setIds(next)
  }

  return (
    <div className="integrations-grant">
      <div className="integrations-chips" role="group" aria-label="Case list">
        {CASE_GRANT_SCOPE_FILTERS.map((option) => (
          <button
            key={option.id}
            type="button"
            className={scope === option.id ? 'is-active' : ''}
            onClick={() => setScope(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <div className="integrations-chips" role="group" aria-label="Case status">
        {CASE_GRANT_STATUS_FILTERS.map((option) => (
          <button
            key={option.id || 'any'}
            type="button"
            className={status === option.id ? 'is-active' : ''}
            onClick={() => setStatus(option.id)}
          >
            {option.label}
          </button>
        ))}
      </div>
      <input
        id="integration-cases-search"
        type="search"
        className="integrations-grant__search"
        placeholder="Search child, therapist, case manager, or case code"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      {selectedIds.length && !allCases ? (
        <ul className="integrations-grant__selected">
          {selectedIds.map((id) => {
            const row = lookup.get(id)
            return (
              <li key={id}>
                <span>{row ? formatCaseLabel(row) : `Case ${id}`}</span>
                <button type="button" onClick={() => toggle(id)}>
                  Remove
                </button>
              </li>
            )
          })}
        </ul>
      ) : allCases ? (
        <p className="integrations-note">Every current and future case is granted. This is not an empty list.</p>
      ) : (
        <p className="integrations-note">No cases granted yet. Pick from the list below, or grant every case.</p>
      )}
      <div className="integrations-grant__toolbar">
        <p className="integrations-note" style={{ margin: 0 }}>
          {allCases
            ? 'Every case'
            : loading
              ? 'Loading cases…'
              : `${visible.length} in this filter · ${selectedIds.length} granted`}
        </p>
        {allCases ? (
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={onChooseSpecific}>
            Choose specific cases
          </button>
        ) : (
          <>
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={onGrantEvery}>
              Grant every case
            </button>
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={addVisible} disabled={!visible.length}>
              Add visible
            </button>
          </>
        )}
      </div>
      {loadError ? <p className="integrations-guidance">{loadError}</p> : null}
      {allCases ? null : (
      <ul className="integrations-grant__list">
        {visible.map((row) => {
          const checked = selectedIds.includes(row.id)
          return (
            <li key={row.id}>
              <button type="button" className={checked ? 'is-on' : ''} onClick={() => toggle(row.id)}>
                <span className="integrations-grant__name">{formatCaseLabel(row)}</span>
                <span className="integrations-grant__meta">
                  {statusLabel(row.status)}
                  {formatCaseMeta(row) ? ` · ${formatCaseMeta(row)}` : ''}
                </span>
              </button>
            </li>
          )
        })}
        {!loading && !visible.length ? (
          <li className="integrations-note">No cases in this filter. Try another status, or grant every case.</li>
        ) : null}
      </ul>
      )}
    </div>
  )
}
