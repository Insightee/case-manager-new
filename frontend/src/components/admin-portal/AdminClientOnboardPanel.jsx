import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PeoplePendingInvitesPanel, PeoplePendingInvitesToggle } from './ui/index.js'

export function AdminClientOnboardPanel({
  canCreateCase,
  canManageUsers,
  isHrPortal,
  pendingInvites,
  parentsAwaitingLoginCount = 0,
  onBulkInviteAwaitingLogin,
  invitesViewOpen,
  onInvitesViewChange,
  onAddFamily,
  onSuccess,
  onError,
  onReload,
}) {
  const navigate = useNavigate()
  const [bulkBusy, setBulkBusy] = useState(false)

  async function handleBulkAwaitingLogin() {
    if (!onBulkInviteAwaitingLogin || bulkBusy) return
    setBulkBusy(true)
    onError?.('')
    try {
      await onBulkInviteAwaitingLogin()
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <>
      <div className="admin-btn-group admin-people-onboard">
        {!invitesViewOpen ? (
          <>
            {canCreateCase ? (
              <button
                type="button"
                className="admin-btn admin-btn--primary admin-btn--sm"
                onClick={() => navigate('/admin/cases?allot=1')}
              >
                Add client & case
              </button>
            ) : null}
            <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={onAddFamily}>
              Add family
            </button>
            <Link to="/admin/client-profiles" className="admin-btn admin-btn--ghost admin-btn--sm">
              Bulk import
            </Link>
          </>
        ) : null}
        {canManageUsers ? (
          <>
            <PeoplePendingInvitesToggle
              label="Pending parent invites"
              count={pendingInvites.length}
              active={invitesViewOpen}
              onClick={() => onInvitesViewChange?.(!invitesViewOpen)}
            />
            {parentsAwaitingLoginCount > 0 ? (
              <button
                type="button"
                className="admin-btn admin-btn--secondary admin-btn--sm"
                disabled={bulkBusy}
                onClick={handleBulkAwaitingLogin}
              >
                {bulkBusy
                  ? 'Sending invites…'
                  : `Invite parents awaiting login (${parentsAwaitingLoginCount})`}
              </button>
            ) : null}
          </>
        ) : null}
        <Link to="/admin/client-profiles" className="admin-btn admin-btn--secondary admin-btn--sm">
          Bulk import
        </Link>
      </div>

      {!canManageUsers ? (
        <p className="admin-muted admin-people-onboard__hint">
          Families are read-only here. Use case allotment to add a child with a parent account.
        </p>
      ) : null}

      {canManageUsers && parentsAwaitingLoginCount > 0 && !invitesViewOpen ? (
        <p className="admin-muted admin-people-onboard__hint">
          {parentsAwaitingLoginCount} parent(s) with open cases have not signed in yet — includes expired
          invites and accounts waiting on first login.
        </p>
      ) : null}

      {canManageUsers ? (
        <PeoplePendingInvitesPanel
          label="Pending parent invites"
          subtitle="Active invite links not yet accepted (expire after 7 days)"
          pendingInvites={pendingInvites}
          open={invitesViewOpen}
          onOpenChange={onInvitesViewChange}
          onSuccess={onSuccess}
          onError={onError}
          onReload={onReload}
        />
      ) : null}

      {isHrPortal && !invitesViewOpen ? (
        <p className="admin-muted admin-people-onboard__hint">
          HR view: open cases from each client row or{' '}
          <Link to="/hr/cases">case list</Link>.
        </p>
      ) : null}
    </>
  )
}
