import { useState } from 'react'
import { MODAL_INPUT_STYLE } from './meetingConstants.js'

const ROLE_BADGE = {
  SUPER_ADMIN: { label: 'Super admin', bg: '#fef3c7', color: '#92400e' },
  ADMIN: { label: 'Admin', bg: '#ede9fe', color: '#5b21b6' },
  MODULE_ADMIN: { label: 'Module admin', bg: '#ede9fe', color: '#5b21b6' },
  CASE_MANAGER: { label: 'Case manager', bg: '#dcfce7', color: '#166534' },
}

function roleBadge(role) {
  const s = ROLE_BADGE[role] || { label: role, bg: '#f1f5f9', color: '#475569' }
  return (
    <span style={{ fontSize: '0.65rem', fontWeight: 600, padding: '2px 6px', borderRadius: 999, background: s.bg, color: s.color }}>
      {s.label}
    </span>
  )
}

export function StaffAttendeePicker({
  users,
  selectedIds,
  onChange,
  loading = false,
  emptyMessage = 'No staff available to invite.',
  searchPlaceholder = 'Search by name…',
}) {
  const [search, setSearch] = useState('')

  const filtered = users.filter((u) => {
    const q = search.trim().toLowerCase()
    if (!q) return true
    return (
      String(u.full_name || '').toLowerCase().includes(q)
      || String(u.email || '').toLowerCase().includes(q)
    )
  })

  function toggle(id) {
    const n = Number(id)
    if (selectedIds.includes(n)) {
      onChange(selectedIds.filter((x) => x !== n))
    } else {
      onChange([...selectedIds, n])
    }
  }

  if (loading) {
    return <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '4px 0 0 24px' }}>Loading staff…</p>
  }

  if (!users.length) {
    return <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '4px 0 0 24px' }}>{emptyMessage}</p>
  }

  return (
    <div style={{ marginLeft: 24, marginBottom: 8 }}>
      <input
        type="search"
        style={{ ...MODAL_INPUT_STYLE, marginBottom: 8, fontSize: '0.8rem' }}
        placeholder={searchPlaceholder}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      <div style={{ maxHeight: 160, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 10, padding: '6px 8px' }}>
        {filtered.map((u) => {
          const primaryRole = (u.roles || []).find((r) => ROLE_BADGE[r]) || u.roles?.[0]
          const checked = selectedIds.includes(Number(u.id))
          return (
            <label
              key={u.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '6px 4px',
                fontSize: '0.875rem',
                cursor: 'pointer',
                borderRadius: 8,
                background: checked ? '#eef2ff' : 'transparent',
              }}
            >
              <input type="checkbox" checked={checked} onChange={() => toggle(u.id)} />
              <span style={{ flex: 1, fontWeight: checked ? 600 : 400 }}>{u.full_name || u.email}</span>
              {primaryRole ? roleBadge(primaryRole) : null}
            </label>
          )
        })}
        {filtered.length === 0 ? (
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: '8px 4px' }}>No matches for that search.</p>
        ) : null}
      </div>
    </div>
  )
}
