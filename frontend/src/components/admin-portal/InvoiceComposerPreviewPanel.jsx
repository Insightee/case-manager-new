import { useState } from 'react'
import { formatCurrency } from './ui/index.js'

export function InvoiceComposerPreviewPanel({
  preview,
  loading,
  card,
  billingMonth,
  canWriteBilling,
  onBuildFromLedger,
  onRemindTherapist,
  onRefresh,
}) {
  const [tab, setTab] = useState('overview')

  if (loading) return <div className="admin-skeleton" style={{ minHeight: 200 }} />
  if (!preview) return <p>Could not load billing preview.</p>

  const ov = preview.overview || {}
  const rule = preview.billingRule || {}
  const warnings = preview.warnings || []

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.25rem' }}>
            {preview.case?.caseCode} — {preview.case?.childName}
          </h2>
          <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '0.85rem' }}>
            {preview.case?.parentName} · {preview.case?.serviceType}
          </p>
        </div>
        {canWriteBilling ? (
          <div className="admin-btn-group">
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" onClick={() => onBuildFromLedger(false)}>
              Build from ledger
            </button>
            {card?.actions?.remindTherapist ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={onRemindTherapist}>
                Remind therapist
              </button>
            ) : null}
            {card?.actions?.useLedgerAnyway ? (
              <button type="button" className="admin-btn admin-btn--secondary admin-btn--sm" onClick={() => onBuildFromLedger(true)}>
                Use ledger anyway
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {preview.savedPreferences?.source ? (
        <p style={{ fontSize: '0.8rem', color: '#6366f1', marginTop: 8 }}>
          Using {preview.savedPreferences.source === 'last_invoice' ? 'last invoice' : 'saved case'} settings. You can edit before sending.
        </p>
      ) : null}

      {warnings.map((w) => (
        <div key={w.code} className="client-inv-composer__warn" style={{ marginTop: 12 }}>
          {w.message}
        </div>
      ))}

      <div className="client-inv__amount-grid" style={{ marginTop: 16, gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))' }}>
        <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>Suggested total</span><br /><strong>{formatCurrency(ov.total)}</strong></div>
        <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>Sessions done</span><br /><strong>{ov.sessionsCompleted ?? 0}</strong></div>
        <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>Leaves</span><br /><strong>{ov.leavesTotal ?? 0}</strong></div>
        <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>GST</span><br /><strong>{rule.gstApplicable ? `${rule.gstRatePercent ?? 0}%` : 'Not taxed'}</strong></div>
        {preview.includeFinanceFields ? (
          <>
            <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>Therapist payout</span><br /><strong>{formatCurrency(ov.therapistPayoutTotal)}</strong></div>
            <div><span style={{ color: '#64748b', fontSize: '0.75rem' }}>Est. margin</span><br /><strong>{formatCurrency(ov.estimatedMargin)}</strong></div>
          </>
        ) : null}
      </div>

      <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: 8 }}>
        Billing model: {rule.billingModel || '—'} · {rule.invoiceType || 'POSTPAID'} · Month {billingMonth}
      </p>

      <div className="client-inv-composer__preview-tabs" style={{ marginTop: 20 }}>
        {['overview', 'ledger', 'therapist', 'suggested'].map((t) => (
          <button
            key={t}
            type="button"
            className={`client-inv__drawer-tab ${tab === t ? 'is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'overview' ? 'Overview' : t === 'ledger' ? 'Ledger' : t === 'therapist' ? 'Therapist' : 'Suggested lines'}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <div style={{ fontSize: '0.85rem' }}>
          <p>Billable sessions: {ov.sessionsBillable ?? 0} · Cancelled: {ov.cancelledSessions ?? 0} · Rescheduled: {ov.rescheduledSessions ?? 0}</p>
          <p>Subtotal {formatCurrency(ov.subtotal)} + tax {formatCurrency(ov.taxAmount)}</p>
        </div>
      ) : null}

      {tab === 'ledger' ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Status</th>
                <th>Billable</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(preview.ledgerRows || []).length === 0 ? (
                <tr><td colSpan={4}>No ledger rows</td></tr>
              ) : (
                preview.ledgerRows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.eventDate}</td>
                    <td>{r.eventType}</td>
                    <td>{r.billableStatus}</td>
                    <td>{formatCurrency(r.totalInr)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {tab === 'therapist' ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Therapist</th>
                <th>Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {(preview.therapistSubmissions || []).length === 0 ? (
                <tr><td colSpan={4}>No therapist submissions</td></tr>
              ) : (
                preview.therapistSubmissions.map((r, i) => (
                  <tr key={`${r.sessionLineId}-${i}`}>
                    <td>{r.sessionDate}</td>
                    <td>{r.therapistName}</td>
                    <td>{formatCurrency(r.submittedAmountInr)}</td>
                    <td>{r.financeStatus}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      {tab === 'suggested' ? (
        <div className="admin-table-wrap">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Therapist</th>
                <th>Amount</th>
              </tr>
            </thead>
            <tbody>
              {(preview.suggestedLineItems || []).map((r, i) => (
                <tr key={r.ledgerId || i}>
                  <td>{r.sessionDate}</td>
                  <td>{r.therapistName}</td>
                  <td>{formatCurrency(r.amountInr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" style={{ marginTop: 16 }} onClick={onRefresh}>
        Refresh preview
      </button>
    </div>
  )
}
