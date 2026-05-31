import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useParentPortal } from '../../hooks/useParentPortal.js'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ParentFilterBar, ParentFilterField, ParentFilterSelect } from './ParentFilterBar.jsx'
import { buildSessionDisputeState, SessionCard } from './SessionCard.jsx'
import './parent-session-updates.css'

function CmMeetingCard({ meeting }) {
  const dateLabel = meeting.scheduled_date
    ? new Date(meeting.scheduled_date + 'T00:00:00').toLocaleDateString(undefined, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : ''

  return (
    <article className="session-card" style={{ borderLeft: '3px solid #7c3aed' }}>
      <header className="session-card__head">
        <div>
          <h3 className="session-card__title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {meeting.child_name || 'Case manager meeting'}
            <span className="session-card__cm-pill">CM Meeting</span>
          </h3>
          <p className="session-card__meta">
            {dateLabel}
            {meeting.scheduled_time ? ` · ${meeting.scheduled_time}` : ''}
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

function buildMonthOptions() {
  const opts = []
  const now = new Date()
  for (let i = 0; i < 12; i++) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1)
    opts.push({
      value: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`,
      label: d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }),
      year: d.getFullYear(),
      month: d.getMonth() + 1,
    })
  }
  return opts
}

const ATTENDANCE_FILTERS = [
  { value: '', label: 'All attendance' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'PARTIAL', label: 'Partial' },
  { value: 'NO_SHOW', label: 'No show' },
  { value: 'CANCELLED', label: 'Cancelled' },
]

export function ClientSessionLogsPage() {
  const { cases } = useParentPortal()
  const navigate = useNavigate()
  const monthOptions = useMemo(() => buildMonthOptions(), [])
  const [selectedMonth, setSelectedMonth] = useState(monthOptions[0].value)
  const [logs, setLogs] = useState([])
  const [meetings, setMeetings] = useState([])
  const [caseId, setCaseId] = useState('')
  const [attendanceFilter, setAttendanceFilter] = useState('')
  const [loading, setLoading] = useState(true)

  const selectedMeta = useMemo(
    () => monthOptions.find((o) => o.value === selectedMonth) || monthOptions[0],
    [selectedMonth, monthOptions],
  )

  function load() {
    setLoading(true)
    const caseQ = caseId ? `&case_id=${caseId}` : ''
    Promise.all([
      apiFetch(`/api/v1/parent/session-logs?year=${selectedMeta.year}&month=${selectedMeta.month}${caseQ}`).catch(
        () => [],
      ),
      apiFetch(`/api/v1/parent/cm-meetings?year=${selectedMeta.year}&month=${selectedMeta.month}`).catch(() => []),
    ])
      .then(([logsData, meetingsData]) => {
        setLogs(logsData || [])
        setMeetings(meetingsData || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [caseId, selectedMonth])

  const caseOptions = useMemo(() => {
    const byChild = new Map()
    for (const c of cases) {
      if (!byChild.has(c.childName)) byChild.set(c.childName, c)
    }
    return [...byChild.values()]
  }, [cases])

  const filteredLogs = useMemo(() => {
    if (!attendanceFilter) return logs
    return logs.filter((l) => (l.attendance_status || '').toUpperCase() === attendanceFilter)
  }, [logs, attendanceFilter])

  function handleDispute(log) {
    navigate('/parent/support?tab=support', { state: buildSessionDisputeState(log) })
  }

  const monthLabel = selectedMeta.label

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

        <ParentFilterField label="Month">
          <ParentFilterSelect value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)}>
            {monthOptions.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </ParentFilterSelect>
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
      ) : filteredLogs.length === 0 && meetings.length === 0 ? (
        <p style={{ color: '#94a3b8' }}>
          No session updates for {monthLabel}. Your therapist will share approved updates after each visit.
        </p>
      ) : (
        (() => {
          const combined = [
            ...filteredLogs.map((l) => ({ type: 'log', date: l.scheduled_date, data: l })),
            ...meetings.map((m) => ({ type: 'meeting', date: m.scheduled_date, data: m })),
          ].sort((a, b) => (a.date > b.date ? -1 : a.date < b.date ? 1 : 0))

          return combined.map((item) =>
            item.type === 'log' ? (
              <SessionCard key={`log-${item.data.id}`} log={item.data} onSaved={load} onDispute={handleDispute} />
            ) : (
              <CmMeetingCard key={`cm-${item.data.id}`} meeting={item.data} />
            ),
          )
        })()
      )}
    </ClientPortalLayout>
  )
}
