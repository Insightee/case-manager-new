/** 0–4 clinical measurement scales — shared with session log UI */

import { validateQuickEvidence } from './clinicalEvidenceFields.js'

export const PARTICIPATION_ANCHORS = {
  0: 'Not available',
  1: 'Observed only',
  2: 'Partial participation',
  3: 'Active participation with support',
  4: 'Independent / self-led participation',
}

export const INDEPENDENCE_ANCHORS = {
  0: 'Full support',
  1: 'High support',
  2: 'Moderate support',
  3: 'Light prompt',
  4: 'No support',
}

export const GOAL_ACHIEVEMENT_ANCHORS = {
  0: 'Not observed',
  1: 'Emerging',
  2: 'Attempted',
  3: 'Mostly achieved',
  4: "Achieved in today's context",
}

export const SESSION_LOG_SCORES = [
  { key: 'participation_score', label: 'Participation', anchors: PARTICIPATION_ANCHORS },
  { key: 'independence_score', label: 'Independence Level', anchors: INDEPENDENCE_ANCHORS },
  { key: 'goal_achievement_score', label: 'Goal Achievement', anchors: GOAL_ACHIEVEMENT_ANCHORS },
]

export const SCORE_DIMENSIONS = SESSION_LOG_SCORES

export const ACTIVITY_PHASES = [
  { key: 'initial', num: '01', label: 'Initial engagement activity', placeholder: 'Initial engagement activity…' },
  { key: 'core', num: '02', label: 'Core therapeutic task', placeholder: 'Core therapeutic task…' },
  { key: 'closing', num: '03', label: 'Transition / closing activity', placeholder: 'Transition / closing activity…' },
]

export const STRATEGY_FEEDBACK_OPTIONS = [
  { id: 'HELPFUL', label: 'Helpful' },
  { id: 'PARTLY_HELPFUL', label: 'Partly helpful' },
  { id: 'NOT_HELPFUL', label: 'Not helpful' },
  { id: 'CHILD_REJECTED', label: 'Child rejected' },
  { id: 'NEEDS_ADAPTATION', label: 'Needs adaptation' },
]

export const NEGATIVE_STRATEGY_FEEDBACK = new Set(['NOT_HELPFUL', 'CHILD_REJECTED', 'NEEDS_ADAPTATION'])

export function parseActivityPhases(raw) {
  if (!raw) return { initial: '', core: '', closing: '' }
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && ('initial' in parsed || 'core' in parsed)) {
      return {
        initial: parsed.initial || '',
        core: parsed.core || '',
        closing: parsed.closing || '',
      }
    }
  } catch {
    /* legacy plain text */
  }
  return { initial: String(raw || ''), core: '', closing: '' }
}

export function serializeActivityPhases(phases) {
  if (!phases) return ''
  const { initial = '', core = '', closing = '' } = phases
  if (!initial && !core && !closing) return ''
  return JSON.stringify({ initial, core, closing })
}

/** True when the therapist documented something for this goal this session. */
export function goalHasSessionWork(goal) {
  if (!goal) return false
  if (goal.marked_complete_today) return true
  const primary = (goal.strategies || [])[0]
  const hasScores = [goal.participation_score, goal.independence_score, goal.goal_achievement_score].some(
    (s) => s != null,
  )
  const hasStrategy =
    primary &&
    ((primary.strategy_label || '').trim() ||
      primary.strategy_feedback ||
      (primary.short_note || '').trim() ||
      (Array.isArray(primary.strategy_steps) && primary.strategy_steps.some(Boolean)))
  const hasNote = (primary?.short_note || goal.measurement_note || '').trim()
  const ext = goal.clinical_extension || {}
  const hasExtension =
    ext.child_response ||
    ext.therapist_interpretation ||
    ext.participation_quality ||
    ext.environment_fit ||
    (ext.barrier_type || []).length ||
    (ext.adaptation_type || []).length ||
    ext.strategy_status
  return hasScores || hasStrategy || Boolean(hasNote) || Boolean(hasExtension)
}

