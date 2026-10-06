import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import { useDebouncedValue } from '../../hooks/useDebouncedValue.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { useStaffDirectory } from '../../hooks/useStaffDirectory.js'
import { ServiceCategoryPicker } from '../shared/ServiceCategoryPicker.jsx'
import { TherapistLeaveBalancePanel } from '../hr-portal/TherapistLeaveBalancePanel.jsx'
import { TherapistReviewsSection } from '../therapist/TherapistReviewsSection.jsx'
import { AdminTherapistVaultPanel } from './AdminTherapistVaultPanel.jsx'
import { qualificationLevelLabel } from '../../lib/therapistQualificationLevels.js'
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
  PeopleListPagination,
  StatusBadge,
} from './ui/index.js'
import './admin-reports.css'
import './admin-therapist-profiles.css'

function serviceLabels(serviceIds, categories) {
  const byId = new Map((categories || []).map((c) => [c.id, c.label]))
  return (serviceIds || []).map((id) => byId.get(id) || String(id).replace(/_/g, ' '))
}

// Therapist-editable fields the admin reviews. Mirrors SNAPSHOT_FIELDS on the
// backend so we can diff a pending profile against its last approved snapshot.
const DIFF_FIELDS = [
  { key: 'display_name', label: 'Display name', type: 'text' },
  { key: 'short_bio', label: 'Short bio', type: 'text' },
  { key: 'academic_qualifications', label: 'Qualifications', type: 'text' },
  { key: 'professional_certificates', label: 'Certificates', type: 'list' },
  { key: 'professional_qualification_entries', label: 'Qualification cards', type: 'cards' },
  { key: 'services_offered', label: 'Services', type: 'services' },
]

function normalizeForDiff(value, type) {
  if (type === 'text') return (value ?? '').toString().trim()
  if (type === 'cards') {
    return [...(value || [])].map((row) => `${row.kind || ''}:${row.title || ''}:${row.year || ''}`).filter(Boolean)
  }
  return [...(value || [])].map((v) => String(v)).filter(Boolean)
}

function valuesEqual(a, b, type) {
  if (type === 'text') return a === b
  const sa = [...a].sort()
  const sb = [...b].sort()
  return sa.length === sb.length && sa.every((v, i) => v === sb[i])
}

// Returns null when there is no approved baseline yet (first submission),
// otherwise an array of changed fields with old/new values.
function computeProfileChanges(profile) {
  const snap = profile?.approved_snapshot
  const pending = profile?.pending_submission
  const candidate = pending || profile
  if (!snap) return null
  const changes = []
  for (const field of DIFF_FIELDS) {
    const oldVal = normalizeForDiff(snap[field.key], field.type)
    const newVal = normalizeForDiff(candidate[field.key], field.type)
    if (!valuesEqual(oldVal, newVal, field.type)) {
      changes.push({ ...field, oldVal, newVal })
    }
  }
  return changes
}

function formatDiffValue(value, type, categories) {
  if (type === 'services') {
    const labels = serviceLabels(value, categories)
    return labels.length ? labels.join(', ') : '—'
  }
  if (type === 'list' || type === 'cards') {
    return value.length ? value.join(', ') : '—'
  }
  return value || '—'
}

