import { SIGN_IN_PATH } from './portalLogin.js'

/** Zero-width and other invisible characters often pasted from email clients. */
const INVISIBLE_IN_PATH = /[\u200B-\u200D\uFEFF\u00AD]/g

/** Known portal login paths and common aliases (after invisible-char removal). */
const PORTAL_PATH_ALIASES = new Map([
  ['/therapist-login', SIGN_IN_PATH.therapist],
  ['/client-login', SIGN_IN_PATH.parent],
  ['/staff-login', SIGN_IN_PATH.admin],
  ['/stafflogin', SIGN_IN_PATH.admin],
  ['/clinetlogin', SIGN_IN_PATH.parent],
])

/**
 * Strip invisible Unicode from a URL pathname and map known portal aliases.
 * @param {string} pathname
 * @returns {string}
 */
export function normalizePathname(pathname) {
  let path = String(pathname || '/').replace(INVISIBLE_IN_PATH, '')
  if (!path.startsWith('/')) path = `/${path}`
  path = path.replace(/\/{2,}/g, '/')
  const alias = PORTAL_PATH_ALIASES.get(path.toLowerCase())
  if (alias) return alias
  return path || '/'
}
