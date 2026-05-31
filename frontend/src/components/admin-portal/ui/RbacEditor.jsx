import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { apiFetch } from '../../../lib/apiClient.js'
import {
  ORG_IDS,
  applyServiceSelection,
  bulkServiceAccessLevel,
  clearAllServices,
  enabledServiceIds,
  isGlobalFeatureEnabled,
  mergeGrants,
  selectAllServices,
  setAllServicesAccess,
  setGlobalFeatureOverride,
  sharedClinicalFeatures,
  splitGrants,
} from '../../../lib/rbacEditorUtils.js'

export { splitGrants, mergeGrants, ORG_IDS }

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

export function buildRbacPayload({ roleNames, grants, serviceGrants, orgGrants, featureOverrides, viewOnly }) {
  const split = grants ? splitGrants(grants) : { service: serviceGrants || {}, org: orgGrants || {} }
  const merged = mergeGrants(split.service, split.org)
  return {
    role_names: roleNames,
    module_assignments: assignmentsFromGrants(merged),
    module_access_grants: merged,
    service_access_grants: split.service,
    org_capability_grants: split.org,
    feature_overrides: featureOverrides,
    view_only: viewOnly,
  }
}

function defaultGrantsForRole(role, roleDefaults, viewOnly) {
  const def = roleDefaults?.[role]
  if (!def) return { service: {}, org: {} }
  if (Array.isArray(def)) return splitGrants(grantsFromAssignments(def, viewOnly))
  return {
    service: grantsFromAssignments(def.services || [], viewOnly),
    org: grantsFromAssignments(def.org || [], viewOnly),
  }
}

