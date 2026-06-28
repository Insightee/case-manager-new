import { Link } from 'react-router-dom'
import { coreDomainLabel, coreEnvironmentLabel } from '../../../lib/coreClinicalTaxonomy.js'
import { sessionLogPath } from '../../../lib/goalEngineHelpers.js'
import { apiFetch } from '../../../lib/apiClient.js'

function Badge({ badge }) {
  if (!badge) return null
  return <span className={`gs-engine-badge gs-engine-badge--${badge.tone || 'muted'}`}>{badge.label}</span>
}

export function GoalEngineCard({
  item,
  kind = 'goal',
  badge,
  caseId,
  variant = 'therapist',
  canModerate = false,
  onAction,
}) {
  const isGoal = kind === 'goal'
  const title = item.label || item.title
  const domains = item.core_domains || (item.domain_key ? [item.domain_key] : [])
  const environments = item.core_environments || []

  async function review(action) {
    const path = isGoal
      ? `/api/v1/cases/${caseId}/goal-repository/${item.id}/review`
      : `/api/v1/cases/${caseId}/strategy-repository/${item.id}/review`
    await apiFetch(path, {
      method: 'POST',
      body: JSON.stringify({ action, note: '' }),
    })
    onAction?.()
  }

  return (
    <article className="gs-engine-card">
      <div className="gs-engine-card__badges">
        <Badge badge={badge} />
        {item.evidence_count != null ? (
          <span className="gs-engine-badge">{item.evidence_count} evidence</span>
        ) : null}
      </div>
      <p className="gs-engine-card__title">{title}</p>
      {(domains.length || environments.length) ? (
        <div className="gs-engine-card__meta">
          {domains.map((d) => (
            <span key={d} className="gs-engine-badge gs-engine-badge--active">
              {coreDomainLabel(d, { short: true })}
            </span>
          ))}
          {environments.map((e) => (
            <span key={e} className="gs-engine-badge">{coreEnvironmentLabel(e, { short: true })}</span>
          ))}
        </div>
      ) : null}
      {item.rationale || item.goal_brief ? (
        <p className="gs-muted">{item.rationale || item.goal_brief}</p>
      ) : null}
      {(item.strategy_steps || []).length ? (
        <ol className="gs-muted">
          {item.strategy_steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
      ) : null}
      {item.created_by_name ? <p className="gs-muted">Created by {item.created_by_name}</p> : null}

      <div className="gs-engine-card__actions">
        {isGoal && item.goal_card_id ? (
          <Link className="gs-btn gs-btn--primary" to={sessionLogPath(caseId, item.goal_card_id, variant)}>
            Use in today&apos;s log
          </Link>
        ) : null}
        {!isGoal && item.linked_goal_card_id ? (
          <Link className="gs-btn" to={sessionLogPath(caseId, item.linked_goal_card_id, variant)}>
            Use in today&apos;s log
          </Link>
        ) : null}
        {item.is_pending && !canModerate ? (
          <button type="button" className="gs-btn" onClick={() => review('request_edits')}>
            Send to CM review
          </button>
        ) : null}
        {canModerate && item.is_pending ? (
          <>
            <button type="button" className="gs-btn gs-btn--primary" onClick={() => review('approve_case')}>
              Keep case-specific
            </button>
            <button type="button" className="gs-btn" onClick={() => review('approve_pool')}>
              Propose to IEP pool
            </button>
            <button type="button" className="gs-btn" onClick={() => review('reject')}>
              Dismiss
            </button>
          </>
        ) : null}
      </div>
    </article>
  )
}
