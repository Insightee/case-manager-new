import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiDownload, apiFetch, apiFetchBlob } from '../../lib/apiClient.js'
import {
  CASE_DOCUMENT_CATEGORIES,
  categoryLabel,
  statusLabel,
  statusTone,
  visibilityLabel,
  workflowActionLabel,
} from '../../lib/caseDocumentCategories.js'
import { GOOGLE_LINK_WARNING } from '../../lib/googleLinkValidation.js'
import { patchCaseDocumentDetail } from '../../lib/caseDocumentCache.js'
import { formatDisplayDate } from '../../lib/datetime.js'
import {
  useCaseDocumentDetail,
  useCaseDocumentMutations,
  useCaseDocumentsList,
} from '../../hooks/useCaseDocuments.js'
import { CaseDocumentComments } from './CaseDocumentComments.jsx'
import { CaseDocumentModal } from './CaseDocumentModal.jsx'
import './case-documents.css'

function StatusChip({ status }) {
  const tone = statusTone(status)
  return <span className={`case-docs__chip case-docs__chip--${tone}`}>{statusLabel(status)}</span>
}

function formatReportMonth(reportMonth) {
  if (!reportMonth) return ''
  const match = String(reportMonth).match(/^(\d{4})-(\d{2})/)
  if (match) return `${match[2]}-${match[1]}`
  return formatDisplayDate(reportMonth) || reportMonth
}

const WORKFLOW_UI = ['submit', 'approve', 'request_changes', 'publish_client', 'archive']
const VISIBILITY_OPTIONS = ['INTERNAL', 'CARE_TEAM', 'CLIENT']

function normalizeVisibility(value) {
  if (value === 'CLIENT_VISIBLE') return 'CLIENT'
  if (value === 'CLIENT_VISIBLE_AFTER_APPROVAL') return 'CARE_TEAM'
  if (value === 'INTERNAL_ONLY') return 'INTERNAL'
  return value || 'INTERNAL'
}

