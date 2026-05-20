/** Merge scheduled sessions and calendar bookings for therapist UI. */

function formatTime(t) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

export function todayIso() {
  const d = new Date()
  return d.toISOString().slice(0, 10)
}

export function mergeUpcomingSchedule({ sessions = [], slots = [] }) {
  const today = todayIso()
  const items = []

  for (const s of sessions) {
    if (s.status !== 'SCHEDULED' || s.scheduled_date < today) continue
    items.push({
      kind: 'session',
      key: `session-${s.id}`,
      sessionId: s.id,
      caseId: s.case_id,
      childName: s.child_name,
      caseCode: s.case_code,
      date: s.scheduled_date,
      startTime: formatTime(s.start_time),
      endTime: formatTime(s.end_time),
      mode: s.mode,
      subtitle: 'Scheduled session',
    })
  }

  for (const sl of slots) {
    if (sl.status !== 'BOOKED' || !sl.case_id || sl.slot_date < today) continue
    const dup = items.some(
      (i) =>
        i.caseId === sl.case_id &&
        i.date === sl.slot_date &&
        i.startTime === formatTime(sl.start_time),
    )
    if (dup) continue
    items.push({
      kind: 'booking',
      key: `slot-${sl.id}`,
      slotId: sl.id,
      caseId: sl.case_id,
      childName: sl.child_name,
      caseCode: sl.case_code,
      date: sl.slot_date,
      startTime: formatTime(sl.start_time),
      endTime: formatTime(sl.end_time),
      bookingSource: sl.booking_source,
      subtitle: sl.booking_source === 'PARENT' ? 'Parent booking' : 'Calendar booking',
    })
  }

  items.sort((a, b) => `${a.date}${a.startTime}`.localeCompare(`${b.date}${b.startTime}`))
  return items
}

export function formatScheduleWhen(item) {
  if (!item) return ''
  const d = new Date(`${item.date}T12:00:00`)
  const day = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
  if (item.startTime && item.endTime) return `${day} · ${item.startTime}–${item.endTime}`
  return day
}

export function isToday(dateStr) {
  return dateStr === todayIso()
}
