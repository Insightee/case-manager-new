import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTimeRange } from '../../lib/datetime.js'
import { addDaysIso, todayIsoIST } from '../scheduling/recurringRange.js'
import '../scheduling/schedule-sheet.css'
import {
  handoverBookingHintForTherapist,
  handoverPolicyFromTherapists,
  normalizeBookingErrorMessage,
  TRANSITION_HANDOVER_BANNER,
} from '../../lib/therapistTransitionBooking.js'

export function AdminScheduleSessionModal({ open, caseItem, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [therapists, setTherapists] = useState([])
  const [slots, setSlots] = useState([])
  const [fromDate, setFromDate] = useState(() => todayIsoIST())
  const [toDate, setToDate] = useState(() => addDaysIso(todayIsoIST(), 7))
  const [booking, setBooking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !caseItem) return
    apiFetch(`/api/v1/booking/therapists?case_id=${caseItem.id}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [open, caseItem])

  useEffect(() => {
    if (!therapistId || !open || !caseItem?.id) return
    apiFetch(
      `/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${fromDate}&to_date=${toDate}&case_id=${caseItem.id}`,
    )
      .then(setSlots)
      .catch(() => setSlots([]))
  }, [therapistId, fromDate, toDate, open, caseItem?.id])

  const handoverPolicy = handoverPolicyFromTherapists(therapists)
  const handoverHint = handoverBookingHintForTherapist(handoverPolicy, therapistId)

  if (!open || !caseItem) return null

  async function bookSlot(slotId) {
    setBooking(true)
    setError('')
    try {
      await apiFetch(`/api/v1/slots/${slotId}/book`, {
        method: 'POST',
        body: JSON.stringify({ case_id: caseItem.id }),
      })
      onDone?.()
      onClose()
    } catch (err) {
      setError(normalizeBookingErrorMessage(err.message) || 'Booking failed')
    } finally {
      setBooking(false)
    }
  }

  return createPortal(
    <div className="sched-modal" onClick={onClose}>
      <div className="sched-modal__panel" role="dialog" aria-labelledby="admin-schedule-title" onClick={(e) => e.stopPropagation()}>
        <h2 id="admin-schedule-title" className="text-lg font-semibold">Schedule session</h2>
        <p className="text-sm text-slate-500">
          {caseItem.case_code} · {caseItem.child_name}
        </p>
        {handoverPolicy ? (
          <p className="mt-2 text-sm text-sky-800 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2" role="status">
            {TRANSITION_HANDOVER_BANNER}
            {handoverHint ? ` ${handoverHint}` : ''}
          </p>
        ) : null}
        {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
        <div className="mt-4 space-y-3">
          <label className="block text-sm font-medium">
            Therapist
            <select
              className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
              value={therapistId}
              onChange={(e) => setTherapistId(e.target.value)}
            >
              <option value="">Select…</option>
              {therapists.map((t) => (
                <option key={t.therapist_user_id} value={t.therapist_user_id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </label>
          <div className="sched-sheet__times">
            <label className="sched-sheet__field">
              From
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
            </label>
            <label className="sched-sheet__field">
              To
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
            </label>
          </div>
          {therapistId && slots.length === 0 ? <p className="text-sm text-slate-500">No open slots in range.</p> : null}
          <ul className="max-h-48 space-y-1 overflow-y-auto">
            {slots.map((s) => (
              <li key={s.id}>
                <button
                  type="button"
                  disabled={booking}
                  className="w-full rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-left text-sm font-medium text-emerald-900 hover:bg-emerald-100 disabled:opacity-50"
                  onClick={() => bookSlot(s.id)}
                >
                  {formatDisplayDateTimeRange(s.slot_date, s.start_time, s.end_time)}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <button type="button" className="sched-sheet__btn sched-sheet__btn--ghost" style={{ width: '100%', marginTop: 16 }} onClick={onClose}>
          Close
        </button>
      </div>
    </div>,
    document.body,
  )
}
