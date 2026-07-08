import { useCallback, useState } from 'react'
import { usePortalInstall } from '../context/usePortalInstall.js'
import { useIsMobilePortal } from './useMediaQuery.js'

function canShowInstallSurface(surface, { installed, config, canNativeInstall, iosSafari, macSafari, isMobilePortal }) {
  if (!config || installed) {
    return false
  }
  if (surface === 'banner') {
    return isMobilePortal
  }
  if (surface === 'sidebar') {
    return canNativeInstall || iosSafari || macSafari
  }
  return isMobilePortal || canNativeInstall || iosSafari || macSafari
}

export function usePortalInstallActions(surface = 'topbar') {
  const install = usePortalInstall()
  const isMobilePortal = useIsMobilePortal()
  const [sheet, setSheet] = useState(null)

  const closeSheet = useCallback(() => setSheet(null), [])

  const canShowInstall = canShowInstallSurface(surface, {
    ...install,
    isMobilePortal,
  })

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
    canShowInstall,
    canNativeInstall: install.canNativeInstall,
    sheet,
    closeSheet,
    runInstall,
  }
}
