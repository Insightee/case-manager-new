import { Link } from 'react-router-dom'

/**
 * Session history timeline list.
 * items: Array<{ date: string (ISO or DD Mon YYYY), title, duration, goals, logUrl }>
 * onViewAll: optional callback for "View All Logs" — only shown if provided
 */
export function ClinicalTimelineList({ items = [], onViewAll, viewAllLabel = 'View All Logs' }) {
  if (!items.length) return null

  return (
    <div>
      <div className="clinical-timeline-list">
        {items.map((item, idx) => {
          const d = item.date ? new Date(item.date) : null
          const day = d && !isNaN(d) ? d.getDate() : item.date?.split('-').pop() || '—'
          const mon = d && !isNaN(d)
            ? d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
            : ''

          return (
            <div key={item.id || idx} className="clinical-timeline-item">
              <div className="clinical-timeline-item__date">
                <div className="clinical-timeline-item__date-day">{day}</div>
                {mon ? <div className="clinical-timeline-item__date-month">{mon}</div> : null}
              </div>
              <div>
                <p className="clinical-timeline-item__title">{item.title}</p>
                <p className="clinical-timeline-item__meta">
                  {item.duration ? `${item.duration} mins` : null}
                  {item.goals ? ` · Goals: ${item.goals}` : null}
                </p>
              </div>
              {item.logUrl ? (
                <Link to={item.logUrl} className="clinical-timeline-item__link">
                  View Detail →
                </Link>
              ) : null}
            </div>
          )
        })}
      </div>
      {onViewAll ? (
        <button type="button" className="clinical-btn-ghost" onClick={onViewAll} style={{ marginTop: '0.5rem' }}>
          {viewAllLabel}
        </button>
      ) : null}
    </div>
  )
}
