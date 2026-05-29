const ROLE_GROUP_ORDER = [
  { key: 'CASE_MANAGER', label: 'Case managers' },
  { key: 'SUPERVISOR', label: 'Supervisors' },
  { key: 'MODULE_ADMIN', label: 'Module admins' },
  { key: 'PROGRAMME_ADMIN', label: 'Programme admins' },
  { key: 'SUPER_ADMIN', label: 'Super admins' },
  { key: 'OTHER', label: 'Other staff' },
]

function primaryRole(roles = []) {
  const upper = roles.map((r) => String(r).toUpperCase())
  for (const g of ROLE_GROUP_ORDER) {
    if (g.key !== 'OTHER' && upper.includes(g.key)) return g.key
  }
  return 'OTHER'
}

function groupStaff(staff = []) {
  const buckets = Object.fromEntries(ROLE_GROUP_ORDER.map((g) => [g.key, []]))
  for (const person of staff) {
    buckets[primaryRole(person.roles)].push(person)
  }
  for (const key of Object.keys(buckets)) {
    buckets[key].sort((a, b) => (a.full_name || '').localeCompare(b.full_name || ''))
  }
  return buckets
}

function formatPersonLabel(person) {
  const role = (person.roles || [])[0]
  const roleLabel = role ? String(role).replace(/_/g, ' ') : ''
  return roleLabel ? `${person.full_name} · ${roleLabel}` : person.full_name
}

/**
 * Grouped staff picker for case manager / mentor assignment (styled select).
 */
export function AdminStaffSelect({
  label,
  value,
  onChange,
  staff = [],
  placeholder = 'Select…',
  allowEmpty = false,
  emptyLabel = '— None —',
  required = false,
  id,
  className = '',
}) {
  const selectId = id || `staff-select-${label?.replace(/\s+/g, '-').toLowerCase() || 'field'}`
  const grouped = groupStaff(staff)

  return (
    <label className={`admin-filter-field admin-staff-select ${className}`.trim()} htmlFor={selectId}>
      {label ? <span className="admin-filter-field__label">{label}</span> : null}
      <span className="admin-filter-select admin-filter-select--block">
        <select
          id={selectId}
          className="admin-filter-select__input"
          value={value}
          onChange={onChange}
          required={required}
        >
          {allowEmpty ? <option value="">{emptyLabel}</option> : <option value="">{placeholder}</option>}
          {ROLE_GROUP_ORDER.map((group) => {
            const people = grouped[group.key]
            if (!people?.length) return null
            return (
              <optgroup key={group.key} label={group.label}>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {formatPersonLabel(person)}
                  </option>
                ))}
              </optgroup>
            )
          })}
        </select>
        <span className="admin-filter-select__chevron" aria-hidden>
          ▾
        </span>
      </span>
    </label>
  )
}
