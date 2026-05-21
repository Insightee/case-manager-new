import { useCallback, useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload, getTokens } from '../../lib/apiClient.js'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../reports/report-editor.css'

const API_URL = import.meta.env.VITE_API_URL || ''

const STATUS_LABELS = {
  pending_review: 'Pending your review',
  approved: 'Approved',
  changes_sent: 'Changes sent',
  pending: 'Pending acknowledgement',
  acknowledged: 'Acknowledged',
}

function StatusChip({ status }) {
  const label = STATUS_LABELS[status] || status
  const tone =
    status === 'approved' || status === 'acknowledged'
      ? 'completed'
      : status === 'changes_sent'
        ? 'warning'
        : 'pending'
  return <span className={`status ${tone}`}>{label}</span>
}

async function fetchBlobUrl(downloadPath) {
  const { access } = getTokens()
  const url = `${API_URL}${downloadPath}`
  const res = await fetch(url, { headers: access ? { Authorization: `Bearer ${access}` } : {} })
  if (!res.ok) throw new Error('Could not load document')
  const blob = await res.blob()
  return URL.createObjectURL(blob)
}

export function ParentReportsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = searchParams.get('type') === 'iep' ? 'iep' : 'monthly'
  const [tab, setTab] = useState(initialTab)
  const [hub, setHub] = useState({ monthly: [], iep: [] })
  const [caseFilter, setCaseFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [commentBody, setCommentBody] = useState('')
  const [commentType, setCommentType] = useState('GENERAL')
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const loadHub = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiFetch('/api/v1/parent/reports/hub')
      setHub({ monthly: data.monthly || [], iep: data.iep || [] })
    } catch (err) {
      setError(err.message || 'Could not load reports')
      setHub({ monthly: [], iep: [] })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadHub()
  }, [loadHub])

  useEffect(() => {
    setSearchParams(tab === 'iep' ? { type: 'iep' } : {}, { replace: true })
  }, [tab, setSearchParams])

  const list = tab === 'iep' ? hub.iep : hub.monthly

  const caseOptions = useMemo(() => {
    const ids = new Map()
    list.forEach((item) => {
      if (item.caseDbId) ids.set(String(item.caseDbId), `${item.childName} · ${item.caseId}`)
    })
    return [...ids.entries()]
  }, [list])

  const filtered = useMemo(() => {
    if (caseFilter === 'all') return list
    return list.filter((item) => String(item.caseDbId) === caseFilter)
  }, [list, caseFilter])

  function closeDetail() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
    setDetail(null)
    setFeedbackOpen(false)
    setFeedbackText('')
    setCommentBody('')
    setCommentType('GENERAL')
  }

  async function openDetail(item) {
    setDetailLoading(true)
    setError('')
    setMessage('')
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
    setDetail(null)
    try {
      const path =
        item.kind === 'iep' || tab === 'iep'
          ? `/api/v1/parent/reports/iep/${item.id}`
          : `/api/v1/parent/reports/monthly/${item.id}`
      const data = await apiFetch(path)
      setDetail({ ...data, kind: item.kind || (tab === 'iep' ? 'iep' : 'monthly') })
      if (data.kind === 'iep' && data.downloadPath) {
        const blobUrl = await fetchBlobUrl(data.downloadPath)
        setPdfUrl(blobUrl)
      }
    } catch (err) {
      setError(err.message || 'Could not open document')
    } finally {
      setDetailLoading(false)
    }
  }

  async function approveReport() {
    if (!detail || detail.kind !== 'monthly') return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/parent/reports/monthly/${detail.id}/approve`, { method: 'POST' })
      setMessage('Report approved. Thank you!')
      await loadHub()
      closeDetail()
    } catch (err) {
      setError(err.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function submitFeedback() {
    if (!detail || !feedbackText.trim()) return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/parent/reports/monthly/${detail.id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ message: feedbackText.trim() }),
      })
      setMessage('Feedback sent. Your case manager will review and reshare.')
      await loadHub()
      closeDetail()
    } catch (err) {
      setError(err.message || 'Could not send feedback')
    } finally {
      setActing(false)
    }
  }

  async function submitIepComment() {
    if (!detail || !commentBody.trim()) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/parent/reports/iep/${detail.id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: commentBody.trim(), comment_type: commentType }),
      })
      const refreshed = await apiFetch(`/api/v1/parent/reports/iep/${detail.id}`)
      setDetail(refreshed)
      setCommentBody('')
      setMessage('Comment added.')
    } catch (err) {
      setError(err.message || 'Could not add comment')
    } finally {
      setActing(false)
    }
  }

  async function acknowledgeIep() {
    if (!detail) return
    setActing(true)
    try {
      await apiFetch(`/api/v1/parent/reports/iep/${detail.id}/acknowledge`, { method: 'POST' })
      setMessage('IEP acknowledged.')
      await loadHub()
      closeDetail()
    } catch (err) {
      setError(err.message || 'Acknowledge failed')
    } finally {
      setActing(false)
    }
  }

  const canApproveMonthly =
    detail?.kind === 'monthly' &&
    (detail.parentReviewStatus === 'PENDING' || detail.status === 'pending_review')

  return (
    <div className="parent-reports">
      {error ? (
        <p role="alert" style={{ color: '#b91c1c', marginBottom: 12 }}>
          {error}
        </p>
      ) : null}
      {message ? (
        <p style={{ padding: '8px 12px', background: '#ecfdf5', borderRadius: 8, color: '#047857', marginBottom: 12 }}>
          {message}
        </p>
      ) : null}

      <div
        className="parent-reports__tabs"
        role="tablist"
        aria-label="Report type"
        style={{ display: 'flex', gap: 8, marginBottom: 16 }}
      >
        {[
          { id: 'monthly', label: 'Monthly reports' },
          { id: 'iep', label: 'IEP plans' },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            className={tab === t.id ? 'admin-btn admin-btn--primary' : 'admin-btn admin-btn--secondary'}
            onClick={() => {
              setTab(t.id)
              closeDetail()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {caseOptions.length > 1 ? (
        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ fontSize: 13, color: '#6b7280' }}>Filter by child</span>
          <select
            value={caseFilter}
            onChange={(e) => setCaseFilter(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4, padding: 8 }}
          >
            <option value="all">All children</option>
            {caseOptions.map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <section className="card">
        <div className="card-head">
          <h3>{tab === 'iep' ? 'IEP plans' : 'Monthly reports'}</h3>
        </div>
        {loading ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>Loading…</p>
        ) : filtered.length === 0 ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>
            {tab === 'iep' ? 'No IEP documents shared yet.' : 'No reports shared for your review yet.'}
          </p>
        ) : (
          <ul className="log-list">
            {filtered.map((item) => (
              <li key={`${item.kind || tab}-${item.id}`}>
                <button
                  type="button"
                  onClick={() => openDetail(item)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    padding: 0,
                    cursor: 'pointer',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    gap: 12,
                  }}
                >
                  <div>
                    <p style={{ margin: 0, fontWeight: 600 }}>
                      {item.childName} · {item.label || item.month}
                    </p>
                    <span style={{ fontSize: 13, color: '#6b7280' }}>{item.caseId}</span>
                  </div>
                  <StatusChip status={item.status} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {detail || detailLoading ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Report detail"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,0.45)',
            zIndex: 60,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div
            style={{
              marginTop: 'auto',
              maxHeight: '92vh',
              background: '#fff',
              borderTopLeftRadius: 16,
              borderTopRightRadius: 16,
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '12px 16px',
                borderBottom: '1px solid #e5e7eb',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>
                  {detail?.month || detail?.fileName || 'Document'}
                </h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7280' }}>
                  {detail?.childName} · {detail?.caseId}
                </p>
              </div>
              <button type="button" onClick={closeDetail} aria-label="Close">
                ✕
              </button>
            </div>

            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
              {detailLoading ? (
                <p>Loading document…</p>
              ) : detail?.kind === 'monthly' ? (
                <>
                  <ReportHtmlView html={detail.bodyHtml || detail.summary} />
                  {detail.planNextMonth ? (
                    <div className="report-plan-block" style={{ marginTop: 16 }}>
                      <strong>Plan for next month</strong>
                      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{detail.planNextMonth}</p>
                    </div>
                  ) : null}
                </>
              ) : pdfUrl ? (
                <iframe
                  title={detail.fileName || 'IEP document'}
                  src={pdfUrl}
                  style={{ width: '100%', minHeight: '70vh', border: '1px solid #e5e7eb', borderRadius: 8 }}
                />
              ) : (
                <p>Preview not available.</p>
              )}

              {detail?.comments?.length > 0 ? (
                <section style={{ marginTop: 24 }}>
                  <h3 style={{ fontSize: 15 }}>Comments & suggestions</h3>
                  <ul className="log-list">
                    {detail.comments.map((c) => (
                      <li key={c.id}>
                        <p style={{ margin: 0, fontWeight: 500 }}>{c.authorName}</p>
                        <span style={{ fontSize: 12, color: '#6b7280' }}>
                          {c.commentType.replace(/_/g, ' ')} ·{' '}
                          {c.createdAt ? new Date(c.createdAt).toLocaleString() : ''}
                        </span>
                        <p style={{ marginTop: 4 }}>{c.body}</p>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}

              {detail?.kind === 'iep' ? (
                <section style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Add a comment</h3>
                  <select
                    value={commentType}
                    onChange={(e) => setCommentType(e.target.value)}
                    style={{ width: '100%', marginBottom: 8, padding: 8 }}
                  >
                    <option value="GENERAL">General comment</option>
                    <option value="GOAL_SUGGESTION">Suggest a goal</option>
                    <option value="CHANGE_REQUEST">Request a change</option>
                  </select>
                  <textarea
                    value={commentBody}
                    onChange={(e) => setCommentBody(e.target.value)}
                    rows={3}
                    placeholder="Your feedback for the care team"
                    style={{ width: '100%', padding: 8 }}
                  />
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary"
                    disabled={acting || !commentBody.trim()}
                    onClick={submitIepComment}
                    style={{ marginTop: 8 }}
                  >
                    Post comment
                  </button>
                </section>
              ) : null}

              {feedbackOpen && detail?.kind === 'monthly' ? (
                <section style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Suggest changes</h3>
                  <textarea
                    value={feedbackText}
                    onChange={(e) => setFeedbackText(e.target.value)}
                    rows={4}
                    placeholder="Describe what should be updated in this report"
                    style={{ width: '100%', padding: 8 }}
                  />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button
                      type="button"
                      className="admin-btn admin-btn--primary"
                      disabled={acting || !feedbackText.trim()}
                      onClick={submitFeedback}
                    >
                      Send feedback
                    </button>
                    <button type="button" className="admin-btn admin-btn--ghost" onClick={() => setFeedbackOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </section>
              ) : null}
            </div>

            {detail && !detailLoading ? (
              <div
                style={{
                  padding: 12,
                  borderTop: '1px solid #e5e7eb',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 8,
                }}
              >
                {detail.kind === 'monthly' && canApproveMonthly ? (
                  <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={approveReport}>
                    Approve
                  </button>
                ) : null}
                {detail.kind === 'monthly' && detail.downloadPath ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary"
                    disabled={acting}
                    onClick={() => apiDownload(detail.downloadPath, `report_${detail.month || detail.id}.pdf`)}
                  >
                    Download PDF
                  </button>
                ) : null}
                {detail.kind === 'monthly' && canApproveMonthly ? (
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary"
                    disabled={acting}
                    onClick={() => setFeedbackOpen(true)}
                  >
                    Suggest changes
                  </button>
                ) : null}
                {detail.kind === 'iep' && detail.status === 'pending' ? (
                  <button type="button" className="admin-btn admin-btn--primary" disabled={acting} onClick={acknowledgeIep}>
                    Acknowledge IEP
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}