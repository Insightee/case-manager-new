import { useRef, useState } from 'react'
import { apiFetch, apiUpload } from '../../../lib/apiClient.js'

const MAX_BYTES = 10 * 1024 * 1024
const ACCEPT = 'image/jpeg,image/png,image/webp,video/mp4,video/quicktime'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function SessionLogEvidenceUpload({ caseId, sessionDate, readOnly = false, uploads = [], onChange }) {
  const inputRef = useRef(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState('upload')
  const [linkUrl, setLinkUrl] = useState('')
  const [linkTitle, setLinkTitle] = useState('')

  const totalBytes = uploads.reduce((sum, u) => sum + (u.size || 0), 0)

  async function handleFiles(fileList) {
    if (!caseId || readOnly || !fileList?.length) return
    setError('')
    const files = [...fileList]
    const nextTotal = totalBytes + files.reduce((s, f) => s + f.size, 0)
    if (nextTotal > MAX_BYTES) {
      setError(`Total upload must stay under 10 MB (currently ${formatSize(totalBytes)}).`)
      return
    }
    setBusy(true)
    const added = []
    try {
      for (const file of files) {
        if (file.size > MAX_BYTES) {
          setError(`${file.name} exceeds 10 MB.`)
          continue
        }
        const fd = new FormData()
        fd.append('category', 'SESSION_EVIDENCE')
        fd.append('title', `Session evidence ${sessionDate || 'log'}`)
        fd.append('source_type', 'UPLOAD')
        fd.append('file', file)
        fd.append('share_with_cm', '1')
        fd.append('share_with_parents', '0')
        const doc = await apiUpload(`/api/v1/cases/${caseId}/documents`, fd)
        added.push({
          id: doc.id,
          title: doc.title || file.name,
          fileName: file.name,
          size: file.size,
          mime: file.type,
          kind: 'upload',
        })
      }
      if (added.length) onChange?.([...uploads, ...added])
    } catch (err) {
      setError(err.message || 'Could not upload file')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  async function handleLinkAdd(e) {
    e.preventDefault()
    e.stopPropagation()
    if (!caseId || readOnly) return
    const url = linkUrl.trim()
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      setError('Paste a full link starting with https://')
      return
    }
    setBusy(true)
    setError('')
    try {
      const doc = await apiFetch(`/api/v1/cases/${caseId}/documents`, {
        method: 'POST',
        body: JSON.stringify({
          category: 'SESSION_EVIDENCE',
          title: linkTitle.trim() || `Session link ${sessionDate || 'log'}`,
          source_type: 'EXTERNAL_LINK',
          external_url: url,
          share_with_cm: true,
          share_with_parents: false,
        }),
      })
      onChange?.([
        ...uploads,
        {
          id: doc.id,
          title: doc.title || url,
          fileName: url,
          size: 0,
          kind: 'link',
        },
      ])
      setLinkUrl('')
      setLinkTitle('')
    } catch (err) {
      setError(err.message || 'Could not save link')
    } finally {
      setBusy(false)
    }
  }

  function removeUpload(id) {
    onChange?.(uploads.filter((u) => u.id !== id))
  }

  return (
    <section className="sl-v2-evidence" aria-labelledby="sl-v2-evidence-heading">
      <h3 id="sl-v2-evidence-heading" className="sl-goals-section__title">
        Evidence &amp; Attachments
      </h3>
      <p className="sl-v2-evidence__hint">
        Photos, videos, or links from this session · {formatSize(totalBytes)} / 10 MB
      </p>

      {uploads.length ? (
        <ul className="sl-v2-evidence__list">
          {uploads.map((u) => (
            <li key={u.id} className="sl-v2-evidence__item">
              <span>{u.kind === 'link' ? `Link: ${u.title}` : u.fileName || u.title}</span>
              {!readOnly ? (
                <button type="button" className="sl-v2-evidence__remove" onClick={() => removeUpload(u.id)}>
                  Remove
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {!readOnly ? (
        <>
          <div className="sl-v2-evidence__modes" role="tablist" aria-label="Evidence type">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'upload'}
              className={`sl-v2-evidence__mode${mode === 'upload' ? ' is-active' : ''}`}
              onClick={() => setMode('upload')}
            >
              Upload file
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'link'}
              className={`sl-v2-evidence__mode${mode === 'link' ? ' is-active' : ''}`}
              onClick={() => setMode('link')}
            >
              Add link
            </button>
          </div>

          {mode === 'upload' ? (
            <label className="sl-v2-evidence__drop">
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                multiple
                disabled={busy}
                className="sl-v2-evidence__input"
                onChange={(e) => handleFiles(e.target.files)}
              />
              <span aria-hidden="true">📎</span>
              {busy ? 'Uploading…' : 'Upload photo / video'}
            </label>
          ) : (
            <form className="sl-v2-evidence__link-form" onSubmit={handleLinkAdd}>
              <label className="gs-field">
                <span className="gs-field__label">Link title (optional)</span>
                <input
                  type="text"
                  value={linkTitle}
                  disabled={busy}
                  placeholder="e.g. Classroom video clip"
                  onChange={(e) => setLinkTitle(e.target.value)}
                />
              </label>
              <label className="gs-field">
                <span className="gs-field__label">URL</span>
                <input
                  type="url"
                  required
                  value={linkUrl}
                  disabled={busy}
                  placeholder="https://…"
                  onChange={(e) => setLinkUrl(e.target.value)}
                />
              </label>
              <button type="submit" className="gs-btn gs-btn--secondary" disabled={busy}>
                {busy ? 'Saving…' : 'Add link'}
              </button>
            </form>
          )}
          {error ? <p className="gs-error">{error}</p> : null}
        </>
      ) : null}
    </section>
  )
}
