/** Session log goal pool — case goals, search, mock concern matching (no LLM). */

import { emptyGoalEntry, emptyStrategyRow } from './clinicalScoring.js'

const CONCERN_HINTS = [
  {
    keywords: ['transition', 'classroom', 'change', 'moving'],
    goals: ['Classroom transition participation'],
    strategies: ['Visual countdown', 'First-then transition cue', 'Choice of transition route'],
  },
  {
    keywords: ['regulation', 'emotion', 'overwhelm', 'meltdown', 'group'],
    goals: ['Emotional regulation during group time'],
    strategies: ['Co-regulation pause', 'Visual feeling chart', 'Sensory break before task'],
  },
  {
    keywords: ['sensory', 'break', 'overstim'],
    goals: ['Sensory self-advocacy'],
    strategies: ['Scheduled sensory break', 'Quiet corner access', 'Noise-reducing headphones'],
  },
]

export function goalLocalId(goal, index = 0) {
  return goal._localId || `goal-${goal.goal_card_id || goal.goal_repository_item_id || index}`
}

export function repoGoalToSessionEntry(g, index = 0) {
  const pending = g.status === 'local' || g.status === 'candidate' || g.is_pending
  return {
    ...emptyGoalEntry({
      id: g.goal_card_id,
      label: g.label,
      goal_statement: g.goal_statement || g.label,
      domain_key: g.domain_key,
      baseline: g.goal_brief || g.baseline_state || g.baseline || g.rationale,
      why_it_matters: g.desired_state,
      core_domains: g.core_domains || (g.domain_key ? [g.domain_key] : []),
      core_environments: g.core_environments || [],
    }),
    _localId: goalLocalId(
      { goal_card_id: g.goal_card_id, goal_repository_item_id: g.id, _localId: g._localId },
      index,
    ),
    goal_repository_item_id: g.id || null,
    review_status: g.status || null,
    pending_review: pending,
    goal_description:
      g.goal_brief ||
      g.baseline_state ||
      g.baseline ||
      [g.baseline_state, g.desired_state].filter(Boolean).join(' · ') ||
      g.rationale ||
      '',
  }
}

/** Build session log goal rows from case IEP + repository (no blank placeholder). */
export function buildCaseGoalsForSessionLog(repo) {
  if (!repo) return []
  const entries = []
  const seen = new Set()

  for (const g of repo.goals || []) {
    const label = (g.label || '').trim().toLowerCase()
    if (!label || seen.has(label)) continue
    seen.add(label)
    entries.push(repoGoalToSessionEntry(g, entries.length))
  }

  for (const g of repo.goalCandidates || []) {
    if (g.status === 'archived') continue
    const label = (g.label || '').trim().toLowerCase()
    if (!label || seen.has(label)) continue
    seen.add(label)
    entries.push(
      repoGoalToSessionEntry(
        {
          ...g,
          goal_brief: g.baseline_state || g.rationale,
          core_domains: g.core_domains || (g.domain_key ? [g.domain_key] : []),
        },
        entries.length,
      ),
    )
  }

  return entries
}

function matchesQuery(text, q) {
  return String(text || '')
    .toLowerCase()
    .includes(q)
}

/** Search approved + case goals/strategies; optional mock concern suggestions. */
export function searchGoalStrategyPool(query, repo) {
  const q = (query || '').trim().toLowerCase()
  if (!q) return { goals: [], strategies: [], suggestions: [] }

  const goals = []
  const strategies = []
  const seenG = new Set()
  const seenS = new Set()

  for (const g of repo?.goals || []) {
    const hay = [g.label, g.goal_brief, g.baseline_state, g.desired_state, ...(g.core_domains || [])].join(' ')
    if (matchesQuery(hay, q) && !seenG.has(g.label)) {
      seenG.add(g.label)
      goals.push(g)
    }
  }

  for (const g of repo?.goalCandidates || []) {
    if (g.status === 'archived') continue
    const hay = [g.label, g.baseline_state, g.desired_state, g.rationale].join(' ')
    if (matchesQuery(hay, q) && !seenG.has(g.label)) {
      seenG.add(g.label)
      goals.push({ ...g, goal_brief: g.baseline_state })
    }
  }

  for (const s of repo?.strategies || []) {
    const hay = [s.label, s.when_to_use, s.how_to_use, s.category].join(' ')
    if (matchesQuery(hay, q) && !seenS.has(s.label)) {
      seenS.add(s.label)
      strategies.push(s)
    }
  }

  const suggestions = []
  for (const hint of CONCERN_HINTS) {
    if (!hint.keywords.some((k) => q.includes(k))) continue
    for (const gl of hint.goals) {
      if (!seenG.has(gl)) suggestions.push({ type: 'goal', label: gl, source: 'suggestion' })
    }
    for (const sl of hint.strategies) {
      if (!seenS.has(sl)) suggestions.push({ type: 'strategy', label: sl, source: 'suggestion' })
    }
  }

  return { goals: goals.slice(0, 8), strategies: strategies.slice(0, 8), suggestions: suggestions.slice(0, 6) }
}

export function strategyRowFromRepoItem(item) {
  const steps = item.strategy_steps?.length
    ? item.strategy_steps
    : String(item.how_to_use || '')
        .split(/\n+/)
        .filter(Boolean)
        .slice(0, 3)
  while (steps.length < 3) steps.push('')
  return {
    ...emptyStrategyRow(item.goal_card_id || item.linked_goal_card_id),
    strategy_id: item.strategy_id || item.id || null,
    strategy_label: item.label,
    strategy_steps: steps,
    expected_outcome: item.expected_outcome || item.when_to_use || '',
    custom_strategy_id: item.id || null,
  }
}
