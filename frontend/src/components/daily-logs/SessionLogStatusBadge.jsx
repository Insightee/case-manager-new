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

const ABSENCE_ATTENDANCE = new Set(['CLIENT_ABSENT', 'CLIENT_LEAVE', 'THERAPIST_LEAVE'])

const ATTENDANCE_LABELS = {
  CLIENT_ABSENT: 'Child absent',
  CLIENT_LEAVE: 'Client leave',
  THERAPIST_LEAVE: 'Therapist leave',
  PRESENT: 'Present',
  LATE: 'Late',
  PARTIAL: 'Partial',
  ABSENT: 'Absent',
}

export function SessionLogStatusBadge({ approvalStatus, attendanceStatus, isAbsenceRecord = false, compact = false }) {
  const approval = APPROVAL_STYLES[approvalStatus] || {
    label: approvalStatus || 'Unknown',
    className: 'ic-log-badge',
  }
  const attClass = ATTENDANCE_STYLES[attendanceStatus] || 'ic-log-badge ic-log-badge--attendance'
  const attendanceLabel = ATTENDANCE_LABELS[attendanceStatus] || attendanceStatus || '—'
  const absenceRow = isAbsenceRecord || ABSENCE_ATTENDANCE.has(attendanceStatus)

  if (absenceRow) {
    return (
      <div className="ic-log-badge-row">
        <span className={attClass}>{attendanceLabel}</span>
        <span className={approval.className}>{approval.label}</span>
      </div>
    )
  }

  if (compact) {
    return (
      <div className="ic-log-badge-row ic-log-badge-row--compact">
        <span className={attClass}>{attendanceStatus || '—'}</span>
        <span className={approval.className}>{approval.label}</span>
      </div>
    )
  }

  return (
    <div className="ic-log-badge-row">
      <span className="ic-log-badge ic-log-badge--done">Log completed</span>
      <span className={attClass}>{attendanceStatus || '—'}</span>
      <span className={approval.className}>{approval.label}</span>
    </div>
  )
}
