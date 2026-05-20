import { useMemo } from 'react'

export function ChecklistPanel({
  items,
  onToggle,
  title = 'Progress checklist',
  subtitle = 'Workflow readiness',
  completeLabel = 'Workflow complete',
  stepLabel = 'step',
}) {
  const total = items.length
  const doneCount = items.filter((i) => i.done).length
  const pct = total ? Math.round((doneCount / total) * 100) : 0
  const remaining = total - doneCount

  const feedback = useMemo(() => {
    if (remaining <= 0) return completeLabel
    if (remaining === 1) return `1 ${stepLabel} left`
    return `${remaining} ${stepLabel}s left`
  }, [remaining, completeLabel, stepLabel])

  return (
    <aside className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-[0_4px_24px_rgba(15,23,42,0.06)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700">{pct}%</span>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-orange-400 transition-[width] duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-sm font-medium text-slate-700">{feedback}</p>

      <ul className="mt-4 space-y-2">
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onToggle?.(item.id)}
              className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition-all hover:shadow-md ${
                item.done
                  ? 'border-emerald-200 bg-emerald-50/80 text-emerald-900'
                  : 'border-slate-200 bg-white text-slate-800'
              }`}
            >
              <span
                className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-xs ${
                  item.done ? 'border-emerald-500 bg-emerald-500 text-white' : 'border-slate-300'
                }`}
                aria-hidden
              >
                {item.done ? '✓' : ''}
              </span>
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
