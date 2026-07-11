import { useCallback, useState } from 'react'
import { apiFetch } from '../lib/apiClient.js'
import { clearLogDraft, saveLogDraft } from '../lib/logDraftStore.js'
import { structuredSessionToSubmitBody } from '../lib/voiceExtractionMapper.js'

/** Submit voice structured session log via existing daily-logs API. */
export function useSessionLogSubmit({ session, existingLog, onSuccess, isLateSession = false }) {
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [draftNote, setDraftNote] = useState('')
  const isEdit = Boolean(existingLog?.id)

  const saveDraft = useCallback(
    async (structuredSession) => {
      if (!session?.id || isEdit) return
      setError('')
      try {
        await saveLogDraft(session.id, {
          structured_session: structuredSession,
          sync_status: 'local',
        })
        setDraftNote('Draft saved on this device')
      } catch {
        setError('Could not save draft on this device')
      }
    },
    [session, isEdit],
  )

  const submitStructured = useCallback(
    async (structuredSession, { lateReason } = {}) => {
      if (!isEdit && session?.status && session.status !== 'COMPLETED') {
        setError('End the session before submitting a log.')
        return null
      }
      const mapped = structuredSessionToSubmitBody(structuredSession, {
        attendanceStatus: 'PRESENT',
        lateReason: isLateSession ? lateReason : undefined,
      })
      if (mapped.error) {
        setError(mapped.error)
        return null
      }
      setSubmitting(true)
      setError('')
      try {
        let saved
        if (isEdit && existingLog.approval_status === 'REJECTED') {
          saved = await apiFetch(`/api/v1/daily-logs/${existingLog.id}/resubmit`, {
            method: 'POST',
            body: JSON.stringify(mapped.body),
          })
        } else if (isEdit) {
          saved = await apiFetch(`/api/v1/daily-logs/${existingLog.id}`, {
            method: 'PATCH',
            body: JSON.stringify(mapped.body),
          })
        } else {
          saved = await apiFetch('/api/v1/daily-logs', {
            method: 'POST',
            body: JSON.stringify({ session_id: session.id, ...mapped.body }),
          })
        }
        if (session?.id) await clearLogDraft(session.id).catch(() => {})
        setDraftNote('')
        onSuccess?.(saved)
        return saved
      } catch (err) {
        if (session?.id) {
          await saveLogDraft(session.id, {
            structured_session: structuredSession,
            sync_status: 'pending_sync',
          }).catch(() => {})
          setDraftNote('Saved on device — will sync when you’re back online')
        }
        setError(err.message || 'Could not save log — your draft is on this device.')
        return null
      } finally {
        setSubmitting(false)
      }
    },
    [session, existingLog, isEdit, isLateSession, onSuccess],
  )

  return { submitting, error, draftNote, setError, saveDraft, submitStructured }
}
