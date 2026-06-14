import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTimeRange } from '../../lib/datetime.js'
import { mapSlotToCalendarEvent } from '../../lib/googleCalendar.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'

export function BookSlotModal({ open, slot, therapistId, onClose, onBooked }) {
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  // TODO: re-enable with new client invite tab — clientName, clientEmail, tab state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successState, setSuccessState] = useState(null)

  useEffect(() => {
    if (!open) return
    setError('')
    setSuccessState(null)
    setCaseId('')
    setSelectedCase(null)
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${qs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, therapistId])

  function finishSuccess() {
    setSuccessState(null)
    onClose()
  }

  if (!open || !slot) return null

  if (successState) {
    return (
      <BookingSuccessSheet
        open
        title="Session booked"
        event={successState.event}
        detailLines={successState.detailLines}
        onClose={finishSuccess}
      />
    )
  }

  async function handleBookExisting(e) {
    e.preventDefault()
    if (!caseId) return
    setLoading(true)
    setError('')
    try {
      await apiFetch(`/api/v1/scheduling/slots/${slot.id}/book`, {
        method: 'POST',
        body: JSON.stringify({ case_id: Number(caseId) }),
      })
      const event = mapSlotToCalendarEvent(
        {
          ...slot,
          child_name: selectedCase?.child_name,
          case_code: selectedCase?.case_code,
        },
        { deepLinkPath: '/therapist/slots' },
      )
      const detailLines = [
        selectedCase?.child_name ? `Client: ${selectedCase.child_name}` : null,
        selectedCase?.case_code ? `Case: ${selectedCase.case_code}` : null,
      ].filter(Boolean)
      setSuccessState({ event, detailLines })
      onBooked?.()
    } catch (err) {
      setError(err.message || 'Booking failed')
    } finally {
      setLoading(false)
    }
  }

  // TODO: re-enable when therapist self-onboarding is allowed again
  /*
  async function handleInvite(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await apiFetch(`/api/v1/scheduling/slots/${slot.id}/invite-client`, {
        method: 'POST',
        body: JSON.stringify({
          client_name: clientName.trim(),
          client_email: clientEmail.trim(),
        }),
      })
      onBooked?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Invite failed')
    } finally {
      setLoading(false)
    }
  }
  */

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/40 p-4" onClick={onClose}>
      <div
        className="w-full max-w-md rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-slate-900">Book slot</h2>
        <p className="mt-1 text-sm text-slate-500">
          {formatDisplayDateTimeRange(slot.slot_date || slot.date, slot.start_time, slot.end_time)}
        </p>

        {/* TODO: re-enable when therapist self-onboarding is allowed again — tab switcher
        <div className="mt-4 flex rounded-lg border border-slate-200 p-0.5">
          <button type="button" ... onClick={() => setTab('existing')}>Existing case</button>
          <button type="button" ... onClick={() => setTab('invite')}>New client invite</button>
        </div>
        */}

        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        <form className="mt-4 space-y-4" onSubmit={handleBookExisting}>
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
        {/* TODO: re-enable when therapist self-onboarding is allowed again — new client invite form
        ) : (
          <form className="mt-4 space-y-4" onSubmit={handleInvite}>...</form>
        )}
        */}
      </div>
    </div>
  )
}
