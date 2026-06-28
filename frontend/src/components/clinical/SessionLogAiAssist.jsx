import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ClinicalSecondaryButton } from '../clinical-ui/ClinicalSecondaryButton.jsx'

export function SessionLogAiAssist({ logId, note, onImprovedNote }) {
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const runClinicalAi = async (path, body) => {
    setLoading(true)
    setMessage('')
    try {
      return await apiFetch(`/api/v1/clinical-ai/${path}`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
    } catch (err) {
      setMessage(err.message || 'Could not complete AI assist.')
      return null
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="session-log-ai-assist" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem' }}>
      <ClinicalSecondaryButton
        disabled={loading || !note?.trim()}
        onClick={async () => {
          const data = await runClinicalAi('session-note/improve', { raw_note: note, context: { daily_log_id: logId } })
          if (data?.draft_text) onImprovedNote?.(data.draft_text)
          else if (data?.skipped) setMessage(data.reason || 'AI assist is off — your note is unchanged.')
        }}
      >
        Improve note
      </ClinicalSecondaryButton>
      <ClinicalSecondaryButton
        disabled={loading || !note?.trim()}
        onClick={async () => {
          const data = await runClinicalAi('language-check/parent-safe', { text: note })
          if (data?.safe_to_publish === false) {
            setMessage(`Consider rephrasing: ${(data.flagged_phrases || []).join(', ')}`)
          } else if (data) {
            setMessage('Language looks parent-safe.')
          }
        }}
      >
        Check parent-safe language
      </ClinicalSecondaryButton>
      {message ? <p style={{ width: '100%', fontSize: '0.8125rem', margin: 0 }}>{message}</p> : null}
    </div>
  )
}
