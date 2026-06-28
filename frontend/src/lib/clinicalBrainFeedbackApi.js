import { apiFetch } from './apiClient.js'

export const FEEDBACK_STATUS_LABELS = {
  accepted: 'Helpful for this child',
  adapted: 'Adapted for this context',
  not_relevant: 'Not a fit right now',
  already_tried: 'Tried before',
  needs_cm_input: 'Needs CM support',
  dismissed: 'Not a fit right now',
}

export async function fetchStrategyFeedback(caseId, params = {}) {
  const qs = new URLSearchParams()
  if (params.goal_repository_item_id) qs.set('goal_repository_item_id', String(params.goal_repository_item_id))
  if (params.goal_card_id) qs.set('goal_card_id', String(params.goal_card_id))
  if (params.strategy_repository_item_id) {
    qs.set('strategy_repository_item_id', String(params.strategy_repository_item_id))
  }
  const suffix = qs.toString() ? `?${qs}` : ''
  return apiFetch(`/api/v1/clinical-brain/cases/${caseId}/strategy-recommendation-feedback${suffix}`)
}

export async function saveStrategyFeedback(caseId, body) {
  return apiFetch(`/api/v1/clinical-brain/cases/${caseId}/strategy-recommendation-feedback`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function feedbackBadgeLabel(status) {
  return FEEDBACK_STATUS_LABELS[status] || status
}

export function feedbackMapByStrategy(items = []) {
  const map = new Map()
  for (const row of items) {
    const key = row.strategy_repository_item_id || row.strategy_id
    if (key) map.set(key, row)
  }
  return map
}
