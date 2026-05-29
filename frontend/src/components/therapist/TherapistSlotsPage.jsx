import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { BookSlotModal } from './BookSlotModal.jsx'
import { WeeklyScheduleDrawer } from './WeeklyScheduleDrawer.jsx'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { SlotDetailSheet } from '../scheduling/SlotDetailSheet.jsx'
import { SlotEditSheet } from '../scheduling/SlotEditSheet.jsx'
import { clearScheduleCache } from '../../lib/scheduleCache.js'
import { addDays, dateStr, startOfWeek } from '../scheduling/slotCalendarUtils.js'

export function TherapistSlotsPage({ therapistId: therapistIdProp } = {}) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const focusDate = searchParams.get('date')
  const [scheduleWeekStart, setScheduleWeekStart] = useState(() => startOfWeek(new Date()))
  const [refreshKey, setRefreshKey] = useState(0)
  const [scheduleOpen, setScheduleOpen] = useState(false)
  const [scheduleTab, setScheduleTab] = useState('availability')
  const [bookSlot, setBookSlot] = useState(null)
  const [detailSlot, setDetailSlot] = useState(null)
  const [editState, setEditState] = useState(null)

  const weekEnd = addDays(scheduleWeekStart, 6)

  function bumpRefresh() {
    clearScheduleCache()
    setRefreshKey((k) => k + 1)
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Availability</p>
          <h1 className="text-2xl font-bold text-slate-900">My calendar</h1>
          <p className="mt-1 text-sm text-slate-500">Tap an empty cell to add a slot, or tap a slot to manage it.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => {
              setScheduleTab('recurring')
              setScheduleOpen(true)
            }}
            className="rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-2 text-sm font-semibold text-indigo-800 hover:bg-indigo-100"
          >
            Book recurring
          </button>
          <button
            type="button"
            onClick={() => {
              setScheduleTab('availability')
              setScheduleOpen(true)
            }}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Weekly schedule
          </button>
        </div>
      </div>

      <TherapistCalendar
        therapistId={therapistIdProp}
        refreshKey={refreshKey}
        focusDate={focusDate}
        mode="therapist"
        onScheduleContext={({ weekStart }) => setScheduleWeekStart(weekStart)}
        onSlotClick={(s) => {
          if (s.event_type === 'session' && s.case_id) {
            navigate(`/therapist/cases/${s.case_id}?tab=sessions`)
            return
          }
          setDetailSlot(s)
        }}
        onCellClick={(day, hour) => setEditState({ mode: 'add', cellDate: day, cellHour: hour })}
      />

      <SlotDetailSheet
        open={!!detailSlot}
        slot={detailSlot}
        onClose={() => setDetailSlot(null)}
        onBook={(s) => {
          setDetailSlot(null)
          setBookSlot(s)
        }}
        onChanged={(action, slot) => {
          if (action === 'edit') {
            setDetailSlot(null)
            setEditState({ mode: 'edit', slot })
          } else {
            bumpRefresh()
          }
        }}
      />

      <SlotEditSheet
        open={!!editState}
        mode={editState?.mode || 'add'}
        slot={editState?.slot}
        cellDate={editState?.cellDate}
        cellHour={editState?.cellHour}
        therapistId={therapistIdProp}
        isAdmin={!!therapistIdProp}
        onClose={() => setEditState(null)}
        onSaved={bumpRefresh}
      />

      <WeeklyScheduleDrawer
        open={scheduleOpen}
        onClose={() => setScheduleOpen(false)}
        initialTab={scheduleTab}
        weekStart={dateStr(scheduleWeekStart)}
        weekEnd={dateStr(weekEnd)}
        therapistId={therapistIdProp}
        onApplied={bumpRefresh}
      />
      <BookSlotModal
        open={!!bookSlot}
        slot={bookSlot}
        therapistId={therapistIdProp}
        onClose={() => setBookSlot(null)}
        onBooked={bumpRefresh}
      />
    </div>
  )
}
