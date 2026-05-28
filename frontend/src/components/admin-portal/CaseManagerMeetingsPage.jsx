import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminCollapsibleFilters, AdminPageHeader, AdminSearchInput, FilterSelect } from './ui/index.js'
import './admin-reports.css'

const MEETING_TYPES = [
  { value: 'CLIENT_ONLY', label: 'Progress review' },
  { value: 'CLIENT_AND_THERAPIST', label: 'Care coordination' },
  { value: 'IEP_MEETING', label: 'IEP discussion' },
]

const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'SCHEDULED', label: 'Scheduled' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

const TYPE_FILTER_OPTIONS = [
  { value: '', label: 'All types' },
  ...MEETING_TYPES,
]

const MONTH_FILTER_OPTIONS = [
  { value: '', label: 'All months' },
  { value: '1', label: 'January' },
  { value: '2', label: 'February' },
  { value: '3', label: 'March' },
  { value: '4', label: 'April' },
  { value: '5', label: 'May' },
  { value: '6', label: 'June' },
  { value: '7', label: 'July' },
  { value: '8', label: 'August' },
  { value: '9', label: 'September' },
  { value: '10', label: 'October' },
  { value: '11', label: 'November' },
  { value: '12', label: 'December' },
]

const SEARCH_DEBOUNCE_MS = 350

const ATTENDEE_ROLE_LABELS = {
  client: 'Client (parent)',
  therapist: 'Therapist',
  case_manager: 'Case manager',
  admin: 'Admin',
}

const STATUS_LABELS = {
  SCHEDULED: { label: 'Scheduled', bg: '#dbeafe', color: '#1e40af' },
  COMPLETED: { label: 'Completed', bg: '#dcfce7', color: '#14532d' },
  CANCELLED: { label: 'Cancelled', bg: '#fee2e2', color: '#991b1b' },
}

function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || { label: status, bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.72rem', fontWeight: 700, borderRadius: 99, padding: '2px 9px', background: s.bg, color: s.color, border: `1px solid ${s.color}22` }}>
      {s.label}
    </span>
  )
}

