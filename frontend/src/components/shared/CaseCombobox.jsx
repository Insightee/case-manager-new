import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { unwrapList } from '../../lib/listApi.js'
import './case-combobox.css'

const DROPDOWN_GAP = 6
const MODULE_LABELS = {
  homecare: 'Homecare',
  shadow_support: 'Shadow',
  b2b: 'B2B',
  billing: 'Billing',
}

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
        className: 'case-combobox__dropdown--up',
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

function formatCaseLabel(c) {
  if (!c) return ''
  return [c.case_code, c.child_name].filter(Boolean).join(' · ')
}

function formatCaseMeta(c) {
  if (!c) return ''
  const parts = []
  const mod = MODULE_LABELS[c.product_module] || c.product_module
  if (mod) parts.push(mod)
  if (c.therapist_name) parts.push(`Therapist: ${c.therapist_name}`)
  return parts.join(' · ')
}

/**
 * Searchable case picker — queries GET /api/v1/cases?search=…
 * Matches case code, client name, or active therapist name.
 */
export function CaseCombobox({
  value,
  onChange,
  assignedOnly = false,
  allowNone = true,
  noneLabel = 'Not linked to a case',
  placeholder = 'Search client, therapist, or case code…',
  disabled = false,
}) {
  const listId = useId().replace(/:/g, '')
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [activeIndex, setActiveIndex] = useState(-1)

  const dropdownPos = useDropdownPosition(open, inputRef)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 280)
    return () => clearTimeout(t)
  }, [search])

  useEffect(() => {
    if (!value) {
      setSelectedCase(null)
      return
    }
    if (selectedCase && String(selectedCase.id) === String(value)) return
    const fromList = cases.find((c) => String(c.id) === String(value))
    if (fromList) {
      setSelectedCase(fromList)
      return
    }
    let cancelled = false
    apiFetch(`/api/v1/cases/${value}`)
      .then((c) => {
        if (!cancelled && c) setSelectedCase(c)
      })
      .catch(() => {
        if (!cancelled) setSelectedCase(null)
      })
    return () => {
      cancelled = true
    }
  }, [value, cases, selectedCase])

  useEffect(() => {
    if (value && selectedCase && String(selectedCase.id) === String(value) && !open) {
      setSearch(formatCaseLabel(selectedCase))
    }
    if (!value && !open) {
      setSearch('')
    }
  }, [value, selectedCase, open])

  useEffect(() => {
    if (!open) return undefined
    setLoading(true)
    const qs = new URLSearchParams({ page_size: '50', page: '1' })
    if (assignedOnly) qs.set('assigned', 'true')
    if (debounced) qs.set('search', debounced)
    let cancelled = false
    apiFetch(`/api/v1/cases?${qs.toString()}`)
      .then((data) => {
        if (!cancelled) setCases(unwrapList(data))
      })
      .catch(() => {
        if (!cancelled) setCases([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [debounced, assignedOnly, open])

  useEffect(() => {
    if (!open) return undefined
    const onDoc = (e) => {
      if (rootRef.current?.contains(e.target)) return
      const portal = document.getElementById(`case-combo-portal-${listId}`)
      if (portal?.contains(e.target)) return
      setOpen(false)
      if (value && selectedCase) setSearch(formatCaseLabel(selectedCase))
      else if (!value) setSearch('')
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [open, listId, value, selectedCase])

  function selectNone() {
    onChange('')
    setSelectedCase(null)
    setSearch('')
    setOpen(false)
    setActiveIndex(-1)
  }

  function selectCase(c) {
    onChange(String(c.id))
    setSelectedCase(c)
    setSearch(formatCaseLabel(c))
    setOpen(false)
    setActiveIndex(-1)
  }

  const options = allowNone ? [{ __none: true }, ...cases] : cases
  const showDropdown = open

  const dropdown =
    showDropdown && dropdownPos && typeof document !== 'undefined'
      ? createPortal(
          <ul
            id={`case-combo-portal-${listId}`}
            className={`case-combobox__dropdown ${dropdownPos.className}`.trim()}
            role="listbox"
            style={{
              top: dropdownPos.top,
              left: dropdownPos.left,
              width: dropdownPos.width,
              maxHeight: dropdownPos.maxHeight,
            }}
          >
            {loading ? (
              <li className="case-combobox__status" role="option">
                Searching…
              </li>
            ) : options.length === 0 || (options.length === 1 && options[0].__none && cases.length === 0 && debounced) ? (
              <>
                {allowNone ? (
                  <li role="option" aria-selected={!value}>
                    <button
                      type="button"
                      className={`case-combobox__option${activeIndex === 0 ? ' case-combobox__option--active' : ''}`}
                      onMouseEnter={() => setActiveIndex(0)}
                      onClick={selectNone}
                    >
                      <span className="case-combobox__option-name">{noneLabel}</span>
                    </button>
                  </li>
                ) : null}
                <li className="case-combobox__status case-combobox__status--empty" role="option">
                  {debounced
                    ? 'No matching cases — try a client name, therapist name, or case code (e.g. SS for shadow).'
                    : 'No cases available.'}
                </li>
              </>
            ) : (
              options.map((item, i) => {
                if (item.__none) {
                  return (
                    <li key="none" role="option" aria-selected={!value}>
                      <button
                        type="button"
                        className={`case-combobox__option${i === activeIndex ? ' case-combobox__option--active' : ''}`}
                        onMouseEnter={() => setActiveIndex(i)}
                        onClick={selectNone}
                      >
                        <span className="case-combobox__option-name">{noneLabel}</span>
                      </button>
                    </li>
                  )
                }
                return (
                  <li key={item.id} role="option" aria-selected={String(item.id) === String(value)}>
                    <button
                      type="button"
                      className={`case-combobox__option${i === activeIndex ? ' case-combobox__option--active' : ''}`}
                      onMouseEnter={() => setActiveIndex(i)}
                      onClick={() => selectCase(item)}
                    >
                      <span className="case-combobox__option-name">{formatCaseLabel(item)}</span>
                      <span className="case-combobox__option-meta">{formatCaseMeta(item)}</span>
                    </button>
                  </li>
                )
              })
            )}
          </ul>,
          document.body,
        )
      : null

  return (
    <div className="case-combobox" ref={rootRef}>
      <input
        ref={inputRef}
        type="search"
        className="admin-input case-combobox__input"
        placeholder={placeholder}
        value={search}
        disabled={disabled}
        autoComplete="off"
        aria-expanded={showDropdown}
        aria-controls={showDropdown ? `case-combo-portal-${listId}` : undefined}
        aria-autocomplete="list"
        aria-label="Link case"
        onChange={(e) => {
          setSearch(e.target.value)
          setOpen(true)
          setActiveIndex(-1)
          if (!e.target.value.trim()) {
            onChange('')
            setSelectedCase(null)
          }
        }}
        onFocus={() => {
          setOpen(true)
          if (value && selectedCase) {
            // Keep label until user types; still open list for browsing
          }
        }}
        onKeyDown={(e) => {
          if (!open || !options.length) return
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActiveIndex((i) => (i + 1) % options.length)
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActiveIndex((i) => (i <= 0 ? options.length - 1 : i - 1))
          } else if (e.key === 'Enter' && activeIndex >= 0) {
            e.preventDefault()
            const item = options[activeIndex]
            if (item?.__none) selectNone()
            else if (item) selectCase(item)
          } else if (e.key === 'Escape') {
            setOpen(false)
            if (value && selectedCase) setSearch(formatCaseLabel(selectedCase))
          }
        }}
      />
      {value && selectedCase ? (
        <p className="case-combobox__selected">
          <strong>{formatCaseLabel(selectedCase)}</strong>
          {formatCaseMeta(selectedCase) ? (
            <>
              <br />
              {formatCaseMeta(selectedCase)}
            </>
          ) : null}
        </p>
      ) : null}
      {dropdown}
    </div>
  )
}
