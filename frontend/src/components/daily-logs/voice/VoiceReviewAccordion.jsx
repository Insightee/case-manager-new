/** Collapsible review section — accordions on mobile, always expanded on desktop. */

export function VoiceReviewAccordion({ id, title, summaryLine, status, open, onToggle, children }) {
  const statusLabel =
    status === 'needs_review'
      ? 'Needs review'
      : status === 'confirmed'
        ? 'Reviewed'
        : status === 'optional'
          ? 'Optional'
          : null

  return (
    <section
      id={`vsl-section-${id}`}
      className={`vsl-stitch__accordion ${open ? 'vsl-stitch__accordion--open' : ''} vsl-stitch__accordion--${status}`}
    >
      <button
        type="button"
        className="vsl-stitch__accordion-head"
        aria-expanded={open}
        aria-controls={`vsl-section-body-${id}`}
        onClick={onToggle}
      >
        <span className="vsl-stitch__accordion-title">{title}</span>
        <span className="vsl-stitch__accordion-meta">
          {statusLabel ? (
            <span className={`vsl-stitch__badge ${status === 'needs_review' ? 'vsl-stitch__badge--review' : ''}`}>
              {statusLabel}
            </span>
          ) : null}
          <span className="vsl-stitch__accordion-summary">{summaryLine}</span>
          <span className="vsl-stitch__accordion-chevron" aria-hidden="true">
            {open ? '▾' : '▸'}
          </span>
        </span>
      </button>
      <div id={`vsl-section-body-${id}`} className="vsl-stitch__accordion-body">
        {children}
      </div>
    </section>
  )
}
