import { displayLineFields } from '../../lib/invoiceLineMath.js'
import { formatCurrency, StatusBadge } from './ui/index.js'

function displayStatus(detail) {
  if (!detail) return '—'
  if (detail.paymentBucket === 'overdue') return 'OVERDUE'
  return (detail.status || '').toUpperCase()
}

export function ClientInvoiceOverviewPanel({
  detail,
  canWriteBilling,
  acting,
  onSendToClient,
  onMarkGenerated,
  onOpenPayment,
  onAddLateFee,
  onSendReminder,
  onPushZoho,
  zohoStatus,
}) {
  if (!detail) return null

  const lines = detail.lines || []

  return (
    <div className="client-inv-overview">
      <div className="client-inv-overview__head">
        <StatusBadge status={displayStatus(detail)} />
        <span className="client-inv-overview__meta">
          {detail.invoiceType} · {detail.billingMonth} · {detail.serviceType}
        </span>
      </div>

      <section className="client-inv-overview__section">
        <h4 className="client-inv-overview__title">Invoice preview</h4>
        <p className="client-inv-overview__lead">
          This is the amount the parent or school owes. Confirm the lines, then send the invoice. TDS is recorded when payment comes in — it is not added to this total.
        </p>
        <div className="client-inv-line-editor__table-wrap">
          <table className="admin-table client-inv-line-editor__table">
            <thead>
              <tr>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit</th>
                <th>Tax</th>
                <th>HSN</th>
                <th>Taxable</th>
                <th>GST</th>
                <th>Total</th>
              </tr>
            </thead>
            <tbody>
              {lines.length === 0 ? (
                <tr>
                  <td colSpan={8}>No lines yet — add lines before sending.</td>
                </tr>
              ) : (
                lines.map((l) => {
                  const d = displayLineFields(l)
                  return (
                    <tr key={l.id}>
                      <td>
                        {l.serviceLabel}
                        <span className="client-inv-line-editor__type-pill" style={{ marginLeft: 6 }}>
                          {l.lineItemType || 'SESSION'}
                        </span>
                      </td>
                      <td>{d.quantity}</td>
                      <td>{d.unitRateInr != null ? formatCurrency(d.unitRateInr) : '—'}</td>
                      <td>{d.taxLabel}</td>
                      <td>{d.hsnSacCode || '—'}</td>
                      <td>{formatCurrency(d.taxableAmountInr)}</td>
                      <td>{d.gstAmountInr > 0 ? formatCurrency(d.gstAmountInr) : '—'}</td>
                      <td><strong>{formatCurrency(d.lineTotalInr)}</strong></td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        <div className="client-inv-overview__totals-grid">
          <div>
            <span className="client-inv-overview__k">Subtotal (taxable)</span>
            <strong>{formatCurrency(detail.subtotalInr)}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">GST / tax</span>
            <strong>{formatCurrency(detail.taxInr)}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">Amount due</span>
            <strong className="client-inv-overview__total">{formatCurrency(detail.totalInr)}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">Balance due</span>
            <strong>{formatCurrency(detail.balanceInr)}</strong>
          </div>
        </div>
      </section>

      {detail.notes ? (
        <section className="client-inv-overview__section">
          <h4 className="client-inv-overview__title">Finance note</h4>
          <p style={{ fontSize: '0.85rem', margin: 0 }}>{detail.notes}</p>
        </section>
      ) : null}

      <section className="client-inv-overview__section">
        <h4 className="client-inv-overview__title">Parent &amp; delivery</h4>
        <p style={{ fontSize: '0.85rem', margin: '0 0 8px' }}>
          {detail.parentName} ({detail.parentEmail})
        </p>
        <p style={{ fontSize: '0.85rem', color: '#64748b' }}>
          Due {detail.dueDate || '—'}
          {detail.gatewayEnabled ? ' · Payment gateway enabled' : ''}
        </p>
        {detail.zohoExternalId ? (
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 8 }}>
            Zoho ref: {detail.zohoExternalId}
          </p>
        ) : zohoStatus ? (
          <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 8 }}>{zohoStatus}</p>
        ) : null}

        {canWriteBilling ? (
          <div className="admin-btn-group" style={{ marginTop: 16, flexWrap: 'wrap' }}>
            {detail.status === 'DRAFT' ? (
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" disabled={acting} onClick={onMarkGenerated}>
                Mark ready
              </button>
            ) : null}
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting || !lines.length} onClick={onSendToClient}>
              Send to client
            </button>
            {detail.balanceInr > 0 && onOpenPayment ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onOpenPayment}>
                Record payment
              </button>
            ) : null}
            {detail.balanceInr > 0 && onSendReminder ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={acting} onClick={onSendReminder}>
                Send reminder
              </button>
            ) : null}
            {onAddLateFee ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={acting} onClick={onAddLateFee}>
                Add late fee
              </button>
            ) : null}
            {onPushZoho ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={acting} onClick={onPushZoho}>
                Push to Zoho
              </button>
            ) : null}
          </div>
        ) : (
          <p className="admin-muted" style={{ marginTop: 12, fontSize: '0.8rem' }}>View-only billing access.</p>
        )}
      </section>
    </div>
  )
}
