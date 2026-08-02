import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import {
  downgradeConfidence,
  formatInr,
  normalizeConfidence,
} from '../../lib/financeConfidence.js'
import {
  isFinanceDashboardV1Enabled,
} from '../../lib/productFeatureFlags.js'
import { QueryState } from '../shared/QueryState.jsx'
import { ConfidenceBadge } from './ui/ConfidenceBadge.jsx'
import {
  AdminEmptyState,
  AdminFilterGrid,
  AdminPanel,
} from './ui/index.js'
import '../../styles/finance-control-tower.css'

const QUEUE_DEFS = [
  { key: 'readyForBilling', label: 'Ready for billing' },
  { key: 'billingExceptions', label: 'Billing exceptions' },
  { key: 'payoutExceptions', label: 'Payout exceptions' },
  { key: 'missingPackageCounts', label: 'Missing package counts' },
  { key: 'assignmentIssues', label: 'Assignment gaps / overlaps' },
  { key: 'leaveExceptions', label: 'Leave exceptions' },
  { key: 'addOnExceptions', label: 'Add-on exceptions' },
  { key: 'periodFlags', label: 'Period flags / no sessions' },
  { key: 'uninvoicedEligible', label: 'Uninvoiced eligible' },
  { key: 'openDisputes', label: 'Open disputes' },
]

const SUMMARY_FIELDS = [
  { key: 'potentialBillable', label: 'Potential billable' },
  { key: 'invoiced', label: 'Invoiced' },
  { key: 'collected', label: 'Collected' },
  { key: 'outstanding', label: 'Outstanding' },
  { key: 'therapistPayable', label: 'Therapist payable' },
  { key: 'exceptionImpact', label: 'Exception impact' },
]

const FUNNEL_STEPS = [
  { key: 'activeCases', label: 'Active cases' },
  { key: 'inputsComplete', label: 'Inputs complete' },
  { key: 'ledgerCalculated', label: 'Ledger calculated' },
  { key: 'noBlockingException', label: 'No blocking exception' },
  { key: 'readyForBilling', label: 'Ready for billing' },
]

function moneyLabel(mv) {
  if (!mv || mv.value == null) return null
  const amt = formatInr(mv.value)
  if (!amt) return null
  const conf = normalizeConfidence(mv.confidence)
  return `${amt} · ${conf.charAt(0)}${conf.slice(1).toLowerCase()}`
}

