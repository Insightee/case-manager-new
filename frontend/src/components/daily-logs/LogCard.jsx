import { StatusBadge } from './StatusBadge.jsx'

export function LogCard({ log, onView, onEdit, onDuplicate }) {
  return (
    <article className="group rounded-2xl border border-[#E2E8F0] bg-white p-4 shadow-[0_2px_12px_rgba(15,23,42,0.04)] transition-transform duration-200 hover:scale-[1.01] hover:shadow-[0_12px_32px_rgba(15,23,42,0.08)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">{log.caseId}</p>
          <p className="mt-1 text-lg font-semibold text-slate-900">{log.child}</p>
          <p className="mt-2 text-sm text-slate-500">{log.date}</p>
        </div>
        <StatusBadge status={log.status} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <span className="rounded-lg bg-slate-50 px-2 py-1 font-medium ring-1 ring-slate-200/80">
          {log.durationMinutes ? `${log.durationMinutes} min` : '—'}
        </span>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onView?.(log)}
          className="rounded-lg bg-white px-3 py-2 text-sm font-semibold text-slate-700 ring-1 ring-[#E2E8F0] transition hover:bg-slate-50"
        >
          View
        </button>
        <button
          type="button"
          onClick={() => onEdit?.(log)}
          className="rounded-lg bg-indigo-50 px-3 py-2 text-sm font-semibold text-indigo-700 ring-1 ring-indigo-100 transition hover:bg-indigo-100"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={() => onDuplicate?.(log)}
          className="rounded-lg bg-orange-50 px-3 py-2 text-sm font-semibold text-orange-800 ring-1 ring-orange-100 transition hover:bg-orange-100"
        >
          Duplicate
        </button>
      </div>
    </article>
  )
}
