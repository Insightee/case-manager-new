export function InsightSelectCheckbox({ insightId, checked, onToggle, label }) {
  if (!insightId) return null
  return (
    <label className="ci-select-check">
      <input
        type="checkbox"
        checked={checked}
        onChange={() => onToggle(insightId)}
        aria-label={label || 'Select insight for report'}
      />
      <span className="ci-select-check__box" aria-hidden="true">
        <span className="material-symbols-outlined">check</span>
      </span>
    </label>
  )
}
