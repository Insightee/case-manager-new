export const CASE_DOCUMENT_CATEGORIES = [
  { value: 'OBSERVATION_REPORT', label: 'Observation report' },
  { value: 'CASE_MANAGER_MEETING_REPORT', label: 'Case manager meeting report' },
  { value: 'CLIENT_MONTHLY_REPORT', label: 'Client monthly report' },
  { value: 'MONTHLY_PROGRESS_REPORT', label: 'Monthly progress report' },
  { value: 'IEP_PLAN', label: 'IEP plan' },
  { value: 'INCIDENT_REPORT', label: 'Incident report' },
  { value: 'TERMINATION_PROGRESS_REPORT', label: 'Termination progress report' },
  { value: 'ANNUAL_PROGRESS_REPORT', label: 'Annual progress report' },
  { value: 'OTHER', label: 'Other' },
]

const CATEGORY_LABELS = Object.fromEntries(
  CASE_DOCUMENT_CATEGORIES.map((c) => [c.value, c.label]),
)

const STATUS_LABELS = {
  DRAFT: 'Draft',
  SUBMITTED: 'Submitted',
  CM_REVIEW: 'Case manager review',
  SUPERVISOR_REVIEW: 'Case manager review',
  CHANGES_REQUESTED: 'Changes requested',
  CLIENT_REVIEW: 'With family',
  APPROVED: 'Approved',
  ARCHIVED: 'Archived',
}

const VISIBILITY_LABELS = {
  INTERNAL_ONLY: 'Internal only',
  CLIENT_VISIBLE_AFTER_APPROVAL: 'Family after approval',
  CLIENT_VISIBLE: 'Shared with family',
}

const WORKFLOW_LABELS = {
  submit: 'Submit for review',
  approve: 'Approve',
  request_changes: 'Request changes',
  publish_client: 'Share with family',
  archive: 'Archive',
  edit: 'Edit details',
  add_version: 'New version',
  parent_approve: 'Approve',
  parent_feedback: 'Request changes',
}

export function categoryLabel(value) {
  return CATEGORY_LABELS[value] || value || 'Document'
}

export function statusLabel(value) {
  return STATUS_LABELS[value] || value || '—'
}

export function visibilityLabel(value) {
  return VISIBILITY_LABELS[value] || value || '—'
}

export function workflowActionLabel(action) {
  return WORKFLOW_LABELS[action] || action
}

export function statusTone(status) {
  if (status === 'APPROVED') return 'completed'
  if (status === 'CHANGES_REQUESTED') return 'warning'
  if (status === 'CLIENT_REVIEW' || status === 'CM_REVIEW' || status === 'SUPERVISOR_REVIEW') {
    return 'pending'
  }
  if (status === 'ARCHIVED') return 'muted'
  return 'default'
}
