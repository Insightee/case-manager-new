import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import { useBillingRuntimeConfig } from '../../hooks/useBillingRuntimeConfig.js'
import { AdminPageHeader, AdminSearchInput, ServiceFilterSelect } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { InvoiceComposerPreviewPanel } from './InvoiceComposerPreviewPanel.jsx'
import './admin-client-invoices.css'
import './admin-client-invoices-composer.css'
import '../../styles/finance-stage2.css'

const QUEUES = [
  { id: 'all', label: 'All' },
  { id: 'not_invoiced_this_month', label: 'Not invoiced (month)' },
  { id: 'not_invoiced_last_30_days', label: 'Not invoiced (30d)' },
  { id: 'new_clients', label: 'New clients' },
  { id: 'ledger_ready', label: 'Ledger ready' },
  { id: 'therapist_submitted', label: 'Therapist submitted' },
  { id: 'therapist_pending', label: 'Therapist pending' },
  { id: 'disputed', label: 'Disputed' },
  { id: 'draft', label: 'Draft' },
]

const BADGE_LABELS = {
  not_invoiced: 'Not invoiced',
  new_client: 'New client',
  ledger_ready: 'Ledger ready',
  therapist_submitted: 'Therapist submitted',
  therapist_pending: 'Therapist pending',
  disputed: 'Disputed',
  overdue: 'Overdue',
  draft: 'Draft',
}

function defaultMonth() {
  return new Date().toISOString().slice(0, 7)
}

function useIsMobile(breakpoint = 1024) {
  const [mobile, setMobile] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < breakpoint : false
  )
  useEffect(() => {
    const onResize = () => setMobile(window.innerWidth < breakpoint)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])
  return mobile
}

