import { useState } from 'react'
import { ClinicalPrimaryButton } from '../../clinical-ui/ClinicalPrimaryButton.jsx'

const SUGGESTED_PROMPTS = [
  'What changed since last week?',
  'Which goal needs more evidence?',
  'What should I observe next?',
  'Draft parent-safe wording',
]

export function AskInsighteAiPanel({ snapshot, onAsk, asking }) {
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const hasSnapshot = Boolean(snapshot?.id)

  const handleAsk = async (q) => {
    const text = q || question
    if (!text.trim() || !hasSnapshot) return
    const res = await onAsk(text.trim())
    if (res?.answer) setAnswer(res.answer)
  }

  return (
    <aside className="insights-ai-panel">
      <header className="insights-ai-panel__header">
        <div className="insights-ai-panel__brand">
          <span className="insights-ai-panel__logo" aria-hidden="true">✦</span>
          <h3>Ask Insighte AI</h3>
        </div>
        <p className="insights-ai-panel__header-sub">
          {hasSnapshot
            ? 'Ask follow-up questions about the generated snapshot.'
            : 'Generate a snapshot first to unlock follow-up questions.'}
        </p>
      </header>

      <div className="insights-ai-panel__body">
        <div className="insights-ai-suggestions" role="list">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              type="button"
              className="insights-ai-suggestion-btn"
              disabled={!hasSnapshot || asking}
              onClick={() => handleAsk(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>

        <div className="insights-ai-input-row">
          <input
            type="text"
            className="insights-ai-input"
            placeholder="Ask about this snapshot…"
            value={question}
            disabled={!hasSnapshot || asking}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAsk()}
          />
          <ClinicalPrimaryButton disabled={!hasSnapshot || asking || !question.trim()} onClick={() => handleAsk()}>
            {asking ? 'Asking…' : 'Ask'}
          </ClinicalPrimaryButton>
        </div>

        {answer ? (
          <div className="insights-ai-answer">
            <p>{answer}</p>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
