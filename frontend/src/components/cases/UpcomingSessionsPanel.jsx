import { Link } from 'react-router-dom'
import { formatScheduleWhen, isToday } from '../../lib/therapistSchedule.js'

export function UpcomingSessionsPanel({ items = [], loading = false }) {
  const preview = items.slice(0, 6)
  const todayCount = items.filter((i) => isToday(i.date)).length

  return (
    <section className="ic-upcoming" aria-label="Upcoming sessions">
      <div className="ic-upcoming__head">
        <div>
          <h2 className="ic-upcoming__title">Upcoming sessions</h2>
          <p className="ic-upcoming__sub">
            {todayCount > 0
              ? `${todayCount} today · ${items.length} in the next 90 days`
              : items.length
                ? `${items.length} booked in the next 90 days`
                : 'Bookings and scheduled visits across your caseload'}
          </p>
        </div>
        <Link to="/therapist/slots" className="ic-btn ic-btn--ghost">
          Open calendar
        </Link>
      </div>

      {loading ? (
        <p className="ic-upcoming__loading">Loading schedule…</p>
      ) : preview.length === 0 ? (
        <div className="ic-upcoming__empty">
          <p>No upcoming bookings yet.</p>
          <Link to="/therapist/slots" className="ic-btn ic-btn--primary">
            Set availability
          </Link>
        </div>
      ) : (
        <ul className="ic-upcoming__list">
          {preview.map((item) => (
            <li key={item.key}>
              <Link
                to={`/therapist/cases/${item.caseId}?tab=sessions`}
                className={`ic-upcoming__card${isToday(item.date) ? ' ic-upcoming__card--today' : ''}`}
              >
                <div className="ic-upcoming__card-top">
                  <span className="ic-upcoming__when">{formatScheduleWhen(item)}</span>
                  {isToday(item.date) ? <span className="ic-upcoming__pill">Today</span> : null}
                </div>
                <p className="ic-upcoming__child">{item.childName || item.caseCode || 'Client'}</p>
                <p className="ic-upcoming__meta">
                  {item.caseCode ? `${item.caseCode} · ` : ''}
                  {item.subtitle}
                </p>
              </Link>
            </li>
          ))}
        </ul>
      )}
      {items.length > preview.length ? (
        <p className="ic-upcoming__more">
          +{items.length - preview.length} more — use filters below or{' '}
          <Link to="/therapist/slots">calendar</Link>
        </p>
      ) : null}
    </section>
  )
}
