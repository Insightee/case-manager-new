/**
 * Map voice extraction / API structured_session onto frontend state.
 */

import {
  canSubmitVoiceDraft,
  emptyStructuredSession,
  inferResponseSignals,
} from './structuredSessionEvidence.js'
import { repoGoalToSessionEntry } from './sessionLogGoals.js'

export function extractionToStructuredSession(extraction, { sessionId, recordingId, transcript, extractionVersion } = {}) {
  if (!extraction && !transcript) {
    return emptyStructuredSession({ sessionId, recordingId })
  }
  const base = emptyStructuredSession({ sessionId, recordingId })
  base.extraction_version = extractionVersion ?? extraction?.schema_version ?? null
  if (transcript) {
    base.voice_transcript = transcript
    if (!extraction) {
      base.todays_story = transcript.slice(0, 2000)
      return base
    }
  }

  base.todays_story = extraction.session_summary || transcript?.slice(0, 2000) || ''
  base.clinical_summary = extraction.internal_note_candidate || extraction.session_summary || ''
  base.parent_summary = extraction.parent_note_draft || extraction.session_summary || ''

  const strategiesByGoal = {}
  for (const strat of extraction.strategies || []) {
    const item = {
      strategy_id: strat.strategy_id || null,
      strategy_label: strat.strategy_label || strat.strategy_candidate_label || '',
      feedback: strat.strategy_feedback || null,
      confidence: strat.match_confidence || 0,
      spoken_phrase: strat.spoken_phrase || strat.implementation_summary || '',
    }
    if (strat.goal_index != null && strat.goal_index < (extraction.goal_evidence || []).length) {
      strategiesByGoal[strat.goal_index] = [...(strategiesByGoal[strat.goal_index] || []), item]
    } else {
      base.strategies_session_level.push(item)
    }
  }

  let matched = 0
  let suggested = 0
  base.goals = (extraction.goal_evidence || []).map((goal, idx) => {
    let match_type = 'suggested'
    if (goal.goal_card_id) {
      match_type = 'active_iep'
      matched += 1
    } else if (goal.goal_candidate_label) {
      match_type = 'new_observation'
    } else {
      suggested += 1
    }
    const progress = [goal.participation, goal.goal_achievement].filter(Boolean)
    const evidence = [goal.evidence_summary, goal.child_response].filter(Boolean).map((s) => s.slice(0, 200))
    return {
      goal_id: goal.goal_card_id,
      goal_card_id: goal.goal_card_id,
      goal_repository_item_id: goal.goal_repository_item_id,
      goal_label: goal.goal_label || goal.goal_candidate_label || '',
      match_type,
      match_label: goal.match_label || null,
      source_type: goal.source_type || null,
      confidence: goal.confidence ?? 0,
      status: 'pending',
      source_transcript_excerpt: goal.source_transcript_excerpt || goal.evidence_summary?.slice(0, 500) || '',
      strategies: strategiesByGoal[idx] || [],
      progress,
      evidence,
      participation: goal.participation || null,
      independence_support_needed: goal.independence_support_needed || null,
      goal_achievement: goal.goal_achievement || null,
    }
  })

  base.child_response_signals = inferResponseSignals(
    [extraction.child_response_summary, extraction.session_summary, transcript].filter(Boolean).join(' '),
  )

  if (extraction.barriers_or_concerns) {
    base.challenge_observations = extraction.barriers_or_concerns
      .split(/\n+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 3)
      .map((text) => ({ text, source: 'ai', flag_cm_review: false, incident_reported: false }))
  }

  if (extraction.child_response_summary) {
    base.observations.strengths = [extraction.child_response_summary.slice(0, 300)]
  }
  if (extraction.progress_summary) {
    base.parent_update.wins_today = [extraction.progress_summary.slice(0, 300)]
  }
  if (extraction.parent_note_draft) {
    base.parent_update.todays_session = extraction.parent_note_draft
      .split(/[\n•]/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, 5)
  }
  if (extraction.next_session_plan) {
    base.parent_update.next_session = [extraction.next_session_plan.slice(0, 300)]
  }
  base.parent_update.helpful_supports = (extraction.strategies || [])
    .map((s) => s.strategy_label)
    .filter(Boolean)
    .slice(0, 4)

  base.ai_metadata = {
    matched_goal_count: matched,
    suggested_goal_count: suggested,
    rejected_matches: [],
    new_strategies: (extraction.strategies || [])
      .filter((s) => !s.strategy_id)
      .map((s) => s.strategy_label)
      .filter(Boolean),
    review_items: extraction.review_flags || extraction.missing_information || [],
    extraction_confidence:
      base.goals.length > 0
        ? base.goals.reduce((a, g) => a + (g.confidence || 0), 0) / base.goals.length
        : 0,
  }

  base.session_insights = (extraction.session_insights || []).map((item) => ({
    insight_type: item.insight_type,
    title: item.title,
    summary: item.summary,
    certainty: item.certainty || 'single_session_signal',
  }))

  if (extraction.family_summary) {
    const fs = extraction.family_summary
    if (fs.worked_on?.length && !base.parent_update.todays_session.length) {
      base.parent_update.todays_session = fs.worked_on.slice(0, 5)
    }
    if (fs.appeared_helpful?.length && !base.parent_update.helpful_supports.length) {
      base.parent_update.helpful_supports = fs.appeared_helpful.slice(0, 4)
    }
    if (fs.strength_highlight?.length && !base.parent_update.wins_today.length) {
      base.parent_update.wins_today = fs.strength_highlight.slice(0, 3)
    }
    if (fs.looking_ahead?.length && !base.parent_update.next_session.length) {
      base.parent_update.next_session = fs.looking_ahead.slice(0, 3)
    }
  }

  if (extraction.participation_signals?.length) {
    for (const sig of extraction.participation_signals) {
      if (sig.signal_id && !base.child_response_signals.includes(sig.signal_id)) {
        base.child_response_signals.push(sig.signal_id)
      }
    }
  }
  if (extraction.strengths?.length) {
    for (const s of extraction.strengths) {
      if (s.label && !base.observations.strengths.includes(s.label)) {
        base.observations.strengths.push(s.label.slice(0, 300))
      }
    }
  }
  if (extraction.support_signals?.length) {
    base.support_signals = extraction.support_signals.map((s) => ({
      label: s.label || '',
      support_type: s.support_type || 'accommodation',
      evidence: s.evidence || '',
    }))
  }

  return base
}

