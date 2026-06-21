import { ClinicalProgressBar } from '../../clinical-ui/ClinicalProgressBar.jsx'
import { EVIDENCE_LABELS } from '../../../lib/insightsConstants.js'

const EVIDENCE_PROGRESS = {
  insufficient: 10,
  weak: 25,
  moderate: 55,
  strong_operational: 85,
}

const STATUS_CLASS = {
  'variable progress': 'variable',
  emerging: 'emerging',
  active: 'active',
  'mixed signal': 'mixed',
  supports: 'supports',
  review: 'mixed',
}

const CARD_ACTIONS = [
  { label: 'Add to goals', action: 'add_goals', variant: 'primary' },
  { label: 'Add to report', action: 'add_report', variant: 'secondary' },
  { label: 'Suggest to IEP', action: 'suggest_iep', variant: 'secondary' },
]

function formatStatusLabel(status) {
  if (!status) return ''
  return String(status).replace(/_/g, ' ')
}

function weakestStrength(items) {
  const order = ['insufficient', 'weak', 'moderate', 'strong_operational']
  let weakest = 'moderate'
  for (const item of items) {
    const idx = order.indexOf(item)
    const wIdx = order.indexOf(weakest)
    if (idx >= 0 && idx < wIdx) weakest = item
  }
  return weakest
}

export function GoalInsightCard({ card, onAction }) {
  const progress = EVIDENCE_PROGRESS[card.evidenceStrength] ?? 30
  const statusKey = STATUS_CLASS[card.status] || 'default'
  const actions = card.actions?.length ? card.actions : CARD_ACTIONS

  return (
    <article className={`insights-goal-card${card.placeholder ? ' insights-goal-card--placeholder' : ''}`}>
      <div className="insights-goal-card__top">
        <div className="insights-goal-card__top-left">
          {card.categoryLabel ? (
            <span className="insights-goal-card__category">{card.categoryLabel}</span>
          ) : null}
          {card.status ? (
            <span className={`insights-goal-card__status insights-goal-card__status--${statusKey}`}>
              {formatStatusLabel(card.status)}
            </span>
          ) : null}
        </div>
        {card.sessionsCount != null ? (
          <span className="insights-goal-card__sessions">
            <span className="insights-goal-card__sessions-icon" aria-hidden="true">🕐</span>
            {card.sessionsCount} sessions
          </span>
        ) : null}
      </div>

      <h4 className="insights-goal-card__title">{card.title}</h4>

      {card.brief ? (
        <p className="insights-goal-card__brief">{card.brief}</p>
      ) : null}

      {card.evidenceStrength ? (
        <div className="insights-goal-card__evidence">
          <ClinicalProgressBar
            pct={progress}
            label={EVIDENCE_LABELS[card.evidenceStrength] || card.evidenceStrength}
            showPct={false}
            variant={card.evidenceStrength === 'weak' || card.evidenceStrength === 'insufficient' ? 'default' : 'green'}
          />
        </div>
      ) : null}

      {card.strategies?.length ? (
        <div className="insights-goal-card__strategies-block">
          <p className="insights-goal-card__strategies-label">{card.strategiesLabel || 'Active strategies'}</p>
          <div className="insights-goal-card__strategies">
            {card.strategies.map((s) => (
              <span key={s} className="insights-strategy-chip">{s}</span>
            ))}
          </div>
        </div>
      ) : null}

      {card.observation ? (
        <blockquote className="insights-goal-card__observation">&ldquo;{card.observation}&rdquo;</blockquote>
      ) : null}

      {card.insight ? (
        <div className={`insights-goal-card__alert${card.alert ? '' : ' insights-goal-card__alert--muted'}`}>
          {card.alert ? <strong>Important: </strong> : null}
          {card.insight}
        </div>
      ) : null}

      <div className="insights-goal-card__actions">
        {actions.map((a) => (
          <button
            key={a.label}
            type="button"
            className={`insights-goal-card__action-btn insights-goal-card__action-btn--${a.variant || 'secondary'}`}
            onClick={() => onAction?.(a)}
          >
            {a.label}
          </button>
        ))}
      </div>
    </article>
  )
}

