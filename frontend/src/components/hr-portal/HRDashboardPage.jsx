import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'

export function HRDashboardPage() {
  const { user } = useAuth()
  const [stats, setStats] = useState({ therapists: 0, pending_leave: 0, open_tickets: 0, memos_sent: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [therapists, leaves, tickets, memos] = await Promise.all([
          apiFetch('/api/v1/hr/therapists').catch(() => []),
          apiFetch('/api/v1/leave').catch(() => []),
          apiFetch('/api/v1/tickets?page_size=100').catch(() => ({ items: [] })),
          apiFetch('/api/v1/hr/memos').catch(() => []),
        ])
        const ticketRows = unwrapList(tickets)
        setStats({
          therapists: therapists.length,
          pending_leave: leaves.filter((l) => l.status === 'PENDING').length,
          open_tickets: ticketRows.filter((t) => t.status === 'OPEN').length,
          memos_sent: memos.length,
        })
      } catch {
        // ignore
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const cards = [
    { label: 'Total therapists', value: stats.therapists, to: '/hr/therapists', color: '#6366f1', bg: '#eef2ff' },
    { label: 'Pending leave requests', value: stats.pending_leave, to: '/hr/leave', color: '#a16207', bg: '#fefce8' },
    { label: 'Open tickets', value: stats.open_tickets, to: '/hr/tickets', color: '#1d4ed8', bg: '#eff6ff' },
    { label: 'Memos sent', value: stats.memos_sent, to: '/hr/memos', color: '#15803d', bg: '#f0fdf4' },
  ]

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 28 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>
          HR Portal
        </p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Dashboard</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
          Welcome back, {user?.full_name}. Here's your team at a glance.
        </p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 14, marginBottom: 28 }}>
        {cards.map((c) => (
          <Link key={c.label} to={c.to} style={{ textDecoration: 'none' }}>
            <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 20px', transition: 'box-shadow 0.15s', cursor: 'pointer' }}
              onMouseEnter={(e) => e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'}
              onMouseLeave={(e) => e.currentTarget.style.boxShadow = 'none'}>
              <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 6 }}>{c.label}</p>
              {loading ? (
                <div style={{ height: 32, width: 48, background: '#f3f4f6', borderRadius: 6 }} />
              ) : (
                <p style={{ fontSize: '2rem', fontWeight: 800, color: c.color, margin: 0, lineHeight: 1 }}>{c.value}</p>
              )}
            </div>
          </Link>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 20px' }}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>Quick actions</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Link to="/hr/therapists" style={{ display: 'block', padding: '10px 14px', background: '#f9fafb', borderRadius: 8, textDecoration: 'none', color: '#374151', fontSize: '0.875rem', fontWeight: 500 }}>
              View therapist profiles →
            </Link>
            <Link to="/hr/leave" style={{ display: 'block', padding: '10px 14px', background: '#f9fafb', borderRadius: 8, textDecoration: 'none', color: '#374151', fontSize: '0.875rem', fontWeight: 500 }}>
              Review pending leave →
            </Link>
            <Link to="/hr/memos" style={{ display: 'block', padding: '10px 14px', background: '#f9fafb', borderRadius: 8, textDecoration: 'none', color: '#374151', fontSize: '0.875rem', fontWeight: 500 }}>
              Send a memo →
            </Link>
          </div>
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 20px' }}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>Your access</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {user?.module_assignments?.map((m) => (
              <span key={m} style={{ background: '#eef2ff', color: '#3730a3', fontSize: '0.75rem', fontWeight: 600, padding: '4px 12px', borderRadius: 20, textTransform: 'capitalize' }}>
                {m.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
