import { useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { computeLineFromInputs, displayLineFields } from '../../lib/invoiceLineMath.js'
import { formatCurrency } from './ui/index.js'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'

const LINE_TYPES = [
  'SESSION_CHARGE',
  'PACKAGE_CHARGE',
  'LEAVE_ADJUSTMENT',
  'DISCOUNT',
  'MANUAL_FEE',
  'TAX',
  'OTHER',
]

function InvoiceTotalsFooter({ detail, lines }) {
  const subtotal = detail?.subtotalInr ?? 0
  const tax = detail?.taxInr ?? 0
  const discount = detail?.discountInr ?? 0
  const pkgDed = detail?.packageDeductionInr ?? 0
  const adj = detail?.adjustmentInr ?? 0
  const total = detail?.totalInr ?? 0

  return (
    <div className="client-inv-line-editor__totals">
      <div className="client-inv-line-editor__totals-row">
        <span>Taxable subtotal</span>
        <strong>{formatCurrency(subtotal)}</strong>
      </div>
      <div className="client-inv-line-editor__totals-row">
        <span>GST / tax</span>
        <strong>{formatCurrency(tax)}</strong>
      </div>
      {discount > 0 ? (
        <div className="client-inv-line-editor__totals-row client-inv-line-editor__totals-row--deduct">
          <span>Discount</span>
          <strong>−{formatCurrency(discount)}</strong>
        </div>
      ) : null}
      {pkgDed > 0 ? (
        <div className="client-inv-line-editor__totals-row client-inv-line-editor__totals-row--deduct">
          <span>Package deduction</span>
          <strong>−{formatCurrency(pkgDed)}</strong>
        </div>
      ) : null}
      {adj !== 0 ? (
        <div className="client-inv-line-editor__totals-row">
          <span>Adjustment</span>
          <strong>{formatCurrency(adj)}</strong>
        </div>
      ) : null}
      <div className="client-inv-line-editor__totals-row client-inv-line-editor__totals-row--grand">
        <span>Invoice total</span>
        <strong>{formatCurrency(total)}</strong>
      </div>
      <p className="client-inv-line-editor__totals-hint">
        {lines?.length ?? 0} line{(lines?.length ?? 0) === 1 ? '' : 's'} · Recalculate after edits to sync with invoice header.
      </p>
    </div>
  )
}

export function InvoiceLineItemEditor({ invoiceId, lines, detail, canWrite, onUpdated }) {
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState({})
  const { loading: busy, error, successMessage, run, clearMessages, setError } = useBillingAction()

  const livePreview = useMemo(
    () =>
      editingId
        ? computeLineFromInputs({
            quantity: form.quantity,
            unitRateInr: form.unit_rate_inr,
            gstRatePercent: form.gst_rate_percent,
            amountInr: form.amount_inr,
          })
        : null,
    [editingId, form]
  )

  function startEdit(line) {
    const d = displayLineFields(line)
    setEditingId(line.id)
    setForm({
      amount_inr: d.lineTotalInr,
      therapist_name: line.therapistName,
      service_label: line.serviceLabel,
      session_date: line.sessionDate,
      line_item_type: line.lineItemType || 'SESSION_CHARGE',
      finance_note: line.financeNote || '',
      quantity: d.quantity ?? 1,
      unit_rate_inr: d.unitRateInr ?? '',
      gst_rate_percent: line.gstRatePercent ?? '',
      hsn_sac_code: line.hsnSacCode || '',
    })
  }

  function patchForm(patch) {
    setForm((f) => {
      const next = { ...f, ...patch }
      const computed = computeLineFromInputs({
        quantity: next.quantity,
        unitRateInr: next.unit_rate_inr,
        gstRatePercent: next.gst_rate_percent,
        amountInr: next.amount_inr,
      })
      if (patch.quantity !== undefined || patch.unit_rate_inr !== undefined || patch.gst_rate_percent !== undefined) {
        next.amount_inr = computed.lineTotalInr
      }
      return next
    })
  }

  async function recalculate() {
    await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/recalculate`, {
          method: 'POST',
        }),
      { successMsg: 'Totals recalculated' }
    )
    onUpdated()
  }

  async function saveLine(lineId) {
    const gstPct = form.gst_rate_percent !== '' ? Number(form.gst_rate_percent) : 0
    if (gstPct > 0 && !String(form.hsn_sac_code || '').trim()) {
      setError('HSN/SAC code is required when GST applies')
      return
    }
    const computed = computeLineFromInputs({
      quantity: form.quantity,
      unitRateInr: form.unit_rate_inr,
      gstRatePercent: form.gst_rate_percent,
      amountInr: form.amount_inr,
    })
    await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines/${lineId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            amount_inr: computed.lineTotalInr,
            therapist_name: form.therapist_name,
            service_label: form.service_label,
            session_date: form.session_date,
            line_item_type: form.line_item_type,
            finance_note: form.finance_note || null,
            quantity: computed.quantity,
            unit_rate_inr: computed.unitRateInr,
            gst_rate_percent: gstPct || null,
            gst_amount_inr: computed.gstAmountInr,
            taxable_amount_inr: computed.taxableAmountInr,
            hsn_sac_code: form.hsn_sac_code?.trim() || null,
          }),
        }),
      { successMsg: 'Line saved' }
    )
    setEditingId(null)
    onUpdated()
  }

  async function deleteLine(lineId) {
    if (!window.confirm('Remove this line item?')) return
    await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines/${lineId}`, {
          method: 'DELETE',
        }),
      { successMsg: 'Line removed' }
    )
    onUpdated()
  }

  async function addLine() {
    const today = new Date().toISOString().slice(0, 10)
    await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/invoices/${invoiceId}/lines`, {
          method: 'POST',
          body: JSON.stringify({
            session_date: today,
            therapist_name: 'Finance',
            service_label: 'Adjustment',
            amount_inr: 0,
            line_item_type: 'MANUAL_FEE',
            session_status: 'COMPLETED',
            quantity: 1,
            unit_rate_inr: 0,
            gst_rate_percent: null,
          }),
        }),
      { successMsg: 'Line added' }
    )
    onUpdated()
  }

  return (
    <div className="client-inv-line-editor">
      <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
      {canWrite ? (
        <div className="admin-btn-group client-inv-line-editor__toolbar">
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={addLine}>
            + Add line
          </button>
          <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={busy} onClick={recalculate}>
            Recalculate totals
          </button>
        </div>
      ) : null}

      <div className="client-inv-line-editor__table-wrap">
        <table className="admin-table client-inv-line-editor__table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Type</th>
              <th>Description</th>
              <th>Qty</th>
              <th>Unit (ex-GST)</th>
              <th>Tax</th>
              <th>HSN</th>
              <th>Taxable</th>
              <th>GST</th>
              <th>Line total</th>
              {canWrite ? <th /> : null}
            </tr>
          </thead>
          <tbody>
            {lines.map((l) => {
              const d = displayLineFields(l)
              return (
                <tr key={l.id}>
                  {editingId === l.id ? (
                    <>
                      <td>
                        <input className="client-inv__filter-input" type="date" value={form.session_date} onChange={(e) => patchForm({ session_date: e.target.value })} />
                      </td>
                      <td>
                        <select className="client-inv__filter-input" value={form.line_item_type} onChange={(e) => patchForm({ line_item_type: e.target.value })}>
                          {LINE_TYPES.map((t) => (
                            <option key={t} value={t}>{t}</option>
                          ))}
                        </select>
                      </td>
                      <td colSpan={canWrite ? 1 : 1}>
                        <input className="client-inv__filter-input" value={form.service_label} onChange={(e) => patchForm({ service_label: e.target.value })} placeholder="Service label" />
                        <input className="client-inv__filter-input" placeholder="Finance note" value={form.finance_note} onChange={(e) => patchForm({ finance_note: e.target.value })} style={{ marginTop: 4 }} />
                      </td>
                      <td>
                        <input className="client-inv__filter-input" type="number" min="0.01" step="0.01" value={form.quantity} onChange={(e) => patchForm({ quantity: e.target.value })} />
                      </td>
                      <td>
                        <input className="client-inv__filter-input" type="number" step="0.01" value={form.unit_rate_inr} onChange={(e) => patchForm({ unit_rate_inr: e.target.value })} />
                      </td>
                      <td>
                        <select className="client-inv__filter-input" value={form.gst_rate_percent === '' ? '' : String(form.gst_rate_percent)} onChange={(e) => patchForm({ gst_rate_percent: e.target.value === '' ? '' : Number(e.target.value) })}>
                          <option value="">Non-taxable</option>
                          <option value="5">GST 5%</option>
                          <option value="12">GST 12%</option>
                          <option value="18">GST 18%</option>
                          <option value="28">GST 28%</option>
                        </select>
                      </td>
                      <td>
                        <input className="client-inv__filter-input" placeholder="HSN/SAC" value={form.hsn_sac_code} onChange={(e) => patchForm({ hsn_sac_code: e.target.value })} />
                      </td>
                      <td colSpan={3}>
                        {livePreview ? (
                          <div className="client-inv-line-editor__live-preview">
                            Taxable {formatCurrency(livePreview.taxableAmountInr)} + GST {formatCurrency(livePreview.gstAmountInr)} ={' '}
                            <strong>{formatCurrency(livePreview.lineTotalInr)}</strong>
                          </div>
                        ) : null}
                      </td>
                      {canWrite ? (
                        <td>
                          <div className="admin-btn-group">
                            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={busy} onClick={() => saveLine(l.id)}>Save</button>
                            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setEditingId(null)}>Cancel</button>
                          </div>
                        </td>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <td>{l.sessionDate}</td>
                      <td><span className="client-inv-line-editor__type-pill">{l.lineItemType || 'SESSION_CHARGE'}</span></td>
                      <td>
                        <span className="client-inv-line-editor__desc">{l.serviceLabel}</span>
                        {l.financeNote ? <span className="client-inv-line-editor__note">{l.financeNote}</span> : null}
                      </td>
                      <td>{d.quantity}</td>
                      <td>{d.unitRateInr != null ? formatCurrency(d.unitRateInr) : formatCurrency(d.taxableAmountInr / (d.quantity || 1))}</td>
                      <td><span className={`client-inv-line-editor__tax-pill ${d.gstRatePercent ? 'is-taxable' : ''}`}>{d.taxLabel}</span></td>
                      <td>{d.hsnSacCode || '—'}</td>
                      <td>{formatCurrency(d.taxableAmountInr)}</td>
                      <td>{d.gstAmountInr > 0 ? formatCurrency(d.gstAmountInr) : '—'}</td>
                      <td><strong>{formatCurrency(d.lineTotalInr)}</strong></td>
                      {canWrite ? (
                        <td>
                          <div className="admin-btn-group">
                            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => startEdit(l)}>Edit</button>
                            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={busy} onClick={() => deleteLine(l.id)}>Remove</button>
                          </div>
                        </td>
                      ) : null}
                    </>
                  )}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <InvoiceTotalsFooter detail={detail} lines={lines} />
    </div>
  )
}
