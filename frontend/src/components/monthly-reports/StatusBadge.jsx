const variants = {
  draft: 'bg-amber-50 text-amber-900 ring-amber-200',
  under_review: 'bg-sky-50 text-sky-900 ring-sky-200',
  published: 'bg-emerald-50 text-emerald-900 ring-emerald-200',
  overdue: 'bg-red-50 text-red-900 ring-red-200',
  rejected: 'bg-rose-50 text-rose-900 ring-rose-200',
  not_started: 'bg-slate-100 text-slate-800 ring-slate-200',
}

const labels = {
  draft: 'Draft',
  under_review: 'Under Review',
  published: 'Published',
  overdue: 'Overdue',
  rejected: 'Rejected',
  not_started: 'Not started',
}

export function StatusBadge({ status }) {
  const key = String(status || '').toLowerCase()
  const className = variants[key] || variants.draft
  const label = labels[key] || status

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${className}`}
    >
      {label}
    </span>
  )
}
