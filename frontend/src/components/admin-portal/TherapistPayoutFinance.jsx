import { useCallback, useEffect, useState, Fragment } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useBillingRuntimeConfig } from '../../hooks/useBillingRuntimeConfig.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { formatInr, normalizeConfidence } from '../../lib/financeConfidence.js'
import { isFinanceDashboardV1Enabled } from '../../lib/productFeatureFlags.js'
import '../../styles/finance-dashboard-modern.css'
import '../../styles/finance-control-tower.css'
import {
  AdminCollapsibleFilters,
  AdminDataList,
  AdminEmptyState,
  AdminPanel,
  AdminSearchInput,
  AdminTaskCard,
  StatusBadge,
  formatCurrency,
} from './ui/index.js'
import { ConfidenceBadge } from './ui/ConfidenceBadge.jsx'

const FINANCE_SUMMARY_FIELDS = [
  { key: 'potentialBillable', label: 'Potential billable' },
  { key: 'invoiced', label: 'Invoiced' },
  { key: 'collected', label: 'Collected' },
  { key: 'outstanding', label: 'Outstanding' },
  { key: 'therapistPayable', label: 'Therapist payable' },
  { key: 'exceptionImpact', label: 'Exception impact' },
]

function summaryMoneyLabel(mv) {
  if (!mv || mv.value == null) return null
  const amt = formatInr(mv.value)
  if (!amt) return null
  const conf = normalizeConfidence(mv.confidence)
  return `${amt} · ${conf.charAt(0)}${conf.slice(1).toLowerCase()}`
}

function statusPillClass(status) {
  const key = (status || '').toLowerCase()
  if (key === 'queried') return 'client-inv__status-pill client-inv__status-pill--overdue'
  return `client-inv__status-pill client-inv__status-pill--${key || 'draft'}`
}

