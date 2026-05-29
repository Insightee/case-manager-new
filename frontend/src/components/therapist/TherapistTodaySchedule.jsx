import { Link } from 'react-router-dom'
import { formatScheduleWhen, isToday } from '../../lib/therapistSchedule.js'

function kindLabel(item) {
  if (item.kind === 'booking') {
    return item.bookingSource === 'PARENT' ? 'Parent booking' : 'Calendar'
  }
  return 'Session'
}

export function TherapistTodaySchedule({ items = [], limit = 8 }) {
  const visible = items.slice(0, limit)
  if (!visible.length) return null

  return (
    <ul className="therapist-schedule" aria-label="Upcoming schedule">
      {visible.map((item) => {
        const today = isToday(item.date)
        const when = formatScheduleWhen(item)
        const href = item.sessionId
          ? `/therapist/logs?session=${item.sessionId}`
          : item.caseId
            ? `/therapist/cases/${item.caseId}`
            : '/therapist/logs'

        return (
          <li key={item.key} className={`therapist-schedule__item${today ? ' therapist-schedule__item--today' : ''}`}>
            <Link to={href} className="therapist-schedule__link">
              <div className="therapist-schedule__main">
                <span className="therapist-schedule__name">{item.childName || item.caseCode}</span>
                {today ? <span className="therapist-schedule__badge">Today</span> : null}
              </div>
              <p className="therapist-schedule__when">{when}</p>
              <p className="therapist-schedule__meta">
                <span className="therapist-schedule__kind">{kindLabel(item)}</span>
                {item.subtitle ? <span className="therapist-schedule__subtitle">{item.subtitle}</span> : null}
              </p>
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
