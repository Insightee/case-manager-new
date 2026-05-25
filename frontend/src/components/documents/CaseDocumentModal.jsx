import { useEffect, useState } from 'react'
import { CASE_DOCUMENT_CATEGORIES } from '../../lib/caseDocumentCategories.js'
import { GOOGLE_LINK_WARNING, validateGoogleLink } from '../../lib/googleLinkValidation.js'
import './case-documents.css'

const EMPTY = {
  category: 'OTHER',
  title: '',
  report_month: '',
  report_date: '',
  source_type: 'UPLOAD',
  external_url: '',
}

export function CaseDocumentModal({ open, onClose, onSave, initial, mode = 'create' }) {
  const [form, setForm] = useState(EMPTY)
  const [sourceTab, setSourceTab] = useState('UPLOAD')
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!open) return
    if (initial) {
      setForm({
        category: initial.category || 'OTHER',
        title: initial.title || '',
        report_month: initial.report_month || '',
        report_date: initial.report_date || '',
        source_type: initial.current_version?.source_type || 'UPLOAD',
        external_url: initial.current_version?.external_url || '',
      })
      setSourceTab(initial.current_version?.source_type === 'EXTERNAL_LINK' ? 'EXTERNAL_LINK' : 'UPLOAD')
    } else {
      setForm(EMPTY)
      setSourceTab('UPLOAD')
    }
    setFile(null)
    setError('')
  }, [open, initial])

  if (!open) return null

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (!form.title.trim()) {
      setError('Title is required.')
      return
    }
    if (mode === 'create') {
      if (sourceTab === 'UPLOAD' && !file) {
        setError('Choose a file to upload.')
        return
      }
      if (sourceTab === 'EXTERNAL_LINK') {
        const check = validateGoogleLink(form.external_url)
        if (!check.ok) {
          setError(check.message)
          return
        }
      }
    }

    setSaving(true)
    try {
      if (mode === 'edit') {
        await onSave({
          json: {
            title: form.title.trim(),
            category: form.category,
            report_month: form.report_month || null,
            report_date: form.report_date || null,
          },
        })
      } else if (sourceTab === 'EXTERNAL_LINK') {
        const check = validateGoogleLink(form.external_url)
        await onSave({
          json: {
            category: form.category,
            title: form.title.trim(),
            report_month: form.report_month || null,
            report_date: form.report_date || null,
            source_type: 'EXTERNAL_LINK',
            external_url: check.normalized,
          },
        })
      } else {
        const fd = new FormData()
        fd.append('category', form.category)
        fd.append('title', form.title.trim())
        if (form.report_month) fd.append('report_month', form.report_month)
        if (form.report_date) fd.append('report_date', form.report_date)
        fd.append('source_type', 'UPLOAD')
        fd.append('file', file)
        await onSave({ formData: fd })
      }
      onClose()
    } catch (err) {
      setError(err.message || 'Could not save document')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="case-docs-modal__backdrop" role="dialog" aria-modal="true" aria-labelledby="case-doc-modal-title">
      <form className="case-docs-modal" onSubmit={handleSubmit}>
        <h2 id="case-doc-modal-title" style={{ marginTop: 0 }}>
          {mode === 'edit' ? 'Edit document' : 'Add document'}
        </h2>
        <p style={{ fontSize: 13, color: '#6b7280', marginTop: 0 }}>
          Uploaded files and Google links. For rich-text monthly reports, use Monthly Reports.
        </p>

        {mode === 'create' ? (
          <div className="case-docs-modal__tabs">
            <button
              type="button"
              className={sourceTab === 'UPLOAD' ? 'is-active' : ''}
              onClick={() => setSourceTab('UPLOAD')}
            >
              Upload file
            </button>
            <button
              type="button"
              className={sourceTab === 'EXTERNAL_LINK' ? 'is-active' : ''}
              onClick={() => setSourceTab('EXTERNAL_LINK')}
            >
              Google link
            </button>
          </div>
        ) : null}

        <label>
          Category
          <select value={form.category} onChange={(e) => update('category', e.target.value)} required>
            {CASE_DOCUMENT_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>

        <label>
          Title
          <input value={form.title} onChange={(e) => update('title', e.target.value)} required maxLength={255} />
        </label>

        <label>
          Report month (optional)
          <input
            type="month"
            value={form.report_month ? form.report_month.slice(0, 7) : ''}
            onChange={(e) => update('report_month', e.target.value ? `${e.target.value}` : '')}
          />
        </label>

        <label>
          Report date (optional)
          <input type="date" value={form.report_date || ''} onChange={(e) => update('report_date', e.target.value)} />
        </label>

        {mode === 'create' && sourceTab === 'UPLOAD' ? (
          <label>
            File (PDF or Word)
            <input
              type="file"
              accept=".pdf,.doc,.docx,application/pdf,application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </label>
        ) : null}

        {mode === 'create' && sourceTab === 'EXTERNAL_LINK' ? (
          <>
            <label>
              Google Docs or Drive file URL
              <input
                type="url"
                value={form.external_url}
                onChange={(e) => update('external_url', e.target.value)}
                placeholder="https://docs.google.com/document/..."
              />
            </label>
            <p className="case-docs__banner" style={{ marginBottom: 12 }}>
              {GOOGLE_LINK_WARNING}
            </p>
          </>
        ) : null}

        {error ? (
          <p role="alert" style={{ color: '#b91c1c', fontSize: 14 }}>
            {error}
          </p>
        ) : null}

        <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
          <button type="submit" className="ic-btn ic-btn--primary" disabled={saving}>
            {saving ? 'Saving…' : mode === 'edit' ? 'Save' : 'Add document'}
          </button>
          <button type="button" className="ic-btn ic-btn--ghost" onClick={onClose} disabled={saving}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  )
}
