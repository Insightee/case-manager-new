import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'

const STAFF_ROLE_ORDER = ['SUPER_ADMIN', 'MODULE_ADMIN', 'CASE_MANAGER', 'FINANCE', 'HR']

function normalizeRoles(roles) {
  return (roles || []).map((r) => r.trim().toUpperCase()).filter(Boolean)
}

export function grantsFromAssignments(moduleIds, viewOnly = false) {
  const grants = {}
  for (const mid of moduleIds || []) {
    const id = String(mid).trim().toLowerCase()
    if (id) grants[id] = { enabled: true, access: viewOnly ? 'view' : 'write' }
  }
  return grants
}

function assignmentsFromGrants(grants) {
  return Object.entries(grants || {})
    .filter(([, g]) => g?.enabled)
    .map(([id]) => id)
}

export function buildRbacPayload({ roleNames, grants, featureOverrides, viewOnly }) {
  return {
    role_names: roleNames,
    module_assignments: assignmentsFromGrants(grants),
    module_access_grants: grants,
    feature_overrides: featureOverrides,
    view_only: viewOnly,
  }
}

export function RbacEditor({
  catalog = [],
  assignableRoles = [],
  roleDefaults = {},
  selectedRoles = [],
  onRoleChange,
  allowMultiRole = false,
  grants: grantsProp,
  onGrantsChange,
  featureOverrides: overridesProp = {},
  onOverridesChange,
  viewOnly = false,
  onViewOnlyChange,
  disabled = false,
}) {
  const [combineMode, setCombineMode] = useState(false)
  const [expanded, setExpanded] = useState({})
  const [preview, setPreview] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const roles = useMemo(() => normalizeRoles(selectedRoles), [selectedRoles])
  const isSuperAdmin = roles.includes('SUPER_ADMIN')

  const grants = grantsProp ?? {}
  const featureOverrides = overridesProp ?? {}

  const roleOptions = useMemo(() => {
    if (assignableRoles.length) return assignableRoles
    return STAFF_ROLE_ORDER.map((id) => ({ id, label: id.replace(/_/g, ' ') }))
  }, [assignableRoles])

  const suggested = useMemo(() => {
    const ids = new Set()
    for (const role of roles) {
      for (const mid of roleDefaults[role] || []) ids.add(mid)
    }
    return [...ids]
  }, [roles, roleDefaults])

  const applySuggested = useCallback(() => {
    if (!onGrantsChange || !suggested.length) return
    onGrantsChange(grantsFromAssignments(suggested, viewOnly))
  }, [onGrantsChange, suggested, viewOnly])

  const toggleModule = (moduleId) => {
    if (!onGrantsChange || disabled) return
    const id = moduleId.trim().toLowerCase()
    const current = grants[id]
    if (current?.enabled) {
      const next = { ...grants }
      delete next[id]
      onGrantsChange(next)
      return
    }
    onGrantsChange({
      ...grants,
      [id]: { enabled: true, access: viewOnly ? 'view' : 'write' },
    })
  }

  const setModuleAccess = (moduleId, access) => {
    if (!onGrantsChange || disabled) return
    const id = moduleId.trim().toLowerCase()
    if (!grants[id]?.enabled) return
    onGrantsChange({ ...grants, [id]: { ...grants[id], access } })
  }

  const toggleFeature = (moduleId, featureId, enabled) => {
    if (!onOverridesChange || disabled) return
    const mid = moduleId.trim().toLowerCase()
    const disabledList = [...(featureOverrides[mid] || [])]
    const idx = disabledList.indexOf(featureId)
    if (!enabled && idx === -1) disabledList.push(featureId)
    if (enabled && idx >= 0) disabledList.splice(idx, 1)
    onOverridesChange({ ...featureOverrides, [mid]: disabledList })
  }

  const isFeatureEnabled = (moduleId, featureId) => {
    const mid = moduleId.trim().toLowerCase()
    return !(featureOverrides[mid] || []).includes(featureId)
  }

  useEffect(() => {
    if (isSuperAdmin || !roles.length) {
      setPreview(null)
      return
    }
    const t = setTimeout(async () => {
      setPreviewLoading(true)
      try {
        const body = await apiFetch('/api/v1/admin/rbac/preview', {
          method: 'POST',
          body: JSON.stringify({
            role_names: roles,
            module_access_grants: grants,
            feature_overrides: featureOverrides,
            view_only: viewOnly,
          }),
        })
        setPreview(body)
      } catch {
        setPreview(null)
      } finally {
        setPreviewLoading(false)
      }
    }, 350)
    return () => clearTimeout(t)
  }, [roles, grants, featureOverrides, viewOnly, isSuperAdmin])

  useEffect(() => {
    if (!onGrantsChange || isSuperAdmin) return
    if (viewOnly) {
      const next = {}
      let changed = false
      for (const [mid, g] of Object.entries(grants)) {
        if (g.access !== 'view') changed = true
        next[mid] = { ...g, access: 'view' }
      }
      if (changed) onGrantsChange(next)
    }
  }, [viewOnly, isSuperAdmin])

  function selectRole(roleId) {
    if (!onRoleChange || disabled) return
    const id = roleId.toUpperCase()
    if (combineMode && allowMultiRole) {
      const set = new Set(roles)
      if (set.has(id)) set.delete(id)
      else set.add(id)
      onRoleChange([...set])
      return
    }
    onRoleChange([id])
    if (onGrantsChange && roleDefaults[id]) {
      onGrantsChange(grantsFromAssignments(roleDefaults[id], viewOnly))
    }
  }

  return (
    <div className="rbac-editor">
      <fieldset className="rbac-editor__section" disabled={disabled}>
        <legend className="rbac-editor__legend">Role</legend>
        {allowMultiRole ? (
          <label className="rbac-editor__combine">
            <input
              type="checkbox"
              checked={combineMode}
              onChange={(e) => setCombineMode(e.target.checked)}
            />
            Combine multiple roles
          </label>
        ) : null}
        <div className="admin-chip-row">
          {roleOptions.map((r) => {
            const id = r.id || r
            const active = roles.includes(String(id).toUpperCase())
            return (
              <button
                key={id}
                type="button"
                className={`admin-chip admin-chip--btn ${active ? 'is-active' : ''}`}
                onClick={() => selectRole(String(id))}
                title={r.description || ''}
              >
                {r.label || String(id).replace(/_/g, ' ')}
              </button>
            )
          })}
        </div>
      </fieldset>

      {isSuperAdmin ? (
        <p className="admin-muted rbac-editor__hint">Super Admin has full access; module grants are not required.</p>
      ) : (
        <>
          <fieldset className="rbac-editor__section" disabled={disabled}>
            <legend className="rbac-editor__legend">Programme modules</legend>
            {suggested.length ? (
              <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={applySuggested}>
                Apply defaults for role
              </button>
            ) : null}
            <ul className="rbac-module-list">
              {catalog.map((mod) => {
                const grant = grants[mod.id] || {}
                const enabled = Boolean(grant.enabled)
                return (
                  <li key={mod.id} className={`rbac-module-list__item ${enabled ? 'is-enabled' : ''}`}>
                    <label className="rbac-module-list__toggle">
                      <input
                        type="checkbox"
                        checked={enabled}
                        onChange={() => toggleModule(mod.id)}
                      />
                      <span>
                        <strong>{mod.label}</strong>
                        <small>{mod.description}</small>
                      </span>
                    </label>
                    {enabled ? (
                      <div className="access-level-toggle access-level-toggle--inline">
                        <div className="access-level-toggle__options">
                          <label
                            className={`access-level-toggle__option ${grant.access === 'view' ? 'is-active' : ''}`}
                          >
                            <input
                              type="radio"
                              name={`access-${mod.id}`}
                              checked={grant.access === 'view'}
                              onChange={() => setModuleAccess(mod.id, 'view')}
                            />
                            <span>
                              <strong>View</strong>
                              <small>Read-only in this module</small>
                            </span>
                          </label>
                          <label
                            className={`access-level-toggle__option ${grant.access !== 'view' ? 'is-active' : ''}`}
                          >
                            <input
                              type="radio"
                              name={`access-${mod.id}`}
                              checked={grant.access !== 'view'}
                              onChange={() => setModuleAccess(mod.id, 'write')}
                              disabled={viewOnly}
                            />
                            <span>
                              <strong>Edit</strong>
                              <small>Create and update records</small>
                            </span>
                          </label>
                        </div>
                      </div>
                    ) : null}
                    {enabled && (mod.features || []).length ? (
                      <div className="rbac-feature-list">
                        <button
                          type="button"
                          className="rbac-feature-list__toggle"
                          onClick={() =>
                            setExpanded((e) => ({ ...e, [mod.id]: !e[mod.id] }))
                          }
                        >
                          {expanded[mod.id] ? 'Hide' : 'Show'} features ({mod.features.length})
                        </button>
                        {(expanded[mod.id] ?? enabled) ? (
                          <ul>
                            {mod.features.map((f) => (
                              <li key={f.id}>
                                <label>
                                  <input
                                    type="checkbox"
                                    checked={isFeatureEnabled(mod.id, f.id)}
                                    onChange={(ev) =>
                                      toggleFeature(mod.id, f.id, ev.target.checked)
                                    }
                                  />
                                  {f.label}
                                </label>
                              </li>
                            ))}
                          </ul>
                        ) : null}
                      </div>
                    ) : null}
                  </li>
                )
              })}
            </ul>
          </fieldset>

          {onViewOnlyChange ? (
            <div className="access-level-toggle">
              <p className="access-level-toggle__label">Global access mode</p>
              <div className="access-level-toggle__options">
                <label className={`access-level-toggle__option ${!viewOnly ? 'is-active' : ''}`}>
                  <input
                    type="radio"
                    name="rbac-global-access"
                    checked={!viewOnly}
                    onChange={() => onViewOnlyChange(false)}
                  />
                  <span>
                    <strong>Standard</strong>
                    <small>Per-module view/edit applies</small>
                  </span>
                </label>
                <label className={`access-level-toggle__option ${viewOnly ? 'is-active' : ''}`}>
                  <input
                    type="radio"
                    name="rbac-global-access"
                    checked={viewOnly}
                    onChange={() => onViewOnlyChange(true)}
                  />
                  <span>
                    <strong>View only (all modules)</strong>
                    <small>No create or update anywhere</small>
                  </span>
                </label>
              </div>
            </div>
          ) : null}

          <p className="admin-muted rbac-editor__hint" style={{ fontSize: '0.75rem', margin: '8px 0 0' }}>
            Applies to admin portal staff. Therapist and parent access is configured under People → Therapist profiles
            or client records.
          </p>

          <div className="capability-preview rbac-preview">
            <p className="capability-preview__label">
              Effective access (preview){previewLoading ? ' — updating…' : ''}
            </p>
            <p className="admin-muted" style={{ fontSize: '0.7rem', margin: '0 0 8px' }}>
              Read-only summary — enable modules and features above to change access.
            </p>
            {preview?.warnings?.length ? (
              <ul className="rbac-preview__warnings">
                {preview.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            ) : null}
            {preview?.modules?.length ? (
              <ul className="rbac-preview__modules">
                {preview.modules.map((m) => (
                  <li key={m.id}>
                    <span className="rbac-preview__module-label">{m.label}</span>
                    <span
                      className={`admin-badge ${
                        m.access === 'view' ? 'admin-badge--neutral' : 'admin-badge--success'
                      }`}
                    >
                      {m.access === 'view' ? 'View' : 'Edit'}
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
            {preview?.portal_areas?.length ? (
              <>
                <p className="capability-preview__label" style={{ marginTop: 8 }}>
                  Portal areas
                </p>
                <ul className="capability-preview__list">
                  {preview.portal_areas.map((a) => (
                    <li key={a}>{a}</li>
                  ))}
                </ul>
              </>
            ) : !preview?.modules?.length ? (
              <p className="admin-muted">Enable at least one module to see effective access.</p>
            ) : null}
          </div>
        </>
      )}
    </div>
  )
}
