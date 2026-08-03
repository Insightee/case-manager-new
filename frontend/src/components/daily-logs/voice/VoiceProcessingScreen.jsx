import { pipelineStepIndex, PROCESSING_STEPS, PROCESSING_STEPS_V2 } from '../../../lib/structuredSessionEvidence.js'

export function VoiceProcessingScreen({
  pipelinePhase,
  pipelineVersion = 'v1',
  error,
  onCancel,
  onRetry,
  onTypeInstead,
}) {
  const isV2 = pipelineVersion === 'v2'
  const steps = isV2 ? PROCESSING_STEPS_V2 : PROCESSING_STEPS
  const activeIdx = pipelineStepIndex(pipelinePhase, { version: isV2 ? 'v2' : 'v1' })
  const allDone = isV2 ? activeIdx >= 3 : activeIdx >= 6

  if (error) {
    return (
      <div className="vsl-stitch__card">
        <p className="vsl-stitch__error">{error}</p>
        <div className="vsl-stitch__pill-row">
          {onRetry ? (
            <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary vsl-stitch__btn--sm" onClick={onRetry}>
              Try again
            </button>
          ) : null}
          {onTypeInstead ? (
            <button type="button" className="vsl-stitch__text-link" onClick={onTypeInstead}>
              Type instead
            </button>
          ) : null}
        </div>
      </div>
    )
  }

  return (
    <div className="vsl-stitch__card vsl-stitch__processing">
      <div className="vsl-stitch__processing-icon" aria-hidden="true">
        ◎
      </div>
      <h2 className="vsl-stitch__processing-title">Analyzing session audio</h2>
      <p className="vsl-stitch__processing-sub">
        {isV2
          ? 'Transcription and clinical mapping usually finish in under 30 seconds. You can leave and return when the draft is ready.'
          : 'Please wait while we prepare your session draft.'}
      </p>

      <ol className="vsl-stitch__stepper vsl-stitch__stepper--left" aria-busy={!allDone}>
        {steps.map((step, idx) => {
          let state = 'pending'
          if (allDone || idx < activeIdx) state = 'done'
          else if (idx === activeIdx) state = 'active'
          return (
            <li key={step.id} className={`vsl-stitch__step vsl-stitch__step--${state}`}>
              <span className="vsl-stitch__step-icon" aria-hidden="true">
                {state === 'done' ? '✓' : idx + 1}
              </span>
              <div>
                <p className="vsl-stitch__step-label">{step.label}</p>
                {state === 'active' ? <p className="vsl-stitch__step-hint">Working…</p> : null}
              </div>
            </li>
          )
        })}
      </ol>

      {isV2 && !allDone ? (
        <div
          className="vsl-stitch__indeterminate"
          role="progressbar"
          aria-valuetext="Processing"
          style={{ height: 3, background: '#e7eefe', borderRadius: 4, margin: '16px auto', maxWidth: 280, overflow: 'hidden' }}
        >
          <div
            style={{
              height: '100%',
              width: '40%',
              background: '#416656',
              animation: 'vsl-indeterminate 1.4s ease-in-out infinite',
            }}
          />
        </div>
      ) : null}

      <p style={{ fontSize: '0.8125rem', color: 'var(--vsl-secondary)', marginTop: 12 }}>
        Draft sections fill automatically from your recording — you can edit everything before submit.
      </p>

      {onCancel ? (
        <button type="button" className="vsl-stitch__text-link" style={{ marginTop: 12 }} onClick={onCancel}>
          Cancel processing
        </button>
      ) : null}
    </div>
  )
}
