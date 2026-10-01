import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { useModuleWrite } from '../../hooks/useModuleWrite.js'
import { BillingActionAlert } from './ui/BillingActionAlert.jsx'
import { useBillingAction } from '../../hooks/useBillingAction.js'
import { formatCurrency } from './ui/index.js'

export function CaseBillingActionsCard({ caseId, compact = false }) {
  const navigate = useNavigate()
  const { canWriteBilling } = useModuleWrite()
  const [summary, setSummary] = useState(null)
  const [loadState, setLoadState] = useState('loading')
  const [loadError, setLoadError] = useState('')
  const { loading, error, successMessage, run, clearMessages } = useBillingAction()

  useEffect(() => {
    if (!caseId) return
    let cancelled = false
    setLoadState('loading')
    setLoadError('')
    apiFetch(`/api/v1/admin/client-billing/cases/${caseId}/billing-summary`)
      .then((data) => {
        if (cancelled) return
        setSummary(data)
        setLoadState('ready')
      })
      .catch((err) => {
        if (cancelled) return
        setSummary(null)
        setLoadState('error')
        const status = err?.status
        if (status === 404) {
          setLoadError(
            'Client billing tools are not enabled on this server yet. Case billing rates below still apply — ask ops to set ENABLE_BILLING=true when finance is ready.',
          )
        } else if (status === 403) {
          setLoadError('You can view case billing, but invoice actions need invoice.approve access.')
        } else {
          setLoadError(err?.message || 'Could not load billing actions for this case.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [caseId])

  async function raiseInvoice() {
    const inv = await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/cases/${caseId}/onboarding-invoice-draft`, {
          method: 'POST',
          body: JSON.stringify({}),
        }),
      { successMsg: 'Draft invoice created' },
    )
    if (inv?.id) navigate(`/admin/invoices/client/${inv.id}`)
  }

  async function sendToQueue() {
    await run(
      () =>
        apiFetch(`/api/v1/admin/client-billing/cases/${caseId}/onboarding-invoice-draft`, {
          method: 'POST',
          body: JSON.stringify({ send_to_queue_only: true }),
        }),
      { successMsg: 'Case queued for Finance composer' },
    )
  }

  if (loadState === 'loading') {
    return (
      <section className="admin-panel" style={{ padding: compact ? 12 : 16, marginBottom: 16 }}>
        <p className="admin-muted" style={{ margin: 0, fontSize: '0.85rem' }}>
          Loading billing actions…
        </p>
      </section>
    )
  }

  if (loadState === 'error') {
    return (
      <section className="admin-panel" style={{ padding: compact ? 12 : 16, marginBottom: 16 }}>
        <h3 style={{ margin: '0 0 8px', fontSize: compact ? '0.95rem' : '1.05rem' }}>Billing actions</h3>
        <p className="admin-alert admin-alert--info" style={{ margin: 0, fontSize: '0.85rem' }}>
          {loadError}
        </p>
        <div className="admin-btn-group" style={{ marginTop: 12 }}>
          <Link to={`/admin/invoices?tab=client&case_id=${caseId}`} className="admin-btn admin-btn--ghost admin-btn--sm">
            View invoices
          </Link>
        </div>
      </section>
    )
  }

  if (!summary) return null

  return (
    <section className="admin-panel" style={{ padding: compact ? 12 : 16, marginBottom: 16 }}>
      <h3 style={{ margin: '0 0 8px', fontSize: compact ? '0.95rem' : '1.05rem' }}>Billing actions</h3>
      <BillingActionAlert error={error} successMessage={successMessage} onDismiss={clearMessages} />
      <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0 0 8px' }}>
        {summary.clientBillingMode || summary.billingType || '—'}
        {summary.productBillingRuleName ? ` · ${summary.productBillingRuleName}` : ''}
        {summary.openBalanceInr > 0 ? ` · Outstanding ${formatCurrency(summary.openBalanceInr)}` : ''}
      </p>
      {summary.lastInvoice ? (
        <p style={{ fontSize: '0.8rem', margin: '0 0 12px' }}>
          Last invoice: {summary.lastInvoice.billingMonth} · {summary.lastInvoice.status}
        </p>
      ) : null}
      <div className="admin-btn-group">
        {canWriteBilling ? (
          <>
            <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={loading} onClick={raiseInvoice}>
              Raise invoice
            </button>
            <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" disabled={loading} onClick={sendToQueue}>
              Send to billing queue
            </button>
          </>
        ) : null}
        <Link to={`/admin/invoices?tab=client&case_id=${caseId}`} className="admin-btn admin-btn--ghost admin-btn--sm">
          View invoices
        </Link>
        <Link
          to={`/admin/invoices/compose?case_id=${caseId}&queue=not_invoiced_this_month`}
          className="admin-btn admin-btn--ghost admin-btn--sm"
        >
          Open composer
        </Link>
      </div>
    </section>
  )
}
