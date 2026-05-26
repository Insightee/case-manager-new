import { useEffect, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'

export function AdminFamilyCombobox({ value, onChange, onSelectFamily, placeholder = 'Search child or parent…' }) {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [families, setFamilies] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    setLoading(true)
    const qs = debounced ? `?search=${encodeURIComponent(debounced)}` : ''
    apiFetch(`/api/v1/admin/families${qs}`)
      .then((rows) => {
        const list = Array.isArray(rows) ? rows : []
        const byId = new Map()
        for (const f of list) {
          if (!byId.has(f.childId)) byId.set(f.childId, f)
        }
        setFamilies([...byId.values()])
      })
      .catch(() => setFamilies([]))
      .finally(() => setLoading(false))
  }, [debounced])

  const selected = families.find((f) => String(f.childId) === String(value))

  return (
    <div style={{ position: 'relative' }}>
      <input
        type="search"
        className="admin-input"
        placeholder={placeholder}
        value={search}
        onChange={(e) => {
          setSearch(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
      />
      {value && selected ? (
        <p className="admin-muted" style={{ fontSize: '0.8rem', marginTop: 4 }}>
          Selected: {selected.childName} (#{selected.childId})
          {selected.parents?.[0]?.parentEmail ? ` · ${selected.parents[0].parentEmail}` : ''}
        </p>
      ) : null}
      {open && (search || families.length) ? (
        <ul
          className="admin-panel"
          style={{
            position: 'absolute',
            zIndex: 20,
            left: 0,
            right: 0,
            marginTop: 4,
            maxHeight: 240,
            overflowY: 'auto',
            listStyle: 'none',
            padding: 0,
          }}
        >
          {loading ? (
            <li style={{ padding: 12, fontSize: '0.85rem', color: '#64748b' }}>Searching…</li>
          ) : families.length === 0 ? (
            <li style={{ padding: 12, fontSize: '0.85rem', color: '#b45309' }}>No matches — try another term or add a new family.</li>
          ) : (
            families.map((f) => (
              <li key={f.childId}>
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost"
                  style={{ width: '100%', textAlign: 'left', borderRadius: 0, justifyContent: 'flex-start' }}
                  onClick={() => {
                    onChange(String(f.childId))
                    onSelectFamily?.(f)
                    setSearch(f.childName)
                    setOpen(false)
                  }}
                >
                  <strong>{f.childName}</strong>
                  <span className="admin-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                    #{f.childId}
                    {f.parents?.[0]?.parentEmail ? ` · ${f.parents[0].parentEmail}` : ' · no parent'}
                    {f.caseCodes?.length ? ` · ${f.caseCodes.join(', ')}` : ''}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  )
}
