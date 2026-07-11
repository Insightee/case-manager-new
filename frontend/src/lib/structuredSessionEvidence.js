/** Structured session evidence v1 — canonical voice log state. */

export const STRUCTURED_SESSION_SCHEMA_VERSION = 1

export const GOAL_STATUSES = ['pending', 'confirmed', 'rejected', 'changed']
/** Canonical aliases: pending→suggested, changed→edited_and_confirmed (see docs/product/SESSION_LOG_V1.md) */
export const GOAL_STATUS_CANONICAL = {
  pending: 'suggested',
  confirmed: 'confirmed',
  rejected: 'rejected',
  changed: 'edited_and_confirmed',
}
export const GOAL_MATCH_TYPES = ['active_iep', 'suggested', 'new_observation']
export const STRATEGY_FEEDBACK = ['worked_well', 'partially_worked', 'did_not_work', 'not_observed']

export const REFLECTION_PROMPTS = [
  'Something that surprised me',
  'What worked better than expected',
  'Something I want supervision on',
  'Something to remember next session',
]

export const RECORDING_CUES = [
  'What did you work on?',
  'Which strategies did you use?',
  'How did the child respond?',
  'Any challenging behaviors?',
]

export const PROCESSING_STEPS = [
  { id: 'transcribing', label: 'Transcribing' },
  { id: 'identifying_goals', label: 'Identifying goals' },
  { id: 'matching_strategies', label: 'Matching existing strategies' },
  { id: 'identifying_observations', label: 'Identifying observations' },
  { id: 'creating_therapist_draft', label: 'Creating therapist draft' },
  { id: 'creating_parent_summary', label: 'Creating parent summary' },
]

/** Child response vocabulary — neuro-affirming, deterministic (no LLM). */
export const CHILD_RESPONSE_SIGNALS = [
  { id: 'engaged', label: 'Engaged with activities' },
  { id: 'participated_with_support', label: 'Participated with support' },
  { id: 'initiated_interaction', label: 'Initiated interaction' },
  { id: 'requested_break', label: 'Requested a break' },
  { id: 'needed_extra_time', label: 'Needed extra time' },
  { id: 'declined_activity', label: 'Declined an activity' },
  { id: 'became_overwhelmed', label: 'Became overwhelmed' },
  { id: 'returned_after_regulation', label: 'Returned after regulation' },
  { id: 'self_advocated', label: 'Self-advocated' },
  { id: 'explored_independently', label: 'Explored independently' },
]

export const COMMON_RESPONSE_SIGNAL_IDS = ['engaged', 'participated_with_support', 'requested_break']

export function responseSignalLabel(id) {
  return CHILD_RESPONSE_SIGNALS.find((s) => s.id === id)?.label || id.replace(/_/g, ' ')
}

/** Keyword → signal inference from extraction prose (Layer 1, deterministic). */
const SIGNAL_KEYWORDS = [
  { id: 'became_overwhelmed', words: ['overwhelm', 'meltdown', 'distress', 'upset'] },
  { id: 'requested_break', words: ['break', 'pause', 'stepped away'] },
  { id: 'returned_after_regulation', words: ['calmed', 'regulat', 'came back', 'returned'] },
  { id: 'declined_activity', words: ['refus', 'declin', 'did not want', "didn't want"] },
  { id: 'initiated_interaction', words: ['initiat', 'greet', 'waved', 'approached'] },
  { id: 'self_advocated', words: ['asked for', 'advocat', 'requested help'] },
  { id: 'participated_with_support', words: ['with support', 'with prompting', 'with help', 'prompted'] },
  { id: 'engaged', words: ['engag', 'enjoyed', 'participat', 'focused', 'interested'] },
]

export function inferResponseSignals(text) {
  const hay = String(text || '').toLowerCase()
  if (!hay) return []
  const found = []
  for (const { id, words } of SIGNAL_KEYWORDS) {
    if (words.some((w) => hay.includes(w))) found.push(id)
  }
  return found.slice(0, 4)
}

export const NO_GOAL_REASONS = [
  { id: 'regulation_day', label: 'Regulation-focused day' },
  { id: 'rapport_building', label: 'Rapport building' },
  { id: 'child_led_exploration', label: 'Child-led exploration' },
  { id: 'environment_change', label: 'Environment change / transition day' },
  { id: 'assessment_observation', label: 'Assessment or observation only' },
]

