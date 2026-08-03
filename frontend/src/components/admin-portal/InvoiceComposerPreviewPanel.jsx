import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ConfidenceBadge, formatCurrency } from './ui/index.js'

export function InvoiceComposerPreviewPanel({
  preview,
  loading,
  card,
  billingMonth,
  canWriteBilling,
  writesEnabled = true,
  actionLoading = false,
  onBuildFromLedger,
  onCreateManualInvoice,
  onRemindTherapist,
  onPostDraftCharge,
  onRefresh,
}) {
  const [tab, setTab] = useState('overview')

  if (loading) return <div className="admin-skeleton finance-stage2-skeleton" aria-busy="true" />
  if (!preview) {
    return (
      <p className="finance-stage2-empty" role="status">
        Looks like we still need a few details before we can load this billing preview. Try refresh, or pick another case.
      </p>
    )
  }

  const ov = preview.overview || {}
  const rule = preview.billingRule || {}
  const warnings = preview.warnings || []
  const blocking = preview.blockingExceptions || []
  const draftCharges = preview.postableDraftCharges || []
  const canBuild = preview.canBuild !== false && blocking.length === 0
  const provisional = Boolean(preview.provisional)
  const zohoConfigured = Boolean(preview.zohoConfigured)
  const ledgerReady = (card?.ledgerReadyCount ?? ov.ledgerReadyCount ?? 0) > 0
  const allowWrites = Boolean(canWriteBilling && writesEnabled && canBuild)

  function handleWarningAction(w) {
    if (w.action === 'manual_invoice') onCreateManualInvoice?.()
    else if (w.action === 'remind_therapist') onRemindTherapist?.()
  }

  return (
    <div className="finance-stage2-preview">
      <div className="finance-stage2-preview__head">
        <div>
          <h2 className="finance-stage2-preview__title">
            {preview.case?.caseCode} — {preview.case?.childName}
          </h2>
          <p className="finance-stage2-preview__meta">
            {preview.case?.parentName} · {preview.case?.serviceType}
          </p>
        </div>
        {canWriteBilling ? (
          <div className="admin-btn-group client-inv-composer__primary-actions">
            <button
              type="button"
              className={`admin-btn admin-btn--sm ${ledgerReady && canBuild ? 'admin-btn--primary' : 'admin-btn--secondary'}`}
              disabled={actionLoading || !allowWrites}
              title={
                !writesEnabled
                  ? 'Posting disabled until cutover / ledger writes are enabled'
                  : !canBuild
                    ? 'Blocked by open calculation exceptions'
                    : undefined
              }
              onClick={() => onBuildFromLedger(false)}
            >
              {actionLoading ? 'Working…' : 'Build from ledger'}
            </button>
            <button
              type="button"
              className={`admin-btn admin-btn--sm ${ledgerReady ? 'admin-btn--secondary' : 'admin-btn--primary'}`}
              disabled={actionLoading || !allowWrites}
              onClick={onCreateManualInvoice}
            >
              Create invoice manually
            </button>
            {card?.actions?.useLedgerAnyway ? (
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                disabled={actionLoading || !allowWrites}
                onClick={() => onBuildFromLedger(true)}
              >
                Use ledger anyway
              </button>
            ) : null}
          </div>
        ) : (
          <p className="finance-stage2-state finance-stage2-state--muted" role="status">
            You can preview this case, but posting requires invoice write access.
          </p>
        )}
      </div>

      {!writesEnabled && canWriteBilling ? (
        <div className="finance-stage2-banner finance-stage2-banner--amber" role="status">
          Posting is disabled until cutover (ledger writes remain off). You can still review queues and previews.
        </div>
      ) : null}

      {provisional ? (
        <div className="finance-stage2-banner finance-stage2-banner--mint" role="status">
          Provisional engine amounts — not reconciled until finance cutover.
        </div>
      ) : null}

      <div className="finance-stage2-zoho" role="status">
        Zoho sync:{' '}
        {zohoConfigured ? (
          <span className="finance-stage2-chip finance-stage2-chip--ok">Configured</span>
        ) : (
          <span className="finance-stage2-chip finance-stage2-chip--muted">Not configured</span>
        )}
      </div>

      {blocking.length > 0 ? (
        <section className="finance-stage2-banner finance-stage2-banner--danger" aria-label="Blocking exceptions">
          <h3 className="finance-stage2-banner__title">Invoice build blocked</h3>
          <p>
            Open calculation exceptions must be resolved before a client invoice can be built from this case.
          </p>
          <ul className="finance-stage2-exception-list">
            {blocking.map((ex) => (
              <li key={ex.id || ex.code}>
                <strong className="finance-stage2-mono">{ex.code}</strong> — {ex.message}{' '}
                {ex.openHref ? (
                  <Link to={ex.openHref} className="finance-stage2-link">
                    View exception
                  </Link>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {preview.savedPreferences?.source ? (
        <p className="finance-stage2-hint finance-stage2-hint--accent">
          Using {preview.savedPreferences.source === 'last_invoice' ? 'last invoice' : 'saved case'} settings. You can
          edit before sending.
        </p>
      ) : null}

      {warnings.map((w) => (
        <div key={w.code} className="client-inv-composer__warn finance-stage2-warn">
          {w.message}
          {w.action && canWriteBilling ? (
            <button
              type="button"
              className="admin-btn admin-btn--ghost admin-btn--sm"
              onClick={() => handleWarningAction(w)}
            >
              {w.action === 'manual_invoice'
                ? 'Create manually'
                : w.action === 'remind_therapist'
                  ? 'Remind'
                  : 'Review ledger'}
            </button>
          ) : null}
          {w.action === 'review_ledger' && preview.case?.caseId ? (
            <Link
              to={`/admin/invoices?tab=ledger&case_id=${preview.case.caseId}`}
              className="admin-btn admin-btn--ghost admin-btn--sm"
            >
              Session ledger
            </Link>
          ) : null}
        </div>
      ))}

      {draftCharges.length > 0 ? (
        <section className="finance-stage2-card" aria-label="Draft period charges">
          <h3 className="finance-stage2-card__title">Zero-session DRAFT charges</h3>
          <p className="finance-stage2-hint">
            These PENDING_FINANCE rows need an explicit finance post before they can enter an invoice. They are never
            auto-posted.
          </p>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Type</th>
                  <th>Amount</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {draftCharges.map((d) => (
                  <tr key={d.id}>
                    <td className="finance-stage2-mono">{d.eventDate || '—'}</td>
                    <td>{d.sourceType}</td>
                    <td className="finance-stage2-mono">{formatCurrency(d.totalInr)}</td>
                    <td>
                      {canWriteBilling && writesEnabled ? (
                        <button
                          type="button"
                          className="admin-btn admin-btn--secondary admin-btn--sm"
                          disabled={actionLoading}
                          onClick={() => onPostDraftCharge?.(d.id)}
                        >
                          Post charge
                        </button>
                      ) : (
                        <span className="finance-stage2-hint">Awaiting explicit post</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      <div className="client-inv__amount-grid finance-stage2-amount-grid">
        <div>
          <span className="finance-stage2-amount-label">Suggested total</span>
          <br />
          <strong className="finance-stage2-mono">{formatCurrency(ov.total)}</strong>{' '}
          <ConfidenceBadge confidence={ov.confidence} reason={ov.confidenceReason} />
        </div>
        <div>
          <span className="finance-stage2-amount-label">Sessions done</span>
          <br />
          <strong className="finance-stage2-mono">{ov.sessionsCompleted ?? 0}</strong>
        </div>
        <div>
          <span className="finance-stage2-amount-label">Leaves</span>
          <br />
          <strong className="finance-stage2-mono">{ov.leavesTotal ?? 0}</strong>
        </div>
        <div>
          <span className="finance-stage2-amount-label">GST</span>
          <br />
          <strong>{rule.gstApplicable ? `${rule.gstRatePercent ?? 0}%` : 'Not taxed'}</strong>
        </div>
        {preview.includeFinanceFields ? (
          <>
            <div>
              <span className="finance-stage2-amount-label">Therapist payout</span>
              <br />
              <strong className="finance-stage2-mono">{formatCurrency(ov.therapistPayoutTotal)}</strong>
            </div>
            <div>
              <span className="finance-stage2-amount-label">Est. margin</span>
              <br />
              <strong className="finance-stage2-mono">{formatCurrency(ov.estimatedMargin)}</strong>
            </div>
          </>
        ) : null}
      </div>

      <p className="finance-stage2-hint">
        Billing model: {rule.billingModel || '—'} · {rule.invoiceType || 'POSTPAID'} · Month{' '}
        <span className="finance-stage2-mono">{billingMonth}</span>
      </p>
      <p className="finance-stage2-hint finance-stage2-hint--soft">
        Ledger rows are created when daily logs are approved — not when sessions complete alone.
      </p>

      <div className="client-inv-composer__preview-tabs finance-stage2-tabs" role="tablist" aria-label="Preview sections">
        {['overview', 'ledger', 'therapist', 'suggested'].map((t) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`client-inv__drawer-tab ${tab === t ? 'is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t === 'overview' ? 'Overview' : t === 'ledger' ? 'Ledger' : t === 'therapist' ? 'Therapist' : 'Suggested lines'}
          </button>
        ))}
      </div>

      {tab === 'overview' ? (
        <div className="finance-stage2-panel">
          <p>
            Billable sessions: {ov.sessionsBillable ?? 0} · Cancelled: {ov.cancelledSessions ?? 0} · Rescheduled:{' '}
            {ov.rescheduledSessions ?? 0}
          </p>
          <p>
            Subtotal {formatCurrency(ov.subtotal)} + tax {formatCurrency(ov.taxAmount)}
          </p>
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
                <tr>
                  <td colSpan={4}>No ledger rows</td>
                </tr>
              ) : (
                preview.ledgerRows.map((r) => (
                  <tr key={r.id}>
                    <td className="finance-stage2-mono">{r.eventDate}</td>
                    <td>{r.eventType}</td>
                    <td>{r.billableStatus}</td>
                    <td className="finance-stage2-mono">{formatCurrency(r.totalInr)}</td>
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
                <tr>
                  <td colSpan={4}>No therapist submissions</td>
                </tr>
              ) : (
                preview.therapistSubmissions.map((r, i) => (
                  <tr key={`${r.sessionLineId}-${i}`}>
                    <td className="finance-stage2-mono">{r.sessionDate}</td>
                    <td>{r.therapistName}</td>
                    <td className="finance-stage2-mono">{formatCurrency(r.submittedAmountInr)}</td>
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
              {(preview.suggestedLineItems || []).length === 0 ? (
                <tr>
                  <td colSpan={3}>No suggested lines yet</td>
                </tr>
              ) : (
                preview.suggestedLineItems.map((r, i) => (
                  <tr key={r.ledgerId || i}>
                    <td className="finance-stage2-mono">{r.sessionDate}</td>
                    <td>{r.therapistName}</td>
                    <td className="finance-stage2-mono">{formatCurrency(r.amountInr)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}

      <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm finance-stage2-refresh" onClick={onRefresh}>
        Refresh preview
      </button>
    </div>
  )
}
