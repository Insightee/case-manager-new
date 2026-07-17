export const MEETING_TYPES = [
  { value: 'OBSERVATION_REVIEW', label: 'Observation review' },
  { value: 'OBSERVATION_CHECKLIST_REVIEW', label: 'Observation checklist review' },
  { value: 'IEP_MEETING', label: 'IEP meeting' },
  { value: 'MONTHLY_REPORT_REVIEW', label: 'Monthly report review' },
  { value: 'PROGRESS_REVIEW', label: 'Progress review' },
  { value: 'PARENT_MEETING', label: 'Parent meeting' },
  { value: 'SCHOOL_MEETING', label: 'School meeting' },
  { value: 'THERAPIST_SUPPORT', label: 'Therapist support' },
  { value: 'MENTOR_REVIEW', label: 'Mentor review' },
  { value: 'INCIDENT_REVIEW', label: 'Incident review' },
  { value: 'SUPPORT_TICKET_REVIEW', label: 'Support ticket review' },
  { value: 'ADMINISTRATIVE_MEETING', label: 'Administrative meeting' },
  { value: 'TRANSITION_PLANNING', label: 'Transition planning' },
  { value: 'CASE_CLOSURE_MEETING', label: 'Case closure meeting' },
  { value: 'OTHER', label: 'Other (specify below)' },
]

export const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

export const TYPE_FILTER_OPTIONS = [
  { value: '', label: 'All types' },
  ...MEETING_TYPES,
]

export const MONTH_FILTER_OPTIONS = [
  { value: '', label: 'All months' },
  { value: '1', label: 'January' },
  { value: '2', label: 'February' },
  { value: '3', label: 'March' },
  { value: '4', label: 'April' },
  { value: '5', label: 'May' },
  { value: '6', label: 'June' },
  { value: '7', label: 'July' },
  { value: '8', label: 'August' },
  { value: '9', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
]

export const ATTENDEE_ROLE_LABELS = {
  client: 'Client (parent)',
  therapist: 'Therapist',
  case_manager: 'Case manager',
  admin: 'Admin',
}

export const STATUS_LABELS = {
  SCHEDULED: { label: 'Scheduled', bg: '#dbeafe', color: '#1e40af' },
  COMPLETED: { label: 'Completed', bg: '#dcfce7', color: '#14532d' },
  CANCELLED: { label: 'Cancelled', bg: '#fee2e2', color: '#991b1b' },
  RESCHEDULED: { label: 'Rescheduled', bg: '#f3e8ff', color: '#6b21a8' },
}

export const SEARCH_DEBOUNCE_MS = 350

export const MODAL_INPUT_STYLE = {
  display: 'block',
  width: '100%',
  border: '1px solid #e2e8f0',
  borderRadius: 10,
  padding: '8px 10px',
  fontSize: '0.875rem',
  marginTop: 4,
  boxSizing: 'border-box',
}

export const MODAL_LABEL_STYLE = {
  fontSize: '0.875rem',
  fontWeight: 500,
  color: '#475569',
  display: 'block',
  marginBottom: 12,
}
