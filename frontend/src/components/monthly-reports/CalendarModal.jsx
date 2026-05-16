function formatDate(iso) {
  try {
    const d = new Date(iso + 'T12:00:00')
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
  } catch {
    return iso
  }
}

const kindStyles = {
  deadline: 'bg-red-50 text-red-900 ring-red-200',
  submission: 'bg-indigo-50 text-indigo-900 ring-indigo-200',
  review: 'bg-sky-50 text-sky-900 ring-sky-200',
}

export function CalendarModal({ open, onClose, events }) {
  if (!open) return null

  const sorted = [...events].sort((a, b) => a.date.localeCompare(b.date))

  return (
    <div
      className="fixed inset-0 z-[90] flex items-end justify-center bg-slate-900/40 p-4 backdrop-blur-[2px] sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="calendar-modal-title"
      onClick={onClose}
    >
      <div
        className="max-h-[85vh] w-full max-w-lg overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[#E2E8F0] px-5 py-4">
          <div>
            <h2 id="calendar-modal-title" className="text-lg font-semibold text-slate-900">
              Report calendar
            </h2>
            <p className="text-sm text-slate-500">Deadlines, submissions, and review windows</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            aria-label="Close"
          >
            ×
          </button>
        </div>
        <ul className="max-h-[60vh] space-y-2 overflow-auto p-4">
          {sorted.map((ev) => (
            <li
              key={`${ev.date}-${ev.caseId}-${ev.title}`}
              className="rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 shadow-sm"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{formatDate(ev.date)}</p>
                <span
                  className={`rounded-full px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide ring-1 ring-inset ${
                    kindStyles[ev.kind] || 'bg-slate-100 text-slate-800 ring-slate-200'
                  }`}
                >
                  {ev.kind === 'deadline'
                    ? 'Deadline'
                    : ev.kind === 'submission'
                      ? 'Submission'
                      : ev.kind === 'review'
                        ? 'Review'
                        : ev.kind}
                </span>
              </div>
              <p className="mt-1 text-sm font-medium text-slate-800">{ev.title}</p>
              <p className="text-xs text-slate-500">
                {ev.caseId} · {ev.child}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
