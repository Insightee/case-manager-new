import { useMemo } from 'react'

const ROLE_LABELS = {
  SUPER_ADMIN: 'Super Admin',
  ADMIN: 'Admin',
  CASE_MANAGER: 'Case Manager',
  SUPERVISOR: 'Supervisor',
  FINANCE: 'Finance',
  HR: 'HR',
  THERAPIST: 'Therapist',
  PARENT: 'Parent',
  SCHOOL_COORDINATOR: 'School Coordinator',
}

export function ModulePicker({
  catalog,
  roleDefaults,
  selectedRoles,
  value,
  onChange,
  disabled = false,
}) {
  const roles = useMemo(
    () => selectedRoles.map((r) => r.trim().toUpperCase()).filter(Boolean),
    [selectedRoles],
  )

  const isSuperAdmin = roles.includes('SUPER_ADMIN')

  const suggested = useMemo(() => {
    if (!roleDefaults || roles.length === 0) return []
    const ids = new Set()
    for (const role of roles) {
      for (const mid of roleDefaults[role] ?? []) ids.add(mid)
    }
    return [...ids]
  }, [roles, roleDefaults])

  function toggle(moduleId) {
    if (disabled || isSuperAdmin) return
    const next = value.includes(moduleId) ? value.filter((id) => id !== moduleId) : [...value, moduleId]
    onChange(next)
  }

  function applySuggested() {
    if (disabled || isSuperAdmin) return
    onChange(suggested)
  }

  if (!catalog?.length) {
    return <p className="admin-empty__desc">Loading product modules…</p>
  }

  return (
    <div className="module-picker">
      <div className="module-picker__intro">
        <p className="module-picker__title">Product modules</p>
        <p className="module-picker__hint">
          {isSuperAdmin
            ? 'Super admins have access to all modules and features.'
            : 'Select which programmes this user can access. Features in the admin portal follow these modules.'}
        </p>
        {!isSuperAdmin && suggested.length > 0 ? (
          <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={applySuggested}>
            Apply defaults for {roles.map((r) => ROLE_LABELS[r] ?? r).join(', ')}
          </button>
        ) : null}
      </div>

      <div className="module-picker__grid">
        {catalog.map((mod) => {
          const checked = isSuperAdmin || value.includes(mod.id)
          return (
            <label
              key={mod.id}
              className={`module-card ${checked ? 'is-selected' : ''} ${disabled || isSuperAdmin ? 'is-disabled' : ''}`}
            >
              <input
                type="checkbox"
                checked={checked}
                disabled={disabled || isSuperAdmin}
                onChange={() => toggle(mod.id)}
              />
              <div className="module-card__body">
                <p className="module-card__label">{mod.label}</p>
                <p className="module-card__desc">{mod.description}</p>
                {mod.case_product_modules?.length > 0 ? (
                  <p className="module-card__cases">
                    Cases: {mod.case_product_modules.join(', ')}
                  </p>
                ) : null}
                <ul className="module-card__features">
                  {mod.features.map((f) => (
                    <li key={f.id}>{f.label}</li>
                  ))}
                </ul>
              </div>
            </label>
          )
        })}
      </div>
    </div>
  )
}
