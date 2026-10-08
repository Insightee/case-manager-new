import { WEEKDAY_KEYS } from './slotCalendarUtils.js'
import './schedule-sheet.css'

/**
 * Shared weekday chip row for therapist, admin, and add-slot recurring flows.
 */
export function ScheduleWeekdayPicker({ value = [], onChange, label = 'Repeat on', compact = false }) {
  const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

  function toggle(key) {
    onChange?.(value.includes(key) ? value.filter((d) => d !== key) : [...value, key])
  }

  return (
    <div>
      {label ? <p className="sched-sheet__eyebrow">{label}</p> : null}
      <div className="sched-days" role="group" aria-label={label || 'Weekdays'}>
        {WEEKDAY_KEYS.map((key, i) => {
          const active = value.includes(key)
          return (
            <button
              key={key}
              type="button"
              aria-pressed={active}
              onClick={() => toggle(key)}
              className={`sched-day${compact ? ' sched-day--compact' : ''}${active ? ' is-on' : ''}`}
            >
              {compact ? labels[i].slice(0, 2) : labels[i]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
