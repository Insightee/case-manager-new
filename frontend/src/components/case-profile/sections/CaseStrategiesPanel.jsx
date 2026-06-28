import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { GOAL_REPOSITORY_ENABLED } from '../../../lib/reportsRevampFlags.js'
import { ClinicalMetricCard } from '../../clinical-ui/ClinicalMetricCard.jsx'
import { ClinicalStrategyCard } from '../../clinical-ui/ClinicalStrategyCard.jsx'
import { ClinicalEmptyState } from '../../clinical-ui/ClinicalEmptyState.jsx'
import { ClinicalCard } from '../../clinical-ui/ClinicalCard.jsx'

const FILTER_CHIPS = [
  { id: 'all',             label: 'All' },
  { id: 'from_iep',        label: 'From IEP' },
  { id: 'custom',          label: 'Custom' },
  { id: 'pending_review',  label: 'Pending Review' },
  { id: 'helpful',         label: 'Helpful' },
  { id: 'needs_adaptation', label: 'Needs Adaptation' },
]

export function CaseStrategiesPanel({ caseId, variant = 'therapist' }) {
  const [strategies, setStrategies] = useState([])
  const [iepStrategies, setIepStrategies] = useState([])
  const [evidenceStrategies, setEvidenceStrategies] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [newItem, setNewItem] = useState({ label: '', when_to_use: '', how_to_use: '', avoid: '' })
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const tasks = [
        apiFetch(`/api/v1/cases/${caseId}/iep-plan`).catch(() => null),
        apiFetch(`/api/v1/cases/${caseId}/strategies/evidence-summary`).catch(() => ({ strategies: [] })),
      ]
      if (GOAL_REPOSITORY_ENABLED) {
        tasks.push(apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`).catch(() => ({ items: [] })))
      }
      const results = await Promise.all(tasks)
      const iep      = results[0]
      const evidence = results[1]
      const repo     = results[2]
      const sections = iep?.sections || {}
      const fromIep  = []
      if (sections.talent_development?.strategies) {
        fromIep.push({ id: 'iep-1', source: 'IEP', label: sections.talent_development.strategies, category: 'IEP' })
      }
      setIepStrategies(fromIep)
      setStrategies(repo?.items || [])
      setEvidenceStrategies(evidence?.strategies || [])
    } catch {
      setStrategies([])
      setIepStrategies([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => { load() }, [load])

  async function createCandidate(e) {
    e.preventDefault()
    if (!newItem.label.trim()) return
    setMsg('')
    try {
      await apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`, {
        method: 'POST',
        body: JSON.stringify(newItem),
      })
      setNewItem({ label: '', when_to_use: '', how_to_use: '', avoid: '' })
      setMsg('Strategy saved — pending case manager review.')
      await load()
    } catch (err) {
      setMsg(err.message || 'Could not save strategy')
    }
  }

  if (loading) return <p className="ic-case-panel__loading">Loading strategies…</p>

  const allFromIep   = iepStrategies.length
  const customCount  = strategies.filter((s) => s.status !== 'approved').length
  const pendingCount = strategies.filter((s) => s.status === 'pending_review' || s.status === 'local').length
  const helpfulCount = evidenceStrategies.filter((s) => s.outcome_rating >= 4).length

  /* Combine for display */
  const combined = [
    ...iepStrategies.map((s) => ({
      id:    s.id,
      title: s.label,
      category: 'IEP',
      source: 'iep',
      status: 'approved',
    })),
    ...strategies.map((s) => ({
      id:       s.id,
      title:    s.label,
      category: 'Custom',
      source:   'custom',
      whenToUse: s.when_to_use,
      howToUse:  s.how_to_use,
      status:    s.status || 'local',
    })),
  ]

  const filtered = combined.filter((s) => {
    if (filter === 'all')             return true
    if (filter === 'from_iep')        return s.source === 'iep'
    if (filter === 'custom')          return s.source === 'custom'
    if (filter === 'pending_review')  return s.status === 'pending_review' || s.status === 'local'
    if (filter === 'helpful')         return s.status === 'approved'
    if (filter === 'needs_adaptation') return s.status === 'local'
    return true
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
      <div className="clinical-page-header">
        <h2 className="clinical-section-heading">Strategies</h2>
        <p className="clinical-section-subtitle">
          Strategies and accommodations from the IEP and your local proposals.
        </p>
      </div>

      {/* Metric row */}
      <div className="clinical-metric-grid">
        <ClinicalMetricCard count={combined.length}  label="Total Strategies"  icon="🔧" />
        <ClinicalMetricCard count={allFromIep}        label="From IEP"          icon="📋" />
        <ClinicalMetricCard count={customCount}       label="Custom"            icon="✏️" />
        <ClinicalMetricCard count={pendingCount}      label="Pending Review"    icon="🕐" />
      </div>

      {/* Filter chips */}
      <div className="clinical-filter-chips">
        {FILTER_CHIPS.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className={`clinical-filter-chip${filter === chip.id ? ' is-active' : ''}`}
            onClick={() => setFilter(chip.id)}
          >
            {chip.label}
          </button>
        ))}
      </div>

      {/* Strategy cards */}
      {filtered.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {filtered.map((s) => (
            <ClinicalStrategyCard key={s.id} strategy={s} />
          ))}
        </div>
      ) : iepStrategies.length === 0 && strategies.length === 0 ? (
        <ClinicalEmptyState
          icon="🔧"
          title="No strategies linked yet"
          body="Strategies from the IEP builder will appear here once published."
        />
      ) : (
        <ClinicalEmptyState
          title="No strategies match this filter"
          body="Try a different filter to see linked strategies."
        />
      )}

      {/* Propose form */}
      {GOAL_REPOSITORY_ENABLED && variant === 'therapist' ? (
        <ClinicalCard>
          <h4 style={{ fontSize: '0.9375rem', fontWeight: 700, margin: '0 0 0.375rem' }}>Propose a Strategy</h4>
          <p className="cp-hint" style={{ margin: '0 0 0.75rem' }}>
            Strategy suggestions go to your case manager for review.
          </p>
          <form onSubmit={createCandidate} style={{ display: 'flex', flexDirection: 'column', gap: '0.625rem' }}>
            {[
              { field: 'label',      label: 'Strategy name',  tagName: 'input' },
              { field: 'when_to_use', label: 'When to use',   tagName: 'textarea' },
              { field: 'how_to_use', label: 'How to use',     tagName: 'textarea' },
            ].map(({ field, label, tagName }) => (
              <label key={field} style={{ fontWeight: 600, fontSize: '0.875rem' }}>
                {label}
                {tagName === 'textarea' ? (
                  <textarea
                    value={newItem[field]}
                    onChange={(e) => setNewItem({ ...newItem, [field]: e.target.value })}
                    rows={2}
                    style={{ display: 'block', width: '100%', marginTop: '0.3rem', padding: '0.5rem 0.625rem', borderRadius: '8px', border: '1px solid var(--clinical-border)', fontSize: '0.875rem', resize: 'vertical' }}
                  />
                ) : (
                  <input
                    value={newItem[field]}
                    onChange={(e) => setNewItem({ ...newItem, [field]: e.target.value })}
                    style={{ display: 'block', width: '100%', marginTop: '0.3rem', padding: '0.5rem 0.625rem', borderRadius: '8px', border: '1px solid var(--clinical-border)', fontSize: '0.875rem' }}
                  />
                )}
              </label>
            ))}
            {msg ? <p style={{ color: 'var(--clinical-green)', fontSize: '0.875rem' }}>{msg}</p> : null}
            <button type="submit" className="clinical-btn-primary" disabled={newItem.label.trim().length < 3}>
              Save local candidate
            </button>
          </form>
        </ClinicalCard>
      ) : null}
    </div>
  )
}
