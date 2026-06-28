/** Session log goal/strategy pool — same sources as case profile Goals & Strategies tabs. */

import { apiFetch } from './apiClient.js'
import { sectionsJsonToCards } from './iepPlanAdapter.js'
import { mergeRepositoryGoals } from './sessionLogMockGoals.js'

function addUnique(list, seen, item) {
  const key = `${item.strategy_id || ''}:${(item.label || '').toLowerCase()}`
  if (!item.label?.trim() || seen.has(key)) return
  seen.add(key)
  list.push(item)
}

export async function loadSessionLogRepository(caseId) {
  const [iepPlan, goalCandidates, strategyCandidates, goalSummary, strategySummary] = await Promise.all([
    apiFetch(`/api/v1/cases/${caseId}/iep-plan`).catch(() => null),
    apiFetch(`/api/v1/cases/${caseId}/goal-candidates`).catch(() => ({ items: [] })),
    apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`).catch(() => ({ items: [] })),
    apiFetch(`/api/v1/cases/${caseId}/goals/evidence-summary`).catch(() => ({ goals: [] })),
    apiFetch(`/api/v1/cases/${caseId}/strategies/evidence-summary`).catch(() => ({ strategies: [] })),
  ])

  const cards = iepPlan?.sections ? sectionsJsonToCards(iepPlan.sections) : []
  const summaryGoals = goalSummary?.goals || []
  const goalMap = new Map()

  for (const card of cards) {
    const cardId = typeof card.id === 'number' ? card.id : null
    const label = card.label || card.goal_statement || ''
    if (!label.trim()) continue
    goalMap.set(cardId ?? label, {
      goal_card_id: cardId,
      label,
      domain_key: card.domain_key || 'strengths_interests',
      source: 'iep',
      status: card.status || 'active',
    })
  }

  for (const g of summaryGoals) {
    const key = g.goal_id ?? g.label
    if (!goalMap.has(key) && g.label) {
      goalMap.set(key, {
        goal_card_id: g.goal_id || null,
        label: g.label,
        domain_key: g.domain_key,
        source: g.source || 'iep',
        session_count: g.session_count,
        evidence_strength: g.evidence_strength,
      })
    }
  }

  const strategies = []
  const stratSeen = new Set()

  const iepStratText = iepPlan?.sections?.talent_development?.strategies
  if (iepStratText) {
    String(iepStratText)
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((label) => {
        addUnique(strategies, stratSeen, {
          strategy_id: null,
          label,
          source: 'iep',
          category: 'From IEP',
        })
      })
  }

  for (const card of cards) {
    for (const s of card.strategies || []) {
      addUnique(strategies, stratSeen, {
        strategy_id: typeof s.id === 'number' ? s.id : null,
        label: s.label,
        source: 'iep',
        category: 'From IEP',
        goal_card_id: typeof card.id === 'number' ? card.id : null,
        when_to_use: s.when_to_use,
        how_to_use: s.how_to_use,
      })
    }
  }

  for (const s of strategySummary?.strategies || []) {
    addUnique(strategies, stratSeen, {
      strategy_id: s.strategy_id || null,
      label: s.label,
      source: 'evidence',
      category: 'Used in sessions',
      usage_count: s.usage_count,
    })
  }

  for (const s of strategyCandidates?.items || []) {
    if (s.status === 'archived') continue
    addUnique(strategies, stratSeen, {
      strategy_id: s.id,
      label: s.label,
      source: 'custom',
      category: s.status === 'local' || s.status === 'candidate' ? 'Pending review' : 'Custom',
      when_to_use: s.when_to_use,
      how_to_use: s.how_to_use,
      linked_goal_card_id: s.linked_goal_card_id,
    })
  }

  return {
    goals: mergeRepositoryGoals([...goalMap.values()]),
    goalCandidates: goalCandidates?.items || [],
    strategies,
    strategyCandidates: strategyCandidates?.items || [],
  }
}
