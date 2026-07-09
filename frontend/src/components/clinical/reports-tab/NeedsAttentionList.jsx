import { attentionAccent } from '../../../lib/caseReportsCompose.js'

function dueBadgeLabel(item) {
  if (item.priority === 'overdue') return 'Overdue'
  if (item.priority === 'needs_changes') return 'Feedback received'
  if (item.priority === 'pending_cm_approval') return 'Pending CM'
  if (item.priority === 'upcoming_review') return 'Upcoming'
  if (item.due_date) {
    try {
      const due = new Date(`${item.due_date}T00:00:00`)
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const days = Math.round((due - today) / 86400000)
      if (days < 0) return `Overdue · ${Math.abs(days)}d ago`
      if (days === 0) return 'Due today'
      if (days <= 7) return `Due in ${days} day${days === 1 ? '' : 's'}`
    } catch {
      /* fall through */
    }
  }
  return item.status_label || 'Needs attention'
}

export function NeedsAttentionList({ items = [], hasMore = false, onAction, onViewAll }) {
  if (!items.length) return null

  return (
    <section className="crt-attention" aria-labelledby="crt-attention-heading">
      <div className="crt-attention__head">
        <h2 id="crt-attention-heading" className="crt-section-title">
          <span
            className="material-symbols-outlined crt-attention__icon"
            aria-hidden="true"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            error
          </span>
          Needs Your Attention
        </h2>
        <span className="crt-attention__count">
          {items.length} task{items.length === 1 ? '' : 's'}
        </span>
      </div>
      <ul className="crt-attention__grid">
        {items.map((item) => {
          const accent = attentionAccent(item.priority)
          const isFeedback = item.priority === 'needs_changes' && item.summary
          const isUpcoming = item.priority === 'upcoming_review' || accent === 'secondary'

          return (
            <li key={item.id}>
              <article className={`crt-attention-card crt-attention-card--${accent}`}>
                <div className="crt-attention-card__top">
                  <span className={`crt-attention-card__badge crt-attention-card__badge--${accent}`}>
                    {dueBadgeLabel(item)}
                  </span>
                </div>
                <h3 className="crt-attention-card__title">{item.title}</h3>
                {item.summary && !isFeedback ? (
                  <p className="crt-attention-card__body">{item.summary}</p>
                ) : null}
                {isFeedback ? (
                  <div className="crt-attention-card__quote">
                    <span className="material-symbols-outlined" aria-hidden="true">comment</span>
                    <span className="crt-attention-card__quote-text">“{item.summary}”</span>
                  </div>
                ) : null}
                {isUpcoming && !isFeedback ? (
                  <button
                    type="button"
                    className="crt-attention-card__btn"
                    onClick={() => onAction?.(item)}
                  >
                    {item.cta_label || 'Prepare'}
                  </button>
                ) : (
                  <div className="crt-attention-card__foot">
                    <button
                      type="button"
                      className="crt-attention-card__cta"
                      onClick={() => onAction?.(item)}
                    >
                      {item.cta_label || 'Open'}
                      <span className="material-symbols-outlined" aria-hidden="true">arrow_forward</span>
                    </button>
                  </div>
                )}
              </article>
            </li>
          )
        })}
      </ul>
      {hasMore ? (
        <button type="button" className="crt-link-btn" onClick={onViewAll}>
          View all pending
        </button>
      ) : null}
    </section>
  )
}
