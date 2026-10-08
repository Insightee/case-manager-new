import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { mapParentBookedSlotToCalendarEvent } from '../../lib/googleCalendar.js'
import { formatDisplayDateLabel, todayIsoIST } from '../../lib/datetime.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'
import {
  handoverBookingHintForTherapist,
  handoverPolicyFromTherapists,
  normalizeBookingErrorMessage,
  TRANSITION_PARENT_BOOKING_HINT,
} from '../../lib/therapistTransitionBooking.js'

function todayIso() {
  return todayIsoIST()
}

function childSelectLabel(c) {
  const name = c.childName || 'Your child'
  const therapist = c.therapist && c.therapist !== '—' ? c.therapist : null
  return therapist ? `${name} · ${therapist}` : name
}

/**
 * Compact parent booking: pick child → therapist → date → open slot → confirm.
 * Replaces month calendar grid on the session schedule page.
 */
export function ParentBookSessionForm({
  cases = [],
  rescheduleFrom = null,
  onCancelReschedule,
  onBookSuccess,
  onRescheduleSuccess,
  acting,
  setActing,
  setError,
  setMessage,
}) {
  const [caseId, setCaseId] = useState('')
  const [therapists, setTherapists] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [selectedDate, setSelectedDate] = useState(todayIso())
  const [slots, setSlots] = useState([])
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [selectedSlotId, setSelectedSlotId] = useState('')
  const [bookingSuccess, setBookingSuccess] = useState(null)
  const [nextSlotLoading, setNextSlotLoading] = useState(false)
  const [noOpenSlotInHorizon, setNoOpenSlotInHorizon] = useState(false)
  const [requestDate, setRequestDate] = useState(todayIso())
  const [requestNote, setRequestNote] = useState('')
  const autoSlotRef = useRef(null)

  const numericCaseId = useMemo(() => {
    const c = cases.find((x) => String(x.id) === caseId || String(x.caseId) === caseId)
    return c?.id ?? (caseId ? Number(caseId) : null)
  }, [cases, caseId])

  useEffect(() => {
    if (rescheduleFrom) {
      const cid = rescheduleFrom.caseDbId
      if (cid) setCaseId(String(cid))
      if (rescheduleFrom.therapistUserId) {
        setTherapistId(String(rescheduleFrom.therapistUserId))
      }
      return
    }
    if (cases?.length && !caseId) {
      setCaseId(String(cases[0].id ?? cases[0].caseId ?? ''))
    }
  }, [cases, caseId, rescheduleFrom])

  useEffect(() => {
    if (!numericCaseId || rescheduleFrom) return
    apiFetch(`/api/v1/booking/therapists?case_id=${numericCaseId}`)
      .then(setTherapists)
      .catch((err) => {
        setTherapists([])
        setError(err.message || 'Could not load therapists')
      })
  }, [numericCaseId, rescheduleFrom, setError])

  useEffect(() => {
    if (rescheduleFrom?.therapistUserId) return
    if (therapists.length && !therapistId) {
      setTherapistId(String(therapists[0].therapist_user_id))
    }
  }, [therapists, therapistId, rescheduleFrom])

  useEffect(() => {
    if (!numericCaseId || !therapistId || rescheduleFrom) {
      setNoOpenSlotInHorizon(false)
      return
    }
    let cancelled = false
    setNextSlotLoading(true)
    apiFetch(
      `/api/v1/parent/booking/next-open-slot?case_id=${numericCaseId}&therapist_id=${therapistId}&horizon_days=7`,
    )
      .then((data) => {
        if (cancelled) return
        const slot = data?.next_slot
        if (slot?.slot_date) {
          setNoOpenSlotInHorizon(false)
          autoSlotRef.current = slot.id != null ? String(slot.id) : null
          setSelectedDate(slot.slot_date)
        } else {
          setNoOpenSlotInHorizon(true)
          autoSlotRef.current = null
          setRequestDate(todayIso())
        }
      })
      .catch(() => {
        if (!cancelled) setNoOpenSlotInHorizon(false)
      })
      .finally(() => {
        if (!cancelled) setNextSlotLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [numericCaseId, therapistId, rescheduleFrom])

  const handoverPolicy = useMemo(() => handoverPolicyFromTherapists(therapists), [therapists])
  const handoverHint = useMemo(
    () => handoverBookingHintForTherapist(handoverPolicy, therapistId),
    [handoverPolicy, therapistId],
  )

  const loadSlots = useCallback(async () => {
    if (!therapistId || !selectedDate) {
      setSlots([])
      return
    }
    setSlotsLoading(true)
    setError('')
    try {
      let rows = []
      if (numericCaseId && !rescheduleFrom) {
        const cal = await apiFetch(
          `/api/v1/parent/booking/calendar?case_id=${numericCaseId}&therapist_id=${therapistId}&from_date=${selectedDate}&to_date=${selectedDate}`,
        )
        rows = (cal?.slots || []).filter((s) => s.display_status === 'available')
      } else {
        rows = await apiFetch(
          `/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${selectedDate}&to_date=${selectedDate}${numericCaseId ? `&case_id=${numericCaseId}` : ''}`,
        )
      }
      setSlots(rows || [])
      setSelectedSlotId('')
    } catch (err) {
      setSlots([])
      setError(err.message || 'Could not load available times')
    } finally {
      setSlotsLoading(false)
    }
  }, [therapistId, selectedDate, numericCaseId, rescheduleFrom, setError])

  useEffect(() => {
    loadSlots()
  }, [loadSlots])

  useEffect(() => {
    const targetId = autoSlotRef.current
    if (!targetId || !slots.length) return
    const match = slots.find((s) => String(s.id) === String(targetId))
    if (match) {
      setSelectedSlotId(String(match.id))
      autoSlotRef.current = null
    }
  }, [slots])

  async function handleConfirm() {
    if (!selectedSlotId || !numericCaseId) return
    setActing(true)
    setError('')
    try {
      if (rescheduleFrom) {
        const slotId = rescheduleFrom.rawId || rescheduleFrom.id
        await apiFetch(`/api/v1/parent/appointments/${slotId}/reschedule`, {
          method: 'POST',
          body: JSON.stringify({ new_slot_id: Number(selectedSlotId) }),
        })
        setMessage('Reschedule request sent — your therapist will confirm.')
        onRescheduleSuccess?.()
      } else {
        const bookedSlot = slots.find((s) => String(s.id) === String(selectedSlotId))
        const caseRow = cases.find((c) => String(c.id ?? c.caseId) === String(caseId))
        const therapistName = therapists.find((t) => String(t.therapist_user_id) === therapistId)?.full_name
        await apiFetch('/api/v1/booking/appointments', {
          method: 'POST',
          body: JSON.stringify({ slot_id: Number(selectedSlotId), case_id: numericCaseId }),
        })
        const event = mapParentBookedSlotToCalendarEvent({ slot: bookedSlot, caseRow, therapistName })
        setBookingSuccess({
          event,
          detailLines: [
            caseRow?.childName ? `Child: ${caseRow.childName}` : null,
            therapistName ? `Therapist: ${therapistName}` : null,
          ].filter(Boolean),
        })
        setMessage('Appointment booked. Your therapist has been notified.')
        onBookSuccess?.()
      }
      setSelectedSlotId('')
    } catch (err) {
      setError(
        normalizeBookingErrorMessage(err.message) ||
          (rescheduleFrom ? 'Could not reschedule' : 'Could not book'),
      )
    } finally {
      setActing(false)
    }
  }

  async function handleRequestMeeting() {
    if (!numericCaseId || !therapistId || !requestDate) return
    setActing(true)
    setError('')
    try {
      await apiFetch('/api/v1/parent/booking/meeting-requests', {
        method: 'POST',
        body: JSON.stringify({
          case_id: numericCaseId,
          therapist_user_id: Number(therapistId),
          requested_date: requestDate,
          note: requestNote.trim() || undefined,
        }),
      })
      setMessage(
        `We shared your preferred date (${formatDisplayDateLabel(requestDate)}) with your therapist. They will add a time when they can.`,
      )
      setRequestNote('')
    } catch (err) {
      setError(err.message || 'Could not send your meeting request')
    } finally {
      setActing(false)
    }
  }

  const isReschedule = !!rescheduleFrom
  const showMeetingRequest = !isReschedule && noOpenSlotInHorizon && !nextSlotLoading
  const slotsEmptyOnDay = !slotsLoading && slots.length === 0

  return (
    <div className="parent-book-form">
      {isReschedule ? (
        <div className="parent-book-form__banner">
          <span>
            Rescheduling {formatDisplayDateLabel(rescheduleFrom.slotDate)} · {rescheduleFrom.startTime}
            {rescheduleFrom.endTime ? `–${rescheduleFrom.endTime}` : ''}
            {rescheduleFrom.therapistName ? ` · ${rescheduleFrom.therapistName}` : ''}
          </span>
          <button type="button" className="parent-book-form__banner-cancel" onClick={onCancelReschedule}>
            Cancel
          </button>
        </div>
      ) : null}

      {isReschedule ? (
        <p className="parent-book-form__help" style={{ marginTop: 0 }}>
          Pick a new slot with {rescheduleFrom.therapistName || 'your therapist'}.
        </p>
      ) : null}

      {!isReschedule && nextSlotLoading ? (
        <p className="parent-book-form__help parent-book-form__help--muted">Finding the next open time…</p>
      ) : null}
      {handoverPolicy ? (
        <p className="parent-book-form__help parent-book-form__help--handover" role="status">
          {TRANSITION_PARENT_BOOKING_HINT}
          {handoverHint ? ` ${handoverHint}` : ''}
        </p>
      ) : null}

      <div className="parent-book-form__grid">
        <label className="parent-book-form__field">
          Child
          <select
            value={caseId}
            onChange={(e) => {
              setCaseId(e.target.value)
              setTherapistId('')
            }}
            disabled={isReschedule}
            aria-label="Select child"
          >
            {(cases || []).map((c) => (
              <option key={c.id || c.caseId} value={c.id || c.caseId}>
                {childSelectLabel(c)}
              </option>
            ))}
          </select>
        </label>

        <label className="parent-book-form__field">
          Therapist
          {isReschedule ? (
            <input type="text" readOnly value={rescheduleFrom.therapistName || 'Your therapist'} />
          ) : (
            <select
              value={therapistId}
              onChange={(e) => setTherapistId(e.target.value)}
              disabled={!therapists.length}
            >
              {therapists.map((t) => (
                <option key={t.therapist_user_id} value={t.therapist_user_id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          )}
        </label>

        <label className="parent-book-form__field">
          Date
          <input
            type="date"
            min={todayIso()}
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </label>

        <label className="parent-book-form__field parent-book-form__field--wide">
          Available time
          <select
            value={selectedSlotId}
            onChange={(e) => setSelectedSlotId(e.target.value)}
            disabled={slotsLoading || slots.length === 0}
          >
            <option value="">
              {slotsLoading
                ? 'Loading slots…'
                : slots.length === 0
                  ? 'No times available this day'
                  : 'Choose a time'}
            </option>
            {slots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.start_time}–{s.end_time}
              </option>
            ))}
          </select>
        </label>
      </div>

      {showMeetingRequest ? (
        <div className="parent-book-form__request" role="region" aria-label="Request a meeting">
          <p className="parent-book-form__request-lead">
            No open times in the next 7 days. Pick a date that works for you — your therapist will see the request on
            their schedule and can add a slot that day.
          </p>
          <label className="parent-book-form__field">
            Preferred date
            <input
              type="date"
              min={todayIso()}
              value={requestDate}
              onChange={(e) => setRequestDate(e.target.value)}
            />
          </label>
          <label className="parent-book-form__field parent-book-form__field--wide">
            Note for therapist <span className="parent-book-form__optional">(optional)</span>
            <textarea
              rows={2}
              maxLength={500}
              value={requestNote}
              onChange={(e) => setRequestNote(e.target.value)}
              placeholder="Anything helpful about timing or context"
            />
          </label>
          <button
            type="button"
            className="parent-book-form__primary"
            disabled={acting || !requestDate}
            onClick={handleRequestMeeting}
          >
            {acting ? 'Sending…' : 'Request a meeting'}
          </button>
        </div>
      ) : null}

      {!showMeetingRequest && slotsEmptyOnDay && !nextSlotLoading && !isReschedule ? (
        <p className="parent-book-form__help parent-book-form__help--muted">
          Try another date, or refresh slots after your therapist opens new times.
        </p>
      ) : null}

      <div className="parent-book-form__actions">
        <button
          type="button"
          className="parent-book-form__primary"
          disabled={acting || !selectedSlotId}
          onClick={handleConfirm}
        >
          {acting ? 'Saving…' : isReschedule ? 'Confirm new time' : 'Book session'}
        </button>
        <button type="button" className="parent-book-form__ghost" onClick={loadSlots} disabled={slotsLoading}>
          Refresh slots
        </button>
      </div>

      <p className="parent-book-form__footer">
        <Link to="/parent/session-logs">View past session notes and feedback →</Link>
      </p>

      <BookingSuccessSheet
        open={!!bookingSuccess && !isReschedule}
        title="Session booked"
        event={bookingSuccess?.event}
        detailLines={bookingSuccess?.detailLines}
        onClose={() => setBookingSuccess(null)}
      />
    </div>
  )
}
