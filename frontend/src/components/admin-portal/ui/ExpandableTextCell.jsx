import { useState } from 'react'

const LONG_TEXT_COLUMNS = new Set(['Description', 'Subject', 'Notes', 'Body'])

/** Clamp long report cells; click to expand full text. */
export function ExpandableTextCell({ value, column, clampChars = 120 }) {
  const text = value == null ? '' : String(value)
  const [expanded, setExpanded] = useState(false)
  const isLongCol = LONG_TEXT_COLUMNS.has(column)
  const needsClamp = isLongCol && text.length > clampChars

  if (!needsClamp) {
    return <span className={isLongCol ? 'admin-hr-reports__cell-text' : undefined}>{text || '—'}</span>
  }

  if (!expanded) {
    return (
      <button
        type="button"
        className="admin-hr-reports__expand-cell"
        onClick={() => setExpanded(true)}
        aria-expanded={false}
        title="Show full text"
      >
        <span className="admin-hr-reports__cell-text admin-hr-reports__cell-text--clamp">
          {text.slice(0, clampChars).trimEnd()}…
        </span>
        <span className="admin-hr-reports__expand-hint">Show more</span>
      </button>
    )
  }

  return (
    <div className="admin-hr-reports__expand-cell admin-hr-reports__expand-cell--open">
      <span className="admin-hr-reports__cell-text">{text}</span>
      <button
        type="button"
        className="admin-hr-reports__expand-hint"
        onClick={() => setExpanded(false)}
        aria-expanded
      >
        Show less
      </button>
    </div>
  )
}

export function isLongTextColumn(column) {
  return LONG_TEXT_COLUMNS.has(column)
}
