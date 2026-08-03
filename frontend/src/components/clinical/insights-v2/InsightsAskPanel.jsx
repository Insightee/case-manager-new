import { useState } from 'react'
import { INSIGHTS_ASK_PROMPTS, useCaseInsightsAsk } from '../../../hooks/useCaseInsightsAsk.js'

export function InsightsAskPanel({ caseId }) {
  const { messages, ask, isAsking, askError, usage } = useCaseInsightsAsk(caseId)
  const [draft, setDraft] = useState('')

  const remaining = usage?.remaining ?? usage?.cap ?? 5
  const cap = usage?.cap ?? 5

  const handleSubmit = (event) => {
    event.preventDefault()
    const q = draft.trim()
    if (!q) return
    setDraft('')
    ask(q)
  }

  const handleChip = (prompt) => {
    setDraft(prompt)
  }

  return (
    <section
      className="ci-ask-panel"
      role="tabpanel"
      id="ci-subtabpanel-ask"
      aria-labelledby="ci-subtab-ask"
    >
      <header className="ci-ask-panel__header">
        <h2 className="ci-ask-panel__title">Ask about this case</h2>
        <p className="ci-ask-panel__subtext">
          Answers use session logs, goals, and structured insights only — not a diagnosis.
        </p>
        <span className="ci-ask-panel__usage">
          {remaining}/{cap} questions left this week
        </span>
      </header>

      <div className="ci-ask-panel__messages" aria-live="polite">
        {messages.length === 0 ? (
          <p className="ci-ask-panel__empty">
            Ask about this case — answers use session logs, goals, and structured insights only.
          </p>
        ) : (
          messages.map((msg, index) => (
            <div
              key={`${msg.role}-${index}`}
              className={`ci-ask-bubble ci-ask-bubble--${msg.role}`}
            >
              <p className="ci-ask-bubble__label">{msg.role === 'user' ? 'You' : 'Insighte'}</p>
              <p className="ci-ask-bubble__text">{msg.text}</p>
            </div>
          ))
        )}
        {isAsking ? (
          <p className="ci-ask-panel__loading" role="status">
            Looking at the latest case context…
          </p>
        ) : null}
        {askError ? (
          <p className="ci-ask-panel__error" role="alert">
            {askError}
          </p>
        ) : null}
      </div>

      <div className="ci-ask-panel__chips">
        {INSIGHTS_ASK_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="ci-ask-chip"
            onClick={() => handleChip(prompt)}
            disabled={isAsking || remaining <= 0}
          >
            {prompt}
          </button>
        ))}
      </div>

      <form className="ci-ask-panel__composer" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="ci-ask-input">
          Your question
        </label>
        <textarea
          id="ci-ask-input"
          className="ci-ask-panel__input"
          rows={2}
          placeholder="Type a question about this case…"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={isAsking || remaining <= 0}
        />
        <button
          type="submit"
          className="ci-btn ci-btn--primary ci-ask-panel__send"
          disabled={isAsking || remaining <= 0 || !draft.trim()}
        >
          Send
        </button>
      </form>
    </section>
  )
}
