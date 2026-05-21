import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiFetch } from '../../lib/apiClient.js'
import './therapist-leave.css'

const LEAVE_TYPES = ['ANNUAL', 'SICK', 'CASUAL', 'UNPAID']
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAYS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

const STATUS_COLORS = {
  PENDING: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  APPROVED: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  REJECTED: { bg: '#fef2f2', color: '#b91c1c', border: '#fca5a5' },
  CANCELLED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

const TYPE_COLORS = {
  ANNUAL: '#dbeafe',
  SICK: '#fce7f3',
  CASUAL: '#d1fae5',
  UNPAID: '#fde8d8',
}

function daysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

function pad2(n) {
  return String(n).padStart(2, '0')
}

function toDateStr(year, month, day) {
  return `${year}-${pad2(month + 1)}-${pad2(day)}`
}

function leaveOnDate(dateStr, leaves) {
  return leaves.find((l) => l.status !== 'CANCELLED' && dateStr >= l.start_date && dateStr <= l.end_date)
}

/** Role for start→end selection highlight (red range). */
function pickRangeRole(dateStr, rangeStart, rangeEnd) {
  if (!rangeStart) return null
  if (!rangeEnd || rangeEnd < rangeStart) {
    return dateStr === rangeStart ? 'single' : null
  }
  if (dateStr < rangeStart || dateStr > rangeEnd) return null
  if (rangeStart === rangeEnd) return 'single'
  if (dateStr === rangeStart) return 'start'
  if (dateStr === rangeEnd) return 'end'
  return 'middle'
}

function dayClassName(dateStr, leaves, isToday, rangeRole) {
  const entry = leaveOnDate(dateStr, leaves)
  if (rangeRole) {
    return `leave-cal__day leave-cal__day--range-${rangeRole}`
  }
  if (entry?.status === 'APPROVED') return 'leave-cal__day leave-cal__day--approved'
  if (entry?.status === 'PENDING') return 'leave-cal__day leave-cal__day--pending'
  if (entry?.status === 'REJECTED') return 'leave-cal__day leave-cal__day--rejected'
  if (isToday) return 'leave-cal__day leave-cal__day--today'
  return 'leave-cal__day'
}

export function TherapistLeavePage() {
  const { user, loading: authLoading } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const now = useMemo(() => new Date(), [])

  const [viewTab, setViewTab] = useState('month')
  const [calYear, setCalYear] = useState(now.getFullYear())
  const [calMonth, setCalMonth] = useState(now.getMonth())
  const [leaves, setLeaves] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ leave_type: 'ANNUAL', start_date: '', end_date: '', reason: '' })
  const [pickStart, setPickStart] = useState(null)
  const [pickEnd, setPickEnd] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const loadLeaves = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      const [data, sum] = await Promise.all([
        apiFetch('/api/v1/leave'),
        apiFetch(`/api/v1/leave/summary?year=${calYear}`),
      ])
      setLeaves(Array.isArray(data) ? data : [])
      setSummary(sum)
    } catch (err) {
      setLeaves([])
      setSummary(null)
      setLoadError(err.message || 'Could not load leave requests')
    } finally {
      setLoading(false)
    }
  }, [calYear])

  useEffect(() => {
    if (authLoading || !user) return
    loadLeaves()
  }, [authLoading, user, loadLeaves])

  useEffect(() => {
    if (searchParams.get('new') === '1') {
      setShowForm(true)
      searchParams.delete('new')
      setSearchParams(searchParams, { replace: true })
    }
  }, [searchParams, setSearchParams])

  function openRequestForm(start, end) {
    const from = start || form.start_date
    const to = end || start || form.end_date
    setForm((f) => ({
      ...f,
      start_date: from,
      end_date: to,
    }))
    if (from) setPickStart(from)
    if (to) setPickEnd(to)
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  function clearPickRange() {
    setPickStart(null)
    setPickEnd(null)
  }

  function handleDayClick(day) {
    const ds = toDateStr(calYear, calMonth, day)
    if (!pickStart || (pickStart && pickEnd)) {
      setPickStart(ds)
      setPickEnd(null)
      setForm((f) => ({ ...f, start_date: ds, end_date: '' }))
      setShowForm(true)
      setError('')
      setSuccess('')
      return
    }
    if (ds < pickStart) {
      setPickStart(ds)
      setPickEnd(pickStart)
      setForm((f) => ({ ...f, start_date: ds, end_date: pickStart }))
    } else {
      setPickEnd(ds)
      setForm((f) => ({ ...f, start_date: pickStart, end_date: ds }))
    }
    setShowForm(true)
    setError('')
    setSuccess('')
  }

  function syncRangeFromForm(start, end) {
    if (!start) {
      clearPickRange()
      return
    }
    setPickStart(start)
    setPickEnd(end && end >= start ? end : start)
  }

  async function submitLeave(e) {
    e.preventDefault()
    setSubmitting(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch('/api/v1/leave', {
        method: 'POST',
        body: JSON.stringify({
          leave_type: form.leave_type,
          start_date: form.start_date,
          end_date: form.end_date,
          reason: form.reason || null,
        }),
      })
      setForm({ leave_type: 'ANNUAL', start_date: '', end_date: '', reason: '' })
      setShowForm(false)
      clearPickRange()
      setSuccess('Leave request submitted.')
      await loadLeaves()
    } catch (err) {
      setError(err.message || 'Could not submit leave')
    } finally {
      setSubmitting(false)
    }
  }

  async function cancelLeave(id) {
    try {
      await apiFetch(`/api/v1/leave/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'CANCELLED' }),
      })
      await loadLeaves()
    } catch (err) {
      setError(err.message || 'Could not cancel leave')
    }
  }

  const firstDay = new Date(calYear, calMonth, 1).getDay()
  const totalDays = daysInMonth(calYear, calMonth)
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= totalDays; d++) cells.push(d)

  const todayStr = toDateStr(now.getFullYear(), now.getMonth(), now.getDate())

  const pendingCount = summary?.pending_count ?? leaves.filter((l) => l.status === 'PENDING').length
  const rejectedCount = summary?.rejected_count ?? leaves.filter((l) => l.status === 'REJECTED').length
  const approvedDaysYtd = summary?.approved_days ?? 0
  const daysByType = summary?.days_by_type ?? {}

  const monthLeaves = leaves.filter(
    (l) =>
      l.status !== 'CANCELLED' &&
      l.start_date <= toDateStr(calYear, calMonth, totalDays) &&
      l.end_date >= toDateStr(calYear, calMonth, 1),
  )

  const rangeStart = pickStart || (showForm ? form.start_date : null) || null
  const rangeEnd =
    pickEnd ||
    (showForm && form.end_date && form.start_date && form.end_date >= form.start_date ? form.end_date : null)
  const isSelectingRange = Boolean(rangeStart)
  const awaitingEndDate = Boolean(pickStart && !pickEnd)

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '2rem 1rem' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, gap: 12, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
            Leave management
          </p>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>My Leave</h1>
          <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
            Click dates on the calendar to request leave, or use the button below.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            const next = !showForm
            setShowForm(next)
            if (!next) clearPickRange()
            setError('')
            setSuccess('')
          }}
          style={{
            padding: '8px 18px',
            background: '#6366f1',
            color: '#fff',
            border: 'none',
            borderRadius: 8,
            fontWeight: 600,
            fontSize: '0.875rem',
            cursor: 'pointer',
          }}
        >
          {showForm ? 'Close form' : '+ Request leave'}
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <label style={{ fontSize: '0.8rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: 6 }}>
          Year
          <select
            value={calYear}
            onChange={(e) => setCalYear(Number(e.target.value))}
            style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
          >
            {[now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1].map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          {[
            ['month', 'Month calendar'],
            ['year', 'Year at a glance'],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setViewTab(id)}
              style={{
                padding: '6px 14px',
                borderRadius: 20,
                fontSize: '0.8rem',
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                background: viewTab === id ? '#6366f1' : '#f3f4f6',
                color: viewTab === id ? '#fff' : '#374151',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12, marginBottom: 20 }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px' }}>
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Approved days ({calYear})</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#15803d' }}>{loading ? '…' : approvedDaysYtd}</p>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px' }}>
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Pending</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#a16207' }}>{loading ? '…' : pendingCount}</p>
        </div>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '16px 20px' }}>
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 4 }}>Rejected ({calYear})</p>
          <p style={{ fontSize: '1.5rem', fontWeight: 700, color: '#b91c1c' }}>{loading ? '…' : rejectedCount}</p>
        </div>
      </div>
      {Object.keys(daysByType).length > 0 ? (
        <p style={{ fontSize: '0.8rem', color: '#6b7280', margin: '-8px 0 16px' }}>
          By type:{' '}
          {Object.entries(daysByType)
            .map(([t, d]) => `${t} ${d}d`)
            .join(' · ')}
        </p>
      ) : null}

      {loadError ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>
          {loadError}
          <button type="button" onClick={loadLeaves} style={{ marginLeft: 12, textDecoration: 'underline', background: 'none', border: 'none', cursor: 'pointer', color: '#b91c1c' }}>
            Retry
          </button>
        </div>
      ) : null}
      {error ? (
        <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</div>
      ) : null}
      {success ? (
        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '10px 14px', marginBottom: 16, color: '#15803d', fontSize: '0.875rem' }}>{success}</div>
      ) : null}

      {viewTab === 'year' ? (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <p style={{ fontWeight: 600, margin: '0 0 16px' }}>{calYear} — year at a glance</p>
          <div className="leave-year-grid">
            {MONTHS.map((monthName, monthIdx) => {
              const days = daysInMonth(calYear, monthIdx)
              const miniCells = []
              const fd = new Date(calYear, monthIdx, 1).getDay()
              for (let i = 0; i < fd; i++) miniCells.push(null)
              for (let d = 1; d <= days; d++) miniCells.push(d)
              return (
                <div key={monthName} className="leave-year-month">
                  <p className="leave-year-month__title">{monthName.slice(0, 3)}</p>
                  <div className="leave-year-month__grid">
                    {miniCells.map((day, i) => {
                      if (!day) return <span key={`e-${i}`} className="leave-year-day leave-year-day--empty" />
                      const ds = toDateStr(calYear, monthIdx, day)
                      const entry = leaveOnDate(ds, leaves)
                      let cls = 'leave-year-day'
                      if (entry?.status === 'APPROVED') cls += ' leave-year-day--approved'
                      else if (entry?.status === 'PENDING') cls += ' leave-year-day--pending'
                      else if (entry?.status === 'REJECTED') cls += ' leave-year-day--rejected'
                      return <span key={ds} className={cls} title={entry ? `${entry.leave_type} (${entry.status})` : ''} />
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : (
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <button
            type="button"
            onClick={() => {
              if (calMonth === 0) {
                setCalYear(calYear - 1)
                setCalMonth(11)
              } else setCalMonth(calMonth - 1)
            }}
            aria-label="Previous month"
            style={{ background: '#f9fafb', border: '1px solid #d1d5db', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '1rem' }}
          >
            ‹
          </button>
          <p style={{ fontWeight: 600, flex: 1, textAlign: 'center', margin: 0 }}>
            {MONTHS[calMonth]} {calYear}
          </p>
          <button
            type="button"
            onClick={() => {
              if (calMonth === 11) {
                setCalYear(calYear + 1)
                setCalMonth(0)
              } else setCalMonth(calMonth + 1)
            }}
            aria-label="Next month"
            style={{ background: '#f9fafb', border: '1px solid #d1d5db', borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: '1rem' }}
          >
            ›
          </button>
        </div>
        <p
          className={isSelectingRange ? 'leave-cal__hint--selecting' : ''}
          style={{ fontSize: '0.75rem', color: isSelectingRange ? undefined : '#6b7280', textAlign: 'center', marginBottom: 16 }}
        >
          {awaitingEndDate
            ? `Start: ${pickStart} — click end date (range shown in red)`
            : rangeStart && rangeEnd
              ? `Selected: ${rangeStart} → ${rangeEnd}`
              : 'Click a start date, then an end date — your range appears in red'}
        </p>

        <div className="leave-cal">
          {WEEKDAYS.map((d) => (
            <div key={d} className="leave-cal__weekday">
              {d}
            </div>
          ))}
          {cells.map((day, i) => {
            if (!day) {
              return <div key={`empty-${i}`} style={{ minHeight: 36 }} aria-hidden />
            }
            const ds = toDateStr(calYear, calMonth, day)
            const entry = leaveOnDate(ds, leaves)
            const rangeRole = pickRangeRole(ds, rangeStart, rangeEnd)
            const className = dayClassName(ds, leaves, ds === todayStr, rangeRole)
            return (
              <button
                key={ds}
                type="button"
                onClick={() => handleDayClick(day)}
                className={className}
                title={entry ? `${entry.leave_type} (${entry.status})` : 'Select for leave request'}
              >
                {day}
              </button>
            )
          })}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, marginTop: 16, fontSize: '0.75rem', color: '#6b7280' }}>
          <span>
            <span className="leave-cal__legend-swatch--selecting" style={{ display: 'inline-block', width: 10, height: 10, borderRadius: 2, marginRight: 4 }} />
            Selecting range
          </span>
          <span>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: '#bbf7d0', borderRadius: 2, marginRight: 4 }} />
            Approved
          </span>
          <span>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: '#fef9c3', borderRadius: 2, marginRight: 4 }} />
            Pending
          </span>
          <span>
            <span style={{ display: 'inline-block', width: 10, height: 10, background: '#fee2e2', borderRadius: 2, marginRight: 4 }} />
            Rejected
          </span>
        </div>

        {!loading && monthLeaves.length === 0 ? (
          <p style={{ marginTop: 16, marginBottom: 0, fontSize: '0.875rem', color: '#6b7280', textAlign: 'center' }}>
            No leave this month. Click dates above or{' '}
            <button type="button" onClick={() => openRequestForm()} style={{ color: '#6366f1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
              request leave
            </button>
            .
          </p>
        ) : null}
      </div>
      )}

      {showForm ? (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: 24, marginBottom: 20 }}>
          <p style={{ fontWeight: 600, marginBottom: 16 }}>New leave request</p>
          <form onSubmit={submitLeave} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Leave type
              <select
                value={form.leave_type}
                onChange={(e) => setForm({ ...form, leave_type: e.target.value })}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
              >
                {LEAVE_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
                From date
                <input
                  type="date"
                  value={form.start_date}
                  onChange={(e) => {
                    const start = e.target.value
                    const end = form.end_date && form.end_date >= start ? form.end_date : start
                    setForm({ ...form, start_date: start, end_date: end })
                    syncRangeFromForm(start, end)
                  }}
                  required
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
                To date
                <input
                  type="date"
                  value={form.end_date}
                  min={form.start_date || undefined}
                  onChange={(e) => {
                    const end = e.target.value
                    setForm({ ...form, end_date: end })
                    syncRangeFromForm(form.start_date, end)
                  }}
                  required
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
                />
              </label>
            </div>
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
              Reason (optional)
              <textarea
                value={form.reason}
                onChange={(e) => setForm({ ...form, reason: e.target.value })}
                rows={3}
                style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', resize: 'vertical' }}
              />
            </label>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: '10px',
                background: '#6366f1',
                color: '#fff',
                border: 'none',
                borderRadius: 8,
                fontWeight: 600,
                cursor: submitting ? 'not-allowed' : 'pointer',
                opacity: submitting ? 0.7 : 1,
              }}
            >
              {submitting ? 'Submitting…' : 'Submit request'}
            </button>
          </form>
        </div>
      ) : null}

      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden', minHeight: 120 }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid #f3f4f6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <p style={{ fontWeight: 600, margin: 0 }}>All requests</p>
          <button type="button" onClick={loadLeaves} style={{ fontSize: '0.75rem', color: '#6366f1', background: 'none', border: 'none', cursor: 'pointer' }}>
            Refresh
          </button>
        </div>
        {loading ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading leave requests…</div>
        ) : leaves.length === 0 ? (
          <div style={{ padding: 32, textAlign: 'center', color: '#6b7280' }}>
            <p style={{ margin: '0 0 8px' }}>No leave requests yet.</p>
            <button
              type="button"
              onClick={() => openRequestForm()}
              style={{ color: '#6366f1', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
            >
              Submit your first request
            </button>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
              <thead>
                <tr style={{ background: '#f9fafb' }}>
                  {['Type', 'From', 'To', 'Days', 'Reason', 'Status', 'Note', ''].map((h) => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#6b7280', fontSize: '0.75rem' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {leaves.map((l) => {
                  const sc = STATUS_COLORS[l.status] || STATUS_COLORS.PENDING
                  const tc = TYPE_COLORS[l.leave_type] || '#f3f4f6'
                  return (
                    <tr key={l.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ background: tc, color: '#374151', fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{l.leave_type}</span>
                      </td>
                      <td style={{ padding: '10px 16px' }}>{l.start_date}</td>
                      <td style={{ padding: '10px 16px' }}>{l.end_date}</td>
                      <td style={{ padding: '10px 16px' }}>{l.day_count ?? '—'}</td>
                      <td style={{ padding: '10px 16px', color: '#6b7280' }}>{l.reason || '—'}</td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ background: sc.bg, color: sc.color, fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20, border: `1px solid ${sc.border}` }}>{l.status}</span>
                      </td>
                      <td style={{ padding: '10px 16px', color: '#6b7280', fontSize: '0.8rem', maxWidth: 160 }}>
                        {l.status === 'REJECTED' && l.review_note ? l.review_note : '—'}
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        {l.status === 'PENDING' ? (
                          <button
                            type="button"
                            onClick={() => cancelLeave(l.id)}
                            style={{ fontSize: '0.75rem', color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}
                          >
                            Cancel
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
                </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
