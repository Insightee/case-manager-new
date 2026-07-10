import { useCallback, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { apiFetch } from '../../lib/apiClient.js'
import { fetchAllPages } from '../../lib/listApi.js'
import './case-combobox.css'

const DROPDOWN_GAP = 6
const POOL_TTL_MS = 5 * 60 * 1000
const MODULE_LABELS = {
  homecare: 'Homecare',
  shadow_support: 'Shadow',
  b2b: 'B2B',
  billing: 'Billing',
}

/** Shared in-memory case pools so reopen/filter stays instant. */
const casePools = {
  all: { items: null, loadedAt: 0, promise: null },
  assigned: { items: null, loadedAt: 0, promise: null },
}

function poolKey(assignedOnly) {
  return assignedOnly ? 'assigned' : 'all'
}

function isPoolFresh(entry) {
  return Array.isArray(entry.items) && Date.now() - entry.loadedAt < POOL_TTL_MS
}

async function loadCasePool(assignedOnly, { force = false } = {}) {
  const key = poolKey(assignedOnly)
  const entry = casePools[key]
  if (!force && isPoolFresh(entry)) return entry.items
  if (!force && entry.promise) return entry.promise

  entry.promise = fetchAllPages(
    (page, pageSize) => {
      const qs = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
      if (assignedOnly) qs.set('assigned', 'true')
      return apiFetch(`/api/v1/cases?${qs.toString()}`)
    },
    { pageSize: 100, maxPages: 100 },
  )
    .then(({ items }) => {
      entry.items = items
      entry.loadedAt = Date.now()
      entry.promise = null
      return items
    })
    .catch((err) => {
      entry.promise = null
      throw err
    })

  return entry.promise
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

function caseMatchesQuery(c, query) {
  const q = query.trim().toLowerCase()
  if (!q) return true
  const hay = [
    c.case_code,
    c.child_name,
    c.therapist_name,
    c.product_module,
    MODULE_LABELS[c.product_module],
    c.service_type,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return q.split(/\s+/).filter(Boolean).every((tok) => hay.includes(tok))
}

/**
 * Searchable case picker backed by a local case pool.
 * Loads all accessible cases once, then filters/scrolls in memory.
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
  const [pool, setPool] = useState(() => casePools[poolKey(assignedOnly)].items || [])
  const [selectedCase, setSelectedCase] = useState(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [activeIndex, setActiveIndex] = useState(-1)

  const dropdownPos = useDropdownPosition(open, inputRef)

  const ensurePool = useCallback(
    async ({ force = false } = {}) => {
      const cached = casePools[poolKey(assignedOnly)]
      if (!force && isPoolFresh(cached)) {
        setPool(cached.items)
        setLoadError('')
        return cached.items
      }
      setLoading(true)
      setLoadError('')
      try {
        const items = await loadCasePool(assignedOnly, { force })
        setPool(items)
        return items
      } catch (err) {
        setLoadError(err.message || 'Could not load cases')
        if (!casePools[poolKey(assignedOnly)].items) setPool([])
        return []
      } finally {
        setLoading(false)
      }
    },
    [assignedOnly],
  )

  // Prefetch pool when the picker mounts so open feels instant.
  useEffect(() => {
    ensurePool()
  }, [ensurePool])

  useEffect(() => {
    if (!value) {
      setSelectedCase(null)
      return
    }
    if (selectedCase && String(selectedCase.id) === String(value)) return
    const fromPool = pool.find((c) => String(c.id) === String(value))
    if (fromPool) {
      setSelectedCase(fromPool)
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
  }, [value, pool, selectedCase])

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
    // Refresh if stale when opening; otherwise use cached pool.
    ensurePool()
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
  }, [open, listId, value, selectedCase, ensurePool])

  const filtered = useMemo(() => pool.filter((c) => caseMatchesQuery(c, search)), [pool, search])

  const options = useMemo(() => {
    if (allowNone) return [{ __none: true }, ...filtered]
    return filtered
  }, [allowNone, filtered])

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

  const showDropdown = open
  const showEmpty = !loading && filtered.length === 0

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
            {loading && pool.length === 0 ? (
              <li className="case-combobox__status" role="option">
                Loading cases…
              </li>
            ) : loadError && pool.length === 0 ? (
              <li className="case-combobox__status case-combobox__status--empty" role="option">
                {loadError}
              </li>
            ) : showEmpty ? (
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
                  {search.trim()
                    ? 'No matching cases — try a client name, therapist name, or case code (e.g. SS for shadow).'
                    : 'No cases available.'}
                </li>
              </>
            ) : (
              <>
                {loading ? (
                  <li className="case-combobox__status" role="option">
                    Refreshing cases…
                  </li>
                ) : null}
                {options.map((item, i) => {
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
                })}
              </>
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
        onFocus={() => setOpen(true)}
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
