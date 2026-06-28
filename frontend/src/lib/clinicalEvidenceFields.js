/** Shared clinical evidence chip options — mirrors backend clinical_evidence_contract.py */

export const BANNED_UI_STRINGS = [
  'non-compliant',
  'non compliant',
  'failed',
  'problem behavior',
  'refused',
  'severity score',
  'invalid form',
  'submission failed',
  'missing data',
]

export const STRATEGY_USE_STATUS_OPTIONS = [
  { id: 'used_as_planned', label: 'Used as planned' },
  { id: 'adapted_today', label: 'Adapted today' },
  { id: 'not_used', label: 'Not used' },
]

export const ADAPTATION_TYPE_OPTIONS = [
  { id: 'choice_added', label: 'Added choice' },
  { id: 'time_extended', label: 'Gave more time' },
  { id: 'demand_reduced', label: 'Reduced demand' },
  { id: 'sensory_support_added', label: 'Added sensory support' },
  { id: 'communication_mode_changed', label: 'Changed communication mode' },
  { id: 'environment_modified', label: 'Modified environment' },
  { id: 'routine_adjusted', label: 'Adjusted routine' },
  { id: 'peer_support_added', label: 'Peer support' },
  { id: 'other', label: 'Other' },
]

export const CHILD_RESPONSE_OPTIONS = [
  { id: 'accepted', label: 'Accepted' },
  { id: 'needed_more_time', label: 'Needed more time' },
  { id: 'requested_break', label: 'Requested break' },
  { id: 'requested_help', label: 'Requested help' },
  { id: 'chose_another_option', label: 'Chose another option' },
  { id: 'declined', label: 'Declined' },
  { id: 'variable', label: 'Variable' },
  { id: 'not_observed', label: 'Not observed' },
]

export const ENVIRONMENT_FIT_OPTIONS = [
  { id: 'supportive', label: 'Supportive' },
  { id: 'partly_supportive', label: 'Partly supportive' },
  { id: 'barrier_present', label: 'Barrier present' },
  { id: 'overwhelming', label: 'Overwhelming' },
  { id: 'unpredictable', label: 'Unpredictable' },
]

export const NEXT_STEP_OPTIONS = [
  { id: 'continue', label: 'Continue' },
  { id: 'continue_with_adaptation', label: 'Continue with adaptation' },
  { id: 'try_elsewhere', label: 'Try in another setting' },
  { id: 'try_alternative', label: 'Try alternative' },
  { id: 'pause', label: 'Pause and review' },
  { id: 'cm_review', label: 'Needs CM review' },
]

export const PROGRESS_PARTICIPATION_OPTIONS = [
  { id: 'observed_only', label: 'Observed only' },
  { id: 'brief_engagement', label: 'Brief engagement' },
  { id: 'participated_with_support', label: 'Participated with support' },
  { id: 'active_participation', label: 'Active participation' },
  { id: 'initiated', label: 'Initiated' },
  { id: 'shared_engagement', label: 'Shared engagement' },
  { id: 'not_observed', label: 'Not observed' },
]

/** Quick Evidence Card — participation quality (subset per V1.1 spec). */
export const PARTICIPATION_QUALITY_QUICK_OPTIONS = PROGRESS_PARTICIPATION_OPTIONS.filter(
  (o) => o.id !== 'observed_only',
)

export const BARRIER_TYPE_OPTIONS = [
  { id: 'sensory_load', label: 'Sensory load' },
  { id: 'unexpected_change', label: 'Unexpected change' },
  { id: 'peer_context', label: 'Peer context' },
  { id: 'unclear_expectation', label: 'Unclear expectation' },
  { id: 'transition_pressure', label: 'Transition pressure' },
  { id: 'fatigue_or_health', label: 'Fatigue' },
  { id: 'material_or_task_mismatch', label: 'Task mismatch' },
  { id: 'other', label: 'Other' },
]

