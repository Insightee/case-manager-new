import { Link, useNavigate } from 'react-router-dom'
import { AdminInviteRowActions, AdminPanel } from './ui/index.js'

export function AdminClientOnboardPanel({
  canCreateCase,
  canManageUsers,
  isHrPortal,
  pendingInvites,
  onAddFamily,
  onSuccess,
  onError,
  onReload,
}) {
  const navigate = useNavigate()

  return (
    <>
      <div className="admin-btn-group admin-people-onboard">
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
      </div>

      {!canManageUsers ? (
        <p className="admin-muted admin-people-onboard__hint">
          Families are read-only here. Use case allotment to add a child with a parent account.
        </p>
      ) : null}

      {pendingInvites.length > 0 ? (
        <AdminPanel
          title={`Pending parent invites (${pendingInvites.length})`}
          subtitle="Invites not yet accepted"
        >
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th>Expires</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {pendingInvites.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.email}</td>
                    <td>{new Date(inv.expires_at).toLocaleDateString()}</td>
                    <td>
                      <AdminInviteRowActions
                        invite={inv}
                        onSuccess={onSuccess}
                        onError={onError}
                        onReload={onReload}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </AdminPanel>
      ) : null}

      {isHrPortal ? (
        <p className="admin-muted admin-people-onboard__hint">
          HR view: open cases from each client row or{' '}
          <Link to="/hr/cases">case list</Link>.
        </p>
      ) : null}
    </>
  )
}
