import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { usePortalInstallActions } from '../../hooks/usePortalInstallActions.js'
import { useIsMobilePortal } from '../../hooks/useMediaQuery.js'
import { portalAppMenuItems } from '../../lib/portalAppActions.js'
import { refreshApp } from '../../lib/pwaUpdate.js'
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

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const ACTION_COPY = {
  install: { label: 'Install', menu: 'Install app' },
  refresh: { label: 'Refresh', menu: 'Refresh app' },
}

export function PortalInstallButton({ variant = 'topbar' }) {
  const isMobilePortal = useIsMobilePortal()
  const wrapRef = useRef(null)
  const [coachActive, setCoachActive] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuId = useId()
  const { config, canShowInstall, installed, standalone, primaryAction, runInstall, sheet, closeSheet } =
    usePortalInstallActions(variant)

  const closeMenu = useCallback(() => setMenuOpen(false), [])

  useEffect(() => {
    if (!menuOpen) return undefined
    const onPointer = (event) => {
      if (wrapRef.current && !wrapRef.current.contains(event.target)) closeMenu()
    }
    const onKey = (event) => {
      if (event.key === 'Escape') closeMenu()
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [closeMenu, menuOpen])

  const handleRefresh = useCallback(() => {
    closeMenu()
    void refreshApp()
  }, [closeMenu])

  const handleInstall = useCallback(() => {
    closeMenu()
    void runInstall()
  }, [closeMenu, runInstall])

  if (!canShowInstall || !config) {
    return null
  }

  const showDesktopCoach = variant === 'sidebar' && !isMobilePortal && !installed && !menuOpen
  const primary = primaryAction === 'refresh' ? 'refresh' : 'install'
  const items = portalAppMenuItems(primary)
  const buttonLabel = standalone ? ACTION_COPY.refresh.label : ACTION_COPY.install.label
  const buttonClassName =
    variant === 'sidebar'
      ? `portal-install-btn portal-install-btn--sidebar${coachActive ? ' portal-install-btn--highlight' : ''}`
      : 'portal-install-btn'

  const button = (
    <button
      type="button"
      className={buttonClassName}
      aria-label={`${buttonLabel} — Install and Refresh`}
      title={`${buttonLabel} — Install and Refresh`}
      aria-haspopup="menu"
      aria-expanded={menuOpen}
      aria-controls={menuId}
      onClick={() => setMenuOpen((open) => !open)}
    >
      {primary === 'refresh' ? <RefreshIcon /> : <DownloadIcon />}
    </button>
  )

  return (
    <>
      <div className={`portal-install-wrap portal-install-wrap--${variant}`} ref={wrapRef}>
        {button}
        {menuOpen ? (
          <div id={menuId} className={`portal-install-menu portal-install-menu--${variant}`} role="menu">
            {items.map((action) => (
              <button
                key={action}
                type="button"
                role="menuitem"
                onClick={action === 'refresh' ? handleRefresh : handleInstall}
              >
                {ACTION_COPY[action].menu}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {variant === 'sidebar' ? (
        <PortalInstallCoachmark
          appName={config.appName}
          visible={showDesktopCoach}
          anchorRef={wrapRef}
          onActiveChange={setCoachActive}
        />
      ) : null}
      <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={closeSheet} />
    </>
  )
}
