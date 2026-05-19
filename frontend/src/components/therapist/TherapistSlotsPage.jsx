import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { BookSlotModal } from './BookSlotModal.jsx'
import { TherapistAssignedCasesPanel } from './TherapistAssignedCasesPanel.jsx'
import { WeeklyScheduleDrawer } from './WeeklyScheduleDrawer.jsx'
import {
  STATUS_STYLES,
  addDays,
  dateStr,
  defaultHourRows,
  startOfWeek,
  weekDays,
} from './slotCalendarUtils.js'

export function TherapistSlotsPage({ therapistId: therapistIdProp } = {}) {
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [calendar, setCalendar] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [bookSlot, setBookSlot] = useState(null)
  const [menuSlot, setMenuSlot] = useState(null)

  const weekEnd = useMemo(() => addDays(weekStart, 6), [weekStart])
  const days = useMemo(() => weekDays(weekStart), [weekStart])
  const hours = defaultHourRows()
  const today = dateStr(new Date())

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const from = dateStr(weekStart)
    const to = dateStr(weekEnd)
    const tid = therapistIdProp ? `&therapist_id=${therapistIdProp}` : ''
    try {
      const data = await apiFetch(`/api/v1/slots/calendar?from_date=${from}&to_date=${to}${tid}`)
      setCalendar(data)
    } catch (err) {
      setError(err.message || 'Could not load calendar')
      setCalendar(null)
    } finally {
      setLoading(false)
    }
  }, [weekStart, weekEnd, therapistIdProp])

  useEffect(() => {
    load()
  }, [load])

  const slotsByDayHour = useMemo(() => {
    const map = {}
    for (const s of calendar?.slots || []) {
      const hour = parseInt(s.start_time.split(':')[0], 10)
      const key = `${s.slot_date}-${hour}`
      if (!map[key]) map[key] = []
      map[key].push(s)
    }
    return map
  }, [calendar])

  async function markLeave(dayDate) {
    const d = dateStr(dayDate)
    try {
      await apiFetch('/api/v1/leave', {
        method: 'POST',
        body: JSON.stringify({
          leave_type: 'CASUAL',
          start_date: d,
          end_date: d,
          reason: 'Marked from calendar',
        }),
      })
      load()
    } catch (err) {
      setError(err.message || 'Could not mark leave')
    }
  }

  async function handleSlotAction(action, slot) {
    setMenuSlot(null)
    try {
      if (action === 'book') setBookSlot(slot)
      else if (action === 'cancel') {
        await apiFetch(`/api/v1/slots/${slot.id}/cancel`, { method: 'POST' })
        load()
      } else if (action === 'block') {
        await apiFetch(`/api/v1/slots/${slot.id}/block`, { method: 'POST' })
        load()
      } else if (action === 'delete') {
        await apiFetch(`/api/v1/slots/${slot.id}`, { method: 'DELETE' })
        load()
      }
    } catch (err) {
      setError(err.message || 'Action failed')
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Availability</p>
          <h1 className="text-2xl font-bold text-slate-900">My calendar</h1>
          <p className="mt-1 text-sm text-slate-500">Set weekly hours, book clients, mark leave days.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setScheduleOpen(true)}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Weekly schedule
          </button>
          <button
            type="button"
            onClick={() => load()}
            className="rounded-xl border border-[#E2E8F0] px-4 py-2 text-sm font-semibold text-slate-700"
          >
            Refresh
          </button>
        </div>
      </div>

      {error ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      {!therapistIdProp ? <TherapistAssignedCasesPanel /> : null}

      <div className="overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
        <div className="flex items-center gap-3 border-b border-[#E2E8F0] px-4 py-3">
          <button type="button" onClick={() => setWeekStart(addDays(weekStart, -7))} className="rounded-lg border px-3 py-1 text-sm">
            ‹
          </button>
          <p className="flex-1 text-center text-sm font-semibold text-slate-800">
            {dateStr(weekStart)} – {dateStr(weekEnd)}
          </p>
          <button type="button" onClick={() => setWeekStart(addDays(weekStart, 7))} className="rounded-lg border px-3 py-1 text-sm">
            ›
          </button>
          <button
            type="button"
            onClick={() => setWeekStart(startOfWeek(new Date()))}
            className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white"
          >
            Today
          </button>
        </div>

        {loading ? (
          <p className="p-8 text-center text-slate-500">Loading calendar…</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse">
              <thead>
                <tr>
                  <th className="w-14 bg-slate-50 p-2 text-xs text-slate-400">Time</th>
                  {days.map((d) => {
                    const ds = dateStr(d)
                    const overlay = calendar?.day_overlays?.[ds]
                    const isToday = ds === today
                    return (
                      <th
                        key={ds}
                        className={`border-l border-[#E2E8F0] bg-slate-50 p-2 text-center ${isToday ? 'text-indigo-600' : ''}`}
                      >
                        <div className="text-xs font-semibold">{d.toLocaleDateString('en', { weekday: 'short' })}</div>
                        <div className="text-lg font-bold">{d.getDate()}</div>
                        {overlay ? (
                          <span className="mt-1 block text-[10px] font-semibold text-amber-800">Leave</span>
                        ) : (
                          <button
                            type="button"
                            className="mt-1 text-[10px] text-slate-500 underline"
                            onClick={() => markLeave(d)}
                          >
                            Mark leave
                          </button>
                        )}
                      </th>
                    )
                  })}
                </tr>
              </thead>
              <tbody>
                {hours.map((hour) => (
                  <tr key={hour} className="border-t border-[#E2E8F0]">
                    <td className="p-2 text-right text-xs text-slate-400">{String(hour).padStart(2, '0')}:00</td>
                    {days.map((d) => {
                      const ds = dateStr(d)
                      const overlay = calendar?.day_overlays?.[ds]
                      const key = `${ds}-${hour}`
                      const cellSlots = slotsByDayHour[key] || []
                      if (overlay) {
                        return (
                          <td key={ds} className="border-l border-[#E2E8F0] bg-slate-100 p-1 align-top">
                            <div className="min-h-[36px] rounded bg-slate-200/80 text-center text-[10px] leading-9 text-slate-500">
                              Holiday
                            </div>
                          </td>
                        )
                      }
                      return (
                        <td key={ds} className="border-l border-[#E2E8F0] p-1 align-top">
                          {cellSlots.map((s) => (
                            <button
                              key={s.id}
                              type="button"
                              onClick={() => setMenuSlot(menuSlot?.id === s.id ? null : s)}
                              className={`mb-1 w-full rounded border px-1 py-0.5 text-left text-[10px] font-semibold ${STATUS_STYLES[s.status] || ''}`}
                            >
                              {s.status === 'BOOKED' ? (
                                <span>{s.child_name || s.case_code || 'Booked'}</span>
                              ) : (
                                <span>
                                  {s.start_time}–{s.end_time}
                                </span>
                              )}
                            </button>
                          ))}
                          {menuSlot && cellSlots.some((s) => s.id === menuSlot.id) ? (
                            <div className="z-10 mt-1 rounded border bg-white p-1 shadow-lg">
                              {menuSlot.status === 'AVAILABLE' && (
                                <>
                                  <button type="button" className="block w-full px-2 py-1 text-left text-xs hover:bg-slate-50" onClick={() => handleSlotAction('book', menuSlot)}>
                                    Book client
                                  </button>
                                  <button type="button" className="block w-full px-2 py-1 text-left text-xs hover:bg-slate-50" onClick={() => handleSlotAction('block', menuSlot)}>
                                    Block
                                  </button>
                                  <button type="button" className="block w-full px-2 py-1 text-left text-xs text-red-600 hover:bg-red-50" onClick={() => handleSlotAction('delete', menuSlot)}>
                                    Remove
                                  </button>
                                </>
                              )}
                              {menuSlot.status === 'BOOKED' && (
                                <button type="button" className="block w-full px-2 py-1 text-left text-xs hover:bg-slate-50" onClick={() => handleSlotAction('cancel', menuSlot)}>
                                  Cancel booking
                                </button>
                              )}
                              {menuSlot.status === 'BLOCKED' && (
                                <button type="button" className="block w-full px-2 py-1 text-left text-xs hover:bg-slate-50" onClick={() => handleSlotAction('delete', menuSlot)}>
                                  Unblock
                                </button>
                              )}
                            </div>
                          ) : null}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <WeeklyScheduleDrawer
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        weekStart={dateStr(weekStart)}
        weekEnd={dateStr(weekEnd)}
        therapistId={therapistIdProp}
        onApplied={load}
      />
      <BookSlotModal
        open={!!bookSlot}
        slot={bookSlot}
        therapistId={therapistIdProp}
        onClose={() => setBookSlot(null)}
        onBooked={load}
      />
    </div>
  )
}
