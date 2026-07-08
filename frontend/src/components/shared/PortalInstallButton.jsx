import { useRef, useState } from 'react'
import { usePortalInstallActions } from '../../hooks/usePortalInstallActions.js'
import { useIsMobilePortal } from '../../hooks/useMediaQuery.js'
import { PortalInstallCoachmark } from './PortalInstallCoachmark.jsx'
import { PortalInstallSheets } from './PortalInstallSheets.jsx'
import './portal-install.css'

function DownloadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M12 4v10m0 0 4-4m-4 4-4-4M5 18h14"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function PortalInstallButton({ variant = 'topbar' }) {
  const isMobilePortal = useIsMobilePortal()
  const anchorRef = useRef(null)
  const [coachActive, setCoachActive] = useState(false)
  const { config, canShowInstall, installed, runInstall, sheet, closeSheet } = usePortalInstallActions(variant)

  if (!canShowInstall || !config) {
    return null
  }

  const showDesktopCoach = variant === 'sidebar' && !isMobilePortal && !installed
  const buttonClassName =
    variant === 'sidebar'
      ? `portal-install-btn portal-install-btn--sidebar${coachActive ? ' portal-install-btn--highlight' : ''}`
      : 'portal-install-btn'

  const button = (
    <button
      type="button"
      className={buttonClassName}
      aria-label={config.installLabel}
      title={config.installLabel}
      onClick={() => void runInstall()}
    >
      <DownloadIcon />
    </button>
  )

  if (variant !== 'sidebar') {
    return (
      <>
        {button}
        <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={closeSheet} />
      </>
    )
  }

  return (
    <>
      <div className="portal-install-sidebar-wrap" ref={anchorRef}>
        {button}
      </div>
      <PortalInstallCoachmark
        appName={config.appName}
        visible={showDesktopCoach}
        anchorRef={anchorRef}
        onActiveChange={setCoachActive}
      />
      <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={closeSheet} />
    </>
  )
}
