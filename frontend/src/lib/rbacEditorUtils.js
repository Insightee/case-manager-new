/** RBAC editor helpers — bulk service selection and shared clinical features. */

export const ORG_IDS = new Set(['billing', 'people_admin', 'hr_ops', 'service_catalog_admin'])

export function splitGrants(grants = {}) {
  const service = {}
  const org = {}
  for (const [id, g] of Object.entries(grants)) {
    if (ORG_IDS.has(id)) org[id] = g
    else service[id] = g
  }
  return { service, org }
}

export function mergeGrants(serviceGrants = {}, orgGrants = {}) {
  return { ...serviceGrants, ...orgGrants }
}

export function serviceIdsFromCatalog(serviceCatalog) {
  return (serviceCatalog || []).map((m) => String(m.id).trim().toLowerCase()).filter(Boolean)
}

export function enabledServiceIds(grants, serviceCatalog) {
  const allowed = new Set(serviceIdsFromCatalog(serviceCatalog))
  return Object.entries(grants || {})
    .filter(([id, g]) => g?.enabled && allowed.has(String(id).trim().toLowerCase()))
    .map(([id]) => String(id).trim().toLowerCase())
}

export function applyServiceSelection(grants, serviceCatalog, selectedIds, access = 'write') {
  const { org } = splitGrants(grants)
  const allowed = new Set(serviceIdsFromCatalog(serviceCatalog))
  const selected = new Set(
    (selectedIds || []).map((id) => String(id).trim().toLowerCase()).filter((id) => allowed.has(id)),
  )
  const service = {}
  for (const id of selected) {
    service[id] = { enabled: true, access: access === 'view' ? 'view' : 'write' }
  }
  return mergeGrants(service, org)
}

export function selectAllServices(grants, serviceCatalog, access = 'write') {
  return applyServiceSelection(grants, serviceCatalog, serviceIdsFromCatalog(serviceCatalog), access)
}

export function clearAllServices(grants) {
  const { org } = splitGrants(grants)
  return mergeGrants({}, org)
}

export function setAllServicesAccess(grants, serviceCatalog, access) {
  const ids = enabledServiceIds(grants, serviceCatalog)
  if (!ids.length) return grants
  const { org, service } = splitGrants(grants)
  const nextService = { ...service }
  const level = access === 'view' ? 'view' : 'write'
  for (const id of ids) {
    if (nextService[id]?.enabled) {
      nextService[id] = { ...nextService[id], access: level }
    }
  }
  return mergeGrants(nextService, org)
}

export function bulkServiceAccessLevel(grants, serviceCatalog, viewOnly = false) {
  const ids = enabledServiceIds(grants, serviceCatalog)
  if (!ids.length) return viewOnly ? 'view' : 'write'
  const levels = ids.map((id) => (grants[id]?.access === 'view' ? 'view' : 'write'))
  if (levels.every((l) => l === 'view')) return 'view'
  if (levels.every((l) => l === 'write')) return 'write'
  return 'mixed'
}

export function sharedClinicalFeatures(serviceCatalog, catalogClinicalFeatures) {
  if (Array.isArray(catalogClinicalFeatures) && catalogClinicalFeatures.length) {
    return catalogClinicalFeatures
  }
  const first = (serviceCatalog || []).find((m) => (m.features || []).length)
  return first?.features || []
}

export function setGlobalFeatureOverride(overrides, serviceIds, featureId, enabled) {
  const next = { ...(overrides || {}) }
  const fid = String(featureId).trim()
  for (const rawId of serviceIds || []) {
    const mid = String(rawId).trim().toLowerCase()
    const disabledList = [...(next[mid] || [])]
    const idx = disabledList.indexOf(fid)
    if (!enabled && idx === -1) disabledList.push(fid)
    if (enabled && idx >= 0) disabledList.splice(idx, 1)
    next[mid] = disabledList
  }
  return next
}

/** @returns {true | false | 'mixed'} */
export function isGlobalFeatureEnabled(overrides, serviceIds, featureId) {
  const ids = serviceIds || []
  if (!ids.length) return false
  const fid = String(featureId).trim()
  let enabledCount = 0
  for (const rawId of ids) {
    const mid = String(rawId).trim().toLowerCase()
    const disabled = (overrides?.[mid] || []).includes(fid)
    if (!disabled) enabledCount += 1
  }
  if (enabledCount === 0) return false
  if (enabledCount === ids.length) return true
  return 'mixed'
}
