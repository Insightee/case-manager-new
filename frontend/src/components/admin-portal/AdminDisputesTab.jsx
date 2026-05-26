import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPanel, AdminEmptyState, StatusBadge } from './ui/index.js'

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
      )}
    </AdminPanel>
  )
}
