import { useMemo } from 'react'
import { addDays, addMonths, dateStr, startOfMonth } from './slotCalendarUtils.js'

function slotsForDate(slots, ds) {
  return (slots || []).filter((s) => s.slot_date === ds)
}

export function MonthCalendarGrid({
  calendar,
  loading,
  monthDate,
  onMonthChange,
  onSelectDay,
}) {
  const gridStart = useMemo(() => {
    const first = startOfMonth(monthDate)
    const s = new Date(first)
    s.setDate(first.getDate() - first.getDay())
    s.setHours(0, 0, 0, 0)
    return s
  }, [monthDate])

  const cells = useMemo(() => Array.from({ length: 42 }, (_, i) => addDays(gridStart, i)), [gridStart])
  const today = dateStr(new Date())
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  return (
    <div className="overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
      <div className="flex items-center gap-3 border-b border-[#E2E8F0] px-4 py-3">
        <button
          type="button"
          onClick={() => onMonthChange(addMonths(monthDate, -1))}
          className="rounded-lg border px-3 py-1 text-sm"
        >
          ‹
        </button>
        <p className="flex-1 text-center text-sm font-semibold text-slate-800">
          {monthDate.toLocaleDateString('en', { month: 'long', year: 'numeric' })}
        </p>
        <button
          type="button"
          onClick={() => onMonthChange(addMonths(monthDate, 1))}
          className="rounded-lg border px-3 py-1 text-sm"
        >
          ›
        </button>
        <button
          type="button"
          onClick={() => onMonthChange(new Date())}
          className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white"
        >
          This month
        </button>
      </div>

      {loading ? (
        <p className="p-8 text-center text-slate-500">Loading calendar…</p>
      ) : (
        <div className="p-2 sm:p-4">
          <div className="grid grid-cols-7 gap-px rounded-lg bg-[#E2E8F0] text-center text-[10px] font-semibold text-slate-500 sm:text-xs">
            {weekdays.map((w) => (
              <div key={w} className="bg-slate-50 py-2">
                {w}
              </div>
            ))}
            {cells.map((d) => {
              const ds = dateStr(d)
              const inMonth = d.getMonth() === monthDate.getMonth()
              const daySlots = slotsForDate(calendar?.slots, ds)
              const overlay = calendar?.day_overlays?.[ds]
              const hasBooked = daySlots.some((s) => s.status === 'BOOKED')
              const hasAvailable = daySlots.some((s) => s.status === 'AVAILABLE')
              const isToday = ds === today
              return (
                <button
                  key={ds}
                  type="button"
                  onClick={() => onSelectDay?.(d)}
                  className={`min-h-[52px] bg-white p-1 text-left align-top transition hover:bg-indigo-50/60 sm:min-h-[64px] ${
                    !inMonth ? 'opacity-40' : ''
                  } ${isToday ? 'ring-1 ring-inset ring-indigo-400' : ''}`}
                >
                  <span className={`block text-xs font-bold sm:text-sm ${isToday ? 'text-indigo-700' : 'text-slate-800'}`}>
                    {d.getDate()}
                  </span>
                  <span className="mt-1 flex flex-wrap gap-0.5">
                    {overlay ? (
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500" title="Leave" />
                    ) : null}
                    {hasBooked ? (
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-indigo-600" title="Booked" />
                    ) : null}
                    {hasAvailable && !overlay ? (
                      <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-500" title="Available" />
                    ) : null}
                  </span>
                </button>
              )
            })}
          </div>
          <p className="mt-3 text-center text-[10px] text-slate-500 sm:text-xs">
            Tap a day for hourly view · <span className="text-indigo-600">●</span> booked{' '}
            <span className="text-emerald-600">●</span> available <span className="text-amber-600">●</span> leave
          </p>
        </div>
      )}
    </div>
  )
}
