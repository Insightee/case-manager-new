import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ScheduleWeekdayPicker } from '../scheduling/ScheduleWeekdayPicker.jsx'
import {
  ONGOING_MATERIALIZE_WEEKS,
  addDayWindow,
  normalizeTemplateConfig,
  removeDayWindow,
  updateDayWindow,
} from '../scheduling/scheduleTemplateUtils.js'
import { WEEKDAY_KEYS, WEEKDAY_LABELS, dateStr } from '../scheduling/slotCalendarUtils.js'

function normalizeTime(t) {
  if (!t) return '09:00:00'
  return t.length === 5 ? `${t}:00` : t
}

function addDaysStr(iso, n) {
  const d = new Date(iso + 'T12:00:00')
  d.setDate(d.getDate() + n)
  return dateStr(d)
}

function previewDates(weekdays, fromStr, toStr) {
  const out = []
  const start = new Date(fromStr + 'T12:00:00')
  const end = new Date(toStr + 'T12:00:00')
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end < start) return out
  const keys = new Set(weekdays)
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const wk = WEEKDAY_KEYS[d.getDay() === 0 ? 6 : d.getDay() - 1]
    if (keys.has(wk)) out.push(dateStr(d))
  }
  return out
}

const TABS = [
  { id: 'availability', label: 'Weekly availability' },
  { id: 'recurring', label: 'Book recurring' },
]

const APPLY_MODES = [
  { id: 'this_week', label: 'This week only' },
  { id: 'weeks', label: 'For N weeks' },
  { id: 'ongoing', label: 'Ongoing (until you stop)' },
]

