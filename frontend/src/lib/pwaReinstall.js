/**
 * One-tap PWA reinstall flow for stale installed shortcuts (Chrome, Safari, Edge).
 *
 * Inside the old installed app: one action opens the canonical portal URL with ?reinstall=1
 * in the normal browser. The landing there shows: 1) remove the old app, 2) install again.
 * The reinstall URL is only ever built from the canonical origin + a fixed portal path;
 * the query flag is a boolean and nothing from the URL is reflected into the page.
 */

import { buildIosSafariOpenUrl, detectReinstallPlatform } from './appVersionUpdate.js'
import { getCanonicalPortalUrl } from './canonicalAppUrl.js'
import { PORTAL_PWA } from './portalPwa.js'

export const REINSTALL_QUERY_PARAM = 'reinstall'
export const REINSTALL_QUERY_VALUE = '1'
export const REINSTALL_LANDING_KEY = 'insightcase:reinstall-landing'
export const REINSTALL_LANDING_EVENT = 'insightcase:reinstall-landing-change'

const PORTAL_IDS = /** @type {const} */ (['parent', 'therapist', 'admin'])

export { detectReinstallPlatform }

/** @param {string} platform */
export function isIosPlatform(platform) {
  return platform === 'ios' || platform === 'ios-chrome' || platform === 'ios-edge'
}

/** Platforms where the browser can show its own install dialog (beforeinstallprompt). */
export function supportsOneTapInstall(platform) {
  return platform === 'android' || platform === 'android-edge' || platform === 'desktop' || platform === 'desktop-edge'
}

/**
 * @param {string | URL} url
 * @returns {string}
 */
export function appendReinstallParam(url) {
  const parsed = new URL(String(url), 'https://www.insighte.org')
  parsed.searchParams.set(REINSTALL_QUERY_PARAM, REINSTALL_QUERY_VALUE)
  return parsed.toString()
}

/**
 * @param {string} href
 * @returns {string} same URL without the reinstall flag (other params kept)
 */
export function stripReinstallParam(href) {
  const parsed = new URL(String(href), 'https://www.insighte.org')
  parsed.searchParams.delete(REINSTALL_QUERY_PARAM)
  return `${parsed.pathname}${parsed.search}${parsed.hash}`
}

/**
 * @param {URLSearchParams | string} search
 */
export function isReinstallLanding(search) {
  const params =
    typeof search === 'string'
      ? new URLSearchParams(search.startsWith('?') ? search.slice(1) : search)
      : search
  return params.get(REINSTALL_QUERY_PARAM) === REINSTALL_QUERY_VALUE
}

/**
 * @param {string} pathname
 * @returns {'parent' | 'therapist' | 'admin' | null}
 */
export function portalFromPath(pathname) {
  const p = String(pathname || '').toLowerCase()
  if (/^\/(therapist|therapistlogin)(\/|$)/.test(p)) return 'therapist'
  if (/^\/(parent|clientlogin|clinetlogin)(\/|$)/.test(p)) return 'parent'
  if (/^\/(admin|adminlogin|stafflogin|hr)(\/|$)/.test(p)) return 'admin'
  return null
}

function safeSession() {
  try {
    return typeof sessionStorage !== 'undefined' ? sessionStorage : null
  } catch {
    return null
  }
}

function notifyLandingChange() {
  if (typeof window !== 'undefined') window.dispatchEvent(new Event(REINSTALL_LANDING_EVENT))
}

/**
 * Called once in main.jsx before React renders, so login redirects that drop the query
 * (/therapist -> /therapistlogin) still show the landing in this tab.
 * @param {{ pathname: string, search: string }} [loc]
 */
export function captureReinstallLanding(loc = typeof window !== 'undefined' ? window.location : null) {
  if (!loc || !isReinstallLanding(loc.search)) return false
  const store = safeSession()
  const portal = portalFromPath(loc.pathname) || ''
  store?.setItem(REINSTALL_LANDING_KEY, portal)
  return true
}

/**
 * @returns {{ active: boolean, portal: 'parent' | 'therapist' | 'admin' | null }}
 */
export function readReinstallLanding() {
  const fromUrl = typeof window !== 'undefined' && isReinstallLanding(window.location.search)
  const stored = safeSession()?.getItem(REINSTALL_LANDING_KEY)
  const active = fromUrl || stored != null
  const portalRaw =
    stored || (typeof window !== 'undefined' ? portalFromPath(window.location.pathname) : null) || ''
  const portal = PORTAL_IDS.includes(/** @type {any} */ (portalRaw)) ? /** @type {any} */ (portalRaw) : null
  return { active, portal }
}

