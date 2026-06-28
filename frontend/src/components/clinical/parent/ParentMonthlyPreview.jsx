import { useNavigate } from 'react-router-dom'
import { ClinicalVisibilityBadge } from '../../clinical-ui/ClinicalVisibilityBadge.jsx'

/**
 * Parent-safe monthly report preview.
 * Only server-filtered parent-visible content is shown.
 * Actions: Back to Builder, Share for Review (submit to CM), Publish to Parent (CM only), Download PDF (if route exists).
 */
export function ParentMonthlyPreview({ preview, reportId, isCM = false, onBack, onSubmitToCM, onPublish, hasPdfRoute = false }) {
  const navigate = useNavigate()

  if (!preview) return null

  return (
    <section className="clinical-doc-canvas" aria-labelledby="parent-preview-title">
      {/* Document header */}
      <div className="clinical-doc-canvas__header">
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div>
            <h2 className="clinical-doc-canvas__report-title" id="parent-preview-title">
              {preview.child_name ? `${preview.child_name} — ` : ''}Monthly Progress Report
            </h2>
            {preview.report_period ? (
              <p className="clinical-doc-canvas__meta">{preview.report_period}</p>
            ) : null}
            {preview.preview_note ? (
              <p className="clinical-doc-canvas__meta" style={{ marginTop: '0.25rem' }}>{preview.preview_note}</p>
            ) : null}
          </div>
          <ClinicalVisibilityBadge visibility="parent" />
        </div>
      </div>

      {/* Report sections */}
      <div>
        {(preview.sections || []).map((s) => (
          <div key={s.section_key} className="clinical-doc-canvas__section">
            <h3 className="clinical-doc-canvas__section-title">
              {s.section_key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </h3>
            <div
              style={{ fontSize: '0.9375rem', color: '#334155', lineHeight: 1.7 }}
              dangerouslySetInnerHTML={{ __html: s.content_html }}
            />
          </div>
        ))}
      </div>

      {/* Sticky action bar */}
      <div className="cp-builder-sticky-actions" style={{ borderTop: '1px solid var(--clinical-border)', paddingTop: '0.875rem', marginTop: '1rem' }}>
        {onBack ? (
          <button type="button" className="clinical-btn-ghost" onClick={onBack}>
            ← Back to Builder
          </button>
        ) : null}
        {onSubmitToCM ? (
          <button type="button" className="clinical-btn-secondary" onClick={onSubmitToCM}>
            Share for Review
          </button>
        ) : null}
        {isCM && onPublish ? (
          <button type="button" className="clinical-btn-primary" onClick={onPublish}>
            Publish to Parent
          </button>
        ) : null}
        {hasPdfRoute && reportId ? (
          <a
            href={`/api/v1/reports/monthly/${reportId}/download`}
            className="clinical-btn-ghost"
            download
            style={{ fontSize: '0.8125rem', minHeight: '36px' }}
          >
            Download PDF
          </a>
        ) : null}
      </div>
    </section>
  )
}
