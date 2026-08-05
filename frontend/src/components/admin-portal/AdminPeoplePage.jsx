import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import {
  PEOPLE_PAGE_SIZE,
  THERAPIST_SORT_OPTIONS,
} from '../../lib/peopleDirectoryList.js'
import {
  fetchStaffPage,
  fetchTherapistsPage,
  fetchClientsPage,
  fetchStaffMeta,
  fetchTabInvites,
  fetchParentsAwaitingLogin,
  fetchTherapistProfiles,
  fetchAllTherapists,
  fetchAllClients,
} from '../../lib/peopleDirectoryApi.js'
import { useDebouncedValue } from '../../hooks/useDebouncedValue.js'
import { AdminStaffDirectoryReadOnly } from './AdminStaffDirectoryReadOnly.jsx'
import { useAuth } from '../../context/AuthContext.jsx'
import { AdminClientOnboardPanel } from './AdminClientOnboardPanel.jsx'
import { AdminTherapistOnboardPanel } from './AdminTherapistOnboardPanel.jsx'
import { AdminStaffManageSection } from './AdminStaffManageSection.jsx'
import { AdminAddFamilyWizard } from './AdminAddFamilyWizard.jsx'
import {
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
  TherapistIdCell,
  PeopleListPagination,
} from './ui/index.js'
import { FilterSelect } from './ui/FilterSelect.jsx'
import { accountStatusLabel, accountStatusTone, clientAccountStatus, clientStatusHint } from '../../lib/accountStatus.js'
import { exportClientCsv, exportTherapistCsv } from '../../lib/peopleDirectoryExport.js'

