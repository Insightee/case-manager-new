import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateLabel, formatDisplayDateTimeRange } from '../../lib/datetime.js'

/**
 * Compact leave + child-absence alerts for the parent home dashboard.
 */
export function ParentAttendanceAlerts() {
  const [absences, setAbsences] = useState([])
  const [leaves, setLeaves] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [absenceRes, leaveRows] = await Promise.all([
        apiFetch('/api/v1/parent/absence-requests').catch(() => ({ items: [] })),
        apiFetch('/api/v1/parent/therapist-leaves').catch(() => []),
      ])
      setAbsences(absenceRes?.items ?? [])
      setLeaves(Array.isArray(leaveRows) ? leaveRows : [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const leaveAlerts = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10)
    return leaves
      .filter((row) => row.scheduled_date && row.scheduled_date >= today)
      .slice(0, 5)
      .map((row) => ({
        key: `leave-${row.leave_id}-${row.scheduled_date}`,
        kind: 'leave',
        title: row.status_label || 'Therapist leave',
        meta: [
          formatDisplayDateLabel(row.scheduled_date),
          row.child_name,
          row.therapist_name,
        ]
          .filter(Boolean)
          .join(' · '),
        href: row.leave_id
          ? `/parent/session-logs?leave_id=${row.leave_id}`
          : '/parent/session-logs',
      }))
  }, [leaves])

  const absenceAlerts = useMemo(
    () =>
      absences.slice(0, 5).map((row) => ({
        key: `absence-${row.id}`,
        kind: 'absence',
        title: 'Child absence recorded',
        meta: [
          formatDisplayDateTimeRange(row.scheduled_date, row.start_time, row.end_time),
          row.child_name,
          row.therapist_name,
        ]
          .filter(Boolean)
          .join(' · '),
        href: '/parent/session-logs',
        status: row.dispute_status === 'DISPUTED' ? 'Disputed' : null,
      })),
    [absences],
  )

  const items = [...absenceAlerts, ...leaveAlerts]

  if (loading) {
    return <p className="parent-dash-muted">Checking leave and absence updates…</p>
  }

  if (!items.length) return null

  return (
    <ul className="parent-dash-notify-list">
      {items.map((item) => (
        <li key={item.key}>
          <Link to={item.href} className="parent-dash-notify-list__row">
            <span
              className={`parent-dash-notify-list__icon parent-dash-notify-list__icon--${item.kind}`}
              aria-hidden
            >
              {item.kind === 'leave' ? 'L' : 'A'}
            </span>
            <span className="parent-dash-notify-list__body">
              <span className="parent-dash-notify-list__title">{item.title}</span>
              <span className="parent-dash-notify-list__meta">{item.meta}</span>
            </span>
            {item.status ? (
              <span className="parent-dash-status parent-dash-status--warn">{item.status}</span>
            ) : (
              <span className="parent-dash-notify-list__chevron" aria-hidden>
                →
              </span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  )
}
