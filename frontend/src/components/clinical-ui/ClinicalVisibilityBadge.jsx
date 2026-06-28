const VISIBILITY_MAP = {
  parent:   { cls: 'parent',   label: 'Parent Visible' },
  internal: { cls: 'internal', label: 'Internal Only' },
  cm:       { cls: 'cm-only',  label: 'CM Only' },
  draft:    { cls: 'draft',    label: 'Draft Only' },
}

/**
 * visibility: 'parent' | 'internal' | 'cm' | 'draft'
 */
export function ClinicalVisibilityBadge({ visibility }) {
  const entry = VISIBILITY_MAP[visibility] || VISIBILITY_MAP.internal
  return (
    <span className={`clinical-visibility-badge clinical-visibility-badge--${entry.cls}`}>
      {entry.label}
    </span>
  )
}
