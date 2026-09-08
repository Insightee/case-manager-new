import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel } from './ui/index.js'

export function AdminMentorTherapistsPage() {
  const [therapists, setTherapists] = useState([])
  const [available, setAvailable] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [actingId, setActingId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [roster, open] = await Promise.all([
        apiFetch('/api/v1/admin/mentor/therapists'),
        apiFetch('/api/v1/admin/mentor/therapists/available'),
      ])
      setTherapists(roster?.therapists || [])
      setAvailable(open?.therapists || [])
    } catch (err) {
      setError(err.message || 'Could not load mentor roster')
      setTherapists([])
      setAvailable([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function handleAdd(therapistUserId) {
    setActingId(therapistUserId)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/admin/mentor/therapists/${therapistUserId}`, { method: 'POST' })
      setSuccess('Therapist added to your mentor roster.')
      setShowAdd(false)
      await load()
    } catch (err) {
      setError(err.message || 'Could not add therapist')
    } finally {
      setActingId(null)
    }
  }

  async function handleRemove(therapistUserId, name) {
    if (!window.confirm(`Remove ${name || 'this therapist'} from your mentor roster?`)) return
    setActingId(therapistUserId)
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/admin/mentor/therapists/${therapistUserId}`, { method: 'DELETE' })
      setSuccess('Therapist removed from your mentor roster.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not remove therapist')
    } finally {
      setActingId(null)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Case management"
        title="My therapists"
        subtitle="Therapists you mentor — open their cases, schedule meetings, review logs, and manage support."
        actions={
          <div className="admin-btn-group">
            <Link to="/admin/cm" className="admin-btn admin-btn--ghost admin-btn--sm">
              ← Dashboard
            </Link>
            <button
              type="button"
              className="admin-btn admin-btn--primary admin-btn--sm"
              onClick={() => setShowAdd((v) => !v)}
            >
              {showAdd ? 'Close' : 'Add therapist'}
            </button>
          </div>
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--info">{success}</p> : null}

      {showAdd ? (
        <AdminPanel title={`Available therapists (${available.length})`} className="admin-panel--spaced">
          {available.length === 0 ? (
            <AdminEmptyState
              title="No unassigned therapists"
              description="All therapists already have a mentor, or none match the directory."
            />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Primary CM</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {available.map((t) => (
                    <tr key={t.therapist_user_id}>
                      <td>{t.full_name || t.display_name || '—'}</td>
                      <td>{t.email || '—'}</td>
                      <td>{t.primary_case_manager_name || '—'}</td>
                      <td>
                        <button
                          type="button"
                          className="admin-btn admin-btn--primary admin-btn--sm"
                          disabled={actingId === t.therapist_user_id}
                          onClick={() => handleAdd(t.therapist_user_id)}
                        >
                          Add to my roster
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </AdminPanel>
      ) : null}

      <AdminPanel title={`Mentored therapists (${therapists.length})`} padded={false}>
        {loading ? (
          <p className="admin-muted" style={{ padding: 18 }}>
            Loading…
          </p>
        ) : therapists.length === 0 ? (
          <AdminEmptyState
            title="No mentored therapists yet"
            description="Add therapists from the directory or ask an admin to assign you as mentor."
          />
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Primary CM</th>
                  <th>Active cases</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {therapists.map((t) => (
                  <tr key={t.therapist_user_id}>
                    <td>{t.full_name || t.display_name || '—'}</td>
                    <td>{t.email || '—'}</td>
                    <td>{t.primary_case_manager_name || '—'}</td>
                    <td>{t.active_case_count ?? 0}</td>
                    <td>
                      <div className="admin-btn-group admin-btn-group--wrap">
                        <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
                          Cases
                        </Link>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          disabled={actingId === t.therapist_user_id}
                          onClick={() => handleRemove(t.therapist_user_id, t.full_name)}
                        >
                          Remove
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </AdminPanel>
    </div>
  )
}
