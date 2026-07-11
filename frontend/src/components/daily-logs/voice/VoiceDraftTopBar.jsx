import { getVoiceRecordingAudioUrl } from '../../../lib/voiceLogApi.js'

export function VoiceDraftTopBar({
  recordingId,
  audioAvailable,
  onReRecord,
  onListen,
  onViewTranscript,
  onSaveDraft,
  onPreview,
  onSubmit,
  submitting,
}) {
  return (
    <div className="vsl-stitch__topbar">
      {onReRecord ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onReRecord}>
          Re-record
        </button>
      ) : null}
      {recordingId && audioAvailable ? (
        <button
          type="button"
          className="vsl-stitch__btn vsl-stitch__btn--ghost"
          onClick={() => {
            if (onListen) onListen()
            else {
              const audio = new Audio(getVoiceRecordingAudioUrl(recordingId))
              audio.play().catch(() => {})
            }
          }}
        >
          Listen
        </button>
      ) : null}
      {onViewTranscript ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onViewTranscript}>
          Transcript
        </button>
      ) : null}
      {onSaveDraft ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" onClick={onSaveDraft}>
          Save draft
        </button>
      ) : null}
      {onPreview ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--secondary" onClick={onPreview}>
          Preview
        </button>
      ) : null}
      {onSubmit ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" disabled={submitting} onClick={onSubmit}>
          {submitting ? 'Submitting…' : 'Submit log'}
        </button>
      ) : null}
    </div>
  )
}
