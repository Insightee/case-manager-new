import { useMemo } from 'react'

export function ChecklistPanel({ items, onToggle }) {
  const total = items.length
  const doneCount = items.filter((i) => i.done).length
  const pct = total ? Math.round((doneCount / total) * 100) : 0
  const remaining = total - doneCount

  const feedback = useMemo(() => {
    if (remaining <= 0) return 'All set — ready to submit'
    if (remaining === 1) return '1 step left to submit'
    return `${remaining} steps left to submit`
  }, [remaining])

  return (
    <aside className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-[0_4px_24px_rgba(15,23,42,0.06)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">Log completion checklist</h3>
          <p className="mt-1 text-sm text-slate-500">Smart assistant</p>
        </div>
        <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700">
          {pct}%
        </span>
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
                  : 'border-amber-200 bg-amber-50/90 text-amber-950 ring-1 ring-amber-100'
              }`}
            >
              <span
                className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  item.done ? 'bg-emerald-600 text-white' : 'bg-white text-amber-700 ring-1 ring-amber-300'
                }`}
                aria-hidden
              >
                {item.done ? '✓' : '!'}
              </span>
              <span className={item.done ? 'line-through decoration-slate-400' : ''}>{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
