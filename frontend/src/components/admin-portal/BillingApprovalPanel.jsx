import { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { formatDateTimeIN } from '../../lib/datetime.js'
import { billingSummary, formatInr } from '../invoices/invoiceUtils.js'


export function BillingApprovalPanel({ requestId, onApplied }) {
  const [request, setRequest] = useState(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    if (!requestId) return
    setLoading(true)
    setError('')
    try {
      setRequest(await apiFetch(`/api/v1/billing-approvals/${requestId}`))
    } catch (err) {
      setError(err.message || 'Could not load this billing approval request.')
    } finally {
      setLoading(false)
    }
  }, [requestId])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      void load()
    }, 0)
    return () => window.clearTimeout(timeoutId)
  }, [load])

  async function review(action) {
    setActing(true)
    setError('')
    try {
      const updated = await apiFetch(`/api/v1/billing-approvals/${requestId}/${action}`, {
        method: 'POST',
      })
      setRequest((current) => ({ ...current, ...updated, canReview: current?.canReview }))
      if (action === 'approve') await onApplied?.()
    } catch (err) {
      setError(err.message || 'Could not review this billing request.')
    } finally {
      setActing(false)
    }
  }

  if (!requestId) return null
  if (loading) return <p className="admin-muted">Loading billing approval…</p>
  if (error && !request) return <p className="admin-alert" style={{ color: '#b91c1c' }}>{error}</p>
  if (!request) return null

  const isPending = request.status === 'PENDING'

  return (
    <section className="admin-panel" style={{ padding: 16 }}>
      <p className="admin-page__eyebrow">Minimum profit guardrail</p>
      <h3 style={{ marginTop: 4 }}>
        {isPending ? 'Low-margin billing needs approval' : `Billing request ${request.status.toLowerCase()}`}
      </h3>
      <p>
        Projected Insighte profit: <strong>{formatInr(request.projectedProfitInr)}</strong>
        {' · '}minimum required: {formatInr(5000)}
      </p>
      <div className="admin-form-grid" style={{ marginTop: 12 }}>
        <div>
          <strong>Current billing</strong>
          <p className="admin-muted">{billingSummary(request.previousBilling)}</p>
        </div>
        <div>
          <strong>Requested billing</strong>
          <p>{billingSummary(request.proposedBilling)}</p>
        </div>
      </div>
      <p className="admin-muted" style={{ fontSize: '0.8rem' }}>
        Requested by {request.requestedBy || 'Unknown user'}
        {request.requestedAt ? ` on ${formatDateTimeIN(request.requestedAt)}` : ''}
        {request.reviewedBy ? ` · Reviewed by ${request.reviewedBy}` : ''}
        {request.appliedAt ? ` · Applied ${formatDateTimeIN(request.appliedAt)}` : ''}
      </p>
      {error ? <p className="admin-alert" style={{ color: '#b91c1c' }}>{error}</p> : null}
      {isPending && request.canReview ? (
        <div className="admin-btn-group" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="admin-btn admin-btn--primary"
            disabled={acting}
            onClick={() => review('approve')}
          >
            {acting ? 'Reviewing…' : 'Approve billing'}
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--ghost"
            disabled={acting}
            onClick={() => review('reject')}
          >
            Reject
          </button>
        </div>
      ) : null}
      {isPending && !request.canReview ? (
        <p className="admin-alert admin-alert--info">Waiting for Nicky’s review. Current billing remains active.</p>
      ) : null}
    </section>
  )
}
