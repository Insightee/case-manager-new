import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiDownload, apiFetch } from '../../../lib/apiClient.js'
import { useAuth } from '../../../context/AuthContext.jsx'
import {
  TIME_PERIOD_FILTERS,
  REPORT_TYPE_FILTERS,
  buildDocumentPrompts,
  canDeleteDocument,
  groupDriveItems,
  matchesReportType,
  matchesTimePeriod,
  normalizeDriveDoc,
} from '../../../lib/caseDocumentDrive.js'
import { useCaseDocumentMutations, useCaseDocumentsList } from '../../../hooks/useCaseDocuments.js'
import { CaseDocumentsPanel } from '../../documents/CaseDocumentsPanel.jsx'
import { CaseDocumentModal } from '../../documents/CaseDocumentModal.jsx'
import '../../../styles/case-document-drive.css'

const SECTION_EMPTY = {
  reports: 'Monthly and progress reports you create will appear here.',
  evidence: 'Upload session photos, PDFs, or notes from visits.',
  links: 'Google Docs and Drive links you add will appear here with the URL.',
}

function matchesSearch(item, query) {
  if (!query) return true
  const hay = [item.title, item.subtitle, item.meta, item.statusText, item.externalUrl]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return hay.includes(query)
}

export function CaseDocumentDriveView({
  caseId,
  variant = 'therapist',
  childName = 'Client',
  caseCode = '',
  monthlyReportsPath,
}) {
  const { user, can } = useAuth()
  const navigate = useNavigate()
  const canCreate = can('case_document.create')
  const [search, setSearch] = useState('')
  const [timePeriod, setTimePeriod] = useState('all')
  const [reportType, setReportType] = useState('all')
  const [selectedId, setSelectedId] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createCategory, setCreateCategory] = useState('SESSION_EVIDENCE')
  const [createSourceType, setCreateSourceType] = useState('UPLOAD')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busyId, setBusyId] = useState(null)

  const { data: list = [], isLoading, refetch } = useCaseDocumentsList(caseId, {})
  const { create, remove } = useCaseDocumentMutations(caseId)

  const { data: qualitySummary } = useQuery({
    queryKey: ['case-quality-summary', caseId],
    queryFn: () => apiFetch(`/api/v1/cases/${caseId}/clinical-quality-summary`),
    enabled: Boolean(caseId),
    staleTime: 60_000,
  })

  const prompts = useMemo(
    () => (variant === 'therapist' ? buildDocumentPrompts({ caseId, qualitySummary, childName }) : []),
    [caseId, qualitySummary, childName, variant],
  )

  const normalizedDocs = useMemo(() => list.map(normalizeDriveDoc), [list])

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase()
    const merged = [...prompts, ...normalizedDocs]
    return merged.filter((item) => {
      if (!matchesTimePeriod(item, timePeriod)) return false
      if (!matchesReportType(item, reportType)) return false
      return matchesSearch(item, q)
    })
  }, [prompts, normalizedDocs, search, timePeriod, reportType])

  const sections = useMemo(() => groupDriveItems(filteredItems), [filteredItems])

  async function handleDownload(doc, event) {
    event?.stopPropagation()
    if (!doc?.id) return
    setError('')
    setBusyId(doc.id)
    try {
      if (doc.current_version?.source_type === 'EXTERNAL_LINK') {
        const url = doc.current_version?.external_url
        if (!url) throw new Error('No link available')
        window.open(url, '_blank', 'noopener,noreferrer')
        return
      }
      const name = doc.current_version?.file_name || `${doc.title || 'document'}.pdf`
      await apiDownload(`/api/v1/documents/${doc.id}/download`, name)
    } catch (err) {
      setError(err.message || 'Could not download this file')
    } finally {
      setBusyId(null)
    }
  }

  async function handleDelete(doc, event) {
    event?.stopPropagation()
    if (!canDeleteDocument(doc, user?.id)) return
    const ok = window.confirm(`Remove “${doc.title}”? This cannot be undone.`)
    if (!ok) return
    setError('')
    setBusyId(doc.id)
    try {
      await remove.mutateAsync(doc.id)
      setMessage('Document removed.')
      if (selectedId === doc.id) setSelectedId(null)
      void refetch()
    } catch (err) {
      setError(err.message || 'Could not remove this file')
    } finally {
      setBusyId(null)
    }
  }

  function openUpload(category = 'SESSION_EVIDENCE', sourceType = 'UPLOAD') {
    setCreateCategory(category)
    setCreateSourceType(sourceType)
    setCreateOpen(true)
  }

  function handlePromptAction(prompt, event) {
    event?.stopPropagation()
    if (prompt.action?.intent === 'upload-evidence' || prompt.secondaryAction?.intent === 'upload-evidence') {
      openUpload('SESSION_EVIDENCE')
      return
    }
    if (prompt.action?.to) {
      navigate(prompt.action.to)
    }
  }

  async function handleCreate(payload) {
    const doc = await create.mutateAsync(payload)
    setMessage('Asset saved to this case.')
    setCreateOpen(false)
    setSelectedId(doc.id)
    void refetch()
    return doc
  }

  return (
    <div className="cdd">
      <header className="cdd__header">
        <div>
          <h2 className="clinical-section-heading">Documents</h2>
          <p className="clinical-section-subtitle">
            Reports, session evidence, and uploads for {childName}
            {caseCode ? ` (${caseCode})` : ''}.
          </p>
        </div>
        {canCreate ? (
          <div className="cdd__header-actions">
            <button type="button" className="cdd__btn cdd__btn--ghost" onClick={() => openUpload('OTHER', 'EXTERNAL_LINK')}>
              <span className="material-symbols-outlined" aria-hidden="true">add_link</span>
              Add link
            </button>
            <button type="button" className="cdd__btn cdd__btn--primary" onClick={() => openUpload('SESSION_EVIDENCE')}>
              <span className="material-symbols-outlined" aria-hidden="true">upload</span>
              Upload
            </button>
          </div>
        ) : null}
      </header>

      <div className="cdd__toolbar">
        <label className="cdd__search">
          <span className="material-symbols-outlined" aria-hidden="true">search</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, type, or month…"
            aria-label="Search documents"
          />
        </label>
        <select
          className="cdd__select"
          value={timePeriod}
          onChange={(e) => setTimePeriod(e.target.value)}
          aria-label="Filter by time period"
        >
          {TIME_PERIOD_FILTERS.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
        <select
          className="cdd__select"
          value={reportType}
          onChange={(e) => setReportType(e.target.value)}
          aria-label="Filter by report type"
        >
          {REPORT_TYPE_FILTERS.map((t) => (
            <option key={t.id} value={t.id}>{t.label}</option>
          ))}
        </select>
      </div>

      {monthlyReportsPath ? (
        <p className="cdd__hint">
          Rich-text monthly reports live in{' '}
          <Link to={monthlyReportsPath}>Reports →</Link>
        </p>
      ) : null}

      {error ? <p className="cdd__alert cdd__alert--error" role="alert">{error}</p> : null}
      {message ? <p className="cdd__alert cdd__alert--ok" role="status">{message}</p> : null}

      {isLoading ? (
        <p className="cdd__loading">Loading documents…</p>
      ) : (
        sections.map((section) => (
          <section key={section.id} className="cdd__section-card" aria-labelledby={`cdd-section-${section.id}`}>
            <div className="cdd__section-head">
              <h3 id={`cdd-section-${section.id}`} className="cdd__section-title">{section.title}</h3>
              <span className="cdd__section-count">{section.items.length}</span>
            </div>
            {section.items.length === 0 ? (
              <p className="cdd__section-empty">{SECTION_EMPTY[section.id]}</p>
            ) : (
            <ul className="cdd__list">
              {section.items.map((item) => (
                <li key={item.id}>
                  {item.kind === 'prompt' ? (
                    <div className="cdd__row cdd__row--prompt">
                      <div className="cdd__row-icon cdd__row-icon--prompt" aria-hidden="true">
                        <span className="material-symbols-outlined">lightbulb</span>
                      </div>
                      <div className="cdd__row-body">
                        <p className="cdd__row-title">{item.title}</p>
                        <p className="cdd__row-meta">{item.subtitle}</p>
                      </div>
                      <span className={`cdd__status cdd__status--${item.status === 'ATTENTION' ? 'warn' : 'draft'}`}>
                        {item.statusLabel}
                      </span>
                      <div className="cdd__row-actions">
                        {item.secondaryAction ? (
                          <button
                            type="button"
                            className="cdd__icon-btn"
                            onClick={(e) => handlePromptAction({ ...item, action: item.secondaryAction }, e)}
                          >
                            Upload
                          </button>
                        ) : null}
                        {item.action ? (
                          <button
                            type="button"
                            className="cdd__btn cdd__btn--small"
                            onClick={(e) => handlePromptAction(item, e)}
                          >
                            {item.action.label}
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className={`cdd__row${item.fileKind === 'link' ? ' cdd__row--link' : ''}`}
                      onClick={() => setSelectedId(item.id)}
                    >
                      <div className={`cdd__row-icon cdd__row-icon--${item.fileKind}`} aria-hidden="true">
                        <span className="material-symbols-outlined">{item.icon}</span>
                      </div>
                      <div className="cdd__row-body">
                        <p className="cdd__row-title">{item.title}</p>
                        <p className="cdd__row-meta">{item.meta}</p>
                        {item.fileKind === 'link' && item.externalUrl ? (
                          <p className="cdd__row-link">{item.externalUrl}</p>
                        ) : null}
                      </div>
                      <span className={`cdd__status cdd__status--${item.statusTone}`}>{item.statusText}</span>
                      <div className="cdd__row-actions">
                        <button
                          type="button"
                          className="cdd__icon-btn"
                          title={item.fileKind === 'link' ? 'Open link' : 'Download'}
                          aria-label={item.fileKind === 'link' ? `Open ${item.title}` : `Download ${item.title}`}
                          disabled={busyId === item.id}
                          onClick={(e) => handleDownload(item, e)}
                        >
                          <span className="material-symbols-outlined" aria-hidden="true">
                            {item.fileKind === 'link' ? 'open_in_new' : 'download'}
                          </span>
                        </button>
                        {canDeleteDocument(item, user?.id) ? (
                          <button
                            type="button"
                            className="cdd__icon-btn cdd__icon-btn--danger"
                            title="Remove"
                            aria-label={`Remove ${item.title}`}
                            disabled={busyId === item.id}
                            onClick={(e) => handleDelete(item, e)}
                          >
                            <span className="material-symbols-outlined" aria-hidden="true">delete</span>
                          </button>
                        ) : null}
                        <span className="cdd__open-hint" aria-hidden="true">
                          <span className="material-symbols-outlined">chevron_right</span>
                        </span>
                      </div>
                    </button>
                  )}
                </li>
              ))}
            </ul>
            )}
          </section>
        ))
      )}

      <CaseDocumentModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSave={handleCreate}
        showShareOptions={variant === 'therapist'}
        defaultCategory={createCategory}
        defaultSourceType={createSourceType}
      />

      <CaseDocumentsPanel
        caseId={caseId}
        variant={variant}
        monthlyReportsPath={monthlyReportsPath}
        presentation="embedded"
        externalSelectedId={selectedId}
        externalCreateOpen={false}
        onExternalClose={() => setSelectedId(null)}
      />
    </div>
  )
}
