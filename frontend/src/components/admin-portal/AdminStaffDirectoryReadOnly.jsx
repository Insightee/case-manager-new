import { exportStaffCsv } from '../../lib/peopleDirectoryExport.js'
import { fetchAllStaff } from '../../lib/peopleDirectoryApi.js'
import { PEOPLE_PAGE_SIZE } from '../../lib/peopleDirectoryList.js'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
  PeopleListPagination,
} from './ui/index.js'
import { accountStatusLabel, accountStatusTone } from '../../lib/accountStatus.js'
import { staffDepartmentLabel } from '../../lib/staffDepartments.js'

export function AdminStaffDirectoryReadOnly({
  staff,
  staffDepartments = [],
  staffTotal = 0,
  staffPage = 1,
  onStaffPageChange,
  staffSearch = '',
  onStaffSearchChange,
  staffLoading = false,
}) {
  const staffPages = Math.max(1, Math.ceil(staffTotal / PEOPLE_PAGE_SIZE))
  const safeStaffPage = Math.min(Math.max(1, staffPage), staffPages)
  const staffRangeStart = staffTotal ? (safeStaffPage - 1) * PEOPLE_PAGE_SIZE + 1 : 0
  const staffRangeEnd = Math.min(safeStaffPage * PEOPLE_PAGE_SIZE, staffTotal)

  async function handleExportCsv() {
    const result = await fetchAllStaff({ search: staffSearch })
    exportStaffCsv(result.items, { includeAccess: false })
  }

  return (
    <AdminPanel
      title={`Staff directory (${staffTotal})`}
      subtitle="Read-only view. Contact an administrator to change access or deactivate accounts."
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
            <AdminDataList
              desktop={
                <div className="admin-table-wrap">
                  <table className="admin-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Email</th>
                        <th>Department</th>
                        <th>Role</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {staff.map((u) => (
                        <tr key={u.id}>
                          <td>{u.full_name}</td>
                          <td>{u.email}</td>
                          <td>{staffDepartmentLabel(u.department, staffDepartments) || '—'}</td>
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
                  {staff.map((u) => (
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
                        <p className="admin-muted" style={{ margin: 0 }}>
                          {staffDepartmentLabel(u.department, staffDepartments) || 'No department'}
                          {' · '}
                          {(u.roles || []).map((r) => r.replace(/_/g, ' ')).join(', ') || '—'}
                        </p>
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
  )
}