export function CaseDocumentsPanel({ caseId, variant = 'therapist', monthlyReportsPath }) {
  const { can } = useAuth()
  const canCreate = can('case_document.create')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [selectedId, setSelectedId] = useState(null)
  const [detail, setDetail] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editDoc, setEditDoc] = useState(null)
  const [workflowComment, setWorkflowComment] = useState('')
  const [visibilityTarget, setVisibilityTarget] = useState('INTERNAL')
  const [visibilityReason, setVisibilityReason] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [commentLoadWarning, setCommentLoadWarning] = useState('')
  const [acting, setActing] = useState(false)
  const [drawerExpanded, setDrawerExpanded] = useState(false)
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null)
  const [previewError, setPreviewError] = useState('')

  const filters = useMemo(
    () => ({
      ...(categoryFilter ? { category: categoryFilter } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
    }),
    [categoryFilter, statusFilter],
  )

  const { data: list = [], isLoading, refetch } = useCaseDocumentsList(caseId, filters)
  const { data: queryDetail } = useCaseDocumentDetail(selectedId, { enabled: !!selectedId })
  const { create, patch, workflow } = useCaseDocumentMutations(caseId)

  const btnPrimary = variant === 'admin' ? 'admin-btn admin-btn--primary' : 'ic-btn ic-btn--primary'
  const btnGhost = variant === 'admin' ? 'admin-btn admin-btn--ghost' : 'ic-btn ic-btn--ghost'
  const btnSecondary = variant === 'admin' ? 'admin-btn admin-btn--secondary' : 'ic-btn ic-btn--ghost'

  const loadDetail = useCallback(async (documentId) => {
    setDetailLoading(true)
    setError('')
    setCommentLoadWarning('')
    try {
      const doc = await apiFetch(`/api/v1/documents/${documentId}`)
      let comments = []
      try {
        comments = await apiFetch(`/api/v1/documents/${documentId}/comments`)
      } catch (commentErr) {
        setCommentLoadWarning(commentErr.message || 'Could not load comments')
      }
      setDetail({ ...doc, comments })
      patchCaseDocumentDetail(doc)
    } catch (err) {
      setError(err.message || 'Could not load document')
      setDetail(null)
    } finally {
      setDetailLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedId) loadDetail(selectedId)
    else setDetail(null)
  }, [selectedId, loadDetail])

  useEffect(() => {
    if (queryDetail && selectedId === queryDetail.id) {
      setDetail((d) => (d ? { ...d, ...queryDetail } : { ...queryDetail, comments: d?.comments }))
    }
  }, [queryDetail, selectedId])

  useEffect(() => {
    if (detail?.visibility) {
      setVisibilityTarget(normalizeVisibility(detail.visibility))
    }
    setVisibilityReason('')
  }, [detail?.id, detail?.visibility])

  useEffect(() => {
    let objectUrl = null
    setPreviewError('')
    if (!detail?.id || detail.current_version?.source_type === 'EXTERNAL_LINK') {
      setPdfPreviewUrl(null)
      return undefined
    }
    const mime = detail.current_version?.mime_type || ''
    const name = detail.current_version?.file_name || ''
    const isPdf = mime.includes('pdf') || name.toLowerCase().endsWith('.pdf')
    if (!isPdf) {
      setPdfPreviewUrl(null)
      return undefined
    }
    let cancelled = false
    apiFetchBlob(`/api/v1/documents/${detail.id}/download`)
      .then((blob) => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setPdfPreviewUrl(objectUrl)
      })
      .catch((err) => {
        if (!cancelled) setPreviewError(err.message || 'Preview unavailable')
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [detail?.id, detail?.current_version?.mime_type, detail?.current_version?.file_name, detail?.current_version?.source_type])

  function closeDrawer() {
    setSelectedId(null)
    setDetail(null)
    setWorkflowComment('')
    setDrawerExpanded(false)
    setPdfPreviewUrl(null)
  }

  async function handleCreate(payload) {
    const doc = await create.mutateAsync(payload)
    setMessage('Document added.')
    patchCaseDocumentDetail(doc)
    void refetch()
    setSelectedId(doc.id)
    return doc
  }

  async function handleEdit(payload) {
    if (!editDoc) return
    const doc = await patch.mutateAsync({ documentId: editDoc.id, body: payload.json })
    setMessage('Document updated.')
    setDetail((d) => (d?.id === doc.id ? { ...d, ...doc } : d))
    setEditDoc(null)
    void refetch()
  }

  async function runWorkflow(action) {
    if (!detail) return
    setActing(true)
    setError('')
    setMessage('')
    try {
      const body = ['request_changes', 'archive'].includes(action) && workflowComment.trim()
        ? { comment: workflowComment.trim() }
        : {}
      const doc = await workflow.mutateAsync({ documentId: detail.id, action, body })
      setDetail((d) => ({ ...d, ...doc, comments: d?.comments }))
      setMessage(`${workflowActionLabel(action)} completed.`)
      setWorkflowComment('')
      void refetch()
    } catch (err) {
      setError(err.message || 'Action failed')
    } finally {
      setActing(false)
    }
  }

  async function updateVisibility() {
    if (!detail) return
    setActing(true)
    setError('')
    setMessage('')
    try {
      const doc = await apiFetch(`/api/v1/documents/${detail.id}/visibility`, {
        method: 'POST',
        body: JSON.stringify({ to: visibilityTarget, reason: visibilityReason.trim() }),
      })
      setDetail((d) => ({ ...d, ...doc, comments: d?.comments }))
      setMessage('Visibility updated.')
      setVisibilityReason('')
      void refetch()
    } catch (err) {
      setError(err.message || 'Visibility update failed')
    } finally {
      setActing(false)
    }
  }

  async function handleDownload() {
    if (!detail?.id) return
    setError('')
    try {
      if (detail.current_version?.source_type === 'EXTERNAL_LINK') {
        const url = detail.current_version?.external_url
        if (!url) throw new Error('No link available')
        window.open(url, '_blank', 'noopener,noreferrer')
        return
      }
      const name = detail.current_version?.file_name || `document_${detail.id}`
      await apiDownload(`/api/v1/documents/${detail.id}/download`, name)
    } catch (err) {
      setError(err.message || 'Download failed')
    }
  }

  const workflowActions = (detail?.allowed_actions || []).filter((a) => {
    if (!WORKFLOW_UI.includes(a)) return false
    if (variant === 'therapist' && a === 'submit') return false
    return true
  })

  const isWordDoc =
    detail?.current_version?.mime_type?.includes('word') ||
    /\.docx?$/i.test(detail?.current_version?.file_name || '')

  const meetingDocumentGroups = useMemo(() => {
    const groups = new Map()
    for (const doc of list) {
      if (!doc.meeting_id) continue
      const key = doc.meeting_series_id || `meeting-${doc.meeting_id}`
      const current = groups.get(key) || {
        key,
        meetingSeriesId: doc.meeting_series_id,
        meetingId: doc.meeting_id,
        meetingDate: doc.meeting_scheduled_date || doc.report_date || null,
        meetingTime: doc.meeting_scheduled_time || null,
        meetingTitle: doc.meeting_title || null,
        docs: [],
      }
      current.docs.push(doc)
      if (doc.meeting_scheduled_date && (!current.meetingDate || doc.meeting_scheduled_date > current.meetingDate)) {
        current.meetingDate = doc.meeting_scheduled_date
      }
      if (doc.meeting_scheduled_time && (!current.meetingTime || doc.meeting_scheduled_time > current.meetingTime)) {
        current.meetingTime = doc.meeting_scheduled_time
      }
      if (doc.meeting_title) current.meetingTitle = doc.meeting_title
      groups.set(key, current)
    }
    return Array.from(groups.values()).sort((a, b) => String(b.meetingDate || '').localeCompare(String(a.meetingDate || '')))
  }, [list])

  const regularDocs = useMemo(() => list.filter((doc) => !doc.meeting_id), [list])

  return (
    <div className={`case-docs case-docs--${variant}`}>
      {error ? (
        <p role="alert" style={{ color: '#b91c1c' }}>
          {error}
        </p>
      ) : null}
      {message ? (
        <p style={{ padding: '8px 12px', background: '#ecfdf5', borderRadius: 8, color: '#047857' }}>{message}</p>
      ) : null}

      <div className="case-docs__toolbar">
        <div className="case-docs__filters">
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} aria-label="Category">
            <option value="">All categories</option>
            {CASE_DOCUMENT_CATEGORIES.map((category) => (
              <option key={category.value} value={category.value}>
                {category.label}
              </option>
            ))}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status">
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="CM_REVIEW">Case manager review</option>
            <option value="CLIENT_REVIEW">With family</option>
            <option value="APPROVED">Approved</option>
          </select>
        </div>
        {canCreate ? (
          <button type="button" className={btnPrimary} onClick={() => setModalOpen(true)}>
            Add document
          </button>
        ) : null}
      </div>

      {monthlyReportsPath ? (
        <p style={{ fontSize: 13, color: '#6b7280', margin: 0 }}>
          In-app monthly report (rich text):{' '}
          <Link to={monthlyReportsPath}>Open Monthly Reports →</Link>
        </p>
      ) : null}

      {meetingDocumentGroups.length ? (
        <section className="case-docs__meeting-section">
          <h3 className="case-docs__meeting-section-title">Meeting notes &amp; files</h3>
          <div className="case-docs__meeting-section-body">
            {meetingDocumentGroups.map((group) => (
              <article key={group.key} className="case-docs__meeting-group">
                <div className="case-docs__meeting-group-head">
                  <div>
                    <p className="case-docs__meeting-group-title">
                      {group.meetingTitle || 'Meeting'}
                    </p>
                    <p className="case-docs__meeting-group-meta">
                      {group.meetingDate ? formatDisplayDate(group.meetingDate) : 'Meeting date unavailable'}
                      {group.meetingTime ? ` · ${group.meetingTime}` : ''}
                    </p>
                  </div>
                  <Link to="/admin/meetings" className="case-docs__meeting-link">
                    Open meetings
                  </Link>
                </div>
                <ul className="case-docs__meeting-doc-list">
                  {group.docs.map((doc) => (
                    <li key={doc.id} className="case-docs__meeting-doc-item">
                      <div>
                        <p className="case-docs__meeting-doc-title">{doc.title}</p>
                        <p className="case-docs__meeting-doc-meta">
                          {doc.title?.toLowerCase().startsWith('meeting notes —')
                            ? 'Shared minutes'
                            : doc.current_version?.source_type === 'UPLOAD'
                              ? 'File'
                              : 'Text note'}
                          {doc.meeting_status ? ` · ${doc.meeting_status}` : ''}
                        </p>
                      </div>
                      <button type="button" className={btnGhost} onClick={() => setSelectedId(doc.id)}>
                        Open
                      </button>
                    </li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {isLoading ? (
        <p className={variant === 'admin' ? 'admin-muted' : 'ic-case-detail__loading'}>Loading documents…</p>
      ) : regularDocs.length === 0 && meetingDocumentGroups.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No documents yet. Upload a file or add a Google link.</p>
      ) : regularDocs.length ? (
        <ul className="case-docs__list">
          {regularDocs.map((doc) => (
            <li key={doc.id}>
              <button type="button" className="case-docs__card" onClick={() => setSelectedId(doc.id)}>
                <div className="case-docs__card-head">
                  <div>
                    <p className="case-docs__card-title">{doc.title}</p>
                    <p className="case-docs__card-meta">
                      {categoryLabel(doc.category)}
                      {doc.report_month ? ` · ${formatReportMonth(doc.report_month)}` : ''}
                      {doc.current_version?.source_type === 'EXTERNAL_LINK' ? ' · Google link' : ' · Upload'}
                    </p>
                  </div>
                  <div className="case-docs__chips">
                    <StatusChip status={doc.status} />
                    <span className="case-docs__chip">{visibilityLabel(doc.visibility)}</span>
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <CaseDocumentModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleCreate}
      />
      <CaseDocumentModal
        open={!!editDoc}
        onClose={() => setEditDoc(null)}
        onSave={handleEdit}
        initial={editDoc}
        mode="edit"
      />

      {selectedId ? (
        <div className="case-docs__drawer-backdrop" role="dialog" aria-modal="true">
          <div className={`case-docs__drawer${drawerExpanded ? ' case-docs__drawer--expanded' : ''}`}>
            <div className="case-docs__drawer-head">
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>{detail?.title || 'Document'}</h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7280' }}>
                  {detail ? categoryLabel(detail.category) : ''}
                  {detail ? ` · ${statusLabel(detail.status)}` : ''}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {pdfPreviewUrl ? (
                  <button
                    type="button"
                    className={btnGhost}
                    onClick={() => setDrawerExpanded((v) => !v)}
                    aria-label={drawerExpanded ? 'Exit fullscreen preview' : 'Expand preview'}
                  >
                    {drawerExpanded ? 'Exit expand' : 'Expand'}
                  </button>
                ) : null}
                <button type="button" onClick={closeDrawer} aria-label="Close">
                  ✕
                </button>
              </div>
            </div>
            <div className="case-docs__drawer-body">
              {detailLoading ? (
                <p>Loading…</p>
              ) : detail ? (
                <>
                  {detail.current_version?.source_type === 'EXTERNAL_LINK' ? (
                    <p className="case-docs__banner">{GOOGLE_LINK_WARNING}</p>
                  ) : null}

                  {pdfPreviewUrl ? (
                    <iframe
                      title={detail.current_version?.file_name || 'Document preview'}
                      src={pdfPreviewUrl}
                      className="case-docs__preview-frame"
                    />
                  ) : isWordDoc ? (
                    <p className="case-docs__preview-hint">Word documents can be downloaded but not previewed here.</p>
                  ) : previewError ? (
                    <p className="case-docs__preview-hint">{previewError}</p>
                  ) : null}

                  <dl style={{ fontSize: 14, margin: '0 0 16px' }}>
                    <div style={{ marginBottom: 8 }}>
                      <dt style={{ color: '#6b7280', fontSize: 12 }}>Visibility</dt>
                      <dd style={{ margin: 0 }}>{visibilityLabel(detail.visibility)}</dd>
                    </div>
                    {detail.current_version?.file_name ? (
                      <div style={{ marginBottom: 8 }}>
                        <dt style={{ color: '#6b7280', fontSize: 12 }}>File</dt>
                        <dd style={{ margin: 0 }}>{detail.current_version.file_name}</dd>
                      </div>
                    ) : null}
                    {detail.current_version?.external_url ? (
                      <div>
                        <dt style={{ color: '#6b7280', fontSize: 12 }}>Link</dt>
                        <dd style={{ margin: 0, wordBreak: 'break-all' }}>
                          <a href={detail.current_version.external_url} target="_blank" rel="noreferrer">
                            Open in Google
                          </a>
                        </dd>
                      </div>
                    ) : null}
                  </dl>

                  {can('case_document.publish') ? (
                    <section style={{ marginBottom: 16, padding: 12, border: '1px solid #e5e7eb', borderRadius: 10 }}>
                      <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                        Audience ceiling
                        <select
                          value={visibilityTarget}
                          onChange={(e) => setVisibilityTarget(e.target.value)}
                          style={{ width: '100%', marginTop: 4, padding: 8 }}
                        >
                          {VISIBILITY_OPTIONS.map((value) => (
                            <option key={value} value={value}>
                              {visibilityLabel(value)}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label style={{ display: 'block', marginBottom: 8, fontSize: 13 }}>
                        Reason
                        <textarea
                          value={visibilityReason}
                          onChange={(e) => setVisibilityReason(e.target.value)}
                          rows={2}
                          style={{ width: '100%', marginTop: 4, padding: 8 }}
                        />
                      </label>
                      {detail.current_version?.source_type === 'EXTERNAL_LINK' && visibilityTarget !== 'INTERNAL' ? (
                        <p role="status" style={{ margin: '0 0 8px', color: '#92400e', fontSize: 12 }}>
                          Google links stay internal-only. Upload a file if this needs a wider audience.
                        </p>
                      ) : null}
                      <button
                        type="button"
                        className={btnSecondary}
                        disabled={
                          acting ||
                          !visibilityReason.trim() ||
                          (detail.current_version?.source_type === 'EXTERNAL_LINK' && visibilityTarget !== 'INTERNAL')
                        }
                        onClick={updateVisibility}
                      >
                        Update visibility
                      </button>
                    </section>
                  ) : null}

                  {['request_changes', 'archive'].some((a) => workflowActions.includes(a)) ? (
                    <label style={{ display: 'block', marginBottom: 12, fontSize: 13 }}>
                      Note (optional for some actions)
                      <textarea
                        value={workflowComment}
                        onChange={(e) => setWorkflowComment(e.target.value)}
                        rows={2}
                        style={{ width: '100%', marginTop: 4, padding: 8 }}
                      />
                    </label>
                  ) : null}

                  {commentLoadWarning ? (
                    <p role="status" style={{ color: '#b45309', fontSize: 13 }}>
                      {commentLoadWarning}
                    </p>
                  ) : null}

                  <CaseDocumentComments
                    documentId={detail.id}
                    detail={detail}
                    onDetailChange={setDetail}
                    canComment={detail.allowed_actions?.includes('comment')}
                  />
                </>
              ) : null}
            </div>
            {detail && !detailLoading ? (
              <div className="case-docs__drawer-foot">
                {(detail.allowed_actions || []).includes('edit') ? (
                  <button type="button" className={btnSecondary} onClick={() => setEditDoc(detail)}>
                    Edit details
                  </button>
                ) : null}
                <button type="button" className={btnSecondary} disabled={acting} onClick={handleDownload}>
                  {detail.current_version?.source_type === 'EXTERNAL_LINK' ? 'Open link' : 'Download'}
                </button>
                {workflowActions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    className={action === 'approve' || action === 'publish_client' ? btnPrimary : btnSecondary}
                    disabled={acting}
                    onClick={() => runWorkflow(action)}
                  >
                    {workflowActionLabel(action)}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}