export function WeeklyScheduleDrawer({
  open,
  onClose,
  weekStart,
  weekEnd,
  therapistId,
  onApplied,
  /** 'availability' | 'recurring' — opens on Book recurring when launched from old Quick recurring */
  initialTab = 'availability',
  fixedCaseId,
  therapistUserId: therapistUserIdProp,
  /** Hide tab bar when only one flow is needed */
  singleTab,
}) {
  const [tab, setTab] = useState(initialTab)
  const [config, setConfig] = useState(null)
  const [applyMode, setApplyMode] = useState('this_week')
  const [weeks, setWeeks] = useState(4)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // Recurring book tab
  const [meId, setMeId] = useState(null)
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [bookWeekdays, setBookWeekdays] = useState(['mon', 'wed', 'fri'])
  const [startTime, setStartTime] = useState('10:00')
  const [endTime, setEndTime] = useState('11:00')
  const [rangeMode, setRangeMode] = useState('this_week')
  const [rangeWeeks, setRangeWeeks] = useState(4)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  useEffect(() => {
    if (!open) return
    setTab(singleTab || initialTab)
    setError('')
    setApplyMode('this_week')
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/template${qs}`)
      .then((r) => setConfig(normalizeTemplateConfig(r.config)))
      .catch(() => setError('Could not load schedule'))

    const today = new Date()
    setStartDate(weekStart || today.toISOString().slice(0, 10))
    const end = new Date(today)
    end.setMonth(end.getMonth() + 1)
    setEndDate(end.toISOString().slice(0, 10))
    if (fixedCaseId) setCaseId(String(fixedCaseId))

    apiFetch('/api/v1/auth/me')
      .then((u) => setMeId(u.id))
      .catch(() => {})

    const caseQs = therapistUserIdProp || therapistId ? `?therapist_id=${therapistUserIdProp || therapistId}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${caseQs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, therapistId, fixedCaseId, therapistUserIdProp, initialTab, singleTab, weekStart])

  const materializeToDate = useMemo(() => {
    if (applyMode === 'this_week') return weekEnd
    if (applyMode === 'ongoing') return addDaysStr(weekStart, ONGOING_MATERIALIZE_WEEKS * 7)
    return addDaysStr(weekEnd, (weeks - 1) * 7)
  }, [applyMode, weekStart, weekEnd, weeks])

  const bookRange = useMemo(() => {
    if (rangeMode === 'this_week') return { from: weekStart, to: weekEnd }
    if (rangeMode === 'ongoing') {
      return { from: startDate || weekStart, to: addDaysStr(startDate || weekStart, ONGOING_MATERIALIZE_WEEKS * 7) }
    }
    return { from: startDate, to: addDaysStr(startDate, rangeWeeks * 7 - 1) }
  }, [rangeMode, weekStart, weekEnd, startDate, rangeWeeks])

  const bookPreview = useMemo(
    () => previewDates(bookWeekdays, bookRange.from, bookRange.to),
    [bookWeekdays, bookRange],
  )

  if (!open) return null

  function updateDay(key, patch) {
    setConfig((prev) => ({
      ...prev,
      days: { ...prev.days, [key]: { ...prev.days[key], ...patch } },
    }))
  }

  function toggleDayEnabled(key) {
    const day = config.days[key]
    updateDay(key, { enabled: !day.enabled })
  }

  async function saveTemplate(extra = {}) {
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    await apiFetch(`/api/v1/slots/template${qs}`, {
      method: 'PATCH',
      body: JSON.stringify({ config: { ...config, ...extra } }),
    })
  }

  async function materializeAvailability() {
    setSaving(true)
    setError('')
    try {
      const ongoing = applyMode === 'ongoing'
      await saveTemplate({
        ongoing_enabled: ongoing,
        ongoing_horizon_weeks: ONGOING_MATERIALIZE_WEEKS,
      })
      await apiFetch('/api/v1/slots/materialize', {
        method: 'POST',
        body: JSON.stringify({
          from_date: weekStart,
          to_date: materializeToDate,
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

  async function stopOngoing() {
    setSaving(true)
    setError('')
    try {
      await saveTemplate({ ongoing_enabled: false })
      setConfig((c) => ({ ...c, ongoing_enabled: false }))
    } catch (err) {
      setError(err.message || 'Could not update schedule')
    } finally {
      setSaving(false)
    }
  }

  async function bookRecurring() {
    const cid = fixedCaseId ?? Number(caseId)
    const tid = Number(therapistUserIdProp || therapistId || meId)
    if (!cid || !tid) {
      setError('Select a case')
      return
    }
    if (!bookWeekdays.length) {
      setError('Select at least one weekday')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch('/api/v1/scheduling/assign-recurring', {
        method: 'POST',
        body: JSON.stringify({
          case_id: cid,
          therapist_user_id: tid,
          weekdays: bookWeekdays,
          start_time: normalizeTime(startTime),
          end_time: normalizeTime(endTime),
          start_date: bookRange.from,
          end_date: bookRange.to,
        }),
      })
      const booked = result?.booked_slot_count ?? 0
      if (booked === 0 && bookPreview.length > 0) {
        setError(
          'No sessions were booked for those dates. Check leave days, time conflicts, and that the week range matches the calendar.',
        )
        return
      }
      onApplied?.(result)
      onClose()
    } catch (err) {
      setError(err.message || 'Could not book recurring sessions')
    } finally {
      setSaving(false)
    }
  }

  const showTabs = !singleTab

  if (!config) {
    return (
      <div className="fixed inset-0 z-[70] flex justify-end bg-slate-900/30" onClick={onClose}>
        <div className="h-full w-full max-w-lg bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
          <p className="text-slate-500">Loading…</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[70] flex justify-end bg-slate-900/30" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-lg flex-col bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 border-b border-slate-100 bg-white px-5 py-4">
          <h2 className="text-lg font-bold text-slate-900">Schedule</h2>
          <p className="mt-0.5 text-sm text-slate-500">
            Same layout as add slot — set availability or book a recurring client pattern.
          </p>
          {showTabs ? (
            <div className="mt-3 flex rounded-lg border border-slate-200 p-0.5">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setTab(t.id)}
                  className={`flex-1 rounded-md py-1.5 text-xs font-semibold ${
                    tab === t.id ? 'bg-indigo-600 text-white' : 'text-slate-600'
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {error ? <p className="text-sm text-red-700">{error}</p> : null}

          {tab === 'availability' && (
            <>
              {config.ongoing_enabled ? (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <p className="font-semibold">Ongoing availability is on</p>
                  <p className="mt-1 text-xs">
                    Re-apply ongoing to extend open slots, or stop when you no longer want auto-style weeks ahead.
                  </p>
                  <button
                    type="button"
                    className="mt-2 text-xs font-semibold text-amber-800 underline"
                    onClick={stopOngoing}
                    disabled={saving}
                  >
                    Stop ongoing schedule
                  </button>
                </div>
              ) : null}

              <div className="rounded-xl border border-slate-200 p-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Session length</p>
                <select
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  value={config.slot_duration_minutes || 60}
                  onChange={(e) => setConfig({ ...config, slot_duration_minutes: Number(e.target.value) })}
                >
                  <option value={30}>30 min</option>
                  <option value={60}>60 min</option>
                  <option value={90}>90 min</option>
                  <option value={120}>2 h</option>
                </select>
              </div>

              {WEEKDAY_KEYS.map((key, i) => {
                const day = config.days[key]
                return (
                  <div key={key} className="rounded-xl border border-slate-200 p-4">
                    <label className="flex items-center gap-2 font-semibold text-slate-800">
                      <input type="checkbox" checked={!!day.enabled} onChange={() => toggleDayEnabled(key)} />
                      {WEEKDAY_LABELS[i]}
                    </label>
                    {day.enabled ? (
                      <div className="mt-3 space-y-2">
                        {day.windows.map((win, wi) => (
                          <div key={wi} className="flex items-end gap-2">
                            <label className="flex-1 text-xs text-slate-600">
                              From
                              <input
                                type="time"
                                value={win.start}
                                onChange={(e) =>
                                  setConfig((prev) => ({
                                    ...prev,
                                    days: {
                                      ...prev.days,
                                      [key]: updateDayWindow(prev.days[key], wi, 'start', e.target.value),
                                    },
                                  }))
                                }
                                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                              />
                            </label>
                            <label className="flex-1 text-xs text-slate-600">
                              To
                              <input
                                type="time"
                                value={win.end}
                                onChange={(e) =>
                                  setConfig((prev) => ({
                                    ...prev,
                                    days: {
                                      ...prev.days,
                                      [key]: updateDayWindow(prev.days[key], wi, 'end', e.target.value),
                                    },
                                  }))
                                }
                                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                              />
                            </label>
                            {day.windows.length > 1 ? (
                              <button
                                type="button"
                                className="mb-1 rounded-lg border border-slate-200 px-2 py-1.5 text-xs text-slate-600"
                                onClick={() =>
                                  setConfig((prev) => ({
                                    ...prev,
                                    days: { ...prev.days, [key]: removeDayWindow(prev.days[key], wi) },
                                  }))
                                }
                              >
                                Remove
                              </button>
                            ) : null}
                          </div>
                        ))}
                        <button
                          type="button"
                          className="text-xs font-semibold text-indigo-600 hover:underline"
                          onClick={() =>
                            setConfig((prev) => ({
                              ...prev,
                              days: { ...prev.days, [key]: addDayWindow(prev.days[key]) },
                            }))
                          }
                        >
                          + Add time block (e.g. break between sessions)
                        </button>
                      </div>
                    ) : null}
                  </div>
                )
              })}

              <div className="rounded-xl border border-slate-200 p-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Apply availability</p>
                <div className="space-y-2">
                  {APPLY_MODES.map((m) => (
                    <label key={m.id} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                      <input
                        type="radio"
                        name="applyMode"
                        checked={applyMode === m.id}
                        onChange={() => setApplyMode(m.id)}
                      />
                      {m.label}
                    </label>
                  ))}
                </div>
                {applyMode === 'weeks' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Number of weeks
                    <input
                      type="number"
                      min={1}
                      max={52}
                      value={weeks}
                      onChange={(e) => setWeeks(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </label>
                ) : null}
                {applyMode === 'ongoing' ? (
                  <p className="text-xs text-slate-500">
                    Generates open slots for the next {ONGOING_MATERIALIZE_WEEKS} weeks ({weekStart} →{' '}
                    {materializeToDate}). Run again later to extend.
                  </p>
                ) : null}
                <p className="text-xs text-slate-500">
                  Week shown on calendar: {weekStart} – {weekEnd}
                  {applyMode !== 'this_week' ? ` · applying through ${materializeToDate}` : ''}
                </p>
              </div>
            </>
          )}

          {tab === 'recurring' && (
            <>
              <div className="rounded-xl border border-slate-200 p-4">
                {fixedCaseId ? (
                  <p className="text-sm text-slate-600">Case #{fixedCaseId}</p>
                ) : (
                  <label className="block text-sm font-medium text-slate-700">
                    Case
                    <select
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      value={caseId}
                      onChange={(e) => setCaseId(e.target.value)}
                    >
                      <option value="">Select case…</option>
                      {cases.map((c) => (
                        <option key={c.case_id} value={c.case_id}>
                          {c.case_code} · {c.child_name || 'Client'}
                          {c.pending_allotment ? ' (under review)' : ''}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              <div className="rounded-xl border border-slate-200 p-4 space-y-4">
                <ScheduleWeekdayPicker value={bookWeekdays} onChange={setBookWeekdays} label="Repeat on" compact />
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm font-medium text-slate-700">
                    Start
                    <input
                      type="time"
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                    />
                  </label>
                  <label className="text-sm font-medium text-slate-700">
                    End
                    <input
                      type="time"
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                    />
                  </label>
                </div>
              </div>

              <div className="rounded-xl border border-slate-200 p-4 space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">How long</p>
                {[
                  { id: 'this_week', label: 'This week only' },
                  { id: 'weeks', label: 'For N weeks from start date' },
                  { id: 'ongoing', label: 'Ongoing (until stopped on case)' },
                ].map((m) => (
                  <label key={m.id} className="flex items-center gap-2 text-sm cursor-pointer">
                    <input
                      type="radio"
                      name="rangeMode"
                      checked={rangeMode === m.id}
                      onChange={() => setRangeMode(m.id)}
                    />
                    {m.label}
                  </label>
                ))}
                {rangeMode === 'weeks' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Weeks
                    <input
                      type="number"
                      min={1}
                      max={52}
                      value={rangeWeeks}
                      onChange={(e) => setRangeWeeks(Number(e.target.value))}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </label>
                ) : null}
                {rangeMode !== 'this_week' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Start date
                    <input
                      type="date"
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                ) : null}
                {rangeMode === 'ongoing' ? (
                  <p className="text-xs text-slate-500">
                    Books matching slots through {bookRange.to} ({ONGOING_MATERIALIZE_WEEKS} weeks). Extend by
                    running again or end via case assignment changes.
                  </p>
                ) : null}
                <p className="text-xs text-slate-500">~{bookPreview.length} session dates (before conflicts).</p>
              </div>
            </>
          )}
        </div>

        <div className="border-t border-slate-100 p-4 flex flex-col gap-2">
          <button type="button" className="rounded-xl border py-2.5 text-sm font-semibold text-slate-700" onClick={onClose}>
            Cancel
          </button>
          {tab === 'availability' ? (
            <button
              type="button"
              disabled={saving}
              onClick={materializeAvailability}
              className="rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving
                ? 'Applying…'
                : applyMode === 'this_week'
                  ? 'Apply to this week'
                  : applyMode === 'ongoing'
                    ? 'Apply ongoing'
                    : `Apply for ${weeks} weeks`}
            </button>
          ) : (
            <button
              type="button"
              disabled={saving || (!fixedCaseId && !caseId)}
              onClick={bookRecurring}
              className="rounded-xl bg-indigo-600 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {saving ? 'Booking…' : 'Book recurring sessions'}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
