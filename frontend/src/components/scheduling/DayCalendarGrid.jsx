import { useMemo } from 'react'
import {
  PARENT_SLOT_STYLES,
  THERAPIST_STATUS_STYLES,
  calendarGridEvents,
  dateStr,
  defaultHourRows,
} from './slotCalendarUtils.js'

function groupSlotsByDayHour(slots, hourField = 'start_time') {
  const map = {}
  for (const s of slots || []) {
    const hour = parseInt(String(s[hourField]).split(':')[0], 10)
    const key = `${s.slot_date}-${hour}`
    if (!map[key]) map[key] = []
    map[key].push(s)
  }
  return map
}

export function DayCalendarGrid({
  calendar,
  loading,
  dayDate,
  onDayChange,
  mode = 'therapist',
  onSlotClick,
  onCellClick,
  selectedSlotId,
  showLeaveActions = false,
  onMarkLeave,
}) {
  const ds = dateStr(dayDate)
  const hours = defaultHourRows()
  const today = dateStr(new Date())
  const slotsByDayHour = useMemo(() => groupSlotsByDayHour(calendarGridEvents(calendar)), [calendar])
  const overlay = calendar?.day_overlays?.[ds]
  const isToday = ds === today

  return (
    <div className="overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-sm">
      <div className="flex items-center gap-3 border-b border-[#E2E8F0] px-4 py-3">
        <button
          type="button"
          onClick={() => onDayChange(new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate() - 1))}
          className="rounded-lg border px-3 py-1 text-sm"
        >
          ‹
        </button>
        <p className="flex-1 text-center text-sm font-semibold text-slate-800">
          {dayDate.toLocaleDateString('en', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
        <button
          type="button"
          onClick={() => onDayChange(new Date(dayDate.getFullYear(), dayDate.getMonth(), dayDate.getDate() + 1))}
          className="rounded-lg border px-3 py-1 text-sm"
        >
          ›
        </button>
        <button
          type="button"
          onClick={() => onDayChange(new Date())}
          className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-semibold text-white"
        >
          Today
        </button>
      </div>

      {loading ? (
        <p className="p-8 text-center text-slate-500">Loading calendar…</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[320px] border-collapse">
            <thead>
              <tr>
                <th className="w-14 bg-slate-50 p-2 text-xs text-slate-400">Time</th>
                <th
                  className={`border-l border-[#E2E8F0] bg-slate-50 p-2 text-center ${isToday ? 'text-indigo-600' : ''}`}
                >
                  <div className="text-lg font-bold">{dayDate.getDate()}</div>
                  {overlay ? (
                    <span className="mt-1 block text-[10px] font-semibold text-amber-800">Leave</span>
                  ) : showLeaveActions && onMarkLeave ? (
                    <button
                      type="button"
                      className="mt-1 text-[10px] text-slate-500 underline"
                      onClick={() => onMarkLeave(dayDate)}
                    >
                      Mark leave
                    </button>
                  ) : null}
                </th>
              </tr>
            </thead>
            <tbody>
              {hours.map((hour) => {
                const key = `${ds}-${hour}`
                const cellSlots = slotsByDayHour[key] || []
                if (overlay) {
                  return (
                    <tr key={hour} className="border-t border-[#E2E8F0]">
                      <td className="p-2 text-right text-xs text-slate-400">{String(hour).padStart(2, '0')}:00</td>
                      <td className="border-l border-[#E2E8F0] bg-slate-100 p-1 align-top">
                        <div className="min-h-[44px] rounded bg-slate-200/80 text-center text-[10px] leading-[44px] text-slate-500">
                          Unavailable
                        </div>
                      </td>
                    </tr>
                  )
                }
                return (
                  <tr key={hour} className="border-t border-[#E2E8F0]">
                    <td className="p-2 text-right text-xs text-slate-400">{String(hour).padStart(2, '0')}:00</td>
                    <td className="border-l border-[#E2E8F0] p-1 align-top">
                      {cellSlots.length === 0 && onCellClick ? (
                        <button
                          type="button"
                          className="mb-1 min-h-[44px] w-full rounded border border-dashed border-slate-200 text-[10px] text-slate-400 hover:border-indigo-300 hover:bg-indigo-50/50 hover:text-indigo-600"
                          onClick={() => onCellClick(dayDate, hour)}
                        >
                          +
                        </button>
                      ) : null}
                      {cellSlots.map((s) => {
                        const isParent = mode === 'parent'
                        const style = isParent
                          ? PARENT_SLOT_STYLES[s.is_mine ? 'mine' : 'available']
                          : THERAPIST_STATUS_STYLES[s.status] || ''
                        const label = isParent
                          ? s.is_mine
                            ? `My session · ${s.start_time}`
                            : `Available · ${s.start_time}`
                          : s.event_type === 'cm_meeting'
                            ? `CM · ${s.title || s.child_name || s.case_code || 'Meeting'}`
                            : s.event_type === 'session'
                            ? `${s.status === 'IN_PROGRESS' ? 'In progress · ' : 'Session · '}${s.child_name || s.case_code || 'Visit'}`
                            : s.status === 'BOOKED'
                              ? `${s.approval_status === 'PENDING_THERAPIST' ? '⏳ ' : ''}${s.booking_source === 'PARENT' ? 'Parent · ' : ''}${s.child_name || s.case_code || 'Booked'}`
                              : `${s.start_time}–${s.end_time}`
                        return (
                          <button
                            key={s.id}
                            type="button"
                            onClick={() => onSlotClick?.(s)}
                            className={`mb-1 w-full min-h-[40px] rounded border px-1 py-1 text-left text-[10px] font-semibold ${style} ${
                              selectedSlotId === s.id ? 'ring-2 ring-indigo-500' : ''
                            }`}
                          >
                            {label}
                          </button>
                        )
                      })}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
