import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area,
} from 'recharts'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, StatusBadge } from './ui/index.js'
import './admin-sessions-dashboard.css'

const STATUS_COLORS = {
  COMPLETED:       '#10b981',
  SCHEDULED:       '#6366f1',
  IN_PROGRESS:     '#3b82f6',
  CANCELLED:       '#ef4444',
  NO_SHOW:         '#f59e0b',
  RESCHEDULED:     '#8b5cf6',
  CLIENT_ABSENT:   '#f97316',
  THERAPIST_LEAVE: '#94a3b8',
}

const PIE_PALETTE = ['#6366f1', '#10b981', '#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#f97316']

const FLAG_REASONS = [
  'Session cancelled without notice',
  'Therapist no-show',
  'Client no-show — follow up needed',
  'Late cancellation',
  'Repeated cancellations',
  'Quality concern',
  'Other',
]

function fmt(d) {
  if (!d) return '—'
  const dt = new Date(d)
  return dt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true })
}

function fmtDate(s) {
  if (!s) return '—'
  const [y, m, d] = s.split('-')
  return `${d}/${m}/${String(y).slice(2)}`
}

function toISODate(d) {
  return d.toISOString().slice(0, 10)
}

function buildUrl(filters) {
  const p = new URLSearchParams()
  if (filters.dateFrom)      p.set('date_from', filters.dateFrom)
  if (filters.dateTo)        p.set('date_to', filters.dateTo)
  if (filters.therapistId)   p.set('therapist_id', filters.therapistId)
  if (filters.productModule) p.set('product_module', filters.productModule)
  if (filters.status)        p.set('status', filters.status)
  return `/api/v1/admin/sessions/analytics?${p}`
}

// ── KPI card ────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, accent }) {
  return (
    <div className={`sessions-dash__kpi sessions-dash__kpi--${accent}`}>
      <p className="sessions-dash__kpi-label">{label}</p>
      <p className="sessions-dash__kpi-value">{value ?? 0}</p>
      {sub ? <p className="sessions-dash__kpi-sub">{sub}</p> : null}
    </div>
  )
}

// ── Custom tooltip ───────────────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div style={{ background: '#1e293b', borderRadius: 10, padding: '8px 12px', fontSize: '0.8rem', color: '#f1f5f9', lineHeight: 1.6 }}>
      <p style={{ fontWeight: 700, marginBottom: 4 }}>{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value}
        </p>
      ))}
    </div>
  )
}

