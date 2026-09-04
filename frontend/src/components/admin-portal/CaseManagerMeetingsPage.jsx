import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { TherapistCalendar } from '../scheduling/TherapistCalendar.jsx'
import { dateStr } from '../scheduling/slotCalendarUtils.js'
import { BookMeetingModal } from '../meetings/BookMeetingModal.jsx'
import { MeetingDetailSheet } from '../meetings/MeetingDetailSheet.jsx'
import { MeetingNotesSheet } from '../meetings/MeetingNotesSheet.jsx'
import { RescheduleMeetingModal } from '../meetings/RescheduleMeetingModal.jsx'
import {
  MONTH_FILTER_OPTIONS,
  SEARCH_DEBOUNCE_MS,
  STATUS_FILTER_OPTIONS,
  STATUS_LABELS,
  TYPE_FILTER_OPTIONS,
} from '../meetings/meetingConstants.js'
import { formatAttendeeList, meetingDisplayTitle, padHour, parseMeetingIdFromGridEvent } from '../meetings/meetingUtils.js'
import { mapCmMeetingToCalendarEvent } from '../../lib/googleCalendar.js'
import { AddToGoogleCalendarButton } from '../shared/AddToGoogleCalendarButton.jsx'
import { StaffAvailabilityPanel } from '../meetings/StaffAvailabilityPanel.jsx'
import {
  AdminCollapsibleFilters,
  AdminPageHeader,
  AdminSearchInput,
  FilterSelect,
  StaffCategoryPeopleFilter,
  STAFF_CATEGORY_TO_PARTICIPANT_ROLE,
} from './ui/index.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import './admin-reports.css'
import './admin-scheduling-hub.css'
import '../meetings/meetings-mobile.css'

function StatusBadge({ status }) {
  const s = STATUS_LABELS[status] || { label: status, bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '3px 8px', borderRadius: 6, background: s.bg, color: s.color }}>
      {s.label}
    </span>
  )
}

function CmNotesModal({ meeting, onClose, onUpdated }) {
  return (
    <MeetingNotesSheet
      open
      meeting={meeting}
      onClose={onClose}
      onSaved={onUpdated}
      isTherapistView={false}
    />
  )
}

function TherapistNotesModal({ meeting, onClose, onUpdated }) {
  return (
    <MeetingNotesSheet
      open
      meeting={meeting}
      onClose={onClose}
      onSaved={onUpdated}
      isTherapistView
    />
  )
}

