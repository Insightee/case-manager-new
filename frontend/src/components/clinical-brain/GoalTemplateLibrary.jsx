import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AI_ENABLED } from '../../lib/reportsRevampFlags.js'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { enrichGoalTemplatesFromApi } from '../../lib/clinicalBrainMockData.js'
import { applyClinicalFilters, EMPTY_FILTERS } from '../../lib/clinicalBrainFilters.js'
import { ClinicalBrainFilterOverlay } from './ClinicalBrainFilterOverlay.jsx'

export function GoalTemplateLibrary({
  caseId,
  onUseTemplate,
  onPreview,
  onSelectForCustom,
}) {
  const [query, setQuery] = useState('')
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [filterOpen, setFilterOpen] = useState(false)
  const [templates, setTemplates] = useState([])
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!caseId) return
    setLoading(true)
    try {
      const params = new URLSearchParams({ kind: 'goals' })
      if (query.trim()) params.set('q', query.trim())
      if (filters.domain) params.set('domain', filters.domain)
      const data = await apiFetch(`/api/v1/cases/${caseId}/clinical/repository-search?${params}`)
      setTemplates(enrichGoalTemplatesFromApi(data.items || []))
    } catch {
      setTemplates(enrichGoalTemplatesFromApi([]))
    } finally {
      setLoading(false)
    }
  }, [caseId, query, filters.domain])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(
    () => applyClinicalFilters(templates, { ...filters, query }),
    [templates, filters, query],
  )

  const activeFilterCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="cb-template-library">
      <div className="sg-search-row">
        <input
          type="search"
          className="sg-search-input"
          placeholder="Search goal templates…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button type="button" className="cb-btn" onClick={() => setFilterOpen(true)}>
          Filters{activeFilterCount ? ` (${activeFilterCount})` : ''}
        </button>
      </div>

      {loading ? <p className="sg-hint">Searching templates…</p> : null}

      <ul className="sg-template-list">
        {filtered.map((item) => (
          <li key={item.id} className="cb-template-card">
            <div className="cb-card__head">
              <p className="cb-card__title">{item.label}</p>
              {!AI_ENABLED && item.source === 'repository' ? (
                <span className="cb-pill cb-pill--muted">Suggested from Goal Bank</span>
              ) : null}
            </div>
            <div className="cb-card__meta">
              <span className="cb-pill cb-pill--active">
                {coreDomainLabel(item.domain_key, { short: true }) || item.domain_key}
              </span>
              {item.support_need ? <span>{item.support_need.replace(/_/g, ' ')}</span> : null}
              {item.related_strategies_count ? (
                <span>{item.related_strategies_count} related strategies</span>
              ) : null}
            </div>
            {item.parent_meaning ? <p className="gs-muted">{item.parent_meaning}</p> : null}
            <p className="gs-muted" style={{ fontSize: '0.8125rem' }}>
              {item.goal_statement || item.desired_state || '—'}
            </p>
            <div className="cb-card__actions">
              <button type="button" className="cb-btn cb-btn--primary" onClick={() => onUseTemplate?.(item)}>
                Use template
              </button>
              <button type="button" className="cb-btn" onClick={() => onPreview?.(item)}>
                Preview
              </button>
              <button type="button" className="cb-btn" onClick={() => onSelectForCustom?.(item)}>
                Select
              </button>
            </div>
          </li>
        ))}
      </ul>

      {!loading && !filtered.length ? (
        <p className="sg-hint">No templates match — try another domain or search term.</p>
      ) : null}

      <ClinicalBrainFilterOverlay
        open={filterOpen}
        onClose={() => setFilterOpen(false)}
        filters={filters}
        onChange={setFilters}
        onApply={setFilters}
      />
    </div>
  )
}
