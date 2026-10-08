/** Build / version labels for optional update notice (all portals). Auto-update is handled in main.jsx. */

import { isStandaloneDisplay } from './portalPwa.js'
import {
  getEmbeddedReleaseLabel,
  isDeployedReleaseNewer,
} from './releaseLabel.js'

export const VERSION_DISMISS_KEY = 'insightcase:version-notice-dismissed'
export const VERSION_PRIOR_STALE_KEY = 'insightcase:version-prior-stale-build'
export const VERSION_CHECK_TS_KEY = 'insightcase:version-last-check'

const MIN_CHECK_INTERVAL_MS = 5 * 60 * 1000

export function getEmbeddedBuildId() {
  if (typeof import.meta !== 'undefined' && import.meta.env?.VITE_BUILD_ID) {
    return String(import.meta.env.VITE_BUILD_ID)
  }
  return 'dev'
}

export { getEmbeddedReleaseLabel }

export function shouldPollRemoteVersion() {
  if (import.meta.env?.VITE_VERSION_POLL === 'true') return true
  return Boolean(import.meta.env?.PROD)
}

/** @deprecated use isDeployedReleaseNewer */
export function isRemoteBuildNewer(embedded, remote) {
  return isDeployedReleaseNewer(embedded, remote)
}

/** @param {unknown} err */
export function isGenericNetworkError(err) {
  const msg = String(err?.message || err || '').toLowerCase().trim()
  if (!msg) return false
  if (msg === 'load failed' || msg === 'error: load failed') return true
  if (msg === 'failed to fetch' || msg === 'networkerror when attempting to fetch resource.') return true
  if (msg.includes('network request failed')) return true
  return false
}

/**
 * @param {string} embedded
 * @param {string | null | undefined} remote
 */
export function formatVersionNoticeLead(embedded, remote) {
  const you = embedded || 'unknown'
  const latest = remote || 'unknown'
  return `You're on ${you}, latest is ${latest}.`
}

export function clearPriorStaleBuild() {
  if (typeof localStorage === 'undefined') return
  localStorage.removeItem(VERSION_PRIOR_STALE_KEY)
}

/**
 * After auto-update, offer reinstall guidance only if this build was already stale on a prior visit.
 * @param {string} buildKey
 * @param {boolean} remoteNewer
 */
export function shouldOfferReinstallFallback(buildKey, remoteNewer) {
  if (!remoteNewer) {
    clearPriorStaleBuild()
    return false
  }
  if (typeof localStorage === 'undefined') return false
  const key = buildKey || 'unknown'
  const prior = localStorage.getItem(VERSION_PRIOR_STALE_KEY)
  if (prior === key) return true
  localStorage.setItem(VERSION_PRIOR_STALE_KEY, key)
  return false
}

/**
 * Re-add shortcut steps for the browsers we support: Chrome, Safari and Edge.
 * Other browsers fall back to the closest of these (Chromium-style on Android
 * and desktop, the shared iOS home-screen flow on iPhone).
 * @param {'ios' | 'ios-chrome' | 'ios-edge' | 'android' | 'android-edge' | 'mac-safari' | 'desktop' | 'desktop-edge'} platform
 * @param {{ portalUrl: string, appName: string }} ctx
 */
