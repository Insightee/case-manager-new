/** Portal-specific PWA install metadata (one home-screen app per portal). */

export const PORTAL_PWA = {
  admin: {
    manifestHref: '/manifest-admin.webmanifest',
    appleTouchIcon: '/branding/portal-admin.png',
    installLabel: 'Add Admin Portal to home screen',
    appName: 'InsighteCase Admin',
  },
  therapist: {
    manifestHref: '/manifest-therapist.webmanifest',
    appleTouchIcon: '/branding/portal-therapist.png',
    installLabel: 'Add Therapist Portal to home screen',
    appName: 'InsighteCase Therapist',
  },
  parent: {
    manifestHref: '/manifest-parent.webmanifest',
    appleTouchIcon: '/branding/portal-parent.png',
    installLabel: 'Add Client Portal to home screen',
    appName: 'InsighteCase Client',
  },
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