function GlobalFeatureCheckbox({ featureId, label, serviceIds, overrides, onOverridesChange, disabled }) {
  const ref = useRef(null)
  const state = isGlobalFeatureEnabled(overrides, serviceIds, featureId)

  useEffect(() => {
    if (ref.current) ref.current.indeterminate = state === 'mixed'
  }, [state])

  return (
    <li>
      <label>
        <input
          ref={ref}
          type="checkbox"
          checked={state === true}
          disabled={disabled}
          onChange={(ev) => {
            if (!onOverridesChange) return
            const enabled = state === 'mixed' ? true : ev.target.checked
            onOverridesChange(setGlobalFeatureOverride(overrides, serviceIds, featureId, enabled))
          }}
        />
        {label}
      </label>
    </li>
  )
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
    let service = {}
    let org = {}
    for (const role of roles) {
      const d = defaultGrantsForRole(role, roleDefaults, viewOnly)
      service = { ...service, ...d.service }
      org = { ...org, ...d.org }
    }
    return mergeGrants(service, org)
  }, [roles, roleDefaults, viewOnly])

  const serviceCatalog = useMemo(() => {
    if (!Array.isArray(catalog) && catalog?.service_categories?.length) {
      return catalog.service_categories
    }
    const mods = Array.isArray(catalog) ? catalog : catalog?.modules || []
    return mods.filter((m) => m.module_type === 'service' || (!ORG_IDS.has(m.id) && m.id !== 'billing'))
  }, [catalog])

  const orgCatalog = useMemo(() => {
    if (!Array.isArray(catalog) && catalog?.org_capabilities?.length) {
      return catalog.org_capabilities
    }
    const mods = Array.isArray(catalog) ? catalog : catalog?.modules || []
    return mods.filter((m) => ORG_IDS.has(m.id) || m.module_type === 'org')
  }, [catalog])

  const clinicalFeatures = useMemo(
    () => sharedClinicalFeatures(serviceCatalog, catalog?.clinical_features),
    [serviceCatalog, catalog],
  )

  const selectedServiceIds = useMemo(
    () => enabledServiceIds(grants, serviceCatalog),
    [grants, serviceCatalog],
  )

  const bulkAccess = useMemo(
    () => bulkServiceAccessLevel(grants, serviceCatalog, viewOnly),
    [grants, serviceCatalog, viewOnly],
  )

  const applySuggested = useCallback(() => {
    if (!onGrantsChange || !Object.keys(suggested).length) return
    onGrantsChange(suggested)
  }, [onGrantsChange, suggested])

  const handleSelectAllServices = () => {
    if (!onGrantsChange || disabled) return
    const access = bulkAccess === 'view' || viewOnly ? 'view' : 'write'
    onGrantsChange(selectAllServices(grants, serviceCatalog, access))
  }

  const handleClearAllServices = () => {
    if (!onGrantsChange || disabled) return
    onGrantsChange(clearAllServices(grants))
  }

  const handleServiceMultiselect = (event) => {
    if (!onGrantsChange || disabled) return
    const selected = Array.from(event.target.selectedOptions).map((o) => o.value)
    const access =
      bulkAccess === 'mixed' || bulkAccess === 'view' ? (viewOnly ? 'view' : bulkAccess === 'view' ? 'view' : 'write') : bulkAccess
    onGrantsChange(applyServiceSelection(grants, serviceCatalog, selected, viewOnly ? 'view' : access))
  }

  const handleBulkServiceAccess = (access) => {
    if (!onGrantsChange || disabled || !selectedServiceIds.length) return
    onGrantsChange(setAllServicesAccess(grants, serviceCatalog, access))
  }

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
    if (id === 'SUPER_ADMIN') {
      onGrantsChange?.({})
      onOverridesChange?.({})
      return
    }
    if (onGrantsChange && roleDefaults[id]) {
      const d = defaultGrantsForRole(id, roleDefaults, viewOnly)
      onGrantsChange(mergeGrants(d.service, d.org))
    }
  }

  return (
    <div className="rbac-editor">
      <div className="rbac-editor__section" aria-disabled={disabled || undefined}>
        <p className="rbac-editor__legend">Role</p>
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
                disabled={disabled}
                title={r.description || ''}
              >
                {r.label || String(id).replace(/_/g, ' ')}
              </button>
            )
          })}
        </div>
      </div>

      {isSuperAdmin ? (
        <div className="capability-preview rbac-preview">
          <p className="admin-muted rbac-editor__hint">Super Admin has full access to all services and org capabilities.</p>
          <p className="capability-preview__label">Effective access (read-only)</p>
          <ul className="capability-preview__list">
            <li>All service lines</li>
            <li>Billing, people, HR, and settings</li>
          </ul>
        </div>
      ) : (
        <>
          <div className="rbac-editor__section" aria-disabled={disabled || undefined}>
            <p className="rbac-editor__legend">Service access</p>
            <p className="admin-muted rbac-editor__hint" style={{ marginTop: 0 }}>
              Service lines from Settings → Service categories. Select lines below; clinical features apply to all
              selected services at once.
            </p>
            <div className="rbac-service-toolbar">
              {Object.keys(suggested).length > 0 ? (
                <button type="button" className="admin-btn admin-btn--ghost admin-btn--sm" onClick={applySuggested}>
                  Apply defaults for role
                </button>
              ) : null}
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={handleSelectAllServices}
                disabled={disabled || !serviceCatalog.length}
              >
                Select all services
              </button>
              <button
                type="button"
                className="admin-btn admin-btn--ghost admin-btn--sm"
                onClick={handleClearAllServices}
                disabled={disabled || !selectedServiceIds.length}
              >
                Clear all services
              </button>
            </div>

            <label className="rbac-service-multiselect__label" htmlFor="rbac-service-multiselect">
              Service categories
            </label>
            <select
              id="rbac-service-multiselect"
              className="admin-input rbac-service-multiselect"
              multiple
              size={Math.min(Math.max(serviceCatalog.length, 3), 8)}
              value={selectedServiceIds}
              disabled={disabled}
              onChange={handleServiceMultiselect}
              aria-describedby="rbac-service-multiselect-hint"
            >
              {serviceCatalog.map((mod) => (
                <option key={mod.id} value={mod.id}>
                  {mod.label}
                </option>
              ))}
            </select>
            <p id="rbac-service-multiselect-hint" className="admin-muted rbac-editor__hint">
              {selectedServiceIds.length} of {serviceCatalog.length} selected — hold Cmd/Ctrl to pick multiple, or use
              Select all.
            </p>

            {selectedServiceIds.length > 0 ? (
              <>
                <div className="rbac-service-meta">
                  <p className="access-level-toggle__label">Access for all selected services</p>
                  <div className="access-level-toggle access-level-toggle--inline">
                    <div className="access-level-toggle__options">
                      <label
                        className={`access-level-toggle__option ${bulkAccess === 'view' ? 'is-active' : ''}`}
                      >
                        <input
                          type="radio"
                          name="rbac-bulk-service-access"
                          checked={bulkAccess === 'view'}
                          disabled={disabled}
                          onChange={() => handleBulkServiceAccess('view')}
                        />
                        <span>
                          <strong>View</strong>
                          <small>Read-only in these service lines</small>
                        </span>
                      </label>
                      <label
                        className={`access-level-toggle__option ${bulkAccess === 'write' || bulkAccess === 'mixed' ? 'is-active' : ''}`}
                      >
                        <input
                          type="radio"
                          name="rbac-bulk-service-access"
                          checked={bulkAccess === 'write' || bulkAccess === 'mixed'}
                          disabled={disabled || viewOnly}
                          onChange={() => handleBulkServiceAccess('write')}
                        />
                        <span>
                          <strong>Edit</strong>
                          <small>Create and update records</small>
                        </span>
                      </label>
                    </div>
                  </div>
                  {bulkAccess === 'mixed' ? (
                    <p className="admin-muted rbac-editor__hint">Mixed access levels — choose View or Edit to align all.</p>
                  ) : null}
                </div>

                {clinicalFeatures.length > 0 ? (
                  <div className="rbac-global-features rbac-feature-list">
                    <p className="rbac-editor__legend">Clinical features (applies to all selected service lines)</p>
                    <ul>
                      {clinicalFeatures.map((f) => (
                        <GlobalFeatureCheckbox
                          key={f.id}
                          featureId={f.id}
                          label={f.label}
                          serviceIds={selectedServiceIds}
                          overrides={featureOverrides}
                          onOverridesChange={onOverridesChange}
                          disabled={disabled}
                        />
                      ))}
                    </ul>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>

          {orgCatalog.length > 0 ? (
            <div className="rbac-editor__section" aria-disabled={disabled || undefined}>
              <p className="rbac-editor__legend">Org capabilities</p>
              <ul className="rbac-module-list">
                {orgCatalog.map((mod) => {
                  const grant = grants[mod.id] || {}
                  const enabled = Boolean(grant.enabled)
                  return (
                    <li key={mod.id} className={`rbac-module-list__item ${enabled ? 'is-enabled' : ''}`}>
                      <label className="rbac-module-list__toggle">
                        <input
                          type="checkbox"
                          checked={enabled}
                          disabled={disabled}
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
                                disabled={disabled}
                                onChange={() => setModuleAccess(mod.id, 'view')}
                              />
                              <span>
                                <strong>View</strong>
                                <small>Read-only</small>
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
                                <small>Full access</small>
                              </span>
                            </label>
                          </div>
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            </div>
          ) : null}

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
