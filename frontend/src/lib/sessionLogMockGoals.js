/** Demo IEP goals — shown when case repository is sparse (local dev / empty cases). */

export const MOCK_IEP_GOALS = [
  {
    goal_card_id: 'mock-iep-1',
    label: 'Classroom transition participation',
    goal_brief:
      'Baseline: needs high support during transitions. Desired: moves between activities with predictable visual support.',
    core_domains: ['social_participation'],
    core_environments: ['school_classroom', 'transitions'],
    source: 'iep',
  },
  {
    goal_card_id: 'mock-iep-2',
    label: 'Emotional regulation during group time',
    goal_brief: 'Uses co-regulation strategies before escalation; working toward naming feelings with a visual cue.',
    core_domains: ['emotional_regulation', 'social_participation'],
    core_environments: ['school_classroom', 'peer_interaction'],
    source: 'iep',
  },
  {
    goal_card_id: 'mock-iep-3',
    label: 'Sensory breaks before tasks',
    goal_brief: 'Requests or accepts a sensory break when overwhelmed; participates after reset.',
    core_domains: ['sensory_regulation', 'learning_readiness'],
    core_environments: ['school_classroom', 'home'],
    source: 'iep',
  },
]

export function mergeRepositoryGoals(repoGoals = []) {
  if (repoGoals.length >= 2) return repoGoals
  const seen = new Set(repoGoals.map((g) => (g.label || '').toLowerCase()))
  const extras = MOCK_IEP_GOALS.filter((m) => !seen.has(m.label.toLowerCase()))
  return [...repoGoals, ...extras]
}
