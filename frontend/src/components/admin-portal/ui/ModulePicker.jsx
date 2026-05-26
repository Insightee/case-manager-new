import { useMemo, useState } from 'react'

const FEATURE_HINTS = {
  cases: 'Case pipeline, allotment and reassignment',
  session_logs: 'Daily session logs and workbench queues',
  reports: 'Monthly reports & observation checklists',
  iep: 'Structured IEP builder and attachment uploads',
  cm_meetings: 'CM meetings, supervision calls and case reviews',
  invoices: 'Therapist payouts and client payment claims',
  tickets: 'Internal support tickets',
  incidents: 'Incident reporting and investigation',
  dashboard: 'Role-aware KPIs and home widgets',
}

const ROLE_LABELS = {
  SUPER_ADMIN: 'Super Admin',
  MODULE_ADMIN: 'Module Admin',
  ADMIN: 'Legacy Admin',
  CASE_MANAGER: 'Case Manager',
  SUPERVISOR: 'Supervisor (legacy)',
  FINANCE: 'Finance',
  HR: 'HR',
  THERAPIST: 'Therapist',
  PARENT: 'Parent / Guardian',
  SCHOOL_COORDINATOR: 'School Coordinator',
  VIEWER: 'View only (legacy)',
}

const NAV_UNLOCKED_BY_FEATURE = {
  cases: 'Cases & case pipeline',
  session_logs: 'Workbench & session logs',
  reports: 'Reports & observation checklists',
  iep: 'IEP builder & attachments',
  cm_meetings: 'CM meetings hub',
  invoices: 'Invoices & client payment claims',
  tickets: 'Support tickets',
  incidents: 'Incidents',
  dashboard: 'Operations dashboard',
}

function previewAreas(catalog, moduleIds) {
  const areas = new Set()
  for (const mod of catalog || []) {
    if (!moduleIds.includes(mod.id)) continue
    for (const f of mod.features || []) {
      const label = NAV_UNLOCKED_BY_FEATURE[f.id]
      if (label) areas.add(label)
    }
  }
  return [...areas].sort()
}

