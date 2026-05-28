import { Fragment, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminEmptyState, AdminPageHeader, AdminPanel, AdminSearchInput, AdminToolbar, StatusBadge } from './ui/index.js'
import { ModulePicker } from './ui/ModulePicker.jsx'
import { buildRbacPayload, grantsFromAssignments } from './ui/RbacEditor.jsx'

const INVITE_ONLY_ROLES = ['THERAPIST']

const EMPTY_FORM = {
  email: '',
  full_name: '',
  password: 'demo123',
  role_names: ['THERAPIST'],
  region: '',
  module_assignments: [],
  feature_overrides: {},
  view_only: false,
}

export function AdminUsersPage() {
  const [users, setUsers] = useState([])
  const [catalog, setCatalog] = useState([])
  const [roleDefaults, setRoleDefaults] = useState({})
  const [search, setSearch] = useState('')
  const [mode, setMode] = useState('invite')
  const [form, setForm] = useState(EMPTY_FORM)
  const [inviteUrl, setInviteUrl] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editModules, setEditModules] = useState([])
  const [editOverrides, setEditOverrides] = useState({})
  const [editViewOnly, setEditViewOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [userRows, moduleMeta] = await Promise.all([
        apiFetch('/api/v1/admin/users'),
        apiFetch('/api/v1/admin/modules'),
      ])
      setUsers(userRows)
      setCatalog(moduleMeta.modules ?? [])
      setRoleDefaults(moduleMeta.role_defaults ?? {})
    } catch {
      setUsers([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return users
    return users.filter(
      (u) =>
        u.email?.toLowerCase().includes(q) ||
        u.full_name?.toLowerCase().includes(q) ||
        u.roles?.some((r) => r.toLowerCase().includes(q)) ||
        u.module_assignments?.some((m) => m.toLowerCase().includes(q)),
    )
  }, [users, search])

  function setRoles(roles) {
    const finalRoles = roles.length ? roles : form.role_names
    setForm((prev) => ({
      ...prev,
      role_names: finalRoles,
      module_assignments:
        prev.module_assignments.length && finalRoles.length === 1
          ? prev.module_assignments
          : suggestModules(finalRoles),
    }))
    if (finalRoles.some((r) => INVITE_ONLY_ROLES.includes(r))) setMode('invite')
    setInviteUrl('')
  }

  function suggestModules(roles) {
    const suggested = new Set()
    for (const r of roles) {
      for (const m of roleDefaults[r] ?? []) suggested.add(m)
    }
    return [...suggested]
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setSubmitting(true)
    try {
      const grants = grantsFromAssignments(form.module_assignments, form.view_only)
      const access = buildRbacPayload({
        roleNames: form.role_names,
        grants,
        featureOverrides: form.feature_overrides,
        viewOnly: form.view_only,
      })
      if (mode === 'invite') {
        const role = form.role_names[0] || 'THERAPIST'
        const res = await apiFetch('/api/v1/admin/therapists/invite', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            role_name: role,
            ...access,
          }),
        })
        setInviteUrl(res.invite_url)
        setSuccess(`Invite link generated for ${form.email}`)
      } else {
        await apiFetch('/api/v1/admin/users', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            password: form.password,
            full_name: form.full_name,
            region: form.region || null,
            ...access,
          }),
        })
        setForm(EMPTY_FORM)
        setSuccess('User created successfully.')
        load()
      }
    } catch (err) {
      setError(err.message || 'Action failed')
    } finally {
      setSubmitting(false)
    }
  }

  function startEditModules(u) {
    setEditingId(u.id)
    setEditModules(u.module_assignments ?? [])
    setEditOverrides(u.feature_overrides ?? {})
    setEditViewOnly(Boolean(u.is_view_only))
  }

  async function saveEditModules(userId) {
    setError('')
    try {
      const access = buildRbacPayload({
        roleNames: users.find((x) => x.id === userId)?.roles ?? [],
        grants: grantsFromAssignments(editModules, editViewOnly),
        featureOverrides: editOverrides,
        viewOnly: editViewOnly,
      })
      await apiFetch(`/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify(access),
      })
      setEditingId(null)
      load()
    } catch (err) {
      setError(err.message || 'Could not update modules')
    }
  }

  async function setPasswordForUser(userId, email) {
    const nextPassword = window.prompt(`Set a new password for ${email} (min 6 characters):`)
    if (!nextPassword) return
    if (nextPassword.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    setError('')
    setSuccess('')
    try {
      await apiFetch(`/api/v1/admin/users/${userId}/set-password`, {
        method: 'POST',
        body: JSON.stringify({ password: nextPassword }),
      })
      setSuccess(`Password updated for ${email}.`)
    } catch (err) {
      setError(err.message || 'Could not update password')
    }
  }

  const needsFullName = mode === 'direct'
  const needsPassword = mode === 'direct'

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Access control"
        title="Users & invites"
        subtitle="Assign roles and product modules to control which programmes and admin features each user can access."
      />

      {error ? <p className="admin-alert admin-alert--error">{error}</p> : null}
      {success ? <p className="admin-alert admin-alert--success">{success}</p> : null}

      <AdminPanel title="Add user">
        <div className="admin-mode-toggle" style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
          <button
            type="button"
            className={`admin-btn admin-btn--sm ${mode === 'invite' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => {
              setMode('invite')
              setInviteUrl('')
            }}
          >
            Send invite
          </button>
          <button
            type="button"
            className={`admin-btn admin-btn--sm ${mode === 'direct' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => {
              setMode('direct')
              setInviteUrl('')
            }}
          >
            Create directly
          </button>
        </div>

        <form onSubmit={handleSubmit} className="admin-form-grid">
          <label>
            Email
            <input
              className="admin-input"
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </label>

          {needsFullName ? (
            <label>
              Full name
              <input
                className="admin-input"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </label>
          ) : null}

          {needsPassword && (
            <label>
              Password
              <input
                className="admin-input"
                type="password"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
                minLength={6}
                required
              />
            </label>
          )}

          {needsFullName && (
            <label>
              Region (optional)
              <input
                className="admin-input"
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
              />
            </label>
          )}

          <ModulePicker
            catalog={catalog}
            roleDefaults={roleDefaults}
            selectedRoles={form.role_names}
            onRoleChange={setRoles}
            allowMultiRole={mode === 'direct'}
            value={form.module_assignments}
            onChange={(module_assignments) => setForm({ ...form, module_assignments })}
            featureOverrides={form.feature_overrides}
            onFeatureOverridesChange={(feature_overrides) => setForm({ ...form, feature_overrides })}
            viewOnly={form.view_only}
            onViewOnlyChange={(view_only) => setForm({ ...form, view_only })}
          />

          <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
            {submitting ? 'Working…' : mode === 'invite' ? 'Send invite link' : 'Create user'}
          </button>
        </form>

        {inviteUrl ? (
          <div style={{ marginTop: 16, padding: '10px 14px', background: '#f0fdf4', borderRadius: 8, border: '1px solid #86efac' }}>
            <p style={{ fontSize: '0.75rem', marginBottom: 4, fontWeight: 600, color: '#15803d' }}>Invite link generated</p>
            <code style={{ fontSize: '0.72rem', wordBreak: 'break-all', color: '#166534' }}>{inviteUrl}</code>
          </div>
        ) : null}
      </AdminPanel>

      <AdminPanel title={`${filtered.length} users`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={setSearch} placeholder="Search name, email, role, or module…" />
          </AdminToolbar>

          {loading ? (
            <div className="admin-skeleton" />
          ) : filtered.length === 0 ? (
            <AdminEmptyState title="No users found" />
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Roles</th>
                    <th>Modules</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => (
                    <Fragment key={u.id}>
                      <tr>
                        <td>
                          <span className="admin-table__primary">{u.full_name}</span>
                        </td>
                        <td>{u.email}</td>
                        <td>
                          <div className="admin-chip-row">
                            {u.roles.map((r) => (
                              <span key={r} className="admin-chip">
                                {r}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td>
                          <div className="admin-chip-row">
                            {(u.module_assignments?.length ? u.module_assignments : ['all']).map((m) => (
                              <span key={m} className="admin-chip" style={{ background: '#eef2ff', color: '#3730a3' }}>
                                {m}
                              </span>
                            ))}
                            {u.is_view_only ? (
                              <span className="admin-chip" style={{ background: '#f1f5f9', color: '#475569' }}>
                                view only
                              </span>
                            ) : null}
                          </div>
                        </td>
                        <td>
                          <StatusBadge status={u.is_active ? 'ACTIVE' : 'SUSPENDED'} />
                        </td>
                        <td>
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            onClick={() => (editingId === u.id ? setEditingId(null) : startEditModules(u))}
                          >
                            {editingId === u.id ? 'Cancel' : 'Modules'}
                          </button>
                          <button
                            type="button"
                            className="admin-btn admin-btn--ghost admin-btn--sm"
                            style={{ marginLeft: 8 }}
                            onClick={() => setPasswordForUser(u.id, u.email)}
                          >
                            Set password
                          </button>
                        </td>
                      </tr>
                      {editingId === u.id ? (
                        <tr key={`${u.id}-edit`}>
                          <td colSpan={6}>
                            <div className="admin-drawer" style={{ margin: 0 }}>
                              <ModulePicker
                                catalog={catalog}
                                roleDefaults={roleDefaults}
                                selectedRoles={u.roles}
                                value={editModules}
                                onChange={setEditModules}
                                featureOverrides={editOverrides}
                                onFeatureOverridesChange={setEditOverrides}
                                viewOnly={editViewOnly}
                                onViewOnlyChange={setEditViewOnly}
                              />
                              <button
                                type="button"
                                className="admin-btn admin-btn--primary admin-btn--sm"
                                style={{ marginTop: 12 }}
                                onClick={() => saveEditModules(u.id)}
                              >
                                Save modules
                              </button>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </AdminPanel>
    </div>
  )
}