function BookMeetingModal({ cases, onClose, onCreated, onOpen, canPickAdmin = true, isTherapistBooking = false }) {
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    case_id: '',
    scheduled_date: today,
    scheduled_time: '10:00',
    duration_minutes: 30,
    meeting_type: 'CLIENT_ONLY',
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
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    onOpen?.()
  }, [onOpen])

  const filteredCases = useMemo(() => {
    const q = caseSearch.trim().toLowerCase()
    if (!q) return cases
    return cases.filter(
      (c) =>
        String(c.childName || '').toLowerCase().includes(q)
        || String(c.caseCode || c.caseId || c.id).toLowerCase().includes(q)
    )
  }, [cases, caseSearch])

  const selectedCase = cases.find((c) => String(c.id) === String(form.case_id))

  useEffect(() => {
    if (!canPickAdmin) return
    apiFetch('/api/v1/admin/users?page_size=200')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : rows?.items || []
        setAdminUsers(
          list.filter((u) => {
            const roles = u.roles || []
            return (
              roles.includes('MODULE_ADMIN')
              || roles.includes('SUPER_ADMIN')
              || roles.includes('ADMIN')
            ) && !roles.includes('SUPERVISOR')
          }),
        )
      })
      .catch(() => setAdminUsers([]))
  }, [canPickAdmin])

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
    if (!form.scheduled_date) { setError('Date is required'); return }
    if (!attendees.client && !attendees.therapist && !attendees.caseManager && !attendees.admin) {
      setError('Select at least one attendee')
      return
    }
    if (attendees.therapist && form.case_id && therapists.length > 0 && !therapistUserId) {
      setError('Choose a therapist to invite')
      return
    }
    if (attendees.admin && canPickAdmin && !adminUserId) {
      setError('Choose an admin to invite')
      return
    }
    setSaving(true)
    setError('')
    try {
      const body = {
        scheduled_date: form.scheduled_date,
        scheduled_time: form.scheduled_time || null,
        duration_minutes: Number(form.duration_minutes) || 30,
        meeting_type: form.meeting_type,
        title: form.title || null,
        meeting_url: form.meeting_url?.trim() || null,
        guest_emails: guestEmails,
        invite_client: attendees.client,
        invite_therapist: attendees.therapist,
        invite_case_manager: attendees.caseManager,
        admin_user_ids: attendees.admin && adminUserId ? [Number(adminUserId)] : [],
      }
      if (form.case_id) body.case_id = Number(form.case_id)
      if (attendees.therapist && therapistUserId) body.therapist_user_id = Number(therapistUserId)
      const result = await apiFetch('/api/v1/cm-meetings', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      onCreated(result)
    } catch (err) {
      setError(err.message || 'Could not create meeting')
    } finally {
      setSaving(false)
    }
  }

  const inputStyle = { display: 'block', width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem', marginTop: 4, boxSizing: 'border-box' }
  const labelStyle = { fontSize: '0.875rem', fontWeight: 500, color: '#475569', display: 'block', marginBottom: 12 }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.45)', padding: 16 }}>
      <div style={{ background: '#fff', borderRadius: 20, padding: 24, width: '100%', maxWidth: 520, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.18)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', margin: '0 0 20px' }}>Book a case manager meeting</h2>
        {error ? <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', color: '#991b1b', marginBottom: 12 }}>{error}</p> : null}
        <form onSubmit={submit}>
          <label style={labelStyle}>
            Search case
            <input
              type="search"
              style={inputStyle}
              placeholder="Child name or case code"
              value={caseSearch}
              onChange={(e) => setCaseSearch(e.target.value)}
            />
          </label>
          <label style={labelStyle}>
            Case (optional)
            <select style={inputStyle} value={form.case_id} onChange={(e) => set('case_id', e.target.value)}>
              <option value="">— No specific case —</option>
              {filteredCases.map((c) => (
                <option key={c.id} value={c.id}>{c.childName} ({c.caseCode || c.caseId || c.id})</option>
              ))}
            </select>
          </label>

          {selectedCase || caseDetail ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div style={{ background: '#f8fafc', borderRadius: 10, padding: 10, fontSize: '0.8rem' }}>
                <strong>Client</strong>
                <p style={{ margin: '4px 0 0' }}>{caseDetail?.child_name || selectedCase?.childName}</p>
                <p style={{ margin: 0, color: '#64748b' }}>{caseDetail?.case_code || selectedCase?.caseCode}</p>
              </div>
              <div style={{ background: '#f8fafc', borderRadius: 10, padding: 10, fontSize: '0.8rem' }}>
                <strong>Assigned team</strong>
                <p style={{ margin: '4px 0 0' }}>{caseDetail?.active_therapist_name || '—'}</p>
                <p style={{ margin: 0, color: '#64748b' }}>{caseDetail?.case_manager_name || '—'}</p>
              </div>
            </div>
          ) : null}

          <label style={labelStyle}>
            Meeting link (optional)
            <input
              type="url"
              style={inputStyle}
              placeholder="https://meet.google.com/..."
              value={form.meeting_url}
              onChange={(e) => set('meeting_url', e.target.value)}
            />
          </label>

          <label style={labelStyle}>
            Guest emails
            <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
              <input
                type="email"
                style={{ ...inputStyle, marginTop: 0, flex: 1 }}
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
            {guestEmails.length > 0 ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                {guestEmails.map((email) => (
                  <span key={email} style={{ background: '#e0e7ff', color: '#3730a3', borderRadius: 99, padding: '4px 10px', fontSize: '0.75rem', fontWeight: 600 }}>
                    {email}
                    <button type="button" style={{ marginLeft: 6, border: 'none', background: 'transparent', cursor: 'pointer', color: '#6366f1' }} onClick={() => setGuestEmails((g) => g.filter((x) => x !== email))}>×</button>
                  </span>
                ))}
              </div>
            ) : null}
          </label>

          <label style={labelStyle}>
            Meeting type
            <select style={inputStyle} value={form.meeting_type} onChange={(e) => set('meeting_type', e.target.value)}>
              {MEETING_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>

          <fieldset style={{ border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 14px', marginBottom: 12 }}>
            <legend style={{ fontSize: '0.875rem', fontWeight: 600, color: '#475569', padding: '0 6px' }}>
              Invite attendees
            </legend>
            <p style={{ margin: '0 0 10px', fontSize: '0.78rem', color: '#64748b' }}>
              Invited people receive a notification and see this meeting in their CM meetings list and calendar.
            </p>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={attendees.client}
                disabled={!form.case_id}
                onChange={() => toggleAttendee('client')}
              />
              {ATTENDEE_ROLE_LABELS.client}
              {!form.case_id ? <span style={{ color: '#94a3b8', fontSize: '0.75rem' }}>(select a case)</span> : null}
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={attendees.therapist}
                disabled={!form.case_id}
                onChange={() => toggleAttendee('therapist')}
              />
              {ATTENDEE_ROLE_LABELS.therapist}
            </label>
            {attendees.therapist && form.case_id && therapists.length > 0 ? (
              <select
                style={{ ...inputStyle, marginBottom: 10, marginLeft: 24 }}
                value={therapistUserId}
                onChange={(e) => setTherapistUserId(e.target.value)}
              >
                <option value="">Select therapist…</option>
                {therapists.map((t) => (
                  <option key={t.therapist_user_id} value={t.therapist_user_id}>{t.full_name}</option>
                ))}
              </select>
            ) : null}
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
              <input
                type="checkbox"
                checked={attendees.caseManager}
                onChange={() => toggleAttendee('caseManager')}
              />
              {ATTENDEE_ROLE_LABELS.case_manager}
              {caseDetail?.case_manager_name ? (
                <span style={{ color: '#64748b', fontSize: '0.75rem' }}>({caseDetail.case_manager_name})</span>
              ) : null}
            </label>
            {canPickAdmin ? (
              <>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, fontSize: '0.875rem' }}>
                  <input
                    type="checkbox"
                    checked={attendees.admin}
                    onChange={() => toggleAttendee('admin')}
                  />
                  {ATTENDEE_ROLE_LABELS.admin}
                </label>
                {attendees.admin ? (
                  <select
                    style={{ ...inputStyle, marginLeft: 24 }}
                    value={adminUserId}
                    onChange={(e) => setAdminUserId(e.target.value)}
                  >
                    <option value="">Select admin…</option>
                    {adminUsers.map((u) => (
                      <option key={u.id} value={u.id}>{u.full_name || u.email}</option>
                    ))}
                  </select>
                ) : null}
              </>
            ) : null}
          </fieldset>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={labelStyle}>
              Date
              <input type="date" style={inputStyle} value={form.scheduled_date} required onChange={(e) => set('scheduled_date', e.target.value)} />
            </label>
            <label style={labelStyle}>
              Time
              <input type="time" style={inputStyle} value={form.scheduled_time} onChange={(e) => set('scheduled_time', e.target.value)} />
            </label>
          </div>

          <label style={labelStyle}>
            Duration (minutes)
            <input type="number" style={inputStyle} min={15} max={180} step={15} value={form.duration_minutes} onChange={(e) => set('duration_minutes', e.target.value)} />
          </label>

          <label style={labelStyle}>
            Meeting title / agenda (optional)
            <input type="text" style={inputStyle} placeholder="e.g. Progress review, IEP discussion" value={form.title} onChange={(e) => set('title', e.target.value)} />
          </label>

          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="submit" disabled={saving} style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '11px 0', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }}>
              {saving ? 'Booking…' : 'Book meeting'}
            </button>
            <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '11px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={onClose}>
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function NotesModal({ meeting, onClose, onUpdated }) {
  const [form, setForm] = useState({
    notes_concerns: meeting.notes_concerns || '',
    notes_follow_up: meeting.notes_follow_up || '',
    notes_action: meeting.notes_action || '',
    notes_other: meeting.notes_other || '',
    status: meeting.status || 'SCHEDULED',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function set(k, v) { setForm((f) => ({ ...f, [k]: v })) }

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/cm-meetings/${meeting.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: form.status,
          notes_concerns: form.notes_concerns || null,
          notes_follow_up: form.notes_follow_up || null,
          notes_action: form.notes_action || null,
          notes_other: form.notes_other || null,
        }),
      })
      onUpdated(result)
    } catch (err) {
      setError(err.message || 'Could not save')
    } finally {
      setSaving(false)
    }
  }

  const taStyle = { display: 'block', width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem', marginTop: 4, minHeight: 72, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }
  const labelStyle = { fontSize: '0.875rem', fontWeight: 500, color: '#475569', display: 'block', marginBottom: 12 }

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 60, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(15,23,42,0.45)', padding: 16 }}>
      <div style={{ background: '#fff', borderRadius: 20, padding: 24, width: '100%', maxWidth: 540, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.18)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: '#1e293b', margin: '0 0 4px' }}>Meeting notes</h2>
        <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '0 0 20px' }}>
          {meeting.child_name ? `${meeting.child_name} · ` : ''}{meeting.scheduled_date} {meeting.scheduled_time || ''}
        </p>
        {error ? <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', color: '#991b1b', marginBottom: 12 }}>{error}</p> : null}
        <form onSubmit={submit}>
          <label style={labelStyle}>
            Status
            <select style={{ display: 'block', width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem', marginTop: 4 }} value={form.status} onChange={(e) => set('status', e.target.value)}>
              <option value="SCHEDULED">Scheduled</option>
              <option value="COMPLETED">Completed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </label>
          <label style={labelStyle}>
            Concerns addressed
            <textarea style={taStyle} placeholder="What concerns were raised and addressed?" value={form.notes_concerns} onChange={(e) => set('notes_concerns', e.target.value)} />
          </label>
          <label style={labelStyle}>
            Follow-up steps
            <textarea style={taStyle} placeholder="Actions to be taken by parent / therapist / case manager…" value={form.notes_follow_up} onChange={(e) => set('notes_follow_up', e.target.value)} />
          </label>
          <label style={labelStyle}>
            Actions taken
            <textarea style={taStyle} placeholder="What was done during or after the meeting…" value={form.notes_action} onChange={(e) => set('notes_action', e.target.value)} />
          </label>
          <label style={labelStyle}>
            Additional inputs / log
            <textarea style={taStyle} placeholder="Any other notes for the record…" value={form.notes_other} onChange={(e) => set('notes_other', e.target.value)} />
          </label>
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="submit" disabled={saving} style={{ flex: 1, background: '#4f46e5', color: '#fff', border: 'none', borderRadius: 12, padding: '11px 0', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }}>
              {saving ? 'Saving…' : 'Save notes'}
            </button>
            <button type="button" style={{ background: '#f1f5f9', border: 'none', borderRadius: 12, padding: '11px 16px', fontWeight: 600, fontSize: '0.875rem', cursor: 'pointer' }} onClick={onClose}>
              Close
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function formatAttendeeList(meeting) {
  if (meeting.attendees?.length) {
    return meeting.attendees.map((a) => {
      const role = ATTENDEE_ROLE_LABELS[a.role] || a.role
      return `${role}: ${a.name}`
    }).join(' · ')
  }
  const parts = []
  if (meeting.parent_name) parts.push(`Client: ${meeting.parent_name}`)
  if (meeting.therapist_name) parts.push(`Therapist: ${meeting.therapist_name}`)
  if (meeting.case_manager_name) parts.push(`CM: ${meeting.case_manager_name}`)
  return parts.join(' · ')
}

function MeetingCard({ meeting, onAddNotes, onCancel }) {
  const typeLabel = MEETING_TYPES.find((t) => t.value === meeting.meeting_type)?.label
    || (meeting.meeting_type === 'SUPERVISION' ? 'Internal meeting' : meeting.meeting_type)
  const hasNotes = meeting.notes_concerns || meeting.notes_follow_up || meeting.notes_action || meeting.notes_other
  const attendeeLine = formatAttendeeList(meeting)

  return (
    <article style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '16px 18px', marginBottom: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '0.9rem', color: '#1e293b' }}>
            {meeting.title || typeLabel}
          </p>
          <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#64748b' }}>
            {meeting.scheduled_date}
            {meeting.scheduled_time ? ` · ${meeting.scheduled_time}` : ''}
            {meeting.duration_minutes ? ` · ${meeting.duration_minutes} min` : ''}
          </p>
        </div>
        <StatusBadge status={meeting.status} />
      </div>

      <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 8 }}>
        {meeting.case_id ? (
          <span>
            <Link to={`/admin/cases/${meeting.case_id}?tab=overview`}>{meeting.case_code || `Case #${meeting.case_id}`}</Link>
            {meeting.child_name ? ` · ${meeting.child_name}` : ''} &nbsp;·&nbsp;{' '}
          </span>
        ) : meeting.child_name ? (
          <span>Child: <strong>{meeting.child_name}</strong> &nbsp;·&nbsp; </span>
        ) : null}
        {attendeeLine ? <div style={{ marginTop: 4, color: '#334155' }}>Attendees: {attendeeLine}</div> : null}
        {!meeting.child_name && !attendeeLine ? <span>{typeLabel}</span> : null}
      </div>
      {meeting.meeting_url ? (
        <p style={{ fontSize: '0.8rem', margin: '0 0 8px' }}>
          <a href={meeting.meeting_url} target="_blank" rel="noreferrer">Join meeting</a>
        </p>
      ) : null}
      {meeting.guest_emails?.length > 0 ? (
        <p style={{ fontSize: '0.75rem', color: '#64748b', margin: '0 0 8px' }}>
          Guests: {meeting.guest_emails.join(', ')}
        </p>
      ) : null}

      {hasNotes ? (
        <div style={{ background: '#f8fafc', borderRadius: 10, padding: '10px 12px', marginBottom: 10, fontSize: '0.8rem', color: '#334155' }}>
          {meeting.notes_concerns ? <p style={{ margin: '0 0 4px' }}><strong>Concerns:</strong> {meeting.notes_concerns}</p> : null}
          {meeting.notes_follow_up ? <p style={{ margin: '0 0 4px' }}><strong>Follow-up:</strong> {meeting.notes_follow_up}</p> : null}
          {meeting.notes_action ? <p style={{ margin: '0 0 4px' }}><strong>Actions:</strong> {meeting.notes_action}</p> : null}
          {meeting.notes_other ? <p style={{ margin: 0 }}><strong>Other:</strong> {meeting.notes_other}</p> : null}
        </div>
      ) : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {meeting.status !== 'CANCELLED' ? (
          <button
            type="button"
            style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600, color: '#3730a3', cursor: 'pointer' }}
            onClick={() => onAddNotes(meeting)}
          >
            {hasNotes ? 'Edit notes' : 'Add notes / complete'}
          </button>
        ) : null}
        {meeting.status === 'SCHEDULED' ? (
          <button
            type="button"
            style={{ background: '#fff', border: '1px solid #fca5a5', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600, color: '#dc2626', cursor: 'pointer' }}
            onClick={() => onCancel(meeting)}
          >
            Cancel meeting
          </button>
        ) : null}
      </div>
    </article>
  )
}

