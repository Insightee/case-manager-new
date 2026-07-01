import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ParentFilterBar, ParentFilterField, ParentFilterSelect } from './ParentFilterBar.jsx'
import { buildSessionDisputeState, SessionCard } from './SessionCard.jsx'
import { formatDisplayDateLabel, formatDisplayDateTime, todayIsoIST } from '../../lib/datetime.js'
import { isAbsenceAttendanceLog, isChildAbsentLog, isLeaveLog } from '../../lib/sessionLogFilters.js'
import './parent-session-updates.css'

function sessionDateIso(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function matchesAttendanceFilter(log, filter) {
  if (!filter) return true
  if (filter === 'COMPLETED') return !isAbsenceAttendanceLog(log)
  if (filter === 'CHILD_LEAVE') return isChildAbsentLog(log)
  if (filter === 'THERAPIST_LEAVE') return isLeaveLog(log)
  return true
}

function CmMeetingCard({ meeting }) {
  const dateLabel = meeting.scheduled_date ? formatDisplayDateLabel(meeting.scheduled_date) : ''

  return (
    <article className="session-card" style={{ borderLeft: '3px solid #7c3aed' }}>
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {meeting.child_name || 'Case manager meeting'}
            <span className="session-card__cm-pill">CM Meeting</span>
          </h3>
          <p className="session-card__meta">
            {formatDisplayDateTime(meeting.scheduled_date, meeting.scheduled_time) || dateLabel}
            {meeting.case_manager_name ? ` · Case manager: ${meeting.case_manager_name}` : ''}
          </p>
        </div>
        <span className="session-card__badge session-card__badge--cm">{meeting.status}</span>
      </header>

      <div className="session-card__body">
        {meeting.notes_concerns ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Concerns addressed</h4>
            <p className="session-card__section-text">{meeting.notes_concerns}</p>
          </section>
        ) : null}
        {meeting.notes_follow_up ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Follow-up steps</h4>
            <p className="session-card__section-text">{meeting.notes_follow_up}</p>
          </section>
        ) : null}
        {meeting.notes_action ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Actions taken</h4>
            <p className="session-card__section-text">{meeting.notes_action}</p>
          </section>
        ) : null}
        {meeting.notes_other ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Additional notes</h4>
            <p className="session-card__section-text">{meeting.notes_other}</p>
          </section>
        ) : null}
        {!meeting.notes_concerns &&
        !meeting.notes_follow_up &&
        !meeting.notes_action &&
        !meeting.notes_other ? (
          <p className="session-card__empty-note">
            Meeting notes will appear here after your case manager completes the meeting.
          </p>
        ) : null}
      </div>
    </article>
  )
}

