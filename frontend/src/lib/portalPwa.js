/** Portal-specific PWA install metadata (one home-screen app per portal). */

export const INSTALL_BANNER_DISMISS_MS = 30 * 24 * 60 * 60 * 1000

export const PORTAL_PWA = {
  admin: {
    manifestHref: '/manifest-admin.webmanifest',
    appleTouchIcon: '/branding/portal-admin.png',
    installLabel: 'Add Admin Portal to home screen',
    appName: 'InsighteCase Admin',
    bannerTitle: 'Open InsighteCase faster next time',
    bannerSubtitle: 'Add the Admin portal to your home screen — one tap from your phone.',
    bannerIcon: '/branding/portal-admin.png',
  },
  therapist: {
    manifestHref: '/manifest-therapist.webmanifest',
    appleTouchIcon: '/branding/portal-therapist.png',
    installLabel: 'Add Therapist Portal to home screen',
    appName: 'InsighteCase Therapist',
    bannerTitle: 'Open InsighteCase faster next time',
    bannerSubtitle: 'Add the Therapist portal to your home screen — quick access from the field.',
    bannerIcon: '/branding/portal-therapist.png',
  },
  parent: {
    manifestHref: '/manifest-parent.webmanifest',
    appleTouchIcon: '/branding/portal-parent.png',
    installLabel: 'Add Client Portal to home screen',
    appName: 'InsighteCase Client',
    bannerTitle: 'Open InsighteCase faster next time',
    bannerSubtitle: 'Add the Client portal to your home screen — session updates at your fingertips.',
    bannerIcon: '/branding/portal-parent.png',
  },
}

function installBannerDismissKey(portal) {
  return `insightcase:install-banner-dismissed:${portal}`
}

function portalInstalledKey(portal) {
  return `insightcase:portal-installed:${portal}`
}

export function isPortalMarkedInstalled(portal) {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(portalInstalledKey(portal)) === '1'
}

export function markPortalInstalled(portal) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(portalInstalledKey(portal), '1')
}

export function clearPortalInstalled(portal) {
  if (typeof localStorage === 'undefined') return
  localStorage.removeItem(portalInstalledKey(portal))
}

/** True when opened as installed app or user completed install for this portal. */
export function isPortalInstalled(portal) {
  if (isStandaloneDisplay()) return true
  return isPortalMarkedInstalled(portal)
}

export function isInstallBannerDismissed(portal) {
  if (typeof localStorage === 'undefined') return false
  const raw = localStorage.getItem(installBannerDismissKey(portal))
  if (!raw) return false
  const dismissedAt = Number(raw)
  if (!Number.isFinite(dismissedAt)) return false
  return Date.now() - dismissedAt < INSTALL_BANNER_DISMISS_MS
}

export function dismissInstallBanner(portal) {
  if (typeof localStorage === 'undefined') return
  localStorage.setItem(installBannerDismissKey(portal), String(Date.now()))
}

export function isStandaloneDisplay() {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    window.navigator.standalone === true
  )
}

function isSafariBrowser() {
  const ua = navigator.userAgent || ''
  return /Safari/.test(ua) && !/Chrome|Chromium|CriOS|Edg|EdgiOS|FxiOS|Firefox|OPR|OPiOS/.test(ua)
}

export function isIosSafari() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const isIos = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  return isIos && isSafariBrowser()
}

/** Desktop Safari on macOS (Add to Dock — no beforeinstallprompt). */
export function isMacSafari() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const isIos = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  if (isIos) return false
  const isMac = /Mac/.test(navigator.platform || '') || /Macintosh/.test(ua)
  return isMac && isSafariBrowser()
}

function upsertLink(rel, href, extra = {}) {
  let link = document.querySelector(`link[rel="${rel}"]`)
  if (!link) {
    link = document.createElement('link')
    link.rel = rel
    document.head.appendChild(link)
  }
  link.href = href
  Object.entries(extra).forEach(([key, value]) => {
    link.setAttribute(key, value)
  })
  return link
}

/** Point the document at the portal manifest + iOS icon while this shell is active. */
export function applyPortalPwaMeta(portal) {
  const config = PORTAL_PWA[portal]
  if (!config) return

  upsertLink('manifest', config.manifestHref)
  upsertLink('apple-touch-icon', config.appleTouchIcon)

  let capable = document.querySelector('meta[name="apple-mobile-web-app-capable"]')
  if (!capable) {
    capable = document.createElement('meta')
    capable.name = 'apple-mobile-web-app-capable'
    document.head.appendChild(capable)
  }
  capable.content = 'yes'

  let title = document.querySelector('meta[name="apple-mobile-web-app-title"]')
  if (!title) {
    title = document.createElement('meta')
    title.name = 'apple-mobile-web-app-title'
    document.head.appendChild(title)
  }
  title.content = config.appName
}
