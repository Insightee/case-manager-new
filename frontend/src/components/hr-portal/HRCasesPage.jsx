import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { ErrorBanner } from '../shared/ErrorBanner.jsx'

const STATUS_COLORS = {
  ACTIVE: { bg: '#f0fdf4', color: '#15803d' },
  PENDING: { bg: '#fefce8', color: '#a16207' },
  CLOSED: { bg: '#f4f4f5', color: '#71717a' },
  ON_HOLD: { bg: '#eff6ff', color: '#1d4ed8' },
}

export function HRCasesPage() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await apiFetch('/api/v1/cases?page_size=100')
        setCases(unwrapList(data))
      } catch (err) {
        setCases([])
        setError(err.message || 'Could not load cases')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  const filtered = cases.filter((c) => {
    const q = search.trim().toLowerCase()
    return !q || c.case_code?.toLowerCase().includes(q) || c.product_module?.toLowerCase().includes(q)
  })

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1rem' }}>
      <ErrorBanner message={error} />
      <header style={{ marginBottom: 24 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Cases</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>Read-only overview of all active cases.</p>
      </header>

      <input
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search by case code or programme…"
        style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', marginBottom: 16, boxSizing: 'border-box' }}
      />

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                {['Case code', 'Programme', 'Status', 'Region'].map((h) => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#6b7280', fontSize: '0.75rem' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={4} style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>No cases found.</td></tr>
              ) : filtered.map((c) => {
                const sc = STATUS_COLORS[c.status] || STATUS_COLORS.ACTIVE
                return (
                  <tr key={c.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '12px 16px', fontWeight: 600, fontFamily: 'monospace' }}>{c.case_code}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ background: '#eef2ff', color: '#3730a3', fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20, textTransform: 'capitalize' }}>
                        {c.product_module?.replace(/_/g, ' ') || '—'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ background: sc.bg, color: sc.color, fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>{c.status}</span>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#6b7280' }}>{c.region || '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
