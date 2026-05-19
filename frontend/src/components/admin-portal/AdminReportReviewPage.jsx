import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AdminPageHeader, AdminPanel, AdminEmptyState, StatusBadge } from './ui/index.js'

export function AdminReportReviewPage() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [viewReport, setViewReport] = useState(null)
  const [rejectTarget, setRejectTarget] = useState(null)
  const [rejectComment, setRejectComment] = useState('')
  const [message, setMessage] = useState('')
  const [acting, setActing] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const rows = await apiFetch('/api/v1/reports/monthly?status=UNDER_REVIEW').catch(() =>
        apiFetch('/api/v1/reports/monthly'),
      )
      setReports(rows.filter((r) => String(r.status).toUpperCase() === 'UNDER_REVIEW'))
    } catch {
      setReports([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function openView(id) {
    try {
      const detail = await apiFetch(`/api/v1/reports/monthly/${id}`)
      setViewReport(detail)
    } catch (err) {
      setMessage(err.message || 'Could not load report')
    }
  }

  async function approve(id) {
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${id}/approve`, {
        method: 'POST',
        body: JSON.stringify({
          comment: 'Approved',
          visibility_status: 'APPROVED_FOR_PARENT',
        }),
      })
      setMessage('Report approved and published for parents.')
      setViewReport(null)
      load()
    } catch (err) {
      setMessage(err.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function submitReject() {
    if (!rejectTarget || !rejectComment.trim()) return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/reports/monthly/${rejectTarget.id}/reject`, {
        method: 'POST',
        body: JSON.stringify({ comment: rejectComment.trim() }),
      })
      setRejectTarget(null)
      setRejectComment('')
      setViewReport(null)
      setMessage('Report returned to therapist with comments.')
      load()
    } catch (err) {
      setMessage(err.message || 'Reject failed')
    } finally {
      setActing(false)
    }
  }

  return (
    <div className="admin-page">
      <AdminPageHeader
        eyebrow="Quality & compliance"
        title="Report review"
        subtitle="Approve to publish for parents; reject with comments for resubmission."
        actions={
          <button type="button" className="admin-btn admin-btn--secondary" onClick={load}>
            Refresh
          </button>
        }
      />

      {message ? (
        <p style={{ padding: '8px 12px', background: '#ecfdf5', borderRadius: 8, color: '#047857', marginBottom: 16 }}>{message}</p>
      ) : null}

      <AdminPanel title={`${reports.length} awaiting review`} subtitle="Monthly therapist reports">
        {loading ? (
          <div className="admin-skeleton" />
        ) : reports.length === 0 ? (
          <AdminEmptyState title="Review queue empty" description="All monthly reports are processed." />
        ) : (
          <ul className="admin-queue">
            {reports.map((r) => (
              <li key={r.id} className="admin-queue__item">
                <div>
                  <p className="admin-queue__title">
                    {r.child_name} — {r.month}
                  </p>
                  <p className="admin-queue__meta">
                    {r.case_code}
                    {r.summary ? ` · ${r.summary.slice(0, 80)}${r.summary.length > 80 ? '…' : ''}` : ''}
                  </p>
                </div>
                <div className="admin-btn-group">
                  <StatusBadge status={r.status} />
                  <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => openView(r.id)}>
                    View
                  </button>
                  <button type="button" className="admin-btn admin-btn--primary admin-btn--sm" disabled={acting} onClick={() => approve(r.id)}>
                    Approve
                  </button>
                  <button
                    type="button"
                    className="admin-btn admin-btn--danger admin-btn--sm"
                    disabled={acting}
                    onClick={() => {
                      setRejectTarget(r)
                      setRejectComment('')
                    }}
                  >
                    Reject
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </AdminPanel>

      {viewReport ? (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 560, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>
              {viewReport.child_name} — {viewReport.month}
            </h2>
            <p style={{ color: '#64748b' }}>{viewReport.case_code}</p>
            <p style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{viewReport.summary || 'No summary provided.'}</p>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={() => approve(viewReport.id)}>
                Approve for parents
              </button>
              <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setViewReport(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {rejectTarget ? (
        <div
          role="dialog"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.4)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
            zIndex: 50,
          }}
        >
          <div style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 480, width: '100%' }}>
            <h2 style={{ marginTop: 0 }}>Reject report</h2>
            <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
              {rejectTarget.child_name} — {rejectTarget.month}
            </p>
            <label style={{ display: 'block', marginTop: 12 }}>
              Comment for therapist (required)
              <textarea
                className="admin-input"
                rows={4}
                value={rejectComment}
                onChange={(e) => setRejectComment(e.target.value)}
                style={{ width: '100%', marginTop: 6 }}
              />
            </label>
            <div className="admin-btn-group" style={{ marginTop: 16 }}>
              <button type="button" className="admin-btn admin-btn--danger" disabled={acting || !rejectComment.trim()} onClick={submitReject}>
                Send rejection
              </button>
              <button type="button" className="admin-btn admin-btn--secondary" onClick={() => setRejectTarget(null)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
