import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { mapSlotToCalendarEvent } from '../../lib/googleCalendar.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'
import { ScheduleWeekdayPicker } from './ScheduleWeekdayPicker.jsx'
import { ONGOING_MATERIALIZE_WEEKS } from './scheduleTemplateUtils.js'
import { dateStr, weekEndContaining } from './slotCalendarUtils.js'
import {
  addDaysIso,
  earlierWeekdayMessage,
  formatSkipMessage,
  todayIsoIST,
} from './recurringRange.js'
import './schedule-sheet.css'
import {
  handoverBookingHintForTherapist,
  normalizeBookingErrorMessage,
  TRANSITION_HANDOVER_BANNER,
} from '../../lib/therapistTransitionBooking.js'

const DURATION_CHIPS = [
  { label: '30 min', mins: 30 },
  { label: '60 min', mins: 60 },
  { label: '90 min', mins: 90 },
  { label: '2 h', mins: 120 },
]

const SERVICE_TYPES = [
  { value: 'homecare', label: 'Homecare' },
  { value: 'shadow_support', label: 'Shadow care' },
  { value: 'counselling', label: 'Counselling' },
  { value: 'special_education', label: 'Special Education' },
  { value: 'behaviour_therapy', label: 'Behaviour Therapy' },
  { value: 'tutoring', label: 'Tutoring' },
  { value: 'other', label: 'Other' },
]

function addMinsToHM(hm, mins) {
  const [h, m] = hm.split(':').map(Number)
  const total = h * 60 + m + mins
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
}

function diffMins(start, end) {
  if (!start || !end) return null
  const [sh, sm] = start.split(':').map(Number)
  const [eh, em] = end.split(':').map(Number)
  const d = eh * 60 + em - (sh * 60 + sm)
  return d > 0 ? d : null
}

// 3-months from today
function defaultEndDate() {
  return addDaysIso(todayIsoIST(), 90)
}

