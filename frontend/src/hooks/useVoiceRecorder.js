import { useCallback, useEffect, useRef, useState } from 'react'
import { uploadVoiceRecording } from '../lib/voiceLogApi.js'
import { clearPendingAudio, clearVoiceFlowState, getPendingAudio, savePendingAudio } from '../lib/voiceLogStore.js'

const DEFAULT_MAX_SECONDS = 120
export const CUE_INTERVAL_MS = 20000

export const RECORDING_CUES = [
  'What did you work on?',
  'Which strategies did you use?',
  'How did the child respond?',
  'Any challenging behaviors?',
]

function pickMimeType() {
  if (typeof MediaRecorder === 'undefined') return ''
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4']
  return candidates.find((t) => MediaRecorder.isTypeSupported?.(t)) || ''
}

export function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

/** MediaRecorder hook — shared by VoiceRecordingScreen. */
export function useVoiceRecorder(sessionId, { maxSeconds = DEFAULT_MAX_SECONDS, onUploaded } = {}) {
  const [phase, setPhase] = useState('idle')
  const [elapsed, setElapsed] = useState(0)
  const [cueIndex, setCueIndex] = useState(0)
  const [error, setError] = useState('')
  const [permissionDenied, setPermissionDenied] = useState(false)
  const [previewUrl, setPreviewUrl] = useState('')
  const [recoveredDraft, setRecoveredDraft] = useState(null)
  const [liveStream, setLiveStream] = useState(null)

  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)
  const cueTimerRef = useRef(null)
  const elapsedRef = useRef(0)
  const blobRef = useRef(null)
  const previewUrlRef = useRef('')

  useEffect(() => {
    let cancelled = false
    getPendingAudio(sessionId)
      .then((row) => {
        if (!cancelled && row?.blob && !row.recordingId) setRecoveredDraft(row)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      stopTimers()
      streamRef.current?.getTracks().forEach((t) => t.stop())
      if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current)
    }
  }, [sessionId])

  function stopTimers() {
    if (timerRef.current) clearInterval(timerRef.current)
    if (cueTimerRef.current) clearInterval(cueTimerRef.current)
    timerRef.current = null
    cueTimerRef.current = null
  }

  function startTimers() {
    timerRef.current = setInterval(() => {
      elapsedRef.current += 1
      setElapsed(elapsedRef.current)
      if (elapsedRef.current >= maxSeconds) stopRecording()
    }, 1000)
    cueTimerRef.current = setInterval(() => {
      setCueIndex((i) => (i + 1) % RECORDING_CUES.length)
    }, CUE_INTERVAL_MS)
  }

  const startRecording = useCallback(async () => {
    setError('')
    setPermissionDenied(false)
    clearVoiceFlowState(sessionId)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      setLiveStream(stream)
      const mimeType = pickMimeType()
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        streamRef.current = null
        setLiveStream(null)
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        blobRef.current = blob
        const url = URL.createObjectURL(blob)
        previewUrlRef.current = url
        setPreviewUrl(url)
        setPhase('review')
        savePendingAudio(sessionId, blob, { durationSeconds: elapsedRef.current }).catch(() => {})
      }
      recorderRef.current = recorder
      recorder.start(1000)
      elapsedRef.current = 0
      setElapsed(0)
      setCueIndex(0)
      setPhase('recording')
      startTimers()
    } catch (err) {
      if (err?.name === 'NotAllowedError' || err?.name === 'PermissionDeniedError') {
        setPermissionDenied(true)
      } else {
        setError('We could not reach your microphone — you can type your update instead.')
      }
    }
  }, [sessionId, maxSeconds])

  function pauseRecording() {
    recorderRef.current?.pause()
    stopTimers()
    setPhase('paused')
  }

  function resumeRecording() {
    recorderRef.current?.resume()
    startTimers()
    setPhase('recording')
  }

  function stopRecording() {
    stopTimers()
    if (recorderRef.current && recorderRef.current.state !== 'inactive') {
      recorderRef.current.stop()
    }
  }

  function discardRecording() {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current)
      previewUrlRef.current = ''
    }
    setPreviewUrl('')
    blobRef.current = null
    setRecoveredDraft(null)
    clearPendingAudio(sessionId).catch(() => {})
    setPhase('idle')
    setElapsed(0)
    elapsedRef.current = 0
  }

  async function uploadRecording(blob, durationSeconds) {
    setPhase('uploading')
    setError('')
    try {
      const result = await uploadVoiceRecording(sessionId, blob, { durationSeconds })
      await savePendingAudio(sessionId, blob, { durationSeconds, recordingId: result.id }).catch(() => {})
      setPhase('done')
      if (onUploaded) await onUploaded(result)
      return result
    } catch (err) {
      setPhase('upload_failed')
      setError(err.message || 'The upload did not go through — your recording is safe on this device.')
      throw err
    }
  }

  function handleUseRecording() {
    if (blobRef.current) return uploadRecording(blobRef.current, elapsedRef.current)
    return Promise.resolve(null)
  }

  function handleRecoveredUpload() {
    if (recoveredDraft?.blob) {
      blobRef.current = recoveredDraft.blob
      elapsedRef.current = recoveredDraft.durationSeconds || 0
      uploadRecording(recoveredDraft.blob, recoveredDraft.durationSeconds || undefined)
      setRecoveredDraft(null)
    }
  }

  async function uploadFile(file) {
    if (!file) return null
    blobRef.current = file
    elapsedRef.current = 0
    return uploadRecording(file, undefined)
  }

  return {
    phase,
    elapsed,
    cueIndex,
    error,
    permissionDenied,
    previewUrl,
    recoveredDraft,
    liveStream,
    blobRef,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    discardRecording,
    handleUseRecording,
    handleRecoveredUpload,
    uploadFile,
    setPhase,
    setError,
  }
}
