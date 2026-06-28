const STATUS_MAP = {
  DRAFT:            { cls: 'draft',       label: 'Draft' },
  DRAFTING:         { cls: 'drafting',    label: 'Drafting in Progress' },
  UNDER_REVIEW:     { cls: 'review',      label: 'Under Review' },
  REJECTED:         { cls: 'revision',    label: 'Revision Needed' },
  APPROVED:         { cls: 'approved',    label: 'Approved' },
  PUBLISHED:        { cls: 'published',   label: 'Published' },
  ACTIVE:           { cls: 'active',      label: 'Active' },
  PENDING_CM:       { cls: 'pending-cm',  label: 'Pending CM Review' },
  LOCKED:           { cls: 'locked',      label: 'Locked' },
  not_started:      { cls: 'draft',       label: 'Not Started' },
  in_progress:      { cls: 'drafting',    label: 'In Progress' },
  overdue:          { cls: 'revision',    label: 'Overdue' },
}

/**
 * Standard status badge.
 * status: one of the STATUS_MAP keys (case-insensitive).
 * customLabel: override display text.
 */
export function ClinicalStatusBadge({ status, customLabel }) {
  const key = (status || '').toUpperCase()
  const entry = STATUS_MAP[status] || STATUS_MAP[key] || { cls: 'draft', label: status || '—' }
  return (
    <span className={`clinical-status-badge clinical-status-badge--${entry.cls}`}>
      {customLabel || entry.label}
    </span>
  )
}
