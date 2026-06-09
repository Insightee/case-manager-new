/** Human labels for case product modules (shared across therapist/admin UI). */

export const MODULE_LABELS = {
  homecare: 'Homecare',
  shadow_support: 'Shadow support',
  counselling: 'Counselling',
  special_education: 'Special education',
  behaviour_therapy: 'Behaviour therapy',
  tutoring: 'Tutoring',
  other: 'Other',
}

export function moduleLabel(key) {
  if (!key) return null
  return MODULE_LABELS[key] || String(key).replace(/_/g, ' ')
}
