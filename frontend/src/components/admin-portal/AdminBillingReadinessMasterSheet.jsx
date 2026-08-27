import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { formatInr } from '../../lib/financeConfidence.js'
import { AdminEmptyState, AdminSearchInput } from './ui/index.js'
import '../../styles/billing-readiness-master-sheet.css'
import { FinanceCorrectionPanel } from './FinanceCorrectionPanel.jsx'

const EXCEPTION_PILL = {
  CLEAR: 'brms-pill--clear',
  WARN: 'brms-pill--warn',
  BLOCK: 'brms-pill--block',
}

const WIDE_COLUMNS = [
  { key: 'caseCode', label: 'Client ID', sticky: true },
  { key: 'zohoId', label: 'Zoho id' },
  { key: 'clientName', label: 'Client name', sticky: true },
  { key: 'parentName', label: 'Parent name', sticky: true },
  { key: 'childName', label: 'Child' },
  { key: 'therapistName', label: 'Therapist' },
  { key: 'serviceType', label: 'Service type' },
  { key: 'clientType', label: 'Client type' },
  { key: 'clientStatus', label: 'Client status' },
  { key: 'caseManagerName', label: 'Case manager' },
  { key: 'startDate', label: 'Start date' },
  { key: 'prepaidPostpaid', label: 'Prepaid/postpaid' },
  { key: 'clientBillingRate', label: 'Client billing (agreement)' },
  { key: 'insighteShare', label: 'Insighte share' },
  { key: 'sessionsDelivered', label: 'Sessions delivered' },
  { key: 'leaves', label: 'Leaves' },
  { key: 'childAbsence', label: 'Child absence' },
  { key: 'extraSessions', label: 'Extra sessions' },
  { key: 'disputedSessions', label: 'Disputed sessions' },
  { key: 'engineAmountInr', label: 'Engine output (INR)' },
  { key: 'raisedInvoiceAmountInr', label: 'Raised invoice (INR)' },
  { key: 'sessionCountDiff', label: 'Session diff' },
  { key: 'leaveDiff', label: 'Leave diff' },
  { key: 'amountDiffInr', label: 'Amount diff (INR)' },
  { key: 'exceptionState', label: 'Exception' },
  { key: 'crm', label: 'CRM' },
  { key: 'hr', label: 'HR' },
  { key: 'notes', label: 'Notes' },
]

function formatCell(row, col) {
  switch (col.key) {
    case 'clientBillingRate':
      return formatMaybeMoney(row.billingInputs?.clientBillingRate)
    case 'insighteShare':
      return formatMaybeMoney(row.billingInputs?.insighteShare)
    case 'sessionsDelivered':
      return row.activity?.sessionsDelivered ?? '—'
    case 'leaves':
      return row.activity?.leaves ?? '—'
    case 'childAbsence':
      return row.activity?.childAbsence ?? '—'
    case 'extraSessions':
      return row.activity?.extraSessions ?? '—'
    case 'disputedSessions':
      return row.activity?.disputedSessions ?? '—'
    case 'engineAmountInr':
      return row.engineAmountInr != null ? formatInr(row.engineAmountInr) : '—'
    case 'raisedInvoiceAmountInr':
      return row.reconciliation?.raisedInvoiceAmountInr != null
        ? formatInr(row.reconciliation.raisedInvoiceAmountInr)
        : '—'
    case 'sessionCountDiff':
      return row.reconciliation?.sessionCountDiff ?? '—'
    case 'leaveDiff':
      return row.reconciliation?.leaveDiff ?? '—'
    case 'amountDiffInr':
      return row.reconciliation?.amountDiffInr != null ? formatInr(row.reconciliation.amountDiffInr) : '—'
    case 'crm':
      return row.comments?.crm ?? '—'
    case 'hr':
      return row.comments?.hr ?? '—'
    case 'notes':
      return row.comments?.notes ?? '—'
    default:
      return row[col.key] ?? '—'
  }
}

function formatMaybeMoney(value) {
  if (value == null) return '—'
  if (typeof value === 'number') return formatInr(value)
  return String(value)
}

function ExceptionPill({ state, held }) {
  const key = (state || 'CLEAR').toUpperCase()
  return (
    <span className={`brms-pill ${EXCEPTION_PILL[key] || EXCEPTION_PILL.CLEAR}${held ? ' brms-pill--held' : ''}`}>
      {key}
      {held ? ' · hold' : ''}
    </span>
  )
}

