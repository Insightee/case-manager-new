import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'

function todayIso() {
  const d = new Date()
  return d.toISOString().slice(0, 10)
}

function fmtDateLabel(iso) {
  if (!iso) return ''
  return new Date(iso + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

/**
 * Compact parent booking: pick case → therapist → date → open slot → confirm.
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

  const numericCaseId = useMemo(() => {
    const c = cases.find((x) => String(x.id) === caseId || String(x.caseId) === caseId)
    return c?.id ?? (caseId ? Number(caseId) : null)
  }, [cases, caseId])

  useEffect(() => {
    if (cases?.length && !caseId) {
      setCaseId(String(cases[0].id ?? cases[0].caseId ?? ''))
    }
  }, [cases, caseId])

  useEffect(() => {
    if (!numericCaseId) return
    apiFetch(`/api/v1/booking/therapists?case_id=${numericCaseId}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [numericCaseId])

  useEffect(() => {
    if (therapists.length && !therapistId) {
      setTherapistId(String(therapists[0].therapist_user_id))
    }
  }, [therapists, therapistId])

  const loadSlots = useCallback(async () => {
    if (!therapistId || !selectedDate) {
      setSlots([])
      return
    }
    setSlotsLoading(true)
    setError('')
    try {
      const rows = await apiFetch(
        `/api/v1/booking/availability?therapist_id=${therapistId}&from_date=${selectedDate}&to_date=${selectedDate}`,
      )
      setSlots(rows || [])
      setSelectedSlotId('')
    } catch (err) {
      setSlots([])
      setError(err.message || 'Could not load open slots')
    } finally {
      setSlotsLoading(false)
    }
  }, [therapistId, selectedDate, setError])

  useEffect(() => {
    loadSlots()
  }, [loadSlots])

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
        await apiFetch('/api/v1/booking/appointments', {
          method: 'POST',
          body: JSON.stringify({ slot_id: Number(selectedSlotId), case_id: numericCaseId }),
        })
        setMessage('Appointment booked. Your therapist has been notified.')
        onBookSuccess?.()
      }
      setSelectedSlotId('')
    } catch (err) {
      setError(err.message || (rescheduleFrom ? 'Could not reschedule' : 'Could not book'))
    } finally {
      setActing(false)
    }
  }

  const isReschedule = !!rescheduleFrom

  return (
    <div className="parent-book-form">
      {isReschedule ? (
        <div className="parent-book-form__banner">
          <span>
            Rescheduling {fmtDateLabel(rescheduleFrom.slotDate)} · {rescheduleFrom.startTime}
            {rescheduleFrom.endTime ? `–${rescheduleFrom.endTime}` : ''}
          </span>
          <button type="button" className="parent-book-form__banner-cancel" onClick={onCancelReschedule}>
            Cancel
          </button>
        </div>
      ) : null}

      <p className="parent-book-form__help">
        Your <strong>therapist</strong> is assigned for therapy sessions. Your <strong>case manager</strong> is assigned
        separately by the clinic — they may schedule review meetings with you directly.
      </p>

      <div className="parent-book-form__grid">
        <label className="parent-book-form__field">
          Case
          <select
            value={caseId}
            onChange={(e) => {
              setCaseId(e.target.value)
              setTherapistId('')
            }}
            disabled={isReschedule}
          >
            {(cases || []).map((c) => (
              <option key={c.id || c.caseId} value={c.id || c.caseId}>
                {c.childName} ({c.caseId})
              </option>
            ))}
          </select>
        </label>

        <label className="parent-book-form__field">
          Therapist
          <select
            value={therapistId}
            onChange={(e) => setTherapistId(e.target.value)}
            disabled={isReschedule || !therapists.length}
          >
            {therapists.map((t) => (
              <option key={t.therapist_user_id} value={t.therapist_user_id}>
                {t.full_name}
              </option>
            ))}
          </select>
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

        <label className="parent-book-form__field">
          Open slot
          <select
            value={selectedSlotId}
            onChange={(e) => setSelectedSlotId(e.target.value)}
            disabled={slotsLoading || slots.length === 0}
          >
            <option value="">
              {slotsLoading
                ? 'Loading slots…'
                : slots.length === 0
                  ? 'No open slots this day'
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
    </div>
  )
}
