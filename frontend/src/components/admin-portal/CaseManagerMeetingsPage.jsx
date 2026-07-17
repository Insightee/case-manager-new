import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { dateStr } from '../scheduling/slotCalendarUtils.js'
import { BookMeetingModal } from '../meetings/BookMeetingModal.jsx'
import { MeetingDetailSheet } from '../meetings/MeetingDetailSheet.jsx'
import { RescheduleMeetingModal } from '../meetings/RescheduleMeetingModal.jsx'
import {
  MONTH_FILTER_OPTIONS,
  SEARCH_DEBOUNCE_MS,
  STATUS_FILTER_OPTIONS,
  STATUS_LABELS,
  TYPE_FILTER_OPTIONS,
} from '../meetings/meetingConstants.js'
import { formatAttendeeList, meetingTypeLabel, padHour, parseMeetingIdFromGridEvent } from '../meetings/meetingUtils.js'
import { mapCmMeetingToCalendarEvent } from '../../lib/googleCalendar.js'
import { AddToGoogleCalendarButton } from '../shared/AddToGoogleCalendarButton.jsx'
import { AdminCollapsibleFilters, AdminPageHeader, AdminSearchInput, FilterSelect } from './ui/index.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import './admin-reports.css'
import './admin-scheduling-hub.css'

function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || { label: status, bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '3px 8px', borderRadius: 6, background: s.bg, color: s.color }}>
      {s.label}
    </span>
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

  function set(k, v) {
    setForm((f) => ({ ...f, [k]: v }))
  }

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/meetings/${meeting.id}`, {
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
          {meeting.child_name ? `${meeting.child_name} · ` : ''}{formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time)}
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

function MeetingCard({ meeting, onAddNotes, onCancel, onReschedule, caseLinkPrefix, readOnly = false }) {
  const typeLabel = meetingTypeLabel(meeting)
  const hasNotes = meeting.notes_concerns || meeting.notes_follow_up || meeting.notes_action || meeting.notes_other
  const attendeeLine = formatAttendeeList(meeting)
  const calendarEvent = meeting.status === 'SCHEDULED' ? mapCmMeetingToCalendarEvent(meeting) : null

  return (
    <article style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '16px 18px', marginBottom: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '0.9rem', color: '#1e293b' }}>
            {meeting.title || typeLabel}
          </p>
          <p style={{ margin: '2px 0 0', fontSize: '0.8rem', color: '#64748b' }}>
            {formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time)}
            {meeting.duration_minutes ? ` · ${meeting.duration_minutes} min` : ''}
          </p>
        </div>
        <StatusBadge status={meeting.status} />
      </div>

      <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: 8 }}>
        {meeting.case_id && caseLinkPrefix ? (
          <span>
            <Link to={`${caseLinkPrefix}/${meeting.case_id}?tab=overview`}>{meeting.case_code || `Case #${meeting.case_id}`}</Link>
            {meeting.child_name ? ` · ${meeting.child_name}` : ''} &nbsp;·&nbsp;{' '}
          </span>
        ) : meeting.child_name ? (
          <span>Child: <strong>{meeting.child_name}</strong> &nbsp;·&nbsp; </span>
        ) : null}
        {attendeeLine ? <div style={{ marginTop: 4, color: '#334155' }}>Attendees: {attendeeLine}</div> : null}
      </div>
      {meeting.meeting_url ? (
        <p style={{ fontSize: '0.8rem', margin: '0 0 8px' }}>
          <a href={meeting.meeting_url} target="_blank" rel="noreferrer">Join meeting</a>
        </p>
      ) : null}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        {calendarEvent ? <AddToGoogleCalendarButton event={calendarEvent} variant="inline" /> : null}
        {!readOnly && meeting.status !== 'CANCELLED' ? (
          <button type="button" style={{ background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600, color: '#3730a3', cursor: 'pointer' }} onClick={() => onAddNotes(meeting)}>
            {hasNotes ? 'Edit notes' : 'Add notes / complete'}
          </button>
        ) : null}
        {!readOnly && meeting.status === 'SCHEDULED' ? (
          <>
            <button type="button" style={{ background: '#fff', border: '1px solid #c7d2fe', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600, color: '#3730a3', cursor: 'pointer' }} onClick={() => onReschedule(meeting)}>
              Reschedule
            </button>
            <button type="button" style={{ background: '#fff', border: '1px solid #fca5a5', borderRadius: 8, padding: '6px 14px', fontSize: '0.8rem', fontWeight: 600, color: '#dc2626', cursor: 'pointer' }} onClick={() => onCancel(meeting)}>
              Cancel meeting
            </button>
          </>
        ) : null}
      </div>
    </article>
  )
}

