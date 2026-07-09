/** Status pill config for Clinical Brain UI. */

export const GOAL_STATUS = {
  active_iep: { id: 'active_iep', label: 'Active IEP goal', tone: 'active' },
  paused: { id: 'paused', label: 'Paused', tone: 'muted' },
  case_candidate: { id: 'case_candidate', label: 'Case candidate', tone: 'pending' },
  draft: { id: 'draft', label: 'Draft', tone: 'muted' },
  sent_for_review: { id: 'sent_for_review', label: 'Sent for review', tone: 'warning' },
  returned: { id: 'returned', label: 'Returned', tone: 'warning' },
  approved_for_case: { id: 'approved_for_case', label: 'Approved for case', tone: 'success' },
  archived: { id: 'archived', label: 'Archived', tone: 'muted' },
}

export const STRATEGY_STATUS = {
  pool_active: { id: 'pool_active', label: 'Pool active', tone: 'active' },
  paused: { id: 'paused', label: 'Paused', tone: 'muted' },
  case_candidate: { id: 'case_candidate', label: 'Case candidate', tone: 'pending' },
  trial: { id: 'trial', label: 'Trial', tone: 'progress' },
  sent_for_review: { id: 'sent_for_review', label: 'Sent for review', tone: 'warning' },
  approved_for_case: { id: 'approved_for_case', label: 'Approved for case', tone: 'success' },
  deprecated: { id: 'deprecated', label: 'Deprecated', tone: 'muted' },
}

export function mapRepositoryGoalStatus(item) {
  if (item?.scope === 'organization' || item?.case_id == null) {
    if (item?.status === 'approved' || item?.status === 'active') return GOAL_STATUS.approved_for_case
    return GOAL_STATUS.archived
  }
  if (item?.lifecycle_status === 'pending_review' || item?.source === 'cm_iep_review') {
    return GOAL_STATUS.sent_for_review
  }
  if (item?.review_note && item?.status === 'candidate') return GOAL_STATUS.returned
  if (item?.status === 'candidate') return GOAL_STATUS.case_candidate
  if (item?.status === 'local') return GOAL_STATUS.draft
  if (item?.status === 'active' || item?.status === 'approved') return GOAL_STATUS.approved_for_case
  return GOAL_STATUS.draft
}

export function mapRepositoryStrategyStatus(item) {
  if (item?.scope === 'organization' || item?.case_id == null) {
    if (item?.status === 'approved' || item?.status === 'active') return STRATEGY_STATUS.pool_active
    if (item?.status === 'archived') return STRATEGY_STATUS.deprecated
    return STRATEGY_STATUS.sent_for_review
  }
  if (item?.lifecycle_status === 'trial' || item?.source === 'trial') return STRATEGY_STATUS.trial
  if (item?.lifecycle_status === 'paused' || item?.source === 'paused' || item?.status === 'paused') {
    return STRATEGY_STATUS.paused
  }
  if (item?.status === 'candidate' || item?.status === 'local') return STRATEGY_STATUS.case_candidate
  if (item?.status === 'active' || item?.status === 'approved') return STRATEGY_STATUS.approved_for_case
  return STRATEGY_STATUS.case_candidate
}

export function evidenceLabelFromCount(count = 0) {
  if (count >= 5) return 'commonly_used'
  if (count >= 2) return 'emerging'
  if (count === 1) return 'used_once'
  return 'new'
}
