import { useMemo } from 'react'
import {
  applyFamilyPreviewEdits,
  buildFamilyPreview,
  updateFamilyPreviewLine,
} from '../../../lib/structuredSessionEvidence.js'

function TimelineSection({ icon, title, children }) {
  return (
    <section className="vsl-stitch__preview-section">
      <div className="vsl-stitch__preview-node" aria-hidden="true" />
      <div className="vsl-stitch__timeline-card">
        <h4 className="vsl-stitch__preview-heading">
          <span className="vsl-stitch__preview-icon" aria-hidden="true">
            {icon}
          </span>
          {title}
        </h4>
        {children}
      </div>
    </section>
  )
}

function EditableLines({ items, onChange, placeholder }) {
  const lines = items?.length ? items : ['']
  return (
    <div className="vsl-stitch__editable-lines">
      {lines.map((line, i) => (
        <textarea
          key={i}
          className="vsl-stitch__field vsl-stitch__field--inline"
          rows={2}
          value={line}
          placeholder={placeholder}
          onChange={(e) => onChange(i, e.target.value)}
        />
      ))}
    </div>
  )
}

export function VoiceSessionPreviewScreen({
  structuredSession,
  onChange,
  isLateSession,
  lateReason,
  onLateReasonChange,
  error,
  childName,
  caseCode,
}) {
  const preview = useMemo(() => buildFamilyPreview(structuredSession), [structuredSession])
  const familyEmpty =
    !preview.worked_on.length &&
    !preview.appeared_helpful.length &&
    !preview.strength_highlight.length &&
    !preview.looking_ahead.length

  function editField(field, index, value) {
    if (!onChange) return
    onChange(updateFamilyPreviewLine(structuredSession, field, index, value))
  }

  function ensureLine(field) {
    if (!onChange) return
    const p = buildFamilyPreview(structuredSession)
    if ((p[field] || []).length) return
    onChange(applyFamilyPreviewEdits(structuredSession, { ...p, [field]: [''] }))
  }

  return (
    <div className="vsl-stitch__preview-page">
      <header className="vsl-stitch__preview-header">
        <div>
          <h2 className="vsl-stitch__preview-title">{childName || 'Family update'}</h2>
          <p className="vsl-stitch__preview-meta">
            {caseCode ? `Case ${caseCode}` : ''}
            {structuredSession.session_id ? ` · Session ${structuredSession.session_id}` : ''}
          </p>
        </div>
        <span className="vsl-stitch__badge vsl-stitch__badge--mint">Clinician verified preview</span>
      </header>

      <p className="vsl-stitch__preview-lead">
        Edit each section before submit — only confirmed, parent-safe evidence is shown here.
      </p>

      {familyEmpty ? (
        <div className="vsl-stitch__banner vsl-stitch__banner--review">
          Confirm at least one goal or add today&apos;s narrative in the draft step first.
        </div>
      ) : (
        <div className="vsl-stitch__preview-timeline">
          <TimelineSection icon="◎" title="What we worked on">
            <EditableLines
              items={preview.worked_on}
              placeholder="What goals or activities were addressed today?"
              onChange={(i, v) => editField('worked_on', i, v)}
            />
            <button type="button" className="vsl-stitch__text-link" onClick={() => ensureLine('worked_on')}>
              + Add line
            </button>
          </TimelineSection>

          <TimelineSection icon="◈" title="What appeared helpful">
            <EditableLines
              items={preview.appeared_helpful}
              placeholder="Supports or strategies that seemed helpful"
              onChange={(i, v) => editField('appeared_helpful', i, v)}
            />
          </TimelineSection>

          <TimelineSection icon="✦" title="Strength or participation highlight">
            <EditableLines
              items={preview.strength_highlight}
              placeholder="Observable strength or participation moment"
              onChange={(i, v) => editField('strength_highlight', i, v)}
            />
          </TimelineSection>

          <TimelineSection icon="→" title="Looking ahead">
            <EditableLines
              items={preview.looking_ahead}
              placeholder="What to watch for or try next session"
              onChange={(i, v) => editField('looking_ahead', i, v)}
            />
          </TimelineSection>
        </div>
      )}

      <p className="vsl-stitch__preview-footnote">
        Transcript, internal reflection, unapproved emerging goals, and CM flags stay off the family portal.
      </p>

      {isLateSession ? (
        <div className="vsl-stitch__banner vsl-stitch__banner--review">
          Past-day visit — add a late reason before submitting.
          <textarea
            className="vsl-stitch__field vsl-stitch__field--inline"
            style={{ marginTop: 10 }}
            placeholder="Why is this log late?"
            value={lateReason || ''}
            onChange={(e) => onLateReasonChange?.(e.target.value)}
          />
        </div>
      ) : null}

      {error ? <p className="vsl-stitch__error">{error}</p> : null}
    </div>
  )
}
