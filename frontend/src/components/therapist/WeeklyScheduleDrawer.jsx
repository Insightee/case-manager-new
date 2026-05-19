import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { WEEKDAY_KEYS, WEEKDAY_LABELS } from './slotCalendarUtils.js'

export function WeeklyScheduleDrawer({ open, onClose, weekStart, weekEnd, therapistId, onApplied }) {
  const [config, setConfig] = useState(null)
  const [weeks, setWeeks] = useState(4)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/template${qs}`)
      .then((r) => setConfig(r.config))
      .catch(() => setError('Could not load schedule'))
  }, [open, therapistId])

  if (!open) return null

  function updateDay(key, field, value) {
    setConfig((prev) => ({
      ...prev,
      days: {
        ...prev.days,
        [key]: { ...prev.days[key], [field]: value },
      },
    }))
  }

  async function saveTemplate() {
    setSaving(true)
    setError('')
    try {
      const qs = therapistId ? `?therapist_id=${therapistId}` : ''
      await apiFetch(`/api/v1/slots/template${qs}`, {
        method: 'PATCH',
        body: JSON.stringify({ config }),
      })
    } catch (err) {
      setError(err.message || 'Save failed')
      setSaving(false)
      return
    }
    setSaving(false)
  }

  async function materialize(weekCount) {
    await saveTemplate()
    setSaving(true)
    setError('')
    try {
      const end = new Date(weekEnd)
      if (weekCount > 1) {
        end.setDate(end.getDate() + (weekCount - 1) * 7)
      }
      const to = end.toISOString().slice(0, 10)
      await apiFetch('/api/v1/slots/materialize', {
        method: 'POST',
        body: JSON.stringify({
          from_date: weekStart,
          to_date: to,
          therapist_id: therapistId || undefined,
        }),
      })
      onApplied?.()
      onClose()
    } catch (err) {
      setError(err.message || 'Could not apply schedule')
    } finally {
      setSaving(false)
    }
  }

  if (!config) {
    return (
      <div className="fixed inset-0 z-[70] flex justify-end bg-slate-900/30" onClick={onClose}>
        <div className="h-full w-full max-w-md bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
          <p className="text-slate-500">Loading…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[70] flex justify-end bg-slate-900/30" onClick={onClose}>
      <div className="flex h-full w-full max-w-md flex-col bg-white shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="border-b border-[#E2E8F0] px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-900">Weekly schedule</h2>
          <p className="text-sm text-slate-500">Default 9 AM – 6 PM. Apply to generate open slots.</p>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error ? <p className="text-sm text-red-700">{error}</p> : null}
          <label className="block text-sm font-medium text-slate-700">
            Slot length (minutes)
            <select
              className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
              value={config.slot_duration_minutes || 30}
              onChange={(e) => setConfig({ ...config, slot_duration_minutes: Number(e.target.value) })}
            >
              <option value={30}>30 min</option>
              <option value={60}>60 min</option>
            </select>
          </label>
          {WEEKDAY_KEYS.map((key, i) => {
            const day = config.days[key] || {}
            return (
              <div key={key} className="rounded-lg border border-[#E2E8F0] p-3">
                <label className="flex items-center gap-2 font-semibold text-slate-800">
                  <input
                    type="checkbox"
                    checked={!!day.enabled}
                    onChange={(e) => updateDay(key, 'enabled', e.target.checked)}
                  />
                  {WEEKDAY_LABELS[i]}
                </label>
                {day.enabled ? (
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <input
                      type="time"
                      value={day.start || '09:00'}
                      onChange={(e) => updateDay(key, 'start', e.target.value)}
                      className="rounded-lg border border-[#E2E8F0] px-2 py-1 text-sm"
                    />
                    <input
                      type="time"
                      value={day.end || '18:00'}
                      onChange={(e) => updateDay(key, 'end', e.target.value)}
                      className="rounded-lg border border-[#E2E8F0] px-2 py-1 text-sm"
                    />
                  </div>
                ) : null}
              </div>
            )
          })}
          <label className="block text-sm font-medium text-slate-700">
            Repeat for weeks
            <input
              type="number"
              min={1}
              max={12}
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-[#E2E8F0] px-3 py-2 text-sm"
            />
          </label>
        </div>
        <div className="border-t border-[#E2E8F0] p-4 flex flex-col gap-2">
          <button
            type="button"
            disabled={saving}
            onClick={() => materialize(1)}
            className="rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
          >
            Apply to this week
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => materialize(weeks)}
            className="rounded-xl border border-indigo-200 bg-indigo-50 py-2.5 text-sm font-semibold text-indigo-800 disabled:opacity-50"
          >
            Apply for {weeks} weeks
          </button>
        </div>
      </div>
    </div>
  )
}
