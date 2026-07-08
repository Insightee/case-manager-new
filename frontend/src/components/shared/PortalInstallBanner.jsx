import { useEffect, useState } from 'react'
import { usePortalInstall } from '../../context/usePortalInstall.js'
import { usePortalInstallActions } from '../../hooks/usePortalInstallActions.js'
import { useIsMobilePortal } from '../../hooks/useMediaQuery.js'
import { dismissInstallBanner, isInstallBannerDismissed } from '../../lib/portalPwa.js'
import { PortalInstallSheets } from './PortalInstallSheets.jsx'
import './portal-install.css'

const BANNER_DELAY_MS = 2500

export function PortalInstallBanner() {
  const { portal } = usePortalInstall()
  const isMobilePortal = useIsMobilePortal()
  const [revealed, setRevealed] = useState(false)
  const [dismissedSession, setDismissedSession] = useState(false)
  const dismissed = dismissedSession || isInstallBannerDismissed(portal)
  const { config, canShowInstall, installed, runInstall, sheet, closeSheet } = usePortalInstallActions('banner')

  const eligible = isMobilePortal && canShowInstall && !dismissed && !installed

  useEffect(() => {
    if (!eligible) {
      return undefined
    }
    const timer = window.setTimeout(() => setRevealed(true), BANNER_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [eligible])

  if (!config) {
    return null
  }

  function handleDismiss() {
    dismissInstallBanner(portal)
    setDismissedSession(true)
  }

  const showBanner = eligible && revealed

  return (
    <>
      {showBanner ? (
        <div className="portal-install-banner" role="region" aria-label="Add portal shortcut">
          <img className="portal-install-banner__icon" src={config.bannerIcon} alt="" aria-hidden />
          <div className="portal-install-banner__copy">
            <p className="portal-install-banner__title">{config.bannerTitle}</p>
            <p className="portal-install-banner__subtitle">{config.bannerSubtitle}</p>
          </div>
          <button type="button" className="portal-install-banner__action" onClick={() => void runInstall()}>
            Add shortcut
          </button>
          <button
            type="button"
            className="portal-install-banner__dismiss"
            aria-label="Dismiss install suggestion"
            onClick={handleDismiss}
          >
            ×
          </button>
        </div>
      ) : null}
      <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={closeSheet} />
    </>
  )
}
