import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function AdminScheduleSessionModal({ open, caseItem, onClose, onDone }) {
  const [therapistId, setTherapistId] = useState('')
  const [therapists, setTherapists] = useState([])
  const [slots, setSlots] = useState([])
  const [fromDate, setFromDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [toDate, setToDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 7)
    return d.toISOString().slice(0, 10)
  })
  const [booking, setBooking] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open || !caseItem) return
    apiFetch(`/api/v1/booking/therapists?case_id=${caseItem.id}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [open, caseItem])

  useEffect(() => {
    if (!therapistId || !open) return
    apiFetch(`/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${fromDate}&to_date=${toDate}`)
      .then(setSlots)
      .catch(() => setSlots([]))
  }, [therapistId, fromDate, toDate, open])

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
      setError(err.message || 'Booking failed')
    } finally {
      setBooking(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[85] flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border bg-white p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold">Schedule session</h2>
        <p className="text-sm text-slate-500">
          {caseItem.case_code} · {caseItem.child_name}
        </p>
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
          <div className="grid grid-cols-2 gap-2">
            <label className="text-sm">
              From
              <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="mt-1 w-full rounded-lg border px-2 py-1 text-sm" />
            </label>
            <label className="text-sm">
              To
              <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="mt-1 w-full rounded-lg border px-2 py-1 text-sm" />
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
                  {s.slot_date} · {s.start_time}–{s.end_time}
                </button>
              </li>
            ))}
          </ul>
        </div>
        <button type="button" className="mt-4 w-full rounded-xl border py-2 text-sm font-semibold" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  )
}