export function CaseManagerMeetingsPage({ portal = 'admin' } = {}) {
  const [searchParams, setSearchParams] = useSearchParams()
  const { user } = useAuth()
  const isTherapistPortal = portal === 'therapist'
  const isParentPortal = portal === 'parent'
  const isAdmin =
    !isTherapistPortal
    && !isParentPortal
    && (user?.roles?.includes('SUPER_ADMIN')
      || user?.roles?.includes('ADMIN')
      || user?.roles?.includes('MODULE_ADMIN'))
  const canBookMeetings =
    !isParentPortal
    && (user?.roles?.includes('CASE_MANAGER')
      || user?.roles?.includes('ADMIN')
      || user?.roles?.includes('SUPER_ADMIN')
      || user?.roles?.includes('MODULE_ADMIN')
      || user?.roles?.includes('THERAPIST'))
  const caseLinkPrefix = isParentPortal ? null : isTherapistPortal ? '/therapist/cases' : '/admin/cases'

  const [pageView, setPageView] = useState('calendar')
  const [meetings, setMeetings] = useState([])
  const [cases, setCases] = useState([])
  const [cmUsers, setCmUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [showBook, setShowBook] = useState(false)
  const [bookPrefill, setBookPrefill] = useState({ date: null, time: null })
  const [notesTarget, setNotesTarget] = useState(null)
  const [detailMeeting, setDetailMeeting] = useState(null)
  const [rescheduleTarget, setRescheduleTarget] = useState(null)
  const [calendarRefresh, setCalendarRefresh] = useState(0)
  const [selectedCalendarEventId, setSelectedCalendarEventId] = useState(null)
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
    apiFetch(`/api/v1/meetings${buildQuery()}`)
      .then((rows) => setMeetings(Array.isArray(rows) ? rows : []))
      .catch((e) => setError(e.message || 'Could not load meetings'))
      .finally(() => setLoading(false))
  }, [buildQuery])

  const meetingsById = useMemo(() => {
    const map = new Map()
    for (const m of meetings) map.set(m.id, m)
    return map
  }, [meetings])

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
    return apiFetch(`/api/v1/meetings/bookable-cases${qs}`)
      .then((data) => {
        const arr = Array.isArray(data) ? data : unwrapList(data)
        setCases(
          arr.map((c) => ({
            id: c.id,
            childName: c.child_name || c.childName || `Case ${c.id}`,
            caseCode: c.case_code || c.caseCode,
            caseId: c.case_code || c.caseId,
          })),
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

  function refreshAll() {
    load()
    setCalendarRefresh((k) => k + 1)
  }

  function openBookModal(prefill = {}) {
    setBookPrefill({
      date: prefill.date || null,
      time: prefill.time || null,
    })
    loadBookableCases()
    setShowBook(true)
  }

  function handleCreated(m) {
    setShowBook(false)
    setBookPrefill({ date: null, time: null })
    setMeetings((prev) => [m, ...prev])
    refreshAll()
  }

  function handleUpdated(m) {
    setNotesTarget(null)
    setMeetings((prev) => prev.map((x) => (x.id === m.id ? m : x)))
    if (detailMeeting?.id === m.id) setDetailMeeting(m)
    refreshAll()
  }

  function handleRescheduled(m) {
    const oldId = rescheduleTarget?.id
    setRescheduleTarget(null)
    setDetailMeeting(null)
    setMeetings((prev) => {
      const withoutOld = oldId ? prev.filter((x) => x.id !== oldId) : prev
      return [m, ...withoutOld]
    })
    refreshAll()
  }

  async function handleCalendarSlotClick(event) {
    if (event.event_type !== 'cm_meeting') return
    setSelectedCalendarEventId(event.id)
    const meetingId = parseMeetingIdFromGridEvent(event)
    if (!meetingId) return
    const cached = meetingsById.get(meetingId)
    if (cached) {
      setDetailMeeting(cached)
      return
    }
    try {
      const rows = await apiFetch('/api/v1/meetings?status=SCHEDULED')
      const found = (Array.isArray(rows) ? rows : []).find((item) => item.id === meetingId)
      if (found) setDetailMeeting(found)
    } catch {
      setError('Could not open that meeting')
    }
  }

  function handleCalendarCellClick(day, hour) {
    if (!canBookMeetings) return
    openBookModal({ date: dateStr(day), time: padHour(hour) })
  }

  async function handleCancel(meeting) {
    if (!window.confirm('Cancel this meeting?')) return
    try {
      await apiFetch(`/api/v1/meetings/${meeting.id}`, { method: 'DELETE' })
      setMeetings((prev) => prev.map((x) => (x.id === meeting.id ? { ...x, status: 'CANCELLED' } : x)))
      if (detailMeeting?.id === meeting.id) setDetailMeeting(null)
      refreshAll()
    } catch (e) {
      setError(e.message || 'Could not cancel')
    }
  }

  const calendarMode = isParentPortal ? 'parent' : 'therapist'

  return (
    <div className="admin-page" style={{ maxWidth: 1100 }}>
      <AdminPageHeader
        title={
          isParentPortal
            ? 'Your meetings'
            : isTherapistPortal
              ? 'Book case manager meeting'
              : 'Case manager meetings'
        }
        subtitle={
          isParentPortal
            ? 'View upcoming meetings on your calendar and export to Google Calendar.'
            : isTherapistPortal
              ? 'Request a meeting with the case manager for one of your assigned cases.'
              : 'Schedule meetings, view your calendar, and manage follow-ups.'
        }
        actions={
          canBookMeetings ? (
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => openBookModal()}
            >
              Book meeting
            </button>
          ) : null
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}

      <div className="mb-4 inline-flex rounded-full border border-slate-200 bg-slate-50 p-1" role="tablist" aria-label="Meetings view">
        {[
          { id: 'calendar', label: 'Calendar' },
          { id: 'list', label: 'List' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={pageView === tab.id}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold ${pageView === tab.id ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-600'}`}
            onClick={() => setPageView(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {pageView === 'calendar' ? (
        <article className="card admin-scheduling-hub__calendar-wrap" style={{ marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>My meeting calendar</h3>
          <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 12 }}>
            {canBookMeetings
              ? 'Tap a meeting for details, or tap + on an open slot to book.'
              : 'Tap a meeting to view details or add it to Google Calendar.'}
          </p>
          <TherapistCalendar
            apiPrefix="/api/v1/meetings"
            mode={calendarMode}
            refreshKey={calendarRefresh}
            selectedSlotId={selectedCalendarEventId}
            onSlotClick={handleCalendarSlotClick}
            onCellClick={canBookMeetings ? handleCalendarCellClick : undefined}
          />
        </article>
      ) : null}

      {pageView === 'list' ? (
        <>
          <div className="admin-reports__kpis" style={{ marginBottom: 16 }}>
            <button type="button" className="admin-reports__kpi" style={{ cursor: 'pointer', textAlign: 'left' }} onClick={() => { setStatusFilter('SCHEDULED'); setSearchParams({}) }}>
              <div className="admin-reports__kpi-value">{kpis.scheduled}</div>
              <div className="admin-reports__kpi-label">Scheduled (filtered)</div>
            </button>
            {!isParentPortal ? (
              <button type="button" className="admin-reports__kpi" style={{ cursor: 'pointer', textAlign: 'left' }} onClick={() => setSearchParams({ queue: 'admin', status: 'SCHEDULED' })}>
                <div className="admin-reports__kpi-value">{kpis.withAdmin}</div>
                <div className="admin-reports__kpi-label">With admin invited</div>
              </button>
            ) : null}
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
              <AdminSearchInput value={searchInput} onChange={setSearchInput} placeholder="Child, case code, or meeting title…" className="admin-meetings-filters__search" />
            }
            activeChips={[
              statusFilter && statusFilter !== 'ALL' ? statusFilter : null,
              typeFilter && typeFilter !== 'ALL' ? typeFilter : null,
              caseFilter ? `Case ${caseFilter}` : null,
            ].filter(Boolean)}
            activeCount={[statusFilter, typeFilter, caseFilter, cmFilter, monthFilter].filter((v) => v && v !== 'ALL' && v !== '').length}
          >
            <div className="admin-meetings-filters">
              <AdminSearchInput value={searchInput} onChange={setSearchInput} placeholder="Child, case code, or meeting title…" className="admin-meetings-filters__search" />
              <FilterSelect label="Status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} options={STATUS_FILTER_OPTIONS} />
              <FilterSelect label="Meeting type" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} options={TYPE_FILTER_OPTIONS} disabled={queueTab} />
              {!isParentPortal ? (
                <FilterSelect
                  label="Case"
                  value={caseFilter}
                  onChange={(e) => setCaseFilter(e.target.value)}
                  options={[
                    { value: '', label: 'All cases' },
                    ...cases.map((c) => ({ value: String(c.id), label: `${c.childName} (${c.caseCode || c.id})` })),
                  ]}
                />
              ) : null}
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
              <FilterSelect label="Month" value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)} options={MONTH_FILTER_OPTIONS} />
              <FilterSelect label="Year" value={yearFilter} onChange={(e) => setYearFilter(e.target.value)} options={yearFilterOptions} disabled={!monthFilter} />
            </div>
          </AdminCollapsibleFilters>

          {loading ? (
            <p style={{ color: '#94a3b8' }}>Loading meetings…</p>
          ) : displayedMeetings.length === 0 ? (
            <div style={{ background: '#f8fafc', border: '1px dashed #cbd5e1', borderRadius: 14, padding: '32px 24px', textAlign: 'center' }}>
              <p style={{ color: '#94a3b8', margin: 0 }}>
                {canBookMeetings ? 'No meetings yet. Book one from the calendar or use the button above.' : 'No meetings scheduled yet.'}
              </p>
            </div>
          ) : (
            displayedMeetings.map((m) => (
              <MeetingCard
                key={m.id}
                meeting={m}
                caseLinkPrefix={caseLinkPrefix}
                readOnly={isParentPortal}
                onAddNotes={setNotesTarget}
                onCancel={handleCancel}
                onReschedule={setRescheduleTarget}
              />
            ))
          )}
        </>
      ) : null}

      {showBook ? (
        <BookMeetingModal
          cases={cases}
          onClose={() => {
            setShowBook(false)
            setBookPrefill({ date: null, time: null })
          }}
          onCreated={handleCreated}
          onOpen={loadBookableCases}
          isTherapistBooking={isTherapistPortal}
          initialDate={bookPrefill.date}
          initialTime={bookPrefill.time}
        />
      ) : null}

      <MeetingDetailSheet
        open={!!detailMeeting}
        meeting={detailMeeting}
        readOnly={isParentPortal}
        caseLinkPrefix={caseLinkPrefix}
        onClose={() => {
          setDetailMeeting(null)
          setSelectedCalendarEventId(null)
        }}
        onReschedule={(m) => {
          setDetailMeeting(null)
          setRescheduleTarget(m)
        }}
        onCancel={handleCancel}
        onAddNotes={isParentPortal ? undefined : setNotesTarget}
      />

      {rescheduleTarget ? (
        <RescheduleMeetingModal
          meeting={rescheduleTarget}
          onClose={() => setRescheduleTarget(null)}
          onRescheduled={handleRescheduled}
        />
      ) : null}

      {notesTarget ? <NotesModal meeting={notesTarget} onClose={() => setNotesTarget(null)} onUpdated={handleUpdated} /> : null}
    </div>
  )
}
