import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDisplayDateTime } from '../../lib/datetime.js'
import { addDays, dateStr } from '../scheduling/slotCalendarUtils.js'

function sortMeetings(items) {
  return [...items].sort((a, b) => {
    const left = `${a.date || ''} ${a.start_time || ''} ${a.id || ''}`
    const right = `${b.date || ''} ${b.start_time || ''} ${b.id || ''}`
    return left.localeCompare(right)
  })
}

export function UpcomingMeetingsPanel({
  title = 'Upcoming meetings',
  subtitle = 'Next 7 days',
  href = '/admin/meetings',
  daysAhead = 7,
  variant = 'admin',
  className = '',
}) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const range = useMemo(() => {
    const from = dateStr(new Date())
    const to = dateStr(addDays(new Date(), Math.max(daysAhead - 1, 0)))
    return { from, to }
  }, [daysAhead])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    apiFetch(`/api/v1/calendar/events?from=${range.from}&to=${range.to}`)
      .then((body) => {
        if (cancelled) return
        const events = Array.isArray(body?.events) ? body.events : []
        setItems(sortMeetings(events.filter((event) => event.event_type === 'cm_meeting')))
      })
      .catch((err) => {
        if (cancelled) return
        setItems([])
        setError(err.message || 'Could not load upcoming meetings')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [range.from, range.to])

  const tone = variant === 'therapist' ? '#4f46e5' : '#0f172a'

  return (
    <section
      className={className}
      style={{
        border: '1px solid #e2e8f0',
        borderRadius: 18,
        background: '#fff',
        padding: 16,
        boxShadow: '0 1px 3px rgba(15, 23, 42, 0.05)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 12 }}>
        <div>
          <p style={{ margin: 0, fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#64748b' }}>
            {subtitle}
          </p>
          <h3 style={{ margin: '4px 0 0', fontSize: '1rem', fontWeight: 800, color: tone }}>{title}</h3>
        </div>
        <Link to={href} style={{ color: '#4f46e5', fontSize: '0.875rem', fontWeight: 700, textDecoration: 'none' }}>
          View all
        </Link>
      </div>

      {loading ? (
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>Loading upcoming meetings…</p>
      ) : error ? (
        <p style={{ margin: 0, color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p>
      ) : items.length === 0 ? (
        <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>No meetings in the next 7 days.</p>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.slice(0, 5).map((item) => (
            <li
              key={item.id}
              style={{
                border: '1px solid #e2e8f0',
                borderRadius: 14,
                padding: '12px 14px',
                background: '#f8fafc',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
                <div style={{ minWidth: 0 }}>
                  <p style={{ margin: 0, fontWeight: 800, color: '#0f172a' }}>
                    {item.title || item.child_name || item.case_code || 'Meeting'}
                  </p>
                  <p style={{ margin: '4px 0 0', color: '#475569', fontSize: '0.875rem' }}>
                    {formatDisplayDateTime(item.date, item.start_time) || item.date}
                  </p>
                  <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.8125rem' }}>
                    {item.case_code || item.child_name ? [item.case_code, item.child_name].filter(Boolean).join(' · ') : 'Participant calendar'}
                  </p>
                </div>
                <span
                  style={{
                    flexShrink: 0,
                    borderRadius: 999,
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    color: '#3730a3',
                    background: '#eef2ff',
                  }}
                >
                  {item.status || 'SCHEDULED'}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
