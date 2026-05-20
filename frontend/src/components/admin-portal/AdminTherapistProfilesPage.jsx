import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'
import { TherapistReviewsSection } from '../therapist/TherapistReviewsSection.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar, StatusBadge } from './ui/index.js'

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'PAUSED', 'DRAFT']

const EMPTY_FORM = {
  user_id: '',
  display_name: '',
  short_bio: '',
  academic_qualifications: '',
  professional_certificates: '',
  services_offered: [],
}

export function AdminTherapistProfilesPage() {
  const [profiles, setProfiles] = useState([])
  const [therapists, setTherapists] = useState([])
  const [categories, setCategories] = useState([])
  const [statusFilter, setStatusFilter] = useState('PENDING')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try {
      const q = statusFilter !== 'ALL' ? `?status=${statusFilter}` : ''
      const [rows, users, cats] = await Promise.all([
        apiFetch(`/api/v1/admin/therapist-profiles${q}`),
        apiFetch('/api/v1/admin/users'),
        apiFetch('/api/v1/therapist/service-categories'),
      ])
      setProfiles(rows)
      setTherapists(users.filter((u) => u.roles?.includes('THERAPIST')))
      setCategories(cats)
    } catch {
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [statusFilter])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return profiles
    return profiles.filter(
      (p) =>
        p.display_name?.toLowerCase().includes(q) ||
        p.full_name?.toLowerCase().includes(q) ||
        p.email?.toLowerCase().includes(q),
    )
  }, [profiles, search])

  const therapistsWithoutProfile = useMemo(() => {
    const ids = new Set(profiles.map((p) => p.user_id))
    return therapists.filter((t) => !ids.has(t.id))
  }, [therapists, profiles])

  async function act(path, profileId) {
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}/${path}`, {
        method: 'POST',
        body: JSON.stringify({ admin_note: note || null }),
      })
      setNote('')
      setSelected(null)
      setSuccess(`Profile ${path}d.`)
      await load()
    } catch (err) {
      setError(err.message || 'Action failed')
    }
  }

  async function handleCreate(e) {
    e.preventDefault()
    setError('')
    try {
      const certs = form.professional_certificates
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean)
      await apiFetch('/api/v1/admin/therapist-profiles', {
        method: 'POST',
        body: JSON.stringify({
          user_id: Number(form.user_id),
          display_name: form.display_name.trim(),
          short_bio: form.short_bio.trim() || null,
          academic_qualifications: form.academic_qualifications.trim() || null,
          professional_certificates: certs,
          services_offered: form.services_offered,
          status: 'APPROVED',
        }),
      })
      setForm(EMPTY_FORM)
      setShowCreate(false)
      setSuccess('Profile created.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not create profile')
    }
  }

  async function handleDelete(profileId) {
    if (!window.confirm('Delete this therapist profile?')) return
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}`, { method: 'DELETE' })
      setSelected(null)
      await load()
    } catch (err) {
      setError(err.message || 'Delete failed')
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Therapists"
        title="Service profiles"
        subtitle="Review, approve, pause, or create therapist service listings."
        actions={
          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? 'Close' : '+ Add profile'}
          </button>
        }
      />

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem' }}>{success}</p> : null}

      {showCreate ? (
        <form className="admin-form-grid" style={{ maxWidth: 520, marginBottom: 20 }} onSubmit={handleCreate}>
          <p className="admin-drawer__subtitle" style={{ gridColumn: '1 / -1' }}>
            Create profile for therapist
          </p>
          <label>
            Therapist
            <select required value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}>
              <option value="">Select…</option>
              {therapistsWithoutProfile.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.full_name} ({t.email})
                </option>
              ))}
            </select>
          </label>
          <label>
            Display name
            <input required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Short bio
            <textarea value={form.short_bio} onChange={(e) => setForm({ ...form, short_bio: e.target.value })} rows={2} />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Qualifications
            <textarea
              value={form.academic_qualifications}
              onChange={(e) => setForm({ ...form, academic_qualifications: e.target.value })}
              rows={2}
            />
          </label>
          <label style={{ gridColumn: '1 / -1' }}>
            Certificates (one per line)
            <textarea
              value={form.professional_certificates}
              onChange={(e) => setForm({ ...form, professional_certificates: e.target.value })}
              rows={2}
            />
          </label>
          <div style={{ gridColumn: '1 / -1' }}>
            <p className="admin-drawer__subtitle">Services</p>
            <ServiceCategoryPicker
              categories={categories}
              value={form.services_offered}
              onChange={(services_offered) => setForm({ ...form, services_offered })}
            />
          </div>
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ gridColumn: '1 / -1' }}>
            Create & approve
          </button>
        </form>
      ) : null}

      <AdminPanel title="Profiles" padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or email…" />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 18px 16px' }} />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No profiles" description="Try another filter or add a profile." />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Therapist</th>
                    <th>Services</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((p) => (
                    <tr key={p.id}>
                      <td>
                        <span className="admin-table__primary">{p.display_name || p.full_name}</span>
                        <span className="admin-table__meta">{p.email}</span>
                      </td>
                      <td>{(p.services_offered || []).length} selected</td>
                      <td>
                        <StatusBadge status={p.status} />
                      </td>
                      <td>
                        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setSelected(p)}>
                          Review
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>

      {selected ? (
        <div className="admin-drawer">
          <h3 className="admin-drawer__title">{selected.display_name || selected.full_name}</h3>
          <p className="admin-drawer__subtitle">{selected.email}</p>
          {selected.short_bio ? <p style={{ fontSize: '0.875rem' }}>{selected.short_bio}</p> : null}
          {selected.academic_qualifications ? (
            <p style={{ fontSize: '0.8rem', color: '#64748b' }}>
              <strong>Qualifications:</strong> {selected.academic_qualifications}
            </p>
          ) : null}
          {(selected.professional_certificates || []).length ? (
            <ul style={{ fontSize: '0.8rem', paddingLeft: 18 }}>
              {selected.professional_certificates.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          ) : null}
          <p style={{ fontSize: '0.8rem' }}>
            <strong>Services:</strong> {(selected.services_offered || []).join(', ')}
          </p>
          <div style={{ marginTop: 16 }}>
            <TherapistReviewsSection
              apiPath={`/api/v1/admin/therapist-profiles/${selected.user_id}/reviews`}
              title="Client session reviews"
            />
          </div>
          <label style={{ display: 'block', marginTop: 12 }}>
            Admin note
            <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} className="admin-search__input" style={{ width: '100%', marginTop: 4 }} />
          </label>
          <div className="admin-btn-group" style={{ marginTop: 12, flexWrap: 'wrap' }}>
            {selected.status === 'PENDING' ? (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('approve', selected.id)}>
                Approve
              </button>
            ) : null}
            {selected.status === 'APPROVED' ? (
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => act('pause', selected.id)}>
                Pause
              </button>
            ) : null}
            {selected.status === 'PAUSED' ? (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('resume', selected.id)}>
                Resume
              </button>
            ) : null}
            <button type="button" className="admin-btn admin-btn--danger admin-btn--sm" onClick={() => handleDelete(selected.id)}>
              Delete
            </button>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
