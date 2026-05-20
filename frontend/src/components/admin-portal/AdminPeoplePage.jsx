import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar, StatusBadge } from './ui/index.js'
import { ModulePicker } from './ui/ModulePicker.jsx'

const INVITE_ROLES = [
  { id: 'THERAPIST', label: 'Therapist' },
  { id: 'PARENT', label: 'Parent (client portal)' },
  { id: 'ADMIN', label: 'Admin' },
  { id: 'CASE_MANAGER', label: 'Case manager' },
]

const EMPTY_INVITE = { email: '', role_name: 'THERAPIST', module_assignments: [] }
const EMPTY_CHILD = { first_name: '', last_name: '' }

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
  const [inviteForm, setInviteForm] = useState(EMPTY_INVITE)
  const [inviteUrl, setInviteUrl] = useState('')
  const [childForm, setChildForm] = useState(EMPTY_CHILD)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const t = searchParams.get('tab')
    if (t && ['staff', 'therapists', 'families', 'invites', 'onboarding'].includes(t)) setTab(t)
  }, [searchParams])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [userRows, moduleMeta, profileRows, familyRows, inviteRows] = await Promise.all([
        apiFetch('/api/v1/admin/users'),
        apiFetch('/api/v1/admin/modules'),
        apiFetch('/api/v1/admin/therapist-profiles'),
        apiFetch('/api/v1/admin/families'),
        apiFetch('/api/v1/admin/invites'),
      ])
      setUsers(unwrapList(userRows))
      setCatalog(moduleMeta.modules ?? [])
      setRoleDefaults(moduleMeta.role_defaults ?? {})
      setProfiles(profileRows)
      setFamilies(familyRows)
      setInvites(inviteRows)
    } catch (err) {
      setError(err.message || 'Could not load people data')
    } finally {
      setLoading(false)
    }
  }, [])

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
  const filteredFamilies = families.filter((f) =>
    filterText(`${f.childName} ${f.parents?.map((p) => p.parentEmail).join(' ')} ${(f.caseCodes || []).join(' ')}`),
  )
  const filteredInvites = invites.filter((i) => filterText(`${i.email} ${i.role_name}`))
  const walkInInvites = useMemo(
    () => invites.filter((i) => i.pending_slot_id && filterText(`${i.email} ${i.client_name || ''}`)),
    [invites, search],
  )

  function suggestModules(role) {
    return [...(roleDefaults[role] ?? [])]
  }

  async function sendInvite(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSubmitting(true)
    try {
      const res = await apiFetch('/api/v1/admin/invites', {
        method: 'POST',
        body: JSON.stringify({
          email: inviteForm.email.trim(),
          role_name: inviteForm.role_name,
          module_assignments: inviteForm.role_name === 'PARENT' ? [] : inviteForm.module_assignments,
        }),
      })
      setInviteUrl(res.invite_url)
      setSuccess(`Invite created for ${inviteForm.email}`)
      setInviteForm(EMPTY_INVITE)
      load()
    } catch (err) {
      setError(err.message || 'Invite failed')
    } finally {
      setSubmitting(false)
    }
  }

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

  async function inviteParent(userId) {
    setError('')
    try {
      const res = await apiFetch(`/api/v1/admin/families/${userId}/invite`, { method: 'POST' })
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
    { id: 'invites', label: 'Invites' },
    { id: 'onboarding', label: 'Walk-in onboarding' },
  ]

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Directory"
        title="People"
        subtitle="Staff, therapists, client families, and pending portal invites in one place."
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

      {tab === 'invites' ? (
        <AdminPanel title="Send invite">
          <form onSubmit={sendInvite} className="admin-form-grid" style={{ maxWidth: 520 }}>
            <label>
              Email
              <input
                type="email"
                className="admin-input"
                value={inviteForm.email}
                onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                required
              />
            </label>
            <label>
              Role
              <select
                className="admin-input"
                value={inviteForm.role_name}
                onChange={(e) => {
                  const role = e.target.value
                  setInviteForm((f) => ({
                    ...f,
                    role_name: role,
                    module_assignments: suggestModules(role),
                  }))
                }}
              >
                {INVITE_ROLES.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            {inviteForm.role_name !== 'PARENT' ? (
              <div style={{ gridColumn: '1 / -1' }}>
                <ModulePicker
                  catalog={catalog}
                  value={inviteForm.module_assignments}
                  onChange={(mods) => setInviteForm((f) => ({ ...f, module_assignments: mods }))}
                />
              </div>
            ) : null}
            <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm" disabled={submitting}>
              {submitting ? 'Sending…' : 'Generate invite link'}
            </button>
          </form>
        </AdminPanel>
      ) : null}

      {tab === 'families' ? (
        <AdminPanel title="Quick add child" subtitle="Link parents when creating a case or from a new family">
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
            <button type="submit" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={submitting}>
              Add child
            </button>
          </form>
        </AdminPanel>
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
            <AdminPanel
              title={`Therapists (${filteredTherapists.length})`}
              actions={
                <Link to="/admin/therapist-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
                  Profile editor
                </Link>
              }
            >
              {filteredTherapists.length === 0 ? (
                <AdminEmptyState title="No therapists" description="Send an invite from the Invites tab." />
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Profile</th>
                      <th>Modules</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTherapists.map((u) => {
                      const prof = profileByUser.get(u.id)
                      return (
                        <tr key={u.id}>
                          <td>{u.full_name}</td>
                          <td>{u.email}</td>
                          <td>
                            {prof ? <StatusBadge status={prof.status} /> : <span className="admin-muted">No profile</span>}
                          </td>
                          <td>{(u.module_assignments || []).join(', ') || '—'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              )}
            </AdminPanel>
          )}

          {tab === 'families' && (
            <AdminPanel title={`Families (${filteredFamilies.length})`}>
              {filteredFamilies.length === 0 ? (
                <AdminEmptyState title="No families" description="Add a child or create a family from case allotment." />
              ) : (
                <ul className="admin-queue">
                  {filteredFamilies.map((f) => (
                    <li key={f.childId} className="admin-queue__item">
                      <div>
                        <p className="admin-queue__title">{f.childName}</p>
                        <p className="admin-queue__meta">
                          {f.parents?.length
                            ? f.parents.map((p) => `${p.parentName} · ${p.parentEmail}`).join(' | ')
                            : 'No parent linked'}
                          {f.caseCodes?.length ? ` · Cases: ${f.caseCodes.join(', ')}` : ''}
                        </p>
                      </div>
                      <div className="admin-btn-group">
                        {f.parents?.[0]?.userId ? (
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => inviteParent(f.parents[0].userId)}
                          >
                            Invite parent
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

          {tab === 'invites' && (
            <AdminPanel title={`Pending invites (${filteredInvites.length})`}>
              {filteredInvites.length === 0 ? (
                <AdminEmptyState title="No pending invites" description="Generate a link above." />
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Email</th>
                      <th>Role</th>
                      <th>Walk-in</th>
                      <th>Expires</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredInvites.map((inv) => (
                      <tr key={inv.id}>
                        <td>{inv.email}</td>
                        <td>{inv.role_name}</td>
                        <td>{inv.pending_slot_id ? `${inv.client_name || '—'} · slot #${inv.pending_slot_id}` : '—'}</td>
                        <td>{new Date(inv.expires_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => copyLink(inv.invite_url)}
                          >
                            Copy link
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </AdminPanel>
          )}

          {tab === 'onboarding' && (
            <AdminPanel title={`Walk-in onboarding (${walkInInvites.length})`} subtitle="Slots held for new client invites — finalize family & case, then share the invite link.">
              {walkInInvites.length === 0 ? (
                <AdminEmptyState title="No walk-in invites" description="When a therapist invites a new parent from a slot, it appears here." />
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Client</th>
                      <th>Email</th>
                      <th>Slot</th>
                      <th>Therapist</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {walkInInvites.map((inv) => (
                      <tr key={inv.id}>
                        <td>{inv.client_name || '—'}</td>
                        <td>{inv.email}</td>
                        <td>#{inv.pending_slot_id}</td>
                        <td className="admin-muted">{inv.therapist_user_id ?? '—'}</td>
                        <td>
                          <div className="admin-btn-group">
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              onClick={() => copyLink(inv.invite_url)}
                            >
                              Copy link
                            </button>
                            <Link
                              to={`/admin/cases?allot=1&parent_email=${encodeURIComponent(inv.email)}`}
                              className="admin-btn admin-btn--primary admin-btn--sm"
                            >
                              Finalize case
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </AdminPanel>
          )}
        </>
      )}
    </div>
  )
}
