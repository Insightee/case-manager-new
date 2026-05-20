import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { WeekCalendarGrid } from './WeekCalendarGrid.jsx'
import { DayCalendarGrid } from './DayCalendarGrid.jsx'
import { MonthCalendarGrid } from './MonthCalendarGrid.jsx'
import { addDays, dateStr, endOfMonth, startOfMonth, startOfWeek } from './slotCalendarUtils.js'

/**
 * Client-facing calendar (Day / Week / Month view).
 * Mirrors TherapistCalendar but targets the parent booking API.
 * The week view is wrapped in overflow-x-auto so it never blows
 * past the narrow client-portal content column (~640 px).
 */
export function ClientCalendar({
  caseId,
  therapistId,
  onSlotClick,
  selectedSlotId,
  refreshKey = 0,
  onCalendarLoad,
}) {
  const [view, setView] = useState('week')
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
      return { fromDate: dateStr(startOfMonth(monthDate)), toDate: dateStr(endOfMonth(monthDate)) }
    }
    return { fromDate: dateStr(weekStart), toDate: dateStr(addDays(weekStart, 6)) }
  }, [view, weekStart, dayDate, monthDate])

  const [calendar, setCalendar] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!caseId || !therapistId) return
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch(
        `/api/v1/parent/booking/calendar?case_id=${caseId}&therapist_id=${therapistId}&from_date=${fromDate}&to_date=${toDate}`,
      )
      setCalendar(data)
      onCalendarLoad?.(data)
    } catch (err) {
      setError(err.message || 'Could not load calendar')
      setCalendar(null)
    } finally {
      setLoading(false)
    }
  }, [caseId, therapistId, fromDate, toDate, refreshKey])

  useEffect(() => {
    load()
  }, [load])

  function switchView(next) {
    setView(next)
    if (next === 'week') setWeekStart(startOfWeek(dayDate))
    if (next === 'month') setMonthDate(startOfMonth(dayDate))
  }

  return (
    <div>
      {/* View switcher */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <div style={{ display: 'inline-flex', borderRadius: 999, border: '1px solid #e2e8f0', background: '#f8fafc', padding: 3 }}>
          {[
            { id: 'day', label: 'Day' },
            { id: 'week', label: 'Week' },
            { id: 'month', label: 'Month' },
          ].map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => switchView(t.id)}
              style={{
                borderRadius: 999,
                padding: '5px 16px',
                fontSize: '0.8rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: view === t.id ? '#fff' : 'transparent',
                color: view === t.id ? '#4338ca' : '#64748b',
                boxShadow: view === t.id ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              }}
            >
              {t.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={() => {
            const today = new Date()
            today.setHours(0, 0, 0, 0)
            setDayDate(today)
            setWeekStart(startOfWeek(today))
            setMonthDate(startOfMonth(today))
          }}
          style={{ fontSize: '0.78rem', fontWeight: 600, color: '#4f46e5', background: 'none', border: '1px solid #c7d2fe', borderRadius: 8, padding: '4px 12px', cursor: 'pointer' }}
        >
          Today
        </button>
      </div>

      {error ? (
        <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '8px 12px', fontSize: '0.875rem', color: '#991b1b', marginBottom: 10 }}>
          {error}
        </p>
      ) : null}

      {/* Week view — wrapped in horizontal scroll so it can't overflow the column */}
      {view === 'week' ? (
        <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch', borderRadius: 16 }}>
          <div style={{ minWidth: 480 }}>
            <WeekCalendarGrid
              calendar={calendar}
              loading={loading}
              weekStart={weekStart}
              onWeekStartChange={setWeekStart}
              mode="parent"
              onSlotClick={onSlotClick}
              selectedSlotId={selectedSlotId}
              showLeaveActions={false}
            />
          </div>
        </div>
      ) : null}

      {view === 'day' ? (
        <DayCalendarGrid
          calendar={calendar}
          loading={loading}
          dayDate={dayDate}
          onDayChange={setDayDate}
          mode="parent"
          onSlotClick={onSlotClick}
          selectedSlotId={selectedSlotId}
          showLeaveActions={false}
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
    </div>
  )
}
