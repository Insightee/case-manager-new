import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateLabel } from '../../lib/datetime.js'
import { BookSlotModal } from './BookSlotModal.jsx'
import { WeeklyScheduleDrawer } from './WeeklyScheduleDrawer.jsx'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { SlotDetailSheet } from '../scheduling/SlotDetailSheet.jsx'
import { SlotEditSheet } from '../scheduling/SlotEditSheet.jsx'
import { clearScheduleCache } from '../../lib/scheduleCache.js'
import { addDays, dateStr, startOfWeek } from '../scheduling/slotCalendarUtils.js'
import '../scheduling/scheduling-day.css'
import '../scheduling/schedule-sheet.css'

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
  const [meetingRequests, setMeetingRequests] = useState([])

  const weekEnd = addDays(scheduleWeekStart, 6)

  useEffect(() => {
    if (therapistIdProp) return
    apiFetch('/api/v1/scheduling/parent-meeting-requests')
      .then((rows) => setMeetingRequests(Array.isArray(rows) ? rows : []))
      .catch(() => setMeetingRequests([]))
  }, [therapistIdProp, refreshKey])

  function bumpRefresh() {
    clearScheduleCache()
    setRefreshKey((k) => k + 1)
  }

  async function dismissMeetingRequest(requestId) {
    try {
      await apiFetch(`/api/v1/scheduling/parent-meeting-requests/${requestId}/dismiss`, {
        method: 'POST',
      })
      setMeetingRequests((rows) => rows.filter((r) => r.id !== requestId))
    } catch {
      bumpRefresh()
    }
  }

  return (
    <div className="therapist-slots-page">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start sm:justify-between">
        <div>
          <p className="sched-sheet__eyebrow">Availability</p>
          <h1 className="text-2xl font-bold text-slate-900">Scheduling</h1>
          <p className="mt-1 text-sm text-slate-500">Tap an empty cell to add a slot, or tap a slot to manage it.</p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap">
          <Link
            to="/therapist/meetings?availability=1"
            className="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-center text-sm font-semibold text-slate-800 hover:bg-slate-50 sm:w-auto"
          >
            My availability
          </Link>
          <button
            type="button"
            onClick={() => {
              setScheduleTab('recurring')
              setScheduleOpen(true)
            }}
            className="sched-entry sched-entry--quiet"
          >
            Book recurring
          </button>
          <button
            type="button"
            onClick={() => {
              setScheduleTab('availability')
              setScheduleOpen(true)
            }}
            className="sched-entry sched-entry--primary"
          >
            Weekly schedule
          </button>
        </div>
      </div>

      {meetingRequests.length > 0 ? (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <p className="font-semibold">Parent meeting requests</p>
          <ul className="mt-2 space-y-2">
            {meetingRequests.map((req) => (
              <li key={req.id} className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <span>
                  {req.child_name || req.case_code || 'Case'} · {formatDisplayDateLabel(req.requested_date)}
                  {req.parent_name ? ` · ${req.parent_name}` : ''}
                  {req.note ? ` — “${req.note}”` : ''}
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    to={`/therapist/slots?date=${req.requested_date}`}
                    className="font-semibold text-indigo-700 hover:text-indigo-900"
                  >
                    Open {formatDisplayDateLabel(req.requested_date)} →
                  </Link>
                  <button
                    type="button"
                    className="text-sm font-semibold text-slate-600 underline-offset-2 hover:underline"
                    onClick={() => dismissMeetingRequest(req.id)}
                  >
                    Dismiss
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

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
