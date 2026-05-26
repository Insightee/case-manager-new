import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatCurrency } from './ui/index.js'

const LINE_TYPES = [
  'SESSION_CHARGE',
  'PACKAGE_CHARGE',
  'LEAVE_ADJUSTMENT',
  'DISCOUNT',
  'MANUAL_FEE',
  'TAX',
  'OTHER',
]

export function InvoiceLineItemEditor({ invoiceId, lines, canWrite, onUpdated }) {
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})
  const [busy, setBusy] = useState(false)

  function startEdit(line) {
    setEditingId(line.id)
    setForm({
      amount_inr: line.amountInr,
      therapist_name: line.therapistName,
      service_label: line.serviceLabel,
      session_date: line.sessionDate,
      line_item_type: line.lineItemType || 'SESSION_CHARGE',
      finance_note: line.financeNote || '',
    })
  }

  async function saveLine(lineId) {
    setBusy(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines/${lineId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          amount_inr: Number(form.amount_inr),
          therapist_name: form.therapist_name,
          service_label: form.service_label,
          session_date: form.session_date,
          line_item_type: form.line_item_type,
          finance_note: form.finance_note || null,
        }),
      })
      setEditingId(null)
      onUpdated()
    } finally {
      setBusy(false)
    }
  }

  async function deleteLine(lineId) {
    if (!window.confirm('Remove this line item?')) return
    setBusy(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines/${lineId}`, {
        method: 'DELETE',
      })
      onUpdated()
    } finally {
      setBusy(false)
    }
  }

  async function addLine() {
    const today = new Date().toISOString().slice(0, 10)
    setBusy(true)
    try {
      await apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines`, {
        method: 'POST',
        body: JSON.stringify({
          session_date: today,
          therapist_name: 'Finance',
          service_label: 'Adjustment',
          amount_inr: 0,
          line_item_type: 'MANUAL_FEE',
          session_status: 'COMPLETED',
        }),
      })
      onUpdated()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      {canWrite ? (
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginBottom: 10 }} disabled={busy} onClick={addLine}>
          + Add line
        </button>
      ) : null}
      <div className="admin-table-wrap">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Therapist</th>
              <th>Amount</th>
              {canWrite ? <th /> : null}
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => (
              <tr key={l.id}>
                {editingId === l.id ? (
                  <>
                    <td>
                      <input className="client-inv__filter-input" type="date" value={form.session_date} onChange={(e) => setForm((f) => ({ ...f, session_date: e.target.value }))} />
                    </td>
                    <td>
                      <select className="client-inv__filter-input" value={form.line_item_type} onChange={(e) => setForm((f) => ({ ...f, line_item_type: e.target.value }))}>
                        {LINE_TYPES.map((t) => (
                          <option key={t} value={t}>{t}</option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input className="client-inv__filter-input" value={form.therapist_name} onChange={(e) => setForm((f) => ({ ...f, therapist_name: e.target.value }))} />
                    </td>
                    <td>
                      <input className="client-inv__filter-input" type="number" value={form.amount_inr} onChange={(e) => setForm((f) => ({ ...f, amount_inr: e.target.value }))} />
                    </td>
                    <td>
                      <div className="admin-btn-group">
                        <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={busy} onClick={() => saveLine(l.id)}>Save</button>
                        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setEditingId(null)}>Cancel</button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td>{l.sessionDate}</td>
                    <td>{l.lineItemType || 'SESSION_CHARGE'}</td>
                    <td>{l.therapistName}</td>
                    <td>{formatCurrency(l.amountInr)}</td>
                    {canWrite ? (
                      <td>
                        <div className="admin-btn-group">
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => startEdit(l)}>Edit</button>
                          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => deleteLine(l.id)}>Remove</button>
                        </div>
                      </td>
                    ) : null}
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
