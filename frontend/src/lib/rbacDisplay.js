/** Display helpers for RBAC editor and staff directory (aligned with /auth/me modules). */

export const ROLE_LANDING_HINTS = {
  SUPER_ADMIN: 'lands on Admin dashboard',
  MODULE_ADMIN: 'lands on Admin dashboard',
  ADMIN: 'legacy — use Module Admin for new staff',
  CASE_MANAGER: 'lands on My caseload (/admin/cm)',
  FINANCE: 'lands on Invoices',
  HR: 'lands on HR portal',
}

export const DEPRECATED_STAFF_ROLES = new Set(['SUPERVISOR', 'VIEWER'])
export const LEGACY_ADMIN_ROLE = 'ADMIN'

export function primaryLandingHint(roleNames) {
  const roles = (roleNames || []).map((r) => String(r).toUpperCase())
  if (roles.includes('CASE_MANAGER') && !roles.some((r) => ['SUPER_ADMIN', 'ADMIN', 'MODULE_ADMIN', 'FINANCE', 'HR'].includes(r))) {
    return ROLE_LANDING_HINTS.CASE_MANAGER
  }
  for (const key of ['SUPER_ADMIN', 'MODULE_ADMIN', 'ADMIN', 'FINANCE', 'HR']) {
    if (roles.includes(key)) return ROLE_LANDING_HINTS[key]
  }
  const first = roles[0]
  return ROLE_LANDING_HINTS[first] || null
}

export function grantsForUser(user, grantsFromAssignments) {
  const raw = user?.module_access_grants
  if (raw && Object.keys(raw).length) return raw
  return grantsFromAssignments(user?.module_assignments ?? [], Boolean(user?.is_view_only))
}

/** @returns {{ id: string, label: string, access: string }[]} */
export function moduleAccessSummary(user, catalog = [], grantsFromAssignments) {
  if (!user) return []
  if (user.roles?.includes('SUPER_ADMIN')) {
    return [{ id: '_all', label: 'All programmes', access: 'Edit' }]
  }
  if (user.is_view_only) {
    return [{ id: '_vo', label: 'All modules', access: 'View only' }]
  }

  const grants = grantsForUser(user, grantsFromAssignments)
  const enabled = Object.entries(grants).filter(([, g]) => g?.enabled)
  if (!enabled.length) return [{ id: '_none', label: 'No modules', access: '—' }]

  const moduleCatalog = Array.isArray(catalog)
    ? catalog
    : Array.isArray(catalog?.modules)
      ? catalog.modules
      : []

  return enabled.map(([id, g]) => {
    const label = moduleCatalog.find((m) => m.id === id)?.label || id.replace(/_/g, ' ')
    const access = g.access === 'view' ? 'View' : 'Edit'
    return { id, label, access }
  })
}

export function hasDeprecatedStaffRole(roleNames) {
  return (roleNames || []).some((r) => DEPRECATED_STAFF_ROLES.has(String(r).toUpperCase()))
}
