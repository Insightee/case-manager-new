import { useCallback, useEffect, useState, Fragment } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { parseClientInvoiceFilters, buildClientBillingScopeQuery } from '../../lib/invoiceFilters.js'
import { useBillingRuntimeConfig } from '../../hooks/useBillingRuntimeConfig.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import '../../styles/finance-dashboard-modern.css'
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

function statusPillClass(status) {
  const key = (status || '').toLowerCase()
  if (key === 'queried') return 'client-inv__status-pill client-inv__status-pill--overdue'
  return `client-inv__status-pill client-inv__status-pill--${key || 'draft'}`
}

export function FinanceMondayBrief() {
  const [searchParams] = useSearchParams()
  const filters = parseClientInvoiceFilters(searchParams)
  const [brief, setBrief] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setLoadError(null)
    const scopeQs = buildClientBillingScopeQuery(filters)
    const briefQs = filters.month ? `?billing_month=${encodeURIComponent(filters.month)}` : ''
    Promise.all([
      apiFetch(`/api/v1/admin/client-billing/receivables${scopeQs}`),
      apiFetch(`/api/v1/admin/finance-overview/monday-brief${briefQs}`),
    ])
      .then(([receivables, briefData]) => {
        const totals = receivables?.totals || {}
        setBrief({
          ...briefData,
          moneyIn: {
            ...(briefData?.moneyIn || {}),
            collectibleOutstandingInr: totals.outstandingInr,
            overdueInr: totals.overdueInr,
            overdueCount: totals.overdueCount,
          },
          receivablesSource: receivables,
        })
      })
      .catch((err) => {
        setBrief(null)
        setLoadError(err?.message || 'Finance overview is unavailable right now.')
      })
      .finally(() => setLoading(false))
  }, [searchParams])

  if (loading) return <div className="admin-skeleton" style={{ minHeight: 120, marginBottom: 16 }} />
  if (loadError) {
    return (
      <AdminPanel title="Finance snapshot" padded style={{ marginBottom: 16 }}>
        <AdminEmptyState title="Finance snapshot could not load" description={loadError} />
      </AdminPanel>
    )
  }
  if (!brief) return null

  const moneyIn = brief.moneyIn || {}
  const moneyOut = brief.moneyOut || {}
  const top = brief.thisWeek?.topItems || []

  return (
    <AdminPanel title="Monday briefing" padded className="finance-dash" style={{ marginBottom: 16 }}>
      <div className="finance-dash__hero">
        <h2>Good morning — finance snapshot</h2>
        <p>
          {filters.month
            ? `Outstanding figures for billing month ${filters.month} — same source as Client invoices and Receivables.`
            : 'Figures match receivables and payout queue sources. Tap a card to drill in.'}
        </p>
      </div>
      <div className="finance-dash__grid" style={{ marginBottom: 16 }}>
        <div className="finance-dash__card finance-dash__card--accent">
          <span className="finance-dash__card-k">Money in · outstanding</span>
          <strong>{formatCurrency(moneyIn.collectibleOutstandingInr)}</strong>
          <Link to={brief.links?.receivables || '/admin/invoices?tab=receivables'} className="finance-dash__card-link">
            Receivables →
          </Link>
        </div>
        <div className="finance-dash__card finance-dash__card--warn">
          <span className="finance-dash__card-k">Overdue</span>
          <strong>{formatCurrency(moneyIn.overdueInr)}</strong>
          <span className="finance-dash__card-meta">{moneyIn.overdueCount ?? 0} invoice(s)</span>
        </div>
        <div className="finance-dash__card">
          <span className="finance-dash__card-k">Payment claims</span>
          <strong>{moneyIn.paymentClaimsPending ?? 0}</strong>
          <Link to={brief.links?.paymentClaims || '/admin/invoices?tab=payments'} className="finance-dash__card-link">
            Review →
          </Link>
        </div>
        <div className="finance-dash__card">
          <span className="finance-dash__card-k">Client disputes</span>
          <strong>{moneyIn.openClientDisputes ?? 0}</strong>
          <Link to={brief.links?.clientDisputes || '/admin/invoices?tab=disputes'} className="finance-dash__card-link">
            Disputes →
          </Link>
        </div>
        <div className="finance-dash__card finance-dash__card--accent">
          <span className="finance-dash__card-k">Money out · payable now</span>
          <strong>{formatCurrency(moneyOut.totalPayableInr)}</strong>
          <Link to={brief.links?.therapistPayoutQueue || '/admin/therapist-payouts?sub=payouts'} className="finance-dash__card-link">
            Payout queue →
          </Link>
        </div>
        <div className="finance-dash__card">
          <span className="finance-dash__card-k">Statements pending</span>
          <strong>{moneyOut.statementsPendingApproval ?? 0}</strong>
          <span className="finance-dash__card-meta">{moneyOut.disputedQueriedCount ?? 0} disputed</span>
        </div>
      </div>
      {brief.thisWeek?.mostImportant ? (
        <p style={{ margin: 0 }}>
          <strong>Focus:</strong> {brief.thisWeek.mostImportant.label}
        </p>
      ) : top.length === 0 ? (
        <p className="admin-muted" style={{ margin: 0 }}>Nothing urgent this week.</p>
      ) : (
        <ul className="admin-muted" style={{ margin: '8px 0 0', paddingLeft: 18 }}>
          {top.map((item) => (
            <li key={item.kind}>
              <Link to={item.href}>{item.label}</Link>
            </li>
          ))}
        </ul>
      )}
      <p className="admin-muted" style={{ marginTop: 12, marginBottom: 0, fontSize: '0.85rem' }}>
        {moneyOut.approveDisabledNote}
      </p>
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
                          <td>{row.therapistName}</td>
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