export function CaseManagerMeetingsPage({ portal = 'admin' } = {}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const isTherapistPortal = portal === 'therapist'
  const isAdmin =
    !isTherapistPortal
    && (user?.roles?.includes('SUPER_ADMIN')
      || user?.roles?.includes('ADMIN')
      || user?.roles?.includes('MODULE_ADMIN'))
  const canBookMeetings =
    user?.roles?.includes('CASE_MANAGER')
    || user?.roles?.includes('ADMIN')
    || user?.roles?.includes('SUPER_ADMIN')
    || user?.roles?.includes('MODULE_ADMIN')
    || user?.roles?.includes('THERAPIST')
  const [meetings, setMeetings] = useState([])
  const [cases, setCases] = useState([])
  const [cmUsers, setCmUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showBook, setShowBook] = useState(false)
  const [notesTarget, setNotesTarget] = useState(null)
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [typeFilter, setTypeFilter] = useState(searchParams.get('meeting_type') || '')
  const [caseFilter, setCaseFilter] = useState(searchParams.get('case_id') || '')
  const [cmFilter, setCmFilter] = useState(searchParams.get('cm_id') || '')
  const [monthFilter, setMonthFilter] = useState(searchParams.get('month') || '')
  const [yearFilter, setYearFilter] = useState(searchParams.get('year') || String(new Date().getFullYear()))
  const [searchInput, setSearchInput] = useState(() => searchParams.get('search') || '')
  const [search, setSearch] = useState(searchInput)
  const [error, setError] = useState('')
  const yearFilterOptions = useMemo(() => {
    const currentYear = new Date().getFullYear()
    return Array.from({ length: 5 }, (_, idx) => {
      const year = String(currentYear - 2 + idx)
      return { value: year, label: year }
    })
  }, [])

  const queueTab = searchParams.get('queue') === 'admin'

  useEffect(() => {
    const id = window.setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [searchInput])

  const buildQuery = useCallback(() => {
    const p = new URLSearchParams()
    if (statusFilter) p.set('status', statusFilter)
    if (typeFilter && !queueTab) p.set('meeting_type', typeFilter)
    if (caseFilter) p.set('case_id', caseFilter)
    if (cmFilter && isAdmin) p.set('case_manager_user_id', cmFilter)
    if (monthFilter) p.set('month', monthFilter)
    if (yearFilter) p.set('year', yearFilter)
    const term = String(search ?? '').trim()
    if (term) p.set('search', term)
    const qs = p.toString()
    return qs ? `?${qs}` : ''
  }, [statusFilter, typeFilter, caseFilter, cmFilter, monthFilter, yearFilter, search, queueTab, isAdmin])

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    apiFetch(`/api/v1/cm-meetings${buildQuery()}`)
      .then((rows) => setMeetings(Array.isArray(rows) ? rows : []))
      .catch((e) => setError(e.message || 'Could not load meetings'))
      .finally(() => setLoading(false))
  }, [buildQuery])

  const kpis = useMemo(() => {
    const scheduled = meetings.filter((m) => m.status === 'SCHEDULED').length
    const withAdmin = meetings.filter(
      (m) => m.status === 'SCHEDULED' && (m.admin_user_ids?.length > 0 || m.attendees?.some((a) => a.role === 'admin')),
    ).length
    return { scheduled, withAdmin, total: meetings.length }
  }, [meetings])

  const loadBookableCases = useCallback(() => {
    const params = new URLSearchParams()
    if (isAdmin && cmFilter) params.set('case_manager_user_id', cmFilter)
    const qs = params.toString() ? `?${params}` : ''
    return apiFetch(`/api/v1/cm-meetings/bookable-cases${qs}`)
      .then((data) => {
        const arr = Array.isArray(data) ? data : unwrapList(data)
        setCases(
          arr.map((c) => ({
            id: c.id,
            childName: c.child_name || c.childName || `Case ${c.id}`,
            caseCode: c.case_code || c.caseCode,
            caseId: c.case_code || c.caseId,
          }))
        )
      })
      .catch(() => setCases([]))
  }, [isAdmin, cmFilter])

  useEffect(() => {
    loadBookableCases()
  }, [loadBookableCases])

  useEffect(() => {
    if (!isAdmin) return
    apiFetch('/api/v1/admin/users')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : rows?.items || []
        setCmUsers(list.filter((u) => u.roles?.includes('CASE_MANAGER')))
      })
      .catch(() => setCmUsers([]))
  }, [isAdmin])

  useEffect(() => {
    load()
  }, [load])

  const displayedMeetings = useMemo(() => {
    if (!queueTab) return meetings
    return meetings.filter(
      (m) => m.admin_user_ids?.length > 0 || m.attendees?.some((a) => a.role === 'admin'),
    )
  }, [meetings, queueTab])

  function handleCreated(m) {
    setShowBook(false)
    setMeetings((prev) => [m, ...prev])
  }

  function handleUpdated(m) {
    setNotesTarget(null)
    setMeetings((prev) => prev.map((x) => (x.id === m.id ? m : x)))
  }

  async function handleCancel(meeting) {
    if (!window.confirm('Cancel this meeting?')) return
    try {
      await apiFetch(`/api/v1/cm-meetings/${meeting.id}`, { method: 'DELETE' })
      setMeetings((prev) => prev.map((x) => x.id === meeting.id ? { ...x, status: 'CANCELLED' } : x))
    } catch (e) {
      setError(e.message || 'Could not cancel')
    }
  }

  return (
    <div className="admin-page" style={{ maxWidth: 900 }}>
      <AdminPageHeader
        title={isTherapistPortal ? 'Book case manager meeting' : 'Case manager meetings'}
        subtitle={
          isTherapistPortal
            ? 'Request a meeting with the case manager for one of your assigned cases.'
            : 'Schedule case meetings, invite attendees, and log notes.'
        }
        actions={
          canBookMeetings ? (
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => {
                loadBookableCases()
                setShowBook(true)
              }}
            >
              Book meeting
            </button>
          ) : null
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      <div className="admin-reports__kpis" style={{ marginBottom: 16 }}>
        <button type="button" className="admin-reports__kpi" style={{ cursor: 'pointer', textAlign: 'left' }} onClick={() => { setStatusFilter('SCHEDULED'); setSearchParams({}) }}>
          <div className="admin-reports__kpi-value">{kpis.scheduled}</div>
          <div className="admin-reports__kpi-label">Scheduled (filtered)</div>
        </button>
        <button
          type="button"
          className="admin-reports__kpi"
          style={{ cursor: 'pointer', textAlign: 'left' }}
          onClick={() => setSearchParams({ queue: 'admin', status: 'SCHEDULED' })}
        >
          <div className="admin-reports__kpi-value">{kpis.withAdmin}</div>
          <div className="admin-reports__kpi-label">With admin invited</div>
        </button>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{kpis.total}</div>
          <div className="admin-reports__kpi-label">In current list</div>
        </div>
      </div>

      {queueTab ? (
        <p className="admin-alert" style={{ marginBottom: 12 }}>
          Showing meetings with an admin attendee.{' '}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setSearchParams({})}>
            Clear
          </button>
        </p>
      ) : null}

      <AdminCollapsibleFilters
        quickSearch={
          <AdminSearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="Child, case code, or meeting title…"
            className="admin-meetings-filters__search"
          />
        }
        activeChips={[
          statusFilter && statusFilter !== 'ALL' ? statusFilter : null,
          typeFilter && typeFilter !== 'ALL' ? typeFilter : null,
          caseFilter ? `Case ${caseFilter}` : null,
        ].filter(Boolean)}
        activeCount={[statusFilter, typeFilter, caseFilter, cmFilter, monthFilter].filter((v) => v && v !== 'ALL' && v !== '').length}
      >
      <div className="admin-meetings-filters">
        <AdminSearchInput
          value={searchInput}
          onChange={setSearchInput}
          placeholder="Child, case code, or meeting title…"
          className="admin-meetings-filters__search"
        />
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          options={STATUS_FILTER_OPTIONS}
        />
        <FilterSelect
          label="Meeting type"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          options={TYPE_FILTER_OPTIONS}
          disabled={queueTab}
        />
        <FilterSelect
          label="Case"
          value={caseFilter}
          onChange={(e) => setCaseFilter(e.target.value)}
          options={[
            { value: '', label: 'All cases' },
            ...cases.map((c) => ({
              value: String(c.id),
              label: `${c.childName} (${c.caseCode || c.id})`,
            })),
          ]}
        />
        {isAdmin ? (
          <FilterSelect
            label="Case manager"
            value={cmFilter}
            onChange={(e) => setCmFilter(e.target.value)}
            options={[
              { value: '', label: 'All case managers' },
              ...cmUsers.map((u) => ({ value: String(u.id), label: u.full_name })),
            ]}
          />
        ) : null}
        <FilterSelect
          label="Month"
          value={monthFilter}
          onChange={(e) => setMonthFilter(e.target.value)}
          options={MONTH_FILTER_OPTIONS}
        />
        <FilterSelect
          label="Year"
          value={yearFilter}
          onChange={(e) => setYearFilter(e.target.value)}
          options={yearFilterOptions}
          disabled={!monthFilter}
        />
      </div>
      </AdminCollapsibleFilters>

      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading meetings…</p>
      ) : displayedMeetings.length === 0 ? (
        <div style={{ background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: 14, padding: '32px 24px', textAlign: 'center' }}>
          <p style={{ color: '#94a3b8', margin: 0 }}>No meetings yet. Click &ldquo;+ Book meeting&rdquo; to schedule one.</p>
        </div>
      ) : (
        displayedMeetings.map((m) => (
          <MeetingCard
            key={m.id}
            meeting={m}
            onAddNotes={setNotesTarget}
            onCancel={handleCancel}
          />
        ))
      )}

      {showBook ? (
        <BookMeetingModal
          cases={cases}
          onClose={() => setShowBook(false)}
          onCreated={handleCreated}
          onOpen={loadBookableCases}
          canPickAdmin={!isTherapistPortal}
          isTherapistBooking={isTherapistPortal}
        />
      ) : null}
      {notesTarget ? <NotesModal meeting={notesTarget} onClose={() => setNotesTarget(null)} onUpdated={handleUpdated} /> : null}
    </div>
  )
}
