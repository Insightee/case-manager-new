import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { dateStr } from './slotCalendarUtils.js'

const DURATION_PRESETS = [30, 60]

function addMinutesToTime(hm, minutes) {
  const [h, m] = hm.split(':').map(Number)
  const total = h * 60 + m + minutes
  const nh = Math.floor(total / 60) % 24
  const nm = total % 60
  return `${String(nh).padStart(2, '0')}:${String(nm).padStart(2, '0')}`
}

export function SlotEditSheet({ open, mode, slot, cellDate, cellHour, therapistId, onClose, onSaved }) {
  const [startTime, setStartTime] = useState('09:00')
  const [duration, setDuration] = useState(60)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setError('')
    if (mode === 'edit' && slot) {
      setStartTime(slot.start_time)
      const dur =
        slot.slot_duration_minutes ||
        (() => {
          const [sh, sm] = slot.start_time.split(':').map(Number)
          const [eh, em] = slot.end_time.split(':').map(Number)
          return eh * 60 + em - (sh * 60 + sm)
        })()
      setDuration(dur >= 60 ? 60 : 30)
      setNotes(slot.notes || '')
    } else if (cellDate != null && cellHour != null) {
      setStartTime(`${String(cellHour).padStart(2, '0')}:00`)
      setDuration(60)
      setNotes('')
    }
  }, [open, mode, slot, cellDate, cellHour])

  if (!open) return null

  const slotDate = mode === 'edit' && slot ? slot.slot_date : cellDate ? dateStr(cellDate) : ''
  const endTime = addMinutesToTime(startTime, duration)

  async function handleSave(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (mode === 'add') {
        await apiFetch('/api/v1/scheduling/slots', {
          method: 'POST',
          body: JSON.stringify({
            slot_date: slotDate,
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
            therapist_id: therapistId || undefined,
          }),
        })
      } else if (slot) {
        await apiFetch(`/api/v1/scheduling/slots/${slot.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
          }),
        })
      }
      onSaved?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Could not save slot')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center">
      <div className="w-full max-w-md rounded-t-2xl bg-white p-6 shadow-xl sm:rounded-2xl">
        <h2 className="text-lg font-bold text-slate-900">{mode === 'add' ? 'Add slot' : 'Edit slot'}</h2>
        <p className="mt-1 text-sm text-slate-500">{slotDate}</p>
        {error ? <p className="mt-2 text-sm text-red-700">{error}</p> : null}
        <form className="mt-4 space-y-4" onSubmit={handleSave}>
          <label className="block text-sm font-medium text-slate-700">
            Start time
            <input
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
              required
            />
          </label>
          <div>
            <span className="text-sm font-medium text-slate-700">Duration</span>
            <div className="mt-2 flex gap-2">
              {DURATION_PRESETS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDuration(d)}
                  className={`min-h-[44px] flex-1 rounded-lg border text-sm font-semibold ${
                    duration === d ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-200'
                  }`}
                >
                  {d} min
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-slate-500">Ends {endTime}</p>
          </div>
          <label className="block text-sm font-medium text-slate-700">
            Notes
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
            />
          </label>
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="min-h-[44px] flex-1 rounded-xl border border-slate-200 text-sm font-semibold"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="min-h-[44px] flex-1 rounded-xl bg-indigo-600 text-sm font-semibold text-white disabled:opacity-60"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
