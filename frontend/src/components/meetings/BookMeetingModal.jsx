import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { mapCmMeetingToCalendarEvent } from '../../lib/googleCalendar.js'
import { BookingSuccessSheet } from '../shared/BookingSuccessSheet.jsx'
import { MeetingAvailabilitySlots } from './MeetingAvailabilitySlots.jsx'
import {
  ATTENDEE_ROLE_LABELS,
  MEETING_TYPES,
  MODAL_INPUT_STYLE,
  MODAL_LABEL_STYLE,
} from './meetingConstants.js'
import { buildMeetingsAvailabilityQuery } from './meetingUtils.js'

export function BookMeetingModal({
  cases,
  onClose,
  onCreated,
  onOpen,
  isTherapistBooking = false,
  initialDate = null,
  initialTime = null,
}) {
  const { user } = useAuth()
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    case_id: '',
    scheduled_date: initialDate || today,
    scheduled_time: initialTime || '10:00',
    duration_minutes: 30,
    meeting_type: 'OBSERVATION_REVIEW',
    other_reason: '',
    title: '',
    meeting_url: '',
  })
  const [attendees, setAttendees] = useState({
    client: true,
    therapist: isTherapistBooking,
    caseManager: true,
    admin: false,
  })
  const [therapistUserId, setTherapistUserId] = useState('')
  const [adminUserId, setAdminUserId] = useState('')
  const [caseSearch, setCaseSearch] = useState('')
  const [guestInput, setGuestInput] = useState('')
  const [guestEmails, setGuestEmails] = useState([])
  const [caseDetail, setCaseDetail] = useState(null)
  const [therapists, setTherapists] = useState([])
  const [adminUsers, setAdminUsers] = useState([])
  const [therapistSlots, setTherapistSlots] = useState(null)
  const [staffSlots, setStaffSlots] = useState(null)
  const [slotsLoading, setSlotsLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [createdMeeting, setCreatedMeeting] = useState(null)

  useEffect(() => {
    onOpen?.()
  }, [onOpen])

  useEffect(() => {
    if (initialDate) setForm((f) => ({ ...f, scheduled_date: initialDate }))
  }, [initialDate])

  useEffect(() => {
    if (initialTime) setForm((f) => ({ ...f, scheduled_time: initialTime }))
  }, [initialTime])

  useEffect(() => {
    if (!isTherapistBooking || form.case_id || cases.length !== 1) return
    setForm((f) => ({ ...f, case_id: String(cases[0].id) }))
  }, [isTherapistBooking, cases, form.case_id])

  useEffect(() => {
    apiFetch('/api/v1/admin/users?page_size=200')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : rows?.items || []
        setAdminUsers(
          list.filter((u) => {
            const roles = u.roles || []
            return (
              roles.includes('MODULE_ADMIN') || roles.includes('SUPER_ADMIN') || roles.includes('ADMIN')
            ) && !roles.includes('SUPERVISOR')
          }),
        )
      })
      .catch(() => setAdminUsers([]))
  }, [])

  useEffect(() => {
    if (!form.case_id) {
      setTherapists([])
      setCaseDetail(null)
      setTherapistUserId('')
      return
    }
    apiFetch(`/api/v1/booking/therapists?case_id=${form.case_id}`)
      .then((rows) => {
        setTherapists(rows || [])
        if (rows?.length === 1) setTherapistUserId(String(rows[0].therapist_user_id))
      })
      .catch(() => setTherapists([]))
    apiFetch(`/api/v1/cases/${form.case_id}`)
      .then(setCaseDetail)
      .catch(() => setCaseDetail(null))
  }, [form.case_id])

  const caseManagerId = useMemo(() => {
    if (caseDetail?.case_manager_user_id) return caseDetail.case_manager_user_id
    if (user?.roles?.includes('CASE_MANAGER')) return user.id
    return user?.id || null
  }, [caseDetail, user])

  useEffect(() => {
    if (isTherapistBooking) {
      if (!form.case_id) {
        setTherapistSlots(null)
        return
      }
      setSlotsLoading(true)
      apiFetch(`/api/v1/booking/slots?case_id=${form.case_id}&date=${form.scheduled_date}`)
        .then(setTherapistSlots)
        .catch(() => setTherapistSlots(null))
        .finally(() => setSlotsLoading(false))
      return
    }

    if (!form.scheduled_date || !caseManagerId) {
      setStaffSlots(null)
      return
    }
    setSlotsLoading(true)
    const qs = buildMeetingsAvailabilityQuery({
      targetDate: form.scheduled_date,
      durationMinutes: form.duration_minutes,
      caseManagerId,
      therapistId: attendees.therapist && therapistUserId ? Number(therapistUserId) : null,
      adminIds: attendees.admin && adminUserId ? [Number(adminUserId)] : [],
    })
    apiFetch(`/api/v1/meetings/availability?${qs}`)
      .then(setStaffSlots)
      .catch(() => setStaffSlots(null))
      .finally(() => setSlotsLoading(false))
  }, [
    isTherapistBooking,
    form.case_id,
    form.scheduled_date,
    form.duration_minutes,
    caseManagerId,
    attendees.therapist,
    attendees.admin,
    therapistUserId,
    adminUserId,
  ])

  function addGuestEmail() {
    const email = guestInput.trim()
    if (!email || !email.includes('@')) {
      setError('Enter a valid guest email')
      return
    }
    if (!guestEmails.includes(email)) setGuestEmails((g) => [...g, email])
    setGuestInput('')
    setError('')
  }

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  function toggleAttendee(key) {
    setAttendees((a) => {
      const next = { ...a, [key]: !a[key] }
      if (key === 'admin' && !next.admin) setAdminUserId('')
      if (key === 'therapist' && !next.therapist) setTherapistUserId('')
      return next
    })
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.meeting_url) {
      setError('Meeting link is required')
      return
    }
    if (!form.scheduled_date) {
      setError('Date is required')
      return
    }
    if (!form.scheduled_time) {
      setError('Pick an available time slot')
      return
    }
    if (isTherapistBooking && !form.case_id) {
      setError('Select a case')
      return
    }
    if (form.meeting_type === 'OTHER' && !form.other_reason.trim() && !form.title.trim()) {
      setError('Looks like we still need a short reason before we can book this meeting.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const body = {
        scheduled_date: form.scheduled_date,
        scheduled_time: form.scheduled_time,
        duration_minutes: Number(form.duration_minutes) || 30,
        meeting_type: form.meeting_type,
        title: form.title.trim() || null,
        meeting_url: form.meeting_url.trim(),
        guest_emails: guestEmails,
        invite_client: attendees.client,
        invite_therapist: attendees.therapist,
        invite_case_manager: attendees.caseManager,
        admin_user_ids: attendees.admin && adminUserId ? [Number(adminUserId)] : [],
      }
      if (form.meeting_type === 'OTHER') {
        body.other_reason = form.other_reason.trim() || form.title.trim() || null
        if (!body.title && body.other_reason) body.title = body.other_reason
      }
      if (form.case_id) body.case_id = Number(form.case_id)
      if (attendees.therapist && therapistUserId) body.therapist_user_id = Number(therapistUserId)
      const result = await apiFetch('/api/v1/meetings', { method: 'POST', body: JSON.stringify(body) })
      setCreatedMeeting(result)
    } catch (err) {
      setError(err.message || 'Could not create meeting')
    } finally {
      setSaving(false)
    }
  }

  const filteredCases = cases.filter((c) => {
    const q = caseSearch.trim().toLowerCase()
    return !q || String(c.childName || '').toLowerCase().includes(q) || String(c.caseCode || c.caseId || c.id).toLowerCase().includes(q)
  })
  const selectedCase = cases.find((c) => String(c.id) === String(form.case_id))

  if (createdMeeting) {
    return (
      <BookingSuccessSheet
        open
        title="Meeting booked"
        event={mapCmMeetingToCalendarEvent(createdMeeting)}
        onClose={() => {
          onCreated(createdMeeting)
          setCreatedMeeting(null)
        }}
      />
    )
  }

  const typeLabel = MEETING_TYPES.find((t) => t.value === form.meeting_type)?.label || ''
  const clientName = caseDetail?.child_name || selectedCase?.childName || ''
  const cmName = caseDetail?.case_manager_name || ''
  const autoTitle = [typeLabel, clientName ? `for ${clientName}` : '', cmName ? `— case of ${cmName}` : ''].filter(Boolean).join(' ')

  const activeSlots = isTherapistBooking ? therapistSlots : staffSlots
  const slotLabel = isTherapistBooking
    ? `Available slots — ${caseDetail?.case_manager_name || 'Case manager'}`
    : `Available slots — ${caseDetail?.case_manager_name || 'Your calendar'}`

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.45)', padding: 16 }}>
      <div style={{ background: '#fff', borderRadius: 20, padding: 24, width: '100%', maxWidth: 540, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.18)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', margin: '0 0 20px' }}>Book a meeting</h2>
        {error ? (
          <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', color: '#991b1b', marginBottom: 12 }}>
            {error}
          </p>
        ) : null}
        <form onSubmit={submit}>
          {!isTherapistBooking ? (
            <label style={MODAL_LABEL_STYLE}>
              Search case
              <input type="search" style={MODAL_INPUT_STYLE} placeholder="Child name or case code" value={caseSearch} onChange={(e) => setCaseSearch(e.target.value)} />
            </label>
          ) : null}
          <label style={MODAL_LABEL_STYLE}>
            {isTherapistBooking ? 'Case *' : 'Case (optional)'}
            <select style={MODAL_INPUT_STYLE} value={form.case_id} required={isTherapistBooking} onChange={(e) => set('case_id', e.target.value)}>
              {!isTherapistBooking ? <option value="">— No specific case —</option> : null}
              {!form.case_id && isTherapistBooking ? <option value="">Choose client…</option> : null}
              {filteredCases.map((c) => (
                <option key={c.id} value={c.id}>{c.childName} ({c.caseCode || c.id})</option>
              ))}
            </select>
          </label>

          {(selectedCase || caseDetail) ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div style={{ background: '#f0f9ff', borderRadius: 10, padding: 10, fontSize: '0.8rem' }}>
                <strong style={{ color: '#0369a1' }}>Client</strong>
                <p style={{ margin: '4px 0 0', fontWeight: 600 }}>{caseDetail?.child_name || selectedCase?.childName}</p>
                <p style={{ margin: 0, color: '#64748b' }}>{caseDetail?.case_code || selectedCase?.caseCode}</p>
              </div>
              <div style={{ background: '#f0fdf4', borderRadius: 10, padding: 10, fontSize: '0.8rem' }}>
                <strong style={{ color: '#15803d' }}>Team</strong>
                <p style={{ margin: '4px 0 0', fontWeight: 600 }}>{caseDetail?.case_manager_name || '—'}</p>
                <p style={{ margin: 0, color: '#64748b' }}>{caseDetail?.active_therapist_name || ''}</p>
              </div>
            </div>
          ) : null}

          <label style={MODAL_LABEL_STYLE}>
            Meeting link *
            <input
              type="url"
              style={{ ...MODAL_INPUT_STYLE, borderColor: !form.meeting_url ? '#fca5a5' : '#e2e8f0' }}
              placeholder="https://meet.google.com/..."
              value={form.meeting_url}
              required
              onChange={(e) => set('meeting_url', e.target.value)}
            />
          </label>

          <label style={MODAL_LABEL_STYLE}>
            Meeting type *
            <select style={MODAL_INPUT_STYLE} value={form.meeting_type} required onChange={(e) => set('meeting_type', e.target.value)}>
              {MEETING_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>

          {form.meeting_type === 'OTHER' ? (
            <label style={MODAL_LABEL_STYLE}>
              Specify meeting reason *
              <input
                type="text"
                style={MODAL_INPUT_STYLE}
                placeholder="e.g. School coordination call"
                value={form.other_reason}
                required
                onChange={(e) => set('other_reason', e.target.value)}
              />
            </label>
          ) : null}

          <label style={MODAL_LABEL_STYLE}>
            Meeting title
            <input
              type="text"
              style={{ ...MODAL_INPUT_STYLE, fontStyle: form.title ? 'normal' : 'italic', color: form.title ? '#1e293b' : '#64748b' }}
              placeholder={autoTitle || 'e.g. Progress review for Aarav M.'}
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
            />
            {!form.title && autoTitle ? (
              <button
                type="button"
                style={{ marginTop: 4, fontSize: '0.72rem', color: '#4f46e5', background: 'none', border: 'none', cursor: 'pointer', padding: 0, textDecoration: 'underline' }}
                onClick={() => set('title', autoTitle)}
              >
                Use: "{autoTitle}"
              </button>
            ) : null}
          </label>

          <label style={MODAL_LABEL_STYLE}>
            Guest emails
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <input
                type="email"
                style={{ ...MODAL_INPUT_STYLE, marginTop: 0, flex: 1 }}
                placeholder="coordinator@school.edu"
                value={guestInput}
                onChange={(e) => setGuestInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addGuestEmail()
                  }
                }}
              />
              <button type="button" style={{ border: '1px solid #c7d2fe', background: '#eef2ff', borderRadius: 10, padding: '8px 12px', fontWeight: 600, cursor: 'pointer' }} onClick={addGuestEmail}>
                Add
              </button>
            </div>
          </label>

          <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 14px', marginBottom: 14 }}>
            <legend style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569', padding: '0 6px' }}>Invite attendees</legend>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input type="checkbox" checked={attendees.client} disabled={!form.case_id} onChange={() => toggleAttendee('client')} />
              {ATTENDEE_ROLE_LABELS.client}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input type="checkbox" checked={attendees.therapist} disabled={!form.case_id} onChange={() => toggleAttendee('therapist')} />
              {ATTENDEE_ROLE_LABELS.therapist}
            </label>
            {attendees.therapist && form.case_id && therapists.length > 0 ? (
              <select style={{ ...MODAL_INPUT_STYLE, marginBottom: 10, marginLeft: 24 }} value={therapistUserId} onChange={(e) => setTherapistUserId(e.target.value)}>
                <option value="">Select therapist…</option>
                {therapists.map((t) => <option key={t.therapist_user_id} value={t.therapist_user_id}>{t.full_name}</option>)}
              </select>
            ) : null}
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input type="checkbox" checked={attendees.caseManager} onChange={() => toggleAttendee('caseManager')} />
              {ATTENDEE_ROLE_LABELS.case_manager}
              {caseDetail?.case_manager_name ? <span style={{ color: '#64748b', fontSize: '0.75rem' }}>({caseDetail.case_manager_name})</span> : null}
            </label>
            {!isTherapistBooking ? (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
                  <input type="checkbox" checked={attendees.admin} onChange={() => toggleAttendee('admin')} />
                  {ATTENDEE_ROLE_LABELS.admin}
                </label>
                {attendees.admin ? (
                  <select style={{ ...MODAL_INPUT_STYLE, marginLeft: 24, marginBottom: 6 }} value={adminUserId} onChange={(e) => setAdminUserId(e.target.value)}>
                    <option value="">Select admin…</option>
                    {adminUsers.map((u) => <option key={u.id} value={u.id}>{u.full_name || u.email}</option>)}
                  </select>
                ) : null}
              </>
            ) : null}
          </fieldset>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
            <label style={MODAL_LABEL_STYLE}>
              Date *
              <input type="date" style={MODAL_INPUT_STYLE} value={form.scheduled_date} required min={today} onChange={(e) => set('scheduled_date', e.target.value)} />
            </label>
            <label style={MODAL_LABEL_STYLE}>
              Duration
              <select style={MODAL_INPUT_STYLE} value={form.duration_minutes} onChange={(e) => set('duration_minutes', e.target.value)}>
                {[30, 45, 60, 90].map((d) => <option key={d} value={d}>{d} min</option>)}
              </select>
            </label>
          </div>

          {(isTherapistBooking ? form.case_id && caseDetail?.case_manager_user_id : caseManagerId) ? (
            <MeetingAvailabilitySlots
              slots={activeSlots}
              loading={slotsLoading}
              selectedTime={form.scheduled_time}
              targetDate={form.scheduled_date}
              label={slotLabel}
              onSelectTime={(time) => set('scheduled_time', time)}
              onSelectDate={(date) => set('scheduled_date', date)}
            />
          ) : null}

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button
              type="submit"
              disabled={saving}
              style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '12px 0', fontWeight: 700, fontSize: '0.9rem', cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}
            >
              {saving ? 'Booking…' : 'Confirm & book meeting'}
            </button>
            <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '12px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={onClose}>
              Close
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
