const STATUS_LABELS = {
  ACTIVE: 'Active',
  PENDING_ALLOTMENT: 'Pending allotment',
  SUSPENDED: 'Suspended',
  CLOSED: 'Closed',
  UNDER_REVIEW: 'In review',
  IN_REVIEW: 'Escalated',
  INVESTIGATING: 'Escalated',
  OPEN: 'Open',
  RESOLVED: 'Closed',
  ACTION_TAKEN: 'Closed',
  REPORTED: 'Open',
  ESCALATED: 'Escalated',
  IN_PROGRESS: 'In progress',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  DRAFT: 'Draft',
  PAUSED: 'Paused',
  DELETED: 'Deleted',
  NEEDS_LISTING: 'Needs listing',
  PAID: 'Paid',
  // Canonical support buckets (lowercase)
  open: 'Open',
  in_progress: 'In progress',
  closed: 'Closed',
  escalated: 'Escalated',
}

export function formatStatus(status) {
  if (!status) return '—'
  const raw = String(status)
  if (STATUS_LABELS[raw]) return STATUS_LABELS[raw]
  const key = raw.toUpperCase()
  return STATUS_LABELS[key] ?? key.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
}

export function statusTone(status) {
  const key = String(status || '').toUpperCase()
  const lower = String(status || '').toLowerCase()
  if (lower === 'escalated' || key === 'ESCALATED' || key === 'IN_REVIEW' || key === 'INVESTIGATING') return 'danger'
  if (['ACTIVE', 'APPROVED', 'PAID', 'RESOLVED', 'CLOSED', 'COMPLETED', 'ACTION_TAKEN'].includes(key) || lower === 'closed') {
    return 'success'
  }
  if (
    ['PENDING_ALLOTMENT', 'UNDER_REVIEW', 'OPEN', 'IN_PROGRESS', 'DRAFT', 'NO_SHOW', 'CLIENT_ABSENT', 'REPORTED'].includes(
      key,
    ) ||
    lower === 'open' ||
    lower === 'in_progress'
  ) {
    return 'warning'
  }
  if (['SUSPENDED', 'REJECTED', 'QUERIED', 'DELETED', 'CANCELLED'].includes(key)) return 'danger'
  return 'neutral'
}

export function formatCurrency(inr) {
  if (inr == null || Number.isNaN(Number(inr))) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(inr)
}
