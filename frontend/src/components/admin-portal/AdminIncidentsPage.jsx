import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, AdminToolbar, AdminSearchInput, StatusBadge } from './ui/index.js'

const STATUS_FLOW = ['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']

export function AdminIncidentsPage() {
  const [incidents, setIncidents] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [status, setStatus] = useState('')
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/incidents?page_size=100')
      setIncidents(unwrapList(data))
    } catch {
      setIncidents([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return incidents
    return incidents.filter(
      (i) => i.title?.toLowerCase().includes(q) || i.status?.toLowerCase().includes(q),
    )
  }, [incidents, search])

  function openIncident(item) {
    setSelected(item)
    setStatus(item.status)
  }

  async function saveStatus() {
    if (!selected) return
    setSaving(true)
    try {
      await apiFetch(`/api/v1/incidents/${selected.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      })
      setSelected(null)
      load()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Risk & safety"
        title="Incidents"
        subtitle="Sensitive incident reports (supervisor / super admin only)."
      />

      <AdminPanel title={`${filtered.length} incidents`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title or status…" />
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No incidents recorded" description="Incident reports will appear here when filed." />
          ) : (
            <ul className="admin-queue">
              {filtered.map((i) => (
                <li key={i.id} className="admin-queue__item">
                  <button
                    type="button"
                    style={{ flex: 1, textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    onClick={() => openIncident(i)}
                  >
                    <p className="admin-queue__title">{i.title}</p>
                    <p className="admin-queue__meta">
                      Incident #{i.id}
                      {i.case_id ? (
                        <>
                          {' '}
                          · <Link to={`/admin/cases/${i.case_id}`} onClick={(e) => e.stopPropagation()}>
                            Case {i.case_id}
                          </Link>
                        </>
                      ) : null}
                    </p>
                  </button>
                  <div className="admin-btn-group">
                    <StatusBadge status={i.status} />
                    {i.is_sensitive ? <span className="admin-badge admin-badge--danger">Sensitive</span> : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </AdminPanel>

      {selected ? (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 440, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>{selected.title}</h2>
            <p style={{ fontSize: '0.875rem', color: '#64748b' }}>Incident #{selected.id}</p>
            <label style={{ display: 'block', marginTop: 16 }}>
              Status
              <select className="admin-input" value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: '100%', marginTop: 6 }}>
                {STATUS_FLOW.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </label>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--primary" disabled={saving} onClick={saveStatus}>
                Update status
              </button>
              <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