export function goalSessionStatus(goal) {
  if (goal?.marked_complete_today) return { label: 'Done today', tone: 'success', worked: true }
  if (!goalHasSessionWork(goal)) return { label: 'add', tone: 'muted', worked: false }
  const scores = [goal.participation_score, goal.independence_score, goal.goal_achievement_score]
  const filled = scores.filter((s) => s != null).length
  if (filled === 3) return { label: 'Done today', tone: 'success', worked: true }
  return { label: 'In progress', tone: 'progress', worked: true }
}

export function sessionLogProgressPct(goals) {
  const worked = (goals || []).filter(goalHasSessionWork)
  if (!worked.length) return 0
  const total = worked.reduce((sum, g) => {
    const filled = [g.participation_score, g.independence_score, g.goal_achievement_score].filter((s) => s != null).length
    return sum + filled / 3
  }, 0)
  return Math.round((total / worked.length) * 100)
}

export function emptyGoalEntry(iepGoal = null) {
  return {
    schema_version: 2,
    goal_card_id: iepGoal?.id || null,
    goal_label: iepGoal?.label || iepGoal?.goal_statement || '',
    domain_key: iepGoal?.domain_key || null,
    core_domains: iepGoal?.core_domains || [],
    core_environments: iepGoal?.core_environments || [],
    goal_description: iepGoal?.baseline || iepGoal?.why_it_matters || '',
    participation_score: null,
    independence_score: null,
    goal_achievement_score: null,
    activity_phases: { initial: '', core: '', closing: '' },
    activity_used: '',
    measurement_note: '',
    marked_complete_today: false,
    clinical_extension: {},
    strategies: [],
  }
}

export function emptyStrategyRow(goalCardId = null) {
  return {
    schema_version: 2,
    goal_card_id: goalCardId,
    strategy_id: null,
    strategy_label: '',
    strategy_steps: ['', '', ''],
    expected_outcome: '',
    strategy_feedback: null,
    short_note: '',
    activity_used: '',
    clinical_extension: {},
  }
}

export function normalizeGoalEntry(raw) {
  const phases = raw.activity_phases || parseActivityPhases(raw.activity_used)
  return {
    ...emptyGoalEntry(),
    ...raw,
    activity_phases: phases,
  }
}

export function prepareGoalForSubmit(goal) {
  const primary = (goal.strategies || [])[0]
  const stepParts = (primary?.strategy_steps || []).filter(Boolean)
  const stepSummary = stepParts.join(' · ')
  const phases = goal.activity_phases || parseActivityPhases(goal.activity_used)
  const serialized = serializeActivityPhases(phases)
  const legacySummary = [phases.initial, phases.core, phases.closing].filter(Boolean).join(' · ')
  const activityUsed = stepSummary || serialized || goal.activity_used || legacySummary
  const note = primary?.short_note || goal.measurement_note || stepSummary || legacySummary
  const goalExt = { ...(goal.clinical_extension || {}) }
  const stratExt = primary?.clinical_extension || {}
  const clinical_extension = {
    ...goalExt,
    ...stratExt,
    field_provenance: { ...(goalExt.field_provenance || {}), ...(stratExt.field_provenance || {}) },
  }
  const preparedGoal = {
    ...goal,
    activity_used: activityUsed,
    measurement_note: note,
    clinical_extension,
  }
  if (primary) {
    preparedGoal.strategies = [
      {
        ...primary,
        clinical_extension: stratExt,
        activity_used: primary.activity_used || activityUsed,
      },
    ]
  }
  return preparedGoal
}

/** Returns friendly message if quick evidence incomplete for worked goals */
export function validateSessionEvidenceQuickFields(evidence) {
  const goals = (evidence?.goals || []).filter(goalHasSessionWork)
  for (const g of goals) {
    const gaps = validateQuickEvidence(g.clinical_extension || {})
    if (gaps.length) {
      const label = g.goal_label || 'A goal'
      if (gaps.includes('child_response')) {
        return `${label}: add how the child responded — it helps the team learn what supports participation.`
      }
      if (gaps.includes('next_step')) {
        return `${label}: add a next step so we know what to try next.`
      }
    }
  }
  return null
}
