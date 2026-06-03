import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList, fetchAllPages } from '../../lib/listApi.js'
import { AdminStaffDirectoryReadOnly } from './AdminStaffDirectoryReadOnly.jsx'
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
  CopyLinkButton,
  PeopleRowActions,
  PeopleBulkToolbar,
  PeopleSelectCheckbox,
  ClientCaseAccessModal,
} from './ui/index.js'
import { accountStatusLabel, accountStatusTone, clientAccountStatus, clientStatusHint } from '../../lib/accountStatus.js'

export function AdminPeoplePage() {
  const { can, user, isViewOnly } = useAuth()
  const isHrPortal = (user?.roles || []).includes('HR')
  const canManageUsers = can('user.manage') && !isViewOnly
  const canReadStaffDirectory = (canManageUsers || can('user.read')) && !isViewOnly
  const canReadTherapists = canManageUsers || canReadStaffDirectory || can('therapist.read')
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
  const [rowBusy, setRowBusy] = useState(null)
  const [lastProvision, setLastProvision] = useState(null)
  const [selectedTherapistIds, setSelectedTherapistIds] = useState(() => new Set())
  const [selectedClientUserIds, setSelectedClientUserIds] = useState(() => new Set())
  const [clientAccessFamily, setClientAccessFamily] = useState(null)
  const [usersTotal, setUsersTotal] = useState(0)
  const [userSearchDebounced, setUserSearchDebounced] = useState('')

  useEffect(() => {
    const t = searchParams.get('tab')
    if (t && ['staff', 'therapists', 'clients'].includes(t)) setTab(t)
  }, [searchParams])

  useEffect(() => {
    if (tab !== 'clients') return
    const t = setTimeout(() => setFamilySearchDebounced(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search, tab])

  useEffect(() => {
    if (tab === 'clients') return
    const t = setTimeout(() => setUserSearchDebounced(search.trim()), 300)
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

      async function loadDirectoryUsers() {
        const buildQs = (page, pageSize) => {
          const p = new URLSearchParams({
            page: String(page),
            page_size: String(pageSize),
            sort: 'created_at_desc',
          })
          if (userSearchDebounced) p.set('search', userSearchDebounced)
          return p.toString()
        }
        if (userSearchDebounced) {
          const data = await apiFetch(`/api/v1/admin/users?${buildQs(1, 100)}`)
          const items = unwrapList(data)
          return { items, total: data.total ?? items.length }
        }
        return fetchAllPages((page, pageSize) =>
          apiFetch(`/api/v1/admin/users?${buildQs(page, pageSize)}`),
        )
      }

      const userFetch = canReadStaffDirectory
        ? loadDirectoryUsers()
        : canReadTherapists
          ? apiFetch('/api/v1/admin/users/directory?roles=THERAPIST&active_only=false')
          : Promise.resolve({ items: [], total: 0 })
      const modulesFetch = canManageUsers ? apiFetch('/api/v1/admin/modules') : Promise.resolve({ modules: [], role_defaults: {} })
      const rbacFetch = canManageUsers
        ? apiFetch('/api/v1/admin/rbac/catalog').catch(() => null)
        : Promise.resolve(null)
      const [userResult, moduleMeta, rbacMeta, profileRows, clientRows, inviteRows] = await Promise.all([
        userFetch,
        modulesFetch,
        rbacFetch,
        canReadTherapists ? apiFetch('/api/v1/admin/therapist-profiles') : Promise.resolve([]),
        apiFetch(`/api/v1/admin/families${familyQs}`),
        canManageUsers ? apiFetch('/api/v1/admin/invites').catch(() => []) : Promise.resolve([]),
      ])
      const normalizedUsers = canReadStaffDirectory
        ? userResult.items
        : (Array.isArray(userResult) ? userResult : userResult.items || []).map((u) => ({
            id: u.id,
            email: u.email,
            full_name: u.full_name,
            roles: u.roles || ['THERAPIST'],
            is_active: u.is_active ?? true,
            module_assignments: u.module_assignments || [],
          }))
      setUsers(normalizedUsers)
      setUsersTotal(canReadStaffDirectory ? userResult.total : normalizedUsers.length)
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
  }, [tab, familySearchDebounced, userSearchDebounced, canManageUsers, canReadStaffDirectory, canReadTherapists])

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
  const filterText = (hay) =>
    !q || hay.toLowerCase().includes(q) || (canReadStaffDirectory && userSearchDebounced)

  const usersTruncated = canReadStaffDirectory && users.length < usersTotal

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

  const canCreateCase = can('case.create')

  function clientCases(f) {
    if (f.cases?.length) return f.cases
    return (f.caseCodes || []).map((code) => ({ caseId: null, caseCode: code }))
  }

  function toggleSet(setter, id) {
    setter((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function clientUserFromFamily(f) {
    const primary = f.parents?.[0]
    if (!primary?.userId) return null
    return {
      id: primary.userId,
      email: primary.parentEmail,
      full_name: primary.parentName,
      is_active: primary.parentIsActive,
      login_ready: primary.parentLoginReady,
      invite_status: f.pendingInvite ? 'pending' : undefined,
      pending_invite_url: f.pendingInvite?.inviteUrl,
      _reactivateCaseId:
        f.allCasesClosed && primary.parentIsActive !== false ? f.primaryCaseId : null,
    }
  }

  async function invitePendingParent(f) {
    if (f.pendingInvite?.inviteId) {
      setError('')
      try {
        await apiFetch(`/api/v1/admin/invites/${f.pendingInvite.inviteId}/resend-email`, {
          method: 'POST',
        })
        setSuccess(`Invite resent to ${f.pendingInvite.pendingEmail}.`)
      } catch (err) {
        setError(err.message || 'Could not resend invite')
      }
      return
    }
    const primary = f.parents?.[0]
    if (primary?.userId) {
      await inviteParent(primary.userId, f.childId, primary.parentEmail)
    }
  }

  function clientRowActions(f) {
    const primary = f.parents?.[0]
    const clientUser = clientUserFromFamily(f)
    const secondary = []
    if (!f.hasOpenCase && canCreateCase) {
      secondary.push(
        <Link key="allot" to="/admin/cases?allot=1" className="admin-btn admin-btn--ghost admin-btn--sm">
          Allot case
        </Link>,
      )
    }
    if (!primary && !f.pendingInvite) {
      secondary.push(
        <button
          key="add-parent"
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() => setShowFamilyWizard(true)}
        >
          Add parent
        </button>,
      )
    }
    if (clientUser && canManageUsers) {
      return (
        <div className="admin-btn-group admin-btn-group--wrap">
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => setClientAccessFamily(f)}
          >
            Edit access
          </button>
          <PeopleRowActions
            user={clientUser}
            rowBusy={rowBusy}
            setRowBusy={setRowBusy}
            onReload={load}
            onSuccess={setSuccess}
            onError={setError}
            lastProvision={lastProvision}
            setLastProvision={setLastProvision}
            extraActions={secondary}
          />
        </div>
      )
    }
    if (f.pendingInvite && canManageUsers) {
      return (
        <div className="admin-btn-group admin-btn-group--wrap">
          {secondary}
          <CopyLinkButton url={f.pendingInvite.inviteUrl} label="Copy invite link" />
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => invitePendingParent(f)}
          >
            Resend invite
          </button>
        </div>
      )
    }
    return <div className="admin-btn-group admin-btn-group--wrap">{secondary}</div>
  }

  function therapistRowActions(u) {
    const profileHref = `/admin/therapist-profiles?user_id=${u.id}`
    return (
      <div className="admin-btn-group admin-btn-group--wrap">
        <Link to={profileHref} className="admin-btn admin-btn--ghost admin-btn--sm">
          Edit access
        </Link>
        {canManageUsers ? (
          <PeopleRowActions
            user={u}
            rowBusy={rowBusy}
            setRowBusy={setRowBusy}
            onReload={load}
            onSuccess={setSuccess}
            onError={setError}
            lastProvision={lastProvision}
            setLastProvision={setLastProvision}
          />
        ) : null}
      </div>
    )
  }

  function clientStatusBadges(f) {
    const status = clientAccountStatus(f)
    const hint = clientStatusHint(f)
    const badges = [
      <StatusBadge key="status" tone={accountStatusTone(status)}>
        {status}
      </StatusBadge>,
    ]
    if (hint) {
      badges.push(
        <span key="hint" className="admin-muted" style={{ fontSize: '0.75rem' }}>
          {hint}
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
      {usersTruncated ? (
        <p className="admin-alert admin-alert--warn">
          Showing {users.length} of {usersTotal} users. Search by email or name to find someone, or contact
          Super Admin if the directory looks incomplete.
        </p>
      ) : null}
      {inviteUrl ? (
        <p className="admin-alert" style={{ wordBreak: 'break-all', fontSize: '0.875rem' }}>
          Invite link: <CopyLinkButton url={inviteUrl} label="Copy" copiedLabel="Copied" /> {inviteUrl}
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

          {tab === 'staff' && canReadStaffDirectory && !canManageUsers ? (
            <AdminStaffDirectoryReadOnly staff={filteredStaff} />
          ) : null}

          {tab === 'staff' && !canReadStaffDirectory ? (
            <AdminPanel title="Staff">
              <AdminEmptyState
                title="Directory access required"
                description="Your role cannot view the staff directory. Contact an administrator or HR."
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
                  <>
                    {canManageUsers ? (
                      <PeopleBulkToolbar
                        selectedUserIds={[...selectedTherapistIds]}
                        onReload={() => {
                          setSelectedTherapistIds(new Set())
                          load()
                        }}
                        onSuccess={setSuccess}
                        onError={setError}
                      />
                    ) : null}
                  <AdminDataList
                    desktop={
                      <div className="admin-table-wrap">
                        <table className="admin-table">
                          <thead>
                            <tr>
                              {canManageUsers ? <th style={{ width: 36 }} aria-label="Select" /> : null}
                              <th>ID</th>
                              <th>Name</th>
                              <th>Email</th>
                              <th>Phone</th>
                              <th>Profile</th>
                              <th>Status</th>
                              <th>Primary CM</th>
                              <th>Services</th>
                              {canManageUsers ? <th>Actions</th> : null}
                            </tr>
                          </thead>
                          <tbody>
                            {filteredTherapists.map((u) => {
                              const prof = profileByUser.get(u.id)
                              return (
                                <tr key={u.id}>
                                  {canManageUsers ? (
                                    <td>
                                      <PeopleSelectCheckbox
                                        checked={selectedTherapistIds.has(u.id)}
                                        onChange={() => toggleSet(setSelectedTherapistIds, u.id)}
                                        ariaLabel={`Select ${u.full_name}`}
                                      />
                                    </td>
                                  ) : null}
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
                                  <td>
                                    <StatusBadge tone={accountStatusTone(accountStatusLabel(u))}>
                                      {accountStatusLabel(u)}
                                    </StatusBadge>
                                  </td>
                                  <td>{prof?.supervisor_name || '—'}</td>
                                  <td>{(prof?.services_offered || u.module_assignments || []).join(', ') || '—'}</td>
                                  {canManageUsers ? <td>{therapistRowActions(u)}</td> : null}
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
                                  <>
                                    <StatusBadge tone={accountStatusTone(accountStatusLabel(u))}>
                                      {accountStatusLabel(u)}
                                    </StatusBadge>
                                    {prof ? (
                                      <StatusBadge status={prof.status} />
                                    ) : (
                                      <span className="admin-muted">No profile</span>
                                    )}
                                  </>
                                }
                                actions={
                                  canManageUsers ? (
                                    therapistRowActions(u)
                                  ) : (
                                    <Link to={profileHref} className="admin-btn admin-btn--primary admin-btn--sm">
                                      {prof ? 'Open profile' : 'Create profile'}
                                    </Link>
                                  )
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
                  </>
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
                onAddFamily={() => setShowFamilyWizard(true)}
                onSuccess={setSuccess}
                onError={setError}
                onReload={load}
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
                  <>
                    {canManageUsers ? (
                      <PeopleBulkToolbar
                        selectedUserIds={[...selectedClientUserIds]}
                        onReload={() => {
                          setSelectedClientUserIds(new Set())
                          load()
                        }}
                        onSuccess={setSuccess}
                        onError={setError}
                      />
                    ) : null}
                  <AdminDataList
                    desktop={
                      <div className="admin-table-wrap">
                        <table className="admin-table">
                          <thead>
                            <tr>
                              {canManageUsers ? <th style={{ width: 36 }} aria-label="Select" /> : null}
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
                              const clientUser = clientUserFromFamily(f)
                              const firstCase = clientCases(f)[0]
                              const childHref = firstCase?.caseId
                                ? `/admin/cases/${firstCase.caseId}`
                                : canCreateCase
                                  ? '/admin/cases?allot=1'
                                  : null
                              return (
                                <tr key={f.childId}>
                                  {canManageUsers ? (
                                    <td>
                                      {clientUser ? (
                                        <PeopleSelectCheckbox
                                          checked={selectedClientUserIds.has(clientUser.id)}
                                          onChange={() => toggleSet(setSelectedClientUserIds, clientUser.id)}
                                          ariaLabel={`Select parent for ${f.childName}`}
                                        />
                                      ) : null}
                                    </td>
                                  ) : null}
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
                                    <StatusBadge tone={accountStatusTone(clientAccountStatus(f))}>
                                      {clientAccountStatus(f)}
                                    </StatusBadge>
                                    {clientStatusHint(f) ? (
                                      <span className="admin-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                                        {clientStatusHint(f)}
                                      </span>
                                    ) : null}
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
                  </>
                )}
              </AdminPanel>
            </>
          )}

        </>
      )}

      <ClientCaseAccessModal
        family={clientAccessFamily}
        open={!!clientAccessFamily}
        onClose={() => setClientAccessFamily(null)}
        onSuccess={(msg) => {
          setSuccess(msg)
          load()
        }}
        onError={setError}
      />

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
