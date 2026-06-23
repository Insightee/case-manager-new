import { useEffect, useRef, useState } from 'react'
import { apiUpload } from '../../../lib/apiClient.js'

const MAX_VOICE_BYTES = 10 * 1024 * 1024

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export function ParentVoiceNote({ caseId, sessionDate, disabled, attachment, onAttachmentChange }) {
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const mediaRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const previewUrlRef = useRef('')

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [])

  function clearPreview() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = ''
    }
    setPreviewUrl('')
  }

  async function uploadBlob(blob) {
    if (blob.size > MAX_VOICE_BYTES) {
      setError('Voice note must be under 10 MB.')
      return
    }
    if (!caseId) {
      setError('Case is missing — refresh and try again.')
      return
    }
    setBusy(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('category', 'SESSION_EVIDENCE')
      fd.append('title', `Parent voice note ${sessionDate || ''}`.trim())
      fd.append('source_type', 'UPLOAD')
      fd.append('file', blob, `parent-voice-${Date.now()}.webm`)
      fd.append('share_with_cm', '1')
      fd.append('share_with_parents', '1')
      const doc = await apiUpload(`/api/v1/cases/${caseId}/documents`, fd)
      onAttachmentChange?.({ id: doc.id, fileName: 'Voice note', kind: 'voice' })
      clearPreview()
    } catch (err) {
      setError(err.message || 'Could not upload voice note')
    } finally {
      setBusy(false)
    }
  }

  async function startRecording() {
    setError('')
    clearPreview()
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        const url = URL.createObjectURL(blob)
        previewUrlRef.current = url
        setPreviewUrl(url)
        await uploadBlob(blob)
      }
      mediaRef.current = recorder
      recorder.start()
      setRecording(true)
      setElapsed(0)
      timerRef.current = setInterval(() => setElapsed((n) => n + 1), 1000)
    } catch {
      setError('Microphone access is needed to record a voice note.')
    }
  }

  function stopRecording() {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    mediaRef.current?.stop()
    setRecording(false)
  }

  function removeAttachment() {
    onAttachmentChange?.(null)
    clearPreview()
    setError('')
  }

  return (
    <div className="sl-voice-note">
      {attachment ? (
        <div className="sl-voice-note__attached">
          <span className="sl-voice-note__attached-badge">✓ Voice note saved</span>
          <p className="sl-voice-note__attached-copy">Family can play this with the session summary.</p>
          {!disabled ? (
            <button type="button" className="sl-voice-note__clear" onClick={removeAttachment}>
              Remove
            </button>
          ) : null}
        </div>
      ) : null}

      {recording ? (
        <div className="sl-voice-note__recording" role="status" aria-live="polite">
          <span className="sl-voice-note__recording-pulse" aria-hidden="true" />
          <span className="sl-voice-note__recording-label">Recording…</span>
          <span className="sl-voice-note__recording-timer">{formatElapsed(elapsed)}</span>
          <button type="button" className="sl-voice-note__stop" onClick={stopRecording}>
            Stop recording
          </button>
        </div>
      ) : null}

      {previewUrl && !attachment ? (
        <div className="sl-voice-note__preview">
          <p className="sl-voice-note__preview-label">{busy ? 'Uploading…' : 'Preview'}</p>
          <audio controls src={previewUrl} className="sl-voice-note__player" />
          {!busy && !disabled ? (
            <button type="button" className="sl-voice-note__clear" onClick={clearPreview}>
              Discard preview
            </button>
          ) : null}
        </div>
      ) : null}

      {!disabled && !recording && !attachment ? (
        <button
          type="button"
          className="sl-voice-note__btn"
          disabled={busy}
          onClick={startRecording}
        >
          {busy ? 'Saving…' : '🎙 Record voice note for family'}
        </button>
      ) : null}

      {error ? <p className="gs-error">{error}</p> : null}
    </div>
  )
}
