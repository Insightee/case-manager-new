import { useRef } from 'react'
import { formatDisplayDate } from '../../../lib/datetime.js'
import { RECORDING_CUES } from '../../../lib/structuredSessionEvidence.js'

export function VoiceReadyScreen({ session, childName, caseCode, onStartRecording, onUploadFile, onTypeInstead }) {
  const displayName = childName || session?.child_name || 'Client'
  const fileRef = useRef(null)

  return (
    <div className="vsl-stitch__card">
      <h2 className="vsl-stitch__title">Session Log</h2>
      <p className="vsl-stitch__subtitle">
        Record what happened today. We will organise it into goals, strategies, progress evidence and a family update.
      </p>

      <div className="vsl-stitch__meta-grid">
        <div>
          <span className="vsl-stitch__meta-label">Client</span>
          <strong>{displayName}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Case ID</span>
          <strong>{caseCode || session?.case_code || '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Date</span>
          <strong>{session?.scheduled_date ? formatDisplayDate(session.scheduled_date) : '—'}</strong>
        </div>
        <div>
          <span className="vsl-stitch__meta-label">Setting</span>
          <strong>{session?.mode || '—'}</strong>
        </div>
      </div>

      <div className="vsl-stitch__recording-ring" style={{ marginTop: 32 }}>
        <button type="button" className="vsl-stitch__mic-btn" onClick={onStartRecording} aria-label="Start recording">
          🎤
        </button>
      </div>

      <p style={{ textAlign: 'center', fontWeight: 600, margin: '0 0 8px' }}>Tell us about today&apos;s session</p>
      <p style={{ textAlign: 'center', color: 'var(--vsl-secondary)', fontSize: '0.9375rem', margin: '0 0 20px' }}>
        Speak naturally. Describe the activities, responses, and any challenges.
      </p>

      <button type="button" className="vsl-stitch__btn vsl-stitch__btn--primary" onClick={onStartRecording}>
        Start recording →
      </button>

      <input
        ref={fileRef}
        type="file"
        accept="audio/*"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file && onUploadFile) onUploadFile(file)
          e.target.value = ''
        }}
      />
      <button
        type="button"
        className="vsl-stitch__btn vsl-stitch__btn--ghost"
        style={{ marginTop: 10 }}
        onClick={() => fileRef.current?.click()}
      >
        Upload recording
      </button>

      {onTypeInstead ? (
        <button type="button" className="vsl-stitch__btn vsl-stitch__btn--ghost" style={{ marginTop: 10 }} onClick={onTypeInstead}>
          Type instead
        </button>
      ) : null}

      <div className="vsl-stitch__prompts">
        <p className="vsl-stitch__prompts-title">Prompts</p>
        {RECORDING_CUES.map((cue) => (
          <div key={cue} className="vsl-stitch__prompt-item">
            {cue}
          </div>
        ))}
      </div>
    </div>
  )
}
