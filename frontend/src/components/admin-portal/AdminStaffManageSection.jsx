import { Fragment, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import { AdminEmptyState, AdminPanel, AdminSearchInput, AdminToolbar } from './ui/index.js'
import { ModulePicker } from './ui/ModulePicker.jsx'

const ROLE_OPTIONS = ['ADMIN', 'CASE_MANAGER', 'SUPERVISOR', 'FINANCE', 'HR', 'VIEWER', 'SCHOOL_COORDINATOR']

const NAV_UNLOCKED_BY_FEATURE = {
  cases: 'Cases',
  session_logs: 'Workbench & session logs',
  reports: 'Reports & observation checklists',
  iep: 'IEP builder & attachments',
  invoices: 'Invoices & client payment claims',
  tickets: 'Support tickets',
  incidents: 'Incidents',
  dashboard: 'Operations dashboard',
}

const ROLE_LANDING_HINT = {
  CASE_MANAGER: 'lands on Workbench',
  SUPERVISOR: 'lands on Workbench',
  FINANCE: 'lands on Invoices',
  ADMIN: 'lands on Dashboard',
  SUPER_ADMIN: 'lands on Dashboard',
}

function previewUnlockedAreas(catalog, moduleIds) {
  const areas = new Set()
  for (const mod of catalog || []) {
    if (!moduleIds.includes(mod.id)) continue
    for (const f of mod.features || []) {
      const label = NAV_UNLOCKED_BY_FEATURE[f.id]
      if (label) areas.add(label)
    }
  }
  return [...areas].sort()
}

const EMPTY_FORM = {
  email: '',
  full_name: '',
  password: 'demo123',
  role_names: ['CASE_MANAGER'],
  region: '',
  module_assignments: [],
}

export function AdminStaffManageSection({ catalog, roleDefaults, staff, onReload, onSuccess, onError }) {
  const [mode, setMode] = useState('invite')
  const [form, setForm] = useState(EMPTY_FORM)
  const [inviteUrl, setInviteUrl] = useState('')
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editModules, setEditModules] = useState([])
  const [submitting, setSubmitting] = useState(false)

  const capabilityPreview = useMemo(
    () => previewUnlockedAreas(catalog, form.module_assignments),
    [catalog, form.module_assignments],
  )

  const landingHint = useMemo(() => {
    const primary = form.role_names[0]
    return ROLE_LANDING_HINT[primary] || null
  }, [form.role_names])

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return staff
    return staff.filter(
      (u) =>
        u.email?.toLowerCase().includes(q) ||
        u.full_name?.toLowerCase().includes(q) ||
        u.roles?.some((r) => r.toLowerCase().includes(q)),
    )
  }, [staff, search])

  function suggestModules(roles) {
    const suggested = new Set()
    for (const r of roles) {
      for (const m of roleDefaults[r] ?? []) suggested.add(m)
    }
    return [...suggested]
  }

  function toggleRole(role) {
    setForm((prev) => {
      const roles = prev.role_names.includes(role)
        ? prev.role_names.filter((r) => r !== role)
        : [...prev.role_names, role]
      const finalRoles = roles.length ? roles : [role]
      return { ...prev, role_names: finalRoles, module_assignments: suggestModules(finalRoles) }
    })
    setInviteUrl('')
  }

  async function handleSubmit(e) {
    e.preventDefault()
    onError?.('')
    onSuccess?.('')
    setSubmitting(true)
    try {
      if (mode === 'invite') {
        const role = form.role_names[0] || 'CASE_MANAGER'
        const res = await apiFetch('/api/v1/admin/therapists/invite', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            role_name: role,
            module_assignments: form.module_assignments,
          }),
        })
        setInviteUrl(res.invite_url)
        onSuccess?.(`Invite link generated for ${form.email}`)
        onReload?.()
      } else {
        await apiFetch('/api/v1/admin/users', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            password: form.password,
            full_name: form.full_name,
            role_names: form.role_names,
            region: form.region || null,
            module_assignments: form.role_names.includes('SUPER_ADMIN') ? [] : form.module_assignments,
          }),
        })
        setForm(EMPTY_FORM)
        onSuccess?.('Staff user created.')
        onReload?.()
      }
    } catch (err) {
      onError?.(err.message || 'Action failed')
    } finally {
      setSubmitting(false)
    }
  }

  async function saveEditModules(userId) {
    onError?.('')
    try {
      await apiFetch(`/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ module_assignments: editModules }),
      })
      setEditingId(null)
      onReload?.()
      onSuccess?.('Modules updated.')
    } catch (err) {
      onError?.(err.message || 'Could not update modules')
    }
  }

  return (
    <>
      <AdminPanel title="Add staff user" subtitle="Invite by email or create with a password. Assign product modules for portal access.">
        <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
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
          {mode === 'direct' ? (
            <>
              <label>
                Full name
                <input
                  className="admin-input"
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                  required
                />
              </label>
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
              <label>
                Region (optional)
                <input
                  className="admin-input"
                  value={form.region}
                  onChange={(e) => setForm({ ...form, region: e.target.value })}
                />
              </label>
            </>
          ) : null}
          <fieldset className="module-picker__roles">
            <legend className="module-picker__title">{mode === 'invite' ? 'Role (single)' : 'Roles'}</legend>
            <div className="admin-chip-row">
              {ROLE_OPTIONS.map((role) => (
                <label key={role} className="admin-chip" style={{ cursor: 'pointer' }}>
                  <input
                    type={mode === 'invite' ? 'radio' : 'checkbox'}
                    name={mode === 'invite' ? 'staff-invite-role' : undefined}
                    checked={form.role_names.includes(role)}
                    onChange={() => toggleRole(role)}
                    style={{ marginRight: 6 }}
                  />
                  {role}
                </label>
              ))}
            </div>
          </fieldset>
          <ModulePicker
            catalog={catalog}
            roleDefaults={roleDefaults}
            selectedRoles={form.role_names}
            value={form.module_assignments}
            onChange={(module_assignments) => setForm({ ...form, module_assignments })}
          />
          {capabilityPreview.length > 0 ? (
            <div className="admin-panel" style={{ padding: 12, background: '#f8fafc', borderRadius: 8 }}>
              <p className="admin-page__eyebrow" style={{ marginBottom: 6 }}>
                Portal areas unlocked
              </p>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.875rem', color: '#374151' }}>
                {capabilityPreview.map((area) => (
                  <li key={area}>{area}</li>
                ))}
              </ul>
              {landingHint ? (
                <p className="admin-muted" style={{ marginTop: 8, fontSize: '0.8rem' }}>
                  Primary role ({form.role_names[0]?.replace('_', ' ')}) {landingHint} after sign-in.
                </p>
              ) : null}
            </div>
          ) : null}
          <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
            {submitting ? 'Working…' : mode === 'invite' ? 'Send invite' : 'Create user'}
          </button>
        </form>
        {inviteUrl ? (
          <p className="admin-alert" style={{ marginTop: 12, wordBreak: 'break-all', fontSize: '0.875rem' }}>
            Invite link: {inviteUrl}
          </p>
        ) : null}
      </AdminPanel>

      <AdminPanel title={`Staff directory (${filtered.length})`} padded={false}>
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput value={search} onChange={setSearch} placeholder="Search staff…" />
          </AdminToolbar>
          {filtered.length === 0 ? (
            <AdminEmptyState title="No staff users" description="Add a user above or adjust search." />
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Roles</th>
                  <th>Modules</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {filtered.map((u) => (
                  <Fragment key={u.id}>
                    <tr>
                      <td>{u.full_name}</td>
                      <td>{u.email}</td>
                      <td>{(u.roles || []).join(', ')}</td>
                      <td>{(u.module_assignments || []).join(', ') || '—'}</td>
                      <td>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost admin-btn--sm"
                          onClick={() => {
                            if (editingId === u.id) setEditingId(null)
                            else {
                              setEditingId(u.id)
                              setEditModules(u.module_assignments ?? [])
                            }
                          }}
                        >
                          {editingId === u.id ? 'Cancel' : 'Modules'}
                        </button>
                      </td>
                    </tr>
                    {editingId === u.id ? (
                      <tr>
                        <td colSpan={5}>
                          <ModulePicker
                            catalog={catalog}
                            roleDefaults={roleDefaults}
                            selectedRoles={u.roles}
                            value={editModules}
                            onChange={setEditModules}
                          />
                          <button
                            type="button"
                            className="admin-btn admin-btn--primary admin-btn--sm"
                            style={{ marginTop: 12 }}
                            onClick={() => saveEditModules(u.id)}
                          >
                            Save modules
                          </button>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </AdminPanel>
    </>
  )
}
