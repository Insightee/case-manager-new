import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useAuth } from '../../context/AuthContext.jsx'

const EMPTY_SNAPSHOT = {
  active_cases: 0,
  pending_allotment: 0,
  open_tickets: 0,
  therapists_active: 0,
  therapists_pending_profile: 0,
  pending_leave: 0,
  iep_missing: 0,
  observation_checklists_overdue: 0,
}

export function HRDashboardPage() {
  const { user } = useAuth()
  const [snapshot, setSnapshot] = useState(EMPTY_SNAPSHOT)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('/api/v1/hr/ops-snapshot')
      .then(setSnapshot)
      .catch(() => setSnapshot(EMPTY_SNAPSHOT))
      .finally(() => setLoading(false))
  }, [])

  const teamCards = [
    { label: 'Active therapists', value: snapshot.therapists_active, to: '/hr/therapists', color: '#6366f1', bg: '#eef2ff' },
    { label: 'Profiles pending review', value: snapshot.therapists_pending_profile, to: '/hr/therapists', color: '#7c3aed', bg: '#f5f3ff' },
    { label: 'Pending leave', value: snapshot.pending_leave, to: '/hr/leave', color: '#a16207', bg: '#fefce8' },
    { label: 'Open tickets', value: snapshot.open_tickets, to: '/hr/tickets', color: '#1d4ed8', bg: '#eff6ff' },
  ]

  const programmeCards = [
    { label: 'Active cases', value: snapshot.active_cases, to: '/hr/cases', color: '#0d9488', bg: '#f0fdfa' },
    { label: 'Pending allotment', value: snapshot.pending_allotment, to: '/hr/cases', color: '#b45309', bg: '#fffbeb' },
    { label: 'IEP missing (attachments)', value: snapshot.iep_missing, to: '/hr/cases', color: '#4338ca', bg: '#eef2ff' },
    {
      label: 'Overdue observation checklists',
      value: snapshot.observation_checklists_overdue,
      to: '/hr/cases',
      color: '#be123c',
      bg: '#fff1f2',
    },
  ]

  function renderCard(c) {
    return (
      <Link key={c.label} to={c.to} style={{ textDecoration: 'none' }}>
        <div
          style={{
            background: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: 12,
            padding: '20px 20px',
            transition: 'box-shadow 0.15s',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: 6 }}>{c.label}</p>
          {loading ? (
            <div style={{ height: 32, width: 48, background: '#f3f4f6', borderRadius: 6 }} />
          ) : (
            <p style={{ fontSize: '2rem', fontWeight: 800, color: c.color, margin: 0, lineHeight: 1 }}>{c.value}</p>
          )}
        </div>
      </Link>
    )
  }

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 28 }}>
        <p
          style={{
            fontSize: '0.75rem',
            fontWeight: 600,
            color: '#6366f1',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            marginBottom: 4,
          }}
        >
          HR Portal
        </p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Dashboard</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>
          Welcome back, {user?.full_name}. Programme health and team workload — read-only.
        </p>
      </header>

      <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: 10 }}>Team</p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: 14,
          marginBottom: 24,
        }}
      >
        {teamCards.map(renderCard)}
      </div>

      <p style={{ fontSize: '0.8rem', fontWeight: 600, color: '#374151', marginBottom: 10 }}>Programme health</p>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
          gap: 14,
          marginBottom: 28,
        }}
      >
        {programmeCards.map(renderCard)}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 20px' }}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>Quick actions</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Link
              to="/hr/therapists"
              style={{
                display: 'block',
                padding: '10px 14px',
                background: '#f9fafb',
                borderRadius: 8,
                textDecoration: 'none',
                color: '#374151',
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              View therapist profiles →
            </Link>
            <Link
              to="/hr/leave"
              style={{
                display: 'block',
                padding: '10px 14px',
                background: '#f9fafb',
                borderRadius: 8,
                textDecoration: 'none',
                color: '#374151',
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              Review pending leave →
            </Link>
            <Link
              to="/hr/cases"
              style={{
                display: 'block',
                padding: '10px 14px',
                background: '#f9fafb',
                borderRadius: 8,
                textDecoration: 'none',
                color: '#374151',
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              Browse cases →
            </Link>
          </div>
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, padding: '20px 20px' }}>
          <p style={{ fontWeight: 600, marginBottom: 12 }}>Your access</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {user?.module_assignments?.map((m) => (
              <span
                key={m}
                style={{
                  background: '#eef2ff',
                  color: '#3730a3',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  padding: '4px 12px',
                  borderRadius: 20,
                  textTransform: 'capitalize',
                }}
              >
                {m.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