export function AdminPeoplePage() {
  const { can, user, isViewOnly } = useAuth()
  const isHrPortal = (user?.roles || []).includes('HR')
  const canManageUsers = can('user.manage') && !isViewOnly
  const canReadStaffDirectory = (canManageUsers || can('user.read')) && !isViewOnly
  const canReadTherapists = canManageUsers || canReadStaffDirectory || can('therapist.read')
  const [searchParams, setSearchParams] = useSearchParams()
  const [tab, setTab] = useState(() => searchParams.get('tab') || 'staff')
  const [staff, setStaff] = useState([])
  const [staffTotal, setStaffTotal] = useState(0)
  const [staffPage, setStaffPage] = useState(1)
  const [staffSearch, setStaffSearch] = useState('')
  const [staffLoading, setStaffLoading] = useState(false)
  const [therapists, setTherapists] = useState([])
  const [therapistsTotal, setTherapistsTotal] = useState(0)
  const [therapistsPages, setTherapistsPages] = useState(1)
  const [therapistsLoading, setTherapistsLoading] = useState(false)
  const [clients, setClients] = useState([])
  const [clientsTotal, setClientsTotal] = useState(0)
  const [clientsPages, setClientsPages] = useState(1)
  const [clientsLoading, setClientsLoading] = useState(false)
  const [profiles, setProfiles] = useState([])
  const [invites, setInvites] = useState([])
  const [parentsAwaitingLogin, setParentsAwaitingLogin] = useState({ count: 0, items: [] })
  const [catalog, setCatalog] = useState([])
  const [roleDefaults, setRoleDefaults] = useState({})
  const [assignableRoles, setAssignableRoles] = useState([])
  const [staffDepartments, setStaffDepartments] = useState([])
  const [deprecatedRoles, setDeprecatedRoles] = useState([])
  const [metaLoading, setMetaLoading] = useState(false)
  const [reloadToken, setReloadToken] = useState(0)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [inviteUrl, setInviteUrl] = useState('')
  const [showFamilyWizard, setShowFamilyWizard] = useState(false)
  const [rowBusy, setRowBusy] = useState(null)
  const [lastProvision, setLastProvision] = useState(null)
  const [selectedTherapistIds, setSelectedTherapistIds] = useState(() => new Set())
  const [selectedClientUserIds, setSelectedClientUserIds] = useState(() => new Set())
  const [clientAccessFamily, setClientAccessFamily] = useState(null)
  const [pendingInvitesView, setPendingInvitesView] = useState(false)
  const [therapistSort, setTherapistSort] = useState('id_asc')
  const [therapistSearch, setTherapistSearch] = useState('')
  const [clientSearch, setClientSearch] = useState('')
  const [therapistPage, setTherapistPage] = useState(1)
  const [clientPage, setClientPage] = useState(1)

  const staffSearchDebounced = useDebouncedValue(staffSearch)
  const therapistSearchDebounced = useDebouncedValue(therapistSearch)
  const clientSearchDebounced = useDebouncedValue(clientSearch)

  const reload = useCallback(() => setReloadToken((t) => t + 1), [])

  useEffect(() => {
    const t = searchParams.get('tab')
    if (t && ['staff', 'therapists', 'clients'].includes(t)) setTab(t)
  }, [searchParams])

  useEffect(() => {
    setPendingInvitesView(false)
    setTherapistPage(1)
    setClientPage(1)
    setStaffPage(1)
    setTherapistSearch('')
    setClientSearch('')
    setStaffSearch('')
  }, [tab])

  useEffect(() => {
    if (tab === 'therapists') setTherapistPage(1)
  }, [therapistSearchDebounced, therapistSort, tab])

  useEffect(() => {
    if (tab === 'clients') setClientPage(1)
  }, [clientSearchDebounced, tab])

  useEffect(() => {
    if (tab === 'staff') setStaffPage(1)
  }, [staffSearchDebounced, tab])

  useEffect(() => {
    if (tab !== 'staff' || !canReadStaffDirectory) return undefined
    let cancelled = false
    setStaffLoading(true)
    setError('')
    fetchStaffPage({ page: staffPage, search: staffSearchDebounced })
      .then((data) => {
        if (cancelled) return
        setStaff(data.items || [])
        setStaffTotal(data.total || 0)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load staff')
      })
      .finally(() => {
        if (!cancelled) setStaffLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tab, staffPage, staffSearchDebounced, canReadStaffDirectory, reloadToken])

  useEffect(() => {
    if (tab !== 'therapists' || !canReadTherapists) return undefined
    let cancelled = false
    setTherapistsLoading(true)
    setError('')
    fetchTherapistsPage({
      page: therapistPage,
      search: therapistSearchDebounced,
      sort: therapistSort,
    })
      .then((data) => {
        if (cancelled) return
        setTherapists(data.items || [])
        setTherapistsTotal(data.total || 0)
        setTherapistsPages(data.pages || 1)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load therapists')
      })
      .finally(() => {
        if (!cancelled) setTherapistsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [
    tab,
    therapistPage,
    therapistSearchDebounced,
    therapistSort,
    canReadTherapists,
    reloadToken,
  ])

  useEffect(() => {
    if (tab !== 'clients') return undefined
    let cancelled = false
    setClientsLoading(true)
    setError('')
    fetchClientsPage({ page: clientPage, search: clientSearchDebounced })
      .then((data) => {
        if (cancelled) return
        setClients(data.items || [])
        setClientsTotal(data.total || 0)
        setClientsPages(data.pages || 1)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || 'Could not load clients')
      })
      .finally(() => {
        if (!cancelled) setClientsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tab, clientPage, clientSearchDebounced, reloadToken])

  useEffect(() => {
    if (tab !== 'staff' || !canManageUsers) return undefined
    let cancelled = false
    setMetaLoading(true)
    fetchStaffMeta()
      .then((meta) => {
        if (cancelled) return
        setCatalog(meta.catalog)
        setRoleDefaults(meta.roleDefaults)
        setAssignableRoles(meta.assignableRoles)
        setStaffDepartments(meta.staffDepartments)
        setDeprecatedRoles(meta.deprecatedRoles)
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setMetaLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [tab, canManageUsers, reloadToken])

  useEffect(() => {
    if (!canManageUsers) return undefined
    if (tab !== 'staff' && tab !== 'therapists' && tab !== 'clients') return undefined
    let cancelled = false
    fetchTabInvites()
      .then((rows) => {
        if (!cancelled) setInvites(rows)
      })
      .catch(() => {
        if (!cancelled) setInvites([])
      })
    return () => {
      cancelled = true
    }
  }, [tab, canManageUsers, reloadToken])

  useEffect(() => {
    if (tab !== 'therapists' || !canReadTherapists) return undefined
    let cancelled = false
    fetchTherapistProfiles()
      .then((rows) => {
        if (!cancelled) setProfiles(rows)
      })
      .catch(() => {
        if (!cancelled) setProfiles([])
      })
    return () => {
      cancelled = true
    }
  }, [tab, canReadTherapists, reloadToken])

  useEffect(() => {
    if (tab !== 'clients' || !canManageUsers) return undefined
    let cancelled = false
    fetchParentsAwaitingLogin()
      .then((data) => {
        if (!cancelled) setParentsAwaitingLogin(data?.count != null ? data : { count: 0, items: [] })
      })
      .catch(() => {
        if (!cancelled) setParentsAwaitingLogin({ count: 0, items: [] })
      })
    return () => {
      cancelled = true
    }
  }, [tab, canManageUsers, reloadToken])

  const profileByUser = useMemo(() => {
    const m = new Map()
    for (const p of profiles) m.set(p.user_id, p)
    return m
  }, [profiles])

  const therapistRangeStart = therapistsTotal ? (therapistPage - 1) * PEOPLE_PAGE_SIZE + 1 : 0
  const therapistRangeEnd = Math.min(therapistPage * PEOPLE_PAGE_SIZE, therapistsTotal)
  const clientRangeStart = clientsTotal ? (clientPage - 1) * PEOPLE_PAGE_SIZE + 1 : 0
  const clientRangeEnd = Math.min(clientPage * PEOPLE_PAGE_SIZE, clientsTotal)

  const parentPendingInvites = useMemo(
    () => invites.filter((i) => i.role_name === 'PARENT'),
    [invites],
  )
  const therapistPendingInvites = useMemo(
    () => invites.filter((i) => i.role_name === 'THERAPIST'),
    [invites],
  )
  const staffPendingInvites = useMemo(
    () => invites.filter((i) => !['THERAPIST', 'PARENT'].includes(i.role_name)),
    [invites],
  )

  async function exportTherapistsCsv() {
    try {
      const [userResult, profileRows] = await Promise.all([
        fetchAllTherapists({ search: therapistSearchDebounced, sort: therapistSort }),
        fetchTherapistProfiles(),
      ])
      const map = new Map(profileRows.map((p) => [p.user_id, p]))
      exportTherapistCsv(userResult.items, map)
    } catch (err) {
      setError(err.message || 'Could not export therapist CSV')
    }
  }

  async function exportClientsCsv() {
    try {
      const result = await fetchAllClients({ search: clientSearchDebounced })
      exportClientCsv(result.items)
    } catch (err) {
      setError(err.message || 'Could not export client CSV')
    }
  }

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
      invite_status: f.pendingInvite
        ? f.pendingInvite.isExpired
          ? 'expired'
          : 'pending'
        : undefined,
      pending_invite_url:
        f.pendingInvite && !f.pendingInvite.isExpired ? f.pendingInvite.inviteUrl : undefined,
      _reactivateCaseId:
        f.allCasesClosed && primary.parentIsActive !== false ? f.primaryCaseId : null,
    }
  }

  async function invitePendingParent(f) {
    if (f.pendingInvite?.inviteId) {
      setError('')
      try {
        const force = f.pendingInvite.isExpired ? '?force_resend=true' : ''
        const res = await apiFetch(`/api/v1/admin/invites/${f.pendingInvite.inviteId}/resend-email${force}`, {
          method: 'POST',
        })
        if (res.invite_url) setInviteUrl(res.invite_url)
        setSuccess(`Fresh invite link sent to ${f.pendingInvite.pendingEmail}.`)
        reload()
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

  async function bulkInviteParentsAwaitingLogin() {
    const count = parentsAwaitingLogin.count || 0
    if (!count) return
    if (
      !window.confirm(
        `Send a fresh portal invite to ${count} parent(s) who have not signed in yet?`,
      )
    ) {
      return
    }
    setError('')
    try {
      const res = await apiFetch('/api/v1/admin/families/bulk-invite-parents', {
        method: 'POST',
        body: JSON.stringify({}),
        timeoutMs: 120_000,
      })
      const skippedNote = res.skipped ? ` ${res.skipped} skipped.` : ''
      setSuccess(`Invite emails queued for ${res.sent} of ${res.total} parent(s).${skippedNote}`)
      reload()
    } catch (err) {
      setError(err.message || 'Bulk invite failed')
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
          {f.hasOpenCase && f.primaryCaseId ? (
            <Link
              to={`/admin/cases/${f.primaryCaseId}?tab=overview`}
              className="admin-btn admin-btn--ghost admin-btn--sm"
            >
              Client status →
            </Link>
          ) : null}
          <PeopleRowActions
            user={clientUser}
            rowBusy={rowBusy}
            setRowBusy={setRowBusy}
            onReload={reload}
            onSuccess={setSuccess}
            onError={setError}
            lastProvision={lastProvision}
            setLastProvision={setLastProvision}
            extraActions={secondary}
            showDeactivate={!f.hasOpenCase}
          />
        </div>
      )
    }
    if (f.pendingInvite && canManageUsers) {
      return (
        <div className="admin-btn-group admin-btn-group--wrap">
          {secondary}
          {f.pendingInvite.inviteUrl ? (
            <CopyLinkButton url={f.pendingInvite.inviteUrl} label="Copy invite link" />
          ) : null}
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            onClick={() => invitePendingParent(f)}
          >
            {f.pendingInvite.isExpired ? 'Send fresh invite' : 'Resend invite'}
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
            onReload={reload}
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
    setPendingInvitesView(false)
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

      {tab === 'staff' && canManageUsers ? (
            <AdminStaffManageSection
              catalog={catalog}
              roleDefaults={roleDefaults}
              assignableRoles={assignableRoles}
              staffDepartments={staffDepartments}
              deprecatedRoles={deprecatedRoles}
              staff={staff}
              staffTotal={staffTotal}
              staffPage={staffPage}
              onStaffPageChange={setStaffPage}
              staffSearch={staffSearch}
              onStaffSearchChange={setStaffSearch}
              staffLoading={staffLoading || metaLoading}
              pendingInvites={staffPendingInvites}
              onReload={reload}
              onSuccess={setSuccess}
              onError={setError}
            />
          ) : null}

          {tab === 'staff' && canReadStaffDirectory && !canManageUsers ? (
            <AdminStaffDirectoryReadOnly
              staff={staff}
              staffDepartments={staffDepartments}
              staffTotal={staffTotal}
              staffPage={staffPage}
              onStaffPageChange={setStaffPage}
              staffSearch={staffSearch}
              onStaffSearchChange={setStaffSearch}
              staffLoading={staffLoading}
            />
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
                  invitesViewOpen={pendingInvitesView}
                  onInvitesViewChange={setPendingInvitesView}
                  onSuccess={setSuccess}
                  onError={setError}
                  onReload={reload}
                />
              ) : (
                <AdminPanel title="Therapists">
                  <AdminEmptyState
                    title="View-only access"
                    description="You cannot add therapists or use bulk upload. Open Profile editor to review listings."
                  />
                </AdminPanel>
              )}
              {!pendingInvitesView ? (
              <AdminPanel
                title={`Therapists (${therapistsTotal})`}
                padded={false}
                actions={
                  <div className="admin-btn-group admin-btn-group--wrap">
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={exportTherapistsCsv}
                    >
                      Download CSV
                    </button>
                    {canManageUsers ? (
                      <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                        Profile editor
                      </Link>
                    ) : (
                      <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                        View profiles
                      </Link>
                    )}
                  </div>
                }
              >
                {therapistsLoading ? (
                  <div className="admin-panel__body">
                    <p className="admin-muted">Loading therapists…</p>
                  </div>
                ) : therapistsTotal === 0 ? (
                  <AdminEmptyState title="No therapists yet" description="Use Add therapist or Bulk upload above." />
                ) : therapists.length === 0 ? (
                  <div className="admin-panel__body">
                    <AdminToolbar>
                      <AdminSearchInput
                        value={therapistSearch}
                        onChange={setTherapistSearch}
                        placeholder="Search therapists by name or email…"
                      />
                    </AdminToolbar>
                    <AdminEmptyState title="No therapists match" description="Try adjusting search." />
                  </div>
                ) : (
                  <div className="admin-panel__body">
                    <AdminToolbar>
                      <AdminSearchInput
                        value={therapistSearch}
                        onChange={setTherapistSearch}
                        placeholder="Search therapists by name or email…"
                      />
                    </AdminToolbar>
                    <div className="admin-people-directory-toolbar">
                      <FilterSelect
                        label="Sort"
                        value={therapistSort}
                        onChange={(e) => setTherapistSort(e.target.value)}
                        options={THERAPIST_SORT_OPTIONS}
                      />
                    </div>
                    {canManageUsers ? (
                      <PeopleBulkToolbar
                        selectedUserIds={[...selectedTherapistIds]}
                        onReload={() => {
                          setSelectedTherapistIds(new Set())
                          reload()
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
                              <th>Therapist ID</th>
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
                            {therapists.map((u) => {
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
                                  <td>
                                    <TherapistIdCell
                                      key={`${u.id}-${u.external_employee_id || 'none'}`}
                                      user={u}
                                      canEdit={canManageUsers}
                                      onSaved={(updated) => {
                                        const therapistId = updated?.external_employee_id ?? null
                                        setTherapists((prev) =>
                                          prev.map((row) =>
                                            row.id === updated.id
                                              ? { ...row, external_employee_id: therapistId }
                                              : row,
                                          ),
                                        )
                                        setSuccess('Therapist ID updated.')
                                      }}
                                      onError={setError}
                                      onReload={reload}
                                    />
                                  </td>
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
                        {therapists.map((u) => {
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
                                meta={[
                                  u.external_employee_id ? `ID ${u.external_employee_id}` : null,
                                  u.email,
                                  u.phone,
                                ]
                                  .filter(Boolean)
                                  .join(' · ')}
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
                                {canManageUsers ? (
                                  <p style={{ marginBottom: 8 }}>
                                    <TherapistIdCell
                                      key={`${u.id}-${u.external_employee_id || 'none'}`}
                                      user={u}
                                      canEdit={canManageUsers}
                                      onSaved={(updated) => {
                                        const therapistId = updated?.external_employee_id ?? null
                                        setTherapists((prev) =>
                                          prev.map((row) =>
                                            row.id === updated.id
                                              ? { ...row, external_employee_id: therapistId }
                                              : row,
                                          ),
                                        )
                                        setSuccess('Therapist ID updated.')
                                      }}
                                      onError={setError}
                                      onReload={reload}
                                    />
                                  </p>
                                ) : null}
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
                    <PeopleListPagination
                      page={therapistPage}
                      totalPages={therapistsPages}
                      total={therapistsTotal}
                      rangeStart={therapistRangeStart}
                      rangeEnd={therapistRangeEnd}
                      onPageChange={setTherapistPage}
                    />
                  </div>
                )}
              </AdminPanel>
              ) : null}
            </>
          )}

          {tab === 'clients' && (
            <>
              <AdminClientOnboardPanel
                canCreateCase={canCreateCase}
                canManageUsers={canManageUsers}
                isHrPortal={isHrPortal}
                pendingInvites={parentPendingInvites}
                parentsAwaitingLoginCount={parentsAwaitingLogin.count || 0}
                onBulkInviteAwaitingLogin={bulkInviteParentsAwaitingLogin}
                invitesViewOpen={pendingInvitesView}
                onInvitesViewChange={setPendingInvitesView}
                onAddFamily={() => setShowFamilyWizard(true)}
                onSuccess={setSuccess}
                onError={setError}
                onReload={reload}
              />
              {!pendingInvitesView ? (
              <AdminPanel
                title={`Clients (${clientsTotal})`}
                padded={false}
                actions={
                  <div className="admin-btn-group admin-btn-group--wrap">
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={exportClientsCsv}
                    >
                      Download CSV
                    </button>
                    {canCreateCase ? (
                      <Link to="/admin/cases" className="admin-btn admin-btn--ghost admin-btn--sm">
                        Case list
                      </Link>
                    ) : null}
                  </div>
                }
              >
                {clientsLoading ? (
                  <div className="admin-panel__body">
                    <p className="admin-muted">Loading clients…</p>
                  </div>
                ) : clientsTotal === 0 ? (
                  <AdminEmptyState
                    title="No clients yet"
                    description="Use Add client & case or Bulk import above."
                  />
                ) : clients.length === 0 ? (
                  <div className="admin-panel__body">
                    <AdminToolbar>
                      <AdminSearchInput
                        value={clientSearch}
                        onChange={setClientSearch}
                        placeholder="Search clients by child, parent, email, or case…"
                      />
                    </AdminToolbar>
                    <AdminEmptyState title="No clients match" description="Try adjusting search." />
                  </div>
                ) : (
                  <div className="admin-panel__body">
                    <AdminToolbar>
                      <AdminSearchInput
                        value={clientSearch}
                        onChange={setClientSearch}
                        placeholder="Search clients by child, parent, email, or case…"
                      />
                    </AdminToolbar>
                    {canManageUsers ? (
                      <PeopleBulkToolbar
                        selectedUserIds={[...selectedClientUserIds]}
                        onReload={() => {
                          setSelectedClientUserIds(new Set())
                          reload()
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
                            {clients.map((f) => {
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
                        {clients.map((f) => {
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
                    <PeopleListPagination
                      page={clientPage}
                      totalPages={clientsPages}
                      total={clientsTotal}
                      rangeStart={clientRangeStart}
                      rangeEnd={clientRangeEnd}
                      onPageChange={setClientPage}
                    />
                  </div>
                )}
              </AdminPanel>
              ) : null}
            </>
          )}

      <ClientCaseAccessModal
        family={clientAccessFamily}
        open={!!clientAccessFamily}
        onClose={() => setClientAccessFamily(null)}
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
                  reload()
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