export function getReinstallSteps(platform, { portalUrl, appName }) {
  const link = portalUrl || 'your InsighteCase link'
  const copyStep = { id: 'copy', kind: 'action', action: 'copy', label: 'Copy link' }
  const androidRemove = {
    id: 'remove',
    kind: 'text',
    text: `Remove the old ${appName} home screen shortcut (press and hold the icon → Uninstall or Remove).`,
  }

  if (platform === 'ios' || platform === 'ios-chrome' || platform === 'ios-edge') {
    const browser = platform === 'ios-chrome' ? 'Chrome' : platform === 'ios-edge' ? 'Edge' : 'Safari'
    return [
      copyStep,
      {
        id: 'remove',
        kind: 'text',
        text: `Press and hold the old ${appName} icon on your home screen, then choose Remove App → Delete from Home Screen.`,
      },
      {
        id: 'open-browser',
        kind: 'action',
        action: platform === 'ios' ? 'open_safari' : 'open_browser',
        label: `Open in ${browser}`,
        hint: `Paste the link in ${browser} if it does not open automatically. Safari, Chrome and Edge on iPhone all use the same steps.`,
      },
      {
        id: 'add',
        kind: 'text',
        text:
          browser === 'Safari'
            ? 'Tap Share (the square with an arrow) → Add to Home Screen → Add.'
            : `Tap the Share icon in the address bar, or ⋯ → Share → Add to Home Screen → Add.`,
      },
    ]
  }

  if (platform === 'android' || platform === 'android-edge') {
    const browser = platform === 'android-edge' ? 'Edge' : 'Chrome'
    return [
      copyStep,
      androidRemove,
      {
        id: 'open-browser',
        kind: 'action',
        action: 'open_browser',
        label: `Open in ${browser}`,
        hint: `Paste ${link} in ${browser} if needed.`,
      },
      {
        id: 'install',
        kind: 'text',
        text:
          browser === 'Edge'
            ? 'Tap … → Add to phone → Install app (or Add to Home screen) → Add.'
            : 'Tap ⋮ → Install app or Add to Home screen → Add.',
      },
    ]
  }

  if (platform === 'mac-safari') {
    return [
      copyStep,
      {
        id: 'remove',
        kind: 'text',
        text: `Quit the old ${appName} app, then in Finder open Applications (or your home folder → Applications) and move ${appName} to the Trash (Bin).`,
      },
      {
        id: 'open',
        kind: 'action',
        action: 'open_browser',
        label: 'Open in Safari',
        hint: 'Paste the link in a normal Safari window if it does not open automatically.',
      },
      {
        id: 'install',
        kind: 'text',
        text: 'In Safari choose File → Add to Dock (or Share → Add to Dock) → Add.',
      },
    ]
  }

  if (platform === 'desktop-edge') {
    return [
      copyStep,
      {
        id: 'open',
        kind: 'action',
        action: 'open_browser',
        label: 'Open in Edge',
        hint: 'Use a normal Edge tab, not the installed app window.',
      },
      {
        id: 'remove',
        kind: 'text',
        text: `Remove the old ${appName} shortcut: in the app window open … → App settings → Uninstall, or go to edge://apps, right‑click the icon → Uninstall.`,
      },
      {
        id: 'install',
        kind: 'text',
        text: 'Re-add it: use the install icon in the address bar, or … → Apps → Install this site as an app → Install.',
      },
    ]
  }

  return [
    copyStep,
    {
      id: 'open',
      kind: 'action',
      action: 'open_browser',
      label: 'Open in Chrome',
      hint: 'Use a normal Chrome tab, not the installed shortcut window.',
    },
    {
      id: 'remove',
      kind: 'text',
      text: `Remove the old ${appName} shortcut: in the app window open ⋮ → Uninstall ${appName}, or go to chrome://apps, right‑click the icon → Remove.`,
    },
    {
      id: 'install',
      kind: 'text',
      text: 'Re-add the shortcut: use the install icon in the address bar, or ⋮ → Cast, save and share → Install page as app.',
    },
  ]
}

/**
 * @param {string | { userAgent?: string, platform?: string, maxTouchPoints?: number }} [input]
 * @returns {'ios' | 'ios-chrome' | 'ios-edge' | 'android' | 'android-edge' | 'mac-safari' | 'desktop' | 'desktop-edge'}
 */