/** Merge API structured_session from status poll (preferred when present). */
export function normalizeStructuredSession(raw, fallback) {
  if (raw && raw.schema_version) {
    const base = emptyStructuredSession()
    return {
      ...base,
      ...raw,
      session_context: { ...base.session_context, ...(raw.session_context || {}) },
      observations: { ...base.observations, ...(raw.observations || {}) },
      parent_update: { ...base.parent_update, ...(raw.parent_update || {}) },
      ai_metadata: { ...base.ai_metadata, ...(raw.ai_metadata || {}) },
    }
  }
  return fallback
}

/**
 * Adapt a legacy prose-only daily log into the structured draft so
 * edit/resubmit always opens the canonical editor. No fabricated evidence:
 * prose lands in story/summaries only.
 */
export function legacyLogToStructuredSession(log, { sessionId } = {}) {
  const base = emptyStructuredSession({ sessionId: sessionId ?? log?.session_id })
  base.todays_story = log?.activities_done || log?.session_notes || ''
  base.clinical_summary = log?.session_notes || ''
  base.parent_summary = log?.parent_notes || ''
  base.therapist_reflection = log?.therapist_reflection || null
  if (log?.observations) {
    base.challenge_observations = []
    base.observations.participation_patterns = [String(log.observations).slice(0, 300)]
  }
  if (log?.follow_ups) {
    base.parent_update.next_session = [String(log.follow_ups).slice(0, 300)]
  }
  base.story_edited_by_therapist = true
  return base
}

export function structuredSessionToSubmitBody(session, { attendanceStatus = 'PRESENT', lateReason } = {}) {
  const gate = canSubmitVoiceDraft(session)
  if (!gate.ok) return { error: gate.reason }
  const body = {
    attendance_status: attendanceStatus,
    structured_session_json: { ...session, goals: session.goals },
    therapist_reflection: session.therapist_reflection || undefined,
    recording_id: session.recording_id || undefined,
  }
  if (lateReason) body.late_reason = lateReason
  return { body }
}

export function addGoalFromRepo(session, repoGoal) {
  const entry = repoGoalToSessionEntry(repoGoal, session.goals.length)
  return {
    ...session,
    goals: [
      ...session.goals,
      {
        goal_id: entry.goal_card_id,
        goal_card_id: entry.goal_card_id,
        goal_repository_item_id: entry.goal_repository_item_id,
        goal_label: entry.goal_label,
        match_type: 'active_iep',
        confidence: 1,
        status: 'confirmed',
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

/** Keep for typed fallback only. */
export function extractionToFormFields(extraction) {
  if (!extraction) return {}
  const fields = {}
  if (extraction.session_summary) fields.activities_done = extraction.session_summary
  const labels = (extraction.goal_evidence || []).map((g) => g.goal_label).filter(Boolean)
  if (labels.length) fields.goals_addressed = labels.join('; ')
  const observations = [extraction.child_response_summary, extraction.progress_summary]
    .filter(Boolean)
    .join('\n\n')
  if (observations) fields.observations = observations
  if (extraction.next_session_plan) fields.follow_ups = extraction.next_session_plan
  if (extraction.parent_note_draft) fields.parent_notes = extraction.parent_note_draft
  if (extraction.internal_note_candidate) fields.session_notes = extraction.internal_note_candidate
  return fields
}

export { extractionToSessionEvidence } from './voiceExtractionMapperLegacy.js'
