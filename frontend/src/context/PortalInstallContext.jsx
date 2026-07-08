import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  applyPortalPwaMeta,
  isIosSafari,
  isMacSafari,
  isStandaloneDisplay,
  PORTAL_PWA,
} from '../lib/portalPwa.js'
import { PortalInstallContext } from './portalInstallContext.js'

export function PortalInstallProvider({ portal, children }) {
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [installed, setInstalled] = useState(() => isStandaloneDisplay())
  const iosSafari = useMemo(() => isIosSafari(), [])
  const macSafari = useMemo(() => isMacSafari(), [])
  const config = PORTAL_PWA[portal] ?? null

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

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt) {
      return { outcome: 'unavailable' }
    }
    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    setDeferredPrompt(null)
    if (choice.outcome === 'accepted') {
      setInstalled(true)
    }
    return choice
  }, [deferredPrompt])

  const value = useMemo(
    () => ({
      portal,
      config,
      installed,
      iosSafari,
      macSafari,
      canNativeInstall: Boolean(deferredPrompt),
      promptInstall,
    }),
    [portal, config, installed, iosSafari, macSafari, deferredPrompt, promptInstall],
  )

  return <PortalInstallContext.Provider value={value}>{children}</PortalInstallContext.Provider>
}
