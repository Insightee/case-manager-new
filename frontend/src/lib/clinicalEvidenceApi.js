import { apiFetch } from './apiClient.js'

export function currentReportMonth(date = new Date()) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  return `${y}-${m}`
}

export async function fetchCaseClinicalEvidenceEvents(caseId, month = currentReportMonth()) {
  const qs = new URLSearchParams({ month })
  return apiFetch(`/api/v1/cases/${caseId}/clinical-evidence-events?${qs}`)
}

export async function fetchClinicalBrainEvidence(reportId) {
  return apiFetch(`/api/v1/reports/${reportId}/clinical-brain-evidence`)
}

export function filterEventsForGoal(events, goal) {
  const cardId = goal?.goal_card_id || goal?.goal_source_id
  const title = goal?.label || goal?.title || goal?.goal_statement
  return (events || []).filter((event) => {
    const linkage = event.goal_linkage || {}
    if (cardId && Number(linkage.goal_card_id) === Number(cardId)) return true
    if (title && linkage.goal_title === title) return true
    return false
  })
}

export function aggregateGoalEvidence(events) {
  const filtered = events || []
  let adaptationCount = 0
  let activeParticipationCount = 0
  const interpretationCounts = {}
  const barrierCounts = {}
  const adaptationCounts = {}

  for (const event of filtered) {
    const strategy = event.strategy_linkage || {}
    const support = event.support_and_response || {}
    const therapist = event.therapist_view || {}
    const context = event.context || {}

    if ((strategy.adaptation_type || []).length) adaptationCount += 1
    if (support.participation_signal === 'active_participation') activeParticipationCount += 1

    const nextStep = therapist.therapist_interpretation
    if (nextStep) interpretationCounts[nextStep] = (interpretationCounts[nextStep] || 0) + 1

    for (const barrier of context.barrier_type || []) {
      barrierCounts[barrier] = (barrierCounts[barrier] || 0) + 1
    }
    for (const adapt of strategy.adaptation_type || []) {
      adaptationCounts[adapt] = (adaptationCounts[adapt] || 0) + 1
    }
  }

  const commonBarriers = Object.entries(barrierCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 2)
    .map(([id]) => id)

  const nextStep = Object.entries(interpretationCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || null

  const repeatedAdaptations = Object.fromEntries(
    Object.entries(adaptationCounts).filter(([, count]) => count >= 3),
  )

  return {
    sessionCount: filtered.length,
    activeParticipationCount,
    adaptationCount,
    commonBarriers,
    nextStep,
    repeatedAdaptations,
    adaptationCounts,
  }
}
