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

/** Honest three-stage processing copy for Voice Session Log V2. */
export const PROCESSING_STEPS_V2 = [
  { id: 'transcribing', label: 'Transcribing voice note' },
  { id: 'organising_evidence', label: 'Organising session evidence' },
  { id: 'preparing_review', label: 'Preparing your review' },
]

export const MATCH_LABEL_DISPLAY = {
  strong_possible_match: 'Strong possible match',
  possible_match: 'Possible match',
  needs_review: 'Needs review',
}

export function matchLabelFromConfidence(goal) {
  if (goal?.match_label && MATCH_LABEL_DISPLAY[goal.match_label]) {
    return MATCH_LABEL_DISPLAY[goal.match_label]
  }
  if (goal?.match_type === 'new_observation') return MATCH_LABEL_DISPLAY.needs_review
  const c = goal?.confidence ?? 0
  if (goal?.goal_card_id && c >= 0.75) return MATCH_LABEL_DISPLAY.strong_possible_match
  if (goal?.goal_card_id && c >= 0.5) return MATCH_LABEL_DISPLAY.possible_match
  return MATCH_LABEL_DISPLAY.needs_review
}

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
    session_insights: [],
    support_signals: [],
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

export function pipelineStepIndex(phase, { version = 'v1' } = {}) {
  if (version === 'v2') {
    const v2 = {
      transcribing: 0,
      organising_evidence: 1,
      preparing_review: 2,
      ready: 3,
      failed: -1,
    }
    return v2[phase] ?? 0
  }
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

/** Active session goals vs IEP goals not yet added to this log. */
export function buildIepGoalReviewList(repo, session) {
  const iepGoals = repo?.goals || []
  const active = aiMatchedGoals(session)
  const inSessionById = new Set(active.map((g) => g.goal_card_id).filter(Boolean))
  const inSessionByLabel = new Set(active.map((g) => (g.goal_label || '').toLowerCase()).filter(Boolean))
  const available = []
  for (const rg of iepGoals) {
    const labelKey = (rg.label || '').trim().toLowerCase()
    if (!labelKey) continue
    if (rg.goal_card_id && inSessionById.has(rg.goal_card_id)) continue
    if (inSessionByLabel.has(labelKey)) continue
    available.push(rg)
  }
  return { active, available }
}

/** Therapist selects an IEP goal not mentioned in the recording. */
export function selectIepGoalForSession(session, repoGoal) {
  const label = (repoGoal.label || '').trim()
  if (!label) return session
  const exists = (session.goals || []).some(
    (g) =>
      g.match_type !== 'new_observation' &&
      ((repoGoal.goal_card_id && g.goal_card_id === repoGoal.goal_card_id) ||
        (g.goal_label || '').toLowerCase() === label.toLowerCase()),
  )
  if (exists) return session
  return {
    ...session,
    goals: [
      ...(session.goals || []),
      {
        goal_id: repoGoal.goal_card_id || null,
        goal_card_id: repoGoal.goal_card_id || null,
        goal_label: label,
        match_type: 'active_iep',
        confidence: 1,
        status: 'pending',
        manually_selected: true,
        source_transcript_excerpt: '',
        strategies: [],
        progress: [],
        evidence: [],
        participation: null,
        independence_support_needed: null,
        goal_achievement: null,
      },
    ],
  }
}

const ENV_BARRIER_KEYWORDS = [
  'noise',
  'lighting',
  'crowded',
  'classroom',
  'home environment',
  'environment',
  'sensory',
  'transition space',
  'schedule change',
  'unfamiliar',
]

const CHILD_BARRIER_KEYWORDS = [
  'meltdown',
  'refusal',
  'overwhelm',
  'anxiety',
  'behavior',
  'regulation',
  'distress',
  'shutdown',
  'dysregulation',
]

export function getChallengeContext(session) {
  const obs = session?.challenge_observations?.[0]
  const text = obs?.text || ''
  const hay = text.toLowerCase()
  return {
    text,
    environment: ENV_BARRIER_KEYWORDS.some((k) => hay.includes(k)),
    childLevel: CHILD_BARRIER_KEYWORDS.some((k) => hay.includes(k)),
    aiSuggested: obs?.source === 'ai',
    flagCm: Boolean(obs?.flag_cm_review),
  }
}

/** Keyword → strength inference from transcript (Layer 1, deterministic). */
const STRENGTH_INFERENCE = [
  { words: ['persist', 'persever', 'kept trying', 'did not give up'], tag: 'Persistence' },
  { words: ['calm', 'regulated', 'regulation', 'settled'], tag: 'Self-regulation' },
  { words: ['initiat', 'asked for', 'self-advoc', 'requested'], tag: 'Self-advocacy' },
  { words: ['engag', 'participat', 'focused', 'stayed with'], tag: 'Engagement' },
  { words: ['joy', 'smil', 'laugh', 'enjoy', 'happy'], tag: 'Shared joy' },
  { words: ['break', 'pause', 'stepped away'], tag: 'Self-awareness' },
  { words: ['helped', 'support', 'together', 'turn-taking'], tag: 'Connection' },
  { words: ['try', 'attempt', 'practice'], tag: 'Willingness to try' },
]

export function inferStrengthKeywords(text) {
  const hay = String(text || '').toLowerCase()
  if (!hay) return []
  const found = []
  for (const { words, tag } of STRENGTH_INFERENCE) {
    if (words.some((w) => hay.includes(w)) && !found.includes(tag)) found.push(tag)
  }
  return found.slice(0, 8)
}

export function hydrateStrengthKeywords(session) {
  const existing = strengthKeywords(session)
  const inferred = inferStrengthKeywords(
    [session.voice_transcript, session.todays_story, session.clinical_summary].filter(Boolean).join(' '),
  )
  const merged = [...existing]
  for (const k of inferred) {
    if (!merged.includes(k)) merged.push(k)
  }
  if (merged.length === existing.length) return session
  return setStrengthKeywords(session, merged)
}

export function strengthKeywords(session) {
  const raw = session?.observations?.strengths || []
  const out = []
  for (const item of raw) {
    String(item)
      .split(/[,;•\n]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .forEach((k) => {
        const word = k.slice(0, 80)
        if (!out.includes(word)) out.push(word)
      })
  }
  return out.slice(0, 12)
}

export function setStrengthKeywords(session, keywords) {
  return {
    ...session,
    observations: {
      ...session.observations,
      strengths: (keywords || []).map((k) => String(k).trim()).filter(Boolean).slice(0, 12),
    },
  }
}

export function addStrengthKeyword(session, keyword) {
  const k = String(keyword || '').trim().slice(0, 80)
  if (!k) return session
  const next = [...strengthKeywords(session)]
  if (!next.includes(k)) next.push(k)
  return setStrengthKeywords(session, next)
}

export function removeStrengthKeyword(session, keyword) {
  return setStrengthKeywords(
    session,
    strengthKeywords(session).filter((k) => k !== keyword),
  )
}

export function participationSignalsForDisplay(session) {
  return (session?.child_response_signals || []).map((id) => ({
    id,
    label: responseSignalLabel(id),
  }))
}

export function addParticipationSignal(session, id) {
  if (!id || (session.child_response_signals || []).includes(id)) return session
  return { ...session, child_response_signals: [...(session.child_response_signals || []), id] }
}

export function removeParticipationSignal(session, id) {
  return {
    ...session,
    child_response_signals: (session.child_response_signals || []).filter((x) => x !== id),
  }
}

export function availableParticipationSignals(session) {
  const selected = new Set(session?.child_response_signals || [])
  return CHILD_RESPONSE_SIGNALS.filter((s) => !selected.has(s.id))
}

function planStrategyMatches(plan, row) {
  if (!row) return false
  if (plan.strategy_id && row.strategy_id && plan.strategy_id === row.strategy_id) return true
  return (plan.label || '').toLowerCase() === (row.strategy_label || '').toLowerCase()
}

/** Case-plan strategies + session-only uses for the review UI. */
export function buildPlanStrategyCards(repo, session) {
  const used = collectSessionStrategies(session)
  const plan = repo?.strategies || []
  const cards = []
  const matchedLabels = new Set()

  for (const p of plan) {
    const row = used.find((u) => planStrategyMatches(p, u))
    if (row) matchedLabels.add((row.strategy_label || '').toLowerCase())
    cards.push({ kind: 'plan', plan: p, row: row || null })
  }

  for (const row of used) {
    const labelKey = (row.strategy_label || '').toLowerCase()
    const inPlan = plan.some((p) => planStrategyMatches(p, row))
    if (!inPlan) cards.push({ kind: 'other', row })
  }

  return cards
}

export function ensurePlanStrategyRow(session, planStrategy, patch = {}) {
  const used = collectSessionStrategies(session)
  const existing = used.find((u) => planStrategyMatches(planStrategy, u))
  if (existing) return updateStrategyRow(session, existing, patch)
  const phrase = patch.spoken_phrase || patch.implementation_summary || ''
  const item = {
    strategy_id: planStrategy.strategy_id || null,
    strategy_label: planStrategy.label,
    spoken_phrase: phrase,
    child_response_note: phrase,
    implementation_summary: phrase,
    from_case_plan: true,
  }
  return { ...session, strategies_session_level: [...(session.strategies_session_level || []), item] }
}

export function addCustomSessionStrategy(session, { label, brief, steps = [] }) {
  const name = String(label || '').trim()
  if (!name) return session
  const phrase = String(brief || '').trim()
  const item = {
    strategy_id: null,
    strategy_label: name,
    spoken_phrase: phrase,
    child_response_note: phrase,
    strategy_brief: phrase,
    strategy_steps: (steps || []).map((s) => String(s).trim()).filter(Boolean).slice(0, 5),
    is_custom: true,
  }
  return { ...session, strategies_session_level: [...(session.strategies_session_level || []), item] }
}

export function removeSessionStrategyRow(session, row) {
  if (row._goalIndex != null) {
    const goals = [...(session.goals || [])]
    const goal = goals[row._goalIndex]
    const strategies = [...(goal.strategies || [])]
    strategies.splice(row._strategyIndex, 1)
    goals[row._goalIndex] = { ...goal, strategies }
    return { ...session, goals }
  }
  const list = [...(session.strategies_session_level || [])]
  list.splice(row._strategyIndex, 1)
  return { ...session, strategies_session_level: list }
}

export function linkSessionStrategyToRepo(session, row, repoStrategy) {
  return updateStrategyRow(session, row, {
    strategy_id: repoStrategy.strategy_id || repoStrategy.id || null,
    strategy_label: repoStrategy.label,
    from_case_plan: true,
  })
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

export function setChallengeSummary(session, text) {
  const trimmed = String(text || '').trim()
  if (!trimmed) {
    return { ...session, challenge_observations: [] }
  }
  const prev = session.challenge_observations?.[0] || {}
  const edited = trimmed !== (prev.text || '')
  return {
    ...session,
    challenge_observations: [
      {
        text: trimmed,
        source: edited ? 'therapist' : prev.source || 'therapist',
        flag_cm_review: Boolean(prev.flag_cm_review),
        incident_reported: Boolean(prev.incident_reported),
      },
    ],
  }
}

export function getChallengeSummary(session) {
  return (session.challenge_observations || [])
    .map((e) => e.text)
    .filter(Boolean)
    .join('\n\n')
}

export function updateChallengeFlags(session, patch) {
  const text = getChallengeSummary(session)
  if (!text) return session
  const prev = session.challenge_observations?.[0] || { text, source: 'therapist' }
  return {
    ...session,
    challenge_observations: [{ ...prev, ...patch, text }],
  }
}

/** Parent-safe preview from confirmed evidence only. */
export function buildFamilyPreview(session) {
  const confirmed = confirmedGoals(session)
  const worked_on = confirmed.map((g) => g.goal_label).filter(Boolean)
  if (!worked_on.length && session.todays_story?.trim()) {
    worked_on.push(session.todays_story.trim().slice(0, 220))
  }

  const appeared_helpful = collectSessionStrategies(session)
    .filter((s) => s.feedback === 'worked_well' || s.feedback === 'partially_worked')
    .map((s) => s.strategy_label)
    .filter(Boolean)
    .slice(0, 4)

  const strength_highlight = []
  for (const id of session.child_response_signals || []) {
    strength_highlight.push(responseSignalLabel(id))
  }
  for (const s of session.observations?.strengths || []) {
    if (s && !strength_highlight.includes(s)) strength_highlight.push(s)
  }

  const looking_ahead = [...(session.parent_update?.next_session || [])].filter(Boolean).slice(0, 3)

  return {
    worked_on: worked_on.slice(0, 5),
    appeared_helpful,
    strength_highlight: strength_highlight.slice(0, 3),
    looking_ahead,
  }
}

/** Sync editable family preview fields back onto parent_update. */
export function applyFamilyPreviewEdits(session, preview) {
  return {
    ...session,
    parent_update: {
      ...session.parent_update,
      todays_session: preview.worked_on || [],
      helpful_supports: preview.appeared_helpful || [],
      wins_today: preview.strength_highlight || [],
      next_session: preview.looking_ahead || [],
    },
    parent_summary: [
      ...(preview.worked_on || []),
      ...(preview.strength_highlight || []),
    ]
      .filter(Boolean)
      .join(' ')
      .slice(0, 2000),
  }
}

export function updateFamilyPreviewLine(session, field, index, value) {
  const preview = buildFamilyPreview(session)
  const key =
    field === 'worked_on'
      ? 'worked_on'
      : field === 'appeared_helpful'
        ? 'appeared_helpful'
        : field === 'strength_highlight'
          ? 'strength_highlight'
          : 'looking_ahead'
  const list = [...(preview[key] || [])]
  list[index] = value
  preview[key] = list
  return applyFamilyPreviewEdits(session, preview)
}

export const INSIGHT_CERTAINTY_LABELS = {
  single_session_signal: 'Single-session signal',
  early_pattern: 'Early pattern',
  repeated_pattern: 'Repeated pattern',
  insufficient_evidence: 'Insufficient evidence',
}

export const DRAFT_SECTION_IDS = [
  'story',
  'goals',
  'emerging',
  'strategies',
  'participation',
  'challenges',
  'clinical_brain',
  'reflection',
]

export function getReviewSummary(session) {
  const pendingGoals = aiMatchedGoals(session).filter((g) => g.status === 'pending').length
  const strategies = collectSessionStrategies(session).length
  const participationSignals = (session.child_response_signals || []).length
  const strengths = (session.observations?.strengths || []).length
  const challenges = (session.challenge_observations || []).filter((c) => c.text?.trim()).length
  const family = buildFamilyPreview(session)
  const familyUpdatePending =
    family.worked_on.length === 0 && family.strength_highlight.length === 0 && !session.parent_summary?.trim()

  return {
    pendingGoals,
    strategies,
    participationSignals,
    strengths,
    challenges,
    familyUpdatePending,
    hasUnresolved: getDraftReviewItems(session).length > 0,
  }
}

function _goalSectionSummary(session) {
  const pending = aiMatchedGoals(session).filter((g) => g.status === 'pending').length
  const confirmed = confirmedGoals(session).length
  if (pending) return `${confirmed} confirmed · ${pending} needs review`
  if (confirmed) return `${confirmed} confirmed`
  if (session.no_goal_reason) return 'No IEP goal today — reason noted'
  return 'Confirm goals or note why none were addressed'
}

export function getDraftSectionMeta(session) {
  const pendingGoals = aiMatchedGoals(session).filter((g) => g.status === 'pending').length
  const emerging = emergingGoals(session).length
  const strategies = collectSessionStrategies(session).length
  const signals = (session.child_response_signals || []).length
  const strengths = (session.observations?.strengths || []).length
  const challengeText = getChallengeSummary(session)

  const storyOk = Boolean(session.todays_story?.trim())
  const confirmedCount = confirmedGoals(session).length
  const goalsResolved = pendingGoals === 0 && (confirmedCount > 0 || session.no_goal_reason || storyOk)

  return {
    story: {
      status: storyOk ? 'confirmed' : 'needs_review',
      summary: storyOk ? 'Narrative drafted' : 'Add what happened today',
    },
    goals: {
      status: goalsResolved ? 'confirmed' : 'needs_review',
      summary: _goalSectionSummary(session),
    },
    emerging: {
      status: emerging ? 'optional' : 'empty',
      summary: emerging ? `${emerging} candidate${emerging > 1 ? 's' : ''} · confirm to send to CM` : 'None suggested',
    },
    strategies: {
      status: strategies ? 'confirmed' : 'optional',
      summary: strategies ? `${strategies} noted` : 'Optional',
    },
    participation: {
      status: signals || strengths ? 'confirmed' : 'optional',
      summary:
        signals || strengths
          ? `${signals} participation · ${strengths} strength${strengths === 1 ? '' : 's'}`
          : 'Optional',
    },
    challenges: {
      status: challengeText ? 'confirmed' : 'optional',
      summary: challengeText ? 'Summary added' : 'Optional',
    },
    clinical_brain: {
      status: 'optional',
      summary: (session.session_insights?.length || deriveSessionInsights(session).length)
        ? 'Review insights'
        : 'Available after you confirm evidence',
    },
    reflection: {
      status: session.therapist_reflection?.trim() ? 'confirmed' : 'optional',
      summary: session.therapist_reflection?.trim() ? 'Added' : 'Optional · internal only',
    },
  }
}

export function findFirstUnresolvedSectionId(session) {
  const meta = getDraftSectionMeta(session)
  for (const id of DRAFT_SECTION_IDS) {
    if (meta[id]?.status === 'needs_review') return id
  }
  return 'story'
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
