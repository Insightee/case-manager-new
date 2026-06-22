import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { GOALS_STRATEGIES_ENGINE_V2 } from '../../../lib/reportsRevampFlags.js'
import { coreDomainLabel, coreEnvironmentLabel } from '../../../lib/coreClinicalTaxonomy.js'
import { CaseGoalsPanel } from '../../case-profile/sections/CaseGoalsPanel.jsx'
import { CaseStrategiesPanel } from '../../case-profile/sections/CaseStrategiesPanel.jsx'
import { CreateGoalModal } from './CreateGoalModal.jsx'
import { CreateStrategyModal } from './CreateStrategyModal.jsx'
import { AiStrategyLabPanel } from './AiStrategyLabPanel.jsx'
import '../../../styles/goals-strategies-engine.css'

const STATUS_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'Active' },
  { id: 'pending', label: 'Pending review' },
  { id: 'org', label: 'Org pool' },
]

function TaxonomyChips({ domains = [], environments = [] }) {
  if (!domains.length && !environments.length) return null
  return (
    <div className="gs-engine-card__meta">
      {domains.map((d) => (
        <span key={d} className="gs-engine-badge gs-engine-badge--active">
          {coreDomainLabel(d, { short: true })}
        </span>
      ))}
      {environments.map((e) => (
        <span key={e} className="gs-engine-badge">
          {coreEnvironmentLabel(e, { short: true })}
        </span>
      ))}
    </div>
  )
}

