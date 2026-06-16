import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { PeoplePendingInvitesPanel, PeoplePendingInvitesToggle } from './ui/index.js'

export function AdminClientOnboardPanel({
  canCreateCase,
  canManageUsers,
  isHrPortal,
  pendingInvites,
  invitesViewOpen,
  onInvitesViewChange,
  onAddFamily,
  onSuccess,
  onError,
  onReload,
}) {
  const navigate = useNavigate()

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
          <PeoplePendingInvitesToggle
            label="Pending parent invites"
            count={pendingInvites.length}
            active={invitesViewOpen}
            onClick={() => onInvitesViewChange?.(!invitesViewOpen)}
          />
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

      {canManageUsers ? (
        <PeoplePendingInvitesPanel
          label="Pending parent invites"
          subtitle="Invites not yet accepted"
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
