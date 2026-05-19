export function AdminToolbar({ children, className = '' }) {
  return <div className={`admin-toolbar ${className}`.trim()}>{children}</div>
}

export function AdminSearchInput({ value, onChange, placeholder = 'Search…' }) {
  return (
    <label className="admin-search">
      <span className="sr-only">Search</span>
      <input
        type="search"
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="admin-search__input"
      />
    </label>
  )
}
