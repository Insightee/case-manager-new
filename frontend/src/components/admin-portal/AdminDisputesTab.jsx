import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatTimestampDateIN } from '../../lib/datetime.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import {
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminTaskCard,
  StatusBadge,
} from './ui/index.js'
import { InvoiceDetailDrawer } from './AdminClientInvoicesTab.jsx'

export function AdminDisputesTab() {
  const { canWriteBilling } = useModuleWrite()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [resolveId, setResolveId] = useState(null)
  const [resolveNote, setResolveNote] = useState('')
  const [resolveAdj, setResolveAdj] = useState('')
  const [acting, setActing] = useState(false)
  const [drawerId, setDrawerId] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setRows(await apiFetch('/api/v1/admin/client-billing/disputes'))
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function resolveDispute(disputeId, status) {
    const resolution = resolveNote.trim()
    if (status === 'REJECTED' && !resolution) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/disputes/${disputeId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          status,
          resolution: resolution || (status === 'RESOLVED' ? 'Resolved by finance' : ''),
          adjustment_inr: resolveAdj ? Number(resolveAdj) : null,
        }),
      })
      setResolveId(null)
      setResolveNote('')
      setResolveAdj('')
      load()
    } finally {
      setActing(false)
    }
  }

  return (
    <>
      <AdminPanel title="Billing disputes">
        {loading ? (
          <p>Loading…</p>
        ) : rows.length === 0 ? (
          <AdminEmptyState title="No open disputes" hint="Parent disputes on invoice lines appear here for finance review." />
        ) : (
          <AdminDataList
            desktop={
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Line</th>
                      <th>Reason</th>
                      <th>Status</th>
                      <th>Created</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((d) => (
                      <tr key={d.id}>
                        <td>
                          <button type="button" className="admin-link-btn" onClick={() => setDrawerId(d.invoiceId)}>
                            {d.invoiceNumber || `#${d.invoiceId}`}
                          </button>
                          <br />
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{d.caseCode}</span>
                        </td>
                        <td>{d.lineId ? `#${d.lineId}` : '—'}</td>
                        <td>
                          <strong>{d.reasonCode}</strong>
                          <br />
                          <span style={{ fontSize: '0.85rem', color: '#64748b' }}>{d.message}</span>
                        </td>
                        <td>
                          <StatusBadge tone={d.status === 'OPEN' ? 'amber' : 'green'}>{d.status}</StatusBadge>
                        </td>
                        <td>{d.createdAt ? formatTimestampDateIN(d.createdAt) : '—'}</td>
                        <td>
                          {canWriteBilling && resolveId === d.id ? (
                            <div style={{ minWidth: 220 }}>
                              <textarea
                                className="client-inv__filter-input"
                                style={{ width: '100%', minHeight: 48 }}
                                placeholder="Resolution note"
                                value={resolveNote}
                                onChange={(e) => setResolveNote(e.target.value)}
                              />
                              <input
                                type="number"
                                className="client-inv__filter-input"
                                style={{ width: '100%', marginTop: 4 }}
                                placeholder="Adjustment INR (optional)"
                                value={resolveAdj}
                                onChange={(e) => setResolveAdj(e.target.value)}
                              />
                              <div className="admin-btn-group" style={{ marginTop: 6 }}>
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--primary admin-btn--sm"
                                  disabled={acting}
                                  onClick={() => resolveDispute(d.id, 'RESOLVED')}
                                >
                                  Resolve
                                </button>
                                <button
                                  type="button"
                                  className="admin-btn admin-btn--sm"
                                  disabled={acting || !resolveNote.trim()}
                                  onClick={() => resolveDispute(d.id, 'REJECTED')}
                                >
                                  Reject
                                </button>
                                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setResolveId(null)}>
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : canWriteBilling ? (
                            <button type="button" className="admin-btn admin-btn--sm" onClick={() => setResolveId(d.id)}>
                              Review
                            </button>
                          ) : null}
                        </td>
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
                      title={d.invoiceNumber || `Invoice #${d.invoiceId}`}
                      meta={d.createdAt ? formatTimestampDateIN(d.createdAt) : '—'}
                      badges={<StatusBadge tone={d.status === 'OPEN' ? 'amber' : 'green'}>{d.status}</StatusBadge>}
                    >
                      <p>
                        <strong>{d.reasonCode}</strong>
                        {d.lineId ? ` · Line #${d.lineId}` : ''}
                        <br />
                        {d.message}
                      </p>
                      {canWriteBilling ? (
                        resolveId === d.id ? (
                          <>
                            <textarea
                              className="client-inv__filter-input"
                              style={{ width: '100%', minHeight: 48 }}
                              value={resolveNote}
                              onChange={(e) => setResolveNote(e.target.value)}
                            />
                            <div className="admin-btn-group" style={{ marginTop: 8 }}>
                              <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => resolveDispute(d.id, 'RESOLVED')}>
                                Resolve
                              </button>
                              <button type="button" className="admin-btn admin-btn--sm" disabled={!resolveNote.trim()} onClick={() => resolveDispute(d.id, 'REJECTED')}>
                                Reject
                              </button>
                            </div>
                          </>
                        ) : (
                          <button type="button" className="admin-btn admin-btn--sm" onClick={() => setResolveId(d.id)}>
                            Review dispute
                          </button>
                        )
                      ) : null}
                    </AdminTaskCard>
                  </li>
                ))}
              </ul>
            }
          />
        )}
      </AdminPanel>

      {drawerId ? (
        <InvoiceDetailDrawer invoiceId={drawerId} onClose={() => setDrawerId(null)} onRefresh={load} canWriteBilling={canWriteBilling} />
      ) : null}
    </>
  )
}
