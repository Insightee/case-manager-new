import { Link } from 'react-router-dom'

export function ReportsDashboardBottomRow({ upcomingReports = [] }) {
  const items = upcomingReports.slice(0, 4)

  return (
    <article className="reports-dashboard-upcoming reports-dashboard-upcoming--solo">
      <h3 className="reports-dashboard-upcoming__title">Upcoming Reports</h3>
      <ul className="reports-dashboard-upcoming__list">
        {items.length === 0 ? (
          <li className="reports-dashboard-upcoming__empty">No upcoming reports due right now.</li>
        ) : (
          items.map((item) => (
            <li key={item.id} className="reports-dashboard-upcoming__item">
              <span
                className={`reports-dashboard-upcoming__dot reports-dashboard-upcoming__dot--${item.tone || 'warn'}`}
                aria-hidden
              />
              <div>
                <p className="reports-dashboard-upcoming__label">
                  {item.child}
                  {' · '}
                  {item.label}
                </p>
                <p className="reports-dashboard-upcoming__meta">{item.meta}</p>
              </div>
            </li>
          ))
        )}
      </ul>
      <Link to="/therapist/reports" className="reports-dashboard-upcoming__link">
        View all reports
      </Link>
    </article>
  )
}