export function buildPlaceholderGoalCards(preview) {
  const sessions = preview?.sessions_available ?? 0
  const goalsCount = preview?.active_goals_count ?? 0
  const strategiesCount = preview?.strategies_used_count ?? 0
  const missingLogs = preview?.logs_missing_details ?? 0

  return [
    {
      categoryLabel: 'Goal insight',
      title: goalsCount
        ? 'Participation patterns are starting to show up in logs'
        : 'Goal-linked observations will shape the next support plan',
      brief: goalsCount
        ? `This month includes ${goalsCount} active goal(s) across ${sessions} session(s). Generate insights to see which supports help participation — framed around progress, not gaps.`
        : 'Link IEP goals to session logs so insights can describe what helps the child participate, connect, and grow — in strengths-first language.',
      status: goalsCount ? 'variable progress' : 'emerging',
      evidenceStrength: missingLogs ? 'weak' : goalsCount ? 'moderate' : 'insufficient',
      sessionsCount: sessions || null,
      strategies: goalsCount ? ['Visual countdown', 'First-then'] : [],
      insight: missingLogs
        ? `${missingLogs} log(s) could capture more detail about the child\'s response and the supports in use.`
        : null,
      alert: Boolean(missingLogs),
      placeholder: true,
    },
    {
      categoryLabel: 'Strategy insight',
      title: strategiesCount
        ? 'Some strategies are leaving a trace in session data'
        : 'Strategy signals appear once supports are tagged in logs',
      brief: strategiesCount
        ? `${strategiesCount} strategy signal(s) logged this month. Generate insights to learn which approaches feel regulating and which may need environmental adjustment.`
        : 'When therapists tag strategies during sessions, insights can reflect what appeared helpful — without ranking the child.',
      status: strategiesCount ? 'active' : 'emerging',
      evidenceStrength: strategiesCount ? 'moderate' : 'weak',
      sessionsCount: sessions || null,
      strategies: strategiesCount ? ['Logged in recent sessions'] : [],
      placeholder: true,
    },
    {
      categoryLabel: 'Review insight',
      title: missingLogs
        ? 'A few sessions need richer structured evidence'
        : sessions
          ? 'Mixed signals may be worth a calm second look'
          : 'Session data will reveal what to review next',
      brief: missingLogs
        ? 'Before changing approach, gather what the environment, preparation, and support level were — so review stays curious, not corrective.'
        : sessions
          ? 'Generate insights to flag supports that feel inconsistent — framed as “what may need review,” not what the child did wrong.'
          : 'Add session logs for this month so the team can review patterns with context and care.',
      status: 'review',
      evidenceStrength: missingLogs || !sessions ? 'weak' : 'moderate',
      sessionsCount: sessions || null,
      alert: Boolean(missingLogs),
      insight: missingLogs
        ? 'Recent sessions may lack structured communication or goal evidence — intentional elicitation in the next logs will help.'
        : null,
      placeholder: true,
    },
  ]
}

function primaryGoalHeadline(goals) {
  if (!goals.length) {
    return {
      title: 'Goal progress signals are still forming',
      brief: 'Generate insights to translate session evidence into strengths-first goal summaries.',
    }
  }
  const primary = goals[0]
  return {
    title: primary.goal_title || 'Goal progress insight',
    brief: primary.why || primary.suggested_next_step || primary.recommendation || 'Review session evidence for this goal in neuro-affirmative language.',
  }
}

function primaryStrategyHeadline(strategies) {
  if (!strategies.length) {
    return {
      title: 'Strategy effectiveness is not clear yet',
      brief: 'Tag strategy use in logs, then regenerate to see which supports appeared regulating.',
    }
  }
  const helpful = strategies.find((s) => s.signal === 'appeared_helpful') || strategies[0]
  return {
    title: helpful.strategy || 'Strategy signal',
    brief: helpful.recommendation || helpful.context || 'Continue observing this support in varied environments.',
  }
}

function primaryReviewHeadline(notWorking, evidenceGaps) {
  if (!notWorking.length) {
    const gapText = (evidenceGaps || []).slice(0, 1).join(' ')
    return {
      title: gapText ? 'Documentation gaps to close gently' : 'No major concerns flagged this month',
      brief: gapText || 'Supports appear consistent with current logs — keep collecting structured evidence.',
    }
  }
  const item = notWorking[0]
  return {
    title: item.observation || 'Support may need review',
    brief: item.suggested_review || 'Consider environmental preparation before changing the support approach.',
  }
}

export function buildGoalCardsFromSnapshot(snapshot) {
  if (!snapshot?.ai_output_json) return []

  const out = snapshot.ai_output_json
  const goals = out.goal_recommendations || []
  const strategies = out.strategy_signals || []
  const notWorking = out.what_may_not_be_working || []
  const goalHeadline = primaryGoalHeadline(goals)
  const strategyHeadline = primaryStrategyHeadline(strategies)
  const reviewHeadline = primaryReviewHeadline(notWorking, out.evidence_gaps)
  const goalStrengths = goals.map((g) => g.evidence_strength).filter(Boolean)

  return [
    {
      categoryLabel: 'Goal insight',
      title: goalHeadline.title,
      brief: goalHeadline.brief,
      status: goals.length ? 'variable progress' : 'emerging',
      evidenceStrength: goalStrengths.length ? weakestStrength(goalStrengths) : 'weak',
      strategies: goals.slice(0, 3).map((g) => g.goal_title).filter(Boolean),
      strategiesLabel: 'Related goals',
      observation: goals[0]?.suggested_next_step || null,
      insight: goals.some((g) => g.evidence_strength === 'weak')
        ? 'Some goals still need stronger structured evidence — capture mode, context, and support level in upcoming logs.'
        : null,
      alert: goals.some((g) => g.evidence_strength === 'weak'),
    },
    {
      categoryLabel: 'Strategy insight',
      title: strategyHeadline.title,
      brief: strategyHeadline.brief,
      status: strategies.length ? 'active' : 'emerging',
      evidenceStrength: strategies.some((s) => s.signal === 'mixed') ? 'moderate' : 'moderate',
      strategies: strategies.slice(0, 4).map((s) => s.strategy).filter(Boolean),
      strategiesLabel: 'Active strategies',
      insight: strategies.some((s) => s.signal === 'mixed')
        ? 'One or more strategies showed mixed response — review preparation and environment before intensity.'
        : null,
      alert: strategies.some((s) => s.signal === 'mixed'),
    },
    {
      categoryLabel: 'Review insight',
      title: reviewHeadline.title,
      brief: reviewHeadline.brief,
      status: 'review',
      evidenceStrength: notWorking.length ? 'weak' : 'moderate',
      alert: notWorking.length > 0,
      insight: notWorking.length > 1
        ? notWorking.slice(1).map((n) => n.observation).filter(Boolean).join(' ')
        : null,
    },
  ]
}
