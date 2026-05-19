import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

function formatTime(t) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

export function CaseBookingsPanel({ caseId }) {
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 60)
      const to = toDate.toISOString().slice(0, 10)
      const rows = await apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`)
      setSlots((rows || []).filter((sl) => sl.case_id === caseId))
    } catch {
      setSlots([])
    } finally {
      setLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    load()
  }, [load])

  if (loading) return <p style={{ color: '#6b7280' }}>Loading bookings…</p>

  const booked = slots.filter((s) => s.status === 'BOOKED')

  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
        Parent or admin bookings on your calendar for this case. To propose a new time, use{' '}
        <Link to="/therapist/tickets">Support</Link> or manage slots on{' '}
        <Link to="/therapist/slots">Open Slots</Link>.
      </p>
      {booked.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No upcoming bookings for this case.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {booked.map((sl) => (
            <li key={sl.id} style={{ padding: 12, marginBottom: 8, border: '1px solid #e5e7eb', borderRadius: 8 }}>
              <strong>{sl.slot_date}</strong> · {formatTime(sl.start_time)}–{formatTime(sl.end_time)}
              <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#6b7280' }}>{sl.booking_source || 'BOOKED'}</span>
            </li>
          ))}
        </ul>
      )}
      <p style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: 16 }}>
        Approve / reschedule workflow — coming soon. Bookings currently confirm immediately when parents book.
      </p>
    </div>
  )
}
