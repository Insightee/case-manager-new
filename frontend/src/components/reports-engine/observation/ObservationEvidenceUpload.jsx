import { useRef, useState } from 'react'
import { useCaseDocumentMutations } from '../../../hooks/useCaseDocuments.js'
import { apiFetch } from '../../../lib/apiClient.js'
import { StitchIcon } from './stitch/ObservationStitchBlocks.jsx'

export function ObservationEvidenceUpload({ caseId, reportId, readOnly, onUploaded }) {
  const inputRef = useRef(null)
  const { create } = useCaseDocumentMutations(caseId)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')

  async function handleFiles(fileList) {
    const file = fileList?.[0]
    if (!file || !reportId || readOnly) return
    setBusy(true)
    setMessage('')
    try {
      const formData = new FormData()
      formData.append('category', 'SESSION_EVIDENCE')
      formData.append('title', file.name.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim() || 'Observation evidence')
      formData.append('source_type', 'UPLOAD')
      formData.append('share_with_cm', 'true')
      formData.append('file', file)
      const doc = await create.mutateAsync({ formData })
      await apiFetch(`/api/v1/reports/${reportId}/evidence`, {
        method: 'POST',
        body: JSON.stringify({ case_document_id: doc.id, evidence_label: doc.title }),
      })
      setMessage('Evidence uploaded — visible to case managers on review.')
      onUploaded?.()
    } catch (err) {
      setMessage(err.message || 'Could not upload evidence')
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  if (readOnly) return null

  return (
    <div className="ob-evidence-upload">
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        accept="image/*,.pdf,video/*"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
        {[
          { icon: 'image', label: 'Photo', accept: 'image/*' },
          { icon: 'picture_as_pdf', label: 'PDF', accept: '.pdf' },
          { icon: 'video_library', label: 'Video', accept: 'video/*' },
        ].map((tile) => (
          <button
            key={tile.label}
            type="button"
            disabled={busy}
            className="aspect-square rounded-lg bg-surface-container flex flex-col items-center justify-center border border-outline-variant/50 hover:bg-lush-mint/10 transition-colors text-outline hover:text-lush-forest disabled:opacity-50 min-h-[72px]"
            onClick={() => {
              if (inputRef.current) {
                inputRef.current.accept = tile.accept
                inputRef.current.click()
              }
            }}
          >
            <StitchIcon name={tile.icon} />
            <span className="text-[10px] font-bold mt-1">{tile.label}</span>
          </button>
        ))}
        <button
          type="button"
          disabled={busy}
          className="aspect-square rounded-lg border-2 border-dashed border-lush-forest flex flex-col items-center justify-center hover:bg-lush-mint/10 transition-colors text-lush-forest disabled:opacity-50 min-h-[72px]"
          onClick={() => {
            if (inputRef.current) {
              inputRef.current.accept = 'image/*,.pdf,video/*'
              inputRef.current.click()
            }
          }}
        >
          <StitchIcon name="upload" />
          <span className="text-[10px] font-bold mt-1">{busy ? 'Uploading…' : 'Upload'}</span>
        </button>
      </div>
      {message ? <p className="text-xs text-on-surface-variant mt-3 m-0">{message}</p> : null}
    </div>
  )
}
