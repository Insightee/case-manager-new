export function AdminToolbar({ children, className = '' }) {
  return <div className={`admin-toolbar ${className}`.trim()}>{children}</div>
}

/** @param {string} value @param {(value: string) => void} onChange */
export function AdminSearchInput({ value, onChange, placeholder = 'Search…', className = '' }) {
  return (
    <label className={`admin-search admin-filter-field ${className}`.trim()}>
      <span className="admin-filter-field__label">Search</span>
      <input
        type="search"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="admin-search__input"
      />
    </label>
  )
}
