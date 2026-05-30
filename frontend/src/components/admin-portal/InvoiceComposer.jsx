import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import { AdminPageHeader, AdminSearchInput, ServiceFilterSelect } from './ui/index.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { InvoiceComposerPreviewPanel } from './InvoiceComposerPreviewPanel.jsx'
import './admin-client-invoices.css'
import './admin-client-invoices-composer.css'

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
    if (!selectedCaseId || !canWriteBilling) return
    try {
      const inv = await run(
        () =>
          apiFetch(
            `/api/v1/admin/client-billing/cases/${selectedCaseId}/build-from-ledger?billing_month=${encodeURIComponent(billingMonth)}&include_pending=${includePending}`,
            { method: 'POST' }
          ),
        { successMsg: 'Draft invoice created from ledger' }
      )
      navigate(`/admin/invoices/client/${inv.id}`)
    } catch (err) {
      const msg = err?.message || ''
      if (msg.toLowerCase().includes('no billable ledger')) {
        setError(
          'No billable ledger rows for this month. Approve daily logs first, or use Create invoice manually.'
        )
      }
    }
  }

  async function createManualInvoice() {
    if (!selectedCaseId || !canWriteBilling) return
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
    if (!selectedIds.length || !canWriteBilling) return
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
    <div className="admin-page client-inv-composer-page">
      <AdminPageHeader
        eyebrow="Finance"
        title="Compose client invoice"
        subtitle="Review ledger and therapist billing, then raise or edit a family invoice."
      />
      <p style={{ margin: 0 }}>
        <Link to="/admin/invoices?tab=client">← Back to client invoices</Link>
      </p>

      <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />

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
        {canWriteBilling && selectedIds.length > 0 ? (
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
              <div className="admin-skeleton" style={{ minHeight: 120 }} />
            ) : cases.length === 0 ? (
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No cases in this queue.</p>
            ) : (
              cases.map((c) => (
                <div key={c.caseId} className={`client-inv-composer__case-card ${selectedCaseId === c.caseId ? 'is-selected' : ''}`}>
                  {canWriteBilling ? (
                    <input
                      type="checkbox"
                      checked={selectedIds.includes(c.caseId)}
                      onChange={() => toggleSelect(c.caseId)}
                      aria-label={`Select ${c.caseCode}`}
                      style={{ marginRight: 8 }}
                    />
                  ) : null}
                  <button type="button" className="client-inv-composer__case-card-btn" onClick={() => selectCase(c.caseId)}>
                    <strong>{c.caseCode}</strong> — {c.childName}
                    <span style={{ display: 'block', fontSize: '0.78rem', color: '#64748b', marginTop: 4 }}>
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
                <strong style={{ fontSize: '0.9rem' }}>
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
                  actionLoading={loading}
                  onBuildFromLedger={buildFromLedger}
                  onCreateManualInvoice={createManualInvoice}
                  onRemindTherapist={remindTherapist}
                  onRefresh={loadPreview}
                />
              </div>
            </>
          ) : (
            <div className="client-inv-composer__detail-scroll">
              <p style={{ color: '#64748b', marginTop: 24 }}>Select a case from the queue to review billing context.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
