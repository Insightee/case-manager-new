import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { ScheduleWeekdayPicker } from '../scheduling/ScheduleWeekdayPicker.jsx'
import {
  ONGOING_MATERIALIZE_WEEKS,
  addDayWindow,
  normalizeTemplateConfig,
  removeDayWindow,
  updateDayWindow,
} from '../scheduling/scheduleTemplateUtils.js'
import { WEEKDAY_KEYS, WEEKDAY_LABELS } from '../scheduling/slotCalendarUtils.js'
import {
  addDaysIso,
  earlierWeekdayMessage,
  expandWeekdayDates,
  formatSkipMessage,
  includeEarlierSelectedDays,
  nWeeksRange,
  todayIsoIST,
} from '../scheduling/recurringRange.js'
import '../scheduling/schedule-sheet.css'

function normalizeTime(t) {
  if (!t) return '09:00:00'
  return t.length === 5 ? `${t}:00` : t
}

function addDaysStr(iso, n) {
  return addDaysIso(iso, n)
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
  const [notice, setNotice] = useState('')

  useEffect(() => {
    if (!open) return
    setTab(singleTab || initialTab)
    setError('')
    setNotice('')
    setApplyMode('this_week')
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/template${qs}`)
      .then((r) => setConfig(normalizeTemplateConfig(r.config)))
      .catch(() => setError('Could not load schedule'))

    setStartDate(weekStart || todayIsoIST())
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
    if (applyMode === 'ongoing') return addDaysStr(weekStart, ONGOING_MATERIALIZE_WEEKS * 7 - 1)
    return addDaysStr(weekEnd, (weeks - 1) * 7)
  }, [applyMode, weekStart, weekEnd, weeks])

  const bookRange = useMemo(() => {
    if (rangeMode === 'this_week') return { from: weekStart, to: weekEnd }
    const from = startDate || todayIsoIST()
    if (rangeMode === 'ongoing') {
      return { from, to: addDaysIso(from, ONGOING_MATERIALIZE_WEEKS * 7 - 1) }
    }
    return nWeeksRange(from, rangeWeeks)
  }, [rangeMode, weekStart, weekEnd, startDate, rangeWeeks])

  const bookPreview = useMemo(
    () => expandWeekdayDates(bookWeekdays, bookRange.from, bookRange.to),
    [bookWeekdays, bookRange],
  )
  const earlierNote = useMemo(
    () => (rangeMode === 'this_week' ? '' : earlierWeekdayMessage(bookWeekdays, bookRange.from)),
    [rangeMode, bookWeekdays, bookRange.from],
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
      const skipped = result?.skipped || []
      if (skipped.length || (booked === 0 && bookPreview.length > 0)) {
        setNotice(
          formatSkipMessage(booked, skipped) ||
            'No sessions were booked for those dates. Check leave days and times that are already taken.',
        )
        if (booked > 0) onApplied?.(result)
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
    return createPortal(
      <div className="sched-sheet" onClick={onClose}>
        <div className="sched-sheet__panel" role="dialog" aria-labelledby="sched-sheet-title" onClick={(e) => e.stopPropagation()}>
          <div className="sched-sheet__header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <h2 id="sched-sheet-title" className="sched-sheet__title">Schedule</h2>
            <button type="button" onClick={onClose} className="sched-sheet__btn sched-sheet__btn--ghost" style={{ minHeight: 40, padding: '0 12px' }}>
              Close
            </button>
          </div>
          <div className="sched-sheet__body" style={{ alignItems: 'center', justifyContent: 'center' }}>
            {error ? (
              <>
                <p className="text-sm font-semibold text-red-700">{error}</p>
                <button
                  type="button"
                  className="rounded-xl border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700"
                  onClick={() => {
                    setError('')
                    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
                    apiFetch(`/api/v1/slots/template${qs}`)
                      .then((r) => setConfig(normalizeTemplateConfig(r.config)))
                      .catch(() => setError('Could not load schedule'))
                  }}
                >
                  Retry
                </button>
              </>
            ) : (
              <p className="text-sm text-slate-500">Loading schedule…</p>
            )}
          </div>
        </div>
      </div>,
      document.body,
    )
  }

  return createPortal(
    <div className="sched-sheet" onClick={onClose}>
      <div
        className="sched-sheet__panel"
        role="dialog"
        aria-labelledby="sched-sheet-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sched-sheet__header">
          <h2 id="sched-sheet-title" className="sched-sheet__title">Schedule</h2>
          <p className="sched-sheet__sub">
            Set weekly availability, or book a recurring client pattern.
          </p>
          {showTabs ? (
            <div className="sched-sheet__tabs" role="tablist">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={tab === t.id}
                  onClick={() => setTab(t.id)}
                  className={`sched-sheet__tab${tab === t.id ? ' is-on' : ''}`}
                >
                  {t.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="sched-sheet__body">
          {error ? <p className="sched-sheet__note">{error}</p> : null}
          {notice ? <p className="sched-sheet__note">{notice}</p> : null}

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
                          <div key={wi} className="sched-sheet__times">
                            <label className="sched-sheet__field">
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
                              />
                            </label>
                            <label className="sched-sheet__field">
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
                          className="sched-sheet__hint"
                          style={{ fontWeight: 700, color: '#294e3f', textAlign: 'left' }}
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
              <div className="sched-sheet__card">
                {fixedCaseId ? (
                  <p className="sched-sheet__hint">Case #{fixedCaseId}</p>
                ) : (
                  <label className="sched-sheet__field">
                    Case
                    <select
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

              <div className="sched-sheet__card" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                <ScheduleWeekdayPicker value={bookWeekdays} onChange={setBookWeekdays} label="Repeat on" compact />
                <div className="sched-sheet__times">
                  <label className="sched-sheet__field">
                    Start
                    <input
                      type="time"
                      value={startTime}
                      onChange={(e) => setStartTime(e.target.value)}
                    />
                  </label>
                  <label className="sched-sheet__field">
                    End
                    <input
                      type="time"
                      value={endTime}
                      onChange={(e) => setEndTime(e.target.value)}
                    />
                  </label>
                </div>
              </div>

              <div className="sched-sheet__card" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <p className="sched-sheet__eyebrow">How long</p>
                {[
                  { id: 'this_week', label: 'This week only' },
                  { id: 'weeks', label: 'For N weeks from start date' },
                  { id: 'ongoing', label: 'Ongoing (until stopped on case)' },
                ].map((m) => (
                  <label key={m.id} className="sched-sheet__choice">
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
                  <label className="sched-sheet__field">
                    Weeks
                    <input
                      type="number"
                      min={1}
                      max={52}
                      value={rangeWeeks}
                      onChange={(e) => setRangeWeeks(Number(e.target.value))}
                    />
                  </label>
                ) : null}
                {rangeMode !== 'this_week' ? (
                  <label className="sched-sheet__field">
                    Start date
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                    />
                  </label>
                ) : null}
                {earlierNote ? (
                  <p className="sched-sheet__note">
                    {earlierNote}
                    <button
                      type="button"
                      onClick={() => setStartDate(includeEarlierSelectedDays(bookRange.from, bookWeekdays))}
                    >
                      Include them
                    </button>
                  </p>
                ) : null}
                {rangeMode === 'ongoing' ? (
                  <p className="sched-sheet__hint">
                    Books matching days through {bookRange.to} ({ONGOING_MATERIALIZE_WEEKS} weeks). Run again later to extend.
                  </p>
                ) : null}
                <p className="sched-sheet__hint">
                  {bookPreview.length} session date{bookPreview.length === 1 ? '' : 's'} from {bookRange.from} to {bookRange.to}, before leave or conflicts.
                </p>
              </div>
            </>
          )}
        </div>

        <div className="sched-sheet__footer">
          <button type="button" className="sched-sheet__btn sched-sheet__btn--ghost" onClick={onClose}>
            Cancel
          </button>
          {tab === 'availability' ? (
            <button
              type="button"
              disabled={saving}
              onClick={materializeAvailability}
              className="sched-sheet__btn sched-sheet__btn--primary"
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
              className="sched-sheet__btn sched-sheet__btn--primary"
            >
              {saving ? 'Booking…' : 'Book recurring sessions'}
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
