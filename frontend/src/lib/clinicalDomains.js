/** 13 clinical domains — neuroaffirmative reporting model (shared across modules). */

export const CLINICAL_DOMAINS = [
  { id: 'strengths_interests', label: 'Strengths & Interests' },
  { id: 'autonomy_decision', label: 'Autonomy & Decision-Making' },
  { id: 'classroom_engagement', label: 'Classroom Engagement & Participation' },
  { id: 'peer_social', label: 'Peer Interactions & Social Connection' },
  { id: 'independence', label: 'Independence' },
  { id: 'communication_aac', label: 'Communication / AAC / Alternatives' },
  { id: 'emotional_regulation', label: 'Emotional Regulation & Coping' },
  { id: 'sense_of_self', label: 'Sense of Self / Confidence' },
  { id: 'academics_learning', label: 'Academics / Learning Engagement' },
  { id: 'environment_supports', label: 'Environment Supports' },
  { id: 'parent_inputs', label: 'Parent Inputs' },
  { id: 'school_inputs', label: 'School Inputs' },
  { id: 'therapist_notes', label: 'Therapist/Internal Notes', internalOnly: true },
]

export const NEUROAFFIRMATIVE_AVOID = [
  'non-compliant',
  'non compliant',
  'attention-seeking',
  'attention seeking',
  'manipulative',
  'lazy',
  'aggressive',
  'poor behaviour',
  'poor behavior',
  'refuses',
  'defiant',
]

export const NEUROAFFIRMATIVE_PREFER = [
  'benefits from',
  'needed more time and reassurance',
  'showed signs of overwhelm',
  'used movement to regulate',
  'communicated discomfort through',
  'support was needed during',
  'participation improved when',
  'responded well to',
  'self-advocacy',
  'access and participation',
  'regulation support',
  'environment support',
]

export function domainLabel(id) {
  return CLINICAL_DOMAINS.find((d) => d.id === id)?.label || id?.replace(/_/g, ' ') || 'Domain'
}

export function scanNeuroaffirmative(text) {
  if (!text || !String(text).trim()) return []
  const lower = String(text).toLowerCase()
  return NEUROAFFIRMATIVE_AVOID.filter((phrase) => lower.includes(phrase))
}

/** Map legacy observation checklist keys to clinical domains. */
export const OBSERVATION_KEY_TO_DOMAIN = {
  referral_context: 'strengths_interests',
  classroom_setting: 'environment_supports',
  social_communication: 'peer_social',
  academic_learning: 'academics_learning',
  behavior_regulation: 'emotional_regulation',
  motor_play: 'independence',
  summary_recommendations: 'therapist_notes',
}
