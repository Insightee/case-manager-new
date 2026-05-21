import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { AdminTherapistOnboardPanel } from './AdminTherapistOnboardPanel.jsx'
import { AdminAddFamilyWizard } from './AdminAddFamilyWizard.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar, StatusBadge } from './ui/index.js'

const EMPTY_CHILD = { first_name: '', last_name: '', date_of_birth: '' }

export function AdminPeoplePage() {
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState(() => searchParams.get('tab') || 'staff')
  const [users, setUsers] = useState([])
  const [profiles, setProfiles] = useState([])
  const [families, setFamilies] = useState([])
  const [invites, setInvites] = useState([])
  const [catalog, setCatalog] = useState([])
  const [roleDefaults, setRoleDefaults] = useState({})
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [childForm, setChildForm] = useState(EMPTY_CHILD)
  const [submitting, setSubmitting] = useState(false)
  const [showFamilyWizard, setShowFamilyWizard] = useState(false)
  const [familySearchDebounced, setFamilySearchDebounced] = useState('')

  useEffect(() => {
    const t = searchParams.get('tab')
    if (t && ['staff', 'therapists', 'families'].includes(t)) setTab(t)
  }, [searchParams])

  useEffect(() => {
    if (tab !== 'families') return
    const t = setTimeout(() => setFamilySearchDebounced(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search, tab])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const familyQs =
        tab === 'families' && familySearchDebounced
          ? `?search=${encodeURIComponent(familySearchDebounced)}`
          : ''
      const [userRows, moduleMeta, profileRows, familyRows, inviteRows] = await Promise.all([
        apiFetch('/api/v1/admin/users'),
        apiFetch('/api/v1/admin/modules'),
        apiFetch('/api/v1/admin/therapist-profiles'),
        apiFetch(`/api/v1/admin/families${familyQs}`),
        apiFetch('/api/v1/admin/invites').catch(() => []),
      ])
      setUsers(unwrapList(userRows))
      setCatalog(moduleMeta.modules ?? [])
      setRoleDefaults(moduleMeta.role_defaults ?? {})
      setProfiles(profileRows)
      setFamilies(familyRows)
      setInvites(Array.isArray(inviteRows) ? inviteRows : [])
    } catch (err) {
      setError(err.message || 'Could not load people data')
    } finally {
      setLoading(false)
    }
  }, [tab, familySearchDebounced])

  useEffect(() => {
    load()
  }, [load])

  const profileByUser = useMemo(() => {
    const m = new Map()
    for (const p of profiles) m.set(p.user_id, p)
    return m
  }, [profiles])

  const staff = useMemo(
    () => users.filter((u) => !u.roles?.includes('THERAPIST') && !u.roles?.includes('PARENT')),
    [users],
  )

  const therapists = useMemo(() => users.filter((u) => u.roles?.includes('THERAPIST')), [users])

  const q = search.trim().toLowerCase()
  const filterText = (hay) => !q || hay.toLowerCase().includes(q)

  const filteredStaff = staff.filter(
    (u) => filterText(`${u.full_name} ${u.email} ${(u.roles || []).join(' ')}`),
  )
  const filteredTherapists = therapists.filter((u) => filterText(`${u.full_name} ${u.email}`))
  const filteredFamilies = tab === 'families' ? families : families.filter((f) =>
    filterText(`${f.childName} ${f.parents?.map((p) => p.parentEmail).join(' ')} ${(f.caseCodes || []).join(' ')}`),
  )
  const parentPendingInvites = useMemo(
    () => invites.filter((i) => i.role_name === 'PARENT' && filterText(i.email)),
    [invites, search],
  )
  const therapistPendingInvites = useMemo(
    () => invites.filter((i) => i.role_name === 'THERAPIST' && filterText(i.email)),
    [invites, search],
  )

  async function addChild(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await apiFetch('/api/v1/admin/children', {
        method: 'POST',
        body: JSON.stringify({
          first_name: childForm.first_name.trim(),
          last_name: childForm.last_name.trim(),
          date_of_birth: childForm.date_of_birth || null,
        }),
      })
      setChildForm(EMPTY_CHILD)
      setSuccess('Child added')
      load()
    } catch (err) {
      setError(err.message || 'Could not add child')
    } finally {
      setSubmitting(false)
    }
  }

  async function inviteParent(userId, childId) {
    setError('')
    try {
      const qs = childId ? `?child_id=${childId}` : ''
      const res = await apiFetch(`/api/v1/admin/families/${userId}/invite${qs}`, { method: 'POST' })
      setInviteUrl(res.invite_url)
      setSuccess('Parent invite link generated')
    } catch (err) {
      setError(err.message || 'Invite failed')
    }
  }

  function copyLink(url) {
    navigator.clipboard?.writeText(url)
    setSuccess('Link copied to clipboard')
  }

  const tabs = [
    { id: 'staff', label: 'Staff' },
    { id: 'therapists', label: 'Therapists' },
    { id: 'families', label: 'Families' },
  ]

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Directory"
        title="People"
        subtitle="Staff, therapists, and client families — add therapists with invite or bulk upload."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}
      {inviteUrl ? (
        <p className="admin-alert" style={{ wordBreak: 'break-all', fontSize: '0.875rem' }}>
          Invite link:{' '}
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(inviteUrl)}>
            Copy
          </button>{' '}
          {inviteUrl}
        </p>
      ) : null}

      <nav style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`admin-btn admin-btn--sm ${tab === t.id ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => {
              setTab(t.id)
              setSearch('')
            }}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <AdminToolbar>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search…" />
      </AdminToolbar>

      {tab === 'families' && showFamilyWizard ? (
        <AdminAddFamilyWizard
          onCancel={() => setShowFamilyWizard(false)}
          onComplete={(result) => {
            setShowFamilyWizard(false)
            if (result?.inviteUrl) setInviteUrl(result.inviteUrl)
            setSuccess(result?.case ? 'Family and case created' : 'Family created')
            load()
          }}
        />
      ) : null}

      {tab === 'families' && !showFamilyWizard ? (
        <>
          <div className="admin-btn-group" style={{ marginBottom: 12 }}>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => setShowFamilyWizard(true)}>
              Add family
            </button>
          </div>
          <AdminPanel title="Quick add child" subtitle="Or use Add family to include parent and optional case">
            <form onSubmit={addChild} className="admin-form-grid" style={{ maxWidth: 420, marginBottom: 16 }}>
              <label>
                First name
                <input
                  className="admin-input"
                  value={childForm.first_name}
                  onChange={(e) => setChildForm((c) => ({ ...c, first_name: e.target.value }))}
                  required
                />
              </label>
              <label>
                Last name
                <input
                  className="admin-input"
                  value={childForm.last_name}
                  onChange={(e) => setChildForm((c) => ({ ...c, last_name: e.target.value }))}
                  required
                />
              </label>
              <label>
                Date of birth
                <input
                  type="date"
                  className="admin-input"
                  value={childForm.date_of_birth}
                  onChange={(e) => setChildForm((c) => ({ ...c, date_of_birth: e.target.value }))}
                />
              </label>
              <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={submitting}>
                Add child
              </button>
            </form>
          </AdminPanel>
          {parentPendingInvites.length > 0 ? (
            <AdminPanel title="Pending parent invites" subtitle="Invites not yet accepted">
              <ul className="admin-queue">
                {parentPendingInvites.map((inv) => (
                  <li key={inv.id} className="admin-queue__item">
                    <div>
                      <p className="admin-queue__title">{inv.email}</p>
                      <p className="admin-queue__meta">Expires {new Date(inv.expires_at).toLocaleDateString()}</p>
                    </div>
                    <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(inv.invite_url)}>
                      Copy link
                    </button>
                  </li>
                ))}
              </ul>
            </AdminPanel>
          ) : null}
        </>
      ) : null}

      {loading ? (
        <p className="admin-muted">Loading…</p>
      ) : (
        <>
          {tab === 'staff' && (
            <AdminPanel title={`Staff (${filteredStaff.length})`}>
              {filteredStaff.length === 0 ? (
                <AdminEmptyState title="No staff" description="Try a different search." />
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Roles</th>
                      <th>Modules</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredStaff.map((u) => (
                      <tr key={u.id}>
                        <td>{u.full_name}</td>
                        <td>{u.email}</td>
                        <td>{(u.roles || []).join(', ')}</td>
                        <td>{(u.module_assignments || []).join(', ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </AdminPanel>
          )}

          {tab === 'therapists' && (
            <>
              <AdminTherapistOnboardPanel
                catalog={catalog}
                roleDefaults={roleDefaults}
                pendingInvites={therapistPendingInvites}
                onSuccess={setSuccess}
                onError={setError}
                onReload={load}
              />
              <AdminPanel
                title={`Therapists (${filteredTherapists.length})`}
                actions={
                  <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                    Profile editor
                  </Link>
                }
              >
                {filteredTherapists.length === 0 ? (
                  <AdminEmptyState title="No therapists yet" description="Use Add therapist or Bulk upload above." />
                ) : (
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Phone</th>
                        <th>Profile</th>
                        <th>Modules</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTherapists.map((u) => {
                        const prof = profileByUser.get(u.id)
                        return (
                          <tr key={u.id}>
                            <td className="admin-muted">{u.id}</td>
                            <td>
                              <Link
                                to={`/admin/therapist-profiles?user_id=${u.id}${prof?.status === 'PENDING' ? '&status=PENDING' : ''}`}
                              >
                                {u.full_name}
                              </Link>
                            </td>
                            <td>{u.email}</td>
                            <td>{u.phone || '—'}</td>
                            <td>
                              {prof ? (
                                <Link to={`/admin/therapist-profiles?user_id=${u.id}&status=${prof.status}`}>
                                  <StatusBadge status={prof.status} />
                                </Link>
                              ) : (
                                <Link to={`/admin/therapist-profiles?user_id=${u.id}`} className="admin-muted">
                                  No profile
                                </Link>
                              )}
                            </td>
                            <td>{(u.module_assignments || []).join(', ') || '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </AdminPanel>
            </>
          )}

          {tab === 'families' && (
            <AdminPanel title={`Families (${filteredFamilies.length})`}>
              {filteredFamilies.length === 0 ? (
                <AdminEmptyState title="No families" description="Use Add family or quick add child to get started." />
              ) : (
                <ul className="admin-queue">
                  {filteredFamilies.map((f) => (
                    <li key={f.childId} className="admin-queue__item">
                      <div>
                        <p className="admin-queue__title">
                          {f.childName}
                          {!f.hasParent && !f.pendingInvite ? (
                            <span className="admin-badge admin-badge--warn" style={{ marginLeft: 8 }}>
                              No parent
                            </span>
                          ) : null}
                          {f.pendingInvite ? (
                            <span className="admin-badge" style={{ marginLeft: 8 }}>
                              Invite pending
                            </span>
                          ) : null}
                          {f.caseCodes?.length ? (
                            <span className="admin-badge admin-badge--ok" style={{ marginLeft: 8 }}>
                              {f.caseCodes.length} case{f.caseCodes.length > 1 ? 's' : ''}
                            </span>
                          ) : null}
                        </p>
                        <p className="admin-queue__meta">
                          {f.parents?.length
                            ? f.parents.map((p) => `${p.parentName} · ${p.parentEmail}`).join(' | ')
                            : f.pendingInvite
                              ? `Pending: ${f.pendingInvite.pendingEmail}`
                              : 'No parent linked'}
                          {f.caseCodes?.length ? ` · ${f.caseCodes.join(', ')}` : ''}
                        </p>
                      </div>
                      <div className="admin-btn-group">
                        {f.parents?.[0]?.userId ? (
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => inviteParent(f.parents[0].userId, f.childId)}
                          >
                            Invite parent
                          </button>
                        ) : null}
                        {!f.hasParent && !f.pendingInvite ? (
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => {
                              setShowFamilyWizard(true)
                            }}
                          >
                            Add parent
                          </button>
                        ) : null}
                        <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary admin-btn--sm">
                          Allot case
                        </Link>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </AdminPanel>
          )}

        </>
      )}
    </div>
  )
}
