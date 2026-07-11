/** Voice-first session log API — upload, status polling, retry. */

import { apiFetch, apiUpload } from './apiClient.js'

export async function uploadVoiceRecording(sessionId, blob, { durationSeconds } = {}) {
  const fd = new FormData()
  fd.append('session_id', String(sessionId))
  if (durationSeconds != null) fd.append('duration_seconds', String(Math.round(durationSeconds)))
  const ext = (blob.type || '').includes('mp4') ? 'm4a' : 'webm'
  fd.append('file', blob, `voice-log-${Date.now()}.${ext}`)
  return apiUpload('/api/v1/daily-logs/voice', fd, { timeoutMs: 120000 })
}

export function getVoiceRecordingStatus(recordingId) {
  return apiFetch(`/api/v1/daily-logs/voice/${recordingId}/status`)
}

export function retryVoiceRecording(recordingId) {
  return apiFetch(`/api/v1/daily-logs/voice/${recordingId}/retry`, { method: 'POST' })
}

export function getVoiceRecordingAudioUrl(recordingId) {
  const base = import.meta.env.VITE_API_URL || ''
  return `${base}/api/v1/daily-logs/voice/${recordingId}/audio`
}

export async function fetchVoiceRecordingAudio(recordingId) {
  const { apiFetchBlob } = await import('./apiClient.js')
  return apiFetchBlob(`/api/v1/daily-logs/voice/${recordingId}/audio`)
}

/** Send an emerging goal candidate to CM review (existing pending_review pipeline). */
export function sendGoalCandidateForReview(caseId, { label, rationale, domainKey, sessionId, note }) {
  return apiFetch(`/api/v1/cases/${caseId}/goal-candidates`, {
    method: 'POST',
    body: JSON.stringify({
      label,
      rationale: [rationale, note].filter(Boolean).join('\n\nTherapist note: '),
      domain_key: domainKey || undefined,
      source: 'voice_session_log',
      source_session_id: sessionId || undefined,
      goal_use: 'cm_iep_review',
    }),
  })
}

/** Send an unlinked strategy to CM review as a case strategy candidate. */
export function sendStrategyCandidateForReview(caseId, { label, howToUse, goalCardId }) {
  return apiFetch(`/api/v1/cases/${caseId}/strategy-candidates`, {
    method: 'POST',
    body: JSON.stringify({
      label,
      how_to_use: howToUse || undefined,
      linked_goal_card_id: goalCardId || undefined,
      source: 'voice_session_log',
      action: 'submit_for_cm_review',
    }),
  })
}

const TERMINAL_RECORDING_STATUSES = new Set(['READY', 'FAILED', 'EXPIRED'])

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Poll until the pipeline reaches a terminal state.
 * onUpdate(status) fires on every poll so the UI can show
 * transcribing/structuring states. Returns the final status object.
 */
export async function pollVoiceRecording(recordingId, { onUpdate, intervalMs = 2500, maxAttempts = 60 } = {}) {
  let idleUploadPolls = 0
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    const status = await getVoiceRecordingStatus(recordingId)
    onUpdate?.(status)
    if (TERMINAL_RECORDING_STATUSES.has(status.recording_status)) return status

    const waitingToStart =
      status.recording_status === 'UPLOADED' ||
      (status.recording_status === 'PROCESSING' && status.transcription_status === 'PENDING')
    if (waitingToStart) {
      idleUploadPolls += 1
      if (idleUploadPolls >= 4) {
        await retryVoiceRecording(recordingId).catch(() => {})
        idleUploadPolls = 0
      }
    } else {
      idleUploadPolls = 0
    }

    const delay = attempt < 6 ? 700 : intervalMs
    await sleep(delay)
  }
  throw new Error('Processing is taking longer than expected — you can keep this open or come back later.')
}
