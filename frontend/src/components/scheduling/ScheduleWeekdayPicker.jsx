import { WEEKDAY_KEYS } from './slotCalendarUtils.js'

/**
 * Shared weekday chip row (matches Add slot / SlotEditSheet styling).
 */
export function ScheduleWeekdayPicker({ value = [], onChange, label = 'Repeat on', compact = false }) {
  const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  function toggle(key) {
    onChange?.(value.includes(key) ? value.filter((d) => d !== key) : [...value, key])
  }

  return (
    <div>
      {label ? <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">{label}</p> : null}
      <div className={`flex flex-wrap ${compact ? 'gap-1.5' : 'gap-2'}`}>
        {WEEKDAY_KEYS.map((key, i) => {
          const active = value.includes(key)
          return (
            <button
              key={key}
              type="button"
              onClick={() => toggle(key)}
              className={
                compact
                  ? `h-9 w-9 rounded-full text-xs font-semibold border transition-colors ${
                      active
                        ? 'border-indigo-600 bg-indigo-600 text-white'
                        : 'border-slate-200 text-slate-600 hover:border-indigo-300'
                    }`
                  : `rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${
                      active
                        ? 'border-indigo-600 bg-indigo-50 text-indigo-800'
                        : 'border-slate-200 text-slate-600 hover:border-indigo-300'
                    }`
              }
            >
              {compact ? labels[i].slice(0, 2) : labels[i]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