/** Remove ?reinstall=1 from the address bar without a navigation. */
export function stripReinstallParamFromAddressBar() {
  if (typeof window === 'undefined' || !isReinstallLanding(window.location.search)) return
  try {
    window.history.replaceState(window.history.state, '', stripReinstallParam(window.location.href))
  } catch {
    // ignore
  }
}

/** End the landing: forget the flag and remove ?reinstall=1 from the address bar. */
export function clearReinstallLanding() {
  safeSession()?.removeItem(REINSTALL_LANDING_KEY)
  stripReinstallParamFromAddressBar()
  notifyLandingChange()
}

/**
 * @param {string} httpsUrl must be an https URL
 * @param {'com.android.chrome' | 'com.microsoft.emmx'} [androidPackage]
 */
export function buildAndroidBrowserIntentUrl(httpsUrl, androidPackage = 'com.android.chrome') {
  const parsed = new URL(httpsUrl)
  if (parsed.protocol !== 'https:') throw new Error('intent target must be https')
  const pkg = androidPackage === 'com.microsoft.emmx' ? 'com.microsoft.emmx' : 'com.android.chrome'
  const path = `${parsed.pathname}${parsed.search}`
  const fallback = encodeURIComponent(parsed.toString())
  return `intent://${parsed.host}${path}#Intent;scheme=https;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=${pkg};S.browser_fallback_url=${fallback};end`
}

/**
 * @param {'parent' | 'therapist' | 'admin' | null | undefined} portalId
 */
export function getReinstallUrl(portalId) {
  return appendReinstallParam(getCanonicalPortalUrl(portalId || 'parent'))
}

/** @param {'parent' | 'therapist' | 'admin' | null | undefined} portalId */
export function getPortalAppName(portalId) {
  return (portalId && PORTAL_PWA[portalId]?.appName) || 'InsighteCase'
}

/**
 * Step 1 on the landing (runs in the browser, so removing the old app is safe).
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 * @param {string} appName
 */
export function getRemoveAppOneLiner(platform, appName) {
  const label = appName || 'InsighteCase'
  if (isIosPlatform(platform)) {
    return `Press and hold the old ${label} icon on your home screen, tap Remove, then confirm.`
  }
  if (platform === 'android' || platform === 'android-edge') {
    return `Press and hold the old ${label} icon on your home screen, then tap Uninstall.`
  }
  if (platform === 'desktop-edge') {
    return `Open the old ${label} app, click the … menu at the top, then Uninstall.`
  }
  if (platform === 'mac-safari') {
    return `In Finder, open Applications and move the old ${label} app to the Trash.`
  }
  return `Open the old ${label} app, click the ⋮ menu at the top, then Uninstall.`
}

/**
 * Step 2 where the browser has no install button we can trigger (Safari).
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 */
export function getManualAddLine(platform) {
  if (platform === 'ios-chrome' || platform === 'ios-edge') {
    return 'Tap the Share button in the address bar, then Add to Home Screen, then Add.'
  }
  if (platform === 'mac-safari') {
    return 'In the Safari menu bar, choose File, then Add to Dock.'
  }
  return 'Tap the Share button, then Add to Home Screen, then Add.'
}

/** @param {ReturnType<typeof detectReinstallPlatform>} platform */
export function getManualAddHint(platform) {
  if (platform === 'ios') {
    return 'On newer iPhones the Share button is inside the ⋯ menu. In Chrome or Edge it is in the address bar.'
  }
  return ''
}

/** @param {ReturnType<typeof detectReinstallPlatform>} platform */
export function getInstalledMessage(platform) {
  const where = platform.startsWith('desktop') || platform === 'mac-safari' ? 'desktop' : 'home screen'
  return `Installed. Open InsighteCase from your ${where}.`
}

/**
 * Open the canonical reinstall URL in the system browser (called from the old installed app).
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 * @param {'parent' | 'therapist' | 'admin'} portalId
 * @param {{ assign?: (url: string) => void, open?: typeof window.open }} [nav]
 */
export function launchReinstallInBrowser(platform, portalId, nav = {}) {
  const target = getReinstallUrl(portalId)
  const assign = nav.assign || ((url) => window.location.assign(url))
  const open = nav.open || ((...args) => window.open(...args))
  if (isIosPlatform(platform)) {
    // x-safari-https hands off to Safari; noopener can't be used with a scheme handoff.
    assign(buildIosSafariOpenUrl(target))
    return target
  }
  if (platform === 'android') {
    assign(buildAndroidBrowserIntentUrl(target, 'com.android.chrome'))
    return target
  }
  if (platform === 'android-edge') {
    assign(buildAndroidBrowserIntentUrl(target, 'com.microsoft.emmx'))
    return target
  }
  open(target, '_blank', 'noopener,noreferrer')
  return target
}

/**
 * @param {string} text
 * @returns {Promise<boolean>}
 */
export async function copyText(text) {
  try {
    if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // fall through
  }
  return false
}
