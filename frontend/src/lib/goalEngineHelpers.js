import {
  GOAL_STATUS_BADGES,
  STRATEGY_EVIDENCE_STATUS_BADGES,
} from './clinicalEvidenceFields.js'

export function resolveGoalBadge(item, { isIep = false } = {}) {
  if (isIep) return GOAL_STATUS_BADGES.active_iep_goal
  if (item.source === 'cm_iep_review' || item.lifecycle_status === 'pending_review') {
    return GOAL_STATUS_BADGES.needs_cm_review
  }
  if (item.status === 'approved' || item.status === 'active') {
    return item.scope === 'organization' ? GOAL_STATUS_BADGES.approved_for_iep : GOAL_STATUS_BADGES.case_specific
  }
  if (item.status === 'candidate') return GOAL_STATUS_BADGES.candidate
  if (item.source === 'session_log_only') return GOAL_STATUS_BADGES.used_today
  if (item.status === 'archived') return GOAL_STATUS_BADGES.rejected
  if (item.review_note?.toLowerCase().includes('merge')) return GOAL_STATUS_BADGES.merged
  if (item.evidence_count === 0 && item.is_pending) return GOAL_STATUS_BADGES.needs_more_evidence
  return GOAL_STATUS_BADGES.case_specific
}

export function resolveStrategyBadge(item) {
  if (item.status === 'approved') return STRATEGY_EVIDENCE_STATUS_BADGES.approved_strategy
  if (item.status === 'candidate') return STRATEGY_EVIDENCE_STATUS_BADGES.strategy_pool_candidate
  if (item.source === 'adaptation') return STRATEGY_EVIDENCE_STATUS_BADGES.repeated_in_case
  if (item.evidence_count >= 3) return STRATEGY_EVIDENCE_STATUS_BADGES.repeated_in_case
  if (item.evidence_count === 1) return STRATEGY_EVIDENCE_STATUS_BADGES.used_once
  if (item.approved_by_user_id) return STRATEGY_EVIDENCE_STATUS_BADGES.cm_reviewed
  return STRATEGY_EVIDENCE_STATUS_BADGES.new
}

export function countEvidenceByGoalCard(events) {
  const counts = {}
  for (const event of events || []) {
    const cardId = event?.goal_linkage?.goal_card_id
    if (!cardId) continue
    counts[cardId] = (counts[cardId] || 0) + 1
  }
  return counts
}

export function sessionLogPath(caseId, goalCardId, variant = 'therapist') {
  const base = variant === 'admin' ? `/admin/cases/${caseId}` : `/therapist/cases/${caseId}`
  const qs = new URLSearchParams({ tab: 'logs' })
  if (goalCardId) qs.set('focus_goal_card', String(goalCardId))
  return `${base}?${qs}`
}
