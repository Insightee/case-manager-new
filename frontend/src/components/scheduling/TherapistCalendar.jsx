import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { WeekCalendarGrid } from './WeekCalendarGrid.jsx'
import { DayCalendarGrid } from './DayCalendarGrid.jsx'
import { MonthCalendarGrid } from './MonthCalendarGrid.jsx'
import { addDays, dateStr, endOfMonth, startOfMonth, startOfWeek } from './slotCalendarUtils.js'

export function TherapistCalendar({
  therapistId,
  apiPrefix = '/api/v1/scheduling',
  mode = 'therapist',
  onSlotClick,
  onCellClick,
  selectedSlotId,
  showLeaveActions = true,
  onMarkLeave,
  refreshKey = 0,
  onScheduleContext,
}) {
  const [view, setView] = useState(() => 'week')
  const [weekStart, setWeekStart] = useState(() => startOfWeek(new Date()))
  const [dayDate, setDayDate] = useState(() => {
    const t = new Date()
    t.setHours(0, 0, 0, 0)
    return t
  })
  const [monthDate, setMonthDate] = useState(() => startOfMonth(new Date()))

  const { fromDate, toDate } = useMemo(() => {
    if (view === 'day') {
      const d = dateStr(dayDate)
      return { fromDate: d, toDate: d }
    }
    if (view === 'month') {
      const start = startOfMonth(monthDate)
      const end = endOfMonth(monthDate)
      return { fromDate: dateStr(start), toDate: dateStr(end) }
    }
    return { fromDate: dateStr(weekStart), toDate: dateStr(addDays(weekStart, 6)) }
  }, [view, weekStart, dayDate, monthDate])

  const scheduleWeekStart = useMemo(() => {
    if (view === 'week') return weekStart
    if (view === 'day') return startOfWeek(dayDate)
    return startOfWeek(startOfMonth(monthDate))
  }, [view, weekStart, dayDate, monthDate])

  useEffect(() => {
    onScheduleContext?.({ weekStart: scheduleWeekStart })
  }, [onScheduleContext, scheduleWeekStart])

  const [calendar, setCalendar] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    const tid = therapistId ? `&therapist_id=${therapistId}` : ''
    try {
      const data = await apiFetch(`${apiPrefix}/calendar?from_date=${fromDate}&to_date=${toDate}${tid}`)
      setCalendar(data)
    } catch (err) {
      setError(err.message || 'Could not load calendar')
      setCalendar(null)
    } finally {
      setLoading(false)
    }
  }, [fromDate, toDate, therapistId, apiPrefix, refreshKey])

  useEffect(() => {
    load()
  }, [load])

  async function handleMarkLeave(dayDateArg) {
    if (onMarkLeave) {
      onMarkLeave(dayDateArg)
      return
    }
    const d = dateStr(dayDateArg)
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

  function switchView(next) {
    setView(next)
    if (next === 'week') setWeekStart(startOfWeek(dayDate))
    if (next === 'month') setMonthDate(startOfMonth(dayDate))
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-full border border-[#E2E8F0] bg-slate-50 p-1">
          {[
            { id: 'day', label: 'Day' },
            { id: 'week', label: 'Week' },
            { id: 'month', label: 'Month' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => switchView(t.id)}
              className={`rounded-full px-4 py-1.5 text-xs font-semibold sm:text-sm ${
                view === t.id ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {error ? <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p> : null}

      {view === 'week' ? (
        <WeekCalendarGrid
          calendar={calendar}
          loading={loading}
          weekStart={weekStart}
          onWeekStartChange={setWeekStart}
          mode={mode}
          onSlotClick={onSlotClick}
          onCellClick={onCellClick}
          selectedSlotId={selectedSlotId}
          showLeaveActions={showLeaveActions}
          onMarkLeave={handleMarkLeave}
          onReload={load}
        />
      ) : null}

      {view === 'day' ? (
        <DayCalendarGrid
          calendar={calendar}
          loading={loading}
          dayDate={dayDate}
          onDayChange={setDayDate}
          mode={mode}
          onSlotClick={onSlotClick}
          onCellClick={onCellClick}
          selectedSlotId={selectedSlotId}
          showLeaveActions={showLeaveActions}
          onMarkLeave={handleMarkLeave}
        />
      ) : null}

      {view === 'month' ? (
        <MonthCalendarGrid
          calendar={calendar}
          loading={loading}
          monthDate={monthDate}
          onMonthChange={setMonthDate}
          onSelectDay={(d) => {
            setDayDate(d)
            setView('day')
          }}
        />
      ) : null}
    </>
  )
}
