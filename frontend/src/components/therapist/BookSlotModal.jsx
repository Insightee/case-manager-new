import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function BookSlotModal({ open, slot, therapistId, onClose, onBooked }) {
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setError('')
    setCaseId('')
    setSelectedCase(null)
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${qs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, therapistId])

  if (!open || !slot) return null

  async function handleSubmit(e) {
    e.preventDefault()
    if (!caseId) return
    setLoading(true)
    setError('')
    try {
      await apiFetch(`/api/v1/slots/${slot.id}/book`, {
        method: 'POST',
        body: JSON.stringify({ case_id: Number(caseId) }),
      })
      onBooked?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Booking failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-900">Book client</h2>
        <p className="mt-1 text-sm text-slate-500">
          {slot.slot_date} · {slot.start_time}–{slot.end_time}
        </p>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700">
            Case
            <select
              className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
              value={caseId}
              onChange={(e) => {
                const id = e.target.value
                setCaseId(id)
                setSelectedCase(cases.find((c) => String(c.case_id) === id) || null)
              }}
              required
            >
              <option value="">Select case…</option>
              {cases.map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_code} · {c.child_name || 'Client'}
                </option>
              ))}
            </select>
          </label>
          {selectedCase?.service_address?.formatted ? (
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700">
              <p className="font-medium text-slate-900">Visit address</p>
              <p className="mt-1">{selectedCase.service_address.formatted}</p>
              {selectedCase.maps_url ? (
                <a
                  href={selectedCase.maps_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-block font-semibold text-indigo-600 hover:underline"
                >
                  Open in Google Maps
                </a>
              ) : null}
            </div>
          ) : null}
          <div className="flex gap-2">
            <button
              type="button"
              className="flex-1 rounded-xl border border-[#E2E8F0] py-2.5 text-sm font-semibold text-slate-700"
              onClick={onClose}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading ? 'Booking…' : 'Confirm'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