export function ModulePicker({
  catalog,
  roleDefaults,
  selectedRoles,
  onRoleChange,
  allowMultiRole = false,
  value,
  onChange,
  featureOverrides = {},
  onFeatureOverridesChange,
  viewOnly = false,
  onViewOnlyChange,
  disabled = false,
}) {
  const [combineMode, setCombineMode] = useState(false)
  const [expandedFeatures, setExpandedFeatures] = useState({})

  const roles = useMemo(
    () => (selectedRoles || []).map((r) => r.trim().toUpperCase()).filter(Boolean),
    [selectedRoles],
  )

  const isSuperAdmin = roles.includes('SUPER_ADMIN')

  const suggestedForRole = (role) => roleDefaults?.[role] ?? []

  const suggested = useMemo(() => {
    if (!roleDefaults || roles.length === 0) return []
    const ids = new Set()
    for (const role of roles) {
      for (const mid of suggestedForRole(role)) ids.add(mid)
    }
    return [...ids]
  }, [roles, roleDefaults])

  function applyDefaultsForRole(role) {
    if (disabled || isSuperAdmin) return
    const mods = suggestedForRole(role)
    onChange(mods)
    if (onRoleChange && !combineMode) onRoleChange([role])
  }

  function toggleModule(moduleId) {
    if (disabled || isSuperAdmin) return
    const next = value.includes(moduleId)
      ? value.filter((id) => id !== moduleId)
      : [...value, moduleId]
    onChange(next)
  }

  function handleRoleChip(role) {
    if (!onRoleChange) return
    if (combineMode || allowMultiRole) {
      const next = roles.includes(role) ? roles.filter((r) => r !== role) : [...roles, role]
      onRoleChange(next.length ? next : [role])
    } else {
      onRoleChange([role])
      if (roleDefaults?.[role]) onChange(suggestedForRole(role))
    }
  }

  function toggleFeatureExpand(modId) {
    setExpandedFeatures((prev) => ({ ...prev, [modId]: !prev[modId] }))
  }

  function isFeatureEnabled(moduleId, featureId) {
    const mid = moduleId.trim().toLowerCase()
    return !(featureOverrides[mid] || []).includes(featureId)
  }

  function toggleFeature(moduleId, featureId, enabled) {
    if (!onFeatureOverridesChange || disabled) return
    const mid = moduleId.trim().toLowerCase()
    const disabledList = [...(featureOverrides[mid] || [])]
    const idx = disabledList.indexOf(featureId)
    if (!enabled && idx === -1) disabledList.push(featureId)
    if (enabled && idx >= 0) disabledList.splice(idx, 1)
    onFeatureOverridesChange({ ...featureOverrides, [mid]: disabledList })
  }

  const areas = useMemo(() => previewAreas(catalog, value), [catalog, value])

  if (!catalog?.length) {
    return <p className="admin-empty__desc">Loading product modules…</p>
  }

  const ROLE_OPTIONS = Object.keys(ROLE_LABELS).filter(
    (r) => !['SUPER_ADMIN', 'PARENT', 'THERAPIST', 'ADMIN', 'VIEWER', 'SUPERVISOR'].includes(r),
  )

  return (
    <div className="module-picker">
      {/* Role selector */}
      {onRoleChange ? (
        <div className="module-picker__roles-block">
          <div className="module-picker__roles-header">
            <p className="module-picker__title">Role</p>
            <label className="module-picker__combine-toggle">
              <input
                type="checkbox"
                checked={combineMode}
                onChange={(e) => setCombineMode(e.target.checked)}
              />
              Combine roles
            </label>
          </div>
          <div className="admin-chip-row">
            {ROLE_OPTIONS.map((role) => {
              const active = roles.includes(role)
              return (
                <button
                  key={role}
                  type="button"
                  className={`admin-chip admin-chip--btn${active ? ' is-active' : ''}`}
                  onClick={() => handleRoleChip(role)}
                  aria-pressed={active}
                >
                  {ROLE_LABELS[role]}
                </button>
              )
            })}
          </div>
          {roles.length > 0 && !isSuperAdmin ? (
            <div className="module-picker__defaults-row">
              {combineMode ? (
                <button
                  type="button"
                  className="admin-btn admin-btn--ghost admin-btn--sm"
                  onClick={() => onChange(suggested)}
                  disabled={disabled}
                >
                  Apply defaults for {roles.map((r) => ROLE_LABELS[r] ?? r).join(' + ')}
                </button>
              ) : (
                roles.map((role) => (
                  <button
                    key={role}
                    type="button"
                    className="admin-btn admin-btn--ghost admin-btn--sm"
                    onClick={() => applyDefaultsForRole(role)}
                    disabled={disabled}
                  >
                    Apply defaults for {ROLE_LABELS[role] ?? role}
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      ) : null}

      {/* Module cards */}
      <div className="module-picker__section">
        <p className="module-picker__title">Programme access</p>
        <p className="module-picker__hint">
          {isSuperAdmin
            ? 'Super admins have access to all modules and features.'
            : 'Select which programmes this user can access. Features follow these modules.'}
        </p>
        {!isSuperAdmin ? (
          <div className="module-picker__grid">
            {catalog.map((mod) => {
              const checked = isSuperAdmin || value.includes(mod.id)
              const featuresOpen = expandedFeatures[mod.id] ?? checked
              const customizable = Boolean(onFeatureOverridesChange)
              return (
                <div
                  key={mod.id}
                  className={`module-card${checked ? ' is-selected' : ''}${disabled || isSuperAdmin ? ' is-disabled' : ''}`}
                >
                  <label className="module-card__toggle">
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={disabled || isSuperAdmin}
                      onChange={() => toggleModule(mod.id)}
                    />
                    <div className="module-card__main">
                      <p className="module-card__label">{mod.label}</p>
                      <p className="module-card__desc">{mod.description}</p>
                      {mod.case_product_modules?.length > 0 ? (
                        <p className="module-card__cases">
                          Cases: {mod.case_product_modules.join(', ')}
                        </p>
                      ) : null}
                    </div>
                  </label>
                  {checked ? (
                    <div className="module-card__features-section">
                      <button
                        type="button"
                        className="module-card__features-toggle"
                        onClick={() => toggleFeatureExpand(mod.id)}
                        aria-expanded={featuresOpen}
                      >
                        {featuresOpen ? '▾ Hide features' : '▸ Customise features'}
                      </button>
                      {featuresOpen ? (
                        <ul className="module-feature-list">
                          {mod.features.map((f) => (
                            <li key={f.id} className="module-feature-list__item">
                              {customizable ? (
                                <label className="module-feature-list__check">
                                  <input
                                    type="checkbox"
                                    checked={isFeatureEnabled(mod.id, f.id)}
                                    disabled={disabled || isSuperAdmin}
                                    onChange={(e) => toggleFeature(mod.id, f.id, e.target.checked)}
                                  />
                                  <span className="module-feature-list__label">{f.label}</span>
                                </label>
                              ) : (
                                <span className="module-feature-list__label">{f.label}</span>
                              )}
                              {FEATURE_HINTS[f.id] ? (
                                <span className="module-feature-list__hint">
                                  {FEATURE_HINTS[f.id]}
                                </span>
                              ) : null}
                            </li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        ) : null}
      </div>

      {/* Access level */}
      {onViewOnlyChange ? (
        <div className="access-level-toggle">
          <p className="module-picker__title">Access level</p>
          <div className="access-level-toggle__options">
            <label className={`access-level-toggle__option${!viewOnly ? ' is-active' : ''}`}>
              <input
                type="radio"
                name="access-level"
                value="edit"
                checked={!viewOnly}
                onChange={() => onViewOnlyChange(false)}
              />
              <span>
                <strong>Full edit</strong>
                <small>Can create, update and act on items</small>
              </span>
            </label>
            <label className={`access-level-toggle__option${viewOnly ? ' is-active' : ''}`}>
              <input
                type="radio"
                name="access-level"
                value="view"
                checked={viewOnly}
                onChange={() => onViewOnlyChange(true)}
              />
              <span>
                <strong>View only</strong>
                <small>Read-only access across their modules</small>
              </span>
            </label>
          </div>
        </div>
      ) : null}

      {/* Capability preview */}
      {areas.length > 0 && !isSuperAdmin ? (
        <div className="capability-preview">
          <p className="capability-preview__label">Portal areas unlocked</p>
          <ul className="capability-preview__list">
            {areas.map((area) => (
              <li key={area}>{area}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  )
}
