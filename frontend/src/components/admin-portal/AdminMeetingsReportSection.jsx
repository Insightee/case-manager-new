import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { MeetingDetailSheet } from '../meetings/MeetingDetailSheet.jsx'
import { STATUS_LABELS } from '../meetings/meetingConstants.js'
import { meetingDisplayTitle } from '../meetings/meetingUtils.js'
import { AdminDataList, AdminEmptyState, AdminSearchInput, AdminTaskCard } from './ui/index.js'

function MeetingStatusBadge({ status }) {
  const s = STATUS_LABELS[status] || { label: status, bg: '#f1f5f9', color: '#475569' }
  return (
    <span
      className="admin-badge"
      style={{ background: s.bg, color: s.color }}
    >
      {s.label}
    </span>
  )
}

export function AdminMeetingsReportSection() {
  const [meetings, setMeetings] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    apiFetch('/api/v1/meetings')
      .then((rows) => setMeetings(Array.isArray(rows) ? rows : []))
      .catch((e) => setError(e.message || 'Could not load your meetings'))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return meetings
    return meetings.filter((m) => {
      const hay = [
        meetingDisplayTitle(m),
        m.case_code,
        m.child_name,
        m.notes_summary,
        m.notes_outcome,
        m.meeting_type,
        m.status,
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
      return hay.includes(q)
    })
  }, [meetings, search])

  if (loading) {
    return <p className="admin-muted">Loading your meetings…</p>
  }

  if (error) {
    return (
      <div>
        <p className="admin-alert admin-alert--error">{error}</p>
        <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={load}>
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="admin-meetings-report">
      <p className="admin-muted admin-portal-lead" style={{ marginBottom: 12 }}>
        Meetings you conducted or own. Tap a row to read notes and outcomes.
      </p>
      <div style={{ marginBottom: 12, maxWidth: 420 }}>
        <AdminSearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search case, child, notes…"
        />
      </div>
      {filtered.length === 0 ? (
        <AdminEmptyState
          title="No meetings yet"
          description="Scheduled and completed case-manager meetings will appear here."
        />
      ) : (
        <AdminDataList
          desktop={
            <div className="admin-table-wrap">
              <table className="admin-table admin-table--compact">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Meeting</th>
                    <th>Case / child</th>
                    <th>Status</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((m) => (
                    <tr
                      key={m.id}
                      className="admin-meetings-report__row"
                      tabIndex={0}
                      role="button"
                      onClick={() => setSelected(m)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setSelected(m)
                        }
                      }}
                    >
                      <td>
                        <span className="admin-table__primary">
                          {formatDisplayDateTime(m.scheduled_date, m.scheduled_time)}
                        </span>
                      </td>
                      <td>{meetingDisplayTitle(m)}</td>
                      <td>
                        {m.case_id ? (
                          <>
                            <Link
                              to={`/admin/cases/${m.case_id}?tab=cm-meetings`}
                              className="admin-table__primary"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {m.case_code || `#${m.case_id}`}
                            </Link>
                            {m.child_name ? (
                              <span className="admin-table__meta">{m.child_name}</span>
                            ) : null}
                          </>
                        ) : (
                          m.child_name || '—'
                        )}
                      </td>
                      <td>
                        <MeetingStatusBadge status={m.status} />
                      </td>
                      <td className="admin-meetings-report__notes">
                        {m.notes_summary || m.notes_outcome || '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          mobile={
            <ul className="admin-data-list__cards">
              {filtered.map((m) => (
                <li key={m.id}>
                  <AdminTaskCard
                    title={formatDisplayDateTime(m.scheduled_date, m.scheduled_time)}
                    meta={[m.case_code, m.child_name].filter(Boolean).join(' · ') || meetingDisplayTitle(m)}
                    badges={<MeetingStatusBadge status={m.status} />}
                    actions={
                      <button
                        type="button"
                        className="admin-btn admin-btn--primary admin-btn--sm"
                        onClick={() => setSelected(m)}
                      >
                        View notes
                      </button>
                    }
                  >
                    {m.notes_summary ? (
                      <p className="admin-muted" style={{ fontSize: '0.8125rem', margin: 0 }}>
                        {m.notes_summary}
                      </p>
                    ) : null}
                  </AdminTaskCard>
                </li>
              ))}
            </ul>
          }
        />
      )}
      <MeetingDetailSheet
        open={Boolean(selected)}
        meeting={selected}
        readOnly
        onClose={() => setSelected(null)}
      />
    </div>
  )
}
