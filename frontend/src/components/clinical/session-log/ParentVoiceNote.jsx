import { useRef, useState } from 'react'
import { apiUpload } from '../../../lib/apiClient.js'

const MAX_VOICE_BYTES = 10 * 1024 * 1024

export function ParentVoiceNote({ caseId, sessionDate, disabled, attachment, onAttachmentChange }) {
  const [recording, setRecording] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const mediaRef = useRef(null)
  const chunksRef = useRef([])

  async function startRecording() {
    setError('')
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
        if (blob.size > MAX_VOICE_BYTES) {
          setError('Voice note must be under 10 MB.')
          return
        }
        if (!caseId) {
          setError('Case is missing — refresh and try again.')
          return
        }
        setBusy(true)
        try {
          const fd = new FormData()
          fd.append('category', 'SESSION_EVIDENCE')
          fd.append('title', `Parent voice note ${sessionDate || ''}`.trim())
          fd.append('source_type', 'FILE_UPLOAD')
          fd.append('file', blob, `parent-voice-${Date.now()}.webm`)
          fd.append('share_with_cm', '1')
          fd.append('share_with_parents', '1')
          const doc = await apiUpload(`/api/v1/cases/${caseId}/documents`, fd)
          onAttachmentChange?.({ id: doc.id, fileName: 'Voice note', kind: 'voice' })
        } catch (err) {
          setError(err.message || 'Could not upload voice note')
        } finally {
          setBusy(false)
        }
      }
      mediaRef.current = recorder
      recorder.start()
      setRecording(true)
    } catch {
      setError('Microphone access is needed to record a voice note.')
    }
  }

  function stopRecording() {
    mediaRef.current?.stop()
    setRecording(false)
  }

  return (
    <div className="sl-voice-note">
      {attachment ? (
        <p className="sl-voice-note__attached">
          Voice note attached — family can play this with the session summary.
          {!disabled ? (
            <button type="button" className="sl-voice-note__clear" onClick={() => onAttachmentChange?.(null)}>
              Remove
            </button>
          ) : null}
        </p>
      ) : null}
      {!disabled ? (
        <button
          type="button"
          className={`sl-voice-note__btn${recording ? ' is-recording' : ''}`}
          disabled={busy}
          onClick={recording ? stopRecording : startRecording}
        >
          {busy ? 'Saving…' : recording ? '■ Stop & attach' : '🎙 Record voice note for family'}
        </button>
      ) : null}
      {error ? <p className="gs-error">{error}</p> : null}
    </div>
  )
}