export function emptyStructuredSession({ sessionId, recordingId } = {}) {
  return {
    schema_version: STRUCTURED_SESSION_SCHEMA_VERSION,
    session_id: sessionId ?? null,
    recording_id: recordingId ?? null,
    voice_transcript: '',
    todays_story: '',
    story_edited_by_therapist: false,
    goals: [],
    strategies_session_level: [],
    child_response_signals: [],
    challenge_observations: [],
    goal_candidates: [],
    strategy_candidates: [],
    session_context: {
      environment: null,
      service_type: null,
    },
    no_goal_reason: null,
    extraction_version: null,
    observations: {
      strengths: [],
      support_needs: [],
      environment_factors: [],
      participation_patterns: [],
    },
    parent_update: {
      todays_session: [],
      wins_today: [],
      helpful_supports: [],
      next_session: [],
    },
    clinical_summary: '',
    parent_summary: '',
    therapist_reflection: null,
    ai_metadata: {
      matched_goal_count: 0,
      suggested_goal_count: 0,
      rejected_matches: [],
      new_strategies: [],
      review_items: [],
      extraction_confidence: 0,
    },
  }
}

export function pendingReviewCount(session) {
  const pending = (session?.goals || []).filter((g) => g.status === 'pending').length
  const flagged = session?.ai_metadata?.review_items?.length || 0
  return pending + flagged
}

export function confirmedGoals(session) {
  return (session?.goals || []).filter((g) => g.status === 'confirmed' || g.status === 'changed')
}

export function updateGoal(session, index, patch) {
  const goals = [...(session.goals || [])]
  goals[index] = { ...goals[index], ...patch }
  return { ...session, goals }
}

export function toggleObservation(session, field, value) {
  const obs = { ...session.observations }
  const list = [...(obs[field] || [])]
  const idx = list.indexOf(value)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(value)
  obs[field] = list
  return { ...session, observations: obs }
}

export function pipelineStepIndex(phase) {
  const map = {
    transcribing: 0,
    identifying_goals: 1,
    matching_strategies: 2,
    identifying_observations: 3,
    creating_therapist_draft: 4,
    creating_parent_summary: 5,
    ready: 6,
    failed: -1,
  }
  return map[phase] ?? 0
}

/** AI-matched active/suggested IEP goals that still block submit while pending. */
export function aiMatchedGoals(session) {
  return (session?.goals || []).filter((g) => g.match_type !== 'new_observation')
}

/** Emerging goal candidates — never counted as IEP evidence. */
export function emergingGoals(session) {
  return (session?.goals || []).filter((g) => g.match_type === 'new_observation')
}

export function toggleResponseSignal(session, id) {
  const list = [...(session.child_response_signals || [])]
  const idx = list.indexOf(id)
  if (idx >= 0) list.splice(idx, 1)
  else list.push(id)
  return { ...session, child_response_signals: list }
}

export function updateChallenge(session, index, patch) {
  const list = [...(session.challenge_observations || [])]
  list[index] = { ...list[index], ...patch }
  return { ...session, challenge_observations: list }
}

export function removeChallenge(session, index) {
  const list = [...(session.challenge_observations || [])]
  list.splice(index, 1)
  return { ...session, challenge_observations: list }
}

export function addChallenge(session, text = '') {
  return {
    ...session,
    challenge_observations: [
      ...(session.challenge_observations || []),
      { text, source: 'therapist', flag_cm_review: false, incident_reported: false },
    ],
  }
}

/** Remove an emerging goal candidate from the draft entirely. */
export function dismissEmergingGoal(session, goal) {
  return { ...session, goals: (session.goals || []).filter((g) => g !== goal) }
}

/** Record that an emerging goal was sent to CM review (candidate id from API). */
export function markGoalCandidateSent(session, goal, candidate) {
  const goals = (session.goals || []).map((g) =>
    g === goal ? { ...g, candidate_id: candidate?.id ?? null, candidate_status: 'pending_review' } : g,
  )
  return {
    ...session,
    goals,
    goal_candidates: [
      ...(session.goal_candidates || []),
      { candidate_id: candidate?.id ?? null, label: goal.goal_label, status: 'pending_review' },
    ],
  }
}

export function markStrategyCandidateSent(session, label, candidate) {
  return {
    ...session,
    strategy_candidates: [
      ...(session.strategy_candidates || []),
      { candidate_id: candidate?.id ?? null, label, status: 'pending_review' },
    ],
  }
}

/**
 * All strategies mentioned today (goal-linked + session-level) with back-refs
 * so feedback edits update the canonical object.
 */
export function collectSessionStrategies(session) {
  const rows = []
  ;(session?.goals || []).forEach((goal, gi) => {
    if (goal.status === 'rejected') return
    ;(goal.strategies || []).forEach((s, si) => {
      rows.push({ ...s, _goalIndex: gi, _strategyIndex: si, _goalLabel: goal.goal_label })
    })
  })
  ;(session?.strategies_session_level || []).forEach((s, si) => {
    rows.push({ ...s, _goalIndex: null, _strategyIndex: si, _goalLabel: null })
  })
  return rows
}

export function updateStrategyRow(session, row, patch) {
  if (row._goalIndex != null) {
    const goals = [...(session.goals || [])]
    const goal = goals[row._goalIndex]
    const strategies = [...(goal.strategies || [])]
    strategies[row._strategyIndex] = { ...strategies[row._strategyIndex], ...patch }
    goals[row._goalIndex] = { ...goal, strategies }
    return { ...session, goals }
  }
  const list = [...(session.strategies_session_level || [])]
  list[row._strategyIndex] = { ...list[row._strategyIndex], ...patch }
  return { ...session, strategies_session_level: list }
}

