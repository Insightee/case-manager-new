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
}) {
  if (!detail) return null

  const lines = detail.lines || []
  const preview = detail.billingPreview

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
          Review line items on the Line items tab, then confirm totals below before sending to the parent.
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
            <span className="client-inv-overview__k">Invoice total</span>
            <strong className="client-inv-overview__total">{formatCurrency(detail.totalInr)}</strong>
          </div>
          <div>
            <span className="client-inv-overview__k">Balance due</span>
            <strong>{formatCurrency(detail.balanceInr)}</strong>
          </div>
        </div>
      </section>

      {preview ? (
        <section className="client-inv-overview__section client-inv-overview__therapist">
          <h4 className="client-inv-overview__title">Therapist payout (estimate)</h4>
          <p className="client-inv-overview__lead">
            Therapist pay is based on their share of completed work for this case, minus approved leave deductions — not the client invoice total.
          </p>
          <div className="client-inv-overview__totals-grid">
            <div>
              <span className="client-inv-overview__k">Sessions (month)</span>
              <strong>{preview.sessionsCompleted ?? 0}</strong>
            </div>
            <div>
              <span className="client-inv-overview__k">Billable sessions</span>
              <strong>{preview.sessionsBillable ?? 0}</strong>
            </div>
            <div>
              <span className="client-inv-overview__k">Leaves</span>
              <strong>{preview.leavesTotal ?? 0}</strong>
            </div>
            <div>
              <span className="client-inv-overview__k">Est. therapist payout</span>
              <strong>{formatCurrency(preview.therapistPayoutTotalInr)}</strong>
            </div>
            <div>
              <span className="client-inv-overview__k">Est. margin</span>
              <strong>{formatCurrency(preview.estimatedMarginInr)}</strong>
            </div>
          </div>
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
        {detail.notes ? <p style={{ fontSize: '0.85rem', marginTop: 8 }}>{detail.notes}</p> : null}

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
          </div>
        ) : (
          <p className="admin-muted" style={{ marginTop: 12, fontSize: '0.8rem' }}>View-only billing access.</p>
        )}
      </section>
    </div>
  )
}