export const ADAPTATION_TRIGGER_FEEDBACK = new Set([
  'PARTLY_HELPFUL',
  'NOT_HELPFUL',
  'CHILD_REJECTED',
  'NEEDS_ADAPTATION',
])

export const BARRIER_ENVIRONMENT_FITS = new Set(['barrier_present', 'overwhelming', 'unpredictable'])

export const PROGRESS_SUPPORT_NEEDED_OPTIONS = [
  { id: 'independent', label: 'Independent' },
  { id: 'visual_support', label: 'Visual support' },
  { id: 'verbal_support', label: 'Verbal support' },
  { id: 'gestural_support', label: 'Gestural support' },
  { id: 'co_regulation', label: 'Co-regulation' },
  { id: 'peer_support', label: 'Peer support' },
  { id: 'environmental_support', label: 'Environmental support' },
  { id: 'not_observed', label: 'Not observed' },
]

export const PROGRESS_GOAL_MOVEMENT_OPTIONS = [
  { id: 'new_exposure', label: 'New exposure' },
  { id: 'practised', label: 'Practised' },
  { id: 'small_movement', label: 'Small movement' },
  { id: 'clear_progress', label: 'Clear progress' },
  { id: 'maintained', label: 'Maintained' },
  { id: 'variable', label: 'Variable' },
  { id: 'more_support_needed', label: 'More support needed' },
  { id: 'not_enough_evidence', label: 'Not enough evidence' },
]

export const OBSERVATION_SIGNAL_OPTIONS = [
  { id: 'strength', label: 'Strength' },
  { id: 'interest', label: 'Interest' },
  { id: 'support_need', label: 'Support need' },
  { id: 'barrier', label: 'Barrier' },
  { id: 'preference', label: 'Preference' },
  { id: 'self_advocacy', label: 'Self-advocacy' },
  { id: 'emerging_pattern', label: 'Emerging pattern' },
  { id: 'needs_more_evidence', label: 'Needs more evidence' },
]

export const GOAL_STATUS_BADGES = {
  active_iep_goal: { label: 'Active IEP goal', tone: 'active' },
  used_today: { label: 'Used today', tone: 'progress' },
  case_specific: { label: 'Case-specific', tone: 'muted' },
  candidate: { label: 'Candidate', tone: 'pending' },
  needs_cm_review: { label: 'Needs CM review', tone: 'warning' },
  approved_for_iep: { label: 'Approved for IEP', tone: 'success' },
  merged: { label: 'Merged', tone: 'muted' },
  rejected: { label: 'Rejected', tone: 'negative' },
  needs_more_evidence: { label: 'Needs more evidence', tone: 'warning' },
}

export const STRATEGY_EVIDENCE_STATUS_BADGES = {
  new: { label: 'New', tone: 'muted' },
  used_once: { label: 'Used once', tone: 'progress' },
  repeated_in_case: { label: 'Repeated in case', tone: 'active' },
  cm_reviewed: { label: 'CM reviewed', tone: 'success' },
  strategy_pool_candidate: { label: 'Strategy pool candidate', tone: 'pending' },
  approved_strategy: { label: 'Approved strategy', tone: 'success' },
}

export const IEP_STRATEGY_STATUS_OPTIONS = [
  { id: 'planned', label: 'Planned' },
  { id: 'being_trialled', label: 'Being trialled' },
  { id: 'useful_in_some_contexts', label: 'Useful in some contexts' },
  { id: 'needs_adaptation', label: 'Needs adaptation' },
  { id: 'paused', label: 'Paused' },
  { id: 'replaced', label: 'Replaced' },
]

export const IEP_GOAL_REVIEW_OPTIONS = [
  { id: 'continue', label: 'Continue' },
  { id: 'revise', label: 'Revise' },
  { id: 'add_environment', label: 'Add environment' },
  { id: 'change_strategy', label: 'Change strategy' },
  { id: 'pause', label: 'Pause' },
  { id: 'close', label: 'Close' },
  { id: 'needs_more_evidence', label: 'Needs more evidence' },
]

