import { useCallback, useState } from 'react'
import { usePortalPwa } from './usePortalPwa.js'

export function usePortalInstallActions(portal, options = {}) {
  const pwa = usePortalPwa(portal, options)
  const [sheet, setSheet] = useState(null)

  const closeSheet = useCallback(() => setSheet(null), [])

  const runInstall = useCallback(async () => {
    if (pwa.canNativeInstall) {
      await pwa.promptInstall()
      return
    }
    if (pwa.iosSafari) {
      setSheet('ios')
      return
    }
    if (pwa.macSafari) {
      setSheet('mac')
      return
    }
    setSheet('generic')
  }, [pwa.canNativeInstall, pwa.iosSafari, pwa.macSafari, pwa.promptInstall])

  return {
    ...pwa,
    sheet,
    closeSheet,
    runInstall,
  }
}
