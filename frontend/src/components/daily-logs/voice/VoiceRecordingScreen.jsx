import { VoiceWaveform } from './VoiceWaveform.jsx'
import { formatElapsed, RECORDING_CUES } from '../../../hooks/useVoiceRecorder.js'

export function VoiceRecordingScreen({
  recorder,
  onCancel,
  onFinish,
  onTypeInstead,
}) {
  const {
    phase,
    elapsed,
    cueIndex,
    error,
    permissionDenied,
    previewUrl,
    liveStream,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    discardRecording,
    handleUseRecording,
  } = recorder

  if (permissionDenied) {
    return (
      <div className="vsl-stitch__card">
        <p className="vsl-stitch__title">Microphone access is off</p>
        <p className="vsl-stitch__subtitle">Allow microphone access in your browser settings, then try again.</p>
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={startRecording}>
          Try again
        </button>
        {onTypeInstead ? (
          <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={onTypeInstead}>
            Type instead
          </button>
        ) : null}
      </div>
    )
  }

  if (phase === 'review') {
    return (
      <div className="vsl-stitch__card">
        <p className="vsl-stitch__title">Review recording ({formatElapsed(elapsed)})</p>
        {previewUrl ? <audio controls src={previewUrl} style={{ width: '100%', marginBottom: 16 }} /> : null}
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={handleUseRecording}>
          Use this recording
        </button>
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={discardRecording}>
          Re-record
        </button>
      </div>
    )
  }

  if (phase === 'uploading' || phase === 'done') {
    return (
      <div className="vsl-stitch__card" role="status">
        <p className="vsl-stitch__title">{phase === 'done' ? 'Recording saved' : 'Saving your recording…'}</p>
      </div>
    )
  }

  if (phase === 'upload_failed') {
    return (
      <div className="vsl-stitch__card">
        <p className="vsl-stitch__error">{error}</p>
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={handleUseRecording}>
          Try upload again
        </button>
        {onTypeInstead ? (
          <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={onTypeInstead}>
            Type instead
          </button>
        ) : null}
      </div>
    )
  }

  const isLive = phase === 'recording' || phase === 'paused'

  return (
    <div className="vsl-stitch__card">
      <p className="vsl-stitch__timer">{formatElapsed(elapsed)}</p>
      {isLive ? (
        <p style={{ textAlign: 'center', marginBottom: 16 }}>
          <span className="vsl-stitch__status-dot" aria-hidden="true" />
          {phase === 'paused' ? 'Recording paused' : 'Recording session'}
        </p>
      ) : null}

      <div className="vsl-stitch__recording-ring">
        {isLive ? (
          <div style={{ position: 'relative', zIndex: 1 }}>
            <VoiceWaveform stream={liveStream} active={phase === 'recording'} paused={phase === 'paused'} />
          </div>
        ) : (
          <button type="button" className="vsl-stitch__mic-btn" onClick={startRecording} aria-label="Start recording">
            🎤
          </button>
        )}
      </div>

      <p style={{ textAlign: 'center', color: 'var(--vsl-secondary)', margin: '0 0 20px' }}>
        Speak naturally. You do not need to use clinical language.
      </p>

      {isLive ? (
        <>
          <div className="vsl-stitch__cues" aria-live="polite">
            <span className="vsl-stitch__cue-pill">{RECORDING_CUES[cueIndex]}</span>
          </div>
          <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
            {phase === 'recording' ? (
              <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ flex: 1 }} onClick={pauseRecording}>
                Pause
              </button>
            ) : (
              <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ flex: 1 }} onClick={resumeRecording}>
                Resume
              </button>
            )}
            <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" style={{ flex: 2 }} onClick={onFinish || stopRecording}>
              Finish recording
            </button>
          </div>
          {onCancel ? (
            <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={onCancel}>
              Cancel
            </button>
          ) : null}
        </>
      ) : (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={startRecording}>
          Start recording
        </button>
      )}

      {error ? <p className="vsl-stitch__error">{error}</p> : null}
    </div>
  )
}
