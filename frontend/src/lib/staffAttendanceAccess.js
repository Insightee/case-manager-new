import { STAFF_LOGIN_ROLES } from './portalLogin.js'

/** Internal staff (not therapist-only) who may use the attendance tab. */
export function isStaffAttendanceUser(user) {
  if (!user?.roles?.length || user.is_view_only) return false
  const roles = user.roles.map((r) => String(r).toUpperCase())
  if (roles.includes('THERAPIST') && !roles.some((r) => STAFF_LOGIN_ROLES.includes(r))) return false
  return roles.some((r) => STAFF_LOGIN_ROLES.includes(r))
}

/** HR and super admin may view/edit all staff attendance. */
export function canManageStaffAttendance(user) {
  const roles = (user?.roles || []).map((r) => String(r).toUpperCase())
  return roles.includes('SUPER_ADMIN') || roles.includes('HR')
}