function ProfileChangesSection({ profile, categories }) {
  const needsReview =
    profile &&
    (profile.status === 'PENDING' ||
      profile.status === 'CHANGES_REQUESTED' ||
      profile.has_pending_changes ||
      profile.status === 'DRAFT')
  if (!needsReview) return null

  const changes = computeProfileChanges(profile)

  if (changes === null) {
    return (
      <section className="therapist-profile-drawer__section therapist-profile-drawer__changes therapist-profile-drawer__changes--new">
        <h3 className="therapist-profile-drawer__section-title">Changes to review</h3>
        <p className="therapist-profile-drawer__text">
          First submission — every detail below is new. Review the profile and approve to publish it.
        </p>
      </section>
    )
  }

  if (changes.length === 0) {
    return (
      <section className="therapist-profile-drawer__section therapist-profile-drawer__changes">
        <h3 className="therapist-profile-drawer__section-title">Changes to review</h3>
        <p className="therapist-profile-drawer__text">
          No changes to the approved details. The therapist may have resubmitted without edits.
        </p>
      </section>
    )
  }

  return (
    <section className="therapist-profile-drawer__section therapist-profile-drawer__changes">
      <h3 className="therapist-profile-drawer__section-title">
        Changes to review · {changes.length} {changes.length === 1 ? 'field' : 'fields'}
      </h3>
      <p className="therapist-profile-drawer__changes-hint">
        Compared with the last approved version. Review what changed, then approve below.
      </p>
      <ul className="therapist-profile-drawer__diff-list">
        {changes.map((c) => (
          <li key={c.key} className="therapist-profile-drawer__diff-row">
            <span className="therapist-profile-drawer__diff-field">{c.label}</span>
            <div className="therapist-profile-drawer__diff-values">
              <span className="therapist-profile-drawer__diff-old">
                {formatDiffValue(c.oldVal, c.type, categories)}
              </span>
              <span className="therapist-profile-drawer__diff-arrow" aria-hidden="true">→</span>
              <span className="therapist-profile-drawer__diff-new">
                {formatDiffValue(c.newVal, c.type, categories)}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

const PAGE_SIZE = 25

const STATUS_FILTERS = ['ALL', 'PENDING', 'APPROVED', 'PAUSED', 'DRAFT', 'DELETED', 'NEEDS_LISTING']

const ACTIVITY_FILTERS = [
  { value: '', label: 'All activity' },
  { value: 'no_sessions_15d', label: 'No session logs (15 days)' },
]

function statusFilterLabel(value) {
  if (value === 'ALL') return 'All statuses'
  if (value === 'NEEDS_LISTING') return 'Needs listing'
  if (value === 'DELETED') return 'Deleted'
  return value.charAt(0) + value.slice(1).toLowerCase()
}

function profileRowKey(profile) {
  return profile.id != null ? String(profile.id) : `user-${profile.user_id}`
}

function formatLastSessionLog(profile) {
  if (profile.last_session_log_at) {
    const d = new Date(profile.last_session_log_at)
    return Number.isNaN(d.getTime()) ? '—' : d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
  }
  if (profile.days_since_last_session_log == null) return 'Never'
  return 'Never'
}

/** Badge/filter status: approved listings with unreviewed edits count as Pending. */
function profileDisplayStatus(profile) {
  if (profile?.status === 'NEEDS_LISTING' || profile?.status === 'DELETED') return profile.status
  if (profile?.has_pending_changes || profile?.status === 'CHANGES_REQUESTED') return 'PENDING'
  return profile?.status || 'DRAFT'
}

const EMPTY_FORM = {
  user_id: '',
  display_name: '',
  short_bio: '',
  academic_qualifications: '',
  academic_qualification_level: '',
  professional_certificates: '',
  services_offered: [],
  supervisor_user_id: '',
  mentor_user_id: '',
  employment_start_date: '',
}

export function AdminTherapistProfilesPage() {
  const { canManageUsers } = useModuleWrite()
  const { user } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlStatus = searchParams.get('status') || 'ALL'
  const urlActivity = searchParams.get('activity') || ''
  const urlUserId = searchParams.get('user_id')
  const canEditProfiles = canManageUsers || (user?.roles || []).includes('SUPER_ADMIN')

  const [profiles, setProfiles] = useState([])
  const [page, setPage] = useState(1)
  const [listMeta, setListMeta] = useState({ total: 0, pages: 1 })
  const { items: therapistDirectory } = useStaffDirectory({ roles: 'THERAPIST' })
  const { items: staffDirectory } = useStaffDirectory({
    roles: 'CASE_MANAGER,MODULE_ADMIN,SUPERVISOR,SUPER_ADMIN,PROGRAMME_ADMIN',
  })
  const { items: mentorDirectory } = useStaffDirectory({
    roles: 'CASE_MANAGER',
  })
  const [categories, setCategories] = useState([])
  const [summary, setSummary] = useState(null)
  const [statusFilter, setStatusFilter] = useState(urlStatus)
  const [activityFilter, setActivityFilter] = useState(urlActivity)
  const [search, setSearch] = useState('')
  const searchDebounced = useDebouncedValue(search)
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
  const [exporting, setExporting] = useState(false)
  const [drawerTab, setDrawerTab] = useState('review')

  const load = useCallback(
    async (selectProfileId = null) => {
      setLoading(true)
      try {
        const params = new URLSearchParams({
          page: String(page),
          page_size: String(PAGE_SIZE),
        })
        if (statusFilter !== 'ALL') params.set('status', statusFilter)
        if (activityFilter) params.set('activity', activityFilter)
        if (searchDebounced.trim()) params.set('q', searchDebounced.trim())
        if (urlUserId) params.set('user_id', urlUserId)
        const qs = params.toString()
        const [data, cats, sum] = await Promise.all([
          apiFetch(`/api/v1/admin/therapist-profiles?${qs}`),
          apiFetch('/api/v1/therapist/service-categories'),
          apiFetch('/api/v1/admin/therapist-profiles/summary').catch(() => null),
        ])
        const rows = data.items || []
        setProfiles(rows)
        setListMeta({ total: data.total ?? 0, pages: data.pages ?? 1 })
        setCategories(cats)
        setSummary(sum)
        if (selectProfileId) {
          const match = rows.find((p) => p.id === selectProfileId)
          if (match) setSelected(match)
        }
      } catch {
        setProfiles([])
        setListMeta({ total: 0, pages: 1 })
      } finally {
        setLoading(false)
      }
    },
    [page, statusFilter, activityFilter, searchDebounced, urlUserId],
  )

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, activityFilter, searchDebounced])

  useEffect(() => {
    setStatusFilter(urlStatus)
  }, [urlStatus])

  useEffect(() => {
    setActivityFilter(urlActivity)
  }, [urlActivity])

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

  function setActivityFilterAndUrl(next) {
    setActivityFilter(next)
    const nextParams = { ...Object.fromEntries(searchParams.entries()) }
    if (!next) delete nextParams.activity
    else nextParams.activity = next
    setSearchParams(nextParams, { replace: true })
  }

  const showLastLogColumn = activityFilter === 'no_sessions_15d'

  const profileUserIds = useMemo(() => new Set(profiles.map((p) => p.user_id)), [profiles])
  const rangeStart = listMeta.total ? (page - 1) * PAGE_SIZE + 1 : 0
  const rangeEnd = Math.min(page * PAGE_SIZE, listMeta.total)

  async function act(path, profileId) {
    setError('')
    setSuccess('')
    if (path === 'request-changes' && (note || '').trim().length < 8) {
      setError('Add a short note so they know what to update.')
      return
    }
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}/${path}`, {
        method: 'POST',
        body: JSON.stringify({ admin_note: note || null }),
      })
      setNote('')
      setSelected(null)
      setSuccess(path === 'request-changes' ? 'Asked for a few updates.' : `Profile ${path}d.`)
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
          academic_qualification_level: form.academic_qualification_level || null,
          professional_certificates: certs,
          services_offered: form.services_offered,
          status: 'APPROVED',
          supervisor_user_id: form.supervisor_user_id ? Number(form.supervisor_user_id) : null,
          mentor_user_id: form.mentor_user_id ? Number(form.mentor_user_id) : null,
          employment_start_date: form.employment_start_date || null,
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

  async function handleRestore(profileId) {
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}/restore`, { method: 'POST' })
      setSelected(null)
      setSuccess('Profile restored as paused.')
      await load()
    } catch (err) {
      setError(err.message || 'Restore failed')
    }
  }

  function openNeedsListingCreate(profile) {
    setForm({
      ...EMPTY_FORM,
      user_id: String(profile.user_id),
      display_name: profile.full_name || profile.display_name || '',
    })
    setShowCreate(true)
    setSelected(null)
  }

  async function saveSupervisorMentor(profileId) {
    setError('')
    try {
      await apiFetch(`/api/v1/admin/therapist-profiles/${profileId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          supervisor_user_id: editSupervisor.supervisorId ? Number(editSupervisor.supervisorId) : null,
          mentor_user_id: editSupervisor.mentorId ? Number(editSupervisor.mentorId) : null,
          employment_start_date: editSupervisor.employmentStartDate || null,
        }),
      })
      setEditingSupervisor(false)
      setSuccess('Case manager, mentor and start date updated.')
      await load(profileId)
    } catch (err) {
      setError(err.message || 'Could not update supervisor/mentor/start date')
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
    setDrawerTab('review')
    setSelected(null)
    setEditingSupervisor(false)
    setEditingServices(false)
  }

  function openSupervisorEdit(p) {
    setEditSupervisor({
      supervisorId: p.supervisor_user_id ? String(p.supervisor_user_id) : '',
      mentorId: p.mentor_user_id ? String(p.mentor_user_id) : '',
      employmentStartDate: p.employment_start_date || '',
    })
    setEditingSupervisor(true)
  }

  async function exportProfiles() {
    setExporting(true)
    setError('')
    try {
      const params = new URLSearchParams()
      if (statusFilter !== 'ALL') params.set('status', statusFilter)
      if (search.trim()) params.set('q', search.trim())
      const qs = params.toString()
      const stamp = new Date().toISOString().slice(0, 10)
      await apiDownload(
        `/api/v1/admin/therapist-profiles/export.csv${qs ? `?${qs}` : ''}`,
        `therapist-profiles-${stamp}.csv`,
      )
    } catch (err) {
      setError(err.message || 'Could not download profiles')
    } finally {
      setExporting(false)
    }
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
          <AdminStatCard title="Deleted" value={summary.DELETED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('DELETED')} />
          <AdminStatCard
            title="Needs listing"
            value={summary.needs_listing ?? summary.no_profile ?? 0}
            tone="indigo"
            hint="Therapist accounts without a service profile yet"
            onClick={() => setStatusFilterAndUrl('NEEDS_LISTING')}
          />
          <AdminStatCard
            title="No logs 15d"
            value={summary.no_sessions_15d ?? 0}
            tone="amber"
            hint="Listed therapists with no submitted session logs in 15 days"
            onClick={() => setActivityFilterAndUrl('no_sessions_15d')}
          />
        </div>
      ) : null}

      <AdminStickyFilterRow>
        <FilterSelect
          label="Status"
          value={statusFilter}
          onChange={(e) => setStatusFilterAndUrl(e.target.value)}
          options={STATUS_FILTERS.map((s) => ({
            value: s,
            label: statusFilterLabel(s),
          }))}
        />
        <FilterSelect
          label="Activity"
          value={activityFilter}
          onChange={(e) => setActivityFilterAndUrl(e.target.value)}
          options={ACTIVITY_FILTERS}
        />
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
      </AdminStickyFilterRow>

      {summary ? (
        <div className="admin-reports-kpi-row admin-reports-kpi-row--mobile-strip">
          <AdminStatCard title="Pending" value={summary.PENDING ?? 0} tone="amber" onClick={() => setStatusFilterAndUrl('PENDING')} />
          <AdminStatCard title="Draft" value={summary.DRAFT ?? 0} tone="slate" onClick={() => setStatusFilterAndUrl('DRAFT')} />
          <AdminStatCard title="Approved" value={summary.APPROVED ?? 0} tone="green" onClick={() => setStatusFilterAndUrl('APPROVED')} />
          <AdminStatCard title="Paused" value={summary.PAUSED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('PAUSED')} />
          <AdminStatCard title="Deleted" value={summary.DELETED ?? 0} tone="rose" onClick={() => setStatusFilterAndUrl('DELETED')} />
          <AdminStatCard
            title="Needs listing"
            value={summary.needs_listing ?? summary.no_profile ?? 0}
            tone="indigo"
            onClick={() => setStatusFilterAndUrl('NEEDS_LISTING')}
          />
          <AdminStatCard
            title="No logs 15d"
            value={summary.no_sessions_15d ?? 0}
            tone="amber"
            onClick={() => setActivityFilterAndUrl('no_sessions_15d')}
          />
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
              staff={mentorDirectory}
              allowEmpty
              emptyLabel="No mentor"
            />
          </div>
          <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" style={{ gridColumn: '1 / -1' }}>
            Create & approve
          </button>
        </form>
      ) : null}

      <AdminPanel
        title="Profiles"
        padded={false}
        actions={
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={exporting || loading}
            onClick={exportProfiles}
          >
            {exporting ? '…' : 'Download CSV'}
          </button>
        }
      >
        <div className="admin-panel__body">
          <div className="admin-desktop-only">
            <AdminCollapsibleFilters
              quickSearch={<AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />}
              activeChips={[statusFilter !== 'ALL' ? statusFilterLabel(statusFilter) : null, activityFilter ? ACTIVITY_FILTERS.find((f) => f.value === activityFilter)?.label : null, search.trim()].filter(Boolean)}
              activeCount={[statusFilter !== 'ALL', activityFilter, search.trim()].filter(Boolean).length}
            >
              <AdminToolbar className="admin-toolbar--mobile-compact">
                <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name or email…" />
                <FilterSelect
                  label="Status"
                  value={statusFilter}
                  onChange={(e) => setStatusFilterAndUrl(e.target.value)}
                  options={STATUS_FILTERS.map((s) => ({
                    value: s,
                    label: statusFilterLabel(s),
                  }))}
                />
                <FilterSelect
                  label="Activity"
                  value={activityFilter}
                  onChange={(e) => setActivityFilterAndUrl(e.target.value)}
                  options={ACTIVITY_FILTERS}
                />
              </AdminToolbar>
            </AdminCollapsibleFilters>
          </div>

          {loading ? (
            <div className="admin-skeleton" style={{ margin: '0 18px 16px' }} />
          ) : profiles.length === 0 ? (
            <AdminEmptyState title="No profiles" description="Try another filter or add a profile." />
          ) : (
            <>
            <AdminDataList
              desktop={
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Therapist</th>
                        <th>Services</th>
                        <th>Primary CM</th>
                        {showLastLogColumn ? <th>Last session log</th> : null}
                        <th>Status</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {profiles.map((p) => (
                        <tr key={profileRowKey(p)}>
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
                          {showLastLogColumn ? (
                            <td>{formatLastSessionLog(p)}</td>
                          ) : null}
                          <td><StatusBadge status={profileDisplayStatus(p)} /></td>
                          <td>
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              onClick={() => {
                                setDrawerTab('review')
                                setSelected(p)
                                setEditingSupervisor(false)
                                setEditingServices(false)
                              }}
                            >
                              {p.status === 'NEEDS_LISTING' ? 'Create' : 'Review'}
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
                  {profiles.map((p) => (
                    <li key={profileRowKey(p)}>
                      <AdminTaskCard
                        title={p.display_name || p.full_name}
                        meta={[p.email, showLastLogColumn ? `Last log: ${formatLastSessionLog(p)}` : null].filter(Boolean).join(' · ')}
                        badges={<StatusBadge status={profileDisplayStatus(p)} />}
                        actions={
                          <button
                            type="button"
                            className="admin-btn admin-btn--primary admin-btn--sm"
                            onClick={() => {
                              setDrawerTab('review')
                              setSelected(p)
                              setEditingSupervisor(false)
                              setEditingServices(false)
                            }}
                          >
                            {p.status === 'NEEDS_LISTING' ? 'Create' : 'Review'}
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
            <PeopleListPagination
              page={page}
              totalPages={listMeta.pages}
              total={listMeta.total}
              rangeStart={rangeStart}
              rangeEnd={rangeEnd}
              onPageChange={setPage}
            />
            </>
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
                    <StatusBadge status={profileDisplayStatus(selected)} />
                  </div>
                </div>
                <div className="admin-btn-group">
                  {selected.status !== 'NEEDS_LISTING' ? (
                    <>
                      <button
                        type="button"
                        className={`admin-btn admin-btn--sm ${drawerTab === 'review' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
                        onClick={() => setDrawerTab('review')}
                      >
                        Review
                      </button>
                      <button
                        type="button"
                        className={`admin-btn admin-btn--sm ${drawerTab === 'documents' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
                        onClick={() => setDrawerTab('documents')}
                      >
                        Documents
                      </button>
                    </>
                  ) : null}
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={closeDrawer}>
                    Close
                  </button>
                </div>
              </div>
            </header>

            <div className="therapist-profile-drawer__body">
              {drawerTab === 'documents' && selected.status !== 'NEEDS_LISTING' ? (
                <section className="therapist-profile-drawer__section">
                  <h3 className="therapist-profile-drawer__section-title">Vault documents</h3>
                  <AdminTherapistVaultPanel therapistUserId={selected.user_id} canReview={canEditProfiles} />
                </section>
              ) : null}
              {drawerTab === 'review' && selected.status === 'NEEDS_LISTING' ? (
                <section className="therapist-profile-drawer__section">
                  <p className="therapist-profile-drawer__text">
                    This therapist account does not have a service listing yet. Pending and deleted listings are tracked separately.
                  </p>
                  {canEditProfiles ? (
                    <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => openNeedsListingCreate(selected)}>
                      Create service profile
                    </button>
                  ) : null}
                </section>
              ) : null}

              {drawerTab === 'review' && selected.status !== 'NEEDS_LISTING' ? (
                <>
              <ProfileChangesSection profile={selected} categories={categories} />

              {(selected.short_bio || selected.academic_qualification_level || selected.academic_qualifications || (selected.professional_certificates || []).length) ? (
                <section className="therapist-profile-drawer__section">
                  <h3 className="therapist-profile-drawer__section-title">Profile</h3>
                  {selected.short_bio ? <p className="therapist-profile-drawer__text">{selected.short_bio}</p> : null}
                  {selected.academic_qualification_level ? (
                    <p className="therapist-profile-drawer__text" style={{ marginTop: 8, color: '#64748b' }}>
                      <strong>Highest qualification:</strong>{' '}
                      {qualificationLevelLabel(selected.academic_qualification_level)}
                    </p>
                  ) : null}
                  {selected.academic_qualifications ? (
                    <p className="therapist-profile-drawer__text" style={{ marginTop: 8, color: '#64748b' }}>
                      <strong>Additional details:</strong> {selected.academic_qualifications}
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
                  <h3 className="therapist-profile-drawer__section-title">Case manager, mentor & start date</h3>
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
                      staff={mentorDirectory}
                      allowEmpty
                      emptyLabel="No mentor"
                    />
                    <label className="admin-filter-field" style={{ gridColumn: '1 / -1' }}>
                      <span className="admin-filter-field__label">Start date</span>
                      <input
                        type="date"
                        className="admin-input"
                        value={editSupervisor.employmentStartDate || ''}
                        onChange={(e) => setEditSupervisor((s) => ({ ...s, employmentStartDate: e.target.value }))}
                      />
                    </label>
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
                    <div>
                      <dt>Start date</dt>
                      <dd>
                        {selected.employment_start_date
                          ? new Date(selected.employment_start_date).toLocaleDateString('en-IN', {
                              day: 'numeric',
                              month: 'short',
                              year: 'numeric',
                            })
                          : 'Not set'}
                      </dd>
                    </div>
                  </dl>
                )}
              </section>

              {selected.quality ? (
                <section className="therapist-profile-drawer__section">
                  <h3 className="therapist-profile-drawer__section-title">
                    Quality score · {selected.quality.percent}%
                    {selected.quality.auto_pass ? ' · would auto-publish' : ''}
                  </h3>
                  {selected.quality.reminders?.length ? (
                    <ul className="therapist-profile-drawer__text">
                      {selected.quality.reminders.map((row) => (
                        <li key={row.key}>{row.message}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="therapist-profile-drawer__text">All quality checks passed.</p>
                  )}
                </section>
              ) : null}

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
                {canEditProfiles && selected.status === 'DELETED' ? (
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => handleRestore(selected.id)}>
                    Restore as paused
                  </button>
                ) : null}
                {canEditProfiles &&
                (selected.status === 'PENDING' ||
                  selected.status === 'CHANGES_REQUESTED' ||
                  selected.has_pending_changes) ? (
                  <>
                    <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => act('approve', selected.id)}>
                      Approve
                    </button>
                    <button
                      type="button"
                      className="admin-btn admin-btn--secondary admin-btn--sm"
                      onClick={() => act('request-changes', selected.id)}
                    >
                      Request changes
                    </button>
                  </>
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
                {canEditProfiles && selected.id && selected.status !== 'DELETED' && selected.status !== 'NEEDS_LISTING' ? (
                  <button type="button" className="admin-btn admin-btn--danger admin-btn--sm" onClick={() => handleDelete(selected.id)}>
                    Delete
                  </button>
                ) : null}
              </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
