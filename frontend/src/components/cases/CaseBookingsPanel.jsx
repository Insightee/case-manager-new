import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { SlotDetailSheet } from '../scheduling/SlotDetailSheet.jsx'

function formatTime(t) {
  if (!t) return ''
  return String(t).slice(0, 5)
}

export function CaseBookingsPanel({ caseId }) {
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [detailSlot, setDetailSlot] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const today = new Date()
      const from = today.toISOString().slice(0, 10)
      const toDate = new Date(today)
      toDate.setDate(toDate.getDate() + 60)
      const to = toDate.toISOString().slice(0, 10)
      const rows = unwrapList(await apiFetch(`/api/v1/slots?from_date=${from}&to_date=${to}`))
      setSlots(rows.filter((sl) => sl.case_id === caseId))
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
  const pendingCount = booked.filter((s) => s.approval_status === 'PENDING_THERAPIST').length

  return (
    <div>
      <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
        Parent or admin bookings on your calendar for this case. Tap a session to confirm or decline a parent
        reschedule request, or use{' '}
        <Link to="/therapist/slots">Open Slots</Link> for full calendar management.
      </p>
      {pendingCount > 0 ? (
        <p style={{ fontSize: '0.85rem', color: '#b45309', marginBottom: 12 }}>
          {pendingCount} reschedule request{pendingCount === 1 ? '' : 's'} awaiting your confirmation.
        </p>
      ) : null}
      {booked.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No upcoming bookings for this case.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0 }}>
          {booked.map((sl) => (
            <li key={sl.id}>
              <button
                type="button"
                onClick={() => setDetailSlot(sl)}
                style={{
                  width: '100%',
                  textAlign: 'left',
                  padding: 12,
                  marginBottom: 8,
                  border: sl.approval_status === 'PENDING_THERAPIST' ? '1px solid #fcd34d' : '1px solid #e5e7eb',
                  borderRadius: 8,
                  background: sl.approval_status === 'PENDING_THERAPIST' ? '#fffbeb' : '#fff',
                  cursor: 'pointer',
                }}
              >
                <strong>{sl.slot_date}</strong> · {formatTime(sl.start_time)}–{formatTime(sl.end_time)}
                {sl.approval_status === 'PENDING_THERAPIST' ? (
                  <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#b45309', fontWeight: 600 }}>
                    Reschedule pending
                  </span>
                ) : (
                  <span style={{ marginLeft: 8, fontSize: '0.75rem', color: '#6b7280' }}>
                    {sl.booking_source || 'BOOKED'}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}

      <SlotDetailSheet
        open={!!detailSlot}
        slot={detailSlot}
        onClose={() => setDetailSlot(null)}
        onChanged={() => {
          setDetailSlot(null)
          load()
        }}
      />
    </div>
  )
}
