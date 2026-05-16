const variants = {
  queried: 'bg-amber-50 text-amber-950 ring-amber-200',
  rejected: 'bg-red-50 text-red-900 ring-red-200',
  in_review: 'bg-sky-50 text-sky-900 ring-sky-200',
  paid: 'bg-emerald-50 text-emerald-900 ring-emerald-200',
  issue: 'bg-orange-50 text-orange-900 ring-orange-200',
}

const labels = {
  queried: 'Queried',
  rejected: 'Rejected',
  in_review: 'In Review',
  paid: 'Paid',
  issue: 'Issue',
}

export function StatusBadge({ status }) {
  const key = String(status || '').toLowerCase()
  const className = variants[key] || variants.in_review
  const label = labels[key] || status

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  )
}
