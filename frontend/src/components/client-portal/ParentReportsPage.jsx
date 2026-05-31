import { useCallback, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch, apiDownload, getTokens } from '../../lib/apiClient.js'
import {
  categoryLabel,
  statusLabel,
  workflowActionLabel,
} from '../../lib/caseDocumentCategories.js'
import { GOOGLE_LINK_WARNING } from '../../lib/googleLinkValidation.js'
import { useParentDocumentsList } from '../../hooks/useCaseDocuments.js'
import { CaseDocumentComments } from '../documents/CaseDocumentComments.jsx'
import { ReportHtmlView } from '../reports/ReportHtmlView.jsx'
import '../documents/case-documents.css'
import '../reports/report-editor.css'
import './parent-portal-filters.css'
import './parent-reports.css'
import { ClientPortalLayout } from './ClientPortalLayout.jsx'
import { ParentFilterBar, ParentFilterField, ParentFilterSelect, ParentPortalTabs } from './ParentFilterBar.jsx'

const API_URL = import.meta.env.VITE_API_URL || ''

const STATUS_LABELS = {
  pending_review: 'Pending your review',
  approved: 'Approved',
  changes_sent: 'Changes sent',
  pending: 'Pending acknowledgement',
  acknowledged: 'Acknowledged',
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function reportPreviewHtml(detail) {
  if (!detail) return ''
  if (detail.bodyHtml) return detail.bodyHtml
  const text = detail.summary || detail.content || ''
  if (!text) return ''
  if (/<[a-z][\s\S]*>/i.test(text)) return text
  return `<p>${escapeHtml(text)}</p>`
}

function detailTitle(detail) {
  if (!detail) return 'Document'
  if (detail.kind === 'case_document') return detail.title || 'Document'
  if (detail.kind === 'iep') return detail.title || detail.fileName || `IEP ${detail.version || ''}`.trim()
  return detail.month || detail.title || 'Monthly report'
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

function reportListLabels(item, tab) {
  if (tab === 'documents') {
    return {
      name: item.child_name || item.childName || 'Document',
      meta: [item.case_code || item.caseId, categoryLabel(item.category)].filter(Boolean).join(' · '),
      subtitle: item.title,
    }
  }
  return {
    name: item.childName || 'Report',
    meta: item.caseId || '',
    subtitle: item.label || item.month || '',
  }
}

function reportListStatus(item, tab) {
  if (tab === 'documents') {
    return item.parent_review_status === 'PENDING'
      ? 'pending_review'
      : item.parent_review_status === 'APPROVED'
        ? 'approved'
        : item.status
  }
  return item.status
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
  const typeParam = searchParams.get('type')
  const initialTab = typeParam === 'iep' ? 'iep' : typeParam === 'documents' ? 'documents' : 'monthly'
  const [tab, setTab] = useState(initialTab)
  const [hub, setHub] = useState({ monthly: [], iep: [] })
  const [parentCases, setParentCases] = useState([])
  const [caseFilter, setCaseFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [pdfUrl, setPdfUrl] = useState(null)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [commentBody, setCommentBody] = useState('')
  const [commentType, setCommentType] = useState('GENERAL')
  const [goalSuggestionText, setGoalSuggestionText] = useState('')
  const [acting, setActing] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [docFeedbackOpen, setDocFeedbackOpen] = useState(false)
  const [docFeedbackText, setDocFeedbackText] = useState('')

  const { data: parentDocs = [], isLoading: docsLoading, refetch: refetchDocs } = useParentDocumentsList({
    enabled: tab === 'documents',
  })

  const loadHub = useCallback(async () => {
    setLoading(true)
    try {
      const [data, cases] = await Promise.all([
        apiFetch('/api/v1/parent/reports/hub'),
        apiFetch('/api/v1/parent/cases').catch(() => []),
      ])
      setHub({ monthly: data.monthly || [], iep: data.iep || [] })
      setParentCases(cases || [])
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
    if (tab === 'iep') setSearchParams({ type: 'iep' }, { replace: true })
    else if (tab === 'documents') setSearchParams({ type: 'documents' }, { replace: true })
    else setSearchParams({}, { replace: true })
  }, [tab, setSearchParams])

  useEffect(() => {
    if (!detail && !detailLoading) return undefined
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKey = (e) => {
      if (e.key === 'Escape') closeDetail()
    }
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = prev
      window.removeEventListener('keydown', onKey)
    }
  }, [detail, detailLoading])

  const list =
    tab === 'iep' ? hub.iep : tab === 'documents' ? parentDocs : hub.monthly

  const caseOptions = useMemo(() => {
    const ids = new Map()
    list.forEach((item) => {
      const caseDbId = item.caseDbId ?? item.case_id
      const childName = item.childName ?? item.child_name
      const caseCode = item.caseId ?? item.case_code
      if (caseDbId) ids.set(String(caseDbId), `${childName} · ${caseCode}`)
    })
    return [...ids.entries()]
  }, [list])

  const filtered = useMemo(() => {
    if (caseFilter === 'all') return list
    return list.filter((item) => String(item.caseDbId ?? item.case_id) === caseFilter)
  }, [list, caseFilter])

  function closeDetail() {
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
    setDetail(null)
    setFeedbackOpen(false)
    setFeedbackText('')
    setCommentBody('')
    setCommentType('GENERAL')
    setDocFeedbackOpen(false)
    setDocFeedbackText('')
  }

  async function openDetail(item) {
    setDetailLoading(true)
    setError('')
    setMessage('')
    if (pdfUrl) URL.revokeObjectURL(pdfUrl)
    setPdfUrl(null)
    setDetail(null)
    try {
      if (tab === 'documents') {
        const [data, comments] = await Promise.all([
          apiFetch(`/api/v1/parent/documents/${item.id}`),
          apiFetch(`/api/v1/parent/documents/${item.id}/comments`).catch(() => []),
        ])
        setDetail({ ...data, kind: 'case_document', comments })
        return
      }
      const path =
        item.kind === 'iep' || tab === 'iep'
          ? `/api/v1/parent/reports/iep/${item.id}`
          : `/api/v1/parent/reports/monthly/${item.id}`
      const data = await apiFetch(path)
      const kind = data.kind || item.kind || (tab === 'iep' ? 'iep' : 'monthly')
      setDetail({ ...data, kind })
      if (kind === 'iep' && data.downloadPath && !data.bodyHtml) {
        const isPdf = (data.fileName || '').toLowerCase().endsWith('.pdf')
        if (isPdf) {
          const blobUrl = await fetchBlobUrl(data.downloadPath)
          setPdfUrl(blobUrl)
        }
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
    setError('')
    try {
      await apiFetch(`/api/v1/parent/reports/iep/${detail.id}/comments`, {
        method: 'POST',
        body: JSON.stringify({ body: commentBody.trim(), comment_type: commentType }),
      })
      const refreshed = await apiFetch(`/api/v1/parent/reports/iep/${detail.id}`)
      setDetail({ ...refreshed, kind: 'iep' })
      setCommentBody('')
      setMessage('Comment added.')
    } catch (err) {
      setError(err.message || 'Could not add comment')
    } finally {
      setActing(false)
    }
  }

  async function approveCaseDocument() {
    if (!detail || detail.kind !== 'case_document') return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/parent/documents/${detail.id}/approve`, { method: 'POST' })
      setMessage('Document approved. Thank you!')
      await refetchDocs()
      closeDetail()
    } catch (err) {
      setError(err.message || 'Approve failed')
    } finally {
      setActing(false)
    }
  }

  async function submitDocFeedback() {
    if (!detail || !docFeedbackText.trim()) return
    setActing(true)
    setMessage('')
    try {
      await apiFetch(`/api/v1/parent/documents/${detail.id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ message: docFeedbackText.trim() }),
      })
      setMessage('Feedback sent. Your care team will review and reshare.')
      await refetchDocs()
      closeDetail()
    } catch (err) {
      setError(err.message || 'Could not send feedback')
    } finally {
      setActing(false)
    }
  }

  async function acknowledgeIep() {
    if (!detail) return
    setActing(true)
    setError('')
    try {
      await apiFetch(`/api/v1/parent/reports/iep/${detail.id}/acknowledge`, { method: 'POST' })
      setMessage('IEP acknowledged.')
      await loadHub()
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl)
        setPdfUrl(null)
      }
      const refreshed = await apiFetch(`/api/v1/parent/reports/iep/${detail.id}`)
      setDetail({ ...refreshed, kind: 'iep' })
    } catch (err) {
      setError(err.message || 'Acknowledge failed')
    } finally {
      setActing(false)
    }
  }

  async function submitGoalSuggestion() {
    if (!detail?.caseDbId || !goalSuggestionText.trim()) return
    setActing(true)
    setError('')
    try {
      await apiFetch(`/api/v1/parent/cases/${detail.caseDbId}/iep-plan/suggestions`, {
        method: 'POST',
        body: JSON.stringify({ body: goalSuggestionText.trim() }),
      })
      setGoalSuggestionText('')
      setMessage('Goal suggestion sent to your care team.')
    } catch (err) {
      setError(err.message || 'Could not send suggestion')
    } finally {
      setActing(false)
    }
  }

  const canApproveMonthly =
    detail?.kind === 'monthly' &&
    (detail.parentReviewStatus === 'PENDING' || detail.status === 'pending_review')

  const canApproveDoc =
    detail?.kind === 'case_document' && detail.allowed_actions?.includes('parent_approve')

  const canDocFeedback =
    detail?.kind === 'case_document' && detail.allowed_actions?.includes('parent_feedback')

  return (
    <ClientPortalLayout
      title="Reports"
      subtitle="Monthly reports, IEP plans, and documents shared by your care team."
    >
    <div className="parent-reports">
      {error ? (
        <p role="alert" className="parent-reports__alert parent-reports__alert--error">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="parent-reports__alert parent-reports__alert--success">{message}</p>
      ) : null}

      {parentCases.length > 0 ? (
        <section className="parent-reports__cases" aria-label="Your children">
          <h2 style={{ fontSize: '1rem', fontWeight: 700, margin: '0 0 12px', color: '#1e293b' }}>Your children</h2>
          <div className="parent-reports__case-grid">
            {parentCases.map((c) => (
              <Link
                key={c.id}
                to={`/parent/cases/${c.id}?tab=overview`}
                className="parent-reports__case-card"
              >
                <p className="parent-reports__case-code">{c.caseId}</p>
                <p className="parent-reports__case-name">{c.childName}</p>
                <p className="parent-reports__case-meta">{c.serviceType}</p>
                <span className="parent-reports__case-cta">View profile & reports →</span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <ParentPortalTabs
        ariaLabel="Report type"
        tabs={[
          { id: 'monthly', label: 'Monthly reports' },
          { id: 'iep', label: 'IEP plans' },
          { id: 'documents', label: 'Documents' },
        ]}
        value={tab}
        onChange={(id) => {
          setTab(id)
          closeDetail()
        }}
      />

      {caseOptions.length > 1 ? (
        <ParentFilterBar ariaLabel="Filter reports" gridClass="">
          <ParentFilterField label="Child">
            <ParentFilterSelect value={caseFilter} onChange={(e) => setCaseFilter(e.target.value)}>
              <option value="all">All children</option>
              {caseOptions.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </ParentFilterSelect>
          </ParentFilterField>
        </ParentFilterBar>
      ) : null}

      <section className="card">
        <div className="card-head">
          <h3>
            {tab === 'iep' ? 'IEP plans' : tab === 'documents' ? 'Shared documents' : 'Monthly reports'}
          </h3>
        </div>
        {(tab === 'documents' ? docsLoading : loading) ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>Loading…</p>
        ) : filtered.length === 0 ? (
          <p style={{ padding: 16, color: '#9ca3af' }}>
            {tab === 'iep'
              ? 'No IEP documents shared yet.'
              : tab === 'documents'
                ? 'No documents shared with your family yet.'
                : 'No reports shared for your review yet.'}
          </p>
        ) : (
          <ul className="log-list parent-reports__list">
            {filtered.map((item) => {
              const labels = reportListLabels(item, tab)
              return (
              <li key={`${item.kind || tab}-${item.id}`}>
                <button type="button" className="parent-reports__list-btn" onClick={() => openDetail(item)}>
                  <div className="parent-reports__list-main">
                    <p className="parent-reports__list-name">{labels.name}</p>
                    {labels.meta ? <p className="parent-reports__list-meta">{labels.meta}</p> : null}
                    {labels.subtitle ? (
                      <p className="parent-reports__list-sub">{labels.subtitle}</p>
                    ) : null}
                  </div>
                  <div className="parent-reports__list-foot">
                    <StatusChip status={reportListStatus(item, tab)} />
                  </div>
                </button>
              </li>
              )
            })}
          </ul>
        )}
      </section>

      {(detail || detailLoading) && typeof document !== 'undefined'
        ? createPortal(
            <div className="parent-reports__modal-root" role="dialog" aria-modal="true" aria-label="Report detail">
              <button type="button" className="parent-reports__modal-backdrop" aria-label="Close" onClick={closeDetail} />
              <div className="parent-reports__modal-panel">
                <div className="parent-reports__modal-head">
                  <div>
                    <h2 className="parent-reports__modal-title">{detailTitle(detail)}</h2>
                    <p className="parent-reports__modal-meta">
                      {detail?.kind === 'case_document'
                        ? `${categoryLabel(detail.category)} · ${statusLabel(detail.status)}`
                        : `${detail?.childName || ''}${detail?.caseId ? ` · ${detail.caseId}` : ''}`}
                    </p>
                  </div>
                  <button type="button" className="parent-reports__modal-close" onClick={closeDetail} aria-label="Close">
                    ×
                  </button>
                </div>

                <div className="parent-reports__modal-body">
                  {detailLoading ? (
                    <p style={{ color: '#64748b' }}>Loading document…</p>
                  ) : detail?.kind === 'case_document' ? (
                <>
                  {detail.current_version?.source_type === 'EXTERNAL_LINK' ? (
                    <p className="case-docs__banner">{GOOGLE_LINK_WARNING}</p>
                  ) : null}
                  {detail.current_version?.external_url ? (
                    <p style={{ marginBottom: 12 }}>
                      <a
                        href={detail.current_version.external_url}
                        target="_blank"
                        rel="noreferrer"
                        className="admin-btn admin-btn--secondary"
                      >
                        Open in Google
                      </a>
                    </p>
                  ) : null}
                  {detail.current_version?.file_name ? (
                    <p style={{ fontSize: 14, color: '#4b5563' }}>File: {detail.current_version.file_name}</p>
                  ) : null}
                  <CaseDocumentComments
                    documentId={detail.id}
                    detail={detail}
                    onDetailChange={setDetail}
                    canComment={detail.allowed_actions?.includes('comment')}
                    commentPathPrefix="/api/v1/parent/documents"
                  />
                  {docFeedbackOpen ? (
                    <section style={{ marginTop: 16 }}>
                      <h3 style={{ fontSize: 15 }}>Request changes</h3>
                      <textarea
                        value={docFeedbackText}
                        onChange={(e) => setDocFeedbackText(e.target.value)}
                        rows={4}
                        placeholder="Describe what should be updated"
                        style={{ width: '100%', padding: 8 }}
                      />
                      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                        <button
                          type="button"
                          className="admin-btn admin-btn--primary"
                          disabled={acting || !docFeedbackText.trim()}
                          onClick={submitDocFeedback}
                        >
                          Send feedback
                        </button>
                        <button
                          type="button"
                          className="admin-btn admin-btn--ghost"
                          onClick={() => setDocFeedbackOpen(false)}
                        >
                          Cancel
                        </button>
                      </div>
                    </section>
                  ) : null}
                </>
              ) : detail?.kind === 'monthly' ? (
                <>
                  <ReportHtmlView html={reportPreviewHtml(detail)} />
                  {detail.planNextMonth ? (
                    <div className="report-plan-block" style={{ marginTop: 16 }}>
                      <strong>Plan for next month</strong>
                      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{detail.planNextMonth}</p>
                    </div>
                  ) : null}
                </>
              ) : detail?.kind === 'iep' && detail.bodyHtml ? (
                <div className="parent-reports__iep-doc">
                  <ReportHtmlView html={detail.bodyHtml} />
                </div>
              ) : pdfUrl ? (
                <iframe
                  title={detail.fileName || 'IEP document'}
                  src={pdfUrl}
                  style={{ width: '100%', minHeight: '60vh', border: '1px solid #e5e7eb', borderRadius: 8 }}
                />
              ) : (
                <p style={{ color: '#64748b' }}>Preview not available. Try downloading the document.</p>
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

              {detail?.kind === 'iep' && detail.canSuggestGoals ? (
                <section className="parent-reports__goal-suggest" style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15 }}>Suggest goal changes</h3>
                  <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '0 0 8px' }}>
                    Share ideas for IEP goals. Your case manager will review suggestions.
                  </p>
                  <textarea
                    value={goalSuggestionText}
                    onChange={(e) => setGoalSuggestionText(e.target.value)}
                    rows={3}
                    placeholder="Describe a goal or change you would like considered"
                    style={{ width: '100%', padding: 8, borderRadius: 8, border: '1px solid #e2e8f0' }}
                  />
                  <button
                    type="button"
                    className="admin-btn admin-btn--secondary"
                    style={{ marginTop: 8 }}
                    disabled={acting || !goalSuggestionText.trim()}
                    onClick={submitGoalSuggestion}
                  >
                    Send goal suggestion
                  </button>
                </section>
              ) : null}

              {detail?.kind === 'iep' ? (
                <section className="parent-reports__comment-form" style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 15, margin: '0 0 10px' }}>Add a comment</h3>
                  <label htmlFor="iep-comment-type">Comment type</label>
                  <select
                    id="iep-comment-type"
                    value={commentType}
                    onChange={(e) => setCommentType(e.target.value)}
                    style={{ marginBottom: 10 }}
                  >
                    <option value="GENERAL">General comment</option>
                    <option value="GOAL_SUGGESTION">Suggest a goal</option>
                    <option value="CHANGE_REQUEST">Request a change</option>
                  </select>
                  <label htmlFor="iep-comment-body">Your message</label>
                  <textarea
                    id="iep-comment-body"
                    value={commentBody}
                    onChange={(e) => setCommentBody(e.target.value)}
                    rows={3}
                    placeholder="Your feedback for the care team"
                  />
                  <button
                    type="button"
                    className="parent-reports__btn parent-reports__btn--secondary"
                    disabled={acting || !commentBody.trim()}
                    onClick={submitIepComment}
                    style={{ marginTop: 10, width: '100%' }}
                  >
                    {acting ? 'Posting…' : 'Post comment'}
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
                  <div className="parent-reports__modal-foot">
                    {detail.kind === 'monthly' && canApproveMonthly ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--primary"
                        disabled={acting}
                        onClick={approveReport}
                      >
                        Approve
                      </button>
                    ) : null}
                    {detail.kind === 'monthly' && detail.downloadPath ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--secondary"
                        disabled={acting}
                        onClick={() => apiDownload(detail.downloadPath, `report_${detail.month || detail.id}.pdf`)}
                      >
                        Download PDF
                      </button>
                    ) : null}
                    {detail.kind === 'monthly' && canApproveMonthly ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--secondary"
                        disabled={acting}
                        onClick={() => setFeedbackOpen(true)}
                      >
                        Suggest changes
                      </button>
                    ) : null}
                    {detail.kind === 'iep' && detail.downloadPath ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--secondary"
                        disabled={acting}
                        onClick={() =>
                          apiDownload(
                            detail.downloadPath,
                            `${(detail.title || detail.fileName || 'iep').replace(/\s+/g, '_')}.pdf`,
                          )
                        }
                      >
                        Download PDF
                      </button>
                    ) : null}
                    {detail.kind === 'iep' && detail.canAcknowledge ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--primary"
                        disabled={acting}
                        onClick={acknowledgeIep}
                      >
                        {acting ? 'Saving…' : 'Acknowledge IEP'}
                      </button>
                    ) : null}
                    {detail.kind === 'case_document' && canApproveDoc ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--primary"
                        disabled={acting}
                        onClick={approveCaseDocument}
                      >
                        {workflowActionLabel('parent_approve')}
                      </button>
                    ) : null}
                    {detail.kind === 'case_document' && detail.current_version?.source_type === 'UPLOAD' ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--secondary"
                        disabled={acting}
                        onClick={() =>
                          apiDownload(
                            `/api/v1/documents/${detail.id}/download`,
                            detail.current_version?.file_name || `document_${detail.id}`,
                          )
                        }
                      >
                        Download
                      </button>
                    ) : null}
                    {detail.kind === 'case_document' && canDocFeedback && !docFeedbackOpen ? (
                      <button
                        type="button"
                        className="parent-reports__btn parent-reports__btn--secondary"
                        disabled={acting}
                        onClick={() => setDocFeedbackOpen(true)}
                      >
                        {workflowActionLabel('parent_feedback')}
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>,
            document.body,
          )
        : null}

      <style>{`
        .parent-reports__cases { margin-bottom: 24px; }
        .parent-reports { width: 100%; min-width: 0; box-sizing: border-box; }
        .parent-reports__case-grid { display: grid; grid-template-columns: 1fr; gap: 12px; }
        @media (min-width: 600px) {
          .parent-reports__case-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (min-width: 900px) {
          .parent-reports__case-grid { grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); }
        }
        .parent-reports__case-card { display: block; padding: 14px 16px; border-radius: 14px; border: 1px solid #e2e8f0; background: #fff; text-decoration: none; color: inherit; box-shadow: 0 1px 3px rgba(0,0,0,0.04); transition: border-color 0.15s, box-shadow 0.15s; }
        .parent-reports__case-card:hover { border-color: #c7d2fe; box-shadow: 0 4px 12px rgba(99,102,241,0.12); }
        .parent-reports__case-code { font-size: 0.7rem; font-weight: 700; color: #6366f1; text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 4px; }
        .parent-reports__case-name { font-size: 1rem; font-weight: 700; color: #1e293b; margin: 0 0 4px; }
        .parent-reports__case-meta { font-size: 0.8rem; color: #64748b; margin: 0 0 8px; }
        .parent-reports__case-cta { font-size: 0.75rem; font-weight: 600; color: #4f46e5; }
      `}</style>
    </div>
    </ClientPortalLayout>
  )
}