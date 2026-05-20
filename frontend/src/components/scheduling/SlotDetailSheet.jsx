import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { STATUS_LABELS } from './slotCalendarUtils.js'

export function SlotDetailSheet({ open, slot, onClose, onBook, onChanged }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  if (!open || !slot) return null

  const pendingTherapist = slot.status === 'BOOKED' && slot.approval_status === 'PENDING_THERAPIST'

  async function run(action) {
    setBusy(true)
    setError('')
    try {
      if (action === 'book') {
        onBook?.(slot)
        return
      }
      if (action === 'edit') {
        onChanged?.('edit', slot)
        return
      }
      if (action === 'confirm_reschedule') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/confirm-reschedule`, { method: 'POST' })
      } else if (action === 'decline_reschedule') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/decline-reschedule`, { method: 'POST' })
      } else if (action === 'cancel') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/cancel`, { method: 'POST' })
      } else if (action === 'block') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}/block`, { method: 'POST' })
      } else if (action === 'delete') {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}`, { method: 'DELETE' })
      }
      onChanged?.('refresh')
      onClose()
    } catch (err) {
      setError(err.message || 'Action failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-6 shadow-xl sm:rounded-2xl">
        <p className="text-xs font-semibold uppercase text-slate-500">{STATUS_LABELS[slot.status] || slot.status}</p>
        <h2 className="text-lg font-bold text-slate-900">
          {slot.slot_date} · {slot.start_time}–{slot.end_time}
        </h2>
        {slot.child_name || slot.case_code ? (
          <p className="mt-1 text-sm text-slate-600">{slot.child_name || slot.case_code}</p>
        ) : null}
        {pendingTherapist ? (
          <p className="mt-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
            Parent requested this time change. Confirm to keep the new slot, or decline to revert to the previous
            booking.
          </p>
        ) : null}
        {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
        <div className="mt-4 flex flex-col gap-2">
          {slot.status === 'AVAILABLE' && (
            <>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl bg-indigo-600 text-sm font-semibold text-white"
                onClick={() => run('book')}
              >
                Book client
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl border text-sm font-semibold"
                onClick={() => run('edit')}
              >
                Edit time
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl border text-sm font-semibold"
                onClick={() => run('block')}
              >
                Block
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl border border-red-200 text-sm font-semibold text-red-700"
                onClick={() => run('delete')}
              >
                Remove slot
              </button>
            </>
          )}
          {slot.status === 'BOOKED' && (
            <>
              {pendingTherapist ? (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    className="min-h-[44px] rounded-xl bg-indigo-600 text-sm font-semibold text-white"
                    onClick={() => run('confirm_reschedule')}
                  >
                    Confirm new time
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="min-h-[44px] rounded-xl border border-amber-300 text-sm font-semibold text-amber-900"
                    onClick={() => run('decline_reschedule')}
                  >
                    Decline reschedule
                  </button>
                </>
              ) : null}
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl border text-sm font-semibold"
                onClick={() => run('edit')}
              >
                Edit time
              </button>
              <button
                type="button"
                disabled={busy}
                className="min-h-[44px] rounded-xl border text-sm font-semibold"
                onClick={() => run('cancel')}
              >
                Cancel booking
              </button>
            </>
          )}
          {slot.status === 'BLOCKED' && (
            <button
              type="button"
              disabled={busy}
              className="min-h-[44px] rounded-xl border text-sm font-semibold"
              onClick={() => run('delete')}
            >
              Unblock / remove
            </button>
          )}
          <button type="button" className="min-h-[44px] text-sm text-slate-500" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
