import { useEffect, useMemo, useRef, useState } from 'react'
import { CASE_DOCUMENT_CATEGORIES } from '../../lib/caseDocumentCategories.js'
import { GOOGLE_LINK_WARNING, validateGoogleLink } from '../../lib/googleLinkValidation.js'
import './case-documents.css'

const MAX_BYTES = 5 * 1024 * 1024
const ACCEPT =
  '.pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

const EMPTY = {
  category: 'SESSION_EVIDENCE',
  title: '',
  source_type: 'UPLOAD',
  external_url: '',
}

function auditReportDates() {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  return {
    report_month: `${now.getFullYear()}-${month}`,
    report_date: now.toISOString().slice(0, 10),
  }
}

function titleFromFileName(name) {
  if (!name) return ''
  return name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim().slice(0, 255)
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function fileIconName(file) {
  if (!file) return 'draft'
  const name = file.name.toLowerCase()
  if (name.endsWith('.pdf')) return 'picture_as_pdf'
  if (name.endsWith('.doc') || name.endsWith('.docx')) return 'description'
  return 'attach_file'
}

export function CaseDocumentModal({ open, onClose, onSave, initial, mode = 'create', showShareOptions = false }) {
  const [form, setForm] = useState(EMPTY)
  const [useLink, setUseLink] = useState(false)
  const [file, setFile] = useState(null)
  const [shareWithCm, setShareWithCm] = useState(true)
  const [shareWithParents, setShareWithParents] = useState(false)
  const [error, setError] = useState('')
  const [sizeWarning, setSizeWarning] = useState('')
  const [saving, setSaving] = useState(false)
  const [uploadedPreview, setUploadedPreview] = useState(null)
  const fileInputRef = useRef(null)

  const previewUrl = useMemo(() => {
    if (!file?.type?.startsWith('image/')) return null
    return URL.createObjectURL(file)
  }, [file])

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl)
    }
  }, [previewUrl])

  useEffect(() => {
    if (!open) return
    if (initial) {
      setForm({
        category: initial.category || 'OTHER',
        title: initial.title || '',
        source_type: initial.current_version?.source_type || 'UPLOAD',
        external_url: initial.current_version?.external_url || '',
      })
      setUseLink(initial.current_version?.source_type === 'EXTERNAL_LINK')
    } else {
      setForm(EMPTY)
      setUseLink(false)
    }
    setFile(null)
    setUploadedPreview(null)
    setShareWithCm(true)
    setShareWithParents(false)
    setError('')
    setSizeWarning('')
  }, [open, initial])

  if (!open) return null

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  function onFileChange(next) {
    setError('')
    setSizeWarning('')
    setUploadedPreview(null)
    if (!next) {
      setFile(null)
      return
    }
    if (next.size > MAX_BYTES) {
      setSizeWarning(`This file is ${formatFileSize(next.size)}. Please choose one up to 5 MB.`)
      setFile(null)
      return
    }
    setFile(next)
    if (!form.title.trim()) {
      update('title', titleFromFileName(next.name))
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    const title = form.title.trim()
    if (!title) {
      setError('Add a title so this upload is easy to find later.')
      return
    }
    if (mode === 'create') {
      if (!useLink && !file) {
        setError('Choose a file to upload or switch to a Google link.')
        return
      }
      if (useLink) {
        const check = validateGoogleLink(form.external_url)
        if (!check.ok) {
          setError(check.message)
          return
        }
      }
    }

    const audit = auditReportDates()
    setSaving(true)
    try {
      if (mode === 'edit') {
        await onSave({
          json: {
            title,
            category: form.category,
          },
        })
      } else if (useLink) {
        const check = validateGoogleLink(form.external_url)
        await onSave({
          json: {
            category: form.category,
            title,
            report_month: audit.report_month,
            report_date: audit.report_date,
            source_type: 'EXTERNAL_LINK',
            external_url: check.normalized,
            share_with_cm: showShareOptions ? shareWithCm : false,
            share_with_parents: showShareOptions ? shareWithParents : false,
          },
        })
        setUploadedPreview({ title, category: form.category, kind: 'link' })
      } else {
        const fd = new FormData()
        fd.append('category', form.category)
        fd.append('title', title)
        fd.append('report_month', audit.report_month)
        fd.append('report_date', audit.report_date)
        fd.append('source_type', 'UPLOAD')
        fd.append('file', file)
        if (showShareOptions) {
          fd.append('share_with_cm', shareWithCm ? 'true' : 'false')
          fd.append('share_with_parents', shareWithParents ? 'true' : 'false')
        }
        await onSave({ formData: fd })
        setUploadedPreview({
          title,
          category: form.category,
          kind: 'file',
          fileName: file.name,
          fileSize: file.size,
        })
      }
      onClose()
    } catch (err) {
      setError(err.message || 'Could not save document')
    } finally {
      setSaving(false)
    }
  }

  const showFileTile = file && !useLink
  const categoryLabel = CASE_DOCUMENT_CATEGORIES.find((c) => c.value === form.category)?.label || 'Document'

  return (
    <div className="case-docs-modal__backdrop" role="dialog" aria-modal="true" aria-labelledby="case-doc-modal-title">
      <form className="case-docs-modal case-docs-modal--v2 forest-light" onSubmit={handleSubmit}>
        <header className="case-docs-modal__head">
          <div>
            <h2 id="case-doc-modal-title" className="case-docs-modal__title">
              {mode === 'edit' ? 'Edit document' : 'Upload document'}
            </h2>
            <p className="case-docs-modal__subtitle">
              PDF or Word up to 5 MB. Rich-text monthly reports live in Monthly Reports.
            </p>
          </div>
          <button type="button" className="case-docs-modal__close" onClick={onClose} aria-label="Close">
            <span className="material-symbols-outlined" aria-hidden="true">close</span>
          </button>
        </header>

        <label className="case-docs-field">
          <span className="case-docs-field__label">Category</span>
          <select
            className="case-docs-field__input"
            value={form.category}
            onChange={(e) => update('category', e.target.value)}
            required
          >
            {CASE_DOCUMENT_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label className="case-docs-field">
          <span className="case-docs-field__label">Title</span>
          <input
            className="case-docs-field__input"
            value={form.title}
            onChange={(e) => update('title', e.target.value)}
            required
            maxLength={255}
            placeholder="e.g. June session photo, assessment PDF"
          />
        </label>

        {mode === 'create' ? (
          <div className="case-docs-modal__source">
            {!useLink ? (
              <>
                <button
                  type="button"
                  className={`case-docs-upload-zone${showFileTile ? ' case-docs-upload-zone--filled' : ''}`}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={ACCEPT}
                    className="case-docs-upload-zone__input"
                    onChange={(e) => onFileChange(e.target.files?.[0] || null)}
                  />
                  {showFileTile ? (
                    <article className="case-docs-upload-tile">
                      <span className="case-docs-upload-tile__icon" aria-hidden="true">
                        <span className="material-symbols-outlined">{fileIconName(file)}</span>
                      </span>
                      <div className="case-docs-upload-tile__body">
                        <strong>{file.name}</strong>
                        <span>{formatFileSize(file.size)} · Ready to upload</span>
                      </div>
                      <span className="case-docs-upload-tile__change">Change file</span>
                    </article>
                  ) : (
                    <>
                      <span className="case-docs-upload-zone__icon" aria-hidden="true">
                        <span className="material-symbols-outlined">upload_file</span>
                      </span>
                      <strong>Tap to choose a file</strong>
                      <span>PDF or Word · max 5 MB</span>
                    </>
                  )}
                </button>
                {previewUrl ? (
                  <img src={previewUrl} alt="" className="case-docs-upload-zone__thumb" />
                ) : null}
              </>
            ) : (
              <label className="case-docs-field">
                <span className="case-docs-field__label">Google Docs or Drive link</span>
                <input
                  className="case-docs-field__input"
                  type="url"
                  value={form.external_url}
                  onChange={(e) => update('external_url', e.target.value)}
                  placeholder="https://docs.google.com/document/..."
                />
              </label>
            )}

            {sizeWarning ? (
              <p className="case-docs-modal__warn" role="alert">
                {sizeWarning}
              </p>
            ) : null}

            {useLink ? (
              <p className="case-docs-modal__hint">{GOOGLE_LINK_WARNING}</p>
            ) : null}

            <button
              type="button"
              className="case-docs-source-toggle"
              onClick={() => {
                setUseLink((v) => !v)
                setError('')
                setSizeWarning('')
              }}
            >
              <span className="material-symbols-outlined" aria-hidden="true">
                {useLink ? 'upload_file' : 'link'}
              </span>
              {useLink ? 'Upload a file instead' : 'Use a Google link instead'}
            </button>
          </div>
        ) : null}

        {mode === 'create' && showShareOptions ? (
          <div className="case-docs-share-grid" role="group" aria-label="Share with">
            <button
              type="button"
              className={`case-docs-share-tile${shareWithCm ? ' is-active' : ''}`}
              aria-pressed={shareWithCm}
              onClick={() => setShareWithCm((v) => !v)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">supervisor_account</span>
              <span>Case manager</span>
            </button>
            <button
              type="button"
              className={`case-docs-share-tile${shareWithParents ? ' is-active' : ''}`}
              aria-pressed={shareWithParents}
              onClick={() => setShareWithParents((v) => !v)}
            >
              <span className="material-symbols-outlined" aria-hidden="true">family_restroom</span>
              <span>Parents</span>
            </button>
          </div>
        ) : null}

        {uploadedPreview ? (
          <article className="case-docs-upload-tile case-docs-upload-tile--success">
            <span className="case-docs-upload-tile__icon" aria-hidden="true">
              <span className="material-symbols-outlined">check_circle</span>
            </span>
            <div className="case-docs-upload-tile__body">
              <strong>{uploadedPreview.title}</strong>
              <span>
                {categoryLabel}
                {uploadedPreview.fileName ? ` · ${uploadedPreview.fileName}` : ' · Link saved'}
              </span>
            </div>
          </article>
        ) : null}

        {error ? (
          <p className="case-docs-modal__error" role="alert">
            {error}
          </p>
        ) : null}

        <footer className="case-docs-modal__footer">
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" className="ic-btn ic-btn--primary case-docs-modal__submit" disabled={saving}>
            {saving ? 'Uploading…' : mode === 'edit' ? 'Save' : 'Upload'}
          </button>
        </footer>
      </form>
    </div>
  )
}
