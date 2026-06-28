/** Unified measurement enums — shared across IEP, session logs, monthly reports */

export const PARTICIPATION_OPTIONS = [
  { value: 'not_yet_participating', label: 'Not yet participating' },
  { value: 'emerging_participation', label: 'Emerging participation' },
  { value: 'participates_with_support', label: 'Participates with support' },
  { value: 'participates_consistently', label: 'Participates consistently' },
  { value: 'generalising_across_settings', label: 'Generalising across settings' },
]

export const INDEPENDENCE_OPTIONS = [
  { value: 'full_adult_support', label: 'Full adult support' },
  { value: 'frequent_support', label: 'Frequent support' },
  { value: 'moderate_support', label: 'Moderate support' },
  { value: 'minimal_support', label: 'Minimal support' },
  { value: 'independent_self_initiated', label: 'Independent / self-initiated' },
]

export const ACHIEVEMENT_OPTIONS = [
  { value: 'baseline', label: 'Baseline' },
  { value: 'emerging', label: 'Emerging' },
  { value: 'progressing', label: 'Progressing' },
  { value: 'achieved_familiar_setting', label: 'Achieved in familiar setting' },
  { value: 'achieved_across_settings', label: 'Achieved across settings' },
]

export const MEASUREMENT_DIMENSIONS = [
  { key: 'participation', label: 'Participation', options: PARTICIPATION_OPTIONS },
  { key: 'independence_support_needed', label: 'Independence / support needed', options: INDEPENDENCE_OPTIONS },
  { key: 'goal_achievement', label: 'Goal achievement', options: ACHIEVEMENT_OPTIONS },
]

export function labelForMeasurement(key, value) {
  const dim = MEASUREMENT_DIMENSIONS.find((d) => d.key === key)
  return dim?.options.find((o) => o.value === value)?.label || value || '—'
}
