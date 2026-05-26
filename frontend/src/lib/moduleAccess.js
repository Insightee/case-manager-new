/** Helpers for RBAC module grants from /auth/me modules[]. */

export function moduleMap(user) {
  const map = new Map()
  for (const m of user?.modules || []) {
    if (m?.id) map.set(String(m.id).toLowerCase(), m)
  }
  return map
}

export function hasModule(user, moduleId) {
  if (!user) return false
  const feats = user.features || []
  if (feats.includes('*')) return true
  const id = String(moduleId || '').toLowerCase()
  return moduleMap(user).has(id)
}

export function moduleAccess(user, moduleId) {
  if (!user) return null
  const feats = user.features || []
  if (feats.includes('*')) return 'write'
  const mod = moduleMap(user).get(String(moduleId || '').toLowerCase())
  return mod?.access || null
}

export function isGlobalViewOnly(user) {
  if (!user) return false
  const feats = user.features || []
  if (feats.includes('*')) return false
  const roles = user.roles || []
  if (roles.includes('SUPER_ADMIN') || roles.includes('MODULE_ADMIN')) {
    return Boolean(user.is_view_only)
  }
  if (user.is_view_only) return true
  return feats.includes('view_only')
}

export function canWriteModule(user, moduleId) {
  if (!user) return false
  if (isGlobalViewOnly(user)) return false
  const feats = user.features || []
  if (feats.includes('*')) return true
  return moduleAccess(user, moduleId) === 'write'
}

export function canWriteProduct(user, productModule) {
  if (!user) return false
  const product = String(productModule || 'homecare').toLowerCase()
  const mods = user?.modules || []
  for (const m of mods) {
    const caseProducts = m.case_product_modules || []
    if (caseProducts.includes(product) || m.id === product) {
      if (canWriteModule(user, m.id)) return true
    }
  }
  return false
}

export function canWriteFeature(user, featureId, productModule = null) {
  if (!user) return false
  if (isGlobalViewOnly(user)) return false
  const feats = user.features || []
  if (feats.includes('*')) return true
  if (!feats.includes(featureId)) return false
  if (featureId === 'invoices' || featureId === 'dashboard') {
    return canWriteModule(user, 'billing')
  }
  if (productModule) return canWriteProduct(user, productModule)
  for (const m of user?.modules || []) {
    if (m.id === 'billing') continue
    if ((m.features || []).includes(featureId) && canWriteModule(user, m.id)) return true
  }
  return false
}

/** Case product_module ids from assigned clinical modules (for nav gating). */
export function clinicalProductModuleIds(user) {
  if (!user) return []
  const feats = user.features || []
  const ids = new Set()
  if (feats.includes('*')) {
    for (const m of user?.modules || []) {
      for (const pid of m.case_product_modules || []) {
        if (pid && pid !== 'billing') ids.add(pid)
      }
      if (m.id && m.id !== 'billing' && (m.case_product_modules || []).includes(m.id)) {
        ids.add(m.id)
      }
    }
    return [...ids]
  }
  for (const m of user?.modules || []) {
    if (m.id === 'billing') continue
    for (const pid of m.case_product_modules || []) {
      if (pid && pid !== 'billing') ids.add(pid)
    }
    if (m.id && m.id !== 'billing') ids.add(m.id)
  }
  return [...ids]
}

/** Nav item may declare moduleIds: all must be enabled; feature optional. */
export function navItemVisible(item, { can, hasFeature, hasModule }) {
  if (item.perm && !can(item.perm)) return false
  if (item.feature && !hasFeature(item.feature)) return false
  if (item.moduleIds?.length) {
    return item.moduleIds.some((id) => hasModule(id))
  }
  return true
}