// ── Flag drawer ──────────────────────────────────────────────────────────────
function FlagDrawer({ session, onClose, onDone }) {
  const [reason, setReason] = useState(FLAG_REASONS[0])
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [ticketId, setTicketId] = useState(null)
  const [err, setErr] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setErr('')
    try {
      const res = await apiFetch(`/api/v1/admin/sessions/${session.id}/flag`, {
        method: 'POST',
        body: JSON.stringify({ reason, notes }),
      })
      setTicketId(res.ticket_id)
      onDone?.()
    } catch (ex) {
      setErr(ex.message || 'Failed to create ticket')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="sessions-dash__overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="sessions-dash__flag-drawer">
        <h3 className="sessions-dash__drawer-title">Flag session for review</h3>
        <p className="sessions-dash__drawer-meta">
          Session #{session.id} · {fmtDate(session.scheduled_date)} · {session.child_name || 'Unknown client'}
          {session.therapist_name ? ` · ${session.therapist_name}` : ''}
        </p>

        {ticketId ? (
          <>
            <div className="sessions-dash__success-banner">
              Ticket #{ticketId} created and assigned to the therapist.
            </div>
            <div className="sessions-dash__drawer-actions">
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={onClose}>
                Close
              </button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="sessions-dash__drawer-field" style={{ marginBottom: 12 }}>
              <label htmlFor="flag-reason">Reason</label>
              <select id="flag-reason" value={reason} onChange={(e) => setReason(e.target.value)}>
                {FLAG_REASONS.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </div>
            <div className="sessions-dash__drawer-field" style={{ marginBottom: 16 }}>
              <label htmlFor="flag-notes">Additional notes (optional)</label>
              <textarea
                id="flag-notes"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder="Describe the issue or context for the therapist…"
              />
            </div>
            {err ? <p style={{ color: '#b91c1c', fontSize: '0.8rem', marginBottom: 8 }}>{err}</p> : null}
            <div className="sessions-dash__drawer-actions">
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onClose}>
                Cancel
              </button>
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={submitting}>
                {submitting ? 'Creating ticket…' : 'Create review ticket'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}

// ── Overview tab ─────────────────────────────────────────────────────────────
function OverviewTab({ data }) {
  const { status_counts = {}, by_therapist = [], by_product = [], by_day = [], by_month = [] } = data

  const completed  = status_counts.COMPLETED  || 0
  const cancelled  = status_counts.CANCELLED  || 0
  const no_show    = status_counts.NO_SHOW    || 0
  const scheduled  = status_counts.SCHEDULED  || 0

  const pieData = Object.entries(status_counts)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => ({ name: k, value: v }))

  const dayData = by_day.map((d) => ({
    date: fmtDate(d.date),
    Completed: d.completed,
    Cancelled: d.cancelled,
    Other: d.total - d.completed - d.cancelled,
  }))

  const therapistData = by_therapist.slice(0, 10).map((t) => ({
    name: t.name.split(' ')[0],
    fullName: t.name,
    Completed: t.completed,
    Cancelled: t.cancelled,
    Scheduled: t.scheduled,
  }))

  const monthData = by_month.map((m) => ({
    month: m.month,
    Total: m.total,
    Completed: m.completed,
    Cancelled: m.cancelled,
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Status summary pill row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {Object.entries(status_counts).map(([k, v]) => (
          <div key={k} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: '#f8fafc', border: '1px solid #e2e8f0',
            borderRadius: 999, padding: '4px 12px',
            fontSize: '0.78rem', fontWeight: 600,
          }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: STATUS_COLORS[k] || '#94a3b8', flexShrink: 0,
            }} />
            {k.replaceAll('_', ' ')}: {v}
          </div>
        ))}
      </div>

      {/* Sessions over time */}
      <div className="sessions-dash__chart-card sessions-dash__chart-card--full">
        <p className="sessions-dash__chart-title">Sessions over time (last 30 days)</p>
        {dayData.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '0.8rem', padding: '20px 0' }}>No session data in this range.</p>
        ) : (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={dayData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '0.75rem' }} />
              <Bar dataKey="Completed" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Cancelled" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
              <Bar dataKey="Other"     stackId="a" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="sessions-dash__chart-grid">
        {/* By therapist */}
        <div className="sessions-dash__chart-card">
          <p className="sessions-dash__chart-title">By therapist (top 10)</p>
          {therapistData.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '0.8rem', padding: '20px 0' }}>No data.</p>
          ) : (
            <ResponsiveContainer width="100%" height={Math.max(180, therapistData.length * 36)}>
              <BarChart data={therapistData} layout="vertical" margin={{ top: 0, right: 12, left: 4, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 11, fill: '#475569' }}
                  tickLine={false}
                  axisLine={false}
                  width={60}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '0.75rem' }} />
                <Bar dataKey="Completed" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Scheduled" stackId="a" fill="#6366f1" radius={[0, 0, 0, 0]} />
                <Bar dataKey="Cancelled" stackId="a" fill="#ef4444" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* By product module */}
        <div className="sessions-dash__chart-card">
          <p className="sessions-dash__chart-title">By product module</p>
          {pieData.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: '0.8rem', padding: '20px 0' }}>No data.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={70}
                    innerRadius={36}
                  >
                    {pieData.map((entry, idx) => (
                      <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || PIE_PALETTE[idx % PIE_PALETTE.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<ChartTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              {/* Product breakdown legend */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {by_product.map((p, idx) => (
                  <div key={p.module} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.78rem' }}>
                    <span style={{ width: 10, height: 10, borderRadius: '50%', background: PIE_PALETTE[idx % PIE_PALETTE.length], flexShrink: 0 }} />
                    <span style={{ flex: 1, color: '#475569', fontWeight: 500 }}>{p.module}</span>
                    <span style={{ color: '#0f172a', fontWeight: 700 }}>{p.total}</span>
                    <span style={{ color: '#94a3b8' }}>({p.completed} done)</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Monthly trend */}
      <div className="sessions-dash__chart-card sessions-dash__chart-card--full">
        <p className="sessions-dash__chart-title">Monthly trend (12 months)</p>
        {monthData.length === 0 ? (
          <p style={{ color: '#94a3b8', fontSize: '0.8rem', padding: '20px 0' }}>No monthly data yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={monthData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="gradTotal" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradCompleted" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%"  stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickLine={false} axisLine={false} />
              <Tooltip content={<ChartTooltip />} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: '0.75rem' }} />
              <Area type="monotone" dataKey="Total"     stroke="#6366f1" fill="url(#gradTotal)"     strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="Completed" stroke="#10b981" fill="url(#gradCompleted)" strokeWidth={2} dot={false} />
              <Area type="monotone" dataKey="Cancelled" stroke="#ef4444" fill="none"                strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  )
}

// ── Sessions table tab ────────────────────────────────────────────────────────
function SessionsTab({ sessions, filters, onRefresh }) {
  const [flagSession, setFlagSession] = useState(null)
  const [tableSearch, setTableSearch] = useState('')

  const filtered = useMemo(() => {
    const q = tableSearch.trim().toLowerCase()
    if (!q) return sessions
    return sessions.filter((s) =>
      s.case_code?.toLowerCase().includes(q) ||
      s.child_name?.toLowerCase().includes(q) ||
      s.therapist_name?.toLowerCase().includes(q) ||
      s.product_module?.toLowerCase().includes(q) ||
      s.status?.toLowerCase().includes(q)
    )
  }, [sessions, tableSearch])

  function downloadFile(endpoint) {
    const p = new URLSearchParams()
    if (filters.dateFrom)      p.set('date_from', filters.dateFrom)
    if (filters.dateTo)        p.set('date_to', filters.dateTo)
    if (filters.therapistId)   p.set('therapist_id', filters.therapistId)
    if (filters.productModule) p.set('product_module', filters.productModule)
    if (filters.status)        p.set('status', filters.status)
    const url = `/api/v1/admin/sessions/export/${endpoint}?${p}`
    const a = document.createElement('a')
    a.href = url
    a.download = ''
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  return (
    <>
      <div className="sessions-dash__export-bar">
        <input
          type="search"
          className="sessions-dash__filter-input"
          style={{ width: 220 }}
          value={tableSearch}
          onChange={(e) => setTableSearch(e.target.value)}
          placeholder="Search table…"
        />
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadFile('xlsx')}>
          ↓ Excel
        </button>
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => downloadFile('pdf')}>
          ↓ PDF
        </button>
      </div>

      {filtered.length === 0 ? (
        <div style={{ padding: '32px 0', textAlign: 'center', color: '#94a3b8', fontSize: '0.875rem' }}>
          No sessions found for this filter.
        </div>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Time</th>
                <th>Case</th>
                <th>Child</th>
                <th>Therapist</th>
                <th>Module</th>
                <th>Mode</th>
                <th>Duration</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => {
                const startDisplay = s.actual_start_at ? fmt(s.actual_start_at) : (s.start_time ? s.start_time.slice(0, 5) : '—')
                const endDisplay   = s.actual_end_at   ? fmt(s.actual_end_at)   : (s.end_time   ? s.end_time.slice(0, 5)   : '—')
                const isLate = s.actual_start_at && s.start_time &&
                  new Date(s.actual_start_at).toISOString().slice(11, 16) > s.start_time.slice(0, 5)
                const canFlag = s.status === 'CANCELLED' || s.status === 'NO_SHOW' || s.status === 'CLIENT_ABSENT'
                return (
                  <tr key={s.id}>
                    <td>
                      <span className="admin-table__primary">{fmtDate(s.scheduled_date)}</span>
                    </td>
                    <td>
                      <span style={{ fontSize: '0.8rem' }}>
                        {startDisplay}
                        {endDisplay !== '—' ? <> – {endDisplay}</> : null}
                        {isLate ? (
                          <span className="admin-badge admin-badge--warning" style={{ marginLeft: 4, fontSize: '0.7rem' }}>Late start</span>
                        ) : null}
                      </span>
                    </td>
                    <td>
                      {s.case_id ? (
                        <Link to={`/admin/cases/${s.case_id}?tab=logs`} className="admin-table__primary">
                          {s.case_code || `Case #${s.case_id}`}
                        </Link>
                      ) : '—'}
                    </td>
                    <td>{s.child_name || '—'}</td>
                    <td>
                      <span className="admin-table__primary" style={{ fontWeight: 500 }}>
                        {s.therapist_name || `#${s.therapist_id}`}
                      </span>
                    </td>
                    <td>
                      {s.product_module ? (
                        <span className="admin-chip">{s.product_module}</span>
                      ) : '—'}
                    </td>
                    <td>
                      <span style={{ fontSize: '0.78rem', color: '#64748b', textTransform: 'capitalize' }}>
                        {s.mode?.toLowerCase() || '—'}
                      </span>
                    </td>
                    <td>
                      {s.duration_mins != null ? (
                        <span style={{ fontSize: '0.8rem', color: '#475569' }}>
                          {s.duration_mins >= 60
                            ? `${Math.floor(s.duration_mins / 60)}h${s.duration_mins % 60 > 0 ? ` ${s.duration_mins % 60}m` : ''}`
                            : `${s.duration_mins}m`}
                          {s.actual_start_at ? (
                            <span className="admin-badge admin-badge--success" style={{ marginLeft: 4, fontSize: '0.68rem' }}>actual</span>
                          ) : null}
                        </span>
                      ) : '—'}
                    </td>
                    <td>
                      <StatusBadge status={s.status} />
                    </td>
                    <td>
                      <div className="admin-table__actions">
                        {s.case_id ? (
                          <Link to={`/admin/cases/${s.case_id}?tab=logs`} className="admin-btn admin-btn--ghost admin-btn--sm">
                            View
                          </Link>
                        ) : null}
                        {canFlag ? (
                          <button
                            type="button"
                            className="admin-btn admin-btn--sm"
                            style={{ background: '#fff1f2', color: '#b91c1c', border: '1px solid #fecaca' }}
                            onClick={() => setFlagSession(s)}
                          >
                            Flag
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {flagSession ? (
        <FlagDrawer
          session={flagSession}
          onClose={() => setFlagSession(null)}
          onDone={() => { onRefresh?.(); }}
        />
      ) : null}
    </>
  )
}

// ── Main dashboard ────────────────────────────────────────────────────────────
export function AdminSessionLogsPage() {
  const today = new Date()
  const thirtyDaysAgo = new Date(today)
  thirtyDaysAgo.setDate(today.getDate() - 29)

  const [filters, setFilters] = useState({
    dateFrom: toISODate(thirtyDaysAgo),
    dateTo:   toISODate(today),
    therapistId: '',
    productModule: '',
    status: '',
  })
  const [activeTab, setActiveTab] = useState('overview')
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [therapists, setTherapists] = useState([])
  const [modules, setModules]   = useState([])

  const loadAnalytics = useCallback(() => {
    setLoading(true)
    apiFetch(buildUrl(filters))
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [filters])

  useEffect(() => {
    loadAnalytics()
  }, [loadAnalytics])

  useEffect(() => {
    apiFetch('/api/v1/admin/allotment/therapists')
      .then((rows) => {
        if (Array.isArray(rows)) setTherapists(rows)
        else if (Array.isArray(rows?.items)) setTherapists(rows.items)
      })
      .catch(() => {})
    apiFetch('/api/v1/admin/modules')
      .then((res) => {
        if (Array.isArray(res?.modules)) {
          setModules(res.modules.map((m) => m.key || m.id || m))
        }
      })
      .catch(() => {})
  }, [])

  function setFilter(key, val) {
    setFilters((prev) => ({ ...prev, [key]: val }))
  }

  const sc = data?.status_counts || {}
  const totalInRange = Object.values(sc).reduce((a, b) => a + b, 0)

  return (
    <div className="admin-page sessions-dash">
      <AdminPageHeader
        eyebrow="Clinical ops"
        title="Sessions analytics"
        subtitle="Live analytics across all sessions — by therapist, product, status, and time."
      />

      {/* Filter bar */}
      <div className="sessions-dash__filters">
        <span className="sessions-dash__filter-label">Range</span>
        <input
          type="date"
          className="sessions-dash__filter-input"
          value={filters.dateFrom}
          onChange={(e) => setFilter('dateFrom', e.target.value)}
        />
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>to</span>
        <input
          type="date"
          className="sessions-dash__filter-input"
          value={filters.dateTo}
          onChange={(e) => setFilter('dateTo', e.target.value)}
        />

        <span className="sessions-dash__filter-label" style={{ marginLeft: 8 }}>Therapist</span>
        <select
          className="sessions-dash__filter-input"
          style={{ width: 160 }}
          value={filters.therapistId}
          onChange={(e) => setFilter('therapistId', e.target.value)}
        >
          <option value="">All therapists</option>
          {therapists.map((t) => (
            <option key={t.therapist_user_id || t.id} value={t.therapist_user_id || t.id}>
              {t.therapist_name || t.full_name || `#${t.therapist_user_id || t.id}`}
            </option>
          ))}
        </select>

        {modules.length > 0 ? (
          <>
            <span className="sessions-dash__filter-label">Module</span>
            <select
              className="sessions-dash__filter-input"
              style={{ width: 140 }}
              value={filters.productModule}
              onChange={(e) => setFilter('productModule', e.target.value)}
            >
              <option value="">All modules</option>
              {modules.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </>
        ) : null}

        <span className="sessions-dash__filter-label">Status</span>
        <select
          className="sessions-dash__filter-input"
          style={{ width: 150 }}
          value={filters.status}
          onChange={(e) => setFilter('status', e.target.value)}
        >
          <option value="">All statuses</option>
          {['SCHEDULED','IN_PROGRESS','COMPLETED','CANCELLED','NO_SHOW','RESCHEDULED','CLIENT_ABSENT','THERAPIST_LEAVE'].map((s) => (
            <option key={s} value={s}>{s.replaceAll('_', ' ')}</option>
          ))}
        </select>
      </div>

      {/* KPI row */}
      <div className="sessions-dash__kpi-grid">
        <KpiCard label="Today's sessions" value={data?.today_count} sub="scheduled for today" accent="indigo" />
        <KpiCard label="This week"         value={data?.week_count}  sub="sessions this week"  accent="blue"   />
        <KpiCard label="Completed"         value={sc.COMPLETED}      sub={`of ${totalInRange} in range`} accent="green"  />
        <KpiCard label="Cancelled"         value={(sc.CANCELLED || 0) + (sc.CLIENT_ABSENT || 0)} sub="+ client absent" accent="red"    />
        <KpiCard label="No-shows"          value={sc.NO_SHOW}        sub="therapist no-shows"  accent="amber"  />
      </div>

      {/* Tabs */}
      <div>
        <div className="sessions-dash__tabs">
          <button
            type="button"
            className={`sessions-dash__tab ${activeTab === 'overview' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            type="button"
            className={`sessions-dash__tab ${activeTab === 'sessions' ? 'is-active' : ''}`}
            onClick={() => setActiveTab('sessions')}
          >
            Sessions ({data?.recent_sessions?.length ?? 0})
          </button>
        </div>

        <div style={{ paddingTop: 20 }}>
          {loading ? (
            <div className="sessions-dash__skeleton" />
          ) : !data ? (
            <p style={{ color: '#94a3b8', fontSize: '0.875rem', padding: '24px 0' }}>
              Could not load analytics. Make sure the server is running.
            </p>
          ) : activeTab === 'overview' ? (
            <OverviewTab data={data} />
          ) : (
            <SessionsTab
              sessions={data.recent_sessions || []}
              filters={filters}
              onRefresh={loadAnalytics}
            />
          )}
        </div>
      </div>
    </div>
  )
}
