import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { AdminPanel, AdminEmptyState, AdminToolbar, formatCurrency } from './ui/index.js'

export function AdminSessionLedgerTab() {
  const { canWriteBilling } = useModuleWrite()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [ledgerMonth, setLedgerMonth] = useState(() => new Date().toISOString().slice(0, 7))
  const [caseId, setCaseId] = useState('')
  const [billableStatus, setBillableStatus] = useState('')
  const [overrideId, setOverrideId] = useState(null)
  const [overrideStatus, setOverrideStatus] = useState('BILLABLE')
  const [overrideReason, setOverrideReason] = useState('')
  const [reconcile, setReconcile] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    const qs = new URLSearchParams()
    if (ledgerMonth) qs.set('ledger_month', ledgerMonth)
    if (caseId) qs.set('case_id', caseId)
    if (billableStatus) qs.set('billable_status', billableStatus)
    try {
      setRows(await apiFetch(`/api/v1/admin/ledger-billing/ledger?${qs}`))
    } catch {
      setRows([])
    } finally {
      setLoading(false)
    }
  }, [ledgerMonth, caseId, billableStatus])

  useEffect(() => {
    load()
  }, [load])

  async function submitOverride(e) {
    e.preventDefault()
    if (!overrideId || !canWriteBilling) return
    try {
      await apiFetch(`/api/v1/admin/ledger-billing/ledger/${overrideId}`, {
        method: 'PATCH',
        body: JSON.stringify({ billable_status: overrideStatus, override_reason: overrideReason }),
      })
      setOverrideId(null)
      setOverrideReason('')
      load()
    } catch (err) {
      alert(err.message || 'Override failed')
    }
  }

  async function runReconcile() {
    if (!caseId || !ledgerMonth) return
    try {
      setReconcile(
        await apiFetch(
          `/api/v1/admin/ledger-billing/reconciliation?case_id=${caseId}&billing_month=${encodeURIComponent(ledgerMonth)}`
        )
      )
    } catch {
      setReconcile(null)
    }
  }

  return (
    <div className="client-inv">
      <AdminToolbar>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Month</span>
          <input className="admin-input" type="month" value={ledgerMonth} onChange={(e) => setLedgerMonth(e.target.value)} />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Case ID</span>
          <input className="admin-input" type="number" placeholder="DB id" value={caseId} onChange={(e) => setCaseId(e.target.value)} />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Billable</span>
          <select className="admin-input" value={billableStatus} onChange={(e) => setBillableStatus(e.target.value)}>
            <option value="">All</option>
            <option value="PENDING_REVIEW">Pending review</option>
            <option value="BILLABLE">Billable</option>
            <option value="NON_BILLABLE">Non-billable</option>
            <option value="INVOICED">Invoiced</option>
          </select>
        </label>
        <button type="button" className="admin-btn admin-btn--sm" onClick={load}>
          Refresh
        </button>
        <button type="button" className="admin-btn admin-btn--sm admin-btn--secondary" onClick={runReconcile}>
          Reconcile case
        </button>
      </AdminToolbar>

      {reconcile ? (
        <div className="admin-alert" style={{ marginBottom: 12 }}>
          Sessions: {reconcile.sessionCount} · Client billable: {formatCurrency(reconcile.ledgerBillableTotalInr)} ·
          Therapist payout: {formatCurrency(reconcile.therapistPayoutTotalInr)} · Margin:{' '}
          {formatCurrency(reconcile.marginInr)}
        </div>
      ) : null}

      {overrideId && canWriteBilling ? (
        <AdminPanel title={`Override ledger #${overrideId}`}>
          <form className="admin-form-grid" onSubmit={submitOverride} style={{ maxWidth: 480 }}>
            <label>
              Status
              <select className="admin-input" value={overrideStatus} onChange={(e) => setOverrideStatus(e.target.value)}>
                <option value="BILLABLE">Billable</option>
                <option value="NON_BILLABLE">Non-billable</option>
                <option value="EXCLUDED">Excluded</option>
                <option value="PENDING_REVIEW">Pending review</option>
              </select>
            </label>
            <label>
              Reason (required)
              <textarea className="admin-input" rows={2} required minLength={3} value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} />
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" className="admin-btn admin-btn--primary admin-btn--sm">
                Save override
              </button>
              <button type="button" className="admin-btn admin-btn--sm" onClick={() => setOverrideId(null)}>
                Cancel
              </button>
            </div>
          </form>
        </AdminPanel>
      ) : null}

      <AdminPanel title="Session ledger">
        {loading ? (
          <p>Loading…</p>
        ) : rows.length === 0 ? (
          <AdminEmptyState title="No ledger rows" hint="Approve daily logs or complete sessions to generate entries." />
        ) : (
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Case</th>
                  <th>Event</th>
                  <th>Status</th>
                  <th>Amount</th>
                  <th>Invoice</th>
                  {canWriteBilling ? <th /> : null}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.eventDate}</td>
                    <td>{r.caseCode}</td>
                    <td>{r.eventType}</td>
                    <td>{r.billableStatus}</td>
                    <td>{formatCurrency(r.totalInr)}</td>
                    <td>{r.clientInvoiceId || '—'}</td>
                    {canWriteBilling && r.billableStatus !== 'INVOICED' ? (
                      <td>
                        <button type="button" className="admin-btn admin-btn--sm" onClick={() => setOverrideId(r.id)}>
                          Override
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
        )}
      </AdminPanel>
    </div>
  )
}
