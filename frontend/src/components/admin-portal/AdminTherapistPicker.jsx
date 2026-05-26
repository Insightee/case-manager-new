import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../lib/apiClient.js'
import './admin-therapist-picker.css'

function initials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}

const AVATAR_COLORS = [
  'bg-indigo-100 text-indigo-700',
  'bg-violet-100 text-violet-700',
  'bg-teal-100 text-teal-700',
  'bg-rose-100 text-rose-700',
  'bg-amber-100 text-amber-700',
  'bg-sky-100 text-sky-700',
]

function avatarColor(id) {
  return AVATAR_COLORS[Number(id) % AVATAR_COLORS.length]
}

function therapistMatchesSearch(t, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = `${t.therapist_name || t.full_name || ''} ${t.email || ''} ${t.therapist_user_id || ''}`.toLowerCase()
  const tokens = q.split(/\s+/).filter(Boolean)
  return tokens.every((tok) => hay.includes(tok))
}

export function AdminTherapistPicker({
  caseId,
  productModule,
  value,
  onChange,
  disabled,
  mode = 'allotment',
  compactThreshold = 80,
}) {
  const [therapists, setTherapists] = useState([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [searchDebounced, setSearchDebounced] = useState('')

  useEffect(() => {
    const t = setTimeout(() => setSearchDebounced(search.trim()), 250)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (mode === 'allotment' && productModule) {
      params.set('product_module', productModule)
      if (searchDebounced) params.set('search', searchDebounced)
      apiFetch(`/api/v1/admin/allotment/therapists?${params}`)
        .then(setTherapists)
        .catch(() => setTherapists([]))
        .finally(() => setLoading(false))
      return
    }
    if (caseId) {
      const qs = searchDebounced ? `&search=${encodeURIComponent(searchDebounced)}` : ''
      apiFetch(`/api/v1/booking/therapists?case_id=${caseId}${qs}`)
        .then(setTherapists)
        .catch(() => setTherapists([]))
        .finally(() => setLoading(false))
      return
    }
    setTherapists([])
    setLoading(false)
  }, [caseId, productModule, mode, searchDebounced])

  const filtered = useMemo(() => {
    return therapists.filter((t) => therapistMatchesSearch(t, search))
  }, [therapists, search])

  const selected = useMemo(() => {
    if (!value) return null
    return therapists.find((t) => String(t.therapist_user_id) === String(value)) || null
  }, [therapists, value])

  const useDropdown = filtered.length > compactThreshold

  const searchInput = (
    <div className="admin-therapist-picker__search">
      <input
        type="search"
        className="admin-input"
        placeholder="Search by name or email…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        disabled={disabled}
        aria-label="Search therapists"
      />
    </div>
  )

  if (mode === 'allotment') {
    if (!productModule) {
      return (
        <p className="admin-therapist-picker__hint admin-therapist-picker__hint--warn">
          Select a service module first.
        </p>
      )
    }
    return (
      <div className="admin-therapist-picker">
        {selected ? (
          <div className="admin-therapist-picker__selected">
            <span className={`admin-therapist-picker__avatar ${avatarColor(value)}`}>{initials(selected.therapist_name || selected.full_name)}</span>
            <span className="admin-therapist-picker__selected-text">
              <strong>{selected.therapist_name || selected.full_name}</strong>
              <span>{selected.email || `ID #${value}`}</span>
            </span>
            {!disabled ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={() => onChange('')}>
                Change
              </button>
            ) : null}
          </div>
        ) : null}
        {!selected || search ? (
          <>
            {searchInput}
            {loading ? <p className="admin-muted" style={{ fontSize: '0.85rem' }}>Loading therapists…</p> : null}
            {!loading && !filtered.length ? (
              <p className="admin-therapist-picker__hint admin-therapist-picker__hint--warn">
                No therapists match — try another search or approve profiles for this module.
              </p>
            ) : null}
            {!loading && filtered.length > 0 && useDropdown ? (
              <select
                className="admin-input"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                disabled={disabled}
              >
                <option value="">Select therapist…</option>
                {filtered.map((t) => (
                  <option key={t.therapist_user_id} value={String(t.therapist_user_id)}>
                    {t.therapist_name || t.full_name} · {t.email || `#${t.therapist_user_id}`}
                  </option>
                ))}
              </select>
            ) : null}
            {!loading && filtered.length > 0 && !useDropdown ? (
              <div className="admin-therapist-picker__grid">
                {filtered.map((t) => {
                  const tid = String(t.therapist_user_id)
                  const name = t.therapist_name || t.full_name || `Therapist #${tid}`
                  const isSelected = value === tid
                  return (
                    <button
                      key={tid}
                      type="button"
                      disabled={disabled}
                      onClick={() => onChange(isSelected ? '' : tid)}
                      className={`admin-therapist-picker__card ${isSelected ? 'admin-therapist-picker__card--selected' : ''}`}
                    >
                      <span className={`admin-therapist-picker__avatar ${avatarColor(tid)}`}>{initials(name)}</span>
                      <span className="admin-therapist-picker__card-body">
                        <span className="admin-therapist-picker__name">{name}</span>
                        <span className="admin-therapist-picker__email">{t.email || `ID #${tid}`}</span>
                      </span>
                    </button>
                  )
                })}
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    )
  }

  return (
    <div className="admin-therapist-picker">
      {searchInput}
      <select
        className="admin-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || loading || !caseId}
      >
        <option value="">{loading ? 'Loading therapists…' : 'Select therapist…'}</option>
        {filtered.map((t) => (
          <option key={t.therapist_user_id} value={String(t.therapist_user_id)}>
            {t.therapist_name || t.full_name || `Therapist #${t.therapist_user_id}`}
          </option>
        ))}
      </select>
    </div>
  )
}
