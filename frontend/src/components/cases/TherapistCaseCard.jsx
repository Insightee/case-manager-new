import { Link } from 'react-router-dom'
import { formatScheduleWhen } from '../../lib/therapistSchedule.js'
import { StatusBadge } from './StatusBadge.jsx'

function IconPlus() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" aria-hidden>
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

function IconEye() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function IconReport() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6M12 18v-6M9 15h6" />
    </svg>
  )
}

function IconInfo() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  )
}

export function TherapistCaseCard({ data }) {
  const accent = data.borderAccent || 'blue'
  const detailTo = `/therapist/cases/${data.id}`
  const logTo = `/therapist/cases/${data.id}?tab=sessions`
  const reportTo = `/therapist/reports?case_id=${data.id}`
  const bookingTo = `/therapist/cases/${data.id}?tab=overview`
  const bookingWhen = data.nextBooking
    ? formatScheduleWhen({
        date: data.nextBooking.date,
        startTime: data.nextBooking.startTime,
        endTime: data.nextBooking.endTime,
      })
    : null

  return (
    <article className={`ic-card ic-card--accent-${accent}`}>
      <div className="ic-card__top">
        <span className="ic-card__id">{data.caseId}</span>
        <div className="ic-card__top-right">
          {data.critical ? <span className="ic-critical" title="Urgent" /> : null}
        </div>
      </div>
      <StatusBadge variant={data.badgeVariant}>{data.stage}</StatusBadge>
      <h3 className="ic-card__name">{data.child}</h3>
      <p className="ic-card__service">{data.service}</p>
      {bookingWhen ? (
        <Link to={bookingTo} className="ic-card__booking">
          <span className="ic-card__booking-label">Next visit</span>
          <span className="ic-card__booking-when">{bookingWhen}</span>
        </Link>
      ) : null}
      {data.nextDue && data.nextDue !== '—' ? (
        <p className="ic-card__due">
          <IconInfo />
          {data.nextDue}
        </p>
      ) : null}
      <div className="ic-card__actions">
        <Link to={logTo} className="ic-btn ic-btn--primary">
          <IconPlus />
          Session log
        </Link>
        <Link to={detailTo} className="ic-btn ic-btn--ghost">
          <IconEye />
          View case
        </Link>
        <Link to={reportTo} className="ic-btn ic-btn--accent">
          <IconReport />
          Reports
        </Link>
      </div>
    </article>
  )
}
