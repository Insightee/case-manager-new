/**
 * @deprecated Legacy v2 evidence mapper — use voiceExtractionMapper.js legacyLogToStructuredSession.
 */

import { normalizeGoalEntry, emptyStrategyRow } from './clinicalScoring.js'
import { repoGoalToSessionEntry } from './sessionLogGoals.js'

const PARTICIPATION_VALUES = [
  'not_yet_participating',
  'emerging_participation',
  'participates_with_support',
  'participates_consistently',
  'generalising_across_settings',
]

const INDEPENDENCE_VALUES = [
  'full_adult_support',
  'frequent_support',
  'moderate_support',
  'minimal_support',
  'independent_self_initiated',
]

const ACHIEVEMENT_VALUES = [
  'baseline',
  'emerging',
  'progressing',
  'achieved_familiar_setting',
  'achieved_across_settings',
]

function enumScore(values, value) {
  const idx = values.indexOf(value)
  return idx >= 0 ? idx : null
}

function strategyRowFromExtraction(strat, goalCardId) {
  return {
    ...emptyStrategyRow(goalCardId),
    strategy_id: strat.strategy_id || null,
    strategy_label: strat.strategy_label || strat.strategy_candidate_label || '',
    short_note: strat.implementation_summary || strat.spoken_phrase || '',
    outcome_note: strat.child_response || '',
    strategy_feedback: strat.strategy_feedback || null,
    pending_review: !strat.strategy_id,
  }
}

export function extractionToSessionEvidence(extraction, repo, selectedGoalEntries = []) {
  const entries = []
  const byCardId = new Map()

  for (const entry of selectedGoalEntries) {
    entries.push(entry)
    if (entry.goal_card_id) byCardId.set(entry.goal_card_id, entry)
  }

  const looseStrategies = []
  const goalEvidence = extraction?.goal_evidence || []

  goalEvidence.forEach((goal, gi) => {
    let entry = goal.goal_card_id ? byCardId.get(goal.goal_card_id) : null
    if (!entry) {
      const repoGoal = goal.goal_card_id
        ? (repo?.goals || []).find((g) => g.goal_card_id === goal.goal_card_id)
        : null
      entry = repoGoal
        ? repoGoalToSessionEntry(repoGoal, entries.length)
        : normalizeGoalEntry({
            goal_card_id: null,
            goal_label: goal.goal_label || goal.goal_candidate_label || '',
            _localId: `voice-goal-${gi}`,
            pending_review: true,
            review_status: 'local',
          })
      entries.push(entry)
      if (entry.goal_card_id) byCardId.set(entry.goal_card_id, entry)
    }
    entry.measurement_note = goal.evidence_summary || entry.measurement_note || ''
    entry.participation = goal.participation || null
    entry.independence_support_needed = goal.independence_support_needed || null
    entry.goal_achievement = goal.goal_achievement || null
    entry.participation_score = enumScore(PARTICIPATION_VALUES, goal.participation)
    entry.independence_score = enumScore(INDEPENDENCE_VALUES, goal.independence_support_needed)
    entry.goal_achievement_score = enumScore(ACHIEVEMENT_VALUES, goal.goal_achievement)
  })

  for (const strat of extraction?.strategies || []) {
    const goalIdxInExtraction = strat.goal_index
    let target = null
    if (goalIdxInExtraction != null && goalEvidence[goalIdxInExtraction]) {
      const cardId = goalEvidence[goalIdxInExtraction].goal_card_id
      target = cardId
        ? byCardId.get(cardId)
        : entries.find((e) => e.goal_label === (goalEvidence[goalIdxInExtraction].goal_label || ''))
    }
    const row = strategyRowFromExtraction(strat, target?.goal_card_id || null)
    if (!row.strategy_label) continue
    if (target && !(target.strategies || []).length) {
      target.strategies = [row]
    } else {
      looseStrategies.push(row)
    }
  }

  return {
    schema_version: 2,
    goals: entries.map((e, i) => normalizeGoalEntry({ ...e, _localId: e._localId || `voice-goal-${i}` })),
    strategies: looseStrategies,
  }
}
