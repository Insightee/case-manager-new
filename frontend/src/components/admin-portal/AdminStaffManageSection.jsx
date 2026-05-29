import { Fragment, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
} from './ui/index.js'
import { RbacEditor, buildRbacPayload, grantsFromAssignments, mergeGrants } from './ui/RbacEditor.jsx'
import { inviteEmailMessage } from '../../lib/inviteEmail.js'
import {
  formatInviteStatus,
  formatLoginReady,
  provisionActivateSuccess,
  provisionInviteFailure,
  provisionInviteSuccess,
} from '../../lib/userProvision.js'
import {
  hasDeprecatedStaffRole,
  moduleAccessSummary,
  primaryLandingHint,
} from '../../lib/rbacDisplay.js'

const EMPTY_FORM = {
  email: '',
  full_name: '',
  password: 'demo123',
  role_names: ['CASE_MANAGER'],
  region: '',
  module_assignments: [],
  module_access_grants: {},
  feature_overrides: {},
  view_only: false,
}

export function AdminStaffManageSection({
  catalog,
  roleDefaults,
  assignableRoles = [],
  deprecatedRoles = [],
  staff,
  pendingInvites = [],
  onReload,
  onSuccess,
  onError,
}) {
  const [mode, setMode] = useState('invite')
  const [form, setForm] = useState(EMPTY_FORM)
  const [inviteUrl, setInviteUrl] = useState('')
  const [search, setSearch] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editGrants, setEditGrants] = useState({})
  const [editOverrides, setEditOverrides] = useState({})
  const [editViewOnly, setEditViewOnly] = useState(false)
  const [editRoles, setEditRoles] = useState([])
  const [submitting, setSubmitting] = useState(false)
  const [resendingId, setResendingId] = useState(null)
  const [rowBusy, setRowBusy] = useState(null)
  const [lastProvision, setLastProvision] = useState(null)

  const deprecatedSet = useMemo(
    () => new Set((deprecatedRoles || []).map((r) => String(r).toUpperCase())),
    [deprecatedRoles],
  )

  const landingHint = useMemo(() => primaryLandingHint(form.role_names), [form.role_names])

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

  const filteredInvites = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return pendingInvites
    return pendingInvites.filter((i) => i.email?.toLowerCase().includes(q))
  }, [pendingInvites, search])

  function setRoles(roles) {
    const finalRoles = roles.length ? roles : form.role_names
    setForm((prev) => ({ ...prev, role_names: finalRoles }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    onError?.('')
    onSuccess?.('')
    setSubmitting(true)
    try {
      if (mode === 'invite') {
        const role = form.role_names[0] || 'CASE_MANAGER'
        const access = buildRbacPayload({
          roleNames: form.role_names,
          grants: form.module_access_grants,
          featureOverrides: form.feature_overrides,
          viewOnly: form.view_only,
        })
        const res = await apiFetch('/api/v1/admin/therapists/invite', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            full_name: form.full_name?.trim() || undefined,
            role_name: role,
            send_email: true,
            ...access,
          }),
        })
        setInviteUrl(res.invite_url)
        const deliveryMsg = inviteEmailMessage(form.email, res.email_delivery)
        if (res.email_delivery === 'skipped_no_smtp') {
          onError?.(deliveryMsg)
        } else {
          onSuccess?.(deliveryMsg)
        }
        onReload?.()
      } else {
        const access = buildRbacPayload({
          roleNames: form.role_names,
          grants: form.module_access_grants,
          featureOverrides: form.feature_overrides,
          viewOnly: form.view_only,
        })
        await apiFetch('/api/v1/admin/users', {
          method: 'POST',
          body: JSON.stringify({
            email: form.email,
            password: form.password,
            full_name: form.full_name,
            role_names: form.role_names,
            region: form.region || null,
            ...access,
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

  async function deactivateUser(userId, name) {
    if (!window.confirm(`Deactivate ${name}? They will not be able to sign in.`)) return
    onError?.('')
    try {
      await apiFetch(`/api/v1/admin/users/${userId}`, { method: 'DELETE' })
      onReload?.()
      onSuccess?.('User deactivated.')
    } catch (err) {
      onError?.(err.message || 'Could not deactivate user')
    }
  }

  async function activateForLogin(u) {
    const key = `${u.id}:activate`
    if (rowBusy) return
    onError?.('')
    setRowBusy(key)
    try {
      const res = await apiFetch(`/api/v1/admin/users/${u.id}/activate-for-login`, {
        method: 'POST',
        timeoutMs: 20_000,
      })
      setLastProvision({ email: res.email, ...res })
      onSuccess?.(provisionActivateSuccess(res))
      onReload?.()
    } catch (err) {
      onError?.(err.message || `Could not activate ${u.email}`)
    } finally {
      setRowBusy(null)
    }
  }

  async function inviteToLogin(u) {
    const key = `${u.id}:invite`
    if (rowBusy) return
    onError?.('')
    setRowBusy(key)
    try {
      const res = await apiFetch(`/api/v1/admin/users/${u.id}/invite-to-login`, {
        method: 'POST',
        timeoutMs: 20_000,
      })
      setLastProvision({ email: res.email, ...res })
      const fail = provisionInviteFailure(res)
      if (fail) onError?.(fail)
      onSuccess?.(provisionInviteSuccess(res))
      if (res.invite_url) setInviteUrl(res.invite_url)
      onReload?.()
    } catch (err) {
      onError?.(err.message || `Could not invite ${u.email}`)
    } finally {
      setRowBusy(null)
    }
  }

  function loginMetaLine(u) {
    const parts = [
      formatLoginReady(u.login_ready, u.is_active),
      formatInviteStatus(u.invite_status),
    ]
    if (u.last_invite_sent_at) {
      parts.push(`Last email ${new Date(u.last_invite_sent_at).toLocaleString()}`)
    }
    return parts.join(' · ')
  }

  function rowLoginActions(u) {
    const busyActivate = rowBusy === `${u.id}:activate`
    const busyInvite = rowBusy === `${u.id}:invite`
    const link = u.pending_invite_url || (lastProvision?.email === u.email ? lastProvision.invite_url : null)
    return (
      <div className="admin-btn-group admin-btn-group--wrap">
        {!u.is_active ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={!!rowBusy}
            onClick={() => activateForLogin(u)}
          >
            {busyActivate ? 'Activating…' : 'Activate user'}
          </button>
        ) : null}
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={!!rowBusy}
          onClick={() => inviteToLogin(u)}
        >
          {busyInvite ? 'Sending…' : u.invite_status === 'pending' ? 'Resend invite' : 'Invite to login'}
        </button>
        {link ? (
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => copyLink(link)}>
            Copy login link
          </button>
        ) : null}
        {u.is_active ? (
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={!!rowBusy}
            onClick={() => deactivateUser(u.id, u.full_name)}
          >
            Deactivate
          </button>
        ) : null}
      </div>
    )
  }

  async function saveEditAccess(userId) {
    onError?.('')
    try {
      const access = buildRbacPayload({
        roleNames: editRoles,
        grants: editGrants,
        featureOverrides: editOverrides,
        viewOnly: editViewOnly,
      })
      await apiFetch(`/api/v1/admin/users/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          role_names: editRoles,
          ...access,
        }),
      })
      setEditingId(null)
      onReload?.()
      onSuccess?.('Access updated.')
    } catch (err) {
      onError?.(err.message || 'Could not update modules')
    }
  }

  function copyLink(url) {
    navigator.clipboard?.writeText(url)
    onSuccess?.('Link copied to clipboard')
  }

  async function resendInviteEmail(inviteId, email) {
    onError?.('')
    setResendingId(inviteId)
    try {
      const res = await apiFetch(`/api/v1/admin/invites/${inviteId}/resend-email`, {
        method: 'POST',
      })
      const msg = inviteEmailMessage(email, res.email_delivery)
      if (res.email_delivery === 'skipped_no_smtp') {
        onError?.(msg)
      } else {
        onSuccess?.(msg)
      }
    } catch (err) {
      onError?.(err.message || 'Could not resend invite email')
    } finally {
      setResendingId(null)
    }
  }

  return (
    <>
      <AdminPanel
        title="Add staff user"
        subtitle="Role sets permissions; programme modules set which areas appear and whether each is view or edit."
      >
        <div style={{ marginBottom: 16, display: 'flex', gap: 8 }}>
          <button
            type="button"
            className={`admin-btn admin-btn--sm ${mode === 'invite' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => { setMode('invite'); setInviteUrl('') }}
          >
            Send invite
          </button>
          <button
            type="button"
            className={`admin-btn admin-btn--sm ${mode === 'direct' ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
            onClick={() => { setMode('direct'); setInviteUrl('') }}
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
          <label>
            Full name
            <input
              className="admin-input"
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required={mode === 'direct'}
              placeholder={mode === 'invite' ? 'Shown on invite (optional)' : ''}
            />
          </label>
          {mode === 'direct' ? (
            <>
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

          <RbacEditor
            catalog={catalog}
            assignableRoles={assignableRoles}
            roleDefaults={roleDefaults}
            selectedRoles={form.role_names}
            onRoleChange={setRoles}
            allowMultiRole={mode === 'direct'}
            disabled={submitting}
            grants={form.module_access_grants}
            onGrantsChange={(module_access_grants) =>
              setForm((prev) => ({
                ...prev,
                module_access_grants,
                module_assignments: Object.entries(module_access_grants)
                  .filter(([, g]) => g?.enabled)
                  .map(([id]) => id),
              }))
            }
            featureOverrides={form.feature_overrides}
            onOverridesChange={(feature_overrides) =>
              setForm((prev) => ({ ...prev, feature_overrides }))
            }
            viewOnly={form.view_only}
            onViewOnlyChange={(view_only) => setForm((prev) => ({ ...prev, view_only }))}
          />

          {landingHint ? (
            <p className="admin-muted" style={{ fontSize: '0.8rem', marginTop: -8 }}>
              Selected role ({form.role_names.map((r) => r.replace(/_/g, ' ')).join(', ')}) — {landingHint}
            </p>
          ) : null}

          <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
            {submitting ? 'Working…' : mode === 'invite' ? 'Send invite' : 'Create user'}
          </button>
        </form>

        {inviteUrl ? (
          <div className="admin-alert" style={{ marginTop: 12, wordBreak: 'break-all', fontSize: '0.875rem' }}>
            <strong>Invite link:</strong>{' '}
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={() => copyLink(inviteUrl)}
            >
              Copy
            </button>{' '}
            {inviteUrl}
          </div>
        ) : null}
      </AdminPanel>

      {filteredInvites.length > 0 ? (
        <AdminPanel title={`Pending staff invitations (${filteredInvites.length})`} subtitle="Links expire after 7 days">
          <ul className="admin-queue">
            {filteredInvites.map((inv) => (
              <li key={inv.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">{inv.email}</p>
                  <p className="admin-queue__meta">
                    {inv.role_name?.replace(/_/g, ' ')} · Expires {new Date(inv.expires_at).toLocaleDateString()}
                  </p>
                </div>
                <div className="admin-btn-group">
                  {inv.invite_url ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={() => copyLink(inv.invite_url)}
                    >
                      Copy link
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    disabled={resendingId === inv.id}
                    onClick={() => resendInviteEmail(inv.id, inv.email)}
                  >
                    {resendingId === inv.id ? 'Sending…' : 'Resend email'}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </AdminPanel>
      ) : null}

      <AdminPanel title={`Staff directory (${filtered.length})`} padded={false}>
        <div className="admin-panel__body">
          <div className="admin-desktop-only">
            <AdminToolbar>
              <AdminSearchInput value={search} onChange={setSearch} placeholder="Search staff…" />
            </AdminToolbar>
          </div>
          {filtered.length === 0 ? (
            <AdminEmptyState title="No staff users" description="Add a user above or adjust search." />
          ) : (
            <AdminDataList
              desktop={
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Access</th>
                    <th>Status</th>
                    <th>Login</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((u) => (
                    <Fragment key={u.id}>
                      <tr>
                        <td>
                          <span className="admin-table__primary">{u.full_name}</span>
                        </td>
                        <td>
                          <span className="admin-table__primary">{u.email}</span>
                        </td>
                        <td>
                          <div className="admin-chip-row">
                            {(u.roles || []).map((r) => {
                              const id = String(r).toUpperCase()
                              const legacy = deprecatedSet.has(id) || hasDeprecatedStaffRole([id])
                              return (
                                <span
                                  key={r}
                                  className={`admin-chip ${legacy ? 'admin-chip--warn' : ''}`}
                                  title={legacy ? 'Legacy role — assign Module Admin or Case Manager for new users' : ''}
                                >
                                  {r.replace(/_/g, ' ')}
                                  {legacy ? ' (legacy)' : ''}
                                </span>
                              )
                            })}
                          </div>
                        </td>
                        <td>
                          <div className="rbac-access-summary">
                            {moduleAccessSummary(u, catalog, grantsFromAssignments).map((row) => (
                              <span
                                key={row.id}
                                className={`admin-badge admin-badge--sm ${
                                  row.access === 'Edit' ? 'admin-badge--success' : 'admin-badge--neutral'
                                }`}
                              >
                                {row.label}: {row.access}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td>
                          <StatusBadge tone={u.is_active ? 'success' : 'neutral'}>
                            {u.is_active ? 'Active' : 'Inactive'}
                          </StatusBadge>
                        </td>
                        <td>
                          <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
                            {loginMetaLine(u)}
                          </p>
                        </td>
                        <td>
                          <div className="admin-btn-group admin-btn-group--wrap">
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              disabled={!!rowBusy}
                              onClick={() => {
                                if (editingId === u.id) {
                                  setEditingId(null)
                                } else {
                                  setEditingId(u.id)
                                  setEditGrants(
                                    Object.keys(u.service_access_grants || {}).length ||
                                      Object.keys(u.org_capability_grants || {}).length
                                      ? mergeGrants(u.service_access_grants || {}, u.org_capability_grants || {})
                                      : Object.keys(u.module_access_grants || {}).length
                                        ? u.module_access_grants
                                        : grantsFromAssignments(u.module_assignments ?? [], u.is_view_only),
                                  )
                                  setEditOverrides(u.feature_overrides ?? {})
                                  setEditViewOnly(u.is_view_only ?? false)
                                  setEditRoles([...(u.roles || [])])
                                }
                              }}
                            >
                              {editingId === u.id ? 'Cancel' : 'Edit access'}
                            </button>
                            {rowLoginActions(u)}
                          </div>
                        </td>
                      </tr>
                      {editingId === u.id ? (
                        <tr>
                          <td colSpan={8} style={{ padding: '12px 16px', background: '#f8fafc' }}>
                            {hasDeprecatedStaffRole(u.roles) ? (
                              <p className="admin-alert admin-alert--warn rbac-editor__hint">
                                Legacy role detected. Prefer Module Admin, Case Manager, or Finance when re-provisioning access.
                              </p>
                            ) : null}
                            <RbacEditor
                              catalog={catalog}
                              assignableRoles={assignableRoles}
                              roleDefaults={roleDefaults}
                              selectedRoles={editRoles}
                              onRoleChange={setEditRoles}
                              allowMultiRole
                              grants={editGrants}
                              onGrantsChange={setEditGrants}
                              featureOverrides={editOverrides}
                              onOverridesChange={setEditOverrides}
                              viewOnly={editViewOnly}
                              onViewOnlyChange={setEditViewOnly}
                            />
                            <div className="admin-btn-group" style={{ marginTop: 12 }}>
                              <button
                                type="button"
                                className="admin-btn admin-btn--primary admin-btn--sm"
                                onClick={() => saveEditAccess(u.id)}
                              >
                                Save access
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--ghost admin-btn--sm"
                                onClick={() => setEditingId(null)}
                              >
                                Cancel
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
              }
              mobile={
                <ul className="admin-data-list__cards">
                  {filtered.map((u) => (
                    <li key={u.id}>
                      <AdminTaskCard
                        title={u.full_name}
                        meta={u.email}
                        badges={
                          <>
                            <StatusBadge tone={u.is_active ? 'success' : 'neutral'}>
                              {u.is_active ? 'Active' : 'Inactive'}
                            </StatusBadge>
                            <StatusBadge tone={u.login_ready ? 'success' : 'neutral'}>
                              {u.login_ready ? 'Login ready' : 'Not login-ready'}
                            </StatusBadge>
                          </>
                        }
                        actions={
                          <div className="admin-btn-group admin-btn-group--wrap">
                            <button
                              type="button"
                              className="admin-btn admin-btn--ghost admin-btn--sm"
                              disabled={!!rowBusy}
                              onClick={() => {
                                if (editingId === u.id) {
                                  setEditingId(null)
                                } else {
                                  setEditingId(u.id)
                                  setEditGrants(
                                    Object.keys(u.service_access_grants || {}).length ||
                                      Object.keys(u.org_capability_grants || {}).length
                                      ? mergeGrants(u.service_access_grants || {}, u.org_capability_grants || {})
                                      : Object.keys(u.module_access_grants || {}).length
                                        ? u.module_access_grants
                                        : grantsFromAssignments(u.module_assignments ?? [], u.is_view_only),
                                  )
                                  setEditOverrides(u.feature_overrides ?? {})
                                  setEditViewOnly(u.is_view_only ?? false)
                                  setEditRoles([...(u.roles || [])])
                                }
                              }}
                            >
                              {editingId === u.id ? 'Cancel' : 'Edit access'}
                            </button>
                            {rowLoginActions(u)}
                          </div>
                        }
                      >
                        <p className="admin-muted" style={{ margin: '0 0 8px', fontSize: '0.8125rem' }}>
                          {loginMetaLine(u)}
                        </p>
                        <div className="admin-chip-row" style={{ marginBottom: 8 }}>
                          {(u.roles || []).map((r) => {
                            const id = String(r).toUpperCase()
                            const legacy = deprecatedSet.has(id) || hasDeprecatedStaffRole([id])
                            return (
                              <span key={r} className={`admin-chip ${legacy ? 'admin-chip--warn' : ''}`}>
                                {r.replace(/_/g, ' ')}
                              </span>
                            )
                          })}
                        </div>
                        <div className="rbac-access-summary">
                          {moduleAccessSummary(u, catalog, grantsFromAssignments).map((row) => (
                            <span
                              key={row.id}
                              className={`admin-badge admin-badge--sm ${
                                row.access === 'Edit' ? 'admin-badge--success' : 'admin-badge--neutral'
                              }`}
                            >
                              {row.label}: {row.access}
                            </span>
                          ))}
                        </div>
                        {editingId === u.id ? (
                          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
                            {hasDeprecatedStaffRole(u.roles) ? (
                              <p className="admin-alert admin-alert--warn rbac-editor__hint">
                                Legacy role detected. Prefer Module Admin, Case Manager, or Finance when re-provisioning access.
                              </p>
                            ) : null}
                            <RbacEditor
                              catalog={catalog}
                              assignableRoles={assignableRoles}
                              roleDefaults={roleDefaults}
                              selectedRoles={editRoles}
                              onRoleChange={setEditRoles}
                              allowMultiRole
                              grants={editGrants}
                              onGrantsChange={setEditGrants}
                              featureOverrides={editOverrides}
                              onOverridesChange={setEditOverrides}
                              viewOnly={editViewOnly}
                              onViewOnlyChange={setEditViewOnly}
                            />
                            <div className="admin-btn-group" style={{ marginTop: 12 }}>
                              <button
                                type="button"
                                className="admin-btn admin-btn--primary admin-btn--sm"
                                onClick={() => saveEditAccess(u.id)}
                              >
                                Save access
                              </button>
                              <button
                                type="button"
                                className="admin-btn admin-btn--ghost admin-btn--sm"
                                onClick={() => setEditingId(null)}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </AdminTaskCard>
                    </li>
                  ))}
                </ul>
              }
            />
          )}
        </div>
      </AdminPanel>
    </>
  )
}
