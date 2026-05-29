import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import './admin-family-combobox.css'

const DROPDOWN_GAP = 6

function useDropdownPosition(open, anchorRef) {
  const [style, setStyle] = useState(null)

  const update = useCallback(() => {
    const el = anchorRef.current
    if (!el || !open) {
      setStyle(null)
      return
    }
    const rect = el.getBoundingClientRect()
    const viewportH = window.innerHeight
    const spaceBelow = viewportH - rect.bottom - DROPDOWN_GAP
    const spaceAbove = rect.top - DROPDOWN_GAP
    const preferBelow = spaceBelow >= 160 || spaceBelow >= spaceAbove
    const maxHeight = Math.max(120, Math.min(400, preferBelow ? spaceBelow - 8 : spaceAbove - 8))

    if (preferBelow) {
      setStyle({
        top: rect.bottom + DROPDOWN_GAP,
        left: rect.left,
        width: rect.width,
        maxHeight,
        className: '',
      })
    } else {
      setStyle({
        top: Math.max(8, rect.top - DROPDOWN_GAP - maxHeight),
        left: rect.left,
        width: rect.width,
        maxHeight,
        className: 'admin-family-combobox__dropdown--up',
      })
    }
  }, [open, anchorRef])

  useLayoutEffect(() => {
    update()
    if (!open) return undefined
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [open, update])

  return style
}

export function AdminFamilyCombobox({ value, onChange, onSelectFamily, placeholder = 'Search child or parent…' }) {
  const listId = useId().replace(/:/g, '')
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [families, setFamilies] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  const dropdownPos = useDropdownPosition(open, inputRef)

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

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => {
      if (rootRef.current?.contains(e.target)) return
      const portal = document.getElementById(`family-combo-portal-${listId}`)
      if (portal?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, listId])

  const selected = families.find((f) => String(f.childId) === String(value))

  function selectFamily(f) {
    onChange(String(f.childId))
    onSelectFamily?.(f)
    setSearch(f.childName)
    setOpen(false)
    setActiveIndex(-1)
  }

  function formatMeta(f) {
    const parts = [`#${f.childId}`]
    if (f.parents?.[0]?.parentEmail) parts.push(f.parents[0].parentEmail)
    else parts.push('no parent on file')
    if (f.caseCodes?.length) parts.push(f.caseCodes.join(', '))
    return parts.join(' · ')
  }

  const showDropdown = open

  const dropdown =
    showDropdown && dropdownPos && typeof document !== 'undefined'
      ? createPortal(
          <ul
            id={`family-combo-portal-${listId}`}
            className={`admin-family-combobox__dropdown ${dropdownPos.className}`.trim()}
            role="listbox"
            style={{
              top: dropdownPos.top,
              left: dropdownPos.left,
              width: dropdownPos.width,
              maxHeight: dropdownPos.maxHeight,
            }}
          >
            {loading ? (
              <li className="admin-family-combobox__status" role="option">
                Searching…
              </li>
            ) : families.length === 0 ? (
              <li className="admin-family-combobox__status admin-family-combobox__status--empty" role="option">
                {debounced
                  ? 'No matches — try another name, email, or case code.'
                  : 'No clients yet — switch to New client or adjust your search.'}
              </li>
            ) : (
              families.map((f, i) => (
                <li key={f.childId} role="option" aria-selected={String(f.childId) === String(value)}>
                  <button
                    type="button"
                    className={`admin-family-combobox__option${i === activeIndex ? ' admin-family-combobox__option--active' : ''}`}
                    onMouseEnter={() => setActiveIndex(i)}
                    onClick={() => selectFamily(f)}
                  >
                    <span className="admin-family-combobox__option-name">{f.childName}</span>
                    <span className="admin-family-combobox__option-meta">{formatMeta(f)}</span>
                  </button>
                </li>
              ))
            )}
          </ul>,
          document.body,
        )
      : null

  return (
    <div className="admin-family-combobox" ref={rootRef}>
      <input
        ref={inputRef}
        type="search"
        className="admin-input admin-family-combobox__input"
        placeholder={placeholder}
        value={search}
        autoComplete="off"
        aria-expanded={showDropdown}
        aria-controls={showDropdown ? `family-combo-portal-${listId}` : undefined}
        aria-autocomplete="list"
        onChange={(e) => {
          setSearch(e.target.value)
          setOpen(true)
          setActiveIndex(-1)
          if (!e.target.value.trim()) onChange('')
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (!open || !families.length) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActiveIndex((i) => (i + 1) % families.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActiveIndex((i) => (i <= 0 ? families.length - 1 : i - 1))
          } else if (e.key === 'Enter' && activeIndex >= 0) {
            e.preventDefault()
            selectFamily(families[activeIndex])
          } else if (e.key === 'Escape') {
            setOpen(false)
          }
        }}
      />
      {value && selected ? (
        <p className="admin-family-combobox__selected">
          <strong>{selected.childName}</strong>
          <br />
          {formatMeta(selected)}
        </p>
      ) : null}
      {dropdown}
    </div>
  )
}
