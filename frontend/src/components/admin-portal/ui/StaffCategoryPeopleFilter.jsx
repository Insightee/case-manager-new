import { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import { FilterSelect } from './FilterSelect.jsx'
import { MultiSelect } from './MultiSelect.jsx'
import './admin-multiselect.css'

export const STAFF_CATEGORY_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'ADMIN', label: 'Admin' },
  { value: 'CASE_MANAGER', label: 'Case manager' },
  { value: 'THERAPIST', label: 'Therapist' },
]

/** Maps directory role category → meetings participant_role query value. */
export const STAFF_CATEGORY_TO_PARTICIPANT_ROLE = {
  ADMIN: 'admin',
  CASE_MANAGER: 'case_manager',
  THERAPIST: 'therapist',
}

function unwrapDirectoryRows(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  return []
}

/**
 * Category select + people MultiSelect for admin meeting filters.
 */
export function StaffCategoryPeopleFilter({
  category = '',
  onCategoryChange,
  peopleIds = [],
  onPeopleChange,
  className = '',
}) {
  const [people, setPeople] = useState([])
  const [loadingPeople, setLoadingPeople] = useState(false)

  useEffect(() => {
    if (!category) {
      setPeople([])
      setLoadingPeople(false)
      return undefined
    }

    let cancelled = false
    setLoadingPeople(true)
    apiFetch(`/api/v1/admin/users/directory?roles=${encodeURIComponent(category)}`)
      .then((payload) => {
        if (cancelled) return
        setPeople(unwrapDirectoryRows(payload))
      })
      .catch(() => {
        if (!cancelled) setPeople([])
      })
      .finally(() => {
        if (!cancelled) setLoadingPeople(false)
      })

    return () => {
      cancelled = true
    }
  }, [category])

  const peopleOptions = useMemo(
    () =>
      people.map((person) => ({
        value: String(person.id),
        label: person.full_name || person.email || `User ${person.id}`,
      })),
    [people],
  )

  function handleCategoryChange(event) {
    const next = event.target.value
    onCategoryChange?.(next)
    onPeopleChange?.([])
  }

  return (
    <div className={`admin-staff-people-filter ${className}`.trim()}>
      <FilterSelect
        label="Category"
        value={category}
        onChange={handleCategoryChange}
        options={STAFF_CATEGORY_OPTIONS}
        id="meetings-staff-category"
      />
      <MultiSelect
        label="People"
        id="meetings-staff-people"
        options={peopleOptions}
        values={peopleIds}
        onChange={onPeopleChange}
        placeholder={category ? (loadingPeople ? 'Loading…' : 'All') : 'Select a category'}
        disabled={!category || loadingPeople}
      />
    </div>
  )
}
