import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useDebouncedValue } from '../../hooks/useDebouncedValue.js'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, PeopleListPagination } from './ui/index.js'
import { AdminOpsKpiGrid } from './AdminOpsKpiGrid.jsx'
import './admin-platform-stats.css'

const PERIOD_OPTIONS = [
  { value: 1, label: 'Today' },
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
]

const STATUS_FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'active_now', label: 'Active now' },
  { value: 'logged_in', label: 'Logged in' },
  { value: 'active', label: 'Active time' },
]

const ROLE_FILTER_OPTIONS = [
  { value: '', label: 'All roles' },
  { value: 'SUPER_ADMIN', label: 'Super admin' },
  { value: 'MODULE_ADMIN', label: 'Module admin' },
  { value: 'CASE_MANAGER', label: 'Case manager' },
  { value: 'SUPERVISOR', label: 'Supervisor' },
  { value: 'FINANCE', label: 'Finance' },
  { value: 'HR', label: 'HR' },
  { value: 'THERAPIST', label: 'Therapist' },
  { value: 'PARENT', label: 'Parent' },
  { value: 'ADMIN', label: 'Admin (legacy)' },
]

const PORTAL_FILTER_OPTIONS = [
  { value: '', label: 'All portals' },
  { value: 'admin', label: 'Admin portal' },
  { value: 'therapist', label: 'Therapist portal' },
  { value: 'parent', label: 'Parent portal' },
]

const ACTIVITY_PAGE_SIZE = 25

const ROLE_LABELS = {
  SUPER_ADMIN: 'Super admin',
  MODULE_ADMIN: 'Module admin',
  ADMIN: 'Admin (legacy)',
  CASE_MANAGER: 'Case manager',
  SUPERVISOR: 'Supervisor',
  FINANCE: 'Finance',
  HR: 'HR',
  THERAPIST: 'Therapist',
  PARENT: 'Parent',
  SCHOOL_COORDINATOR: 'School coordinator',
  VIEWER: 'Viewer',
}

const PORTAL_LABELS = {
  admin: 'Admin portal',
  therapist: 'Therapist portal',
  parent: 'Parent portal',
  unknown: 'Unknown',
}

function formatDuration(seconds) {
  const total = Math.max(0, Number(seconds) || 0)
  if (total < 60) return `${total}s`
  const mins = Math.floor(total / 60)
  if (mins < 60) return `${mins}m`
  const hours = Math.floor(mins / 60)
  const remMins = mins % 60
  return remMins ? `${hours}h ${remMins}m` : `${hours}h`
}

function formatWhen(iso) {
  if (!iso) return '—'
  return formatTimestampDateIN(iso) || iso
}

function roleLabel(role) {
  return ROLE_LABELS[role] || role?.replace(/_/g, ' ') || '—'
}

function portalLabel(portal) {
  return PORTAL_LABELS[portal] || portal || '—'
}

function buildActivityQuery({ days, page, search, status, role, portal }) {
  const qs = new URLSearchParams()
  qs.set('days', String(days))
  qs.set('page', String(page))
  qs.set('limit', String(ACTIVITY_PAGE_SIZE))
  if (search.trim()) qs.set('q', search.trim())
  if (status && status !== 'all') qs.set('status', status)
  if (role) qs.set('role', role)
  if (portal) qs.set('portal', portal)
  return qs.toString()
}

function buildKpis(stats) {
  if (!stats?.summary) return []
  const s = stats.summary
  const periodHint =
    stats.period?.days === 1
      ? 'IST calendar day'
      : `${stats.period?.days ?? '—'} day window (IST)`
  return [
    {
      title: 'Logged in',
      value: s.unique_logins ?? '—',
      hint:
        s.login_events != null && s.login_events !== s.unique_logins
          ? `${s.login_events} sign-in events · ${periodHint}`
          : periodHint,
      tone: 'teal',
      icon: '↪',
    },
    {
      title: 'Active users',
      value: s.unique_active_users ?? '—',
      hint: 'Had tracked active time in period',
      tone: 'indigo',
      icon: '◉',
    },
    {
      title: 'Active now',
      value: s.active_now ?? '—',
      hint: `Seen in last ${s.active_now_window_minutes ?? 15} min`,
      tone: 'amber',
      icon: '●',
    },
    {
      title: 'Active time',
      value: formatDuration(s.total_active_seconds),
      hint: 'Sum of heartbeat active seconds',
      tone: 'slate',
      icon: '⏱',
    },
    {
      title: 'Registered users',
      value: s.total_users ?? '—',
      hint: 'All accounts in the system',
      tone: 'rose',
      icon: '◎',
    },
  ]
}

