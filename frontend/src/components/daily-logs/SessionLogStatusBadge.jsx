const APPROVAL_STYLES = {
  PENDING: { label: 'Pending review', className: 'ic-log-badge ic-log-badge--pending' },
  APPROVED: { label: 'Approved', className: 'ic-log-badge ic-log-badge--approved' },
  REJECTED: { label: 'Rejected', className: 'ic-log-badge ic-log-badge--rejected' },
}

const ATTENDANCE_STYLES = {
  PRESENT: 'ic-log-badge ic-log-badge--attendance',
  LATE: 'ic-log-badge ic-log-badge--attendance-late',
  PARTIAL: 'ic-log-badge ic-log-badge--attendance',
  ABSENT: 'ic-log-badge ic-log-badge--attendance-absent',
}

export function SessionLogStatusBadge({ approvalStatus, attendanceStatus }) {
  const approval = APPROVAL_STYLES[approvalStatus] || {
    label: approvalStatus || 'Unknown',
    className: 'ic-log-badge',
  }
  const attClass = ATTENDANCE_STYLES[attendanceStatus] || 'ic-log-badge ic-log-badge--attendance'

  return (
    <div className="ic-log-badge-row">
      <span className="ic-log-badge ic-log-badge--done">Log completed</span>
      <span className={attClass}>{attendanceStatus || '—'}</span>
      <span className={approval.className}>{approval.label}</span>
    </div>
  )
}