function CancelMeetingModal({ meeting, onClose, onCancelled }) {
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function submit(e) {
    e.preventDefault()
    const trimmed = reason.trim()
    if (trimmed.length < 3) {
      setError('Please add a short reason so the team can understand the cancellation.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const result = await apiFetch(`/api/v1/meetings/${meeting.id}/cancel`, {
        method: 'POST',
        body: JSON.stringify({ reason: trimmed }),
      })
      onCancelled(result)
    } catch (err) {
      setError(err.message || 'Could not cancel meeting')
    } finally {
      setSaving(false)
    }
  }

  const taStyle = { display: 'block', width: '100%', border: '1px solid #e2e8f0', borderRadius: 10, padding: '8px 10px', fontSize: '0.875rem', marginTop: 4, minHeight: 120, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit' }
  const labelStyle = { fontSize: '0.875rem', fontWeight: 500, color: '#475569', display: 'block', marginBottom: 12 }

  return (
    <div className="meetings-modal-backdrop">
      <div className="meetings-modal-panel">
        <h2 className="meetings-modal-panel__title">Cancel meeting</h2>
        <p className="meetings-modal-panel__subtitle">
          {meeting.child_name ? `${meeting.child_name} · ` : ''}{formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time)}
        </p>
        {error ? <p style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, padding: '8px 12px', fontSize: '0.8rem', color: '#991b1b', marginBottom: 12 }}>{error}</p> : null}
        <form onSubmit={submit}>
          <label style={labelStyle}>
            Reason for cancellation
            <textarea
              style={taStyle}
              placeholder="Share the reason so the team and family have context..."
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <div className="meetings-modal-actions">
            <button type="submit" disabled={saving} style={{ flex: 1, background: '#dc2626', color: '#fff', border: 'none', borderRadius: 12, padding: '11px 0', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer' }}>
              {saving ? 'Cancelling…' : 'Cancel meeting'}
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

function MeetingCard({ meeting, onAddNotes, onCancel, onReschedule, caseLinkPrefix, readOnly = false, isTherapistView = false, calendarDeepLink = '/admin/meetings' }) {
  const displayTitle = meetingDisplayTitle(meeting)
  const hasNotes = isTherapistView
    ? Boolean(meeting.therapist_notes)
    : Boolean(
      meeting.notes_outcome || meeting.notes_summary || meeting.notes_additional
      || meeting.notes_concerns || meeting.notes_follow_up || meeting.notes_action || meeting.notes_other
    )
  const attendeeLine = formatAttendeeList(meeting)
  const calendarEvent = meeting.status === 'SCHEDULED'
    ? mapCmMeetingToCalendarEvent(meeting, { deepLinkPath: calendarDeepLink })
    : null

  return (
    <article style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: '16px 18px', marginBottom: 12, boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        <div>
          <p style={{ margin: 0, fontWeight: 700, fontSize: '0.9rem', color: '#1e293b' }}>
            {displayTitle}
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
            {hasNotes ? 'Edit notes' : isTherapistView ? 'Add notes' : 'Add notes / complete'}
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
  const canManageAvailability =
    !isParentPortal
    && (user?.roles?.includes('CASE_MANAGER')
      || user?.roles?.includes('ADMIN')
      || user?.roles?.includes('SUPER_ADMIN')
      || user?.roles?.includes('MODULE_ADMIN')
      || user?.roles?.includes('THERAPIST'))
  const caseLinkPrefix = isParentPortal ? null : isTherapistPortal ? '/therapist/cases' : '/admin/cases'
  const meetingsDeepLink = isParentPortal ? '/parent/meetings' : isTherapistPortal ? '/therapist/meetings' : '/admin/meetings'

  const [pageView, setPageView] = useState(isParentPortal ? 'list' : 'calendar')
  const [meetings, setMeetings] = useState([])
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [showBook, setShowBook] = useState(false)
  const [bookPrefill, setBookPrefill] = useState({ date: null, time: null })
  const [notesTarget, setNotesTarget] = useState(null)
  const [detailMeeting, setDetailMeeting] = useState(null)
  const [rescheduleTarget, setRescheduleTarget] = useState(null)
  const [cancelTarget, setCancelTarget] = useState(null)
  const [calendarRefresh, setCalendarRefresh] = useState(0)
  const [selectedCalendarEventId, setSelectedCalendarEventId] = useState(null)
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') || '')
  const [typeFilter, setTypeFilter] = useState(searchParams.get('meeting_type') || '')
  const [caseFilter, setCaseFilter] = useState(searchParams.get('case_id') || '')
  const [staffCategory, setStaffCategory] = useState('')
  const [peopleIds, setPeopleIds] = useState([])
  const [monthFilter, setMonthFilter] = useState(searchParams.get('month') || '')
  const [yearFilter, setYearFilter] = useState(searchParams.get('year') || String(new Date().getFullYear()))
  const [searchInput, setSearchInput] = useState(() => searchParams.get('search') || '')
  const [search, setSearch] = useState(searchInput)
  const [error, setError] = useState('')

  const showAvailabilityPanel = useMemo(
    () => canManageAvailability && (
      searchParams.get('availability') === '1'
      || !isTherapistPortal
      || pageView === 'list'
    ),
    [canManageAvailability, isTherapistPortal, pageView, searchParams],
  )

  const yearFilterOptions = useMemo(() => {
    const currentYear = new Date().getFullYear()
    return [
      { value: '', label: 'All years' },
      ...Array.from({ length: 5 }, (_, idx) => {
        const year = String(currentYear - 2 + idx)
        return { value: year, label: year }
      }),
    ]
  }, [])

  const queueTab = searchParams.get('queue') === 'admin'
  const listCountLabel = yearFilter ? `In current list (${yearFilter})` : 'In current list'

  useEffect(() => {
    const id = window.setTimeout(() => setSearch(searchInput), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(id)
  }, [searchInput])

  const buildFilterParams = useCallback(() => {
    const p = new URLSearchParams()
    if (statusFilter) p.set('status', statusFilter)
    if (typeFilter && !queueTab) p.set('meeting_type', typeFilter)
    if (caseFilter) p.set('case_id', caseFilter)
    if (isAdmin && peopleIds.length > 0) {
      const participantRole = STAFF_CATEGORY_TO_PARTICIPANT_ROLE[staffCategory]
      if (participantRole) p.set('participant_role', participantRole)
      p.set('participant_user_ids', peopleIds.map(String).join(','))
    }
    if (monthFilter) p.set('month', monthFilter)
    if (yearFilter) p.set('year', yearFilter)
    const term = String(search ?? '').trim()
    if (term) p.set('search', term)
    return p
  }, [statusFilter, typeFilter, caseFilter, staffCategory, peopleIds, monthFilter, yearFilter, search, queueTab, isAdmin])

  const buildQuery = useCallback(() => {
    const qs = buildFilterParams().toString()
    return qs ? `?${qs}` : ''
  }, [buildFilterParams])

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
    if (
      isAdmin
      && staffCategory === 'CASE_MANAGER'
      && peopleIds.length === 1
    ) {
      params.set('case_manager_user_id', peopleIds[0])
    }
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
      .catch((err) => {
        setError(err.message || 'Could not load bookable cases')
      })
  }, [isAdmin, staffCategory, peopleIds])

  useEffect(() => {
    loadBookableCases()
  }, [loadBookableCases])

  useEffect(() => {
    load()
  }, [load])

  async function handleExport(format) {
    const params = buildFilterParams()
    params.set('format', format)
    const ext = format === 'excel' ? 'xlsx' : 'csv'
    const stamp = yearFilter || 'all'
    setExporting(true)
    setError('')
    try {
      await apiDownload(`/api/v1/meetings/export?${params.toString()}`, `meetings_export_${stamp}.${ext}`)
    } catch (err) {
      setError(err.message || 'Could not export meetings')
    } finally {
      setExporting(false)
    }
  }

  const displayedMeetings = useMemo(() => {
    const active = meetings.filter((m) => m.status !== 'RESCHEDULED')
    if (!queueTab) return active
    return active.filter(
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

  function handleCancelled(m) {
    const cancelledId = cancelTarget?.id
    setCancelTarget(null)
    setDetailMeeting(null)
    setMeetings((prev) => prev.map((x) => (x.id === m.id || x.id === cancelledId ? m : x)))
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
      const found = await apiFetch(`/api/v1/meetings/${meetingId}`)
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
    setCancelTarget(meeting)
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
            ? 'View upcoming meetings and join links for your child.'
            : isTherapistPortal
              ? 'Request CM meetings and set the hours you are bookable for meetings and sessions.'
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

      {showAvailabilityPanel && user?.id ? (
        <StaffAvailabilityPanel
          userId={user.id}
          variant={isTherapistPortal ? 'therapist' : 'admin'}
          showGoogleCalendar={!isTherapistPortal}
          schedulingLink={isTherapistPortal ? '/therapist/slots' : null}
        />
      ) : null}

      {!isParentPortal && isTherapistPortal && canManageAvailability && !showAvailabilityPanel ? (
        <p className="admin-muted" style={{ marginBottom: 16, fontSize: '0.85rem' }}>
          <Link to="/therapist/meetings?availability=1" style={{ color: '#4338ca', fontWeight: 600 }}>
            Set your availability
          </Link>
          {' '}— one schedule for CM meetings and session booking.
        </p>
      ) : null}

      {!isParentPortal ? (
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
      ) : null}

      {!isParentPortal && pageView === 'calendar' ? (
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
            calendarFeed="unified"
            refreshKey={calendarRefresh}
            selectedSlotId={selectedCalendarEventId}
            onSlotClick={handleCalendarSlotClick}
            onCellClick={canBookMeetings && !isTherapistPortal ? handleCalendarCellClick : undefined}
          />
        </article>
      ) : null}

      {isParentPortal || pageView === 'list' ? (
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
              <div className="admin-reports__kpi-label">{listCountLabel}</div>
            </div>
          </div>

          {!isParentPortal ? (
            <div className="admin-reports__toolbar" style={{ marginBottom: 12 }}>
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                disabled={exporting}
                onClick={() => handleExport('csv')}
              >
                {exporting ? 'Exporting…' : 'Export CSV'}
              </button>
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                disabled={exporting}
                onClick={() => handleExport('excel')}
              >
                {exporting ? 'Exporting…' : 'Export Excel'}
              </button>
            </div>
          ) : null}

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
              staffCategory || null,
              peopleIds.length ? `${peopleIds.length} people` : null,
              yearFilter || null,
            ].filter(Boolean)}
            activeCount={[
              statusFilter,
              typeFilter,
              caseFilter,
              staffCategory,
              peopleIds.length ? 'people' : '',
              monthFilter,
              yearFilter,
            ].filter((v) => v && v !== 'ALL' && v !== '').length}
          >
            <div className="admin-meetings-filters">
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
                <StaffCategoryPeopleFilter
                  category={staffCategory}
                  onCategoryChange={setStaffCategory}
                  peopleIds={peopleIds}
                  onPeopleChange={setPeopleIds}
                  className="admin-meetings-filters__staff"
                />
              ) : null}
              <FilterSelect label="Month" value={monthFilter} onChange={(e) => setMonthFilter(e.target.value)} options={MONTH_FILTER_OPTIONS} />
              <FilterSelect label="Year" value={yearFilter} onChange={(e) => setYearFilter(e.target.value)} options={yearFilterOptions} />
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
                calendarDeepLink={meetingsDeepLink}
                readOnly={isParentPortal}
                isTherapistView={isTherapistPortal}
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
        isTherapistView={isTherapistPortal}
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

      {cancelTarget ? (
        <CancelMeetingModal
          meeting={cancelTarget}
          onClose={() => setCancelTarget(null)}
          onCancelled={handleCancelled}
        />
      ) : null}

      {notesTarget ? (
        isTherapistPortal ? (
          <TherapistNotesModal meeting={notesTarget} onClose={() => setNotesTarget(null)} onUpdated={handleUpdated} />
        ) : (
          <CmNotesModal meeting={notesTarget} onClose={() => setNotesTarget(null)} onUpdated={handleUpdated} />
        )
      ) : null}
    </div>
  )
}
