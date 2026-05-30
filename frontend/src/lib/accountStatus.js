/** Map admin user records to Invited | Active | Deactivated. */

const SHADOW_MODULE = 'shadow_support'
const HOMECARE_MODULE = 'homecare'

function categoryModuleIds(category) {
  const modules = category?.product_modules || []
  if (modules.length) return modules.map((m) => String(m.id || '').toLowerCase()).filter(Boolean)
  return [String(category?.id || '').toLowerCase()].filter(Boolean)
}

function categoryMatchesProgram(category, productModule) {
  const module = String(productModule || '').toLowerCase()
  const ids = categoryModuleIds(category)
  if (ids.includes(module)) return true

  if (module === SHADOW_MODULE) {
    return category.id === SHADOW_MODULE || ids.includes(SHADOW_MODULE)
  }
  if (module === HOMECARE_MODULE) {
    return category.id !== SHADOW_MODULE && !ids.every((id) => id === SHADOW_MODULE)
  }
  return category.id === module
}

export function accountStatusLabel(user) {
  if (!user) return 'Deactivated'
  if (user.is_active === false) return 'Deactivated'
  if (user.invite_status === 'pending') return 'Invited'
  if (user.login_ready) return 'Active'
  if (user.is_active) return 'Invited'
  return 'Deactivated'
}

export function accountStatusTone(status) {
  if (status === 'Active') return 'success'
  if (status === 'Invited') return 'warning'
  return 'neutral'
}

/** Client/family row: Invited | Active | Deactivated */
export function clientAccountStatus(family) {
  if (!family) return 'Deactivated'
  if (family.pendingInvite) return 'Invited'
  const primary = family.parents?.[0]
  if (!primary) return 'Invited'
  if (primary.parentIsActive === false) return 'Deactivated'
  if (primary.parentLoginReady) return 'Active'
  return 'Invited'
}

/** Service types available for a case program module (homecare vs shadow). */
export function filterServiceCategoriesForModule(categories, productModule) {
  if (!productModule) return categories || []
  return (categories || []).filter(
    (cat) => cat.is_active !== false && categoryMatchesProgram(cat, productModule),
  )
}