export function SlotEditSheet({
  open,
  mode,
  slot,
  cellDate,
  cellHour,
  therapistId,
  isAdmin,
  onClose,
  onSaved,
}) {
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('10:00')
  const [notes, setNotes] = useState('')
  const [serviceType, setServiceType] = useState('')

  // Booking toggle
  const [bookClient, setBookClient] = useState(false)
  const [bookTab, setBookTab] = useState('existing') // 'existing' | 'new'

  // Existing case
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState('')
  const [selectedCase, setSelectedCase] = useState(null)
  const [bookingSuccess, setBookingSuccess] = useState(null)

  // New client invite
  const [clientName, setClientName] = useState('')
  const [childName, setChildName] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  const [clientPhone, setClientPhone] = useState('')

  // Recurring
  const [recurring, setRecurring] = useState(false)
  const [recurWeekdays, setRecurWeekdays] = useState([])
  const [recurScope, setRecurScope] = useState('until')
  const [recurEndDate, setRecurEndDate] = useState(defaultEndDate())

  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [meId, setMeId] = useState(null)
  const [handoverPolicy, setHandoverPolicy] = useState(null)

  const slotDate = mode === 'edit' && slot ? slot.slot_date : cellDate ? dateStr(cellDate) : ''

  useEffect(() => {
    if (!open) return
    setError('')
    apiFetch('/api/v1/auth/me')
      .then((u) => setMeId(u.id))
      .catch(() => {})
    setSaving(false)
    setRecurring(false)
    setRecurWeekdays([])
    setRecurScope('until')
    setRecurEndDate(defaultEndDate())
    setBookClient(!!isAdmin)
    setBookTab('existing')
    setCaseId('')
    setSelectedCase(null)
    setClientName('')
    setChildName('')
    setClientEmail('')
    setClientPhone('')

    if (mode === 'edit' && slot) {
      setStartTime(slot.start_time)
      setEndTime(slot.end_time)
      setNotes(slot.notes || '')
      setServiceType(slot.product_module || slot.service_type || '')
    } else {
      const hour = cellHour != null ? String(cellHour).padStart(2, '0') : '09'
      setStartTime(`${hour}:00`)
      setEndTime(addMinsToHM(`${hour}:00`, 60))
      setNotes('')
      setServiceType('')
    }
  }, [open, mode, slot, cellDate, cellHour, isAdmin])

  // Load cases when booking toggle is on
  useEffect(() => {
    if (!open || !bookClient) return
    const qs = therapistId ? `?therapist_id=${therapistId}` : ''
    apiFetch(`/api/v1/slots/bookable-cases${qs}`)
      .then(setCases)
      .catch(() => setCases([]))
  }, [open, bookClient, therapistId])

  const earlierNote = useMemo(
    () => (recurring && recurScope !== 'this_week' ? earlierWeekdayMessage(recurWeekdays, slotDate) : ''),
    [recurring, recurScope, recurWeekdays, slotDate],
  )
  useEffect(() => {
    if (!caseId) {
      setHandoverPolicy(null)
      return
    }
    apiFetch(`/api/v1/cases/${caseId}/transitions/active`)
      .then((row) => setHandoverPolicy(row?.booking_policy || null))
      .catch(() => setHandoverPolicy(null))
  }, [caseId])

  const handoverHint = handoverBookingHintForTherapist(handoverPolicy, therapistId)

  if (!open) return null

  const durMins = diffMins(startTime, endTime)

  function applyChip(mins) {
    setEndTime(addMinsToHM(startTime, mins))
  }

  function resolveRecurEndDate(fromDate) {
    if (recurScope === 'this_week') return weekEndContaining(fromDate)
    if (recurScope === 'ongoing') return addDaysIso(fromDate, ONGOING_MATERIALIZE_WEEKS * 7 - 1)
    return recurEndDate
  }

  function recurWeeksCount(fromDate) {
    if (recurScope === 'this_week') return 1
    if (recurScope === 'ongoing') return ONGOING_MATERIALIZE_WEEKS
    const start = new Date(`${fromDate}T12:00:00`)
    const end = new Date(`${recurEndDate}T12:00:00`)
    const diff = Math.max(1, Math.ceil((end - start) / (7 * 86400000)))
    return Math.min(52, diff)
  }

  async function handleSave(e) {
    e.preventDefault()
    if (!startTime || !endTime) { setError('Start and end time are required.'); return }
    if (endTime <= startTime) { setError('End time must be after start time.'); return }

    setSaving(true)
    setError('')
    try {
      // ------- Recurring path (no case booking, just open slots) -------
      if (recurring && recurWeekdays.length > 0 && !bookClient) {
        await apiFetch('/api/v1/slots/recurring', {
          method: 'POST',
          body: JSON.stringify({
            weekday_keys: recurWeekdays,
            start_time: startTime,
            end_time: endTime,
            from_date: slotDate,
            weeks: recurWeeksCount(slotDate),
            therapist_id: therapistId || undefined,
          }),
        })
        onSaved?.()
        onClose()
        return
      }

      // ------- Create/edit the single slot -------
      let savedSlot
      if (mode === 'edit' && slot) {
        savedSlot = await apiFetch(`/api/v1/scheduling/slots/${slot.id}`, {
          method: 'PATCH',
          body: JSON.stringify({
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
          }),
        })
      } else {
        savedSlot = await apiFetch('/api/v1/scheduling/slots', {
          method: 'POST',
          body: JSON.stringify({
            slot_date: slotDate,
            start_time: startTime,
            end_time: endTime,
            notes: notes || null,
            therapist_id: therapistId || undefined,
          }),
        })
      }

      const newSlotId = savedSlot?.id || slot?.id
      const createdNewSlot = mode !== 'edit' && Boolean(savedSlot?.id)

      // ------- Book client (if toggle on) -------
      let bookedForCalendar = null
      if (bookClient && newSlotId) {
        if (bookTab === 'existing' && caseId) {
          // Always notify the family about this booked session. The recurring call below can still
          // fail (e.g. handover window 409), and a suppressed anchor notice would then never be sent.
          try {
            await apiFetch(`/api/v1/scheduling/slots/${newSlotId}/book`, {
              method: 'POST',
              body: JSON.stringify({ case_id: Number(caseId) }),
            })
          } catch (bookErr) {
            if (createdNewSlot) {
              await apiFetch(`/api/v1/scheduling/slots/${newSlotId}`, { method: 'DELETE' }).catch(() => {})
            }
            throw bookErr
          }
          bookedForCalendar = {
            id: newSlotId,
            slot_date: slotDate,
            start_time: startTime,
            end_time: endTime,
            child_name: selectedCase?.child_name,
            case_code: selectedCase?.case_code,
          }
        } else if (bookTab === 'new' && clientName && clientEmail) {
          // TODO: re-enable when therapist self-onboarding is allowed again
          /*
          await apiFetch(`/api/v1/scheduling/slots/${newSlotId}/invite-client`, {
            method: 'POST',
            body: JSON.stringify({
              client_name: clientName.trim(),
              client_email: clientEmail.trim(),
              child_name: childName.trim() || null,
              client_phone: clientPhone.trim() || null,
            }),
          })
          */
        }
      }

      // ------- If recurring + case selected, also assign recurring -------
      if (recurring && recurWeekdays.length > 0 && bookClient && caseId) {
        const tid = Number(therapistId || meId)
        if (!tid) {
          setError('Looks like we still need the therapist on this schedule before we can save the repeating days.')
          setSaving(false)
          return
        }
        const result = await apiFetch('/api/v1/scheduling/assign-recurring', {
          method: 'POST',
          body: JSON.stringify({
            case_id: Number(caseId),
            therapist_user_id: tid,
            weekdays: recurWeekdays,
            start_time: startTime,
            end_time: endTime,
            start_date: slotDate,
            end_date: resolveRecurEndDate(slotDate),
          }),
        })
        // The anchor slot booked above always comes back as already_booked — that's success, not a skip.
        const skipped = (result?.skipped || []).filter(
          (row) => !(row?.reason === 'already_booked' && row?.date === slotDate),
        )
        if (skipped.length) {
          setError(formatSkipMessage(result?.booked_slot_count, skipped))
          onSaved?.()
          setSaving(false)
          return
        }
      }

      if (bookedForCalendar) {
        setBookingSuccess({
          event: mapSlotToCalendarEvent(bookedForCalendar, { deepLinkPath: '/therapist/slots' }),
          detailLines: [
            selectedCase?.child_name ? `Client: ${selectedCase.child_name}` : null,
            selectedCase?.case_code ? `Case: ${selectedCase.case_code}` : null,
          ].filter(Boolean),
        })
        onSaved?.()
        return
      }

      onSaved?.()
      onClose()
    } catch (err) {
      setError(normalizeBookingErrorMessage(err.message) || 'Could not save slot')
    } finally {
      setSaving(false)
    }
  }

  return createPortal(
    <>
    <div className="sched-sheet" onClick={onClose}>
      <div
        className="sched-sheet__panel"
        role="dialog"
        aria-labelledby="slot-edit-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sched-sheet__header">
          <h2 id="slot-edit-title" className="sched-sheet__title">{mode === 'add' ? 'Add slot' : 'Edit slot'}</h2>
          <p className="sched-sheet__sub">{slotDate}</p>
          {error ? <p className="sched-sheet__note" style={{ marginTop: 8 }}>{error}</p> : null}
        </div>

        <form id="slot-edit-form" className="sched-sheet__body" onSubmit={handleSave}>
          <div className="sched-sheet__card">
            <p className="sched-sheet__eyebrow">Time</p>
            <div className="sched-sheet__times">
              <label className="sched-sheet__field">
                Start
                <input
                  type="time"
                  value={startTime}
                  onChange={(e) => setStartTime(e.target.value)}
                  required
                />
              </label>
              <label className="sched-sheet__field">
                End
                <input
                  type="time"
                  value={endTime}
                  onChange={(e) => setEndTime(e.target.value)}
                  required
                />
              </label>
            </div>
            {durMins ? (
              <p className="mt-1 text-xs text-slate-400">Duration: {durMins} min</p>
            ) : null}
            {/* Duration quick-select */}
            <div className="mt-2 flex gap-2 flex-wrap">
              {DURATION_CHIPS.map((c) => (
                <button
                  key={c.mins}
                  type="button"
                  onClick={() => applyChip(c.mins)}
                  className={`sched-chip${durMins === c.mins ? ' is-on' : ''}`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Service type ── */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Service type</p>
            <div className="flex gap-2 flex-wrap">
              {SERVICE_TYPES.map((s) => (
                <button
                  key={s.value}
                  type="button"
                  onClick={() => setServiceType(serviceType === s.value ? '' : s.value)}
                  className={`sched-chip${serviceType === s.value ? ' is-on' : ''}`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* ── Section B: Book a client ── */}
          <div className="rounded-xl border border-slate-200 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm font-semibold text-slate-800">Book a client for this slot?</span>
              <button
                type="button"
                role="switch"
                aria-checked={bookClient}
                onClick={() => setBookClient((v) => !v)}
                className={`sched-switch${bookClient ? ' is-on' : ''}`}
              >
                <span />
              </button>
            </label>

            {bookClient && (
              <div className="mt-4">
                {/* TODO: re-enable when therapist self-onboarding is allowed again — tab row included "New client"
                <div className="flex rounded-lg border border-slate-200 p-0.5 mb-4">...</div>
                */}

                <div className="space-y-3">
                    <label className="block text-sm font-medium text-slate-700">
                      Case
                      <select
                        className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                        value={caseId}
                        onChange={(e) => {
                          const id = e.target.value
                          setCaseId(id)
                          const c = cases.find((x) => String(x.case_id) === id) || null
                          setSelectedCase(c)
                          if (c?.product_module) setServiceType(c.product_module)
                        }}
                      >
                        <option value="">Select case…</option>
                        {cases.map((c) => (
                          <option key={c.case_id} value={c.case_id}>
                            {c.case_code} · {c.child_name || 'Client'}
                          </option>
                        ))}
                      </select>
                    </label>
                    {handoverPolicy ? (
                      <p className="text-xs text-sky-800 bg-sky-50 border border-sky-100 rounded-lg px-3 py-2" role="status">
                        {TRANSITION_HANDOVER_BANNER}
                        {handoverHint ? ` ${handoverHint}` : ''}
                      </p>
                    ) : null}
                    {selectedCase?.service_address?.formatted ? (
                      <div className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                        <p className="font-medium text-slate-800 text-xs uppercase tracking-wide mb-1">Visit address</p>
                        <p className="text-slate-700">{selectedCase.service_address.formatted}</p>
                        {selectedCase.maps_url ? (
                          <a
                            href={selectedCase.maps_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="mt-1 inline-block text-xs font-semibold" style={{ color: '#294e3f' }}
                          >
                            Open in Maps ↗
                          </a>
                        ) : null}
                      </div>
                    ) : null}
                </div>
                {/* TODO: re-enable when therapist self-onboarding is allowed again — new client invite fields
                ) : (
                  <div className="space-y-3">...</div>
                )}
                */}
              </div>
            )}
          </div>

          {/* ── Section C: Recurring ── */}
          <div className="rounded-xl border border-slate-200 p-4">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-sm font-semibold text-slate-800">Make recurring?</span>
              <button
                type="button"
                role="switch"
                aria-checked={recurring}
                onClick={() => setRecurring((v) => !v)}
                className={`sched-switch${recurring ? ' is-on' : ''}`}
              >
                <span />
              </button>
            </label>

            {recurring && (
              <div className="mt-4 space-y-3">
                <ScheduleWeekdayPicker value={recurWeekdays} onChange={setRecurWeekdays} compact />
                {earlierNote ? <p className="sched-sheet__note">{earlierNote}</p> : null}
                <div className="space-y-2">
                  {[
                    { id: 'this_week', label: 'This week only' },
                    { id: 'until', label: 'Until a date' },
                    { id: 'ongoing', label: `Ongoing (${ONGOING_MATERIALIZE_WEEKS} weeks ahead)` },
                  ].map((m) => (
                    <label key={m.id} className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                      <input
                        type="radio"
                        name="recurScope"
                        checked={recurScope === m.id}
                        onChange={() => setRecurScope(m.id)}
                      />
                      {m.label}
                    </label>
                  ))}
                </div>
                {recurScope === 'until' ? (
                  <label className="block text-sm font-medium text-slate-700">
                    Until
                    <input
                      type="date"
                      value={recurEndDate}
                      min={slotDate}
                      onChange={(e) => setRecurEndDate(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    />
                  </label>
                ) : null}
                {recurScope === 'ongoing' ? (
                  <p className="text-xs text-slate-500">
                    Open slots or bookings repeat through{' '}
                    {slotDate ? resolveRecurEndDate(slotDate) : '…'} — re-run weekly schedule to extend.
                  </p>
                ) : null}
              </div>
            )}
          </div>

          {/* Notes */}
          <label className="block text-sm font-medium text-slate-700">
            Notes (optional)
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>

        </form>
        <div className="sched-sheet__footer">
          <button type="button" onClick={onClose} className="sched-sheet__btn sched-sheet__btn--ghost">
            Cancel
          </button>
          <button
            type="submit"
            form="slot-edit-form"
            disabled={saving}
            className="sched-sheet__btn sched-sheet__btn--primary"
          >
            {saving ? 'Saving…' : mode === 'add' ? 'Save slot' : 'Update slot'}
          </button>
        </div>
      </div>
    </div>
    <BookingSuccessSheet
      open={!!bookingSuccess}
      title="Session booked"
      event={bookingSuccess?.event}
      detailLines={bookingSuccess?.detailLines}
      onClose={() => {
        setBookingSuccess(null)
        onClose()
      }}
    />
    </>,
    document.body,
  )
}
