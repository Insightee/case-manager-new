import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function ClientBookAppointmentPage({ cases }) {
  const [caseId, setCaseId] = useState('')
  const [therapists, setTherapists] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [fromDate, setFromDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [toDate, setToDate] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() + 14)
    return d.toISOString().slice(0, 10)
  })
  const [slots, setSlots] = useState([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (cases?.length && !caseId) {
      const first = cases[0]
      setCaseId(String(first.id ?? first.caseId ?? ''))
    }
  }, [cases, caseId])

  useEffect(() => {
    if (!caseId) return
    const numericCase = cases.find((c) => String(c.id) === caseId || String(c.caseId) === caseId)
    const idForApi = numericCase?.id ?? caseId
    apiFetch(`/api/v1/booking/therapists?case_id=${idForApi}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [caseId, cases])

  useEffect(() => {
    if (!therapistId) return
    apiFetch(`/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${fromDate}&to_date=${toDate}`)
      .then(setSlots)
      .catch(() => setSlots([]))
  }, [therapistId, fromDate, toDate])

  async function book(slotId) {
    setError('')
    setMessage('')
    const numericCase = cases.find((c) => String(c.caseId) === caseId || String(c.id) === caseId)
    const idForApi = numericCase?.id ?? Number(caseId)
    try {
      await apiFetch('/api/v1/booking/appointments', {
        method: 'POST',
        body: JSON.stringify({ slot_id: slotId, case_id: Number(idForApi) }),
      })
      setMessage('Appointment booked. Your care team will confirm details.')
      setSlots((prev) => prev.filter((s) => s.id !== slotId))
    } catch (err) {
      setError(err.message || 'Could not book')
    }
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-slate-600">Choose your child&apos;s case, therapist, and an available time.</p>
      {message ? <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p> : null}
      {error ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}
      <label className="block text-sm font-medium text-slate-700">
        Case
        <select className="mt-1 w-full rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm" value={caseId} onChange={(e) => setCaseId(e.target.value)}>
          {cases.map((c) => (
            <option key={c.caseId || c.id} value={c.caseId || c.id}>
              {c.childName} ({c.caseId})
            </option>
          ))}
        </select>
      </label>
      <label className="block text-sm font-medium text-slate-700">
        Therapist
        <select className="mt-1 w-full rounded-xl border border-[#E2E8F0] px-3 py-2 text-sm" value={therapistId} onChange={(e) => setTherapistId(e.target.value)}>
          <option value="">Select therapist…</option>
          {therapists.map((t) => (
            <option key={t.therapist_user_id} value={t.therapist_user_id}>
              {t.full_name}
            </option>
          ))}
        </select>
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-sm font-medium">
          From
          <input type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" />
        </label>
        <label className="text-sm font-medium">
          To
          <input type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} className="mt-1 w-full rounded-xl border px-3 py-2 text-sm" />
        </label>
      </div>
      <div>
        <h3 className="text-sm font-semibold text-slate-800">Available slots</h3>
        {therapistId && slots.length === 0 ? <p className="mt-2 text-sm text-slate-500">No slots in this range.</p> : null}
        <ul className="mt-2 space-y-2">
          {slots.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => book(s.id)}
                className="w-full rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 text-left text-sm font-semibold text-indigo-900 hover:bg-indigo-100"
              >
                {s.slot_date} · {s.start_time} – {s.end_time}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
