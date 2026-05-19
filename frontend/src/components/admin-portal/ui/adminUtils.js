const STATUS_LABELS = {
  ACTIVE: 'Active',
  PENDING_ALLOTMENT: 'Pending allotment',
  SUSPENDED: 'Suspended',
  CLOSED: 'Closed',
  UNDER_REVIEW: 'In review',
  IN_REVIEW: 'In review',
  OPEN: 'Open',
  RESOLVED: 'Resolved',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  DRAFT: 'Draft',
  PAID: 'Paid',
}

export function formatStatus(status) {
  if (!status) return '—'
  const key = String(status).toUpperCase()
  return STATUS_LABELS[key] ?? key.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())
}

export function statusTone(status) {
  const key = String(status || '').toUpperCase()
  if (['ACTIVE', 'APPROVED', 'PAID', 'RESOLVED', 'CLOSED'].includes(key)) return 'success'
  if (['PENDING_ALLOTMENT', 'UNDER_REVIEW', 'IN_REVIEW', 'OPEN', 'IN_PROGRESS', 'DRAFT'].includes(key)) return 'warning'
  if (['SUSPENDED', 'REJECTED', 'QUERIED'].includes(key)) return 'danger'
  return 'neutral'
}

export function formatCurrency(inr) {
  if (inr == null || Number.isNaN(Number(inr))) return '—'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(inr)
}