export function GoalStrategyEnginePage({ caseId, canModerate = false, variant = 'therapist' }) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [domainFilter, setDomainFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showGoalModal, setShowGoalModal] = useState(false)
  const [showStrategyModal, setShowStrategyModal] = useState(false)
  const [msg, setMsg] = useState('')

  const load = useCallback(async () => {
    if (!caseId || !GOALS_STRATEGIES_ENGINE_V2) return
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(`/api/v1/cases/${caseId}/goals-engine`)
      setPayload(data)
    } catch (err) {
      setError(err.message || 'Could not load goals engine')
      setPayload(null)
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  const filteredGoals = useMemo(() => {
    if (!payload) return []
    const caseGoals = payload.goals || []
    const orgGoals = statusFilter === 'org' ? payload.org_pool_goals || [] : []
    const combined = statusFilter === 'org' ? orgGoals : [...caseGoals, ...(statusFilter === 'all' ? orgGoals : [])]
    return combined.filter((g) => {
      if (statusFilter === 'pending' && !g.is_pending) return false
      if (statusFilter === 'active' && g.is_pending) return false
      if (domainFilter !== 'all' && !(g.core_domains || []).includes(domainFilter) && g.domain_key !== domainFilter) {
        return false
      }
      return true
    })
  }, [payload, domainFilter, statusFilter])

  const filteredStrategies = useMemo(() => {
    if (!payload) return []
    const caseItems = payload.strategies || []
    const orgItems = statusFilter === 'org' ? payload.org_pool_strategies || [] : []
    const combined = statusFilter === 'org' ? orgItems : [...caseItems, ...(statusFilter === 'all' ? orgItems : [])]
    return combined.filter((s) => {
      if (statusFilter === 'pending' && !s.is_pending) return false
      if (statusFilter === 'active' && s.is_pending) return false
      if (domainFilter !== 'all' && !(s.core_domains || []).includes(domainFilter) && s.domain_key !== domainFilter) {
        return false
      }
      return true
    })
  }, [payload, domainFilter, statusFilter])

  if (!GOALS_STRATEGIES_ENGINE_V2) {
    return (
      <>
        <CaseGoalsPanel caseId={caseId} variant={variant} canModerate={canModerate} />
        <CaseStrategiesPanel caseId={caseId} variant={variant} />
      </>
    )
  }

  if (loading) return <p className="gs-muted">Loading goals &amp; strategies…</p>
  if (error) return <p className="gs-error">{error}</p>

  return (
    <div className="gs-engine gs-engine-page">
      <header className="gs-engine-page__head">
        <div>
          <h2 className="gs-engine-page__title">Goals &amp; Strategies</h2>
          <p className="gs-engine-page__sub">
            Case-specific pool linked to IEP goals, session evidence, and org library.
          </p>
        </div>
        <div className="gs-engine-actions">
          <button type="button" className="gs-btn gs-btn--primary" onClick={() => setShowGoalModal(true)}>
            + Create goal
          </button>
          <button type="button" className="gs-btn" onClick={() => setShowStrategyModal(true)}>
            + Create strategy
          </button>
        </div>
      </header>

      {payload?.pending_count ? (
        <p className="gs-engine-pending-banner">
          {payload.pending_count} item{payload.pending_count === 1 ? '' : 's'} awaiting case manager review
        </p>
      ) : null}

      {msg ? <p className="gs-hint">{msg}</p> : null}

      <div className="gs-engine-filters">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.id}
            type="button"
            className={`gs-engine-filter-chip${statusFilter === f.id ? ' is-active' : ''}`}
            onClick={() => setStatusFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
        {(payload?.filter_domains || []).slice(0, 8).map((d) => (
          <button
            key={d}
            type="button"
            className={`gs-engine-filter-chip${domainFilter === d ? ' is-active' : ''}`}
            onClick={() => setDomainFilter(domainFilter === d ? 'all' : d)}
          >
            {coreDomainLabel(d, { short: true }) || d}
          </button>
        ))}
      </div>

      <section>
        <h3 className="sl-v2-section-label">Goals</h3>
        <div className="gs-engine-grid">
          {(payload?.iep_goals || []).map((g) => (
            <article key={`iep-${g.goal_card_id}`} className="gs-engine-card">
              <span className="gs-engine-badge gs-engine-badge--active">IEP</span>
              <p className="gs-engine-card__title">{g.label}</p>
              {g.goal_brief ? <p className="gs-muted">{g.goal_brief}</p> : null}
            </article>
          ))}
          {filteredGoals.map((g) => (
            <article key={`goal-${g.id}`} className="gs-engine-card">
              {g.is_pending ? <span className="gs-engine-badge gs-engine-badge--pending">Pending</span> : null}
              <p className="gs-engine-card__title">{g.label}</p>
              <TaxonomyChips domains={g.core_domains} environments={g.core_environments} />
              {g.rationale ? <p className="gs-muted">{g.rationale}</p> : null}
              {g.created_by_name ? (
                <p className="gs-muted">Created by {g.created_by_name}</p>
              ) : null}
            </article>
          ))}
          {!filteredGoals.length && !(payload?.iep_goals || []).length ? (
            <p className="gs-muted">No goals yet — create one or complete an IEP plan.</p>
          ) : null}
        </div>
      </section>

      <section>
        <h3 className="sl-v2-section-label">Strategies</h3>
        <div className="gs-engine-grid">
          {filteredStrategies.map((s) => (
            <article key={`strat-${s.id}`} className="gs-engine-card">
              {s.is_pending ? <span className="gs-engine-badge gs-engine-badge--pending">Pending</span> : null}
              <p className="gs-engine-card__title">{s.label}</p>
              <TaxonomyChips domains={s.core_domains} environments={s.core_environments} />
              {(s.strategy_steps || []).length ? (
                <ol className="gs-muted">
                  {s.strategy_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              ) : null}
              {s.created_by_name ? (
                <p className="gs-muted">Created by {s.created_by_name}</p>
              ) : null}
            </article>
          ))}
          {!filteredStrategies.length ? (
            <p className="gs-muted">No strategies in this filter — add one from session log or here.</p>
          ) : null}
        </div>
      </section>

      <AiStrategyLabPanel caseId={caseId} />

      {showGoalModal ? (
        <CreateGoalModal
          caseId={caseId}
          onClose={() => setShowGoalModal(false)}
          onCreated={() => {
            setShowGoalModal(false)
            setMsg('Goal saved — pending case manager review.')
            load()
          }}
        />
      ) : null}

      {showStrategyModal ? (
        <CreateStrategyModal
          caseId={caseId}
          onClose={() => setShowStrategyModal(false)}
          onCreated={() => {
            setShowStrategyModal(false)
            setMsg('Strategy saved — pending case manager review.')
            load()
          }}
        />
      ) : null}
    </div>
  )
}