export function detectReinstallPlatform(input) {
  const env =
    typeof input === 'string'
      ? { userAgent: input }
      : input != null && typeof input === 'object'
        ? input
        : {}

  const ua = env.userAgent ?? (typeof navigator !== 'undefined' ? navigator.userAgent : '')
  const platform = env.platform ?? (typeof navigator !== 'undefined' ? navigator.platform : '')
  const maxTouchPoints =
    env.maxTouchPoints ?? (typeof navigator !== 'undefined' ? navigator.maxTouchPoints : 0)

  // Every iPhone / iPad browser is WebKit. Name the three we support; anything else gets Safari's steps.
  if (/iPad|iPhone|iPod/i.test(ua) || (platform === 'MacIntel' && maxTouchPoints > 1)) {
    if (/CriOS/i.test(ua)) return 'ios-chrome'
    if (/EdgiOS/i.test(ua)) return 'ios-edge'
    return 'ios'
  }
  if (/Android/i.test(ua)) {
    if (/EdgA\//i.test(ua)) return 'android-edge'
    return 'android'
  }
  if (/Edg\//i.test(ua)) return 'desktop-edge'
  if (/Macintosh|Mac OS X/i.test(ua) && /Safari\//i.test(ua) && !/Chrome|Chromium|CriOS|Edg|OPR|Firefox/i.test(ua)) {
    return 'mac-safari'
  }
  return 'desktop'
}

/**
 * @param {string} httpsUrl
 * @returns {string}
 */
export function buildIosSafariOpenUrl(httpsUrl) {
  const raw = String(httpsUrl || '').trim()
  if (!raw) return ''
  if (raw.startsWith('x-safari-https://')) return raw
  const stripped = raw.replace(/^https:\/\//i, '')
  return `x-safari-https://${stripped}`
}

export function dismissVersionNoticeForSession(releaseKey) {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(VERSION_DISMISS_KEY, releaseKey || 'unknown')
}

export function isVersionNoticeDismissed(releaseKey) {
  if (typeof sessionStorage === 'undefined') return false
  const dismissed = sessionStorage.getItem(VERSION_DISMISS_KEY)
  return dismissed && releaseKey && dismissed === releaseKey
}

export function canCheckVersionNow() {
  if (typeof sessionStorage === 'undefined') return true
  const raw = sessionStorage.getItem(VERSION_CHECK_TS_KEY)
  if (!raw) return true
  const last = Number(raw)
  if (!Number.isFinite(last)) return true
  return Date.now() - last >= MIN_CHECK_INTERVAL_MS
}

export function markVersionChecked() {
  if (typeof sessionStorage === 'undefined') return
  sessionStorage.setItem(VERSION_CHECK_TS_KEY, String(Date.now()))
}

/**
 * @param {{
 *   embeddedReleaseLabel: string
 *   remoteReleaseLabel?: string | null
 *   chunkStale?: boolean
 *   standalone?: boolean
 * }} input
 */
export function shouldShowVersionNotice(input) {
  const {
    embeddedReleaseLabel,
    remoteReleaseLabel = null,
    chunkStale = false,
    standalone = isStandaloneDisplay(),
  } = input

  const remoteNewer = isDeployedReleaseNewer(embeddedReleaseLabel, remoteReleaseLabel)
  const buildKey = remoteReleaseLabel || embeddedReleaseLabel || 'unknown'

  if (!remoteNewer && !chunkStale) {
    return { show: false, buildKey, remoteNewer: false, reinstallFallback: false }
  }

  if (isVersionNoticeDismissed(buildKey) && remoteNewer && !chunkStale) {
    return { show: false, buildKey, remoteNewer: false, reinstallFallback: false }
  }

  return {
    show: true,
    buildKey,
    remoteNewer,
    reinstallFallback: false,
  }
}

/**
 * Fetch /version.json (cache-busted lightly).
 * @returns {Promise<{ buildId: string, releaseLabel: string } | null>}
 */
export async function fetchRemoteVersionMeta() {
  if (!shouldPollRemoteVersion()) return null
  if (!canCheckVersionNow()) return null
  markVersionChecked()
  const url = `/version.json?t=${Date.now()}`
  try {
    const res = await fetch(url, { cache: 'no-store', credentials: 'same-origin' })
    if (!res.ok) return null
    const data = await res.json()
    if (!data?.releaseLabel) return null
    return {
      buildId: data.buildId ? String(data.buildId) : '',
      releaseLabel: String(data.releaseLabel),
    }
  } catch (err) {
    if (isGenericNetworkError(err)) return null
    return null
  }
}
