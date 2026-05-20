import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ClientCalendar } from '../scheduling/ClientCalendar.jsx'
function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString(undefined, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function ApptStatusBadge({ status }) {
  if (status === 'PENDING_THERAPIST') {
    return (
      <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#fef3c7', color: '#92400e', borderRadius: 99, padding: '1px 8px', border: '1px solid #fde68a' }}>
        Pending approval
      </span>
    )
  }
  if (status === 'CANCELLED') {
    return (
      <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#fee2e2', color: '#991b1b', borderRadius: 99, padding: '1px 8px', border: '1px solid #fca5a5' }}>
        Cancelled
      </span>
    )
  }
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#dcfce7', color: '#14532d', borderRadius: 99, padding: '1px 8px', border: '1px solid #bbf7d0' }}>
      Confirmed
    </span>
  )
}

function CMMeetingBadge() {
  return (
    <span style={{ fontSize: '0.7rem', fontWeight: 700, background: '#ede9fe', color: '#4c1d95', borderRadius: 99, padding: '1px 8px', border: '1px solid #c4b5fd' }}>
      Case mgr meeting
    </span>
  )
}

function UpcomingApptSheet({ appt, onReschedule, onCancel, onClose, acting }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-4 sm:items-center" role="dialog" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'center', position: 'fixed', inset: 0, zIndex: 50, background: 'rgba(15,23,42,0.4)', padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 420, background: '#fff', borderRadius: 20, padding: 20, boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
        {appt.isCmMeeting ? (
          <>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#7c3aed', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Case Manager Meeting</p>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 4px' }}>
              {fmtDate(appt.slotDate)}
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 4px' }}>
              {appt.startTime}{appt.endTime ? `–${appt.endTime}` : ''}
            </p>
            {appt.caseMgrName ? <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0 0 12px' }}>With: {appt.caseMgrName}</p> : null}
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 16px' }}>Booked by your case manager — contact them to reschedule.</p>
            <button type="button" style={{ width: '100%', background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '10px 0', fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer' }} onClick={onClose}>Close</button>
          </>
        ) : (
          <>
            <p style={{ fontSize: '0.7rem', fontWeight: 700, color: '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Therapy session</p>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 4px' }}>
              {fmtDate(appt.slotDate)}
            </h3>
            <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 4px' }}>
              {appt.startTime}{appt.endTime ? `–${appt.endTime}` : ''}
            </p>
            {appt.childName ? <p style={{ fontSize: '0.8rem', color: '#64748b', margin: '0 0 2px' }}>{appt.childName}</p> : null}
            {appt.therapistName ? <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 16px' }}>{appt.therapistName}</p> : null}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              <button
                type="button"
                disabled={!appt.canReschedule || acting}
                title={appt.rescheduleReason || ''}
                style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 12, padding: '10px 0', fontSize: '0.875rem', fontWeight: 600, color: '#3730a3', cursor: 'pointer', opacity: !appt.canReschedule ? 0.45 : 1 }}
                onClick={() => onReschedule(appt)}
              >
                Reschedule
              </button>
              <button
                type="button"
                disabled={!appt.canCancel || acting}
                title={appt.cancelReason || ''}
                style={{ background: '#fff', border: '1px solid #fca5a5', borderRadius: 12, padding: '10px 0', fontSize: '0.875rem', fontWeight: 600, color: '#dc2626', cursor: 'pointer', opacity: !appt.canCancel ? 0.45 : 1 }}
                onClick={() => onCancel(appt)}
              >
                Cancel session
              </button>
              <button type="button" style={{ background: 'none', border: 'none', fontSize: '0.875rem', color: '#94a3b8', cursor: 'pointer', padding: '6px 0' }} onClick={onClose}>Close</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export function ClientBookAppointmentPage({ cases }) {
  const [appointments, setAppointments] = useState([])
  const [apptLoading, setApptLoading] = useState(true)

  const [caseId, setCaseId] = useState('')
  const [therapists, setTherapists] = useState([])
  const [therapistId, setTherapistId] = useState('')
  const [calendarRefreshKey, setCalendarRefreshKey] = useState(0)
  const [calendarData, setCalendarData] = useState(null)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [sheet, setSheet] = useState(null)
  const [rescheduleFrom, setRescheduleFrom] = useState(null)
  const [acting, setActing] = useState(false)
  const [selectedAppt, setSelectedAppt] = useState(null)

  function loadAppointments() {
    setApptLoading(true)
    Promise.all([
      apiFetch('/api/v1/parent/appointments').catch(() => []),
      apiFetch('/api/v1/parent/cm-meetings').catch(() => []),
    ]).then(([slots, meetings]) => {
      const slotItems = (slots || []).map((a) => ({
        id: `slot-${a.id}`,
        rawId: a.id,
        isCmMeeting: false,
        childName: a.childName,
        therapistName: a.therapistName,
        slotDate: a.slotDate,
        startTime: a.startTime,
        endTime: a.endTime,
        approvalStatus: a.approval_status || a.approvalStatus || 'CONFIRMED',
        canCancel: a.can_cancel,
        canReschedule: a.can_reschedule,
        rescheduleReason: a.reschedule_reason,
        cancelReason: a.cancel_reason,
      }))
      const meetingItems = (meetings || []).map((m) => ({
        id: `cm-${m.id}`,
        rawId: m.id,
        isCmMeeting: true,
        caseMgrName: m.case_manager_name,
        childName: m.child_name,
        therapistName: null,
        slotDate: m.scheduled_date,
        startTime: m.scheduled_time,
        endTime: null,
        approvalStatus: 'CONFIRMED',
        canCancel: false,
        canReschedule: false,
      }))
      const all = [...slotItems, ...meetingItems].sort((a, b) => {
        const da = (a.slotDate || '') + 'T' + (a.startTime || '00:00')
        const db = (b.slotDate || '') + 'T' + (b.startTime || '00:00')
        return da < db ? -1 : da > db ? 1 : 0
      })
      setAppointments(all)
    }).finally(() => setApptLoading(false))
  }

  useEffect(() => {
    loadAppointments()
  }, [])

  const numericCaseId = () => {
    const c = cases.find((x) => String(x.id) === caseId || String(x.caseId) === caseId)
    return c?.id ?? Number(caseId)
  }

  useEffect(() => {
    if (cases?.length && !caseId) {
      setCaseId(String(cases[0].id ?? cases[0].caseId ?? ''))
    }
  }, [cases, caseId])

  useEffect(() => {
    const id = numericCaseId()
    if (!id) return
    apiFetch(`/api/v1/booking/therapists?case_id=${id}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [caseId, cases])

  useEffect(() => {
    if (therapists.length && !therapistId) {
      setTherapistId(String(therapists[0].therapist_user_id))
    }
  }, [therapists, therapistId])

  function refreshCalendar() {
    setCalendarRefreshKey((k) => k + 1)
    loadAppointments()
  }

  function openSlot(slot) {
    if (rescheduleFrom) {
      if (!slot.is_mine && slot.display_status === 'available') {
        setSheet({ type: 'confirm_reschedule', slot, from: rescheduleFrom })
      }
      return
    }
    if (slot.is_mine) {
      setSheet({ type: 'mine', slot })
    } else {
      setSheet({ type: 'book', slot })
    }
  }

  async function confirmBook(slot) {
    setActing(true)
    setError('')
    try {
      await apiFetch('/api/v1/booking/appointments', {
        method: 'POST',
        body: JSON.stringify({ slot_id: slot.id, case_id: numericCaseId() }),
      })
      setMessage('Appointment booked. Your therapist has been notified.')
      setSheet(null)
      setRescheduleFrom(null)
      refreshCalendar()
    } catch (err) {
      setError(err.message || 'Could not book')
    } finally {
      setActing(false)
    }
  }

  async function confirmReschedule(newSlot) {
    setActing(true)
    setError('')
    try {
      await apiFetch(`/api/v1/parent/appointments/${rescheduleFrom.rawId || rescheduleFrom.id}/reschedule`, {
        method: 'POST',
        body: JSON.stringify({ new_slot_id: newSlot.id }),
      })
      setMessage('Reschedule request sent — your therapist will confirm.')
      setSheet(null)
      setRescheduleFrom(null)
      refreshCalendar()
    } catch (err) {
      setError(err.message || 'Could not reschedule')
    } finally {
      setActing(false)
    }
  }

  async function cancelAppointment(appt) {
    setActing(true)
    setError('')
    try {
      const slotId = appt.rawId || appt.id
      await apiFetch(`/api/v1/parent/appointments/${slotId}/cancel`, { method: 'POST' })
      setMessage('Session cancelled.')
      setSelectedAppt(null)
      refreshCalendar()
    } catch (err) {
      setError(err.message || 'Could not cancel')
    } finally {
      setActing(false)
    }
  }

  function startRescheduleFromStrip(appt) {
    setRescheduleFrom(appt)
    setSelectedAppt(null)
    setMessage('Pick a new open slot on the calendar below.')
  }

  function startReschedule(slot) {
    setRescheduleFrom(slot)
    setSheet(null)
    setMessage('Pick a new open slot on the calendar.')
  }

  return (
    <div className="space-y-4" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <h1 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#1e293b', margin: '0 0 4px' }}>Session schedule</h1>
        <p style={{ fontSize: '0.875rem', color: '#64748b', margin: 0 }}>
          View and manage your upcoming sessions, or book a new one below.
        </p>
      </div>

      {message ? <p style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, padding: '8px 12px', fontSize: '0.875rem', color: '#14532d', margin: 0 }}>{message}</p> : null}
      {error ? <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 10, padding: '8px 12px', fontSize: '0.875rem', color: '#991b1b', margin: 0 }}>{error}</p> : null}

      {/* Upcoming sessions strip */}
      <section>
        <h2 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#475569', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Upcoming sessions
        </h2>
        {apptLoading ? (
          <p style={{ fontSize: '0.875rem', color: '#94a3b8' }}>Loading…</p>
        ) : appointments.length === 0 ? (
          <p style={{ fontSize: '0.875rem', color: '#94a3b8' }}>No upcoming sessions booked yet.</p>
        ) : (
          <div style={{ display: 'flex', gap: 10, overflowX: 'auto', paddingBottom: 4 }}>
            {appointments.map((appt) => (
              <button
                key={appt.id}
                type="button"
                onClick={() => setSelectedAppt(appt)}
                style={{
                  flex: '0 0 auto',
                  minWidth: 175,
                  maxWidth: 205,
                  background: appt.isCmMeeting ? '#faf5ff' : '#fff',
                  border: `1px solid ${appt.isCmMeeting ? '#ddd6fe' : '#e2e8f0'}`,
                  borderRadius: 14,
                  padding: '12px 13px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
                }}
              >
                <p style={{ fontSize: '0.7rem', fontWeight: 700, color: appt.isCmMeeting ? '#7c3aed' : '#4f46e5', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '0 0 4px' }}>
                  {fmtDate(appt.slotDate)}
                </p>
                <p style={{ fontSize: '0.875rem', fontWeight: 600, color: '#1e293b', margin: '0 0 4px' }}>
                  {appt.startTime}{appt.endTime ? `–${appt.endTime}` : ''}
                </p>
                <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 6px' }}>
                  {appt.childName || appt.caseMgrName || '—'}
                </p>
                <div>
                  {appt.isCmMeeting ? <CMMeetingBadge /> : <ApptStatusBadge status={appt.approvalStatus} />}
                </div>
              </button>
            ))}
          </div>
        )}
      </section>

      {rescheduleFrom ? (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 10, padding: '8px 12px', fontSize: '0.875rem', color: '#3730a3', flexWrap: 'wrap', gap: 8 }}>
          <span>Rescheduling {rescheduleFrom.slotDate || rescheduleFrom.slot_date} {rescheduleFrom.startTime || rescheduleFrom.start_time} — tap an open slot below</span>
          <button type="button" style={{ fontWeight: 700, fontSize: '0.8rem', background: 'none', border: 'none', cursor: 'pointer', color: '#3730a3', textDecoration: 'underline' }} onClick={() => { setRescheduleFrom(null); setMessage('') }}>Cancel</button>
        </div>
      ) : null}

      {/* Book a new session */}
      <section>
        <h2 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#475569', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Book a new session
        </h2>

        {calendarData?.booking?.booking_mode === 'FIXED' && calendarData?.booking?.fixed_window_label ? (
          <p style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 12px', fontSize: '0.875rem', color: '#475569', marginBottom: 12 }}>
            Your usual window: <strong>{calendarData.booking.fixed_window_label}</strong>
            {calendarData.booking.has_recurring ? ' · Recurring sessions may already be booked.' : ''}
          </p>
        ) : null}

        {calendarData?.reschedules_left != null ? (
          <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: 8 }}>{calendarData.reschedules_left} reschedule(s) left this month</p>
        ) : null}

        <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(220px,1fr))', marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#475569' }}>
            Case
            <select style={{ display: 'block', marginTop: 4, width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem' }} value={caseId} onChange={(e) => { setCaseId(e.target.value); setTherapistId('') }}>
              {(cases || []).map((c) => (
                <option key={c.id || c.caseId} value={c.id || c.caseId}>
                  {c.childName} ({c.caseId})
                </option>
              ))}
            </select>
          </label>
          <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 500, color: '#475569' }}>
            Therapist
            <select style={{ display: 'block', marginTop: 4, width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem' }} value={therapistId} onChange={(e) => setTherapistId(e.target.value)}>
              {therapists.map((t) => (
                <option key={t.therapist_user_id} value={t.therapist_user_id}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <ClientCalendar
          caseId={numericCaseId()}
          therapistId={therapistId}
          onSlotClick={openSlot}
          selectedSlotId={sheet?.slot?.id}
          refreshKey={calendarRefreshKey}
          onCalendarLoad={setCalendarData}
        />
      </section>

      {/* Calendar booking sheet */}
      {sheet ? (
        <div style={{ position: 'fixed', inset: 0, zIndex: 50, display: 'flex', alignItems: 'flex-end', justifyContent: 'center', background: 'rgba(15,23,42,0.4)', padding: 16 }} role="dialog">
          <div style={{ width: '100%', maxWidth: 420, background: '#fff', borderRadius: 20, padding: 20, boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
            {sheet.type === 'book' ? (
              <>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 4px' }}>Book session</h3>
                <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 16px' }}>{sheet.slot.slot_date} · {sheet.slot.start_time}–{sheet.slot.end_time}</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" disabled={acting} style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '11px 0', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }} onClick={() => confirmBook(sheet.slot)}>Confirm booking</button>
                  <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '11px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={() => setSheet(null)}>Close</button>
                </div>
              </>
            ) : null}

            {sheet.type === 'mine' ? (
              <>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 4px' }}>Your session</h3>
                <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 4px' }}>{sheet.slot.slot_date} · {sheet.slot.start_time}–{sheet.slot.end_time}</p>
                {sheet.slot.hours_until_start != null ? <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 16px' }}>Starts in {sheet.slot.hours_until_start} hours</p> : null}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <button type="button" disabled={!sheet.slot.can_reschedule || acting} title={sheet.slot.reschedule_reason || ''} style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 12, padding: '10px 0', fontWeight: 600, fontSize: '0.875rem', color: '#3730a3', cursor: 'pointer', opacity: !sheet.slot.can_reschedule ? 0.5 : 1 }} onClick={() => startReschedule(sheet.slot)}>
                    Reschedule{sheet.slot.reschedules_left != null ? ` (${sheet.slot.reschedules_left} left)` : ''}
                  </button>
                  <button type="button" disabled={!sheet.slot.can_cancel || acting} title={sheet.slot.cancel_reason || ''} style={{ background: '#fff', border: '1px solid #fca5a5', borderRadius: 12, padding: '10px 0', fontWeight: 600, fontSize: '0.875rem', color: '#dc2626', cursor: 'pointer', opacity: !sheet.slot.can_cancel ? 0.5 : 1 }} onClick={() => cancelAppointment({ rawId: sheet.slot.id, ...sheet.slot })}>
                    Cancel session
                  </button>
                  <button type="button" style={{ background: 'none', border: 'none', fontSize: '0.875rem', color: '#94a3b8', cursor: 'pointer', padding: '6px 0' }} onClick={() => setSheet(null)}>Close</button>
                </div>
              </>
            ) : null}

            {sheet.type === 'confirm_reschedule' ? (
              <>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b', margin: '0 0 4px' }}>Confirm new time</h3>
                <p style={{ fontSize: '0.875rem', color: '#475569', margin: '0 0 16px' }}>Move to {sheet.slot.slot_date} · {sheet.slot.start_time}</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button type="button" disabled={acting} style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '11px 0', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }} onClick={() => confirmReschedule(sheet.slot)}>Confirm</button>
                  <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '11px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={() => setSheet(null)}>Back</button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Upcoming session detail sheet */}
      {selectedAppt ? (
        <UpcomingApptSheet
          appt={selectedAppt}
          acting={acting}
          onReschedule={startRescheduleFromStrip}
          onCancel={cancelAppointment}
          onClose={() => setSelectedAppt(null)}
        />
      ) : null}
    </div>
  )
}
