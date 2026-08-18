import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ParentFilterBar, ParentFilterField, ParentFilterSelect } from './ParentFilterBar.jsx'
import { buildSessionDisputeState, SessionCard } from './SessionCard.jsx'
import { formatDisplayDateLabel, formatDisplayDateTime, todayIsoIST } from '../../lib/datetime.js'
import { MEETING_OUTCOME_LABELS } from '../meetings/meetingConstants.js'
import { CaseSessionLogExportButton } from '../shared/CaseSessionLogExportButton.jsx'
import './parent-session-updates.css'

function sessionDateIso(value) {
  if (!value) return ''
  return String(value).slice(0, 10)
}

function formatMonthLabel(monthValue) {
  const [year, month] = monthValue.split('-').map(Number)
  if (!year || !month) return monthValue
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
}

const VIEW_MODES = [
  { value: 'month', label: 'Month' },
  { value: 'day', label: 'Day' },
  { value: 'all', label: 'All' },
]

const ATTENDANCE_FILTERS = [
  { value: '', label: 'All attendance' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'CHILD_LEAVE', label: 'Child on leave' },
  { value: 'THERAPIST_LEAVE', label: 'Therapist on leave' },
  { value: 'MEETINGS', label: 'Meetings' },
]

function normalizedAttendance(log) {
  return (log?.attendance_status || '').toUpperCase()
}

function matchesAttendanceFilter(log, filter) {
  if (!filter) return true
  const att = normalizedAttendance(log)
  if (filter === 'COMPLETED') {
    return att !== 'CLIENT_ABSENT' && att !== 'CLIENT_LEAVE' && att !== 'THERAPIST_LEAVE'
  }
  if (filter === 'CHILD_LEAVE') return att === 'CLIENT_ABSENT' || att === 'CLIENT_LEAVE'
  if (filter === 'THERAPIST_LEAVE') return att === 'THERAPIST_LEAVE'
  return false
}

function shouldShowMeetings(attendanceFilter) {
  return !attendanceFilter || attendanceFilter === 'MEETINGS'
}

function shouldShowTherapistLeaveDays(attendanceFilter) {
  return !attendanceFilter || attendanceFilter === 'THERAPIST_LEAVE'
}

function isUnderReviewTherapistLeaveLog(log) {
  return (
    normalizedAttendance(log) === 'THERAPIST_LEAVE' && log.parent_display_status === 'Under Review'
  )
}

function therapistLeaveCoverageKeys(logs) {
  const keys = new Set()
  for (const log of logs || []) {
    if (normalizedAttendance(log) !== 'THERAPIST_LEAVE') continue
    if (isUnderReviewTherapistLeaveLog(log)) continue
    keys.add(`${log.case_id}:${sessionDateIso(log.scheduled_date)}`)
  }
  return keys
}

function isPendingLeaveEntry(entry) {
  return (entry?.status || '').toUpperCase() === 'PENDING'
}

function therapistLeaveBodyMessage(entry, today) {
  const dateLabel = formatLeaveDateLabel(entry)
  const dateIso = sessionDateIso(entry.scheduled_date)
  if (isPendingLeaveEntry(entry)) {
    if (dateIso > today) {
      return 'Your therapist will be unavailable.'
    }
    return `Your therapist was unavailable on ${dateLabel.toLowerCase()}.`
  }
  return `Your therapist was on leave on ${dateLabel.toLowerCase()}.`
}

function formatLeaveDateLabel(entry) {
  const start = formatDisplayDateLabel(entry.scheduled_date)
  if (entry.leave_end_date && entry.leave_end_date !== entry.scheduled_date) {
    return `${start} – ${formatDisplayDateLabel(entry.leave_end_date)}`
  }
  return start
}

function filterLogsByViewMode(logs, viewMode, selectedDate, selectedMonth) {
  if (viewMode === 'all') return logs
  if (viewMode === 'month') {
    return logs.filter((l) => sessionDateIso(l.scheduled_date).startsWith(selectedMonth))
  }
  return logs.filter((l) => sessionDateIso(l.scheduled_date) === selectedDate)
}

