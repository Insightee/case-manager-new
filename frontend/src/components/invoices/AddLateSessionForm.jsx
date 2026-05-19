import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { monthDateBounds } from './invoiceUtils.js'

export function AddLateSessionForm({ caseId, month, onAdded, onCancel }) {
  const bounds = monthDateBounds(month)
  const [open, setOpen] = useState(false)
  const [sessionDate, setSessionDate] = useState(bounds.min)
  const [startTime, setStartTime] = useState('10:00')
  const [endTime, setEndTime] = useState('11:00')
  const [activities, setActivities] = useState('')
  const [observations, setObservations] = useState('')
  const [lateReason, setLateReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await apiFetch('/api/v1/invoices/late-sessions', {
        method: 'POST',
        body: JSON.stringify({
          case_id: caseId,
          month,
          session_date: sessionDate,
          start_time: `${startTime}:00`,
          end_time: `${endTime}:00`,
          attendance_status: 'present',
          activities_done: activities.trim() || null,
          observations: observations.trim() || null,
          late_reason: lateReason.trim(),
        }),
      })
      setOpen(false)
      setLateReason('')
      setActivities('')
      onAdded?.()
    } catch (err) {
      setError(err.message || 'Could not add session')
    } finally {
      setSaving(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="mt-3 text-sm font-semibold text-indigo-600 hover:text-indigo-800"
        onClick={() => setOpen(true)}
      >
        + Add forgotten session
      </button>
    )
  }

  return (
    <form className="mt-3 rounded-xl border border-dashed border-amber-200 bg-amber-50/50 p-4" onSubmit={handleSubmit}>
      <p className="mb-3 text-sm font-semibold text-amber-900">Add session (requires admin approval)</p>
      {error ? <p className="mb-2 text-sm text-red-700">{error}</p> : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs font-medium text-slate-700 sm:col-span-2">
          Session date
          <input
            type="date"
            required
            min={bounds.min}
            max={bounds.max}
            value={sessionDate}
            onChange={(e) => setSessionDate(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-xs font-medium text-slate-700">
          Start
          <input
            type="time"
            required
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-xs font-medium text-slate-700">
          End
          <input
            type="time"
            required
            value={endTime}
            onChange={(e) => setEndTime(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-xs font-medium text-slate-700 sm:col-span-2">
          Activities
          <input
            value={activities}
            onChange={(e) => setActivities(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
            placeholder="What was done in the session"
          />
        </label>
        <label className="block text-xs font-medium text-slate-700 sm:col-span-2">
          Reason for late entry (required)
          <textarea
            required
            minLength={5}
            rows={2}
            value={lateReason}
            onChange={(e) => setLateReason(e.target.value)}
            className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
            placeholder="e.g. Logged after clinic visit; parent confirmed attendance"
          />
        </label>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={saving}
          className="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {saving ? 'Saving…' : 'Add session'}
        </button>
        <button
          type="button"
          className="rounded-lg border border-[#E2E8F0] bg-white px-3 py-2 text-sm font-semibold text-slate-700"
          onClick={() => {
            setOpen(false)
            onCancel?.()
          }}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
