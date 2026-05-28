import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminDataList, AdminEmptyState, AdminPanel, AdminTaskCard, StatusBadge } from './ui/index.js'

export function AdminDisputesTab() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await apiFetch('/api/v1/admin/ledger-billing/disputes'))
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  return (
    <AdminPanel title="Billing disputes">
      {loading ? (
        <p>Loading…</p>
      ) : rows.length === 0 ? (
        <AdminEmptyState title="No disputes" hint="Parent disputes appear here when filed on invoices." />
      ) : (
        <AdminDataList
          desktop={
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Invoice</th>
                    <th>Reason</th>
                    <th>Status</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((d) => (
                    <tr key={d.id}>
                      <td>#{d.clientInvoiceId}</td>
                      <td>
                        <strong>{d.reasonCode}</strong>
                        <br />
                        <span style={{ fontSize: '0.85rem', color: '#64748b' }}>{d.message}</span>
                      </td>
                      <td>
                        <StatusBadge tone={d.status === 'OPEN' ? 'amber' : 'green'}>{d.status}</StatusBadge>
                      </td>
                      <td>{d.createdAt ? new Date(d.createdAt).toLocaleDateString() : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          }
          mobile={
            <ul className="admin-data-list__cards">
              {rows.map((d) => (
                <li key={d.id}>
                  <AdminTaskCard
                    title={`Invoice #${d.clientInvoiceId}`}
                    meta={d.createdAt ? new Date(d.createdAt).toLocaleDateString() : '—'}
                    badges={<StatusBadge tone={d.status === 'OPEN' ? 'amber' : 'green'}>{d.status}</StatusBadge>}
                  >
                    <p>
                      <strong>{d.reasonCode}</strong>
                      <br />
                      {d.message}
                    </p>
                  </AdminTaskCard>
                </li>
              ))}
            </ul>
          }
        />
      )}
    </AdminPanel>
  )
}