function emptyStateMessage(viewMode, selectedDate, selectedMonth) {
  if (viewMode === 'day') {
    return `No session updates for ${formatDisplayDateLabel(selectedDate)}. Your therapist will share approved updates after each visit.`
  }
  if (viewMode === 'month') {
    return `No session updates for ${formatMonthLabel(selectedMonth)}. Your therapist will share approved updates after each visit.`
  }
  return 'No session updates yet. Your therapist will share approved updates after each visit.'
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
        {meeting.notes_outcome ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Meeting outcome</h4>
            <p className="session-card__section-text">{MEETING_OUTCOME_LABELS[meeting.notes_outcome] || meeting.notes_outcome}</p>
          </section>
        ) : null}
        {meeting.notes_summary ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Discussion summary</h4>
            <p className="session-card__section-text">{meeting.notes_summary}</p>
          </section>
        ) : null}
        {meeting.notes_next_meeting_required ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Follow-up meeting</h4>
            <p className="session-card__section-text">A follow-up meeting has been scheduled or recommended.</p>
          </section>
        ) : null}
        {meeting.notes_additional ? (
          <section className="session-card__section">
            <h4 className="session-card__section-label">Additional notes</h4>
            <p className="session-card__section-text">{meeting.notes_additional}</p>
          </section>
        ) : null}
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
        {!meeting.notes_outcome &&
        !meeting.notes_summary &&
        !meeting.notes_additional &&
        !meeting.notes_concerns &&
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

function TherapistLeaveCard({ entry, highlighted = false }) {
  const dateLabel = formatLeaveDateLabel(entry)
  const pending = isPendingLeaveEntry(entry)
  const today = todayIsoIST()
  const message = therapistLeaveBodyMessage(entry, today)
  const statusBadge = pending ? 'Under review' : entry.status_label || 'On leave'

  return (
    <article
      className="session-card"
      style={{
        borderLeft: '3px solid #94a3b8',
        ...(highlighted ? { boxShadow: '0 0 0 2px #6366f1' } : {}),
      }}
    >
      {pending ? (
        <div
          style={{
            padding: '10px 14px',
            background: '#fffbeb',
            borderBottom: '1px solid #fde68a',
            fontSize: '0.8125rem',
            color: '#b45309',
            display: 'flex',
            gap: 6,
            alignItems: 'flex-start',
          }}
        >
          <span style={{ fontSize: '1.1rem', lineHeight: 1 }} aria-hidden>
            💡
          </span>
          <span>
            This leave is under review. Scheduled sessions are not cancelled until the leave is approved.
          </span>
        </div>
      ) : null}
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title">Therapist unavailable</h3>
          <p className="session-card__meta">
            {dateLabel}
            {entry.child_name ? ` · ${entry.child_name}` : ''}
            {entry.therapist_name ? ` · ${entry.therapist_name}` : ''}
          </p>
        </div>
        <span
          className="session-card__badge session-card__badge--neutral"
          style={
            pending
              ? { background: '#fef3c7', color: '#d97706', borderColor: '#fde68a' }
              : undefined
          }
        >
          {statusBadge}
        </span>
      </header>
      <div className="session-card__body">
        <p className="session-card__section-text" style={{ color: '#475569', margin: 0 }}>
          {message}
        </p>
      </div>
    </article>
  )
}

export function ClientSessionLogsPage() {
  const { cases } = useParentPortal()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const highlightLogId = searchParams.get('log_id')
  const highlightLeaveId = searchParams.get('leave_id')
  const logCardRefs = useRef(new Map())
  const leaveCardRefs = useRef(new Map())
  const today = todayIsoIST()
  const [viewMode, setViewMode] = useState('month')
  const [selectedMonth, setSelectedMonth] = useState(today.slice(0, 7))
  const [selectedDate, setSelectedDate] = useState(today)
  const [logs, setLogs] = useState([])
  const [meetings, setMeetings] = useState([])
  const [therapistLeaveDays, setTherapistLeaveDays] = useState([])
  const [caseId, setCaseId] = useState('')
  const [attendanceFilter, setAttendanceFilter] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchScopeKey = useMemo(() => {
    if (viewMode === 'all') return 'all'
    if (viewMode === 'day') return selectedDate.slice(0, 7)
    return selectedMonth
  }, [viewMode, selectedDate, selectedMonth])

  function load() {
    setLoading(true)
    const caseQ = caseId ? `&case_id=${caseId}` : ''
    const logsUrl =
      fetchScopeKey === 'all'
        ? `/api/v1/parent/session-logs${caseId ? `?case_id=${caseId}` : ''}`
        : (() => {
            const [year, month] = fetchScopeKey.split('-').map(Number)
            return `/api/v1/parent/session-logs?year=${year}&month=${month}${caseQ}`
          })()
    const meetingsUrl =
      fetchScopeKey === 'all'
        ? '/api/v1/parent/cm-meetings'
        : (() => {
            const [year, month] = fetchScopeKey.split('-').map(Number)
            return `/api/v1/parent/cm-meetings?year=${year}&month=${month}`
          })()

    const leaveUrl =
      fetchScopeKey === 'all'
        ? `/api/v1/parent/therapist-leaves${caseId ? `?case_id=${caseId}` : ''}`
        : (() => {
            const [year, month] = fetchScopeKey.split('-').map(Number)
            return `/api/v1/parent/therapist-leaves?year=${year}&month=${month}${caseQ}`
          })()

    Promise.all([
      apiFetch(logsUrl).catch(() => []),
      apiFetch(meetingsUrl).catch(() => []),
      apiFetch(leaveUrl).catch(() => []),
    ])
      .then(([logsData, meetingsData, leaveData]) => {
        setLogs(logsData || [])
        setMeetings(meetingsData || [])
        setTherapistLeaveDays(leaveData || [])
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
        setViewMode('day')
        setSelectedDate(dateValue)
        setSelectedMonth(dateValue.slice(0, 7))
      } catch {
        /* keep default view */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [highlightLogId])

  useEffect(() => {
    if (!highlightLeaveId) return
    let cancelled = false
    ;(async () => {
      try {
        const allLeaves = await apiFetch('/api/v1/parent/therapist-leaves')
        if (cancelled) return
        const matches = (allLeaves || []).filter(
          (entry) => String(entry.leave_id) === String(highlightLeaveId),
        )
        if (!matches.length) return
        matches.sort((a, b) => String(a.scheduled_date).localeCompare(String(b.scheduled_date)))
        const match = matches[0]
        const dateValue = sessionDateIso(match.scheduled_date)
        if (!dateValue) return
        setViewMode('day')
        setSelectedDate(dateValue)
        setSelectedMonth(dateValue.slice(0, 7))
        setAttendanceFilter('THERAPIST_LEAVE')
      } catch {
        /* keep default view */
      }
    })()
    return () => {
      cancelled = true
    }
  }, [highlightLeaveId])

  useEffect(() => {
    load()
  }, [caseId, fetchScopeKey])

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

  const periodFilteredLogs = useMemo(
    () => filterLogsByViewMode(logs, viewMode, selectedDate, selectedMonth),
    [logs, viewMode, selectedDate, selectedMonth],
  )

  const periodFilteredMeetings = useMemo(() => {
    let list = filterLogsByViewMode(meetings, viewMode, selectedDate, selectedMonth)
    if (caseId) {
      list = list.filter((m) => String(m.case_id) === String(caseId))
    }
    return list
  }, [meetings, viewMode, selectedDate, selectedMonth, caseId])

  const filteredLogs = useMemo(() => {
    if (attendanceFilter === 'MEETINGS') return []
    return periodFilteredLogs
      .filter((l) => matchesAttendanceFilter(l, attendanceFilter))
      .filter((l) => !isUnderReviewTherapistLeaveLog(l))
  }, [periodFilteredLogs, attendanceFilter])

  const filteredMeetings = useMemo(() => {
    if (!shouldShowMeetings(attendanceFilter)) return []
    return periodFilteredMeetings
  }, [periodFilteredMeetings, attendanceFilter])

  const filteredLeaveDays = useMemo(() => {
    if (!shouldShowTherapistLeaveDays(attendanceFilter)) return []
    let list = filterLogsByViewMode(therapistLeaveDays, viewMode, selectedDate, selectedMonth)
    if (caseId) {
      list = list.filter((entry) => String(entry.case_id) === String(caseId))
    }
    const covered = therapistLeaveCoverageKeys(periodFilteredLogs)
    return list.filter((entry) => !covered.has(`${entry.case_id}:${sessionDateIso(entry.scheduled_date)}`))
  }, [
    therapistLeaveDays,
    viewMode,
    selectedDate,
    selectedMonth,
    caseId,
    attendanceFilter,
    periodFilteredLogs,
  ])

  useEffect(() => {
    if (!highlightLeaveId || loading) return
    const match = filteredLeaveDays.find((entry) => String(entry.leave_id) === String(highlightLeaveId))
    if (!match) return
    const node = leaveCardRefs.current.get(match.id)
    if (!node) return
    const t = setTimeout(() => {
      node.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    }, 120)
    return () => clearTimeout(t)
  }, [highlightLeaveId, loading, filteredLeaveDays])

  function handleViewModeChange(nextMode) {
    setViewMode(nextMode)
    if (nextMode === 'day') {
      setSelectedDate((prev) => {
        if (prev.startsWith(selectedMonth)) return prev
        return `${selectedMonth}-01`
      })
    }
    if (nextMode === 'month') {
      setSelectedMonth(selectedDate.slice(0, 7))
    }
  }

  function handleDispute(log) {
    navigate('/parent/support?tab=support', { state: buildSessionDisputeState(log) })
  }

  const filterGridClass = caseOptions.length > 0
    ? 'parent-portal-filters__grid--tablet-2 parent-portal-filters__grid--desktop-4'
    : 'parent-portal-filters__grid--tablet-2 parent-portal-filters__grid--desktop-3'

  return (
    <ClientPortalLayout title="Session updates" subtitle="">
      <ParentFilterBar
        ariaLabel="Filter session updates"
        className="parent-portal-filters--compact"
        gridClass={filterGridClass}
        actions={
          <>
            {caseId ? (
              <CaseSessionLogExportButton
                caseId={Number(caseId)}
                caseCode={caseOptions.find((c) => String(c.id) === String(caseId))?.caseId}
                parent
                viewMode={viewMode}
                selectedMonth={selectedMonth}
                selectedDate={selectedDate}
                attendanceFilter={attendanceFilter}
                className="parent-portal-filters__export"
              />
            ) : null}
            <Link to="/parent/book" className="parent-portal-filters__link">
              Schedule →
            </Link>
          </>
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

        <ParentFilterField label="View">
          <ParentFilterSelect
            value={viewMode}
            onChange={(e) => handleViewModeChange(e.target.value)}
            aria-label="Session updates view"
          >
            {VIEW_MODES.map((mode) => (
              <option key={mode.value} value={mode.value}>
                {mode.label}
              </option>
            ))}
          </ParentFilterSelect>
        </ParentFilterField>

        {viewMode === 'day' ? (
          <ParentFilterField label="Date">
            <input
              type="date"
              className="parent-portal-filters__control parent-portal-filters__control--date"
              value={selectedDate}
              onChange={(e) => {
                const next = e.target.value
                setSelectedDate(next)
                if (next) setSelectedMonth(next.slice(0, 7))
              }}
              aria-label="Session date"
            />
          </ParentFilterField>
        ) : null}

        {viewMode === 'month' ? (
          <ParentFilterField label="Month">
            <input
              type="month"
              className="parent-portal-filters__control parent-portal-filters__control--date"
              value={selectedMonth}
              onChange={(e) => setSelectedMonth(e.target.value)}
              aria-label="Session month"
            />
          </ParentFilterField>
        ) : null}

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
      ) : filteredLogs.length === 0 && filteredMeetings.length === 0 && filteredLeaveDays.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>{emptyStateMessage(viewMode, selectedDate, selectedMonth)}</p>
      ) : (
        (() => {
          const combined = [
            ...filteredLogs.map((l) => ({ type: 'log', date: l.scheduled_date, data: l })),
            ...filteredLeaveDays.map((entry) => ({ type: 'leave', date: entry.scheduled_date, data: entry })),
            ...filteredMeetings.map((m) => ({ type: 'meeting', date: m.scheduled_date, data: m })),
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
            if (item.type === 'leave') {
              const isHighlighted =
                highlightLeaveId && String(item.data.leave_id) === String(highlightLeaveId)
              return (
                <div
                  key={item.data.id}
                  ref={(node) => {
                    if (node) leaveCardRefs.current.set(item.data.id, node)
                  }}
                >
                  <TherapistLeaveCard entry={item.data} highlighted={isHighlighted} />
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
