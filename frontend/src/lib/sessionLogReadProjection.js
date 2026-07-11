/** Read-only helpers for structured session logs in list/detail views. */

import { CHILD_RESPONSE_SIGNALS } from './structuredSessionEvidence.js'

export function parseStructuredSessionJson(raw) {
  if (!raw) return null
  try {
    return typeof raw === 'string' ? JSON.parse(raw) : raw
  } catch {
    return null
  }
}

export function structuredReadSections(log) {
  const structured = parseStructuredSessionJson(log?.structured_session_json)
  if (!structured) return null

  const goals = (structured.goals || []).filter(
    (g) => g.status === 'confirmed' || g.status === 'changed' || g.status === 'edited_and_confirmed',
  )
  const signals = (structured.child_response_signals || []).map((id) => {
    const row = CHILD_RESPONSE_SIGNALS.find((s) => s.id === id)
    return row?.label || id.replace(/_/g, ' ')
  })
  const challenges = (structured.challenge_observations || [])
    .map((c) => c.text)
    .filter(Boolean)

  return {
    story: structured.todays_story || log?.activities_done || '',
    goals: goals.map((g) => ({
      label: g.goal_label,
      evidence: (g.evidence || []).join('; '),
    })),
    childResponse: signals,
    challenges,
    strengths: structured.observations?.strengths || [],
    reflection: log?.therapist_reflection || structured.therapist_reflection || '',
    parentSummary: structured.parent_summary || log?.parent_notes || '',
  }
}
