import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState } from './ui/index.js'
import { AdminOpsKpiGrid } from './AdminOpsKpiGrid.jsx'
import './admin-platform-stats.css'

const PERIOD_OPTIONS = [
  { value: 1, label: 'Today' },
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
]

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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

  useEffect(() => {
    if (!can('admin.override')) {
      setLoading(false)
      return undefined
    }
    loadStats()
    const timer = window.setInterval(loadStats, 60_000)
    return () => window.clearInterval(timer)
  }, [can, loadStats])

  const kpis = useMemo(() => buildKpis(stats), [stats])

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
                  onClick={() => setDays(opt.value)}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              className="admin-btn admin-btn--secondary"
              onClick={() => loadStats()}
              disabled={loading}
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

      <AdminPanel title="Recent activity" className="admin-platform-stats__panel admin-platform-stats__panel--wide">
        {loading && !stats ? (
          <div className="admin-skeleton admin-platform-stats__skeleton admin-platform-stats__skeleton--tall" />
        ) : stats?.recent_users?.length ? (
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
                {stats.recent_users.map((row) => (
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