export function FinanceMondayBrief() {
  const [searchParams, setSearchParams] = useSearchParams()
  const flagOn = isFinanceDashboardV1Enabled()
  const monthFromUrl = searchParams.get('month')
  const billingMonth = monthFromUrl || new Date().toISOString().slice(0, 7)
  const [financeSummary, setFinanceSummary] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)

  const setMonth = useCallback(
    (ym) => {
      const next = new URLSearchParams(searchParams)
      next.set('tab', 'overview')
      next.set('month', ym)
      setSearchParams(next, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  useEffect(() => {
    if (!flagOn) {
      setFinanceSummary(null)
      setLoadError(null)
      setLoading(false)
      return undefined
    }
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    const q = `billing_month=${encodeURIComponent(billingMonth)}`
    apiFetch(`/api/v1/admin/finance-control-tower/summary?${q}`)
      .then((data) => {
        if (cancelled) return
        setFinanceSummary(data?.financeSummary || null)
        setLoadError(null)
      })
      .catch((err) => {
        if (cancelled) return
        setFinanceSummary(null)
        setLoadError(err?.message || 'Finance summary unavailable')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [billingMonth, flagOn])

  if (!flagOn) {
    return (
      <AdminEmptyState
        title="Finance snapshot is not enabled"
        description="Set VITE_ENABLE_FINANCE_DASHBOARD_V1=true to load monthly finance summary here. Client invoices and payments tabs stay available."
      />
    )
  }

  if (loading) return <div className="admin-skeleton" style={{ minHeight: 120, marginBottom: 16 }} />

  return (
    <AdminPanel title="Finance snapshot" padded className="finance-dash" style={{ marginBottom: 16 }}>
      <div className="finance-control-tower__toolbar" style={{ marginBottom: 16 }}>
        <label className="finance-control-tower__month-field">
          <span className="client-inv__filter-label">Billing month</span>
          <input
            type="month"
            className="client-inv__filter-input finance-control-tower__month-input"
            value={billingMonth}
            onChange={(e) => setMonth(e.target.value)}
            aria-label="Billing month"
          />
        </label>
      </div>
      {loadError ? (
        <AdminEmptyState
          title="Finance summary could not load"
          description={
            loadError.includes('Finance Control Tower is limited')
              ? 'This summary is available to Finance and Super Admin roles.'
              : loadError
          }
        />
      ) : financeSummary ? (
        <div className="finance-control-tower__summary-grid">
          {FINANCE_SUMMARY_FIELDS.map((field) => {
            const mv = financeSummary[field.key]
            const label = summaryMoneyLabel(mv)
            return (
              <div key={field.key} className="finance-control-tower__summary-item">
                <div className="finance-control-tower__summary-label">{field.label}</div>
                <div className="finance-control-tower__summary-value">{label || '—'}</div>
                <ConfidenceBadge
                  confidence={mv?.confidence}
                  reason={mv?.confidenceReason}
                  materialSourceMissing={mv?.value == null}
                />
              </div>
            )
          })}
        </div>
      ) : (
        <AdminEmptyState
          title="No finance summary for this month"
          description="Try another billing month or check back after invoices and sessions are recorded."
        />
      )}
    </AdminPanel>
  )
}

export function TherapistPayoutQueuePanel() {
  const { canWriteBilling } = useModuleWrite()
  const { config: billingConfig } = useBillingRuntimeConfig()
  const payoutExportEnabled = Boolean(billingConfig?.payoutExportEnabled)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('ALL')
  const [expandedId, setExpandedId] = useState(null)
  const [resolveId, setResolveId] = useState(null)
  const [resolveNote, setResolveNote] = useState('')
  const [acting, setActing] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [exportNote, setExportNote] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (status && status !== 'ALL') params.set('status', status)
      const qs = params.toString()
      setData(await apiFetch(`/api/v1/admin/therapist-payouts/queue${qs ? `?${qs}` : ''}`))
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [search, status])

  useEffect(() => {
    load()
  }, [load])

  async function resolveDispute(disputeId, resolveStatus) {
    const resolution = resolveNote.trim()
    if (resolveStatus === 'REJECTED' && !resolution) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/therapist-payouts/statement-disputes/${disputeId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          status: resolveStatus,
          resolution: resolution || (resolveStatus === 'RESOLVED' ? 'Resolved by finance' : ''),
        }),
      })
      setResolveId(null)
      setResolveNote('')
      load()
    } finally {
      setActing(false)
    }
  }

  function toggleSelect(invoiceId) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(invoiceId)) next.delete(invoiceId)
      else next.add(invoiceId)
      return next
    })
  }

  const totals = data?.totals
  const rows = data?.statements || []

  const exportableSelected = rows.filter(
    (row) =>
      selected.has(row.invoiceId) &&
      row.status === 'APPROVED' &&
      !row.hasOpenDispute &&
      !row.blocked &&
      !row.needsReview
  )

  async function exportBatch() {
    if (!exportableSelected.length) return
    const flaggedSelected = exportableSelected.filter((row) => row.therapistPayoutFlagged)
    if (
      flaggedSelected.length > 0
      && !window.confirm(
        `${flaggedSelected.length} selected therapist payout(s) are flagged. Review them before final payout. Continue with export?`
      )
    ) {
      return
    }
    setActing(true)
    setExportNote(null)
    try {
      const key = `export-${Date.now()}-${exportableSelected.map((r) => r.invoiceId).join('-')}`
      const result = await apiFetch('/api/v1/admin/therapist-payouts/export-batch', {
        method: 'POST',
        body: JSON.stringify({
          invoice_ids: exportableSelected.map((r) => r.invoiceId),
          idempotency_key: key.slice(0, 120),
        }),
      })
      setExportNote(
        result?.alreadyExported
          ? 'Batch already exported for this idempotency key — no duplicate transfers.'
          : `Mock batch exported (${result?.batch?.transferCount ?? 0} transfer(s)).`
      )
      setSelected(new Set())
      load()
    } catch (err) {
      setExportNote(err?.message || 'Export could not complete — check settlement ladder.')
    } finally {
      setActing(false)
    }
  }

  async function syncBatch(batchId) {
    setActing(true)
    try {
      await apiFetch(`/api/v1/admin/therapist-payouts/batches/${batchId}/sync-status`, { method: 'POST' })
      load()
    } finally {
      setActing(false)
    }
  }

  return (
    <>
      <AdminPanel title="Payout finance queue (money out)" className="finance-dash">
        {totals ? (
          <div className="finance-dash__grid" style={{ marginBottom: 16 }}>
            <div className="finance-dash__card">
              <span className="finance-dash__card-k">Pending approval</span>
              <strong>{totals.pendingCount ?? 0}</strong>
            </div>
            <div className="finance-dash__card finance-dash__card--warn">
              <span className="finance-dash__card-k">Disputed / queried</span>
              <strong>{totals.disputedCount ?? 0}</strong>
            </div>
            <div className="finance-dash__card finance-dash__card--accent">
              <span className="finance-dash__card-k">Clean approved</span>
              <strong>{totals.approvedCount ?? 0}</strong>
            </div>
            <div className="finance-dash__card finance-dash__card--accent">
              <span className="finance-dash__card-k">Payable now</span>
              <strong>{formatCurrency(totals.totalPayableNowInr)}</strong>
            </div>
            <div className="finance-dash__card">
              <span className="finance-dash__card-k">Held (contested)</span>
              <strong>{formatCurrency(totals.totalContestedInr)}</strong>
            </div>
          </div>
        ) : null}

        <AdminCollapsibleFilters>
          <AdminSearchInput value={search} onChange={setSearch} placeholder="Search therapist or month" />
          <select className="admin-input" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="ALL">All statuses</option>
            <option value="IN_REVIEW">In review</option>
            <option value="QUERIED">Queried</option>
            <option value="APPROVED">Approved</option>
          </select>
        </AdminCollapsibleFilters>

        {loading ? (
          <p>Loading…</p>
        ) : rows.length === 0 ? (
          <AdminEmptyState title="No statements in queue" hint="Submitted therapist invoices appear here for finance review." />
        ) : (
          <AdminDataList
            desktop={
              <div className="admin-table-wrap">
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th />
                      <th>Therapist</th>
                      <th>Month</th>
                      <th>Cases</th>
                      <th>Sessions</th>
                      <th>Gross</th>
                      <th>TDS</th>
                      <th>Deductions</th>
                      <th>Net</th>
                      <th>Payable now</th>
                      <th>Contested</th>
                      <th>Batch</th>
                      <th>Status</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <Fragment key={row.invoiceId}>
                        <tr>
                          <td>
                            <input
                              type="checkbox"
                              checked={selected.has(row.invoiceId)}
                              disabled={row.needsReview || row.hasOpenDispute || row.blocked || row.status !== 'APPROVED'}
                              onChange={() => toggleSelect(row.invoiceId)}
                            />
                          </td>
                          <td>
                            {row.therapistName}
                            {row.therapistPayoutFlagged ? (
                              <span className="admin-chip admin-chip--warn" style={{ display: 'block', marginTop: 4, width: 'fit-content' }}>
                                This therapist was flagged
                              </span>
                            ) : null}
                          </td>
                          <td>{row.month}</td>
                          <td>{row.caseCount}</td>
                          <td>{row.sessionCount}</td>
                          <td>{formatCurrency(row.grossInr)}</td>
                          <td>
                            {row.tdsInr != null ? (
                              <>
                                {formatCurrency(row.tdsInr)}
                                <span className="admin-muted" style={{ fontSize: '0.75rem' }}>
                                  {' '}
                                  ({row.tdsRatePercent ?? '—'}%)
                                </span>
                              </>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>{formatCurrency(row.deductionsInr)}</td>
                          <td>
                            {formatCurrency(row.netInr)}
                            {row.blocked ? (
                              <span className="admin-chip admin-chip--warn" style={{ marginLeft: 6 }}>
                                Blocked
                              </span>
                            ) : null}
                          </td>
                          <td>
                            {row.needsReview ? (
                              <span className="admin-chip admin-chip--warn">Needs review</span>
                            ) : (
                              formatCurrency(row.payableNowInr)
                            )}
                          </td>
                          <td>{formatCurrency(row.contestedInr)}</td>
                          <td>
                            {row.exportBatchStatus ? (
                              <>
                                <span className="admin-chip">{row.exportBatchStatus}</span>
                                {row.exportBatchStatus === 'FAILED' && row.exportBatchId ? (
                                  <button
                                    type="button"
                                    className="admin-btn admin-btn--ghost admin-btn--sm"
                                    style={{ marginLeft: 6 }}
                                    disabled={acting || !canWriteBilling}
                                    onClick={() => syncBatch(row.exportBatchId)}
                                  >
                                    Return to queue
                                  </button>
                                ) : null}
                              </>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            <span className={statusPillClass(row.status)}>{row.status}</span>
                          </td>
                          <td>
                            {row.disputes?.length ? (
                              <button
                                type="button"
                                className="admin-btn admin-btn--ghost admin-btn--sm"
                                onClick={() => setExpandedId(expandedId === row.invoiceId ? null : row.invoiceId)}
                              >
                                {expandedId === row.invoiceId ? 'Hide' : 'Disputes'}
                              </button>
                            ) : null}
                          </td>
                        </tr>
                        {expandedId === row.invoiceId && row.disputes?.length ? (
                          <tr key={`${row.invoiceId}-disputes`}>
                            <td colSpan={13}>
                              {row.disputes.map((d) => (
                                <div key={d.id} style={{ marginBottom: 12, padding: 12, background: '#f8fafc', borderRadius: 8 }}>
                                  <p style={{ margin: '0 0 6px' }}>
                                    <strong>Sessions:</strong> {(d.disputed_session_ids || []).join(', ') || '—'}
                                  </p>
                                  <p style={{ margin: '0 0 6px' }}>{d.comment}</p>
                                  {d.status === 'OPEN' || d.status === 'UNDER_REVIEW' ? (
                                    resolveId === d.id ? (
                                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                                        <input
                                          className="admin-input"
                                          placeholder="Resolution note"
                                          value={resolveNote}
                                          onChange={(e) => setResolveNote(e.target.value)}
                                        />
                                        <button
                                          type="button"
                                          className="admin-btn admin-btn--primary admin-btn--sm"
                                          disabled={acting || !canWriteBilling}
                                          onClick={() => resolveDispute(d.id, 'RESOLVED')}
                                        >
                                          Resolve
                                        </button>
                                        <button
                                          type="button"
                                          className="admin-btn admin-btn--ghost admin-btn--sm"
                                          disabled={acting || !canWriteBilling}
                                          onClick={() => resolveDispute(d.id, 'REJECTED')}
                                        >
                                          Reject
                                        </button>
                                        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setResolveId(null)}>
                                          Cancel
                                        </button>
                                      </div>
                                    ) : (
                                      <button
                                        type="button"
                                        className="admin-btn admin-btn--primary admin-btn--sm"
                                        disabled={!canWriteBilling}
                                        onClick={() => {
                                          setResolveId(d.id)
                                          setResolveNote('')
                                        }}
                                      >
                                        Resolve / reject
                                      </button>
                                    )
                                  ) : (
                                    <span className="admin-muted">Closed · {d.admin_resolution || d.status}</span>
                                  )}
                                </div>
                              ))}
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            }
            mobile={rows.map((row) => (
              <AdminTaskCard
                key={row.invoiceId}
                title={row.therapistName}
                subtitle={`${row.month} · ${row.caseCount} cases · ${row.sessionCount} sessions`}
                meta={
                  <>
                    <StatusBadge status={row.status} />
                    {row.therapistPayoutFlagged ? (
                      <span className="admin-chip admin-chip--warn">This therapist was flagged</span>
                    ) : null}
                    {row.needsReview ? (
                      <span className="admin-chip admin-chip--warn">Needs review</span>
                    ) : (
                      <span>Payable {formatCurrency(row.payableNowInr)}</span>
                    )}
                  </>
                }
                footer={
                  row.disputes?.length ? (
                    <button
                      type="button"
                      className="admin-btn admin-btn--ghost admin-btn--sm"
                      onClick={() => setExpandedId(expandedId === row.invoiceId ? null : row.invoiceId)}
                    >
                      {row.disputes.length} dispute(s)
                    </button>
                  ) : null
                }
              />
            ))}
          />
        )}

        <div className="finance-dash__sticky-action">
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            disabled={!payoutExportEnabled || !canWriteBilling || acting || exportableSelected.length === 0}
            onClick={exportBatch}
          >
            Export batch (mock) ({exportableSelected.length} selected)
          </button>
          <span className="admin-muted">
            {payoutExportEnabled
              ? 'Mock export only — live release stays off until cutover.'
              : 'Export enabled after cutover (PAYOUT_EXPORT_ENABLED).'}
          </span>
        </div>
        {exportNote ? (
          <p className="admin-muted" style={{ marginTop: 8, marginBottom: 0 }}>
            {exportNote}
          </p>
        ) : null}
      </AdminPanel>
    </>
  )
}
