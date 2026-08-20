import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatLeaveRecordSplit } from '../../lib/leaveFormUtils.js'
import {
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  PortalTabBar,
} from './ui/index.js'
import '../hr-portal/leave-management.css'

const APPROVED_STYLE = { bg: '#f0fdf4', color: '#15803d', border: '#86efac' }

const VIEWS = [
  { id: 'leave', label: 'Therapist leave' },
  { id: 'child_absence', label: 'Child absence' },
]

function normalizeLeaveRow(row) {
  return { ...row, record_type: 'leave', display_status: row.status }
}

function normalizeChildAbsenceRow(row) {
  return {
    ...row,
    record_type: 'child_absence',
    display_status: row.leave_status || row.status,
    start_date: row.scheduled_date,
    end_date: row.scheduled_date,
    day_count: 1,
    leave_type: 'CHILD_ABSENT',
  }
}

function matchesSearch(row, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const haystack = [row.therapist_name, row.child_name, row.reason, row.case_code, row.leave_type]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(q)
}

export function FinanceLeavePage() {
  const [view, setView] = useState('leave')
  const [leaves, setLeaves] = useState([])
  const [childAbsences, setChildAbsences] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    Promise.all([
      apiFetch('/api/v1/leave?leave_status=APPROVED'),
      apiFetch('/api/v1/leave/child-absence').catch(() => ({ items: [] })),
    ])
      .then(([leaveData, childData]) => {
        if (cancelled) return
        setLeaves(Array.isArray(leaveData) ? leaveData : [])
        const childRows = Array.isArray(childData?.items) ? childData.items : []
        setChildAbsences(
          childRows.filter((row) => String(row.leave_status || row.status || '').toUpperCase() === 'APPROVED'),
        )
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load approved leave.')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const source = view === 'child_absence' ? childAbsences.map(normalizeChildAbsenceRow) : leaves.map(normalizeLeaveRow)
  const rows = source.filter((row) => matchesSearch(row, searchQuery))

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Finance"
        title="Therapist leave"
        subtitle="Approved therapist leave and approved child absence only — for payout cross-check. Pending requests stay with HR."
      />

      <PortalTabBar
        className="leave-mgmt__view-tabs"
        ariaLabel="Leave type"
        activeId={view}
        onChange={setView}
        tabs={VIEWS}
      />

      <AdminPanel title={view === 'child_absence' ? 'Approved child absence' : 'Approved therapist leave'} padded={false}>
        <div className="admin-panel__body">
          <div className="leave-mgmt__search-row">
            <AdminSearchInput
              value={searchQuery}
              onChange={setSearchQuery}
              placeholder={view === 'child_absence' ? 'Search child, therapist, or case' : 'Search therapist or reason'}
            />
          </div>
          {error ? <p className="admin-alert" style={{ color: '#b91c1c' }}>{error}</p> : null}
          {loading ? (
            <div className="admin-skeleton" />
          ) : rows.length === 0 ? (
            <AdminEmptyState
              title="No approved records"
              description={
                searchQuery.trim()
                  ? 'Nothing matches that search.'
                  : view === 'child_absence'
                    ? 'No approved child absence to show yet.'
                    : 'No approved therapist leave to show yet.'
              }
            />
          ) : (
            <div className="leave-mgmt__list">
              {rows.map((row) => {
                const isChildAbsence = row.record_type === 'child_absence'
                return (
                  <div key={`${row.record_type}-${row.id}`} className="leave-mgmt__card">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
                      <span
                        style={{
                          background: APPROVED_STYLE.bg,
                          color: APPROVED_STYLE.color,
                          border: `1px solid ${APPROVED_STYLE.border}`,
                          fontSize: '0.72rem',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: 20,
                        }}
                      >
                        {row.display_status || 'APPROVED'}
                      </span>
                      {isChildAbsence ? <span className="leave-mgmt__retro-badge">Child absent</span> : null}
                      {!isChildAbsence ? <span className="admin-chip admin-chip--sm">{row.leave_type}</span> : null}
                      <span className="admin-table__primary">
                        {isChildAbsence
                          ? `${row.child_name || 'Child'} · ${row.therapist_name || `Therapist #${row.therapist_user_id}`}`
                          : row.therapist_name || `Therapist #${row.therapist_user_id}`}
                      </span>
                      <span className="admin-muted" style={{ marginLeft: 'auto', fontSize: '0.75rem' }}>
                        {isChildAbsence
                          ? `${row.start_date}${row.start_time ? ` · ${String(row.start_time).slice(0, 5)}` : ''}`
                          : `${formatLeaveRecordSplit(row)} · ${row.day_count} day${row.day_count === 1 ? '' : 's'}`}
                      </span>
                    </div>
                    {isChildAbsence ? (
                      <div style={{ marginBottom: 10 }}>
                        <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>Session date</p>
                        <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{row.start_date}</p>
                        {row.case_code ? (
                          <p className="admin-muted" style={{ fontSize: '0.8rem', margin: '6px 0 0' }}>
                            Case {row.case_code}
                          </p>
                        ) : null}
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                        <div>
                          <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>From</p>
                          <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{row.start_date}</p>
                        </div>
                        <div>
                          <p className="admin-muted" style={{ fontSize: '0.72rem', margin: 0 }}>To</p>
                          <p style={{ fontWeight: 600, margin: '2px 0 0' }}>{row.end_date}</p>
                        </div>
                      </div>
                    )}
                    {row.reason ? (
                      <p className="admin-muted" style={{ fontSize: '0.85rem', marginBottom: 0 }}>{row.reason}</p>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
