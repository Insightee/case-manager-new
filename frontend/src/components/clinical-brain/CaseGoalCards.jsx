import { Link } from 'react-router-dom'
import { coreDomainLabel } from '../../lib/coreClinicalTaxonomy.js'
import { SOURCE_LABELS, STRATEGY_INSIGHTS_PLACEHOLDER, VISIBILITY_LABELS } from '../../lib/clinicalBrainCopy.js'
import {
  evidenceLabelFromCount,
  mapRepositoryGoalStatus,
  mapRepositoryStrategyStatus,
} from '../../lib/clinicalBrainStatus.js'
import { sessionLogPath } from '../../lib/goalEngineHelpers.js'
import { ClinicalBrainStatusPill } from './ClinicalBrainStatusPill.jsx'

function DomainChip({ domain }) {
  if (!domain) return null
  return <span className="cb-pill cb-pill--active">{coreDomainLabel(domain, { short: true }) || domain}</span>
}

function CardActions({ children }) {
  return <div className="cb-card__actions">{children}</div>
}

export function ActiveIepGoalCard({ goal, caseId, variant, onViewStrategies }) {
  const domain = goal.domain_key || (goal.core_domains || [])[0]
  return (
    <article className="cb-card">
      <div className="cb-card__head">
        <h4 className="cb-card__title">{goal.label}</h4>
        <ClinicalBrainStatusPill status="active_iep" />
      </div>
      <div className="cb-card__meta">
        <DomainChip domain={domain} />
        <span>{goal.evidence_count ?? 0} evidence this month</span>
        <span title="Parent visibility">Parent-safe when in approved report</span>
      </div>
      {goal.goal_brief ? <p className="gs-muted">{goal.goal_brief}</p> : null}
      <CardActions>
        {goal.goal_card_id ? (
          <Link className="cb-btn cb-btn--primary" to={sessionLogPath(caseId, goal.goal_card_id, variant)}>
            Use in today&apos;s log
          </Link>
        ) : null}
        <button type="button" className="cb-btn" onClick={() => onViewStrategies?.(goal)}>
          View strategies
        </button>
      </CardActions>
    </article>
  )
}

export function GoalCandidateCard({ goal, caseId, variant, onEdit, onSendReview }) {
  const status = mapRepositoryGoalStatus(goal)
  const source = SOURCE_LABELS[goal.source] || goal.source || 'Custom'
  return (
    <article className="cb-card">
      <div className="cb-card__head">
        <h4 className="cb-card__title">{goal.label}</h4>
        <ClinicalBrainStatusPill status={status.id} />
      </div>
      <div className="cb-card__meta">
        <DomainChip domain={goal.domain_key || (goal.core_domains || [])[0]} />
        <span>Source: {source}</span>
        {goal.created_by_name ? <span>By {goal.created_by_name}</span> : null}
      </div>
      {goal.rationale ? <p className="gs-muted">{goal.rationale}</p> : null}
      <CardActions>
        <button type="button" className="cb-btn" onClick={() => onEdit?.(goal)}>
          Edit
        </button>
        {goal.is_pending ? (
          <button type="button" className="cb-btn cb-btn--primary" onClick={() => onSendReview?.(goal)}>
            Send to CM review
          </button>
        ) : null}
        {goal.goal_card_id || goal.id ? (
          <Link className="cb-btn" to={sessionLogPath(caseId, goal.goal_card_id || goal.id, variant)}>
            Use in today&apos;s log
          </Link>
        ) : null}
      </CardActions>
    </article>
  )
}

export function StrategySuggestionCard({ strategy, caseId, variant, onUseLog, onAddTrial }) {
  const evidence = evidenceLabelFromCount(strategy.evidence_count || strategy.usage_count || 0)
  return (
    <article className="cb-card">
      <div className="cb-card__head">
        <h4 className="cb-card__title">{strategy.label}</h4>
        <span className="cb-pill cb-pill--progress">{evidence.replace('_', ' ')}</span>
      </div>
      <p className="gs-muted">{strategy.when_to_use || strategy.purpose || strategy.expected_outcome}</p>
      <div className="cb-card__meta">
        <DomainChip domain={strategy.domain_key || (strategy.core_domains || [])[0]} />
        {(strategy.core_environments || []).slice(0, 2).map((e) => (
          <span key={e} className="cb-pill cb-pill--muted">{e}</span>
        ))}
      </div>
      {strategy.avoid ? <p className="gs-muted"><strong>Caution:</strong> {strategy.avoid}</p> : null}
      <CardActions>
        <button type="button" className="cb-btn cb-btn--primary" onClick={() => onUseLog?.(strategy)}>
          Use in today&apos;s log
        </button>
        <button type="button" className="cb-btn" onClick={() => onAddTrial?.(strategy)}>
          Add to case trials
        </button>
      </CardActions>
    </article>
  )
}

export function StrategyTrialCard({ strategy, caseId, variant, onLogUse }) {
  const status = mapRepositoryStrategyStatus({ ...strategy, source: 'trial', lifecycle_status: 'trial' })
  return (
    <article className="cb-card">
      <div className="cb-card__head">
        <h4 className="cb-card__title">{strategy.label}</h4>
        <ClinicalBrainStatusPill status={status.id} kind="strategy" />
      </div>
      <div className="cb-card__meta">
        {strategy.linked_goal_card_id ? <span>Linked goal #{strategy.linked_goal_card_id}</span> : null}
        <DomainChip domain={strategy.domain_key} />
        <span>{strategy.latest_outcome || 'Continue with adaptation'}</span>
      </div>
      <CardActions>
        <Link
          className="cb-btn cb-btn--primary"
          to={sessionLogPath(caseId, strategy.linked_goal_card_id, variant)}
        >
          Log use today
        </Link>
        <button type="button" className="cb-btn" onClick={() => onLogUse?.(strategy)}>
          Open session log
        </button>
      </CardActions>
    </article>
  )
}

export function LibraryShortcuts({ variant }) {
  const adminBase = variant === 'admin' ? '/admin' : null
  if (!adminBase) {
    return (
      <div className="cb-library-shortcuts">
        <p className="gs-muted">Approved templates come from your organisation Goal Bank and Strategy Pool.</p>
      </div>
    )
  }
  return (
    <div className="cb-library-shortcuts">
      <Link className="cb-btn" to={`${adminBase}/goal-bank`}>Organisation Goal Bank</Link>
      <Link className="cb-btn" to={`${adminBase}/strategy-pool`}>Organisation Strategy Pool</Link>
    </div>
  )
}

export function StrategyInsightsPlaceholder() {
  return (
    <div className="cb-insights-placeholder">
      <p className="m-0">{STRATEGY_INSIGHTS_PLACEHOLDER}</p>
    </div>
  )
}

export { VISIBILITY_LABELS }
