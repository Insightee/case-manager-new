import { useRef, useState } from 'react'
import { TICKET_ATTACHMENT_MAX_BYTES, TICKET_ATTACHMENT_MAX_FILES } from '../../lib/apiClient.js'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function TicketFileInput({ files, onChange, disabled = false, maxFiles = TICKET_ATTACHMENT_MAX_FILES, maxBytes = TICKET_ATTACHMENT_MAX_BYTES }) {
  const inputRef = useRef(null)
  const [error, setError] = useState('')

  function addFiles(fileList) {
    setError('')
    const next = [...files]
    for (const f of fileList) {
      if (next.length >= maxFiles) {
        setError(`You can attach up to ${maxFiles} files.`)
        break
      }
      if (f.size > maxBytes) {
        setError(`Each file must be ${formatSize(maxBytes)} or less.`)
        continue
      }
      if (f.size === 0) {
        setError('Empty files are not allowed.')
        continue
      }
      next.push(f)
    }
    onChange(next)
  }

  function removeAt(index) {
    onChange(files.filter((_, i) => i !== index))
    setError('')
  }

  return (
    <div className="ticket-file-input">
      <label className="ticket-file-input__label">
        Attachments
        <span className="ticket-file-input__hint">
          Up to {maxFiles} files, {formatSize(maxBytes)} each (images, PDF, plain text)
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept="image/jpeg,image/png,image/webp,application/pdf,text/plain"
          disabled={disabled || files.length >= maxFiles}
          className="ticket-file-input__native"
          onChange={(e) => {
            addFiles(Array.from(e.target.files || []))
            e.target.value = ''
          }}
        />
        <button
          type="button"
          className="ticket-file-input__pick"
          disabled={disabled || files.length >= maxFiles}
          onClick={() => inputRef.current?.click()}
        >
          Choose files
        </button>
      </label>
      {files.length > 0 ? (
        <ul className="ticket-file-input__list">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="ticket-file-input__chip">
              <span title={f.name}>
                {f.name} <em>({formatSize(f.size)})</em>
              </span>
              <button type="button" onClick={() => removeAt(i)} disabled={disabled} aria-label={`Remove ${f.name}`}>
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {error ? <p className="ticket-file-input__error">{error}</p> : null}
    </div>
  )
}
