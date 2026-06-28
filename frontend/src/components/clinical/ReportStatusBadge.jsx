const STATUS_MAP = {
  DRAFT: { label: 'Draft', className: 'cp-badge--draft' },
  UNDER_REVIEW: { label: 'Under Review', className: 'cp-badge--review' },
  REJECTED: { label: 'Revision Requested', className: 'cp-badge--revision' },
  APPROVED: { label: 'Approved', className: 'cp-badge--approved' },
  PUBLISHED: { label: 'Published', className: 'cp-badge--published' },
  locked: { label: 'Locked', className: 'cp-badge--locked' },
}

export function ReportStatusBadge({ status, locked }) {
  if (locked) {
    return <span className="cp-badge cp-badge--locked">Locked</span>
  }
  const key = String(status || '').toUpperCase()
  const mapped = STATUS_MAP[key] || { label: status || '—', className: 'cp-badge--draft' }
  return <span className={`cp-badge ${mapped.className}`}>{mapped.label}</span>
}
