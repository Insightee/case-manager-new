import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useStaffDirectory } from '../../hooks/useStaffDirectory.js'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'
import { TherapistLeaveBalancePanel } from '../hr-portal/TherapistLeaveBalancePanel.jsx'
import { TherapistReviewsSection } from '../therapist/TherapistReviewsSection.jsx'
import { TherapistServiceProfileForm } from './TherapistServiceProfileForm.jsx'
import { AdminStaffSelect } from './ui/AdminStaffSelect.jsx'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminStatCard,
  AdminStickyFilterRow,
  AdminTaskCard,
  AdminToolbar,
  FilterSelect,
  StatusBadge,
} from './ui/index.js'
import './admin-reports.css'
import './admin-therapist-profiles.css'

function serviceLabels(serviceIds, categories) {
  const byId = new Map((categories || []).map((c) => [c.id, c.label]))
  return (serviceIds || []).map((id) => byId.get(id) || String(id).replace(/_/g, ' '))
}

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
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlStatus = searchParams.get('status') || 'ALL'
  const urlUserId = searchParams.get('user_id')
  const canEditProfiles = canManageUsers || (user?.roles || []).includes('SUPER_ADMIN')

  const [profiles, setProfiles] = useState([])
  const { items: therapistDirectory } = useStaffDirectory({ roles: 'THERAPIST' })
  const { items: staffDirectory } = useStaffDirectory({
    roles: 'CASE_MANAGER,MODULE_ADMIN,SUPERVISOR,SUPER_ADMIN,PROGRAMME_ADMIN',
  })
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
  const [editingServices, setEditingServices] = useState(false)
  const [editServices, setEditServices] = useState([])
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load(selectProfileId = null) {
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
      if (selectProfileId) {
        const match = rows.find((p) => p.id === selectProfileId)
        if (match) setSelected(match)
      }
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
      setSuccess('Case manager and mentor updated.')
      await load(profileId)
    } catch (err) {
      setError(err.message || 'Could not update supervisor/mentor')
    }
  }

  async function saveServices(profileId) {
    if (!editServices.length) {
      setError('Select at least one service')
      return
    }
    setError('')
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}`, {
        method: 'PATCH',
        body: JSON.stringify({ services_offered: editServices }),
      })
      setEditingServices(false)
      setSuccess('Services updated.')
      await load(profileId)
    } catch (err) {
      setError(err.message || 'Could not update services')
    }
  }

  function openServicesEdit(p) {
    setEditServices([...(p.services_offered || [])])
    setEditingServices(true)
  }

  function closeDrawer() {
    setSelected(null)
    setEditingSupervisor(false)
    setEditingServices(false)
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
          canEditProfiles ? (
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowCreate((v) => !v)}>
              {showCreate ? 'Close' : '+ Add profile'}
            </button>
          ) : null
        }
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      {summary ? (
        <div
          className="admin-reports-kpi-row admin-reports-kpi-row--desktop"
          style={{ marginBottom: 16, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 12 }}
        >
          <AdminStatCard title="Pending" value={summary.PENDING ?? 0} tone="amber" onClick={() => setStatusFilterAndUrl('PENDING')} />
          <AdminStatCard title="Draft" value={summary.DRAFT ?? 0} tone="slate" onClick={() => setStatusFilterAndUrl('DRAFT')} />
          <AdminStatCard title="Approved" value={summary.APPROVED ?? 0} tone="green" onClick={() => setStatusFilterAndUrl('APPROVED')} />
          <AdminStatCard title="Paused" value={summary.PAUSED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('PAUSED')} />
          <AdminStatCard title="No profile" value={summary.no_profile ?? 0} tone="indigo" hint="Therapists without listing" />
        </div>
      ) : null}

      <AdminStickyFilterRow>
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilterAndUrl(e.target.value)}
          options={STATUS_FILTERS.map((s) => ({
            value: s,
            label: s === 'ALL' ? 'All statuses' : s.charAt(0) + s.slice(1).toLowerCase(),
          }))}
        />
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
      </AdminStickyFilterRow>

      {summary ? (
        <div className="admin-reports-kpi-row admin-reports-kpi-row--mobile-strip">
          <AdminStatCard title="Pending" value={summary.PENDING ?? 0} tone="amber" onClick={() => setStatusFilterAndUrl('PENDING')} />
          <AdminStatCard title="Draft" value={summary.DRAFT ?? 0} tone="slate" onClick={() => setStatusFilterAndUrl('DRAFT')} />
          <AdminStatCard title="Approved" value={summary.APPROVED ?? 0} tone="green" onClick={() => setStatusFilterAndUrl('APPROVED')} />
          <AdminStatCard title="Paused" value={summary.PAUSED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('PAUSED')} />
          <AdminStatCard title="No profile" value={summary.no_profile ?? 0} tone="indigo" />
        </div>
      ) : null}

      {!canEditProfiles ? (
        <p className="admin-alert" style={{ color: '#b45309', marginBottom: 16 }}>
          View-only access — you can review profiles but cannot create or approve listings.
        </p>
      ) : null}

      {showCreate && canEditProfiles ? (
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
          <div className="therapist-profile-drawer__edit-grid" style={{ gridColumn: '1 / -1' }}>
            <AdminStaffSelect
              label="Primary case manager"
              value={form.supervisor_user_id}
              onChange={(e) => setForm((f) => ({ ...f, supervisor_user_id: e.target.value }))}
              staff={staffDirectory}
              placeholder="Select case manager…"
              required
            />
            <AdminStaffSelect
              label="Mentor (optional)"
              value={form.mentor_user_id}
              onChange={(e) => setForm((f) => ({ ...f, mentor_user_id: e.target.value }))}
              staff={staffDirectory}
              allowEmpty
              emptyLabel="No mentor"
            />
          </div>
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ gridColumn: '1 / -1' }}>
            Create & approve
          </button>
        </form>
      ) : null}

      <AdminPanel title="Profiles" padded={false}>
        <div className="admin-panel__body">
          <div className="admin-desktop-only">
            <AdminCollapsibleFilters
              quickSearch={<AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />}
              activeChips={[statusFilter !== 'ALL' ? statusFilter : null, search.trim()].filter(Boolean)}
              activeCount={[statusFilter !== 'ALL', search.trim()].filter(Boolean).length}
            >
              <AdminToolbar className="admin-toolbar--mobile-compact">
                <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
                <FilterSelect
                  label="Status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilterAndUrl(e.target.value)}
                  options={STATUS_FILTERS.map((s) => ({
                    value: s,
                    label: s === 'ALL' ? 'All statuses' : s.charAt(0) + s.slice(1).toLowerCase(),
                  }))}
                />
              </AdminToolbar>
            </AdminCollapsibleFilters>
          </div>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 18px 16px' }} />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No profiles" description="Try another filter or add a profile." />
          ) : (
            <AdminDataList
              desktop={
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
                          <td>
                            {serviceLabels(p.services_offered, categories).join(', ') || (
                              <span className="admin-muted">—</span>
                            )}
                          </td>
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
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              onClick={() => {
                                setSelected(p)
                                setEditingSupervisor(false)
                                setEditingServices(false)
                              }}
                            >
                              Review
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              }
              mobile={
                <ul className="admin-data-list__cards">
                  {filtered.map((p) => (
                    <li key={p.id}>
                      <AdminTaskCard
                        title={p.display_name || p.full_name}
                        meta={p.email}
                        badges={<StatusBadge status={p.status} />}
                        actions={
                          <button
                            type="button"
                            className="admin-btn admin-btn--primary admin-btn--sm"
                            onClick={() => {
                              setSelected(p)
                              setEditingSupervisor(false)
                              setEditingServices(false)
                            }}
                          >
                            Review
                          </button>
                        }
                      >
                        <p>
                          Services: {serviceLabels(p.services_offered, categories).join(', ') || '—'}
                          <br />
                          Primary CM: {p.supervisor_name || '—'}
                          {p.mentor_name ? ` · Mentor: ${p.mentor_name}` : ''}
                        </p>
                      </AdminTaskCard>
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </div>
      </AdminPanel>

      {selected ? (
        <div className="admin-drawer-backdrop" role="presentation" onClick={closeDrawer}>
          <div
            className="admin-drawer admin-drawer--wide therapist-profile-drawer"
            role="dialog"
            aria-labelledby="therapist-profile-drawer-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="therapist-profile-drawer__header">
              <div className="therapist-profile-drawer__header-main">
                <div>
                  <h2 id="therapist-profile-drawer-title" className="therapist-profile-drawer__title">
                    {selected.display_name || selected.full_name}
                  </h2>
                  <p className="therapist-profile-drawer__subtitle">{selected.email}</p>
                  <div style={{ marginTop: 8 }}>
                    <StatusBadge status={selected.status} />
                  </div>
                </div>
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={closeDrawer}>
                  Close
                </button>
              </div>
            </header>

            <div className="therapist-profile-drawer__body">
              {(selected.short_bio || selected.academic_qualifications || (selected.professional_certificates || []).length) ? (
                <section className="therapist-profile-drawer__section">
                  <h3 className="therapist-profile-drawer__section-title">Profile</h3>
                  {selected.short_bio ? <p className="therapist-profile-drawer__text">{selected.short_bio}</p> : null}
                  {selected.academic_qualifications ? (
                    <p className="therapist-profile-drawer__text" style={{ marginTop: 8, color: '#64748b' }}>
                      <strong>Qualifications:</strong> {selected.academic_qualifications}
                    </p>
                  ) : null}
                  {(selected.professional_certificates || []).length ? (
                    <ul className="therapist-profile-drawer__meta-list">
                      {selected.professional_certificates.map((c) => (
                        <li key={c}>{c}</li>
                      ))}
                    </ul>
                  ) : null}
                </section>
              ) : null}

              <section className="therapist-profile-drawer__section">
                <div className="therapist-profile-drawer__section-head">
                  <h3 className="therapist-profile-drawer__section-title">Service assignment</h3>
                  {canEditProfiles ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={() => {
                        if (editingServices) setEditingServices(false)
                        else openServicesEdit(selected)
                      }}
                    >
                      {editingServices ? 'Cancel' : 'Edit services'}
                    </button>
                  ) : null}
                </div>
                {editingServices ? (
                  <>
                    <ServiceCategoryPicker
                      categories={categories}
                      value={editServices}
                      onChange={setEditServices}
                      disabled={!canEditProfiles}
                    />
                    <div className="admin-btn-group" style={{ marginTop: 12 }}>
                      <button
                        type="button"
                        className="admin-btn admin-btn--primary admin-btn--sm"
                        onClick={() => saveServices(selected.id)}
                      >
                        Save services
                      </button>
                    </div>
                  </>
                ) : (
                  <div className="therapist-profile-drawer__chips">
                    {serviceLabels(selected.services_offered, categories).length ? (
                      serviceLabels(selected.services_offered, categories).map((label) => (
                        <span key={label} className="therapist-profile-drawer__chip">
                          {label}
                        </span>
                      ))
                    ) : (
                      <span className="admin-muted">No services selected</span>
                    )}
                  </div>
                )}
              </section>

              <section className="therapist-profile-drawer__section">
                <div className="therapist-profile-drawer__section-head">
                  <h3 className="therapist-profile-drawer__section-title">Case manager & mentor</h3>
                  {canEditProfiles ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={() => {
                        if (editingSupervisor) setEditingSupervisor(false)
                        else openSupervisorEdit(selected)
                      }}
                    >
                      {editingSupervisor ? 'Cancel' : 'Edit'}
                    </button>
                  ) : null}
                </div>
                {editingSupervisor ? (
                  <div className="therapist-profile-drawer__edit-grid">
                    <AdminStaffSelect
                      label="Primary case manager"
                      value={editSupervisor.supervisorId}
                      onChange={(e) => setEditSupervisor((s) => ({ ...s, supervisorId: e.target.value }))}
                      staff={staffDirectory}
                      placeholder="Select case manager…"
                    />
                    <AdminStaffSelect
                      label="Mentor"
                      value={editSupervisor.mentorId}
                      onChange={(e) => setEditSupervisor((s) => ({ ...s, mentorId: e.target.value }))}
                      staff={staffDirectory}
                      allowEmpty
                      emptyLabel="No mentor"
                    />
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary admin-btn--sm"
                      style={{ gridColumn: '1 / -1' }}
                      onClick={() => saveSupervisorMentor(selected.id)}
                    >
                      Save assignment
                    </button>
                  </div>
                ) : (
                  <dl className="therapist-profile-drawer__assignment-read">
                    <div>
                      <dt>Primary case manager</dt>
                      <dd>{selected.supervisor_name || 'Not assigned'}</dd>
                    </div>
                    <div>
                      <dt>Mentor</dt>
                      <dd>{selected.mentor_name || 'Not assigned'}</dd>
                    </div>
                  </dl>
                )}
              </section>

              <TherapistLeaveBalancePanel therapistUserId={selected.user_id} canEdit={canManageUsers} />

              <section className="therapist-profile-drawer__section">
                <TherapistReviewsSection
                  apiPath={`/api/v1/admin/therapist-profiles/${selected.user_id}/reviews`}
                  title="Client session reviews"
                />
              </section>

              <label className="admin-filter-field">
                <span className="admin-filter-field__label">Admin note (for approve / pause)</span>
                <textarea
                  className="admin-input"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={2}
                />
              </label>

              <div className="therapist-profile-drawer__footer">
                {canEditProfiles && selected.status === 'PENDING' ? (
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('approve', selected.id)}>
                    Approve
                  </button>
                ) : null}
                {canEditProfiles && selected.status === 'APPROVED' ? (
                  <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => act('pause', selected.id)}>
                    Pause
                  </button>
                ) : null}
                {canEditProfiles && selected.status === 'PAUSED' ? (
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('resume', selected.id)}>
                    Resume
                  </button>
                ) : null}
                {canEditProfiles ? (
                  <button type="button" className="admin-btn admin-btn--danger admin-btn--sm" onClick={() => handleDelete(selected.id)}>
                    Delete
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
