/** Dual-write adapter between IEP goal cards and sections_json (Step 6). */

export function cardsToSectionsJson(cards, priorities, existingSections = {}) {
  const goalsText = cards.map((c) => c.goal_statement || c.label).filter(Boolean).join('\n\n')
  const strategiesText = cards
    .flatMap((c) => c.strategies || [])
    .map((s) => s.label)
    .filter(Boolean)
    .join('\n')

  return {
    ...existingSections,
    schema_version: 2,
    talent_development: {
      ...(existingSections.talent_development || {}),
      goals: goalsText || existingSections.talent_development?.goals || '',
      strategies: strategiesText || existingSections.talent_development?.strategies || '',
    },
    support_priorities: priorities.map((p) => p.label),
    goal_cards: cards,
  }
}

export function sectionsJsonToCards(sections) {
  if (sections?.goal_cards?.length) return sections.goal_cards
  const goals = sections?.talent_development?.goals
  if (!goals) return []
  return String(goals)
    .split(/\n\n+/)
    .filter(Boolean)
    .map((label, i) => ({
      id: `legacy-${i}`,
      label,
      goal_statement: label,
      domain_key: 'strengths_interests',
      status: 'active',
    }))
}

export function planIntegrityScore(sections) {
  const checks = [
    Boolean(sections?.header?.child_name),
    Boolean(sections?.talent_development?.strengths),
    Boolean(sections?.talent_development?.goals),
    Boolean(sections?.talent_development?.strategies),
    Boolean(sections?.verification?.therapist_verified),
  ]
  const filled = checks.filter(Boolean).length
  return Math.round((filled / checks.length) * 100)
}
