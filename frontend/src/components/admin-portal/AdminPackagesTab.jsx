import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminTaskCard,
  AdminToolbar,
  StatusBadge,
} from './ui/index.js'

export function AdminPackagesTab() {
  const { canWriteBilling } = useModuleWrite()
  const [packages, setPackages] = useState([])
  const [loading, setLoading] = useState(true)
  const [caseFilter, setCaseFilter] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    const qs = caseFilter ? `?case_id=${caseFilter}` : ''
    try {
      setPackages(await apiFetch(`/api/v1/admin/ledger-billing/packages${qs}`))
    } catch {
      setPackages([])
    } finally {
      setLoading(false)
    }
  }, [caseFilter])

  useEffect(() => {
    load()
  }, [load])

  async function activate(pkg) {
    if (!canWriteBilling) return
    await apiFetch(`/api/v1/admin/ledger-billing/packages/${pkg.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'ACTIVE' }),
    })
    load()
  }

  return (
    <div className="client-inv">
      <AdminCollapsibleFilters
        activeChips={caseFilter ? [`Case ${caseFilter}`] : []}
        activeCount={caseFilter ? 1 : 0}
      >
        <AdminToolbar className="admin-toolbar--mobile-compact">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Case ID</span>
            <input className="admin-input" type="number" value={caseFilter} onChange={(e) => setCaseFilter(e.target.value)} placeholder="Filter" />
          </label>
          <button type="button" className="admin-btn admin-btn--sm" onClick={load}>
            Refresh
          </button>
        </AdminToolbar>
      </AdminCollapsibleFilters>

      <AdminPanel title="Care packages">
        {loading ? (
          <p>Loading…</p>
        ) : packages.length === 0 ? (
          <AdminEmptyState title="No packages" hint="Packages are created from prepaid invoices or admin setup." />
        ) : (
          <AdminDataList
            desktop={
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Case</th>
                      <th>Sessions</th>
                      <th>Valid until</th>
                      <th>Status</th>
                      {canWriteBilling ? <th /> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {packages.map((p) => (
                      <tr key={p.id}>
                        <td>{p.name}</td>
                        <td>{p.caseId}</td>
                        <td>
                          {p.usedSessions}/{p.totalSessions} ({p.remainingSessions} left)
                        </td>
                        <td>{p.validityEnd || '—'}</td>
                        <td>
                          <StatusBadge tone={p.status === 'ACTIVE' ? 'green' : 'amber'}>{p.status}</StatusBadge>
                        </td>
                        {canWriteBilling && p.status === 'PENDING_PAYMENT' ? (
                          <td>
                            <button type="button" className="admin-btn admin-btn--sm" onClick={() => activate(p)}>
                              Mark active
                            </button>
                          </td>
                        ) : canWriteBilling ? (
                          <td />
                        ) : null}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            }
            mobile={
              <ul className="admin-data-list__cards">
                {packages.map((p) => (
                  <li key={p.id}>
                    <AdminTaskCard
                      title={p.name}
                      meta={`Case ${p.caseId} · ${p.usedSessions}/${p.totalSessions} sessions`}
                      badges={<StatusBadge tone={p.status === 'ACTIVE' ? 'green' : 'amber'}>{p.status}</StatusBadge>}
                      actions={
                        canWriteBilling && p.status === 'PENDING_PAYMENT' ? (
                          <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => activate(p)}>
                            Mark active
                          </button>
                        ) : null
                      }
                    >
                      <p>Valid until: {p.validityEnd || '—'} · {p.remainingSessions} remaining</p>
                    </AdminTaskCard>
                  </li>
                ))}
              </ul>
            }
          />
        )}
      </AdminPanel>
    </div>
  )
}
