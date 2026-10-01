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

export const PROFILE_COMPLETION_FIELD_ORDER = [
  'full_name',
  'phone',
  'home_address',
  'avatar',
  'display_name',
  'short_bio',
  'qualification_level',
  'services_offered',
]

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

/** Maps completion field keys to profile page section element ids. */
export const PROFILE_COMPLETION_SECTION_IDS = {
  full_name: 'therapist-profile-contact',
  phone: 'therapist-profile-contact',
  home_address: 'therapist-profile-contact',
  avatar: 'therapist-profile-avatar',
  display_name: 'therapist-profile-service',
  short_bio: 'therapist-profile-service',
  qualification_level: 'therapist-profile-service',
  services_offered: 'therapist-profile-service',
}

export const PROFILE_COMPLETION_ACCOUNT_FIELDS = new Set(['full_name', 'phone', 'home_address'])

export const PROFILE_COMPLETION_SERVICE_FIELDS = new Set([
  'display_name',
  'short_bio',
  'qualification_level',
  'services_offered',
])

export function orderedMissingFields(missingFields) {
  const missing = new Set(missingFields || [])
  return PROFILE_COMPLETION_FIELD_ORDER.filter((key) => missing.has(key))
}
