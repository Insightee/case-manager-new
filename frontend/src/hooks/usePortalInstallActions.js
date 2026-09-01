import { useCallback, useState } from 'react'
import { usePortalInstall } from '../context/usePortalInstall.js'
import { canShowPortalAppActions, primaryPortalAppAction } from '../lib/portalAppActions.js'
import { isStandaloneDisplay } from '../lib/portalPwa.js'
import { useIsMobilePortal } from './useMediaQuery.js'

export function usePortalInstallActions(surface = 'topbar') {
  const install = usePortalInstall()
  const isMobilePortal = useIsMobilePortal()
  const [sheet, setSheet] = useState(null)
  const standalone = isStandaloneDisplay()

  const closeSheet = useCallback(() => setSheet(null), [])

  const canShowInstall = canShowPortalAppActions(surface, {
    ...install,
    isMobilePortal,
  })
  const primaryAction = primaryPortalAppAction({ standalone })

  const runInstall = useCallback(async () => {
    if (install.canNativeInstall) {
      return install.promptInstall()
    }
    if (install.iosSafari) {
      setSheet('ios')
      return { outcome: 'sheet' }
    }
    if (install.macSafari) {
      setSheet('mac')
      return { outcome: 'sheet' }
    }
    setSheet('generic')
    return { outcome: 'sheet' }
  }, [install.canNativeInstall, install.iosSafari, install.macSafari, install.promptInstall])

  return {
    config: install.config,
    installed: install.installed,
    standalone,
    primaryAction,
    canShowInstall,
    canNativeInstall: install.canNativeInstall,
    sheet,
    closeSheet,
    runInstall,
  }
}
