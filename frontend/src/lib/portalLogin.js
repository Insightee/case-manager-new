/** Portal sign-in routes and role checks (client / therapist / staff). */

/** Shown when email/password do not match. */
export const LOGIN_ERROR_INVALID_CREDENTIALS = 'Invalid credentials'

/** Shown when the account role does not match this sign-in page. */
export const LOGIN_ERROR_WRONG_PORTAL = 'Invalid Login. Use the correct portal.'

export const STAFF_LOGIN_ROLES = [
  'SUPER_ADMIN',
  'ADMIN',
  'MODULE_ADMIN',
  'VIEWER',
  'CASE_MANAGER',
  'SUPERVISOR',
  'FINANCE',
  'HR',
  'SCHOOL_COORDINATOR',
]

export const SIGN_IN_PATH = {
  parent: '/clientlogin',
  therapist: '/therapistlogin',
  admin: '/adminlogin',
}

/** Default sign-in when portal is unknown — client portal. */
export const DEFAULT_SIGN_IN_PATH = SIGN_IN_PATH.parent

/** @param {'parent' | 'therapist' | 'admin' | null | undefined} portal */
export function portalLoginPath(portal) {
  if (!portal) return DEFAULT_SIGN_IN_PATH
  return SIGN_IN_PATH[portal] || DEFAULT_SIGN_IN_PATH
}

/** @param {'parent' | 'therapist' | 'staff' | null | undefined} apiPortal */
export function loginPathFromApiPortal(apiPortal) {
  if (apiPortal === 'parent') return SIGN_IN_PATH.parent
  if (apiPortal === 'therapist') return SIGN_IN_PATH.therapist
  if (apiPortal === 'staff') return SIGN_IN_PATH.admin
  return DEFAULT_SIGN_IN_PATH
}

/** @param {string | null | undefined} roleName */
export function loginPathFromRoleName(roleName) {
  const role = String(roleName || '').toUpperCase()
  if (role === 'PARENT') return SIGN_IN_PATH.parent
  if (role === 'THERAPIST') return SIGN_IN_PATH.therapist
  return SIGN_IN_PATH.admin
}

/**
 * Active portal for routing — respects selected sign-in page when roles match.
 * @param {{ roles?: string[] } | null} user
 * @param {'parent' | 'therapist' | 'admin' | null | undefined} selectedPortal
 */
export function resolveAuthPortal(user, selectedPortal) {
  if (!user?.roles?.length) return null
  if (selectedPortal === 'parent' && user.roles.includes('PARENT')) return 'parent'
  if (selectedPortal === 'therapist' && user.roles.includes('THERAPIST')) return 'therapist'
  if (selectedPortal === 'admin' && user.roles.some((r) => STAFF_LOGIN_ROLES.includes(r))) return 'admin'

  if (user.roles.includes('PARENT')) return 'parent'
  if (user.roles.some((r) => STAFF_LOGIN_ROLES.includes(r))) return 'admin'
  if (user.roles.includes('THERAPIST')) return 'therapist'
  return 'admin'
}

/** Post-auth home route for a user (ignores stale sign-in page selection). */
export function portalHomePath(user) {
  const resolved = resolveAuthPortal(user, null)
  if (resolved === 'parent') return '/parent'
  if (resolved === 'therapist') return '/therapist'
  if (resolved === 'admin') return '/admin'
  return SIGN_IN_PATH.parent
}

/** @param {'parent' | 'therapist' | 'admin'} portal */
export function userMatchesLoginPortal(user, portal) {
  if (!user?.roles?.length || !portal) return false
  return resolveAuthPortal(user, portal) === portal
}

/** User-facing message when credentials are valid but this portal is wrong. */
export function portalMismatchMessage() {
  return LOGIN_ERROR_WRONG_PORTAL
}

/** @param {string} message */
export function formatLoginErrorMessage(message) {
  const msg = message || ''
  if (/invalid credentials/i.test(msg)) {
    return LOGIN_ERROR_INVALID_CREDENTIALS
  }
  if (
    /cannot sign in on the/i.test(msg) ||
    /invalid login\. use the correct portal/i.test(msg) ||
    /use the correct portal/i.test(msg)
  ) {
    return LOGIN_ERROR_WRONG_PORTAL
  }
  return msg || 'Sign-in failed.'
}

/** Best sign-in URL when session exists but portal context does not match. */
export function preferredLoginPathForUser(user, selectedPortal) {
  if (selectedPortal) return portalLoginPath(selectedPortal)
  if (user?.roles?.includes('PARENT')) return SIGN_IN_PATH.parent
  if (user?.roles?.includes('THERAPIST')) return SIGN_IN_PATH.therapist
  if (user?.roles?.some((r) => STAFF_LOGIN_ROLES.includes(r))) return SIGN_IN_PATH.admin
  return DEFAULT_SIGN_IN_PATH
}