export function updateStrategyFeedback(session, row, feedback) {
  return updateStrategyRow(session, row, { feedback })
}

/**
 * Recommended strategies — deterministic (Layer 1-3, no LLM): repo strategies
 * linked to confirmed goals but not used today. Max 2.
 */
export function recommendStrategies(session, repo, { max = 2 } = {}) {
  if (!repo?.strategies?.length) return []
  const usedLabels = new Set(
    collectSessionStrategies(session).map((s) => (s.strategy_label || '').toLowerCase()),
  )
  const dismissed = new Set((session.dismissed_recommendations || []).map((l) => l.toLowerCase()))
  const confirmedGoalIds = new Set(
    (session.goals || [])
      .filter((g) => g.status === 'confirmed' || g.status === 'changed')
      .map((g) => g.goal_card_id)
      .filter(Boolean),
  )
  const out = []
  for (const s of repo.strategies) {
    const label = (s.label || '').toLowerCase()
    if (!label || usedLabels.has(label) || dismissed.has(label)) continue
    if (s.goal_card_id && confirmedGoalIds.has(s.goal_card_id)) {
      out.push(s)
      if (out.length >= max) break
    }
  }
  return out
}

export function dismissRecommendation(session, label) {
  return {
    ...session,
    dismissed_recommendations: [...(session.dismissed_recommendations || []), label],
  }
}

export function saveRecommendationForNextSession(session, label) {
  return {
    ...session,
    next_session_strategy_notes: [...(session.next_session_strategy_notes || []), label],
  }
}

/** Deterministic therapist insights — cautious wording, no history claims. */
export function deriveSessionInsights(session) {
  const insights = []
  const strategies = collectSessionStrategies(session)
  const helpful = strategies.filter((s) => s.feedback === 'worked_well')
  const notHelpful = strategies.filter((s) => s.feedback === 'did_not_work')
  const partial = strategies.filter((s) => s.feedback === 'partially_worked')

  for (const s of helpful.slice(0, 2)) {
    insights.push(`${s.strategy_label} appeared helpful in this session.`)
  }
  for (const s of partial.slice(0, 1)) {
    insights.push(`${s.strategy_label} seemed partly helpful today — worth watching how it lands next time.`)
  }
  for (const s of notHelpful.slice(0, 2)) {
    insights.push(`${s.strategy_label} did not seem to help today. This is one session only — evidence is still limited.`)
  }

  const signals = session?.child_response_signals || []
  if (signals.includes('became_overwhelmed') && signals.includes('returned_after_regulation')) {
    insights.push('A pattern may be emerging: regulation support helped re-engagement today.')
  }
  if (signals.includes('requested_break')) {
    insights.push('Asking for a break is a self-advocacy strength worth reinforcing.')
  }

  const confirmed = (session?.goals || []).filter((g) => g.status === 'confirmed' || g.status === 'changed')
  if (confirmed.length === 0 && (session?.goals || []).length > 0) {
    insights.push('No goals confirmed yet — evidence for this session is still limited.')
  }

  const flagged = (session?.challenge_observations || []).filter((c) => c.flag_cm_review)
  if (flagged.length) {
    insights.push('A concern has been flagged — your case manager will review it with you.')
  }
  return insights
}

/** Items still requiring review before preview/submit. */
export function getDraftReviewItems(session) {
  const items = []
  const pendingAi = aiMatchedGoals(session).filter((g) => g.status === 'pending')
  for (const g of pendingAi) {
    items.push({ type: 'goal', label: `Confirm or reject: ${g.goal_label}` })
  }
  const confirmed = (session?.goals || []).filter((g) => g.status === 'confirmed' || g.status === 'changed')
  if (!pendingAi.length && !confirmed.length && !session?.no_goal_reason && !session?.todays_story?.trim()) {
    items.push({ type: 'story', label: 'Add what happened today or confirm a goal' })
  }
  return items
}

export function canSubmitVoiceDraft(session) {
  const pending = aiMatchedGoals(session).filter((g) => g.status === 'pending')
  if (pending.length) {
    return {
      ok: false,
      reason: `Let's resolve ${pending.length} AI-matched goal${pending.length > 1 ? 's' : ''} (confirm or reject) before submitting.`,
    }
  }
  const confirmed = (session?.goals || []).filter((g) => g.status === 'confirmed' || g.status === 'changed')
  if (!confirmed.length && !session?.no_goal_reason && !session?.todays_story?.trim()) {
    return {
      ok: false,
      reason: "Looks like we still need a few details — add what happened today, confirm a goal, or note why no IEP goal was addressed.",
    }
  }
  return { ok: true }
}
