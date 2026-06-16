import { useMemo, useState } from 'react'
import { AdminPanel } from './AdminPanel.jsx'
import { AdminEmptyState } from './AdminEmptyState.jsx'
import { AdminSearchInput, AdminToolbar } from './AdminToolbar.jsx'
import { AdminInviteRowActions } from './AdminInviteRowActions.jsx'
import { PeopleBulkToolbar, PeopleSelectCheckbox } from './PeopleRowActions.jsx'

function inviteSearchHaystack(inv) {
  return [
    inv.email,
    inv.client_name,
    inv.role_name?.replace(/_/g, ' '),
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

export function filterPendingInvites(invites, query) {
  const q = query.trim().toLowerCase()
  if (!q) return invites
  return invites.filter((inv) => inviteSearchHaystack(inv).includes(q))
}

export function PeoplePendingInvitesToggle({ label, count, active, onClick }) {
  return (
    <button
      type="button"
      className={`admin-btn admin-btn--sm ${active ? 'admin-btn--primary' : 'admin-btn--secondary'}`}
      onClick={onClick}
      aria-pressed={active}
    >
      {label} ({count})
    </button>
  )
}

export function PeoplePendingInvitesPanel({
  label,
  subtitle = 'Links expire after 7 days',
  pendingInvites,
  layout = 'table',
  open,
  onOpenChange,
  onSuccess,
  onError,
  onReload,
}) {
  const [inviteSearch, setInviteSearch] = useState('')
  const [selectedInviteIds, setSelectedInviteIds] = useState(() => new Set())

  const filteredInvites = useMemo(
    () => filterPendingInvites(pendingInvites, inviteSearch),
    [pendingInvites, inviteSearch],
  )

  function toggleInviteSelect(id) {
    setSelectedInviteIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function clearSelectionAndReload() {
    setSelectedInviteIds(new Set())
    onReload?.()
  }

  if (!open) return null

  return (
    <AdminPanel
      title={`${label} (${pendingInvites.length})`}
      subtitle={subtitle}
      actions={
        <button
          type="button"
          className="admin-btn admin-btn--ghost admin-btn--sm"
          onClick={() => onOpenChange(false)}
        >
          ← Back
        </button>
      }
    >
      <div style={{ marginBottom: 12 }}>
        <AdminToolbar>
          <AdminSearchInput
            value={inviteSearch}
            onChange={setInviteSearch}
            placeholder="Search by name or email…"
          />
        </AdminToolbar>
      </div>
      <PeopleBulkToolbar
        selectedInviteIds={[...selectedInviteIds]}
        onReload={clearSelectionAndReload}
        onSuccess={onSuccess}
        onError={onError}
      />
      {filteredInvites.length === 0 ? (
        <AdminEmptyState
          title={inviteSearch.trim() ? 'No matching invites' : 'No pending invites'}
          description={
            inviteSearch.trim()
              ? 'Try a different name or email.'
              : 'New invites will appear here after you send them.'
          }
        />
      ) : layout === 'queue' ? (
        <ul className="admin-queue">
          {filteredInvites.map((inv) => (
            <li key={inv.id} className="admin-queue__item">
              <PeopleSelectCheckbox
                checked={selectedInviteIds.has(inv.id)}
                onChange={() => toggleInviteSelect(inv.id)}
                ariaLabel={`Select invite ${inv.email}`}
              />
              <div>
                <p className="admin-queue__title">{inv.email}</p>
                <p className="admin-queue__meta">
                  {inv.role_name?.replace(/_/g, ' ')} · Expires{' '}
                  {new Date(inv.expires_at).toLocaleDateString()}
                </p>
              </div>
              <AdminInviteRowActions
                invite={inv}
                onSuccess={onSuccess}
                onError={onError}
                onReload={onReload}
              />
            </li>
          ))}
        </ul>
      ) : (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th style={{ width: 36 }} aria-label="Select" />
                <th>Email</th>
                <th>Expires</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredInvites.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    <PeopleSelectCheckbox
                      checked={selectedInviteIds.has(inv.id)}
                      onChange={() => toggleInviteSelect(inv.id)}
                      ariaLabel={`Select invite ${inv.email}`}
                    />
                  </td>
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
      )}
    </AdminPanel>
  )
}