export function InvoiceComposer() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { canWriteBilling } = useModuleWrite()
  const runtime = useBillingRuntimeConfig({ enabled: true })
  const writesEnabled = Boolean(runtime.writesEnabled)
  const { loading, error, successMessage, run, clearMessages, setError, setSuccessMessage } = useBillingAction()
  const isMobile = useIsMobile()
  const [billingMonth, setBillingMonth] = useState(searchParams.get('billing_month') || defaultMonth())
  const [queue, setQueue] = useState(searchParams.get('queue') || 'not_invoiced_this_month')
  const [module, setModule] = useState(searchParams.get('module') || '')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [cases, setCases] = useState([])
  const [loadingCases, setLoadingCases] = useState(true)
  const [selectedCaseId, setSelectedCaseId] = useState(
    searchParams.get('case_id') ? Number(searchParams.get('case_id')) : null
  )
  const [selectedIds, setSelectedIds] = useState([])
  const [mobileDetail, setMobileDetail] = useState(Boolean(searchParams.get('case_id')))
  const [preview, setPreview] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 350)
    return () => clearTimeout(t)
  }, [search])

  const loadCases = useCallback(() => {
    setLoadingCases(true)
    const p = new URLSearchParams({
      billing_month: billingMonth,
      queue,
    })
    if (module) p.set('module', module)
    if (debouncedSearch) p.set('search', debouncedSearch)
    apiFetch(`/api/v1/admin/client-billing/composer-cases?${p}`)
      .then((data) => setCases(Array.isArray(data) ? data : []))
      .catch(() => setCases([]))
      .finally(() => setLoadingCases(false))
  }, [billingMonth, queue, module, debouncedSearch])

  useEffect(() => {
    loadCases()
  }, [loadCases])

  useEffect(() => {
    const next = new URLSearchParams()
    next.set('billing_month', billingMonth)
    next.set('queue', queue)
    if (module) next.set('module', module)
    if (selectedCaseId) next.set('case_id', String(selectedCaseId))
    setSearchParams(next, { replace: true })
  }, [billingMonth, queue, module, selectedCaseId, setSearchParams])

  const loadPreview = useCallback(() => {
    if (!selectedCaseId) {
      setPreview(null)
      return
    }
    setLoadingPreview(true)
    apiFetch(
      `/api/v1/admin/client-billing/composer-preview?case_id=${selectedCaseId}&billing_month=${encodeURIComponent(billingMonth)}`
    )
      .then(setPreview)
      .catch(() => setPreview(null))
      .finally(() => setLoadingPreview(false))
  }, [selectedCaseId, billingMonth])

  useEffect(() => {
    loadPreview()
  }, [loadPreview])

  const selectedCard = useMemo(
    () => cases.find((c) => c.caseId === selectedCaseId),
    [cases, selectedCaseId]
  )

  const showSearchQueueHint = debouncedSearch && !loadingCases && cases.length === 0 && queue !== 'all'

  const bodyClass = [
    'client-inv-composer__body',
    selectedCaseId ? 'client-inv-composer__body--has-selection' : '',
    isMobile && mobileDetail && selectedCaseId ? 'client-inv-composer__body--detail-only' : '',
  ]
    .filter(Boolean)
    .join(' ')

  function selectCase(caseId) {
    setSelectedCaseId(caseId)
    if (isMobile) setMobileDetail(true)
    clearMessages()
  }

  function clearSelection() {
    setSelectedCaseId(null)
    setMobileDetail(false)
  }

  function toggleSelect(caseId) {
    setSelectedIds((prev) =>
      prev.includes(caseId) ? prev.filter((id) => id !== caseId) : [...prev, caseId]
    )
  }

  async function buildFromLedger(includePending = false) {
    if (!selectedCaseId || !canWriteBilling || !writesEnabled) return
    if (preview && preview.canBuild === false) {
      setError('Cannot build invoice while calculation exceptions are open for this case.')
      return
    }
    try {
      const inv = await run(
        () =>
          apiFetch(
            `/api/v1/admin/client-billing/cases/${selectedCaseId}/build-from-ledger?billing_month=${encodeURIComponent(billingMonth)}&include_pending=${includePending}`,
            { method: 'POST' }
          ),
        { successMsg: 'Draft invoice created from ledger' }
      )
      if (inv?.zohoSync?.status === 'not_configured') {
        setSuccessMessage('Draft invoice created from ledger · Zoho sync not configured')
      }
      navigate(`/admin/invoices/client/${inv.id}`)
    } catch (err) {
      const msg = err?.message || ''
      if (msg.toLowerCase().includes('no billable ledger')) {
        setError(
          'Looks like we still need billable ledger rows for this month. Approve daily logs first, then try Build from ledger again — it will post the payout-report amount automatically.'
        )
      } else if (msg.toLowerCase().includes('calculation exception')) {
        setError(msg)
      }
    }
  }

  async function createManualInvoice() {
    if (!selectedCaseId || !canWriteBilling || !writesEnabled) return
    if (preview && preview.canBuild === false) {
      setError('Cannot create invoice while calculation exceptions are open for this case.')
      return
    }
    const inv = await run(
      () =>
        apiFetch('/api/v1/admin/client-billing/invoices', {
          method: 'POST',
          body: JSON.stringify({
            case_id: selectedCaseId,
            invoice_type: preview?.billingRule?.invoiceType || 'POSTPAID',
            billing_month: billingMonth,
            lines: [],
          }),
        }),
      { successMsg: 'Manual draft invoice created' }
    )
    navigate(`/admin/invoices/client/${inv.id}`)
  }

  async function postDraftCharge(ledgerId) {
    if (!ledgerId || !canWriteBilling || !writesEnabled) return
    const note = encodeURIComponent('Posted from invoice composer (explicit finance action)')
    await run(
      () =>
        apiFetch(`/api/v1/admin/ledger-billing/ledger/${ledgerId}/post-finance?note=${note}`, {
          method: 'POST',
        }),
      { successMsg: 'DRAFT charge posted — it can now enter an invoice' }
    )
    loadPreview()
  }

  async function remindTherapist() {
    if (!selectedCaseId) return
    try {
      const res = await run(() =>
        apiFetch('/api/v1/admin/client-billing/remind-therapist', {
          method: 'POST',
          body: JSON.stringify({ case_id: selectedCaseId, billing_month: billingMonth }),
        })
      )
      const n = res?.notifiedCount ?? 0
      setSuccessMessage(
        n > 0 ? `Reminder sent to ${n} therapist${n === 1 ? '' : 's'}` : 'No therapist assigned to notify'
      )
    } catch {
      /* error shown via hook */
    }
    loadPreview()
  }

  async function bulkBuildFromLedger() {
    if (!selectedIds.length || !canWriteBilling || !writesEnabled) return
    const result = await run(
      () =>
        apiFetch('/api/v1/admin/finance-bulk/client-invoices', {
          method: 'POST',
          body: JSON.stringify({
            action: 'build_from_ledger',
            case_ids: selectedIds,
            billing_month: billingMonth,
          }),
        }),
      { successMsg: `Built ${selectedIds.length} draft(s)` }
    )
    const ok = result?.succeeded?.length ?? 0
    const fail = result?.failed?.length ?? 0
    if (fail) {
      setError(`${ok} succeeded, ${fail} failed. Check cases without approved ledger rows.`)
    }
    setSelectedIds([])
    loadCases()
  }

  return (
    <div className="admin-page client-inv-composer-page finance-stage2">
      <AdminPageHeader
        eyebrow="Finance"
        title="Compose client invoice"
        subtitle="Review ledger and therapist billing, then raise or edit a family invoice."
      />
      <p className="finance-stage2-back">
        <Link to="/admin/invoices?tab=client">← Back to client invoices</Link>
      </p>

      {runtime.provisional ? (
        <div className="finance-stage2-banner finance-stage2-banner--mint" role="status">
          Engine amounts are provisional until cutover. Builds stay gated by write access and open exceptions.
        </div>
      ) : null}

      <BillingActionAlert error={error || runtime.error} successMessage={successMessage} onDismiss={clearMessages} />

      <div className="client-inv-composer__toolbar">
        <div className="client-inv-composer__toolbar-filters">
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Billing month</span>
            <input
              type="month"
              className="client-inv__filter-input"
              value={billingMonth}
              onChange={(e) => setBillingMonth(e.target.value)}
            />
          </label>
          <label className="client-inv__filter-field">
            <span className="client-inv__filter-label">Service</span>
            <ServiceFilterSelect className="client-inv__filter-input" value={module} onChange={setModule} />
          </label>
          <AdminSearchInput
            className="client-inv__filter-field--search-compact"
            value={search}
            onChange={setSearch}
            placeholder="Search case, child, parent…"
          />
        </div>
        <div className="client-inv-composer__queues" role="tablist" aria-label="Billing queue">
          {QUEUES.map((q) => (
            <button
              key={q.id}
              type="button"
              role="tab"
              aria-selected={queue === q.id}
              className={`client-inv-composer__queue-btn ${queue === q.id ? 'is-active' : ''}`}
              onClick={() => setQueue(q.id)}
            >
              {q.label}
            </button>
          ))}
        </div>
        {canWriteBilling && writesEnabled && selectedIds.length > 0 ? (
          <button
            type="button"
            className="admin-btn admin-btn--secondary admin-btn--sm"
            disabled={loading}
            onClick={bulkBuildFromLedger}
          >
            Build {selectedIds.length} from ledger
          </button>
        ) : null}
      </div>

      <div className={bodyClass}>
        <div className="client-inv-composer__list-pane">
          <p className="client-inv-composer__list-meta" aria-live="polite">
            {loadingCases ? 'Loading cases…' : `${cases.length} case${cases.length === 1 ? '' : 's'} in queue`}
          </p>
          {showSearchQueueHint ? (
            <p className="client-inv-composer__search-hint">
              No matches in this queue.{' '}
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => setQueue('all')}>
                Show all
              </button>
            </p>
          ) : null}
          <div className="client-inv-composer__case-list">
            {loadingCases ? (
              <div className="admin-skeleton finance-stage2-skeleton" aria-busy="true" />
            ) : cases.length === 0 ? (
              <p className="finance-stage2-empty">No cases in this queue.</p>
            ) : (
              cases.map((c) => (
                <div key={c.caseId} className={`client-inv-composer__case-card ${selectedCaseId === c.caseId ? 'is-selected' : ''}`}>
                  {canWriteBilling ? (
                    <input
                      type="checkbox"
                      className="finance-stage2-case-check"
                      checked={selectedIds.includes(c.caseId)}
                      onChange={() => toggleSelect(c.caseId)}
                      aria-label={`Select ${c.caseCode}`}
                    />
                  ) : null}
                  <button type="button" className="client-inv-composer__case-card-btn" onClick={() => selectCase(c.caseId)}>
                    <strong>{c.caseCode}</strong> — {c.childName}
                    <span className="finance-stage2-case-meta">
                      {c.serviceType} · {c.sessionsCompletedThisMonth ?? 0} sessions
                    </span>
                    <div className="client-inv-composer__badges">
                      {(c.badges || []).map((b) => (
                        <span
                          key={b}
                          className={`client-inv-composer__badge ${b === 'therapist_pending' ? 'client-inv-composer__badge--warn' : ''} ${b === 'ledger_ready' ? 'client-inv-composer__badge--ok' : ''}`}
                        >
                          {BADGE_LABELS[b] || b}
                        </span>
                      ))}
                    </div>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>

        <section className="client-inv-composer__detail-pane" aria-label="Invoice preview">
          {selectedCaseId ? (
            <>
              <div className="client-inv-composer__detail-head">
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm client-inv-composer__mobile-back"
                  onClick={clearSelection}
                >
                  ← Back to queue
                </button>
                <strong className="finance-stage2-detail-title">
                  {selectedCard?.caseCode} — {selectedCard?.childName}
                </strong>
              </div>
              <div className="client-inv-composer__detail-scroll">
                <InvoiceComposerPreviewPanel
                  preview={preview}
                  loading={loadingPreview}
                  card={selectedCard}
                  billingMonth={billingMonth}
                  canWriteBilling={canWriteBilling}
                  writesEnabled={writesEnabled}
                  actionLoading={loading}
                  onBuildFromLedger={buildFromLedger}
                  onCreateManualInvoice={createManualInvoice}
                  onRemindTherapist={remindTherapist}
                  onPostDraftCharge={postDraftCharge}
                  onRefresh={loadPreview}
                />
              </div>
            </>
          ) : (
            <div className="client-inv-composer__detail-scroll">
              <p className="finance-stage2-empty finance-stage2-empty--pad">
                Select a case from the queue to review billing context.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
