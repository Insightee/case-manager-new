import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminPageHeader, AdminSearchInput } from './ui/index.js'
import './admin-reports.css'

const MEETING_TYPES = [
  { value: 'CLIENT_ONLY', label: 'Client only' },
  { value: 'CLIENT_AND_THERAPIST', label: 'Client + Therapist' },
  { value: 'SUPERVISION', label: 'Supervision / admin' },
]

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

function BookMeetingModal({ cases, onClose, onCreated }) {
  const today = new Date().toISOString().slice(0, 10)
  const [form, setForm] = useState({
    case_id: '',
    therapist_user_id: '',
    scheduled_date: today,
    scheduled_time: '10:00',
    duration_minutes: 30,
    meeting_type: 'CLIENT_ONLY',
    title: '',
  })
  const [therapists, setTherapists] = useState([])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!form.case_id) { setTherapists([]); return }
    apiFetch(`/api/v1/booking/therapists?case_id=${form.case_id}`)
      .then(setTherapists)
      .catch(() => setTherapists([]))
  }, [form.case_id])

  function set(k, v) {
    setForm((f) => {
      const next = { ...f, [k]: v }
      if (k === 'therapist_user_id' && v) next.meeting_type = 'CLIENT_AND_THERAPIST'
      if (k === 'therapist_user_id' && !v) next.meeting_type = 'CLIENT_ONLY'
      return next
    })
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.scheduled_date) { setError('Date is required'); return }
    setSaving(true)
    setError('')
    try {
      const body = {
        scheduled_date: form.scheduled_date,
        scheduled_time: form.scheduled_time || null,
        duration_minutes: Number(form.duration_minutes) || 30,
        meeting_type: form.meeting_type,
        title: form.title || null,
      }
      if (form.case_id) body.case_id = Number(form.case_id)
      if (form.therapist_user_id) body.therapist_user_id = Number(form.therapist_user_id)
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
            Case (optional)
            <select style={inputStyle} value={form.case_id} onChange={(e) => set('case_id', e.target.value)}>
              <option value="">— No specific case —</option>
              {cases.map((c) => (
                <option key={c.id} value={c.id}>{c.childName} ({c.caseCode || c.caseId || c.id})</option>
              ))}
            </select>
          </label>

          {form.case_id && therapists.length > 0 ? (
            <label style={labelStyle}>
              Include therapist (optional)
              <select style={inputStyle} value={form.therapist_user_id} onChange={(e) => set('therapist_user_id', e.target.value)}>
                <option value="">— Client only —</option>
                {therapists.map((t) => (
                  <option key={t.therapist_user_id} value={t.therapist_user_id}>{t.full_name}</option>
                ))}
              </select>
            </label>
          ) : null}

          <label style={labelStyle}>
            Meeting type
            <select style={inputStyle} value={form.meeting_type} onChange={(e) => set('meeting_type', e.target.value)}>
              {MEETING_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </label>

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

function MeetingCard({ meeting, onAddNotes, onCancel }) {
  const typeLabel = MEETING_TYPES.find((t) => t.value === meeting.meeting_type)?.label || meeting.meeting_type
  const hasNotes = meeting.notes_concerns || meeting.notes_follow_up || meeting.notes_action || meeting.notes_other

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
        {meeting.parent_name ? <span>Parent: {meeting.parent_name} &nbsp;·&nbsp; </span> : null}
        {meeting.therapist_name ? <span>Therapist: {meeting.therapist_name}</span> : null}
        {!meeting.child_name && !meeting.parent_name ? <span>{typeLabel}</span> : null}
      </div>

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

export function CaseManagerMeetingsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const isAdmin = user?.roles?.includes('SUPER_ADMIN') || user?.roles?.includes('ADMIN')
  const canBookMeetings =
    user?.roles?.includes('CASE_MANAGER')
    || user?.roles?.includes('ADMIN')
    || user?.roles?.includes('SUPER_ADMIN')
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
  const [search, setSearch] = useState(searchParams.get('search') || '')
  const [error, setError] = useState('')

  const queueTab = searchParams.get('queue') === 'supervision'

  function buildQuery() {
    const p = new URLSearchParams()
    if (statusFilter) p.set('status', statusFilter)
    if (typeFilter || queueTab) p.set('meeting_type', queueTab ? 'SUPERVISION' : typeFilter)
    if (caseFilter) p.set('case_id', caseFilter)
    if (cmFilter && isAdmin) p.set('case_manager_user_id', cmFilter)
    if (monthFilter) p.set('month', monthFilter)
    if (yearFilter) p.set('year', yearFilter)
    if (search.trim()) p.set('search', search.trim())
    const qs = p.toString()
    return qs ? `?${qs}` : ''
  }

  function load() {
    setLoading(true)
    apiFetch(`/api/v1/cm-meetings${buildQuery()}`)
      .then(setMeetings)
      .catch((e) => setError(e.message || 'Could not load meetings'))
      .finally(() => setLoading(false))
  }

  const kpis = useMemo(() => {
    const scheduled = meetings.filter((m) => m.status === 'SCHEDULED').length
    const supervision = meetings.filter((m) => m.meeting_type === 'SUPERVISION' && m.status === 'SCHEDULED').length
    return { scheduled, supervision, total: meetings.length }
  }, [meetings])

  useEffect(() => {
    apiFetch('/api/v1/admin/cases').catch(() => apiFetch('/api/v1/cases')).then((data) => {
      const arr = Array.isArray(data) ? data : data?.cases || []
      setCases(arr.map((c) => ({
        id: c.id,
        childName: c.childName || c.child_name || c.child?.full_name || `Case ${c.id}`,
        caseCode: c.caseCode || c.case_code,
        caseId: c.case_code || c.caseId,
      })))
    }).catch(() => setCases([]))
  }, [])

  useEffect(() => {
    if (!isAdmin) return
    apiFetch('/api/v1/admin/users')
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : rows?.items || []
        setCmUsers(list.filter((u) => u.roles?.includes('CASE_MANAGER')))
      })
      .catch(() => setCmUsers([]))
  }, [isAdmin])

  useEffect(() => { load() }, [statusFilter, typeFilter, caseFilter, cmFilter, monthFilter, yearFilter, search, queueTab])

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
        title="Case manager meetings"
        subtitle="Schedule client meetings, supervision sessions, and log notes."
        actions={
          canBookMeetings ? (
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowBook(true)}>
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
          onClick={() => setSearchParams({ queue: 'supervision', status: 'SCHEDULED' })}
        >
          <div className="admin-reports__kpi-value">{kpis.supervision}</div>
          <div className="admin-reports__kpi-label">Supervision meetings (CM)</div>
        </button>
        <div className="admin-reports__kpi">
          <div className="admin-reports__kpi-value">{kpis.total}</div>
          <div className="admin-reports__kpi-label">In current list</div>
        </div>
      </div>

      {queueTab ? (
        <p className="admin-alert" style={{ marginBottom: 12 }}>
          Showing scheduled supervision meetings.{' '}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setSearchParams({})}>
            Clear
          </button>
        </p>
      ) : null}

      <div className="admin-reports__toolbar">
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Child, case code, title…" />
        <select className="admin-select" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="SCHEDULED">Scheduled</option>
          <option value="COMPLETED">Completed</option>
          <option value="CANCELLED">Cancelled</option>
        </select>
        <select className="admin-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} disabled={queueTab}>
          <option value="">All types</option>
          {MEETING_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select className="admin-select" value={caseFilter} onChange={(e) => setCaseFilter(e.target.value)}>
          <option value="">All cases</option>
          {cases.map((c) => (
            <option key={c.id} value={c.id}>{c.childName} ({c.caseCode || c.id})</option>
          ))}
        </select>
        {isAdmin ? (
          <select className="admin-select" value={cmFilter} onChange={(e) => setCmFilter(e.target.value)}>
            <option value="">All case managers</option>
            {cmUsers.map((u) => (
              <option key={u.id} value={u.id}>{u.full_name}</option>
            ))}
          </select>
        ) : null}
        <input type="month" className="admin-input" style={{ maxWidth: 160 }} value={monthFilter ? `${yearFilter}-${String(monthFilter).padStart(2, '0')}` : ''} onChange={(e) => {
          if (!e.target.value) { setMonthFilter(''); return }
          const [y, m] = e.target.value.split('-')
          setYearFilter(y)
          setMonthFilter(String(Number(m)))
        }} />
      </div>

      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading meetings…</p>
      ) : meetings.length === 0 ? (
        <div style={{ background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: 14, padding: '32px 24px', textAlign: 'center' }}>
          <p style={{ color: '#94a3b8', margin: 0 }}>No meetings yet. Click &ldquo;+ Book meeting&rdquo; to schedule one.</p>
        </div>
      ) : (
        meetings.map((m) => (
          <MeetingCard
            key={m.id}
            meeting={m}
            onAddNotes={setNotesTarget}
            onCancel={handleCancel}
          />
        ))
      )}

      {showBook ? <BookMeetingModal cases={cases} onClose={() => setShowBook(false)} onCreated={handleCreated} /> : null}
      {notesTarget ? <NotesModal meeting={notesTarget} onClose={() => setNotesTarget(null)} onUpdated={handleUpdated} /> : null}
    </div>
  )
}
