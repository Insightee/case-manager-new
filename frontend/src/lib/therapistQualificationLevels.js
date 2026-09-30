export const THERAPIST_QUALIFICATION_LEVELS = [
  { value: 'DIPLOMA', label: 'Diploma' },
  { value: 'UG', label: "UG (Bachelor's)" },
  { value: 'PG', label: "PG (Master's)" },
  { value: 'M_PHIL', label: 'M.Phil' },
  { value: 'PHD', label: 'PhD / Doctorate' },
  { value: 'PROFESSIONAL_REGISTRATION', label: 'Professional registration (e.g. RCI)' },
  { value: 'OTHER', label: 'Other' },
]

const LABEL_BY_VALUE = Object.fromEntries(THERAPIST_QUALIFICATION_LEVELS.map((row) => [row.value, row.label]))

export function qualificationLevelLabel(value) {
  if (!value) return null
  return LABEL_BY_VALUE[value] || value.replace(/_/g, ' ')
}

export const PROFILE_COMPLETION_FIELD_LABELS = {
  full_name: 'Full name',
  phone: 'Phone number',
  home_address: 'Home / base address',
  avatar: 'Profile photo',
  display_name: 'Display name',
  short_bio: 'Short bio',
  qualification_level: 'Highest qualification',
  services_offered: 'Services offered',
}
