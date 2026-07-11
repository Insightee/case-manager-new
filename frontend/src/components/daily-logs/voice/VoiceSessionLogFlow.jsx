import { useCallback, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { loadSessionLogRepository } from '../../../lib/sessionLogRepository.js'
import { pollVoiceRecording, retryVoiceRecording, getVoiceRecordingStatus, fetchVoiceRecordingAudio } from '../../../lib/voiceLogApi.js'
import {
  clearPendingAudio,
  clearVoiceFlowState,
  readVoiceFlowState,
  saveVoiceFlowState,
} from '../../../lib/voiceLogStore.js'
import { clearLogDraft, getLogDraft } from '../../../lib/logDraftStore.js'
import {
  extractionToStructuredSession,
  legacyLogToStructuredSession,
  normalizeStructuredSession,
} from '../../../lib/voiceExtractionMapper.js'
import { emptyStructuredSession } from '../../../lib/structuredSessionEvidence.js'
import { useVoiceRecorder } from '../../../hooks/useVoiceRecorder.js'
import { useSessionLogSubmit } from '../../../hooks/useSessionLogSubmit.js'
import { isLateSessionLog } from '../../../lib/sessionLogUtils.js'
import { VoiceReadyScreen } from './VoiceReadyScreen.jsx'
import { VoiceRecordingScreen } from './VoiceRecordingScreen.jsx'
import { VoiceProcessingScreen } from './VoiceProcessingScreen.jsx'
import { VoiceStoryDraftScreen } from './VoiceStoryDraftScreen.jsx'
import { VoiceSessionPreviewScreen } from './VoiceSessionPreviewScreen.jsx'
import { VoiceDraftTopBar } from './VoiceDraftTopBar.jsx'
import { VoiceFlowFooter } from './VoiceFlowFooter.jsx'
import { SessionContextHeader } from './SessionContextHeader.jsx'
import './voice-session-log-stitch.css'

const TERMINAL_STATUSES = new Set(['READY', 'FAILED', 'EXPIRED'])

/**
 * Canonical session-log editor: voice-first confirm-and-edit flow.
 * ready → record → processing → draft → preview → submit.
 * Manual entry ("Type instead") uses the same structured draft.
 * Edit/resubmit opens the draft prefilled from structured_session_json
 * (or adapted from legacy prose fields).
 */
export function VoiceSessionLogFlow(props) {
  if (!props.session?.case_id) return null
  return <VoiceFlowInner {...props} />
}

function VoiceFlowInner(props) {
  const { session, existingLog, caseCode, childName, onSuccess, onCancel, onTimesSaved } = props
  const isEdit = Boolean(existingLog?.id)
  const [step, setStep] = useState(isEdit ? 'draft' : 'ready')
  const [repo, setRepo] = useState(null)
  const [recordingId, setRecordingId] = useState(null)
  const [pipelineStatus, setPipelineStatus] = useState(null)
  const [pipelineError, setPipelineError] = useState('')
  const [structuredSession, setStructuredSession] = useState(() => {
    if (isEdit) {
      const legacy = legacyLogToStructuredSession(existingLog, { sessionId: session.id })
      if (existingLog.structured_session_json) {
        return normalizeStructuredSession(existingLog.structured_session_json, legacy)
      }
      return legacy
    }
    return emptyStructuredSession({ sessionId: session.id })
  })
  const [audioAvailable, setAudioAvailable] = useState(false)
  const [transcriptOpen, setTranscriptOpen] = useState(false)
  const [lateReason, setLateReason] = useState(existingLog?.late_reason || '')
  const resumeStartedRef = useRef(false)

  const isLate = isLateSessionLog(session)
  const { submitting, error, draftNote, setError, saveDraft, submitStructured } = useSessionLogSubmit({
    session,
    existingLog: existingLog || null,
    onSuccess,
    isLateSession: isLate,
  })

  // Edit/resubmit: fetch canonical structured JSON when the list row lacks it.
  useEffect(() => {
    if (!isEdit || existingLog.structured_session_json) return undefined
    let cancelled = false
    apiFetch(`/api/v1/daily-logs/${existingLog.id}`)
      .then((full) => {
        if (cancelled || !full?.structured_session_json) return
        setStructuredSession(
          normalizeStructuredSession(
            full.structured_session_json,
            legacyLogToStructuredSession(full, { sessionId: session.id }),
          ),
        )
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isEdit, existingLog, session.id])

  const finishDraft = useCallback(
    async (finalStatus) => {
      const extraction = finalStatus?.extraction
      const transcript = finalStatus?.transcript || ''
      let structured = extractionToStructuredSession(extraction, {
        sessionId: session.id,
        recordingId: finalStatus.id,
        transcript,
      })
      structured = normalizeStructuredSession(finalStatus.structured_session, structured)
      setStructuredSession(structured)
      setRecordingId(finalStatus.id)
      setAudioAvailable(Boolean(finalStatus.audio_available))
      await clearLogDraft(session.id).catch(() => {})
      setStep('draft')
      saveVoiceFlowState(session.id, { step: 'draft', recordingId: finalStatus.id, structuredSession: structured })
    },
    [session.id],
  )

  const handleUploaded = useCallback(
    async (recording) => {
      if (recording.recording_status === 'READY') {
        await finishDraft(recording)
        return
      }
      setRecordingId(recording.id)
      setStep('processing')
      setPipelineError('')
      saveVoiceFlowState(session.id, { step: 'processing', recordingId: recording.id })
      try {
        const finalStatus = await pollVoiceRecording(recording.id, { onUpdate: setPipelineStatus })
        if (finalStatus.recording_status === 'READY') {
          await finishDraft(finalStatus)
        } else {
          setPipelineError(
            finalStatus.error_message ||
              'We could not process the recording — you can retry or continue with manual entry.',
          )
          if (finalStatus.transcript) {
            await finishDraft({ ...finalStatus, extraction: null, structured_session: null })
          }
        }
      } catch (err) {
        setPipelineError(err.message || 'Processing is taking longer than expected.')
      }
    },
    [finishDraft, session.id],
  )

  const recorder = useVoiceRecorder(session.id, { onUploaded: handleUploaded })

  useEffect(() => {
    let cancelled = false
    loadSessionLogRepository(session.case_id)
      .then((data) => {
        if (!cancelled) setRepo(data)
      })
      .catch(() => {})
    if (!isEdit) {
      getLogDraft(session.id)
        .then((draft) => {
          if (!cancelled && draft?.fields?.structured_session) {
            setStructuredSession(draft.fields.structured_session)
          }
        })
        .catch(() => {})
    }
    return () => {
      cancelled = true
    }
  }, [session.case_id, session.id, isEdit])

  useEffect(() => {
    if (!repo || resumeStartedRef.current || isEdit) return
    resumeStartedRef.current = true
    let cancelled = false

    async function resume() {
      const saved = readVoiceFlowState(session.id)
      if (saved?.structuredSession && (saved?.step === 'draft' || saved?.step === 'preview')) {
        setStructuredSession(saved.structuredSession)
        setRecordingId(saved.recordingId)
        setStep(saved.step)
        return
      }
      const recId = saved?.step === 'processing' ? saved.recordingId : null
      if (!recId || cancelled) return
      try {
        const status = await getVoiceRecordingStatus(recId)
        if (cancelled) return
        if (status.recording_status === 'READY') {
          await finishDraft(status)
        } else if (!TERMINAL_STATUSES.has(status.recording_status)) {
          setRecordingId(recId)
          setStep('processing')
          await handleUploaded({ id: recId, recording_status: status.recording_status })
        } else if (status.recording_status === 'FAILED') {
          setRecordingId(recId)
          setStep('processing')
          setPipelineError(status.error_message || 'Processing did not complete.')
        }
      } catch {
        // stay on ready
      }
    }

    resume()
    return () => {
      cancelled = true
    }
  }, [repo, session.id, finishDraft, handleUploaded, isEdit])

  useEffect(() => {
    if (!isEdit && (step === 'draft' || step === 'preview')) {
      saveVoiceFlowState(session.id, { step, recordingId, structuredSession })
    }
  }, [step, structuredSession, session.id, recordingId, isEdit])

  /** Manual entry — same structured editor, no separate typed form. */
  function goManualEntry() {
    clearVoiceFlowState(session.id)
    setStructuredSession((prev) => ({ ...prev, story_edited_by_therapist: true }))
    setStep('draft')
  }

  function goReady() {
    setStep('ready')
    setPipelineError('')
  }

  function goRecording() {
    setStep('recording')
    recorder.discardRecording()
  }

  async function handleListen() {
    if (!recordingId) return
    try {
      const blob = await fetchVoiceRecordingAudio(recordingId)
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audio.play().catch(() => {})
      audio.onended = () => URL.revokeObjectURL(url)
    } catch {
      setError('Recording is no longer available — transcript and notes are still here.')
    }
  }

  async function handleSubmit() {
    if (isLate && !lateReason.trim()) {
      setError('Past-day visit: add a late reason before submitting.')
      return
    }
    const saved = await submitStructured(structuredSession, { lateReason: lateReason.trim() || undefined })
    if (saved) {
      await clearPendingAudio(session.id).catch(() => {})
      clearVoiceFlowState(session.id)
    }
  }

  const focusClass = ' vsl-stitch vsl-stitch--focus'

  return (
    <div className={`ic-session-log-panel${focusClass}`}>
      {(step === 'draft' || step === 'preview') && (
        <>
          <SessionContextHeader
            session={session}
            caseCode={caseCode}
            childName={childName}
            structuredSession={structuredSession}
            onTimesSaved={onTimesSaved}
          />
          <VoiceDraftTopBar
            recordingId={recordingId}
            audioAvailable={audioAvailable}
            onReRecord={!isEdit ? goRecording : undefined}
            onListen={handleListen}
            onViewTranscript={structuredSession.voice_transcript ? () => setTranscriptOpen((o) => !o) : undefined}
            onSaveDraft={step === 'draft' && !isEdit ? () => saveDraft(structuredSession) : undefined}
            onPreview={step === 'draft' ? () => setStep('preview') : undefined}
            onSubmit={step === 'preview' ? handleSubmit : undefined}
            submitting={submitting}
          />
        </>
      )}

      {step === 'ready' && (
        <VoiceReadyScreen
          session={session}
          childName={childName}
          caseCode={caseCode}
          onStartRecording={() => {
            setStep('recording')
            recorder.startRecording()
          }}
          onUploadFile={(file) => {
            setStep('recording')
            recorder.uploadFile(file)
          }}
          onTypeInstead={goManualEntry}
        />
      )}

      {step === 'recording' && (
        <VoiceRecordingScreen
          recorder={recorder}
          onCancel={goReady}
          onFinish={() => recorder.stopRecording()}
          onTypeInstead={goManualEntry}
        />
      )}

      {step === 'processing' && (
        <VoiceProcessingScreen
          pipelinePhase={pipelineStatus?.pipeline_phase || 'transcribing'}
          error={pipelineError}
          onCancel={goReady}
          onRetry={recordingId ? () => retryVoiceRecording(recordingId).then(() => handleUploaded({ id: recordingId })) : undefined}
          onTypeInstead={goManualEntry}
        />
      )}

      {step === 'draft' && (
        <VoiceStoryDraftScreen
          structuredSession={structuredSession}
          onChange={setStructuredSession}
          repo={repo}
          caseId={session.case_id}
          sessionId={session.id}
          transcriptOpen={transcriptOpen}
          onToggleTranscript={setTranscriptOpen}
        />
      )}

      {step === 'preview' && (
        <VoiceSessionPreviewScreen
          structuredSession={structuredSession}
          isLateSession={isLate}
          lateReason={lateReason}
          onLateReasonChange={setLateReason}
          error={error}
        />
      )}

      {(error || draftNote) && step !== 'preview' ? (
        <p className={error ? 'vsl-stitch__error' : ''} style={{ fontSize: '0.875rem', marginTop: 8 }}>
          {error || draftNote}
        </p>
      ) : null}

      {onCancel && (step === 'ready' || (isEdit && step === 'draft')) ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={onCancel}>
          Cancel
        </button>
      ) : null}

      {(step === 'draft' || step === 'preview') && (
        <VoiceFlowFooter
          previewMode={step === 'preview'}
          onSaveDraft={step === 'draft' && !isEdit ? () => saveDraft(structuredSession) : undefined}
          onBack={step === 'preview' ? () => setStep('draft') : undefined}
          onPreview={step === 'draft' ? () => setStep('preview') : undefined}
          onSubmit={step === 'preview' ? handleSubmit : undefined}
          submitting={submitting}
          submitLabel={existingLog?.approval_status === 'REJECTED' ? 'Resubmit log' : isEdit ? 'Save changes' : 'Submit log'}
        />
      )}
    </div>
  )
}
