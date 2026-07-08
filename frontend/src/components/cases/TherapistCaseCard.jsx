import { Link } from 'react-router-dom'
import { formatScheduleWhen } from '../../lib/therapistSchedule.js'
import { serviceStyleFromCase } from '../../lib/serviceColors.js'
import { ServiceBadge } from '../shared/ServiceBadge.jsx'
import { StatusBadge } from './StatusBadge.jsx'

function clientInitials(name) {
  const parts = String(name || '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
}

function avatarTone(name) {
  const code = String(name || '').split('').reduce((n, c) => n + c.charCodeAt(0), 0)
  const tones = ['sage', 'sky', 'sand', 'rose', 'mint']
  return tones[code % tones.length]
}

function hasReportPending(data) {
  const due = String(data.nextDue || '').toLowerCase()
  const stage = String(data.stage || '').toLowerCase()
  return due.includes('report') || stage.includes('report') || data.showSubmitReport
}

function isInactiveCase(data) {
  const status = String(data.status || '').toUpperCase()
  return ['CLOSED', 'SUSPENDED', 'DEACTIVATED', 'PENDING_REPLACEMENT'].includes(status)
}

export function TherapistCaseCard({ data }) {
  const overviewTo = `/therapist/cases/${data.id}?tab=overview`
  const logTo = `/therapist/cases/${data.id}?tab=logs`
  const reportTo = `/therapist/cases/${data.id}?tab=reports&section=monthly`
  const bookingTo = `/therapist/cases/${data.id}?tab=overview`
  const bookingWhen = data.nextBooking
    ? formatScheduleWhen({
        date: data.nextBooking.date,
        startTime: data.nextBooking.startTime,
        endTime: data.nextBooking.endTime,
      })
    : null
  const hasAddress = Boolean(data.serviceAddress?.formatted)
  const tone = avatarTone(data.child)
  const service = serviceStyleFromCase(data)
  const logsDue = (data.needsLogCount ?? 0) > 0
  const reportPending = hasReportPending(data)
  const inactive = isInactiveCase(data)

  return (
    <article
      className={`mc-case-card${inactive ? ' mc-case-card--inactive' : ''}${!inactive && data.critical ? ' mc-case-card--urgent' : ''}`}
      style={{
        '--service-accent': service.text,
        '--service-soft': service.bg,
        '--service-border': service.border,
      }}
    >
      <div className="mc-case-card__topline">
        <ServiceBadge caseRow={data} className="mc-case-card__service-badge" />
        <Link to={overviewTo} className="mc-case-card__status" aria-label={`Case status: ${data.stage}`}>
          <StatusBadge variant={data.badgeVariant || 'active'}>{data.stage || 'Active'}</StatusBadge>
        </Link>
      </div>

      <div className="mc-case-card__head">
        <span className={`mc-case-card__avatar mc-case-card__avatar--${tone}`} aria-hidden="true">
          {clientInitials(data.child)}
        </span>
        <div className="mc-case-card__identity">
          <h3 className="mc-case-card__name">{data.child}</h3>
          <p className="mc-case-card__case-id">{data.caseId}</p>
        </div>
        {hasAddress ? (
          data.mapsUrl ? (
            <a
              href={data.mapsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mc-case-card__map"
              aria-label={`Open visit address for ${data.child} in Maps`}
              title={data.serviceAddress.formatted}
            >
              <span className="material-symbols-outlined" aria-hidden="true">map</span>
            </a>
          ) : (
            <span
              className="mc-case-card__map mc-case-card__map--static"
              title={data.serviceAddress.formatted}
              aria-label={`Visit address: ${data.serviceAddress.formatted}`}
            >
              <span className="material-symbols-outlined" aria-hidden="true">map</span>
            </span>
          )
        ) : null}
      </div>

      {data.caseManagerName ? (
        <p className="mc-case-card__cm">
          CM <strong>{data.caseManagerName}</strong>
        </p>
      ) : null}

      <div className="mc-case-card__pending">
        {logsDue ? (
          <Link to={logTo} className="mc-case-card__pending-chip mc-case-card__pending-chip--log">
            <span className="material-symbols-outlined" aria-hidden="true">edit_note</span>
            {data.needsLogCount} log{data.needsLogCount === 1 ? '' : 's'} due
          </Link>
        ) : (
          <Link to={logTo} className="mc-case-card__pending-chip mc-case-card__pending-chip--ok">
            <span className="material-symbols-outlined" aria-hidden="true">check_circle</span>
            Logs up to date
          </Link>
        )}
        {reportPending ? (
          <Link to={reportTo} className="mc-case-card__pending-chip mc-case-card__pending-chip--report">
            <span className="material-symbols-outlined" aria-hidden="true">description</span>
            {data.nextDue?.toLowerCase().includes('report') ? data.nextDue : 'Report pending'}
          </Link>
        ) : null}
      </div>

      {bookingWhen ? (
        <Link to={bookingTo} className="mc-case-card__visit">
          <span className="material-symbols-outlined" aria-hidden="true">event</span>
          Next visit · {bookingWhen}
        </Link>
      ) : null}

      <div className="mc-case-card__actions">
        <Link to={overviewTo} className="mc-case-card__action mc-case-card__action--primary">
          Open case file
        </Link>
      </div>
    </article>
  )
}