export function AdminFinanceOverviewTab() {
  const [searchParams, setSearchParams] = useSearchParams()
  const flagOn = isFinanceDashboardV1Enabled()
  const monthFromUrl = searchParams.get('month')
  const queue = searchParams.get('queue')
  const [billingMonth, setBillingMonth] = useState(
    () => monthFromUrl || new Date().toISOString().slice(0, 7),
  )
  const [summary, setSummary] = useState(null)
  const [summaryError, setSummaryError] = useState(null)
  const [summaryLoading, setSummaryLoading] = useState(true)
  const [exceptions, setExceptions] = useState(null)
  const [exceptionsError, setExceptionsError] = useState(null)
  const [billingRows, setBillingRows] = useState(null)
  const [billingError, setBillingError] = useState(null)
  const [payoutRows, setPayoutRows] = useState(null)
  const [payoutError, setPayoutError] = useState(null)
  const [forbidden, setForbidden] = useState(false)

  const setMonth = useCallback(
    (ym) => {
      setBillingMonth(ym)
      const next = new URLSearchParams(searchParams)
      next.set('tab', 'overview')
      next.set('month', ym)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const openQueue = useCallback(
    (q) => {
      const next = new URLSearchParams(searchParams)
      next.set('tab', 'overview')
      next.set('month', billingMonth)
      if (q) next.set('queue', q)
      else next.delete('queue')
      setSearchParams(next)
    },
    [billingMonth, searchParams, setSearchParams],
  )

  useEffect(() => {
    if (!flagOn) return undefined
    let cancelled = false
    setSummaryLoading(true)
    setSummaryError(null)
    setForbidden(false)
    const q = `billing_month=${encodeURIComponent(billingMonth)}`
    Promise.allSettled([
      apiFetch(`/api/v1/admin/finance-control-tower/summary?${q}`),
      apiFetch(`/api/v1/admin/finance-control-tower/exceptions?${q}&limit=50${queue ? `&queue=${encodeURIComponent(queue)}` : ''}`),
      apiFetch(`/api/v1/admin/finance-control-tower/billing-readiness?${q}&limit=50`),
      apiFetch(`/api/v1/admin/finance-control-tower/payout-readiness?${q}&limit=50`),
    ]).then(([s, e, b, p]) => {
      if (cancelled) return
      if (s.status === 'fulfilled') {
        setSummary(s.value)
        setSummaryError(null)
      } else {
        const status = s.reason?.status
        if (status === 403) setForbidden(true)
        setSummary(null)
        setSummaryError(s.reason?.message || 'Summary unavailable')
      }
      if (e.status === 'fulfilled') {
        setExceptions(e.value)
        setExceptionsError(null)
      } else {
        setExceptions(null)
        setExceptionsError(e.reason?.message || 'Exceptions unavailable')
      }
      if (b.status === 'fulfilled') {
        setBillingRows(b.value)
        setBillingError(null)
      } else {
        setBillingRows(null)
        setBillingError(b.reason?.message || 'Billing readiness unavailable')
      }
      if (p.status === 'fulfilled') {
        setPayoutRows(p.value)
        setPayoutError(null)
      } else {
        setPayoutRows(null)
        // 403 is expected for non-finance roles that somehow pass — hide section
        setPayoutError(p.reason?.status === 403 ? null : (p.reason?.message || 'Payout readiness unavailable'))
      }
      setSummaryLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [flagOn, billingMonth, queue])

  const pageConfidence = useMemo(() => {
    let c = summary?.pageConfidence || 'ESTIMATED'
    if (exceptionsError || billingError || payoutError) {
      c = downgradeConfidence(c, 'ESTIMATED')
    }
    if (summaryError) c = downgradeConfidence(c, 'INCOMPLETE')
    return normalizeConfidence(c)
  }, [summary, summaryError, exceptionsError, billingError, payoutError])

  if (!flagOn) {
    return (
      <AdminEmptyState
        title="Finance Control Tower is not enabled"
        description="Set VITE_ENABLE_FINANCE_DASHBOARD_V1=true in a non-production environment to open the Stage 1 read-only control tower. Existing invoice tabs remain available."
        hints={['Billing module flags stay separate from this dashboard gate.']}
      />
    )
  }

  if (forbidden) {
    return (
      <AdminEmptyState
        title="Looks like this view needs a Finance or Super Admin role"
        description="The Finance Control Tower is limited to Finance and Super Admin. Therapist payout and cross-client finance details stay scoped."
      />
    )
  }

  return (
    <div className="finance-control-tower forest-light">
      <h2 className="finance-control-tower__title">Finance Control Tower</h2>
      <div className="finance-control-tower__meta">
        <AdminFilterGrid ariaLabel="Control tower filters">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Billing month</span>
            <input
              type="month"
              className="client-inv__filter-input"
              value={billingMonth}
              onChange={(e) => setMonth(e.target.value)}
            />
          </label>
        </AdminFilterGrid>
        <span className="finance-control-tower__meta-chip">
          Last refreshed{' '}
          <span className="mono">{summary?.asOf ? new Date(summary.asOf).toLocaleString('en-IN') : '—'}</span>
        </span>
        <span className="finance-control-tower__meta-chip">
          Engine {summary?.engineAvailable ? 'available' : 'gated off'}
        </span>
        <span className="finance-control-tower__meta-chip">
          Cutover {summary?.cutoverComplete ? 'complete' : 'pending'}
        </span>
        <span className="finance-control-tower__meta-chip">Read-only</span>
        <ConfidenceBadge confidence={pageConfidence} reason={summary?.pageConfidenceReason} />
      </div>

      {summary?.provisionalBanner || !summary?.cutoverComplete ? (
        <div className="finance-control-tower__banner" role="status">
          Showing verified calculations from staging. Live financial cutover is pending, so figures remain
          provisional.
        </div>
      ) : null}

      <QueryState
        isLoading={summaryLoading}
        isError={Boolean(summaryError) && !summary}
        error={summaryError}
        onRetry={() => setMonth(billingMonth)}
        isEmpty={false}
        skeletonVariant="list"
        skeletonRows={4}
      >
        {summary ? (
          <>
            <h3 className="finance-control-tower__section-title">Action queue</h3>
            <div className="finance-control-tower__queue-grid">
              {QUEUE_DEFS.map((def) => {
                const card = summary.actionQueue?.[def.key] || {}
                const impactText = moneyLabel(card.impact)
                const active = queue === card.drillQueue
                return (
                  <button
                    type="button"
                    key={def.key}
                    className={`finance-control-tower__queue-card${active ? ' is-active' : ''}`}
                    onClick={() => openQueue(card.drillQueue || def.key)}
                  >
                    <span className="finance-control-tower__queue-label">{def.label}</span>
                    <span className="finance-control-tower__queue-count">{card.count ?? 0}</span>
                    {impactText ? (
                      <span className="finance-control-tower__queue-impact">{impactText}</span>
                    ) : (
                      <span className="finance-control-tower__queue-meta">Count only — amount not invented</span>
                    )}
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                      <ConfidenceBadge confidence={card.confidence} reason={card.confidenceReason} />
                      {card.oldestAgeDays != null ? (
                        <span className="finance-control-tower__queue-meta">
                          Oldest {card.oldestAgeDays}d
                        </span>
                      ) : null}
                    </div>
                  </button>
                )
              })}
            </div>

            <h3 className="finance-control-tower__section-title">Finance summary</h3>
            <div className="finance-control-tower__summary-grid">
              {SUMMARY_FIELDS.map((f) => {
                const mv = summary.financeSummary?.[f.key]
                const label = moneyLabel(mv)
                return (
                  <div key={f.key} className="finance-control-tower__summary-item">
                    <div className="finance-control-tower__summary-label">{f.label}</div>
                    <div className="finance-control-tower__summary-value">
                      {label || '—'}
                    </div>
                    <ConfidenceBadge
                      confidence={mv?.confidence}
                      reason={mv?.confidenceReason}
                      materialSourceMissing={mv?.value == null}
                    />
                  </div>
                )
              })}
            </div>

            <h3 className="finance-control-tower__section-title">Readiness funnel</h3>
            <div className="finance-control-tower__funnel">
              {FUNNEL_STEPS.map((step) => (
                <div key={step.key} className="finance-control-tower__funnel-step">
                  <strong>{summary.readinessFunnel?.[step.key] ?? 0}</strong>
                  <span>{step.label}</span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </QueryState>

      {queue ? (
        <AdminPanel
          title="Queue drill-down"
          subtitle={`Source queue: ${queue} · month ${billingMonth}`}
          actions={
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => openQueue(null)}>
              Back to Control Tower
            </button>
          }
        >
          {exceptionsError ? (
            <div className="finance-control-tower__section-error">
              This queue could not load. Other Control Tower sections stay available.
            </div>
          ) : (
            <ExceptionTable items={exceptions?.items || []} emptyLabel="No exceptions in this queue." />
          )}
          {summary?.links ? (
            <p style={{ marginTop: 12, fontSize: '0.8rem' }}>
              Related:{' '}
              {queue === 'open_disputes' && summary.links.disputes ? (
                <Link to={summary.links.disputes}>Open disputes tab</Link>
              ) : null}
              {queue === 'ready_for_billing' && summary.links.composerLedgerReady ? (
                <Link to={summary.links.composerLedgerReady}>Open composer (ledger ready)</Link>
              ) : null}
              {queue === 'uninvoiced_eligible' && summary.links.composerNotInvoiced ? (
                <Link to={summary.links.composerNotInvoiced}>Open composer (not invoiced)</Link>
              ) : null}
              {queue === 'payout_exceptions' && summary.links.therapistPayouts ? (
                <Link to={summary.links.therapistPayouts}>Therapist payouts</Link>
              ) : null}
            </p>
          ) : null}
        </AdminPanel>
      ) : null}

      <h3 className="finance-control-tower__section-title">Exception preview</h3>
      {exceptionsError ? (
        <div className="finance-control-tower__section-error">
          Exception preview unavailable. Page confidence is downgraded.
        </div>
      ) : (
        <ExceptionTable items={exceptions?.items || []} emptyLabel="No open exceptions for this month." />
      )}

      <h3 className="finance-control-tower__section-title">Billing readiness</h3>
      {billingError ? (
        <div className="finance-control-tower__section-error">Billing readiness unavailable.</div>
      ) : (
        <div className="finance-control-tower__table-wrap">
          <table>
            <thead>
              <tr>
                <th>Case</th>
                <th>Client</th>
                <th>Service</th>
                <th>Billing type</th>
                <th>Expected amount</th>
                <th>Ledger</th>
                <th>Exceptions</th>
                <th>Invoice</th>
                <th>Confidence</th>
                <th>View</th>
              </tr>
            </thead>
            <tbody>
              {(billingRows?.items || []).length === 0 ? (
                <tr>
                  <td colSpan={10}>No active billed cases to show.</td>
                </tr>
              ) : (
                (billingRows?.items || []).map((row) => (
                  <tr key={row.caseId}>
                    <td className="mono">{row.caseCode}</td>
                    <td>{row.clientName}</td>
                    <td>{row.service}</td>
                    <td className="mono">{row.billingType}</td>
                    <td className="mono">{moneyLabel(row.expectedAmount) || '—'}</td>
                    <td>{row.ledgerStatus}</td>
                    <td>{row.exceptionStatus}</td>
                    <td>{row.invoiceStatus}</td>
                    <td>
                      <ConfidenceBadge confidence={row.confidence} />
                    </td>
                    <td>
                      {row.viewHref ? <Link to={row.viewHref}>View</Link> : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <h3 className="finance-control-tower__section-title">Payout readiness</h3>
      {payoutError ? (
        <div className="finance-control-tower__section-error">Payout readiness unavailable.</div>
      ) : payoutRows == null && !summaryLoading ? (
        <AdminEmptyState
          title="Payout readiness is limited to Finance and Super Admin"
          description="Therapist payout figures stay hidden from other roles."
        />
      ) : (
        <div className="finance-control-tower__table-wrap">
          <table>
            <thead>
              <tr>
                <th>Therapist</th>
                <th>Cases</th>
                <th>Payable units</th>
                <th>Expected payout</th>
                <th>Held lines</th>
                <th>Exceptions</th>
                <th>Confidence</th>
                <th>View</th>
              </tr>
            </thead>
            <tbody>
              {(payoutRows?.items || []).length === 0 ? (
                <tr>
                  <td colSpan={8}>No therapist invoices for this month.</td>
                </tr>
              ) : (
                (payoutRows?.items || []).map((row) => (
                  <tr key={row.therapistUserId}>
                    <td>{row.therapistName}</td>
                    <td className="mono">{row.cases ?? '—'}</td>
                    <td className="mono">{row.payableUnits}</td>
                    <td className="mono">{moneyLabel(row.expectedPayout) || '—'}</td>
                    <td className="mono">{row.heldLines}</td>
                    <td className="mono">{row.exceptionCount}</td>
                    <td>
                      <ConfidenceBadge confidence={row.confidence} />
                    </td>
                    <td>
                      {row.viewHref ? <Link to={row.viewHref}>View</Link> : '—'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}

function ExceptionTable({ items, emptyLabel }) {
  return (
    <div className="finance-control-tower__table-wrap">
      <table>
        <thead>
          <tr>
            <th>Exception</th>
            <th>Case / client</th>
            <th>Service</th>
            <th>Billing month</th>
            <th>Financial impact</th>
            <th>Owner</th>
            <th>Age</th>
            <th>Confidence</th>
            <th>Open</th>
          </tr>
        </thead>
        <tbody>
          {!items.length ? (
            <tr>
              <td colSpan={9}>{emptyLabel}</td>
            </tr>
          ) : (
            items.map((row, idx) => (
              <tr key={`${row.exception}-${row.caseId}-${idx}`}>
                <td className="mono">{row.exception}</td>
                <td>
                  <span className="mono">{row.caseCode || row.caseId || '—'}</span>
                  <br />
                  {row.clientName}
                </td>
                <td>{row.service || '—'}</td>
                <td className="mono">{row.billingMonth}</td>
                <td className="mono">
                  {row.financialImpact != null ? formatInr(row.financialImpact) : '—'}
                </td>
                <td>{row.owner || 'Unassigned'}</td>
                <td className="mono">{row.ageDays != null ? `${row.ageDays}d` : '—'}</td>
                <td>
                  <ConfidenceBadge confidence={row.confidence} reason={row.confidenceReason} />
                </td>
                <td>
                  {row.openHref ? <Link to={row.openHref}>Open</Link> : '—'}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
