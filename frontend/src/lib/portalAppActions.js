/**
 * Portal install / refresh menu: both actions stay available.
 * Primary label follows where the therapist is — browser vs installed dock/PWA.
 */

export function primaryPortalAppAction({ standalone } = {}) {
  return standalone ? 'refresh' : 'install'
}

/** Menu order: primary action first, the other second. Always both. */
export function portalAppMenuItems(primary) {
  if (primary === 'refresh') return ['refresh', 'install']
  return ['install', 'refresh']
}

/**
 * Topbar/sidebar stay visible after install so Refresh remains reachable.
 * The install banner stays a one-time browser prompt and hides once installed.
 */
export function canShowPortalAppActions(
  surface,
  { installed, config, canNativeInstall, iosSafari, macSafari, isMobilePortal } = {},
) {
  if (!config) return false
  if (surface === 'banner') {
    return Boolean(!installed && isMobilePortal)
  }
  if (installed) return true
  if (surface === 'sidebar') {
    return Boolean(canNativeInstall || iosSafari || macSafari)
  }
  return Boolean(isMobilePortal || canNativeInstall || iosSafari || macSafari)
}
