/** Core domains & environments — compact labels for session log UI. */

export const CORE_DOMAINS = [
  { id: 'communication', label: 'Communication', short: 'Communication' },
  { id: 'social_participation', label: 'Social Participation', short: 'Social skills' },
  { id: 'emotional_regulation', label: 'Emotional Regulation', short: 'Emotions' },
  { id: 'sensory_regulation', label: 'Sensory Regulation', short: 'Sensory' },
  { id: 'independence_daily_living', label: 'Independence / Daily Living', short: 'Daily living' },
  { id: 'learning_readiness', label: 'Learning Readiness', short: 'Learning' },
  { id: 'play_engagement', label: 'Play and Engagement', short: 'Play' },
  { id: 'motor_movement_participation', label: 'Motor / Movement Participation', short: 'Movement (OT)' },
]

export const CORE_ENVIRONMENTS = [
  { id: 'home', label: 'Home', short: 'Home' },
  { id: 'school_classroom', label: 'School / Classroom', short: 'School' },
  { id: 'playground', label: 'Playground', short: 'Playground' },
  { id: 'peer_interaction', label: 'Peer Interaction', short: 'Peers' },
  { id: 'community_outing', label: 'Community Outing', short: 'Community' },
  { id: 'transitions', label: 'Transitions', short: 'Transitions' },
  { id: 'interests', label: 'Interests', short: 'Interests' },
  { id: 'meal_self_care_routine', label: 'Meal / Self-care Routine', short: 'Self care' },
]

export function coreDomainLabel(id, { short = false } = {}) {
  const row = CORE_DOMAINS.find((d) => d.id === id)
  if (!row) return id?.replace(/_/g, ' ') || 'Domain'
  return short ? row.short : row.label
}

export function coreEnvironmentLabel(id, { short = false } = {}) {
  const row = CORE_ENVIRONMENTS.find((e) => e.id === id)
  if (!row) return id?.replace(/_/g, ' ') || 'Environment'
  return short ? row.short : row.label
}

/** Match repository strategies to goal domains / label keywords. */
export function matchRecommendedStrategies(strategies, goal, limit = 5) {
  if (!strategies?.length) return []
  const domains = goal?.core_domains || []
  const labelTokens = (goal?.goal_label || '').toLowerCase().split(/\W+/).filter((t) => t.length > 3)

  const scored = strategies.map((s) => {
    let score = 0
    const sDomain = (s.domain_key || '').toLowerCase()
    const sLabel = (s.label || '').toLowerCase()
    for (const d of domains) {
      if (sDomain.includes(d) || d.includes(sDomain)) score += 3
      const short = coreDomainLabel(d, { short: true }).toLowerCase()
      if (short && sLabel.includes(short.split(' ')[0])) score += 2
    }
    for (const t of labelTokens) {
      if (sLabel.includes(t)) score += 1
    }
    if (s.source === 'iep') score += 1
    return { s, score }
  })

  return scored
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ s }) => s)
}
