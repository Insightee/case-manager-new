import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPanel } from './ui/index.js'

export function AdminTherapistPayoutsDashboard() {
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      apiFetch('/api/v1/admin/finance-overview/summary'),
      apiFetch('/api/v1/invoices?status=IN_REVIEW'),
    ])
      .then(([overview, inReview]) => {
        setSummary({
          overview: overview?.queues || {},
          inReviewCount: Array.isArray(inReview) ? inReview.length : 0,
          billingMonth: overview?.billingMonth,
        })
      })
      .catch(() => setSummary(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="admin-skeleton" style={{ minHeight: 120 }} />
  if (!summary) return <p className="admin-muted">Could not load payout dashboard.</p>

  const q = summary.overview

  return (
    <div className="client-inv-therapist-dash">
      <p className="admin-muted" style={{ marginBottom: 16 }}>
        Therapist payouts are separate from client invoices. Approve submitted invoices, then record payment when paid.
      </p>
      <div className="admin-home-queue__grid">
        <AdminPanel title="In review" padded>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 8px' }}>{summary.inReviewCount}</p>
          <Link to="/admin/therapist-payouts?sub=payouts&status=IN_REVIEW" className="admin-btn admin-btn--primary admin-btn--sm">
            Review queue →
          </Link>
        </AdminPanel>
        <AdminPanel title="Approved, unpaid" padded>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 8px' }}>{q.payoutsApprovedUnpaid ?? 0}</p>
          <Link to="/admin/therapist-payouts?sub=payouts&status=APPROVED" className="admin-btn admin-btn--ghost admin-btn--sm">
            View approved →
          </Link>
        </AdminPanel>
        <AdminPanel title="Therapist pending billing" padded>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 8px' }}>{q.therapistPending ?? 0}</p>
          <Link
            to={`/admin/invoices/compose?billing_month=${encodeURIComponent(summary.billingMonth || '')}&queue=therapist_pending`}
            className="admin-btn admin-btn--ghost admin-btn--sm"
          >
            Composer queue →
          </Link>
        </AdminPanel>
        <AdminPanel title="Submitted this month" padded>
          <p style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 8px' }}>{q.therapistSubmitted ?? 0}</p>
          <Link
            to={`/admin/invoices/compose?billing_month=${encodeURIComponent(summary.billingMonth || '')}&queue=therapist_submitted`}
            className="admin-btn admin-btn--ghost admin-btn--sm"
          >
            View in composer →
          </Link>
        </AdminPanel>
      </div>
    </div>
  )
}