function ExpandedDetail({ row, billingMonth, onRefresh }) {
  return (
    <div className="brms-expanded">
      <div className="brms-expanded__grid">
        <section>
          <h4>Identity</h4>
          <dl>
            <dt>Client ID</dt><dd className="mono">{row.caseCode}</dd>
            <dt>Zoho id</dt><dd>{row.zohoId}</dd>
            <dt>Child</dt><dd>{row.childName}</dd>
            <dt>Therapist</dt><dd>{row.therapistName}</dd>
            <dt>Case manager</dt><dd>{row.caseManagerName}</dd>
            <dt>Start</dt><dd>{row.startDate}</dd>
            <dt>Prepaid/postpaid</dt><dd>{row.prepaidPostpaid}</dd>
          </dl>
        </section>
        <section>
          <h4>Billing inputs</h4>
          <dl>
            <dt>Agreement rate</dt><dd>{formatMaybeMoney(row.billingInputs?.clientBillingRate)}</dd>
            <dt>Insighte share</dt><dd>{formatMaybeMoney(row.billingInputs?.insighteShare)}</dd>
          </dl>
        </section>
        <section>
          <h4>Activity (InsighteCase)</h4>
          <dl>
            <dt>Sessions delivered</dt><dd>{row.activity?.sessionsDelivered ?? '—'}</dd>
            <dt>Leaves</dt><dd>{row.activity?.leaves ?? '—'}</dd>
            <dt>Child absence</dt><dd>{row.activity?.childAbsence ?? '—'}</dd>
            <dt>Extra sessions</dt><dd>{row.activity?.extraSessions ?? '—'}</dd>
            <dt>Disputed</dt><dd>{row.activity?.disputedSessions ?? '—'}</dd>
          </dl>
        </section>
        <section>
          <h4>Engine output</h4>
          <p className="brms-engine mono">{row.engineAmountInr != null ? formatInr(row.engineAmountInr) : '—'}</p>
          <p className="admin-muted">{row.engineSource}</p>
        </section>
        <section>
          <h4>Reconciliation</h4>
          <dl>
            <dt>Raised invoice #</dt><dd>{row.reconciliation?.raisedInvoiceNumber ?? '—'}</dd>
            <dt>Raised sessions</dt><dd>{row.reconciliation?.raisedInvoiceSessions ?? '—'}</dd>
            <dt>Raised leaves</dt><dd>{row.reconciliation?.raisedInvoiceLeaves ?? '—'}</dd>
            <dt>Raised amount</dt><dd>{formatMaybeMoney(row.reconciliation?.raisedInvoiceAmountInr)}</dd>
            <dt>Session diff</dt><dd className="mono">{row.reconciliation?.sessionCountDiff ?? '—'}</dd>
            <dt>Leave diff</dt><dd className="mono">{row.reconciliation?.leaveDiff ?? '—'}</dd>
            <dt>Amount diff</dt><dd className="mono">{formatMaybeMoney(row.reconciliation?.amountDiffInr)}</dd>
          </dl>
        </section>
        <section>
          <h4>Comments</h4>
          <dl>
            <dt>CRM</dt><dd>{row.comments?.crm}</dd>
            <dt>HR</dt><dd>{row.comments?.hr}</dd>
            <dt>Notes</dt><dd>{row.comments?.notes}</dd>
          </dl>
        </section>
      </div>
      <FinanceCorrectionPanel row={row} billingMonth={billingMonth} onDone={onRefresh} />
      {row.exceptions?.length ? (
        <ul className="brms-exception-list">
          {row.exceptions.map((ex) => (
            <li key={`${ex.type}-${ex.message}`}>
              <strong>{ex.type}</strong> ({ex.severity}) — {ex.message}
            </li>
          ))}
        </ul>
      ) : null}
      <p className="brms-expanded__links">
        {row.viewHref ? <Link to={row.viewHref}>Open case</Link> : null}
        {row.composerHref ? (
          <>
            {' · '}
            <Link to={row.composerHref}>Open composer</Link>
          </>
        ) : null}
      </p>
    </div>
  )
}

