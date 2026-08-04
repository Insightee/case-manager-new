import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  formatCurrency,
} from './ui/index.js'
import { InvoiceDetailDrawer } from './AdminClientInvoicesTab.jsx'

function statusPillClass(inv) {
  if (inv.isOverdue && inv.balanceInr > 0) return 'client-inv__status-pill client-inv__status-pill--overdue'
  const key = (inv.status || '').toLowerCase()
  return `client-inv__status-pill client-inv__status-pill--${key === 'partially_paid' ? 'partially_paid' : key || 'draft'}`
}

export function AdminReceivablesTab({ openInvoiceId = null }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [overdueOnly, setOverdueOnly] = useState(false)
  const [drawerId, setDrawerId] = useState(openInvoiceId ? Number(openInvoiceId) : null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (overdueOnly) params.set('overdue_only', 'true')
      const qs = params.toString()
      setData(await apiFetch(`/api/v1/admin/client-billing/receivables${qs ? `?${qs}` : ''}`))
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [search, overdueOnly])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (openInvoiceId) setDrawerId(Number(openInvoiceId))
  }, [openInvoiceId])

  const totals = data?.totals
  const rows = data?.invoices || []

  return (
    <>
      <AdminPanel title="Receivables (money in)">
        {totals ? (
          <div className="client-inv__summary-grid" style={{ marginBottom: 16 }}>
            <div className="client-inv__summary-card">
              <span className="client-inv__summary-k">Billed</span>
              <strong>{formatCurrency(totals.billedInr)}</strong>
            </div>
            <div className="client-inv__summary-card">
              <span className="client-inv__summary-k">Collected</span>
              <strong>{formatCurrency(totals.collectedInr)}</strong>
            </div>
            <div className="client-inv__summary-card">
              <span className="client-inv__summary-k">Held (disputes)</span>
              <strong>{formatCurrency(totals.heldInr)}</strong>
            </div>
            <div className="client-inv__summary-card">
              <span className="client-inv__summary-k">Outstanding</span>
              <strong>{formatCurrency(totals.outstandingInr)}</strong>
            </div>
            <div className="client-inv__summary-card">
              <span className="client-inv__summary-k">Overdue</span>
              <strong>{formatCurrency(totals.overdueInr)}</strong>
              <span className="client-inv__summary-meta">{totals.overdueCount} invoice(s)</span>
            </div>
          </div>
        ) : null}

        <AdminCollapsibleFilters>
          <AdminSearchInput value={search} onChange={setSearch} placeholder="Search family, invoice #, case…" />
          <label className="client-inv__filter-check">
            <input type="checkbox" checked={overdueOnly} onChange={(e) => setOverdueOnly(e.target.checked)} />
            Overdue only
          </label>
        </AdminCollapsibleFilters>

        {loading ? (
          <p>Loading…</p>
        ) : rows.length === 0 ? (
          <AdminEmptyState title="No receivables" hint="Invoices with balance due appear here." />
        ) : (
          <AdminDataList
            desktop={
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Family</th>
                      <th>Status</th>
                      <th>Billed</th>
                      <th>Held</th>
                      <th>Outstanding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((inv) => (
                      <tr key={inv.id}>
                        <td>
                          <button type="button" className="admin-link-btn" onClick={() => setDrawerId(inv.id)}>
                            {inv.invoiceNumber}
                          </button>
                        </td>
                        <td>
                          {inv.childName}
                          <br />
                          <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{inv.caseId}</span>
                        </td>
                        <td>
                          <span className={statusPillClass(inv)}>
                            {inv.isOverdue && inv.balanceInr > 0 ? 'OVERDUE' : (inv.status || '').toUpperCase()}
                          </span>
                        </td>
                        <td>{formatCurrency(inv.totalInr)}</td>
                        <td>{formatCurrency(inv.heldAmountInr)}</td>
                        <td>{formatCurrency(inv.balanceInr)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            }
            mobile={
              <ul className="admin-data-list__cards">
                {rows.map((inv) => (
                  <li key={inv.id}>
                    <AdminTaskCard
                      title={inv.invoiceNumber}
                      meta={`${inv.childName} · ${inv.caseId}`}
                      badges={
                        <span className={statusPillClass(inv)}>
                          {inv.isOverdue && inv.balanceInr > 0 ? 'OVERDUE' : (inv.status || '').toUpperCase()}
                        </span>
                      }
                    >
                      <p>
                        Outstanding {formatCurrency(inv.balanceInr)} · Held {formatCurrency(inv.heldAmountInr)}
                      </p>
                      <button type="button" className="admin-btn admin-btn--sm" onClick={() => setDrawerId(inv.id)}>
                        Review
                      </button>
                    </AdminTaskCard>
                  </li>
                ))}
              </ul>
            }
          />
        )}

        <p style={{ marginTop: 12, fontSize: '0.8rem' }}>
          <Link to="/admin/invoices?tab=payments">Payment claims queue →</Link>
          {' · '}
          <Link to="/admin/invoices?tab=disputes">Disputes →</Link>
        </p>
      </AdminPanel>

      {drawerId ? (
        <InvoiceDetailDrawer
          invoiceId={drawerId}
          onClose={() => setDrawerId(null)}
          onRefresh={load}
          canWriteBilling
        />
      ) : null}
    </>
  )
}
