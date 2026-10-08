import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch, apiFetchBlob } from '../../lib/apiClient.js'
import { VaultDocumentPreviewModal } from './VaultDocumentPreviewModal.jsx'
import './therapist-vault.css'

function statusMeta(status) {
  switch (status) {
    case 'APPROVED':
      return { label: 'Approved', className: 'therapist-vault__status--approved', icon: '✓' }
    case 'PENDING':
      return { label: 'Pending approval', className: 'therapist-vault__status--pending', icon: '…' }
    case 'REJECTED':
      return { label: 'Needs another upload', className: 'therapist-vault__status--rejected', icon: '!' }
    default:
      return { label: 'Not uploaded yet', className: 'therapist-vault__status--missing', icon: '○' }
  }
}

function formatMb(bytes) {
  return `${Math.max(1, Math.round(bytes / (1024 * 1024)))} MB`
}

function VaultDocumentRow({ row, slotHelp, maxBytes, apiFilePrefix, onRefresh }) {
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [preview, setPreview] = useState(null)

  const meta = statusMeta(row.status)

  const closePreview = useCallback(() => {
    setPreview((current) => {
      if (current?.blobUrl) URL.revokeObjectURL(current.blobUrl)
      return null
    })
  }, [])

  async function openPreview() {
    if (!row.id) return
    closePreview()
    setPreview({ fileName: row.file_name, loading: true, blobUrl: null, error: null })
    try {
      const base = apiFilePrefix(row.id)
      const blob = await apiFetchBlob(`${base}?inline=1`)
      const blobUrl = URL.createObjectURL(blob)
      setPreview({ fileName: row.file_name, loading: false, blobUrl, error: null, downloadPath: `${base}` })
    } catch (err) {
      setPreview({
        fileName: row.file_name,
        loading: false,
        blobUrl: null,
        error: err.message || 'Could not load preview',
      })
    }
  }

  async function onFileSelected(e) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setError('Please choose a PDF file.')
      return
    }
    if (file.size > maxBytes) {
      setError(`That file is a bit large — please keep it under ${formatMb(maxBytes)}.`)
      return
    }
    setUploading(true)
    setError('')
    try {
      const body = new FormData()
      body.append('slot_key', row.slot_key)
      body.append('file', file)
      if (row.slot_key === 'other_certification' && row.status === 'REJECTED' && row.id) {
        body.append('replaces_document_id', String(row.id))
      }
      await apiFetch('/api/v1/therapist/vault/documents/upload', { method: 'POST', body })
      await onRefresh()
    } catch (err) {
      setError(err.message || 'Could not upload — try again in a moment.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <li className="therapist-vault__row">
      <div className="therapist-vault__row-main">
        <div className="therapist-vault__row-head">
          <h3 className="therapist-vault__row-title">{row.slot_label}</h3>
          <span className={`therapist-vault__status ${meta.className}`} aria-label={meta.label}>
            <span className="therapist-vault__status-icon" aria-hidden>
              {meta.icon}
            </span>
            {meta.label}
          </span>
        </div>
        {slotHelp ? <p className="therapist-vault__help">{slotHelp}</p> : null}
        {row.rejection_reason ? (
          <p className="therapist-vault__rejection">Note from our team: {row.rejection_reason}</p>
        ) : null}
        {row.file_name ? <p className="therapist-vault__file-meta">{row.file_name}</p> : null}
        {error ? <p className="therapist-vault__alert">{error}</p> : null}
      </div>
      <div className="therapist-vault__row-actions">
        {row.can_preview && row.id ? (
          <button type="button" className="therapist-vault__btn therapist-vault__btn--ghost" onClick={openPreview}>
            Preview
          </button>
        ) : null}
        {row.can_upload ? (
          <label className="therapist-vault__btn therapist-vault__btn--primary">
            {uploading ? 'Uploading…' : row.status === 'REJECTED' ? 'Upload again' : 'Upload PDF'}
            <input type="file" accept="application/pdf,.pdf" disabled={uploading} hidden onChange={onFileSelected} />
          </label>
        ) : null}
      </div>
      <VaultDocumentPreviewModal
        open={Boolean(preview)}
        fileName={preview?.fileName}
        fileUrl={preview?.blobUrl}
        downloadPath={preview?.downloadPath}
        loading={preview?.loading}
        error={preview?.error}
        onClose={closePreview}
      />
    </li>
  )
}

export function TherapistVaultPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const json = await apiFetch('/api/v1/therapist/vault/documents')
      setData(json)
    } catch (err) {
      setError(err.message || 'Could not load your vault right now.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const helpByKey = useMemo(() => {
    const map = new Map()
    for (const s of data?.slots || []) {
      if (s.help_text) map.set(s.key, s.help_text)
    }
    return map
  }, [data])

  return (
    <div className="therapist-vault">
      <header className="therapist-vault__header">
        <p className="therapist-profile__eyebrow">Therapist portal</p>
        <h1 className="therapist-profile__title">Vault</h1>
        <p className="therapist-profile__intro">
          Keep onboarding documents in one place. Each file is reviewed separately — we will notify you when it is
          approved or if we need a clearer copy.
        </p>
      </header>

      <section className="therapist-vault__section therapist-vault__section--soon" aria-disabled="true">
        <h2>Important links</h2>
        <p className="therapist-vault__soon">Coming soon.</p>
      </section>

      <section className="therapist-vault__section therapist-vault__section--soon" aria-disabled="true">
        <h2>Training module</h2>
        <p className="therapist-vault__soon">Coming soon.</p>
      </section>

      <section className="therapist-vault__section">
        <h2>Upload documents</h2>
        <p className="therapist-vault__section-intro">
          PDF only{data?.max_upload_bytes ? `, up to ${formatMb(data.max_upload_bytes)} each` : ''}.
        </p>
        {error ? <p className="therapist-vault__alert">{error}</p> : null}
        {loading ? <p className="therapist-vault__loading">Loading your documents…</p> : null}
        {!loading && data ? (
          <>
            <ul className="therapist-vault__list">
              {data.fixed_documents.map((row) => (
                <VaultDocumentRow
                  key={row.slot_key}
                  row={row}
                  slotHelp={helpByKey.get(row.slot_key)}
                  maxBytes={data.max_upload_bytes}
                  apiFilePrefix={(id) => `/api/v1/therapist/vault/documents/${id}/file`}
                  onRefresh={load}
                />
              ))}
            </ul>
            <div className="therapist-vault__other">
              <h3 className="therapist-vault__other-title">Additional certifications</h3>
              <p className="therapist-vault__help">{helpByKey.get('other_certification')}</p>
              <ul className="therapist-vault__list">
                {data.other_certifications.length ? (
                  data.other_certifications.map((row) => (
                    <VaultDocumentRow
                      key={row.id}
                      row={row}
                      maxBytes={data.max_upload_bytes}
                      apiFilePrefix={(id) => `/api/v1/therapist/vault/documents/${id}/file`}
                      onRefresh={load}
                    />
                  ))
                ) : (
                  <li className="therapist-vault__row therapist-vault__row--empty">
                    <p>No extra certifications yet.</p>
                  </li>
                )}
              </ul>
              <VaultDocumentRow
                row={{
                  slot_key: 'other_certification',
                  slot_label: 'Add certification',
                  status: 'MISSING',
                  can_upload: true,
                  can_preview: false,
                }}
                maxBytes={data.max_upload_bytes}
                apiFilePrefix={(id) => `/api/v1/therapist/vault/documents/${id}/file`}
                onRefresh={load}
              />
            </div>
          </>
        ) : null}
      </section>
    </div>
  )
}