export const GOAL_USE_OPTIONS = [
  { id: 'session_log_only', label: 'Use only in today\'s log' },
  { id: 'case_candidate', label: 'Add as case goal candidate' },
  { id: 'cm_iep_review', label: 'Send to CM for IEP review' },
]

export const STRATEGY_TYPE_OPTIONS = [
  { id: 'pool', label: 'Approved strategy from pool' },
  { id: 'case_specific', label: 'Case-specific strategy' },
  { id: 'adaptation', label: 'Adaptation of existing strategy' },
  { id: 'one_time', label: 'One-time session support' },
]

export function emptyClinicalExtension() {
  return {
    child_response: null,
    environment_fit: null,
    therapist_interpretation: null,
    participation_quality: null,
    support_needed: null,
    goal_movement: null,
    strategy_status: null,
    adaptation_type: [],
    adaptation_note: '',
    barrier_type: [],
    field_provenance: {},
  }
}

export function getClinicalExtension(goalOrStrategy) {
  return { ...emptyClinicalExtension(), ...(goalOrStrategy?.clinical_extension || {}) }
}

export function shouldShowBarrierTypes(environmentFit) {
  return BARRIER_ENVIRONMENT_FITS.has(environmentFit)
}

export function shouldShowAdaptation(strategyFeedback, manualOpen = false) {
  return manualOpen || ADAPTATION_TRIGGER_FEEDBACK.has(strategyFeedback)
}

export function mergeClinicalExtension(base, patch) {
  const prev = getClinicalExtension({ clinical_extension: base })
  const next = { ...prev, ...patch }
  const provenance = { ...(prev.field_provenance || {}) }
  Object.keys(patch).forEach((key) => {
    if (key === 'field_provenance') return
    const val = patch[key]
    if (val == null || val === '') return
    if (Array.isArray(val) && !val.length) return
    provenance[key] = key === 'adaptation_note' ? 'human_written' : 'human_selected'
  })
  next.field_provenance = provenance
  return next
}

export function containsBannedLanguage(text) {
  const lower = String(text || '').toLowerCase()
  return BANNED_UI_STRINGS.some((b) => lower.includes(b))
}

export function validateQuickEvidence(extension) {
  const gaps = []
  if (!extension?.child_response) gaps.push('child_response')
  if (!extension?.therapist_interpretation) gaps.push('next_step')
  return gaps
}

export function labelForOption(options, id) {
  return options.find((o) => o.id === id)?.label || id || '—'
}

/** Smart defaults when strategy feedback changes */
export function suggestDefaultsFromFeedback(strategyFeedback, extension = {}) {
  const next = { ...extension }
  if (['PARTLY_HELPFUL', 'NOT_HELPFUL', 'CHILD_REJECTED', 'NEEDS_ADAPTATION'].includes(strategyFeedback)) {
    if (!next.therapist_interpretation) next.therapist_interpretation = 'continue_with_adaptation'
    if (strategyFeedback === 'NOT_HELPFUL' && !next.therapist_interpretation) {
      next.therapist_interpretation = 'try_elsewhere'
    }
    if (strategyFeedback === 'CHILD_REJECTED' && !next.therapist_interpretation) {
      next.therapist_interpretation = 'pause'
    }
  }
  return next
}

export function suggestFromChildResponse(childResponse, extension = {}) {
  const next = { ...extension }
  if (childResponse === 'requested_break' && !next.regulation_signal) {
    next.regulation_signal = 'needed_break'
  }
  return next
}

export function suggestFromStrategyStatus(strategyStatus, extension = {}) {
  const next = { ...extension }
  if (strategyStatus === 'not_used' && !next.therapist_interpretation) {
    next.therapist_interpretation = 'pause'
  }
  return next
}
