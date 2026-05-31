import { useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { CopyLinkButton } from './CopyLinkButton.jsx'
import {
  provisionActivateSuccess,
  provisionInviteFailure,
  provisionInviteSuccess,
} from '../../../lib/userProvision.js'

/**
 * Uniform login lifecycle actions for People directory rows (staff, therapists, parents).
 */
export function PeopleRowActions({
  user,
  rowBusy,
  setRowBusy,
  onReload,
  onSuccess,
  onError,
  lastProvision,
  setLastProvision,
  disabled = false,
  extraActions = null,
  showDeactivate = true,
}) {
  if (!user?.id) return extraActions || null

  const busyActivate = rowBusy === `${user.id}:activate`
  const busyInvite = rowBusy === `${user.id}:invite`
  const busyReactivate = rowBusy === `${user.id}:reactivate`
  const link =
    user.pending_invite_url ||
    (lastProvision?.email === user.email ? lastProvision.invite_url : null)

  async function activateForLogin() {
    const key = `${user.id}:activate`
    if (rowBusy) return
    onError?.('')
    setRowBusy?.(key)
    try {
      const res = await apiFetch(`/api/v1/admin/users/${user.id}/activate-for-login`, {
        method: 'POST',
        timeoutMs: 20_000,
      })
      setLastProvision?.({ email: res.email, ...res })
      onSuccess?.(provisionActivateSuccess(res))
      onReload?.()
    } catch (err) {
      onError?.(err.message || `Could not activate ${user.email}`)
    } finally {
      setRowBusy?.(null)
    }
  }

  async function inviteToLogin() {
    const key = `${user.id}:invite`
    if (rowBusy) return
    onError?.('')
    setRowBusy?.(key)
    try {
      const res = await apiFetch(`/api/v1/admin/users/${user.id}/invite-to-login`, {
        method: 'POST',
        timeoutMs: 20_000,
      })
      setLastProvision?.({ email: res.email, ...res })
      const fail = provisionInviteFailure(res)
      if (fail) onError?.(fail)
      else onSuccess?.(provisionInviteSuccess(res))
      onReload?.()
    } catch (err) {
      onError?.(err.message || `Could not invite ${user.email}`)
    } finally {
      setRowBusy?.(null)
    }
  }

  async function deactivateUser() {
    const name = user.full_name || user.email
    if (!window.confirm(`Deactivate ${name}? They will not be able to sign in.`)) return
    onError?.('')
    try {
      await apiFetch(`/api/v1/admin/users/${user.id}`, { method: 'DELETE' })
      onReload?.()
      onSuccess?.('User deactivated.')
    } catch (err) {
      onError?.(err.message || 'Could not deactivate user')
    }
  }

  async function reactivateCase(caseId) {
    if (!caseId) return
    if (!window.confirm('Reactivate this case? Status will return to Active.')) return
    const key = `${user.id}:reactivate`
    onError?.('')
    setRowBusy?.(key)
    try {
      await apiFetch(`/api/v1/cases/${caseId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'ACTIVE' }),
      })
      onSuccess?.('Case reactivated.')
      onReload?.()
    } catch (err) {
      onError?.(err.message || 'Could not reactivate case')
    } finally {
      setRowBusy?.(null)
    }
  }

  const showReactivateCase = user._reactivateCaseId

  return (
    <div className="admin-btn-group admin-btn-group--wrap">
      {extraActions}
      {!user.is_active ? (
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={disabled || !!rowBusy}
          onClick={activateForLogin}
        >
          {busyActivate ? 'Activating…' : 'Activate user'}
        </button>
      ) : null}
      {showReactivateCase && user.is_active !== false ? (
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={disabled || !!rowBusy}
          onClick={() => reactivateCase(user._reactivateCaseId)}
        >
          {busyReactivate ? 'Reopening…' : 'Reactivate case'}
        </button>
      ) : null}
      <button
        type="button"
        className="admin-btn admin-btn--ghost admin-btn--sm"
        disabled={disabled || !!rowBusy}
        onClick={inviteToLogin}
      >
        {busyInvite ? 'Sending…' : user.invite_status === 'pending' ? 'Resend invite' : 'Invite to login'}
      </button>
      {link ? <CopyLinkButton url={link} label="Copy login link" /> : null}
      {showDeactivate && user.is_active ? (
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={disabled || !!rowBusy}
          onClick={deactivateUser}
        >
          Deactivate
        </button>
      ) : null}
    </div>
  )
}

export function PeopleBulkToolbar({
  selectedUserIds = [],
  selectedInviteIds = [],
  onReload,
  onSuccess,
  onError,
  disabled = false,
}) {
  const [busy, setBusy] = useState(null)
  const userCount = selectedUserIds.length
  const inviteCount = selectedInviteIds.length
  if (!userCount && !inviteCount) return null

  async function bulkUserStatus(isActive) {
    const label = isActive ? 'activate' : 'deactivate'
    if (!window.confirm(`${label.charAt(0).toUpperCase() + label.slice(1)} ${userCount} selected user(s)?`)) {
      return
    }
    setBusy(label)
    onError?.('')
    try {
      const res = await apiFetch('/api/v1/admin/users/bulk-status', {
        method: 'POST',
        body: JSON.stringify({ user_ids: selectedUserIds, is_active: isActive }),
      })
      onSuccess?.(`${res.updated} user(s) ${isActive ? 'activated' : 'deactivated'}.`)
      onReload?.()
    } catch (err) {
      onError?.(err.message || `Bulk ${label} failed`)
    } finally {
      setBusy(null)
    }
  }

  async function bulkRevokeInvites() {
    if (!window.confirm(`Cancel ${inviteCount} selected invite(s)? Links will stop working.`)) return
    setBusy('revoke')
    onError?.('')
    try {
      const res = await apiFetch('/api/v1/admin/invites/bulk-revoke', {
        method: 'POST',
        body: JSON.stringify({ invite_ids: selectedInviteIds }),
      })
      onSuccess?.(`${res.revoked} invite(s) cancelled.`)
      onReload?.()
    } catch (err) {
      onError?.(err.message || 'Bulk cancel failed')
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="admin-toolbar admin-toolbar--bulk" style={{ marginBottom: 12, gap: 8, flexWrap: 'wrap' }}>
      {userCount > 0 ? (
        <>
          <button
            type="button"
            className="admin-btn admin-btn--primary admin-btn--sm"
            disabled={disabled || !!busy}
            onClick={() => bulkUserStatus(true)}
          >
            {busy === 'activate' ? 'Activating…' : `Activate (${userCount})`}
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={disabled || !!busy}
            onClick={() => bulkUserStatus(false)}
          >
            {busy === 'deactivate' ? 'Deactivating…' : `Deactivate (${userCount})`}
          </button>
        </>
      ) : null}
      {inviteCount > 0 ? (
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          disabled={disabled || !!busy}
          onClick={bulkRevokeInvites}
        >
          {busy === 'revoke' ? 'Cancelling…' : `Cancel invites (${inviteCount})`}
        </button>
      ) : null}
    </div>
  )
}

export function PeopleSelectCheckbox({ checked, onChange, ariaLabel }) {
  return (
    <input
      type="checkbox"
      checked={checked}
      onChange={onChange}
      aria-label={ariaLabel}
      style={{ width: 16, height: 16 }}
    />
  )
}
