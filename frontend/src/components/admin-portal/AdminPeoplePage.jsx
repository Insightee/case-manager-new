import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminAddFamilyWizard } from './AdminAddFamilyWizard.jsx'
import { AdminClientOnboardPanel } from './AdminClientOnboardPanel.jsx'
import { AdminTherapistOnboardPanel } from './AdminTherapistOnboardPanel.jsx'
import { AdminStaffManageSection } from './AdminStaffManageSection.jsx'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminMobilePillTabs,
  AdminPageHeader,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
} from './ui/index.js'

export function AdminPeoplePage() {
  const { can, user, isViewOnly } = useAuth()
  const isHrPortal = (user?.roles || []).includes('HR')
  const canManageUsers = can('user.manage') && !isViewOnly
  const canReadTherapists = canManageUsers || can('therapist.read')
  const [searchParams, setSearchParams] = useSearchParams()
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
  const [showFamilyWizard, setShowFamilyWizard] = useState(false)
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

  async function inviteParent(userId, childId, parentEmail) {
    setError('')
    try {
      const qs = childId ? `?child_id=${childId}` : ''
      const res = await apiFetch(`/api/v1/admin/families/${userId}/invite${qs}`, {
        method: 'POST',
        timeoutMs: 20_000,
      })
      const email = res.email || parentEmail || 'parent'
      setInviteUrl(res.invite_url)
      setSuccess(`Parent invite link generated for ${email}. Email is sent separately — copy the link if needed.`)
    } catch (err) {
      setError(err.message || 'Invite failed')
    }
  }

  function copyLink(url) {
    navigator.clipboard?.writeText(url)
    setSuccess('Link copied to clipboard')
  }

  const canCreateCase = can('case.create')

  function clientCases(f) {
    if (f.cases?.length) return f.cases
    return (f.caseCodes || []).map((code) => ({ caseId: null, caseCode: code }))
  }

  function clientStatusBadges(f) {
    const badges = []
    if (!f.hasParent && !f.pendingInvite) {
      badges.push(
        <span key="no-parent" className="admin-chip">
          No parent
        </span>,
      )
    }
    if (f.pendingInvite) {
      badges.push(
        <span key="pending" className="admin-chip">
          Invite pending
        </span>,
      )
    }
    const cases = clientCases(f)
    if (cases.length) {
      badges.push(
        <span key="cases" className="admin-chip">
          {cases.length} case{cases.length > 1 ? 's' : ''}
        </span>,
      )
    }
    return badges
  }

  function clientRowActions(f) {
    const primary = f.parents?.[0]
    return (
      <div className="admin-btn-group">
        {primary?.userId ? (
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => inviteParent(primary.userId, f.childId, primary.parentEmail)}
          >
            Invite parent
          </button>
        ) : null}
        {!f.hasParent && !f.pendingInvite ? (
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => setShowFamilyWizard(true)}
          >
            Add parent
          </button>
        ) : null}
        {isHrPortal ? (
          <Link to="/hr/cases" className="admin-btn admin-btn--primary admin-btn--sm">
            View cases
          </Link>
        ) : canCreateCase ? (
          <Link to="/admin/cases?allot=1" className="admin-btn admin-btn--primary admin-btn--sm">
            Allot case
          </Link>
        ) : null}
      </div>
    )
  }

  function renderClientCaseLinks(f) {
    const cases = clientCases(f)
    if (!cases.length) return '—'
    return cases.map((c, i) => (
      <span key={c.caseId || c.caseCode || i}>
        {i > 0 ? ', ' : null}
        {c.caseId ? (
          <Link to={`/admin/cases/${c.caseId}`}>{c.caseCode}</Link>
        ) : (
          c.caseCode
        )}
      </span>
    ))
  }

  const tabs = [
    { id: 'staff', label: 'Staff' },
    { id: 'therapists', label: 'Therapists' },
    { id: 'clients', label: 'Clients' },
  ]

  function changeTab(id) {
    setTab(id)
    setSearch('')
    setSearchParams({ tab: id }, { replace: true })
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Directory"
        title="People"
        subtitle="Staff, therapists, and clients — onboard with invites, family wizard, or bulk import."
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

      <AdminMobilePillTabs
        ariaLabel="People sections"
        activeId={tab}
        onChange={changeTab}
        primaryIds={tabs.map((t) => t.id)}
        overflowIds={[]}
        tabs={tabs}
      />

      <nav className="admin-desktop-only admin-page__tabs-scroll portal-tabs" style={{ marginBottom: 16 }} aria-label="People sections">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`portal-tabs__tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => changeTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div className="admin-people-search admin-mobile-only">
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search people…" />
      </div>

      <div className="admin-desktop-only">
        <AdminCollapsibleFilters
          quickSearch={<AdminSearchInput value={search} onChange={setSearch} placeholder="Search…" />}
          activeChips={search.trim() ? [search.trim()] : []}
          activeCount={search.trim() ? 1 : 0}
        >
          <AdminToolbar className="admin-toolbar--mobile-compact">
            <AdminSearchInput value={search} onChange={setSearch} placeholder="Search…" />
          </AdminToolbar>
        </AdminCollapsibleFilters>
      </div>

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
                  <AdminDataList
                    desktop={
                      <div className="admin-table-wrap">
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
                      </div>
                    }
                    mobile={
                      <ul className="admin-data-list__cards">
                        {filteredTherapists.map((u) => {
                          const prof = profileByUser.get(u.id)
                          const profileHref = `/admin/therapist-profiles?user_id=${u.id}${prof?.status === 'PENDING' ? '&status=PENDING' : prof?.status ? `&status=${prof.status}` : ''}`
                          return (
                            <li key={u.id}>
                              <AdminTaskCard
                                title={
                                  <Link to={profileHref} style={{ color: 'inherit', textDecoration: 'none' }}>
                                    {u.full_name}
                                  </Link>
                                }
                                meta={[u.email, u.phone].filter(Boolean).join(' · ')}
                                badges={
                                  prof ? (
                                    <StatusBadge status={prof.status} />
                                  ) : (
                                    <span className="admin-muted">No profile</span>
                                  )
                                }
                                actions={
                                  <Link to={profileHref} className="admin-btn admin-btn--primary admin-btn--sm">
                                    {prof ? 'Open profile' : 'Create profile'}
                                  </Link>
                                }
                              >
                                <p>
                                  Primary CM: {prof?.supervisor_name || '—'}
                                  <br />
                                  Services: {(prof?.services_offered || u.module_assignments || []).join(', ') || '—'}
                                </p>
                              </AdminTaskCard>
                            </li>
                          )
                        })}
                      </ul>
                    }
                  />
                )}
              </AdminPanel>
            </>
          )}

          {tab === 'clients' && (
            <>
              <AdminClientOnboardPanel
                canCreateCase={canCreateCase}
                canManageUsers={canManageUsers}
                isHrPortal={isHrPortal}
                pendingInvites={parentPendingInvites}
                onCopyLink={copyLink}
                onAddFamily={() => setShowFamilyWizard(true)}
              />
              <AdminPanel
                title={`Clients (${filteredClients.length})`}
                actions={
                  canCreateCase ? (
                    <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
                      Case list
                    </Link>
                  ) : null
                }
              >
                {filteredClients.length === 0 ? (
                  <AdminEmptyState
                    title="No clients yet"
                    description="Use Add client & case, Add family, or Bulk import above."
                  />
                ) : (
                  <AdminDataList
                    desktop={
                      <div className="admin-table-wrap">
                        <table className="admin-table">
                          <thead>
                            <tr>
                              <th>ID</th>
                              <th>Child</th>
                              <th>Parent</th>
                              <th>Email</th>
                              <th>Phone</th>
                              <th>Status</th>
                              <th>Cases</th>
                              <th>Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {filteredClients.map((f) => {
                              const primary = f.parents?.[0]
                              const firstCase = clientCases(f)[0]
                              const childHref = firstCase?.caseId
                                ? `/admin/cases/${firstCase.caseId}`
                                : canCreateCase
                                  ? '/admin/cases?allot=1'
                                  : null
                              return (
                                <tr key={f.childId}>
                                  <td className="admin-muted">{f.childId}</td>
                                  <td>
                                    {childHref ? (
                                      <Link to={childHref}>{f.childName}</Link>
                                    ) : (
                                      f.childName
                                    )}
                                  </td>
                                  <td>
                                    {primary?.parentName ||
                                      (f.pendingInvite ? `Pending: ${f.pendingInvite.pendingEmail}` : '—')}
                                  </td>
                                  <td>{primary?.parentEmail || '—'}</td>
                                  <td>{primary?.parentPhone || '—'}</td>
                                  <td>
                                    <div className="admin-chip-row admin-chip-row--wrap">{clientStatusBadges(f)}</div>
                                  </td>
                                  <td>{renderClientCaseLinks(f)}</td>
                                  <td>{clientRowActions(f)}</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                      </div>
                    }
                    mobile={
                      <ul className="admin-data-list__cards">
                        {filteredClients.map((f) => {
                        const primary = f.parents?.[0]
                        const firstCase = clientCases(f)[0]
                        const childHref = firstCase?.caseId
                          ? `/admin/cases/${firstCase.caseId}`
                          : canCreateCase
                            ? '/admin/cases?allot=1'
                            : null
                        const metaParts = primary
                          ? [primary.parentName, primary.parentEmail, primary.parentPhone].filter(Boolean)
                          : f.pendingInvite
                            ? [`Pending: ${f.pendingInvite.pendingEmail}`]
                            : ['No parent linked']
                        return (
                          <li key={f.childId}>
                            <AdminTaskCard
                              title={
                                childHref ? (
                                  <Link to={childHref} style={{ color: 'inherit', textDecoration: 'none' }}>
                                    {f.childName}
                                  </Link>
                                ) : (
                                  f.childName
                                )
                              }
                              meta={metaParts.join(' · ')}
                              badges={clientStatusBadges(f)}
                              actions={clientRowActions(f)}
                            >
                              {clientCases(f).length ? (
                                <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
                                  Cases: {renderClientCaseLinks(f)}
                                </p>
                              ) : null}
                            </AdminTaskCard>
                          </li>
                        )
                        })}
                      </ul>
                    }
                  />
                )}
              </AdminPanel>
            </>
          )}

        </>
      )}

      {showFamilyWizard ? (
        <div
          className="admin-drawer-backdrop"
          role="presentation"
          onClick={() => setShowFamilyWizard(false)}
        >
          <div
            className="admin-drawer admin-drawer--wide"
            role="dialog"
            aria-labelledby="add-family-title"
            onClick={(e) => e.stopPropagation()}
          >
            <header className="admin-drawer__header">
              <h2 id="add-family-title" className="admin-drawer__title">
                Add family
              </h2>
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={() => setShowFamilyWizard(false)}
              >
                Close
              </button>
            </header>
            <div className="admin-drawer__body">
              <AdminAddFamilyWizard
                onComplete={() => {
                  setShowFamilyWizard(false)
                  setSuccess('Family saved.')
                  load()
                }}
                onCancel={() => setShowFamilyWizard(false)}
              />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