const ATTENDANCE_FILTERS = [
  { value: '', label: 'All attendance' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CHILD_LEAVE', label: 'Child on leave' },
  { value: 'THERAPIST_LEAVE', label: 'Therapist on leave' },
]

export function ClientSessionLogsPage() {
  const { cases } = useParentPortal()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const highlightLogId = searchParams.get('log_id')
  const logCardRefs = useRef(new Map())
  const [selectedDate, setSelectedDate] = useState(todayIsoIST)
  const [logs, setLogs] = useState([])
  const [meetings, setMeetings] = useState([])
  const [caseId, setCaseId] = useState('')
  const [attendanceFilter, setAttendanceFilter] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchPeriod = useMemo(() => {
    const [year, month] = selectedDate.split('-').map(Number)
    return { year, month }
  }, [selectedDate])

  function load() {
    setLoading(true)
    const caseQ = caseId ? `&case_id=${caseId}` : ''
    Promise.all([
      apiFetch(`/api/v1/parent/session-logs?year=${fetchPeriod.year}&month=${fetchPeriod.month}${caseQ}`).catch(
        () => [],
      ),
      apiFetch(`/api/v1/parent/cm-meetings?year=${fetchPeriod.year}&month=${fetchPeriod.month}`).catch(() => []),
    ])
      .then(([logsData, meetingsData]) => {
        setLogs(logsData || [])
        setMeetings(meetingsData || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!highlightLogId) return
    let cancelled = false
    ;(async () => {
      try {
        const allLogs = await apiFetch('/api/v1/parent/session-logs')
        if (cancelled) return
        const match = (allLogs || []).find((l) => String(l.id) === String(highlightLogId))
        if (!match?.scheduled_date) return
        const dateValue = sessionDateIso(match.scheduled_date)
        if (!dateValue) return
        setSelectedDate((prev) => (prev === dateValue ? prev : dateValue))
      } catch {
        /* keep default date */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [highlightLogId])

  useEffect(() => {
    load()
  }, [caseId, fetchPeriod.year, fetchPeriod.month])

  useEffect(() => {
    if (!highlightLogId || loading) return
    const node = logCardRefs.current.get(String(highlightLogId))
    if (!node) return
    const t = setTimeout(() => {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 120)
    return () => clearTimeout(t)
  }, [highlightLogId, loading, logs])

  const caseOptions = useMemo(() => {
    const byChild = new Map()
    for (const c of cases) {
      if (!byChild.has(c.childName)) byChild.set(c.childName, c)
    }
    return [...byChild.values()]
  }, [cases])

  const dateFilteredLogs = useMemo(
    () => logs.filter((l) => sessionDateIso(l.scheduled_date) === selectedDate),
    [logs, selectedDate],
  )

  const dateFilteredMeetings = useMemo(
    () => meetings.filter((m) => sessionDateIso(m.scheduled_date) === selectedDate),
    [meetings, selectedDate],
  )

  const filteredLogs = useMemo(
    () => dateFilteredLogs.filter((l) => matchesAttendanceFilter(l, attendanceFilter)),
    [dateFilteredLogs, attendanceFilter],
  )

  function handleDispute(log) {
    navigate('/parent/support?tab=support', { state: buildSessionDisputeState(log) })
  }

  const dateLabel = formatDisplayDateLabel(selectedDate)

  return (
    <ClientPortalLayout title="Session updates" subtitle="">
      <ParentFilterBar
        ariaLabel="Filter session updates"
        className="parent-portal-filters--compact"
        gridClass="parent-portal-filters__grid--tablet-2 parent-portal-filters__grid--desktop-3"
        actions={
          <Link to="/parent/book" className="parent-portal-filters__link">
            Schedule →
          </Link>
        }
      >
        {caseOptions.length > 0 ? (
          <ParentFilterField label="Child">
            <ParentFilterSelect value={caseId} onChange={(e) => setCaseId(e.target.value)}>
              <option value="">All children</option>
              {caseOptions.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.childName} · {c.serviceType}
                </option>
              ))}
            </ParentFilterSelect>
          </ParentFilterField>
        ) : null}

        <ParentFilterField label="Date">
          <input
            type="date"
            className="parent-portal-filters__control parent-portal-filters__control--date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            aria-label="Session date"
          />
        </ParentFilterField>

        <ParentFilterField label="Attendance">
          <ParentFilterSelect value={attendanceFilter} onChange={(e) => setAttendanceFilter(e.target.value)}>
            {ATTENDANCE_FILTERS.map((f) => (
              <option key={f.value || 'all'} value={f.value}>
                {f.label}
              </option>
            ))}
          </ParentFilterSelect>
        </ParentFilterField>
      </ParentFilterBar>

      {loading ? (
        <p style={{ color: '#94a3b8' }}>Loading session updates…</p>
      ) : filteredLogs.length === 0 && dateFilteredMeetings.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>
          No session updates for {dateLabel}. Your therapist will share approved updates after each visit.
        </p>
      ) : (
        (() => {
          const combined = [
            ...filteredLogs.map((l) => ({ type: 'log', date: l.scheduled_date, data: l })),
            ...dateFilteredMeetings.map((m) => ({ type: 'meeting', date: m.scheduled_date, data: m })),
          ].sort((a, b) => (a.date > b.date ? -1 : a.date < b.date ? 1 : 0))

          let firstLogSeen = false
          return combined.map((item) => {
            if (item.type === 'log') {
              const isHighlighted = highlightLogId && String(item.data.id) === String(highlightLogId)
              const defaultExpanded = isHighlighted || (!highlightLogId && !firstLogSeen)
              if (!highlightLogId && !firstLogSeen) firstLogSeen = true
              return (
                <div
                  key={`log-${item.data.id}`}
                  ref={(node) => {
                    if (node) logCardRefs.current.set(String(item.data.id), node)
                  }}
                >
                  <SessionCard
                    log={item.data}
                    defaultExpanded={defaultExpanded}
                    onSaved={load}
                    onDispute={handleDispute}
                  />
                </div>
              )
            }
            return <CmMeetingCard key={`cm-${item.data.id}`} meeting={item.data} />
          })
        })()
      )}
    </ClientPortalLayout>
  )
}
