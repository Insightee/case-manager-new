import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminTherapistOnboardPanel } from './AdminTherapistOnboardPanel.jsx'
import { AdminStaffManageSection } from './AdminStaffManageSection.jsx'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar, StatusBadge } from './ui/index.js'

export function AdminPeoplePage() {
  const navigate = useNavigate()
  const { can, user, isViewOnly } = useAuth()
  const isHrPortal = (user?.roles || []).includes('HR')
  const canManageUsers = can('user.manage') && !isViewOnly
  const canReadTherapists = canManageUsers || can('therapist.read')
  const [searchParams] = useSearchParams()
  const [tab, setTab] = useState(() => searchParams.get('tab') || 'staff')
  const [users, setUsers] = useState([])
  const [profiles, setProfiles] = useState([])
  const [clients, setClients] = useState([])
  const [invites, setInvites] = useState([])
  const [catalog, setCatalog] = useState([])
  const [roleDefaults, setRoleDefaults] = useState({})
  const [assignableRoles, setAssignableRoles] = useState([])
  const [deprecatedRoles, setDeprecatedRoles] = useState([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [familySearchDebounced, setFamilySearchDebounced] = useState('')

  useEffect(() => {
    const t = searchParams.get('tab')
    if (t && ['staff', 'therapists', 'clients'].includes(t)) setTab(t)
  }, [searchParams])

  useEffect(() => {
    if (tab !== 'clients') return
    const t = setTimeout(() => setFamilySearchDebounced(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search, tab])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const familyQs =
        tab === 'clients' && familySearchDebounced
          ? `?search=${encodeURIComponent(familySearchDebounced)}`
          : ''
      const userFetch = canManageUsers
        ? apiFetch('/api/v1/admin/users?page_size=100')
        : canReadTherapists
          ? apiFetch('/api/v1/admin/users/directory?roles=THERAPIST&active_only=false')
          : Promise.resolve([])
      const modulesFetch = canManageUsers ? apiFetch('/api/v1/admin/modules') : Promise.resolve({ modules: [], role_defaults: {} })
      const rbacFetch = canManageUsers
        ? apiFetch('/api/v1/admin/rbac/catalog').catch(() => null)
        : Promise.resolve(null)
      const [userRows, moduleMeta, rbacMeta, profileRows, clientRows, inviteRows] = await Promise.all([
        userFetch,
        modulesFetch,
        rbacFetch,
        canReadTherapists ? apiFetch('/api/v1/admin/therapist-profiles') : Promise.resolve([]),
        apiFetch(`/api/v1/admin/families${familyQs}`),
        canManageUsers ? apiFetch('/api/v1/admin/invites').catch(() => []) : Promise.resolve([]),
      ])
      const normalizedUsers = canManageUsers
        ? unwrapList(userRows)
        : (Array.isArray(userRows) ? userRows : []).map((u) => ({
            id: u.id,
            email: u.email,
            full_name: u.full_name,
            roles: u.roles || ['THERAPIST'],
            is_active: u.is_active ?? true,
            module_assignments: u.module_assignments || [],
          }))
      setUsers(normalizedUsers)
      setCatalog(
        rbacMeta ?? {
          modules: moduleMeta.modules ?? [],
          service_categories: moduleMeta.modules ?? [],
          org_capabilities: [],
          role_defaults: moduleMeta.role_defaults ?? {},
        },
      )
      setRoleDefaults(rbacMeta?.role_defaults ?? moduleMeta.role_defaults ?? {})
      setAssignableRoles(rbacMeta?.assignable_roles ?? [])
      setDeprecatedRoles(rbacMeta?.deprecated_roles ?? [])
      setProfiles(profileRows)
      setClients(clientRows)
      setInvites(Array.isArray(inviteRows) ? inviteRows : [])
    } catch (err) {
      setError(err.message || 'Could not load people data')
    } finally {
      setLoading(false)
    }
  }, [tab, familySearchDebounced, canManageUsers, canReadTherapists])

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
  const filteredClients = tab === 'clients' ? clients : clients.filter((f) =>
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
  const staffPendingInvites = useMemo(
    () => invites.filter((i) => !['THERAPIST', 'PARENT'].includes(i.role_name)),
    [invites],
  )

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
    { id: 'therapists', label: 'Therapist profiles' },
    { id: 'clients', label: 'Clients' },
  ]

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Directory"
        title="People"
        subtitle="Staff, therapist profiles, and client records — add therapists with invite or bulk upload."
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

      {tab === 'clients' ? (
        <>
          <div className="admin-btn-group" style={{ marginBottom: 12 }}>
            <div className="admin-btn-group" style={{ marginBottom: 12 }}>
              {can('case.create') ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--primary admin-btn--sm"
                  onClick={() => navigate('/admin/cases?allot=1')}
                >
                  Add client & case (allotment)
                </button>
              ) : null}
              <Link to="/admin/client-profiles" className="admin-btn admin-btn--secondary admin-btn--sm">
                Client profiles & bulk import
              </Link>
            </div>
          </div>
          {!canManageUsers ? (
            <p className="admin-muted" style={{ marginBottom: 12, fontSize: '0.85rem' }}>
              Families are read-only here. Use case allotment to add a child with a parent account.
            </p>
          ) : null}
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
          {tab === 'staff' && canManageUsers ? (
            <AdminStaffManageSection
              catalog={catalog}
              roleDefaults={roleDefaults}
              assignableRoles={assignableRoles}
              deprecatedRoles={deprecatedRoles}
              staff={filteredStaff}
              pendingInvites={staffPendingInvites}
              onReload={load}
              onSuccess={setSuccess}
              onError={setError}
            />
          ) : null}

          {tab === 'staff' && !canManageUsers ? (
            <AdminPanel title="Staff">
              <AdminEmptyState
                title="Directory access required"
                description="Your role cannot manage staff accounts. Contact an administrator or HR."
              />
            </AdminPanel>
          ) : null}

          {tab === 'therapists' && (
            <>
              {canManageUsers ? (
                <AdminTherapistOnboardPanel
                  roleDefaults={roleDefaults}
                  pendingInvites={therapistPendingInvites}
                  onSuccess={setSuccess}
                  onError={setError}
                  onReload={load}
                />
              ) : (
                <AdminPanel title="Therapists">
                  <AdminEmptyState
                    title="View-only access"
                    description="You cannot add therapists or use bulk upload. Open Profile editor to review listings."
                  />
                </AdminPanel>
              )}
              <AdminPanel
                title={`Therapists (${filteredTherapists.length})`}
                actions={
                  canManageUsers ? (
                    <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                      Profile editor
                    </Link>
                  ) : (
                    <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                      View profiles
                    </Link>
                  )
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
                        <th>Primary CM</th>
                        <th>Services</th>
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
                            <td>{prof?.supervisor_name || '—'}</td>
                            <td>{(prof?.services_offered || u.module_assignments || []).join(', ') || '—'}</td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                )}
              </AdminPanel>
            </>
          )}

          {tab === 'clients' && (
            <AdminPanel title={`Clients (${filteredClients.length})`}>
              {filteredClients.length === 0 ? (
                <AdminEmptyState title="No clients" description="Use Add client or quick add above to get started." />
              ) : (
                <ul className="admin-queue">
                  {filteredClients.map((f) => (
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
                        {isHrPortal ? (
                          <Link to="/hr/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
                            View cases
                          </Link>
                        ) : can('case.create') ? (
                          <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary admin-btn--sm">
                            Allot case
                          </Link>
                        ) : null}
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
