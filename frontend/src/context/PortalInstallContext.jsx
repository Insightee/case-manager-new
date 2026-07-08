import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  applyPortalPwaMeta,
  clearPortalInstalled,
  isIosSafari,
  isMacSafari,
  isPortalInstalled,
  isStandaloneDisplay,
  markPortalInstalled,
  PORTAL_PWA,
} from '../lib/portalPwa.js'
import { PortalInstallContext } from './portalInstallContext.js'

function readInstalled(portal) {
  if (isStandaloneDisplay()) {
    markPortalInstalled(portal)
    return true
  }
  return isPortalInstalled(portal)
}

export function PortalInstallProvider({ portal, children }) {
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [installed, setInstalled] = useState(() => readInstalled(portal))
  const iosSafari = useMemo(() => isIosSafari(), [])
  const macSafari = useMemo(() => isMacSafari(), [])
  const config = PORTAL_PWA[portal] ?? null

  useEffect(() => {
    applyPortalPwaMeta(portal)
  }, [portal])

  useEffect(() => {
    function onBeforeInstallPrompt(event) {
      event.preventDefault()
      clearPortalInstalled(portal)
      setInstalled(false)
      setDeferredPrompt(event)
    }

    function onAppInstalled() {
      markPortalInstalled(portal)
      setInstalled(true)
      setDeferredPrompt(null)
    }

    function onDisplayModeChange() {
      if (isStandaloneDisplay()) {
        markPortalInstalled(portal)
        setInstalled(true)
        return
      }
      setInstalled(isPortalInstalled(portal))
    }

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.addEventListener('appinstalled', onAppInstalled)
    window.matchMedia('(display-mode: standalone)').addEventListener('change', onDisplayModeChange)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      window.removeEventListener('appinstalled', onAppInstalled)
      window.matchMedia('(display-mode: standalone)').removeEventListener('change', onDisplayModeChange)
    }
  }, [portal])

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt) {
      return { outcome: 'unavailable' }
    }
    deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    setDeferredPrompt(null)
    if (choice.outcome === 'accepted') {
      markPortalInstalled(portal)
      setInstalled(true)
    }
    return choice
  }, [deferredPrompt, portal])

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
