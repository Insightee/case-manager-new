const DEFAULT_CATEGORIES = []

export function ServiceCategoryPicker({ categories = DEFAULT_CATEGORIES, value = [], onChange, disabled }) {
  function toggle(id) {
    if (disabled) return
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id))
    } else {
      onChange([...value, id])
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
      {categories.map((cat) => {
        const active = value.includes(cat.id)
        return (
          <button
            key={cat.id}
            type="button"
            disabled={disabled}
            onClick={() => toggle(cat.id)}
            style={{
              padding: '6px 12px',
              borderRadius: 20,
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: disabled ? 'not-allowed' : 'pointer',
              border: active ? '2px solid #4f46e5' : '1px solid #d1d5db',
              background: active ? '#eef2ff' : '#fff',
              color: active ? '#3730a3' : '#374151',
              opacity: disabled ? 0.6 : 1,
            }}
          >
            {cat.label}
          </button>
        )
      })}
    </div>
  )
}
