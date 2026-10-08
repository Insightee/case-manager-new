/** One-tap PWA reinstall flow (Chrome, Safari, Edge). Reuses PortalInstallContext prompt() on landing pages. */

import { buildIosSafariOpenUrl, detectReinstallPlatform } from './appVersionUpdate.js'

export const REINSTALL_QUERY_PARAM = 'reinstall'
export const REINSTALL_QUERY_VALUE = '1'

export { detectReinstallPlatform }

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
 * @param {string} httpsUrl
 * @param {'com.android.chrome' | 'com.microsoft.emmx'} [androidPackage]
 */
export function buildAndroidBrowserIntentUrl(httpsUrl, androidPackage = 'com.android.chrome') {
  const parsed = new URL(httpsUrl)
  const path = `${parsed.pathname}${parsed.search}${parsed.hash}`
  return `intent://${parsed.host}${path}#Intent;scheme=https;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;package=${androidPackage};end`
}

/**
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 * @param {string} appName
 */
export function getRemoveAppOneLiner(platform, appName) {
  const label = appName || 'InsighteCase'
  if (platform === 'ios' || platform === 'ios-chrome' || platform === 'ios-edge') {
    return `Press and hold the old ${label} icon on your home screen, then tap Remove App → Delete from Home Screen.`
  }
  if (platform === 'android') {
    return `Press and hold the old ${label} icon, then tap Uninstall or Remove.`
  }
  if (platform === 'android-edge') {
    return `Press and hold the old ${label} icon, then tap Uninstall or Remove.`
  }
  if (platform === 'desktop-edge') {
    return `Remove the old ${label} app: … → Apps → Manage apps → Uninstall.`
  }
  if (platform === 'mac-safari') {
    return `Remove the old ${label} icon from the Dock (right‑click → Remove from Dock).`
  }
  return `Remove the old ${label} app: open ⋮ in the app window → Uninstall, or go to chrome://apps and remove it.`
}

/**
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 */
export function getBrowserMenuInstallFallback(platform) {
  if (platform === 'desktop-edge' || platform === 'android-edge') {
    return '… → Apps → Install this site as an app'
  }
  if (platform.startsWith('ios')) {
    return 'Share → Add to Home Screen'
  }
  return '⋮ → Install app (or Add to Home screen)'
}

/**
 * Open canonical URL in the system browser with ?reinstall=1 (from an installed shortcut window).
 * @param {ReturnType<typeof detectReinstallPlatform>} platform
 * @param {string} httpsUrl
 */
export function launchReinstallInBrowser(platform, httpsUrl) {
  const target = appendReinstallParam(httpsUrl)
  if (platform === 'ios' || platform === 'ios-chrome' || platform === 'ios-edge') {
    window.location.href = buildIosSafariOpenUrl(target)
    return
  }
  if (platform === 'android') {
    window.location.href = buildAndroidBrowserIntentUrl(target, 'com.android.chrome')
    return
  }
  if (platform === 'android-edge') {
    window.location.href = buildAndroidBrowserIntentUrl(target, 'com.microsoft.emmx')
    return
  }
  window.open(target, '_blank', 'noopener,noreferrer')
}

export async function hasInstalledRelatedPwa() {
  if (typeof navigator === 'undefined' || !navigator.getInstalledRelatedApps) return false
  try {
    const related = await navigator.getInstalledRelatedApps()
    return Array.isArray(related) && related.length > 0
  } catch {
    return false
  }
}
