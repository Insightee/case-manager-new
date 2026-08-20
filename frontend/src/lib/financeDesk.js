/** Finance desk users (not super-admin) get a view-only case and leave cross-check. */

export function isFinanceDeskUser(user) {
  const roles = user?.roles || []
  return roles.includes('FINANCE') && !roles.includes('SUPER_ADMIN')
}
