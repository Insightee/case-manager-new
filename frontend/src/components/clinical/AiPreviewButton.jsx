import { useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import { AI_ENABLED, AI_GATEWAY_HARDENED } from '../../lib/reportsRevampFlags.js'

export function AiPreviewButton({ action, caseId, context = {}, onDraft, label = 'AI preview draft' }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [draft, setDraft] = useState('')

  async function runPreview() {
    setBusy(true)
    setError('')
    try {
      const res = await apiFetch('/api/v1/ai/preview', {
        method: 'POST',
        body: JSON.stringify({ action, case_id: caseId, context }),
      })
      setDraft(res.draft_text || '')
      onDraft?.(res.draft_text, res)
    } catch (err) {
      setError(err.message || 'Preview failed')
    } finally {
      setBusy(false)
    }
  }

  function copyDraft() {
    if (draft) navigator.clipboard?.writeText(draft)
  }

  function acceptDraft() {
    if (draft) onDraft?.(draft, { accepted: true })
    setDraft('')
  }

  return (
    <div className="cp-ai-preview">
      <p className="cp-quality-card__hint">Draft suggestion only — never auto-published.</p>
      <button type="button" className="ic-btn ic-btn--ghost" disabled={busy} onClick={runPreview}>
        {busy ? 'Generating…' : label}
      </button>
      {error ? <p className="ic-session-composer__error">{error}</p> : null}
      {draft ? (
        <div className="cp-ai-preview__result">
          <p>{draft}</p>
          {AI_GATEWAY_HARDENED || !AI_ENABLED ? (
            <div className="cp-ai-preview__actions">
              <button type="button" className="ic-btn ic-btn--primary ic-btn--sm" onClick={acceptDraft}>
                Accept into editor
              </button>
              <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={copyDraft}>
                Copy
              </button>
              <button type="button" className="ic-btn ic-btn--ghost ic-btn--sm" onClick={() => setDraft('')}>
                Dismiss
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
