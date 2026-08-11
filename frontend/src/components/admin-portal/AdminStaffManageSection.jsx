import { Fragment, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { fetchAllStaff } from '../../lib/peopleDirectoryApi.js'
import { PEOPLE_PAGE_SIZE } from '../../lib/peopleDirectoryList.js'
import { exportStaffCsv } from '../../lib/peopleDirectoryExport.js'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
  CopyLinkButton,
  PeopleRowActions,
  PeopleBulkToolbar,
  PeopleSelectCheckbox,
  PeoplePendingInvitesToggle,
  PeoplePendingInvitesPanel,
  PeopleListPagination,
} from './ui/index.js'
import { RbacEditor, buildRbacPayload, grantsFromAssignments, mergeGrants } from './ui/RbacEditor.jsx'
import { inviteEmailMessage } from '../../lib/inviteEmail.js'
import { accountStatusLabel, accountStatusTone } from '../../lib/accountStatus.js'
import {
  hasDeprecatedStaffRole,
  moduleAccessSummary,
  primaryLandingHint,
} from '../../lib/rbacDisplay.js'
import { staffDepartmentLabel } from '../../lib/staffDepartments.js'

const EMPTY_FORM = {
  email: '',
  full_name: '',
  password: 'demo123',
  role_names: ['CASE_MANAGER'],
  department: null,
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
  staffDepartments = [],
  deprecatedRoles = [],
  staff,
  staffTotal = 0,
  staffPage = 1,
  onStaffPageChange,
  staffSearch = '',
  onStaffSearchChange,
  staffLoading = false,
  pendingInvites = [],
  onReload,
  onSuccess,
  onError,
}) {
  const [mode, setMode] = useState('invite')
  const [form, setForm] = useState(EMPTY_FORM)
  const [inviteUrl, setInviteUrl] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editGrants, setEditGrants] = useState({})
  const [editOverrides, setEditOverrides] = useState({})
  const [editViewOnly, setEditViewOnly] = useState(false)
  const [editRoles, setEditRoles] = useState([])
  const [editDepartment, setEditDepartment] = useState(null)
  const [showCreatePassword, setShowCreatePassword] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [rowBusy, setRowBusy] = useState(null)
  const [lastProvision, setLastProvision] = useState(null)
  const [selectedStaffIds, setSelectedStaffIds] = useState(() => new Set())
  const [invitesViewOpen, setInvitesViewOpen] = useState(false)
  const [addStaffViewOpen, setAddStaffViewOpen] = useState(false)

  const staffPages = Math.max(1, Math.ceil(staffTotal / PEOPLE_PAGE_SIZE))
  const safeStaffPage = Math.min(Math.max(1, staffPage), staffPages)
  const staffRangeStart = staffTotal ? (safeStaffPage - 1) * PEOPLE_PAGE_SIZE + 1 : 0
  const staffRangeEnd = Math.min(safeStaffPage * PEOPLE_PAGE_SIZE, staffTotal)

  const deprecatedSet = useMemo(
    () => new Set((deprecatedRoles || []).map((r) => String(r).toUpperCase())),
    [deprecatedRoles],
  )

  const landingHint = useMemo(() => primaryLandingHint(form.role_names), [form.role_names])

  async function handleExportCsv() {
    try {
      const result = await fetchAllStaff({ search: staffSearch })
      exportStaffCsv(result.items, {
        catalog,
        grantsFromAssignments,
        includeAccess: true,
        staffDepartments,
      })
    } catch (err) {
      onError?.(err.message || 'Could not export staff CSV')
    }
  }

  function setRoles(roles) {
    const finalRoles = roles.length ? roles : form.role_names
    setForm((prev) => ({ ...prev, role_names: finalRoles }))
  }

  function closeAddStaff() {
    setAddStaffViewOpen(false)
    setInviteUrl('')
    setForm(EMPTY_FORM)
    setMode('invite')
    setShowCreatePassword(false)
  }

  function toggleAddStaff() {
    if (addStaffViewOpen) {
      closeAddStaff()
      return
    }
    setInvitesViewOpen(false)
    setAddStaffViewOpen(true)
  }

  function toggleInvitesView() {
    if (invitesViewOpen) {
      setInvitesViewOpen(false)
      return
    }
    closeAddStaff()
    setInvitesViewOpen(true)
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
            department: form.department || undefined,
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
            department: form.department || undefined,
            region: form.region || null,
            ...access,
          }),
        })
        setForm(EMPTY_FORM)
        setAddStaffViewOpen(false)
        onSuccess?.('Staff user created.')
        onReload?.()
      }
    } catch (err) {
      onError?.(err.message || 'Action failed')
    } finally {
      setSubmitting(false)
    }
  }

  function staffStatus(u) {
    return accountStatusLabel(u)
  }

  function toggleStaffSelect(id) {
    setSelectedStaffIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
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
          department: editDepartment,
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

  return (
    <>
      <div className="admin-btn-group" style={{ marginBottom: 12 }}>
        {!invitesViewOpen ? (
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            onClick={toggleAddStaff}
            aria-pressed={addStaffViewOpen}
          >
            Add staff
          </button>
        ) : null}
        <PeoplePendingInvitesToggle
          label="Pending staff invitations"
          count={pendingInvites.length}
          active={invitesViewOpen}
          onClick={toggleInvitesView}
        />
      </div>

      {invitesViewOpen ? (
        <PeoplePendingInvitesPanel
          label="Pending staff invitations"
          pendingInvites={pendingInvites}
          layout="queue"
          open={invitesViewOpen}
          onOpenChange={setInvitesViewOpen}
          onSuccess={onSuccess}
          onError={onError}
          onReload={onReload}
        />
      ) : addStaffViewOpen ? (
        <AdminPanel
          title="Add staff user"
          subtitle="Role sets permissions; programme modules set which areas appear and whether each is view or edit."
          actions={
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={closeAddStaff}>
              ← Back
            </button>
          }
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
                  <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <input
                      className="admin-input"
                      type={showCreatePassword ? 'text' : 'password'}
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      minLength={6}
                      required
                      style={{ width: '100%', paddingRight: '50px' }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowCreatePassword(!showCreatePassword)}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        fontSize: '0.75rem',
                        fontWeight: 600,
                        color: '#4f46e5',
                        padding: '4px 8px',
                      }}
                    >
                      {showCreatePassword ? 'Hide' : 'Show'}
                    </button>
                  </div>
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
              staffDepartments={staffDepartments}
              selectedDepartment={form.department}
              onDepartmentChange={(department) => setForm((prev) => ({ ...prev, department }))}
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

            <div className="admin-btn-group" style={{ gridColumn: '1 / -1' }}>
              <button type="submit" className="admin-btn admin-btn--primary" disabled={submitting}>
                {submitting ? 'Working…' : mode === 'invite' ? 'Send invite' : 'Create user'}
              </button>
              <button type="button" className="admin-btn admin-btn--ghost" onClick={closeAddStaff}>
                Cancel
              </button>
            </div>
          </form>

          {inviteUrl ? (
            <div className="admin-alert" style={{ marginTop: 12, wordBreak: 'break-all', fontSize: '0.875rem' }}>
              <strong>Invite link:</strong>{' '}
              <CopyLinkButton url={inviteUrl} label="Copy" copiedLabel="Copied" />{' '}
              {inviteUrl}
            </div>
          ) : null}
        </AdminPanel>
      ) : (
        <AdminPanel
          title={`Staff directory (${staffTotal})`}
          padded={false}
          actions={
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={handleExportCsv}
            >
              Download CSV
            </button>
          }
        >
        <div className="admin-panel__body">
          <AdminToolbar>
            <AdminSearchInput
              value={staffSearch}
              onChange={onStaffSearchChange}
              placeholder="Search staff by name or email…"
            />
          </AdminToolbar>
          {staffLoading ? (
            <p className="admin-muted">Loading staff…</p>
          ) : staffTotal === 0 ? (
            <AdminEmptyState title="No staff users" description="Use Add staff or adjust search." />
          ) : staff.length === 0 ? (
            <AdminEmptyState title="No staff match" description="Try adjusting search." />
          ) : (
            <>
            <PeopleBulkToolbar
              selectedUserIds={[...selectedStaffIds]}
              onReload={() => {
                setSelectedStaffIds(new Set())
                onReload?.()
              }}
              onSuccess={onSuccess}
              onError={onError}
            />
            <AdminDataList
              desktop={
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th style={{ width: 36 }} aria-label="Select" />
                    <th>Name</th>
                    <th>Email</th>
                    <th>Department</th>
                    <th>Role</th>
                    <th>Access</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {staff.map((u) => (
                    <Fragment key={u.id}>
                      <tr>
                        <td>
                          <PeopleSelectCheckbox
                            checked={selectedStaffIds.has(u.id)}
                            onChange={() => toggleStaffSelect(u.id)}
                            ariaLabel={`Select ${u.full_name}`}
                          />
                        </td>
                        <td>
                          <span className="admin-table__primary">{u.full_name}</span>
                        </td>
                        <td>
                          <span className="admin-table__primary">{u.email}</span>
                        </td>
                        <td>
                          {staffDepartmentLabel(u.department, staffDepartments) ? (
                            <span className="admin-chip">{staffDepartmentLabel(u.department, staffDepartments)}</span>
                          ) : (
                            <span className="admin-muted">—</span>
                          )}
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
                          <StatusBadge tone={accountStatusTone(staffStatus(u))}>
                            {staffStatus(u)}
                          </StatusBadge>
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
                                  setEditDepartment(u.department || null)
                                }
                              }}
                            >
                              {editingId === u.id ? 'Cancel' : 'Edit access'}
                            </button>
                            <PeopleRowActions
                              user={u}
                              rowBusy={rowBusy}
                              setRowBusy={setRowBusy}
                              onReload={onReload}
                              onSuccess={onSuccess}
                              onError={onError}
                              lastProvision={lastProvision}
                              setLastProvision={setLastProvision}
                            />
                          </div>
                        </td>
                      </tr>
                      {editingId === u.id ? (
                        <tr>
                          <td colSpan={9} style={{ padding: '12px 16px', background: '#f8fafc' }}>
                            {hasDeprecatedStaffRole(u.roles) ? (
                              <p className="admin-alert admin-alert--warn rbac-editor__hint">
                                Legacy role detected. Prefer Module Admin, Case Manager, or Finance when re-provisioning access.
                              </p>
                            ) : null}
                            <RbacEditor
                              catalog={catalog}
                              assignableRoles={assignableRoles}
                              staffDepartments={staffDepartments}
                              selectedDepartment={editDepartment}
                              onDepartmentChange={setEditDepartment}
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
                  {staff.map((u) => (
                    <li key={u.id}>
                      <AdminTaskCard
                        title={u.full_name}
                        meta={u.email}
                        badges={
                          <StatusBadge tone={accountStatusTone(staffStatus(u))}>
                            {staffStatus(u)}
                          </StatusBadge>
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
                                  setEditDepartment(u.department || null)
                                }
                              }}
                            >
                              {editingId === u.id ? 'Cancel' : 'Edit access'}
                            </button>
                            <PeopleRowActions
                              user={u}
                              rowBusy={rowBusy}
                              setRowBusy={setRowBusy}
                              onReload={onReload}
                              onSuccess={onSuccess}
                              onError={onError}
                              lastProvision={lastProvision}
                              setLastProvision={setLastProvision}
                            />
                          </div>
                        }
                      >
                        {staffDepartmentLabel(u.department, staffDepartments) ? (
                          <p className="admin-muted" style={{ margin: '0 0 8px' }}>
                            {staffDepartmentLabel(u.department, staffDepartments)}
                          </p>
                        ) : null}
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
                              staffDepartments={staffDepartments}
                              selectedDepartment={editDepartment}
                              onDepartmentChange={setEditDepartment}
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
            <PeopleListPagination
              page={safeStaffPage}
              totalPages={staffPages}
              total={staffTotal}
              rangeStart={staffRangeStart}
              rangeEnd={staffRangeEnd}
              onPageChange={onStaffPageChange}
            />
            </>
          )}
        </div>
      </AdminPanel>
      )}
    </>
  )
}
