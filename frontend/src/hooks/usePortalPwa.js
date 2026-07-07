import { useCallback, useEffect, useState } from 'react'
import { applyPortalPwaMeta, isIosSafari, isStandaloneDisplay, PORTAL_PWA } from '../lib/portalPwa.js'
import { useIsMobilePortal } from './useMediaQuery.js'

export function usePortalPwa(portal, options = {}) {
  const { surface = 'topbar' } = options
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [installed, setInstalled] = useState(() => isStandaloneDisplay())
  const [iosSafari] = useState(() => isIosSafari())
  const isMobilePortal = useIsMobilePortal()

  useEffect(() => {
    applyPortalPwaMeta(portal)
  }, [portal])

  useEffect(() => {
    function onBeforeInstallPrompt(event) {
      event.preventDefault()
      setDeferredPrompt(event)
    }

    function onAppInstalled() {
      setInstalled(true)
      setDeferredPrompt(null)
    }

    function onDisplayModeChange() {
      setInstalled(isStandaloneDisplay())
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.addEventListener('appinstalled', onAppInstalled)
    window.matchMedia('(display-mode: standalone)').addEventListener('change', onDisplayModeChange)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      window.removeEventListener('appinstalled', onAppInstalled)
      window.matchMedia('(display-mode: standalone)').removeEventListener('change', onDisplayModeChange)
    }
  }, [])

  const config = PORTAL_PWA[portal]
  const canNativeInstall = Boolean(deferredPrompt)
  const canShowInstall =
    Boolean(config) &&
    !installed &&
    (surface === 'sidebar'
      ? canNativeInstall || iosSafari
      : isMobilePortal || canNativeInstall || iosSafari)

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt) return { outcome: 'unavailable' }
    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    setDeferredPrompt(null)
    if (choice.outcome === 'accepted') {
      setInstalled(true)
    }
    return choice
  }, [deferredPrompt])

  return {
    config,
    installed,
    iosSafari,
    canNativeInstall,
    canShowInstall,
    promptInstall,
  }
}
