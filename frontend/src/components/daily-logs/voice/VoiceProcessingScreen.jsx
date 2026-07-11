import { PROCESSING_STEPS, pipelineStepIndex } from '../../../lib/structuredSessionEvidence.js'

export function VoiceProcessingScreen({ pipelinePhase, error, onCancel, onRetry, onTypeInstead }) {
  const activeIdx = pipelineStepIndex(pipelinePhase)

  if (error) {
    return (
      <div className="vsl-stitch__card">
        <p className="vsl-stitch__error">{error}</p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {onRetry ? (
            <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={onRetry}>
              Try again
            </button>
          ) : null}
          {onTypeInstead ? (
            <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onTypeInstead}>
              Type instead
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="vsl-stitch__card">
      <h2 className="vsl-stitch__title">Creating your session draft</h2>
      <p className="vsl-stitch__subtitle">Please wait while we process the session details securely.</p>

      <ol className="vsl-stitch__stepper">
        {PROCESSING_STEPS.map((step, idx) => {
          let state = 'pending'
          if (activeIdx >= 6 || idx < activeIdx) state = 'done'
          else if (idx === activeIdx) state = 'active'
          return (
            <li key={step.id} className={`vsl-stitch__step vsl-stitch__step--${state}`}>
              <span className="vsl-stitch__step-icon" aria-hidden="true">
                {state === 'done' ? '✓' : idx + 1}
              </span>
              <div>
                <p className="vsl-stitch__step-label">{step.label}</p>
                {state === 'active' && step.id === 'identifying_goals' ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', margin: '4px 0 0' }}>
                    Analyzing clinical markers…
                  </p>
                ) : null}
              </div>
            </li>
          )
        })}
      </ol>

      <p style={{ fontSize: '0.875rem', color: 'var(--vsl-secondary)' }}>
        You can leave this page — we&apos;ll keep working and your draft will be waiting.
      </p>

      {onCancel ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 16 }} onClick={onCancel}>
          Cancel processing
        </button>
      ) : null}
    </div>
  )
}
