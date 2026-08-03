import { getVoiceRecordingAudioUrl } from '../../../lib/voiceLogApi.js'

export function VoiceDraftTopBar({
  recordingId,
  audioAvailable,
  onReRecord,
  onListen,
  onViewTranscript,
}) {
  if (!onReRecord && !(recordingId && audioAvailable) && !onViewTranscript) return null

  return (
    <nav className="vsl-stitch__topbar" aria-label="Recording actions">
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
    </nav>
  )
}
