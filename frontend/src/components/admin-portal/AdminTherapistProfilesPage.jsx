import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { useStaffDirectory } from '../../hooks/useStaffDirectory.js'
import { TherapistLeaveBalancePanel } from '../hr-portal/TherapistLeaveBalancePanel.jsx'
import { TherapistReviewsSection } from '../therapist/TherapistReviewsSection.jsx'
import { TherapistServiceProfileForm } from './TherapistServiceProfileForm.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminStatCard, AdminToolbar, StatusBadge } from './ui/index.js'
import './admin-reports.css'

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'PAUSED', 'DRAFT']

const EMPTY_FORM = {
  user_id: '',
  display_name: '',
  short_bio: '',
  academic_qualifications: '',
  professional_certificates: '',
  services_offered: [],
  supervisor_user_id: '',
  mentor_user_id: '',
}

export function AdminTherapistProfilesPage() {
  const { canManageUsers } = useModuleWrite()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlStatus = searchParams.get('status') || 'PENDING'
  const urlUserId = searchParams.get('user_id')

  const [profiles, setProfiles] = useState([])
  const { items: therapistDirectory } = useStaffDirectory({ roles: 'THERAPIST' })
  const { items: mentorDirectory } = useStaffDirectory({ roles: 'CASE_MANAGER,MODULE_ADMIN,SUPER_ADMIN' })
  const [categories, setCategories] = useState([])
  const [summary, setSummary] = useState(null)
  const [statusFilter, setStatusFilter] = useState(urlStatus)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [note, setNote] = useState('')
  const [editSupervisor, setEditSupervisor] = useState({ supervisorId: '', mentorId: '' })
  const [editingSupervisor, setEditingSupervisor] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try {
      const q = statusFilter !== 'ALL' ? `?status=${statusFilter}` : ''
      const [rows, cats, sum] = await Promise.all([
        apiFetch(`/api/v1/admin/therapist-profiles${q}`),
        apiFetch('/api/v1/therapist/service-categories'),
        apiFetch('/api/v1/admin/therapist-profiles/summary').catch(() => null),
      ])
      setProfiles(rows)
      setCategories(cats)
      setSummary(sum)
    } catch {
      setProfiles([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [statusFilter])

  useEffect(() => {
    setStatusFilter(urlStatus)
  }, [urlStatus])

  useEffect(() => {
    if (!urlUserId || loading || profiles.length === 0) return
    const uid = Number(urlUserId)
    const match = profiles.find((p) => p.user_id === uid)
    if (match) setSelected(match)
  }, [urlUserId, loading, profiles])

  function setStatusFilterAndUrl(next) {
    setStatusFilter(next)
    const nextParams = { ...Object.fromEntries(searchParams.entries()) }
    if (next === 'ALL') delete nextParams.status
    else nextParams.status = next
    setSearchParams(nextParams, { replace: true })
  }

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

  const profileUserIds = useMemo(() => new Set(profiles.map((p) => p.user_id)), [profiles])

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
    if (!form.supervisor_user_id) {
      setError('Select a primary case manager')
      return
    }
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
          supervisor_user_id: form.supervisor_user_id ? Number(form.supervisor_user_id) : null,
          mentor_user_id: form.mentor_user_id ? Number(form.mentor_user_id) : null,
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

  async function saveSupervisorMentor(profileId) {
    setError('')
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          supervisor_user_id: editSupervisor.supervisorId ? Number(editSupervisor.supervisorId) : null,
          mentor_user_id: editSupervisor.mentorId ? Number(editSupervisor.mentorId) : null,
        }),
      })
      setEditingSupervisor(false)
      setSuccess('Supervisor/mentor updated.')
      await load()
    } catch (err) {
      setError(err.message || 'Could not update supervisor/mentor')
    }
  }

  function openSupervisorEdit(p) {
    setEditSupervisor({
      supervisorId: p.supervisor_user_id ? String(p.supervisor_user_id) : '',
      mentorId: p.mentor_user_id ? String(p.mentor_user_id) : '',
    })
    setEditingSupervisor(true)
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Therapists"
        title="Service profiles"
        subtitle="Review, approve, pause, or create therapist service listings."
        actions={
          canManageUsers ? (
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? 'Close' : '+ Add profile'}
            </button>
          ) : null
        }
      />

      {error ? <p style={{ color: '#b91c1c', fontSize: '0.875rem' }}>{error}</p> : null}
      {success ? <p style={{ color: '#15803d', fontSize: '0.875rem' }}>{success}</p> : null}

      {summary ? (
        <div className="admin-reports-kpi-row" style={{ marginBottom: 16 }}>
          <AdminStatCard title="Pending" value={summary.PENDING ?? 0} tone="amber" onClick={() => setStatusFilterAndUrl('PENDING')} />
          <AdminStatCard title="Draft" value={summary.DRAFT ?? 0} tone="slate" onClick={() => setStatusFilterAndUrl('DRAFT')} />
          <AdminStatCard title="Approved" value={summary.APPROVED ?? 0} tone="green" onClick={() => setStatusFilterAndUrl('APPROVED')} />
          <AdminStatCard title="Paused" value={summary.PAUSED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('PAUSED')} />
          <AdminStatCard title="No profile" value={summary.no_profile ?? 0} tone="indigo" hint="Therapists without listing" />
        </div>
      ) : null}

      {!canManageUsers ? (
        <p className="admin-alert" style={{ color: '#b45309', marginBottom: 16 }}>
          View-only access — you can review profiles but cannot create or approve listings.
        </p>
      ) : null}

      {showCreate && canManageUsers ? (
        <form className="admin-form-grid" style={{ maxWidth: 560, marginBottom: 20 }} onSubmit={handleCreate}>
          <p className="admin-drawer__subtitle" style={{ gridColumn: '1 / -1' }}>
            Create profile for therapist
          </p>
          <TherapistServiceProfileForm
            form={form}
            setForm={setForm}
            categories={categories}
            showTherapistSelect
            therapists={therapistDirectory}
            profileUserIds={profileUserIds}
          />
          <div style={{ gridColumn: '1 / -1', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label>
              Primary case manager
              <select
                className="admin-input"
                value={form.supervisor_user_id}
                onChange={(e) => setForm((f) => ({ ...f, supervisor_user_id: e.target.value }))}
                required
              >
                <option value="">Select case manager…</option>
                {mentorDirectory.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                ))}
              </select>
            </label>
            <label>
              Mentor (optional)
              <select
                className="admin-input"
                value={form.mentor_user_id}
                onChange={(e) => setForm((f) => ({ ...f, mentor_user_id: e.target.value }))}
              >
                <option value="">— None —</option>
                {mentorDirectory.map((u) => (
                  <option key={u.id} value={u.id}>{u.full_name} ({u.email})</option>
                ))}
              </select>
            </label>
          </div>
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ gridColumn: '1 / -1' }}>
            Create & approve
          </button>
        </form>
      ) : null}

      <AdminPanel title="Profiles" padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
            <select
              className="admin-search__input"
              style={{ flex: '0 0 auto', width: 'auto', minWidth: 140, paddingLeft: 12, backgroundImage: 'none' }}
              value={statusFilter}
              onChange={(e) => setStatusFilterAndUrl(e.target.value)}
            >
              {STATUS_FILTERS.map((s) => (
                <option key={s} value={s}>{s}</option>
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
                    <th>Primary CM</th>
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
                        {p.supervisor_name ? (
                          <span>{p.supervisor_name}</span>
                        ) : (
                          <span className="admin-muted">—</span>
                        )}
                        {p.mentor_name ? (
                          <span className="admin-table__meta">Mentor: {p.mentor_name}</span>
                        ) : null}
                      </td>
                      <td><StatusBadge status={p.status} /></td>
                      <td>
                        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => { setSelected(p); setEditingSupervisor(false) }}>
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
            <strong>Services:</strong> {(selected.services_offered || []).join(', ') || '—'}
          </p>

          {/* Supervisor / mentor assignment */}
          <div className="profile-drawer-supervisor-row">
            <div>
              <p className="admin-muted" style={{ marginBottom: 4 }}>
                <strong>Primary case manager:</strong>{' '}
                {selected.supervisor_name || <em>Not assigned</em>}
              </p>
              <p className="admin-muted" style={{ marginBottom: 4 }}>
                <strong>Mentor:</strong>{' '}
                {selected.mentor_name || <em>Not assigned</em>}
              </p>
            </div>
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={() => {
                if (editingSupervisor) {
                  setEditingSupervisor(false)
                } else {
                  openSupervisorEdit(selected)
                }
              }}
            >
              {editingSupervisor ? 'Cancel' : 'Edit'}
            </button>
          </div>

          {editingSupervisor ? (
            <div className="profile-drawer-supervisor-edit">
              <label>
                Primary case manager
                <select
                  className="admin-input"
                  value={editSupervisor.supervisorId}
                  onChange={(e) => setEditSupervisor((s) => ({ ...s, supervisorId: e.target.value }))}
                >
                  <option value="">Select case manager…</option>
                  {mentorDirectory.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </select>
              </label>
              <label>
                Mentor
                <select
                  className="admin-input"
                  value={editSupervisor.mentorId}
                  onChange={(e) => setEditSupervisor((s) => ({ ...s, mentorId: e.target.value }))}
                >
                  <option value="">— None —</option>
                  {mentorDirectory.map((u) => (
                    <option key={u.id} value={u.id}>{u.full_name}</option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="admin-btn admin-btn--primary admin-btn--sm"
                onClick={() => saveSupervisorMentor(selected.id)}
              >
                Save
              </button>
            </div>
          ) : null}

          <TherapistLeaveBalancePanel therapistUserId={selected.user_id} canEdit={canManageUsers} />

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
            {canManageUsers && selected.status === 'PENDING' ? (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('approve', selected.id)}>
                Approve
              </button>
            ) : null}
            {canManageUsers && selected.status === 'APPROVED' ? (
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => act('pause', selected.id)}>
                Pause
              </button>
            ) : null}
            {canManageUsers && selected.status === 'PAUSED' ? (
              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('resume', selected.id)}>
                Resume
              </button>
            ) : null}
            {canManageUsers ? (
              <button type="button" className="admin-btn admin-btn--danger admin-btn--sm" onClick={() => handleDelete(selected.id)}>
                Delete
              </button>
            ) : null}
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => { setSelected(null); setEditingSupervisor(false) }}>
              Close
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
