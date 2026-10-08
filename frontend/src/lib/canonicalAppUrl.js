/**
 * Canonical production portal URLs (see docs/DOMAIN_CUTOVER_TEAM.md, manifest start_url).
 * Prefer VITE_APP_ORIGIN when set; on production UI hosts use www.insighte.org.
 */

import { PORTAL_PWA } from './portalPwa.js'

/** @type {RegExp} */
export const PRODUCTION_UI_HOSTS = /^((www\.)?insighte\.org|frontend-omega-eight-92\.vercel\.app)$/i

const MANIFEST_START_URL = {
  parent: '/parent',
  therapist: '/therapist',
  admin: '/admin',
}

function readEnv(key) {
  if (typeof import.meta !== 'undefined' && import.meta.env) {
    return import.meta.env[key]
  }
  return undefined
}

/**
 * Production app origin (no path, no trailing slash).
 * @param {{ hostname?: string, protocol?: string }} [ctx]
 */
export function resolveCanonicalAppOrigin(ctx = {}) {
  const fromEnv = String(readEnv('VITE_APP_ORIGIN') || '').replace(/\/$/, '')
  if (fromEnv) return fromEnv

  const hostname =
    ctx.hostname ??
    (typeof window !== 'undefined' ? window.location.hostname : '')
  const protocol =
    ctx.protocol ?? (typeof window !== 'undefined' ? window.location.protocol : 'https:')

  if (hostname === 'insighte.org') {
    return 'https://www.insighte.org'
  }
  if (hostname && PRODUCTION_UI_HOSTS.test(hostname)) {
    return `${protocol}//${hostname}`.replace(/\/$/, '')
  }

  if (typeof window !== 'undefined') {
    return window.location.origin
  }

  return 'https://www.insighte.org'
}

/**
 * @param {'parent' | 'therapist' | 'admin'} portalId
 * @param {{ origin?: string, hostname?: string }} [ctx]
 */
export function getCanonicalPortalUrl(portalId, ctx = {}) {
  const portal = PORTAL_PWA[portalId] ? portalId : 'parent'
  const path = MANIFEST_START_URL[portal] || MANIFEST_START_URL.parent
  const origin = (ctx.origin ?? resolveCanonicalAppOrigin(ctx)).replace(/\/$/, '')
  return `${origin}${path}`
}
