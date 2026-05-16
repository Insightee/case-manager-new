const variants = {
  submitted: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  pending: 'bg-amber-50 text-amber-900 ring-amber-200',
  approved: 'bg-sky-50 text-sky-800 ring-sky-200',
  missing: 'bg-red-50 text-red-800 ring-red-200',
}

const labels = {
  submitted: 'Submitted',
  pending: 'Pending',
  approved: 'Approved',
  missing: 'Missing',
}

export function StatusBadge({ status }) {
  const key = String(status || '').toLowerCase()
  const className = variants[key] || variants.pending
  const label = labels[key] || status

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  )
}
