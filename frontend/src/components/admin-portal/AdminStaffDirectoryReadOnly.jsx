import { useEffect, useMemo, useState } from 'react'
import { filterStaffDirectory } from '../../lib/peopleDirectoryList.js'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
} from './ui/index.js'
import { accountStatusLabel, accountStatusTone } from '../../lib/accountStatus.js'

export function AdminStaffDirectoryReadOnly({ staff }) {
  const [search, setSearch] = useState('')
  const filtered = useMemo(() => filterStaffDirectory(staff, search), [staff, search])

  useEffect(() => {
    setSearch('')
  }, [staff])

  return (
    <AdminPanel
      title={`Staff directory (${filtered.length})`}
      subtitle="Read-only view. Contact an administrator to change access or deactivate accounts."
      padded={false}
    >
      <div className="admin-panel__body">
        <AdminToolbar>
          <AdminSearchInput value={search} onChange={setSearch} placeholder="Search staff by name or email…" />
        </AdminToolbar>
        {filtered.length === 0 ? (
          <AdminEmptyState title="No staff users" description="Use Add staff or adjust search." />
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
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((u) => (
                      <tr key={u.id}>
                        <td>{u.full_name}</td>
                        <td>{u.email}</td>
                        <td>{(u.roles || []).map((r) => r.replace(/_/g, ' ')).join(', ') || '—'}</td>
                        <td>
                          <StatusBadge tone={accountStatusTone(accountStatusLabel(u))}>
                            {accountStatusLabel(u)}
                          </StatusBadge>
                        </td>
                      </tr>
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
                        <StatusBadge tone={accountStatusTone(accountStatusLabel(u))}>
                          {accountStatusLabel(u)}
                        </StatusBadge>
                      }
                    >
                      <p className="admin-muted" style={{ margin: 0, fontSize: '0.8125rem' }}>
                        {(u.roles || []).map((r) => r.replace(/_/g, ' ')).join(', ') || '—'}
                      </p>
                    </AdminTaskCard>
                  </li>
                ))}
              </ul>
            }
          />
        )}
      </div>
    </AdminPanel>
  )
}
