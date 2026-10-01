import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatInr } from '../../lib/financeConfidence.js'
import { isFinanceDashboardV1Enabled } from '../../lib/productFeatureFlags.js'
import { ConfidenceBadge } from './ui/ConfidenceBadge.jsx'
import { AdminEmptyState } from './ui/index.js'
import { AdminBillingReadinessMasterSheet } from './AdminBillingReadinessMasterSheet.jsx'
import '../../styles/finance-control-tower.css'

function moneyLabel(mv) {
  if (!mv || mv.value == null) return null
  const amt = formatInr(mv.value)
  if (!amt) return null
  return amt
}

function financeOverviewErrorMessage(message) {
  const msg = String(message || '')
  if (msg.includes('not available in this environment')) {
    return 'Finance overview is not enabled on this server yet. Use Client invoices and Client payments below for day-to-day billing work.'
  }
  if (msg.includes('Finance Control Tower is limited')) {
    return 'This overview is available to Finance and Super Admin roles.'
  }
  return msg || "We couldn't load readiness tables for this billing month."
}

export function AdminFinanceOverviewTab() {
  const [searchParams, setSearchParams] = useSearchParams()
  const flagOn = isFinanceDashboardV1Enabled()
  const monthFromUrl = searchParams.get('month')
  const billingMonth = monthFromUrl || new Date().toISOString().slice(0, 7)
  const [exceptions, setExceptions] = useState(null)
  const [exceptionsError, setExceptionsError] = useState(null)
  const [billingRows, setBillingRows] = useState(null)
  const [billingError, setBillingError] = useState(null)
  const [payoutRows, setPayoutRows] = useState(null)
  const [payoutError, setPayoutError] = useState(null)
  const [forbidden, setForbidden] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!flagOn) return undefined
    let cancelled = false
    setLoading(true)
    setForbidden(false)
    const q = `billing_month=${encodeURIComponent(billingMonth)}`
    Promise.allSettled([
      apiFetch(`/api/v1/admin/finance-control-tower/exceptions?${q}&limit=50`),
      apiFetch(`/api/v1/admin/finance-control-tower/billing-readiness?${q}&limit=50`),
      apiFetch(`/api/v1/admin/finance-control-tower/payout-readiness?${q}&limit=50`),
    ]).then(([e, b, p]) => {
      if (cancelled) return
      if (e.status === 'fulfilled') {
        setExceptions(e.value)
        setExceptionsError(null)
      } else {
        const status = e.reason?.status
        if (status === 403) setForbidden(true)
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
        setPayoutError(p.reason?.status === 403 ? null : (p.reason?.message || 'Payout readiness unavailable'))
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [flagOn, billingMonth])

  if (!flagOn) {
    return (
      <AdminEmptyState
        title="Finance Control Tower opens when this environment is ready"
        description="Stage 1 is a read-only control tower for Finance and Super Admin. Existing invoice, payment, and receivables tabs stay available while this gate is set for the current build."
        hints={[
          'Non-production: VITE_ENABLE_FINANCE_DASHBOARD_V1 defaults on (or set true).',
          'Canonical production needs VITE_ENABLE_FINANCE_DASHBOARD_V1=true and VITE_FINANCE_DASHBOARD_ALLOW_PROD=true.',
          'Billing module flags stay separate from this dashboard gate.',
        ]}
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
      {loading ? (
        <div className="admin-skeleton" style={{ minHeight: 120, marginBottom: 16 }} aria-busy="true" />
      ) : null}

      <h3 className="finance-control-tower__section-title">Exception preview</h3>
      {exceptionsError ? (
        <div className="finance-control-tower__section-error">
          {financeOverviewErrorMessage(exceptionsError)}
        </div>
      ) : (
        <ExceptionTable items={exceptions?.items || []} emptyLabel="No open exceptions for this month." />
      )}

      <AdminBillingReadinessMasterSheet billingMonth={billingMonth} embedded />

      <h3 className="finance-control-tower__section-title">Billing readiness (legacy summary)</h3>
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
      ) : payoutRows == null && !loading ? (
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