export function AdminBillingReadinessMasterSheet({ billingMonth: billingMonthProp, embedded = false }) {
  const [billingMonth, setBillingMonth] = useState(
    () => billingMonthProp || new Date().toISOString().slice(0, 7),
  )
  const [serviceType, setServiceType] = useState('')
  const [clientType, setClientType] = useState('')
  const [clientStatus, setClientStatus] = useState('')
  const [exceptionState, setExceptionState] = useState('')
  const [search, setSearch] = useState('')
  const [wideView, setWideView] = useState(false)
  const [expandedId, setExpandedId] = useState(null)
  const [rows, setRows] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (billingMonthProp) setBillingMonth(billingMonthProp)
  }, [billingMonthProp])

  const query = useMemo(() => {
    const q = new URLSearchParams()
    q.set('billing_month', billingMonth)
    if (serviceType) q.set('service_type', serviceType)
    if (clientType) q.set('client_type', clientType)
    if (clientStatus) q.set('client_status', clientStatus)
    if (exceptionState) q.set('exception_state', exceptionState)
    if (search.trim()) q.set('search', search.trim())
    q.set('limit', '200')
    return q.toString()
  }, [billingMonth, serviceType, clientType, clientStatus, exceptionState, search])

  const load = useCallback(() => {
    setLoading(true)
    setLoadError(null)
    apiFetch(`/api/v1/admin/finance-control-tower/billing-readiness-master-sheet?${query}`)
      .then((body) => {
        setRows(body)
        setLoadError(null)
      })
      .catch((err) => {
        setRows(null)
        setLoadError(err?.message || 'Billing readiness master sheet could not load right now.')
      })
      .finally(() => setLoading(false))
  }, [query])

  useEffect(() => {
    load()
  }, [load])

  const items = rows?.items || []

  return (
    <section className={`brms${embedded ? ' brms--embedded' : ''}`} aria-label="Billing readiness master sheet">
      {!embedded ? (
        <h3 className="finance-control-tower__section-title">Billing readiness master sheet</h3>
      ) : null}
      <p className="admin-muted brms__intro">
        Read-only client-side readiness — engine output matches the invoice composer path. Reconciliation compares
        InsighteCase client invoices to ledger and session activity (no legacy payout invoices).
      </p>

      <div className="brms__filters">
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Month</span>
          <input
            type="month"
            className="client-inv__filter-input"
            value={billingMonth}
            onChange={(e) => setBillingMonth(e.target.value)}
          />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Service type</span>
          <input
            className="client-inv__filter-input"
            value={serviceType}
            onChange={(e) => setServiceType(e.target.value)}
            placeholder="Filter service"
          />
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Client type</span>
          <select className="client-inv__filter-input" value={clientType} onChange={(e) => setClientType(e.target.value)}>
            <option value="">All</option>
            <option value="Shadow">Shadow</option>
            <option value="Homecare">Homecare</option>
            <option value="Package">Package</option>
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Client status</span>
          <select className="client-inv__filter-input" value={clientStatus} onChange={(e) => setClientStatus(e.target.value)}>
            <option value="">Active (default)</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="SUSPENDED">SUSPENDED</option>
            <option value="DEACTIVATED">DEACTIVATED</option>
            <option value="CLOSED">CLOSED</option>
          </select>
        </label>
        <label className="client-inv__filter-field">
          <span className="client-inv__filter-label">Exception</span>
          <select
            className="client-inv__filter-input"
            value={exceptionState}
            onChange={(e) => setExceptionState(e.target.value)}
          >
            <option value="">All</option>
            <option value="CLEAR">CLEAR</option>
            <option value="WARN">WARN</option>
            <option value="BLOCK">BLOCK</option>
          </select>
        </label>
        <AdminSearchInput value={search} onChange={setSearch} placeholder="Search client or case id…" />
        <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setWideView((v) => !v)}>
          {wideView ? 'Compact rows' : 'All columns view'}
        </button>
      </div>

      {loadError ? (
        <div className="admin-alert admin-alert--warning brms__error">{loadError}</div>
      ) : null}

      {loading ? <p className="admin-muted">Loading master sheet…</p> : null}

      {!loading && !loadError && items.length === 0 ? (
        <AdminEmptyState title="No cases match these filters" description="Try another month or clear filters." />
      ) : null}

      {!wideView && items.length > 0 ? (
        <ul className="brms-compact-list">
          {items.map((row) => {
            const open = expandedId === row.caseId
            return (
              <li key={row.caseId} className={`brms-compact-row${row.held ? ' brms-compact-row--held' : ''}`}>
                <button
                  type="button"
                  className="brms-compact-row__head"
                  aria-expanded={open}
                  onClick={() => setExpandedId(open ? null : row.caseId)}
                >
                  <span className="mono brms-compact-row__id">{row.caseCode}</span>
                  <span className="brms-compact-row__name">{row.clientName}</span>
                  <span className="brms-compact-row__therapist">{row.therapistName}</span>
                  <span className="brms-compact-row__service">{row.serviceType}</span>
                  <span className="brms-compact-row__status">{row.clientStatus}</span>
                  <span className="mono brms-compact-row__engine">
                    {row.engineAmountInr != null ? formatInr(row.engineAmountInr) : '—'}
                  </span>
                  <ExceptionPill state={row.exceptionState} held={row.held} />
                </button>
                {open ? <ExpandedDetail row={row} billingMonth={billingMonth} onRefresh={load} /> : null}
              </li>
            )
          })}
        </ul>
      ) : null}

      {wideView && items.length > 0 ? (
        <div className="brms-wide-wrap" data-testid="brms-wide-scroll">
          <table className="brms-wide-table">
            <thead>
              <tr>
                {WIDE_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className={col.sticky ? 'brms-wide-table__sticky' : undefined}
                    data-col={col.key}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.caseId} className={row.held ? 'brms-wide-table__held' : undefined}>
                  {WIDE_COLUMNS.map((col) => (
                    <td
                      key={col.key}
                      className={col.sticky ? 'brms-wide-table__sticky' : undefined}
                      data-col={col.key}
                    >
                      {col.key === 'exceptionState' ? (
                        <ExceptionPill state={row.exceptionState} held={row.held} />
                      ) : (
                        formatCell(row, col)
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  )
}
