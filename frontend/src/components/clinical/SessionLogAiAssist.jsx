import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { ClinicalSecondaryButton } from '../clinical-ui/ClinicalSecondaryButton.jsx'

export function SessionLogAiAssist({ logId, note, onImprovedNote }) {
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  const run = async (path, body) => {
    if (!logId) return
    setLoading(true)
    setMessage('')
    try {
      const data = await apiFetch(`/api/v1/daily-logs/${logId}/ai/${path}`, {
        method: 'POST',
        body: body ? JSON.stringify(body) : undefined,
      })
      return data
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
        disabled={loading || !logId || !note?.trim()}
        onClick={async () => {
          const data = await run('improve-note', { note })
          if (data?.draft_text) onImprovedNote?.(data.draft_text)
        }}
      >
        Improve note
      </ClinicalSecondaryButton>
      <ClinicalSecondaryButton
        disabled={loading || !logId}
        onClick={async () => {
          const data = await run('check-evidence')
          if (data?.missing?.length) {
            setMessage(`Consider adding: ${data.missing.join(', ')}`)
          } else if (data) {
            setMessage('Structured evidence looks complete for this log.')
          }
        }}
      >
        Check missing evidence
      </ClinicalSecondaryButton>
      <ClinicalSecondaryButton
        disabled={loading || !logId}
        onClick={async () => {
          const data = await run('suggest-capture')
          if (data?.suggestions?.length) setMessage(data.suggestions[0])
        }}
      >
        Suggest what to capture
      </ClinicalSecondaryButton>
      {message ? <p style={{ width: '100%', fontSize: '0.8125rem', margin: 0 }}>{message}</p> : null}
    </div>
  )
}
