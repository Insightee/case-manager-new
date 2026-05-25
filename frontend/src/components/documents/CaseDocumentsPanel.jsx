import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext.jsx'
import { apiDownload, apiFetch } from '../../lib/apiClient.js'
import {
  categoryLabel,
  statusLabel,
  statusTone,
  visibilityLabel,
  workflowActionLabel,
} from '../../lib/caseDocumentCategories.js'
import { GOOGLE_LINK_WARNING } from '../../lib/googleLinkValidation.js'
import { patchCaseDocumentDetail } from '../../lib/caseDocumentCache.js'
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

const WORKFLOW_UI = ['submit', 'approve', 'request_changes', 'publish_client', 'archive']

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
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [acting, setActing] = useState(false)

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
    try {
      const [doc, comments] = await Promise.all([
        apiFetch(`/api/v1/documents/${documentId}`),
        apiFetch(`/api/v1/documents/${documentId}/comments`).catch(() => []),
      ])
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

  function closeDrawer() {
    setSelectedId(null)
    setDetail(null)
    setWorkflowComment('')
  }

  async function handleCreate(payload) {
    const doc = await create.mutateAsync(payload)
    setMessage('Document added.')
    patchCaseDocumentDetail(doc)
    void refetch()
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

  async function handleDownload() {
    if (!detail?.id) return
    const info = await apiFetch(`/api/v1/documents/${detail.id}/download`)
    if (info?.type === 'external_link' && info?.url) {
      window.open(info.url, '_blank', 'noopener,noreferrer')
      return
    }
    const name = detail.current_version?.file_name || `document_${detail.id}`
    await apiDownload(`/api/v1/documents/${detail.id}/download`, name)
  }

  const workflowActions = (detail?.allowed_actions || []).filter((a) => WORKFLOW_UI.includes(a))

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
            <option value="OBSERVATION_REPORT">Observation</option>
            <option value="MONTHLY_PROGRESS_REPORT">Monthly progress</option>
            <option value="IEP_PLAN">IEP</option>
            <option value="INCIDENT_REPORT">Incident</option>
            <option value="OTHER">Other</option>
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status">
            <option value="">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="SUPERVISOR_REVIEW">Supervisor review</option>
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

      {isLoading ? (
        <p className={variant === 'admin' ? 'admin-muted' : 'ic-case-detail__loading'}>Loading documents…</p>
      ) : list.length === 0 ? (
        <p style={{ color: '#9ca3af' }}>No documents yet. Upload a file or add a Google link.</p>
      ) : (
        <ul className="case-docs__list">
          {list.map((doc) => (
            <li key={doc.id}>
              <button type="button" className="case-docs__card" onClick={() => setSelectedId(doc.id)}>
                <div className="case-docs__card-head">
                  <div>
                    <p className="case-docs__card-title">{doc.title}</p>
                    <p className="case-docs__card-meta">
                      {categoryLabel(doc.category)}
                      {doc.report_month ? ` · ${doc.report_month}` : ''}
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
      )}

      <CaseDocumentModal open={modalOpen} onClose={() => setModalOpen(false)} onSave={handleCreate} />
      <CaseDocumentModal
        open={!!editDoc}
        onClose={() => setEditDoc(null)}
        onSave={handleEdit}
        initial={editDoc}
        mode="edit"
      />

      {selectedId ? (
        <div className="case-docs__drawer-backdrop" role="dialog" aria-modal="true">
          <div className="case-docs__drawer">
            <div className="case-docs__drawer-head">
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>{detail?.title || 'Document'}</h2>
                <p style={{ margin: '4px 0 0', fontSize: 13, color: '#6b7280' }}>
                  {detail ? categoryLabel(detail.category) : ''}
                  {detail ? ` · ${statusLabel(detail.status)}` : ''}
                </p>
              </div>
              <button type="button" onClick={closeDrawer} aria-label="Close">
                ✕
              </button>
            </div>
            <div className="case-docs__drawer-body">
              {detailLoading ? (
                <p>Loading…</p>
              ) : detail ? (
                <>
                  {detail.current_version?.source_type === 'EXTERNAL_LINK' ? (
                    <p className="case-docs__banner">{GOOGLE_LINK_WARNING}</p>
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
