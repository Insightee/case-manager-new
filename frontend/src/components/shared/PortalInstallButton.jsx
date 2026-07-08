import { usePortalInstallActions } from '../../hooks/usePortalInstallActions.js'
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
  const { config, canShowInstall, runInstall, sheet, closeSheet } = usePortalInstallActions(variant)

  if (!canShowInstall || !config) {
    return null
  }

  const className =
    variant === 'sidebar'
      ? 'portal-install-btn portal-install-btn--sidebar'
      : 'portal-install-btn'

  return (
    <>
      <button
        type="button"
        className={className}
        aria-label={config.installLabel}
        title={config.installLabel}
        onClick={() => void runInstall()}
      >
        <DownloadIcon />
      </button>
      <PortalInstallSheets sheet={sheet} appName={config.appName} onClose={closeSheet} />
    </>
  )
}
