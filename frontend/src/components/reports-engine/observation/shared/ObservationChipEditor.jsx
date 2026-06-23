import { useState } from 'react'

export function ObservationChipEditor({ label, items = [], onChange, readOnly, placeholder = '+ Add' }) {
  const [draft, setDraft] = useState('')

  function addItem() {
    const v = draft.trim()
    if (!v || readOnly) return
    onChange([...items, v])
    setDraft('')
  }

  function removeItem(idx) {
    if (readOnly) return
    onChange(items.filter((_, i) => i !== idx))
  }

  return (
    <div className="ob-chips">
      <p className="ob-label">{label}</p>
      <div className="ob-chips__list">
        {items.map((item, idx) => (
          <span key={`${item}-${idx}`} className="ob-chip">
            {item}
            {!readOnly ? (
              <button type="button" className="ob-chip__remove" onClick={() => removeItem(idx)} aria-label={`Remove ${item}`}>
                ×
              </button>
            ) : null}
          </span>
        ))}
      </div>
      {!readOnly ? (
        <div className="ob-chips__add">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addItem())}
          />
          <button type="button" className="ob-btn-secondary" onClick={addItem}>Add</button>
        </div>
      ) : null}
    </div>
  )
}