export function AdminPlatformStatsPage() {
  const { can } = useAuth()
  const [days, setDays] = useState(1)
  const [stats, setStats] = useState(null)
  const [activity, setActivity] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activityLoading, setActivityLoading] = useState(true)
  const [error, setError] = useState('')
  const [activityError, setActivityError] = useState('')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [roleFilter, setRoleFilter] = useState('')
  const [portalFilter, setPortalFilter] = useState('')
  const [activityPage, setActivityPage] = useState(1)
  const searchDebounced = useDebouncedValue(search, 300)

  const loadStats = useCallback(() => {
    setLoading(true)
    setError('')
    return apiFetch(`/api/v1/admin/platform-stats?days=${days}`)
      .then((data) => {
        setStats(data)
      })
      .catch((err) => {
        setStats(null)
        setError(err.message || 'Could not load platform stats')
      })
      .finally(() => setLoading(false))
  }, [days])

  const loadActivity = useCallback(() => {
    setActivityLoading(true)
    setActivityError('')
    const qs = buildActivityQuery({
      days,
      page: activityPage,
      search: searchDebounced,
      status: statusFilter,
      role: roleFilter,
      portal: portalFilter,
    })
    return apiFetch(`/api/v1/admin/platform-stats/activity?${qs}`)
      .then((data) => {
        setActivity(data)
      })
      .catch((err) => {
        setActivity(null)
        setActivityError(err.message || 'Could not load activity')
      })
      .finally(() => setActivityLoading(false))
  }, [days, activityPage, searchDebounced, statusFilter, roleFilter, portalFilter])

  useEffect(() => {
    if (!can('admin.override')) {
      setLoading(false)
      setActivityLoading(false)
      return undefined
    }
    loadStats()
    const timer = window.setInterval(loadStats, 60_000)
    return () => window.clearInterval(timer)
  }, [can, loadStats])

  useEffect(() => {
    if (!can('admin.override')) return undefined
    loadActivity()
    const timer = window.setInterval(loadActivity, 60_000)
    return () => window.clearInterval(timer)
  }, [can, loadActivity])

  useEffect(() => {
    setActivityPage(1)
  }, [searchDebounced])

  const kpis = useMemo(() => buildKpis(stats), [stats])

  const refreshAll = () => {
    void loadStats()
    void loadActivity()
  }

  if (!can('admin.override')) {
    return (
      <div className="admin-page admin-platform-stats">
        <AdminPageHeader
          eyebrow="Super admin"
          title="Platform stats"
          subtitle="Usage and sign-in activity across InsighteCase."
        />
        <AdminPanel>
          <AdminEmptyState
            title="Super admin access required"
            description="Platform stats are available to super admin accounts only."
          />
        </AdminPanel>
      </div>
    )
  }

  const activityRows = activity?.items ?? []
  const hasActiveFilters = Boolean(
    search.trim() || statusFilter !== 'all' || roleFilter || portalFilter,
  )

  const resetActivityPage = () => setActivityPage(1)

  return (
    <div className="admin-page admin-platform-stats">
      <AdminPageHeader
        eyebrow="Super admin"
        title="Platform stats"
        subtitle="Sign-ins and active usage from audit logs and portal heartbeats (IST)."
        actions={
          <div className="admin-btn-group admin-platform-stats__header-actions">
            <div className="admin-platform-stats__period" role="group" aria-label="Time period">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`admin-btn admin-btn--secondary admin-platform-stats__period-btn${
                    days === opt.value ? ' is-active' : ''
                  }`}
                  onClick={() => {
                    setDays(opt.value)
                    resetActivityPage()
                  }}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="admin-btn admin-btn--secondary"
              onClick={refreshAll}
              disabled={loading || activityLoading}
            >
              Refresh
            </button>
          </div>
        }
      />

      {error ? (
        <p className="admin-alert admin-alert--error" role="alert">
          {error}
        </p>
      ) : null}

      {stats?.tracking?.note ? (
        <p className="admin-muted admin-platform-stats__note">{stats.tracking.note}</p>
      ) : null}

      <AdminOpsKpiGrid kpis={kpis} loading={loading && !stats} />

      <div className="admin-platform-stats__grid">
        <AdminPanel title="By portal" className="admin-platform-stats__panel">
          {loading && !stats ? (
            <div className="admin-skeleton admin-platform-stats__skeleton" />
          ) : stats?.by_portal?.length ? (
            <div className="admin-table-wrap">
              <table className="admin-table admin-platform-stats__table">
                <thead>
                  <tr>
                    <th>Portal</th>
                    <th>Active users</th>
                    <th>Active now</th>
                    <th>Active time</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_portal.map((row) => (
                    <tr key={row.portal}>
                      <td>{portalLabel(row.portal)}</td>
                      <td>{row.unique_users ?? 0}</td>
                      <td>
                        {row.active_now ? (
                          <span className="admin-platform-stats__live">{row.active_now}</span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td>{formatDuration(row.active_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <AdminEmptyState
              title="No portal activity yet"
              description="Usage heartbeats will appear here once staff use the admin, therapist, or parent portals."
            />
          )}
        </AdminPanel>

        <AdminPanel title="By role" className="admin-platform-stats__panel">
          {loading && !stats ? (
            <div className="admin-skeleton admin-platform-stats__skeleton" />
          ) : stats?.by_role?.length ? (
            <div className="admin-table-wrap">
              <table className="admin-table admin-platform-stats__table">
                <thead>
                  <tr>
                    <th>Role</th>
                    <th>Logged in</th>
                    <th>Active</th>
                    <th>Active now</th>
                    <th>Active time</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_role.map((row) => (
                    <tr key={row.role}>
                      <td>{roleLabel(row.role)}</td>
                      <td>{row.unique_logins ?? 0}</td>
                      <td>{row.unique_active ?? 0}</td>
                      <td>
                        {row.active_now ? (
                          <span className="admin-platform-stats__live">{row.active_now}</span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td>{formatDuration(row.active_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <AdminEmptyState
              title="No role activity in this period"
              description="Try a wider date range or check back after more sign-ins."
            />
          )}
        </AdminPanel>
      </div>

      <AdminPanel
        title="Recent activity"
        className="admin-platform-stats__panel admin-platform-stats__panel--wide"
        actions={
          activity?.total != null ? (
            <span className="admin-muted admin-platform-stats__activity-count">
              {activity.total} {activity.total === 1 ? 'user' : 'users'}
            </span>
          ) : null
        }
      >
        <div className="admin-platform-stats__activity-toolbar">
          <label className="admin-platform-stats__search">
            <span className="admin-platform-stats__search-label">Search</span>
            <input
              type="search"
              className="admin-input"
              placeholder="Name or email"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search activity by name or email"
            />
          </label>

          <div className="admin-platform-stats__status-filters" role="group" aria-label="Activity status">
            {STATUS_FILTERS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`admin-btn admin-btn--sm admin-btn--secondary admin-platform-stats__filter-btn${
                  statusFilter === opt.value ? ' is-active' : ''
                }`}
                onClick={() => {
                  setStatusFilter(opt.value)
                  resetActivityPage()
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <label className="admin-platform-stats__select-wrap">
            <span className="admin-platform-stats__search-label">Role</span>
            <select
              className="admin-input admin-platform-stats__select"
              value={roleFilter}
              onChange={(e) => {
                setRoleFilter(e.target.value)
                resetActivityPage()
              }}
              aria-label="Filter by role"
            >
              {ROLE_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>

          <label className="admin-platform-stats__select-wrap">
            <span className="admin-platform-stats__search-label">Portal</span>
            <select
              className="admin-input admin-platform-stats__select"
              value={portalFilter}
              onChange={(e) => {
                setPortalFilter(e.target.value)
                resetActivityPage()
              }}
              aria-label="Filter by portal"
            >
              {PORTAL_FILTER_OPTIONS.map((opt) => (
                <option key={opt.value || 'all'} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {activityError ? (
          <p className="admin-alert admin-alert--error" role="alert">
            {activityError}
          </p>
        ) : null}

        {activityLoading && !activity ? (
          <div className="admin-skeleton admin-platform-stats__skeleton admin-platform-stats__skeleton--tall" />
        ) : activityRows.length > 0 ? (
          <>
            <div className="admin-table-wrap">
              <table className="admin-table admin-platform-stats__table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Role</th>
                    <th>Portals</th>
                    <th>Last activity</th>
                    <th>Logins</th>
                    <th>Active time</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {activityRows.map((row) => (
                    <tr key={row.user_id}>
                      <td>
                        <div className="admin-platform-stats__user-cell">
                          <span className="admin-platform-stats__user-name">{row.user_name || '—'}</span>
                          {row.user_email ? (
                            <span className="admin-muted admin-platform-stats__user-email">{row.user_email}</span>
                          ) : null}
                        </div>
                      </td>
                      <td>{roleLabel(row.primary_role)}</td>
                      <td>
                        {row.portals?.length
                          ? row.portals.map((p) => portalLabel(p)).join(', ')
                          : '—'}
                      </td>
                      <td>{formatWhen(row.last_activity_at)}</td>
                      <td>{row.login_count ?? 0}</td>
                      <td>{formatDuration(row.active_seconds)}</td>
                      <td>
                        {row.active_now ? (
                          <span className="admin-platform-stats__badge admin-platform-stats__badge--live">
                            Active now
                          </span>
                        ) : row.logged_in_period ? (
                          <span className="admin-platform-stats__badge">Logged in</span>
                        ) : (
                          <span className="admin-muted">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PeopleListPagination
              page={activity?.page ?? 1}
              totalPages={activity?.total_pages ?? 0}
              total={activity?.total ?? 0}
              rangeStart={activity?.range_start ?? 0}
              rangeEnd={activity?.range_end ?? 0}
              onPageChange={setActivityPage}
            />
          </>
        ) : hasActiveFilters || (activity && activity.total === 0) ? (
          <AdminEmptyState
            title="No users match these filters"
            description="Try clearing search or choosing a different status filter."
          />
        ) : (
          <AdminEmptyState
            title="No recent activity"
            description="Sign-ins and usage heartbeats for this period will show up here."
          />
        )}
      </AdminPanel>

      <p className="admin-muted admin-platform-stats__footer">
        Period: {formatWhen(stats?.period?.start_at)} → {formatWhen(stats?.period?.end_at)} ({stats?.timezone || 'IST'}).
        {' '}
        <Link to="/admin/hr-reports">HR Reports</Link> includes parent portal login status by case.
      </p>
    </div>
  )
}
