import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

const STATUS_OPTIONS = ['ACTIVE', 'SUSPENDED', 'ARCHIVED']

const STATUS_COLORS = {
  ACTIVE: { bg: '#f0fdf4', color: '#15803d', border: '#86efac' },
  SUSPENDED: { bg: '#fefce8', color: '#a16207', border: '#fde047' },
  ARCHIVED: { bg: '#f4f4f5', color: '#71717a', border: '#d4d4d8' },
}

export function HRTherapistsPage() {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [drawerUser, setDrawerUser] = useState(null)
  const [editStatus, setEditStatus] = useState('')
  const [editRegion, setEditRegion] = useState('')
  const [editLocation, setEditLocation] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/hr/therapists')
      setTherapists(data)
    } catch {
      setTherapists([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function openDrawer(t) {
    setDrawerUser(t)
    setEditStatus(t.employment_status || 'ACTIVE')
    setEditRegion(t.region || '')
    setEditLocation(t.location || '')
    setError('')
    setSuccess('')
  }

  async function saveTherapist() {
    if (!drawerUser) return
    setSaving(true)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/hr/therapists/${drawerUser.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          employment_status: editStatus,
          region: editRegion || null,
          location: editLocation || null,
        }),
      })
      setSuccess('Profile updated.')
      load()
      setDrawerUser((prev) => prev ? { ...prev, employment_status: editStatus, region: editRegion, location: editLocation } : prev)
    } catch (err) {
      setError(err.message || 'Could not update')
    } finally {
      setSaving(false)
    }
  }

  const filtered = therapists.filter((t) => {
    const q = search.trim().toLowerCase()
    const matchSearch = !q || t.full_name.toLowerCase().includes(q) || t.email.toLowerCase().includes(q)
    const matchStatus = !statusFilter || (t.employment_status || 'ACTIVE') === statusFilter
    return matchSearch && matchStatus
  })

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ marginBottom: 24 }}>
        <p style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6366f1', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>HR</p>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Therapist Profiles</h1>
        <p style={{ fontSize: '0.875rem', color: '#6b7280', marginTop: 4 }}>View and manage all therapist accounts.</p>
      </header>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or email…"
          style={{ flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem', background: '#fff' }}
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading ? (
        <div style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>Loading…</div>
      ) : (
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 12, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                {['Name', 'Email', 'Status', 'Region', 'Location', 'Modules', ''].map((h) => (
                  <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontWeight: 600, color: '#6b7280', fontSize: '0.75rem' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: 32, textAlign: 'center', color: '#9ca3af' }}>No therapists found.</td></tr>
              ) : filtered.map((t) => {
                const sc = STATUS_COLORS[t.employment_status || 'ACTIVE'] || STATUS_COLORS.ACTIVE
                return (
                  <tr key={t.id} style={{ borderTop: '1px solid #f3f4f6' }}>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#6366f1', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', fontWeight: 700, flexShrink: 0 }}>
                          {t.full_name.charAt(0).toUpperCase()}
                        </div>
                        <span style={{ fontWeight: 500 }}>{t.full_name}</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#6b7280' }}>{t.email}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <span style={{ background: sc.bg, color: sc.color, border: `1px solid ${sc.border}`, fontSize: '0.72rem', fontWeight: 700, padding: '2px 8px', borderRadius: 20 }}>
                        {t.employment_status || 'ACTIVE'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 16px', color: '#6b7280' }}>{t.region || '—'}</td>
                    <td style={{ padding: '12px 16px', color: '#6b7280' }}>{t.location || '—'}</td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                        {t.module_assignments?.map((m) => (
                          <span key={m} style={{ background: '#eef2ff', color: '#3730a3', fontSize: '0.68rem', fontWeight: 600, padding: '2px 8px', borderRadius: 20 }}>{m}</span>
                        ))}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <button type="button" onClick={() => openDrawer(t)}
                        style={{ fontSize: '0.75rem', padding: '5px 12px', borderRadius: 6, background: 'none', border: '1px solid #d1d5db', cursor: 'pointer', fontWeight: 600 }}>
                        Edit
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {drawerUser && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'flex-end', justifyContent: 'center', zIndex: 50 }}
          onClick={(e) => { if (e.target === e.currentTarget) setDrawerUser(null) }}>
          <div style={{ background: '#fff', borderRadius: '16px 16px 0 0', padding: 28, width: '100%', maxWidth: 520, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 20 }}>
              <p style={{ fontWeight: 700, fontSize: '1.1rem' }}>{drawerUser.full_name}</p>
              <button type="button" onClick={() => setDrawerUser(null)} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#6b7280' }}>×</button>
            </div>
            <p style={{ fontSize: '0.8rem', color: '#6b7280', marginBottom: 16 }}>{drawerUser.email}</p>

            {error ? <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: 8, padding: '8px 12px', marginBottom: 12, color: '#b91c1c', fontSize: '0.8rem' }}>{error}</div> : null}
            {success ? <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: 8, padding: '8px 12px', marginBottom: 12, color: '#15803d', fontSize: '0.8rem' }}>{success}</div> : null}

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
                Employment status
                <select value={editStatus} onChange={(e) => setEditStatus(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }}>
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
                Region
                <input value={editRegion} onChange={(e) => setEditRegion(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: '0.875rem', fontWeight: 500 }}>
                Location
                <input value={editLocation} onChange={(e) => setEditLocation(e.target.value)}
                  style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid #d1d5db', fontSize: '0.875rem' }} />
              </label>
              <button type="button" onClick={saveTherapist} disabled={saving}
                style={{ padding: '10px', background: '#6366f1', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 600, cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.7 : 1 }}>
                {saving ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
