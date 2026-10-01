import { STAFF_LOGIN_ROLES } from './portalLogin.js'

/** True when the account is SPOT-only (no other staff operational roles). */
export function isSpotOnlyUser(user) {
  if (!user?.roles?.length) return false
  const roles = user.roles.map((r) => String(r).toUpperCase())
  if (!roles.includes('SPOT')) return false
  const otherStaff = STAFF_LOGIN_ROLES.filter((r) => r !== 'SPOT')
  return !roles.some((r) => otherStaff.includes(r))
}

export function spotNav() {
  return [
    { to: '/admin', label: 'Dashboard', end: true, perm: null, feature: null, icon: 'dashboard' },
    { to: '/admin/spot-attendance', label: 'Attendance', perm: null, feature: null, icon: 'grid' },
    { to: '/admin/spot-leave', label: 'Leave', perm: null, feature: null, icon: 'leave' },
  ]
}
