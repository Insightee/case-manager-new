import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const EMPTY_DATES = new Set()

function localDateIso(value) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function addDays(value, amount) {
  const next = new Date(value)
  next.setDate(next.getDate() + amount)
  return next
}

function calendarStart(monthDate) {
  const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1)
  return addDays(first, -first.getDay())
}

export function TransitionDateCalendar({
  caseId,
  incomingTherapistId,
  outgoingTherapistId,
  value,
  onChange,
  lockedDates = [],
  disabled = false,
  requiredCount = 3,
}) {
  const [monthDate, setMonthDate] = useState(() => new Date())
  const [availability, setAvailability] = useState({
    key: '',
    dates: EMPTY_DATES,
    error: '',
  })
  const selectedDates = useMemo(() => new Set(value || []), [value])
  const locked = useMemo(() => new Set(lockedDates), [lockedDates])
  const gridStart = useMemo(() => calendarStart(monthDate), [monthDate])
  const cells = useMemo(
    () => Array.from({ length: 42 }, (_, index) => addDays(gridStart, index)),
    [gridStart],
  )
  const today = localDateIso(new Date())
  const rangeStart = localDateIso(gridStart)
  const rangeEnd = localDateIso(addDays(gridStart, 41))
  const requestKey = caseId && incomingTherapistId && outgoingTherapistId
    ? `${caseId}:${outgoingTherapistId}:${incomingTherapistId}:${rangeStart}:${rangeEnd}`
    : ''
  const hasCurrentAvailability = Boolean(requestKey && availability.key === requestKey)
  const unavailableDates = hasCurrentAvailability ? availability.dates : EMPTY_DATES
  const error = hasCurrentAvailability ? availability.error : ''
  const loading = Boolean(requestKey && !hasCurrentAvailability)
  const availabilityReady = Boolean(incomingTherapistId && outgoingTherapistId) && !loading && !error

  useEffect(() => {
    if (!requestKey) return undefined
    let active = true
    apiFetch(
      `/api/v1/cases/${caseId}/transitions/availability?incoming_therapist_user_id=${encodeURIComponent(incomingTherapistId)}&outgoing_therapist_user_id=${encodeURIComponent(outgoingTherapistId)}&start_date=${rangeStart}&end_date=${rangeEnd}`,
    )
      .then((data) => {
        if (active) {
          setAvailability({
            key: requestKey,
            dates: new Set(data?.unavailable_dates || []),
            error: '',
          })
        }
      })
      .catch((err) => {
        if (active) {
          setAvailability({
            key: requestKey,
            dates: EMPTY_DATES,
            error: err.message || 'Could not check therapist leave for this month.',
          })
        }
      })
    return () => {
      active = false
    }
  }, [caseId, incomingTherapistId, outgoingTherapistId, rangeEnd, rangeStart, requestKey])

  function changeMonth(amount) {
    setMonthDate((current) => new Date(current.getFullYear(), current.getMonth() + amount, 1))
  }

  function toggleDate(dateValue) {
    const iso = localDateIso(dateValue)
    if (disabled || locked.has(iso)) return
    if (selectedDates.has(iso)) {
      onChange?.((value || []).filter((item) => item !== iso))
      return
    }
    if (iso < today || unavailableDates.has(iso)) return
    if ((value || []).length >= requiredCount) return
    onChange?.([...(value || []), iso].sort())
  }

  return (
    <div className="transition-calendar">
      <div className="transition-calendar__head">
        <button type="button" onClick={() => changeMonth(-1)} disabled={disabled} aria-label="Previous month">
          ‹
        </button>
        <strong>{monthDate.toLocaleDateString('en', { month: 'long', year: 'numeric' })}</strong>
        <button type="button" onClick={() => changeMonth(1)} disabled={disabled} aria-label="Next month">
          ›
        </button>
      </div>
      <p className="transition-calendar__progress" aria-live="polite">
        {!incomingTherapistId
          ? 'Choose the incoming therapist to check leave dates'
          : `${(value || []).length} of ${requiredCount} transition days selected`}
        {loading ? ' · Checking leave…' : ''}
      </p>
      <div className="transition-calendar__grid transition-calendar__weekdays" aria-hidden="true">
        {WEEKDAYS.map((weekday) => <span key={weekday}>{weekday}</span>)}
      </div>
      <div className="transition-calendar__grid">
        {cells.map((dateValue) => {
          const iso = localDateIso(dateValue)
          const selected = selectedDates.has(iso)
          const isLocked = locked.has(iso)
          const onLeave = unavailableDates.has(iso)
          const isPast = iso < today
          const inMonth = dateValue.getMonth() === monthDate.getMonth()
          const dayDisabled = disabled || !availabilityReady || isLocked || ((!selected && isPast) || (!selected && onLeave)) || (!selected && (value || []).length >= requiredCount)
          const reason = isLocked
            ? 'A transition log has already been submitted'
            : onLeave
              ? 'A therapist has pending or approved leave'
              : isPast
                ? 'Past dates cannot be selected'
                : selected
                  ? 'Selected transition day'
                  : 'Available transition day'
          return (
            <button
              key={iso}
              type="button"
              className={[
                'transition-calendar__day',
                inMonth ? '' : 'transition-calendar__day--outside',
                selected ? 'transition-calendar__day--selected' : '',
                isLocked ? 'transition-calendar__day--locked' : '',
                onLeave ? 'transition-calendar__day--leave' : '',
              ].filter(Boolean).join(' ')}
              onClick={() => toggleDate(dateValue)}
              disabled={dayDisabled}
              aria-pressed={selected}
              aria-label={`${dateValue.toLocaleDateString('en', { dateStyle: 'long' })}. ${reason}`}
              title={reason}
            >
              {dateValue.getDate()}
            </button>
          )
        })}
      </div>
      <div className="transition-calendar__legend">
        <span><i className="transition-calendar__dot transition-calendar__dot--selected" /> Selected</span>
        <span><i className="transition-calendar__dot transition-calendar__dot--leave" /> Therapist leave</span>
        {locked.size ? <span><i className="transition-calendar__dot transition-calendar__dot--locked" /> Log submitted</span> : null}
      </div>
      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
    </div>
  )
}
