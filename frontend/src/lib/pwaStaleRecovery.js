/** Detect stale PWA / cached bundle issues after deploys (field therapists & parents). */

import { getCanonicalPortalUrl } from './canonicalAppUrl.js'

export const PWA_STALE_HINT_KEY = 'insightcase:pwa-stale-hint'

const STALE_MESSAGE_FRAGMENTS = [
  'failed to fetch dynamically imported module',
  'error loading dynamically imported module',
  'importing a module script failed',
  'failed to load module script',
  'dynamically imported module',
  'chunkloaderror',
]

export function markPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(PWA_STALE_HINT_KEY, String(Date.now()))
}

export function hasPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return false
  return Boolean(sessionStorage.getItem(PWA_STALE_HINT_KEY))
}

export function clearPwaStaleHint() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.removeItem(PWA_STALE_HINT_KEY)
}

/** @param {unknown} err */
export function isLikelyStaleAppError(err) {
  const msg = String(err?.message || err || '').toLowerCase()
  if (err?.name === 'ChunkLoadError') return true
  if (STALE_MESSAGE_FRAGMENTS.some((fragment) => msg.includes(fragment))) return true
  // Safari standalone often reports a generic "Load failed" for network errors — ignore unless
  // the rejection looks like a failed module/chunk load.
  if (msg === 'load failed' || msg === 'error: load failed') {
    const stack = String(err?.stack || '').toLowerCase()
    const cause = String(err?.cause?.message || err?.cause || '').toLowerCase()
    const context = `${stack} ${cause}`
    return /import|chunk|module script|preload|vite/.test(context)
  }
  return false
}

/**
 * Login failures in a home-screen app are often a stale bundle, not bad passwords.
 * @param {unknown} err
 * @param {{ standalone?: boolean }} [opts]
 */
export function isLikelyStaleLoginFailure(err, opts = {}) {
  if (!opts.standalone) return false
  const msg = String(err?.message || err || '').toLowerCase()
  if (msg.includes('invalid credentials')) return false
  if (msg.includes('invalid login')) return false
  if (msg.includes('use the correct portal')) return false
  if (isLikelyStaleAppError(err)) return true
  if (isGenericNetworkFailureMessage(msg)) return false
  if (/unexpected token|<!doctype/i.test(msg)) return true
  return false
}

function isGenericNetworkFailureMessage(msg) {
  if (msg === 'load failed' || msg === 'error: load failed') return true
  if (msg === 'failed to fetch') return true
  if (msg.includes('network request failed')) return true
  if (msg.includes('network') && !msg.includes('module')) return true
  return false
}

export function portalUrlForBrowser(portalId = 'parent') {
  if (typeof window === 'undefined') return ''
  const canonical = getCanonicalPortalUrl(portalId)
  if (canonical) return canonical
  return window.location.href
}

export async function copyPortalUrlForBrowser(portalId = 'parent') {
  const url = portalUrlForBrowser(portalId)
  if (!url) return { ok: false }
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(url)
      return { ok: true, url }
    }
  } catch {
    // fall through
  }
  return { ok: false, url }
}

export async function copyCanonicalPortalUrl(portalId = 'parent') {
  return copyPortalUrlForBrowser(portalId)
}
