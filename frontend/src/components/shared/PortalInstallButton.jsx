import { useState } from 'react'
import { createPortal } from 'react-dom'
import { usePortalPwa } from '../../hooks/usePortalPwa.js'
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

function InstallSheet({ appName, title, children, onClose }) {
  return createPortal(
    <div className="portal-install-overlay" role="presentation" onClick={onClose}>
      <div
        className="portal-install-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="portal-install-title"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="portal-install-title">{title || `Add ${appName} to your home screen`}</h2>
        <p>This opens the portal directly from an app icon — same login and features as the website.</p>
        {children}
        <div className="portal-install-sheet__actions">
          <button type="button" className="portal-install-sheet__close" onClick={onClose}>
            Got it
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}

function IosInstallSheet({ appName, onClose }) {
  return (
    <InstallSheet appName={appName} onClose={onClose}>
      <ol>
        <li>Tap the Share button in Safari (square with an arrow).</li>
        <li>Scroll down and choose <strong>Add to Home Screen</strong>.</li>
        <li>Tap <strong>Add</strong> in the top corner.</li>
      </ol>
    </InstallSheet>
  )
}

function GenericInstallSheet({ appName, onClose }) {
  return (
    <InstallSheet appName={appName} onClose={onClose}>
      <ol>
        <li>Open your browser menu (three dots or lines).</li>
        <li>Choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.</li>
        <li>Confirm to add the {appName} shortcut.</li>
      </ol>
    </InstallSheet>
  )
}

export function PortalInstallButton({ portal, variant = 'topbar' }) {
  const { config, canShowInstall, iosSafari, canNativeInstall, promptInstall } = usePortalPwa(portal, {
    surface: variant,
  })
  const [sheet, setSheet] = useState(null)

  if (!canShowInstall || !config) {
    return null
  }

  async function handleClick() {
    if (canNativeInstall) {
      await promptInstall()
      return
    }
    if (iosSafari) {
      setSheet('ios')
      return
    }
    setSheet('generic')
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
        onClick={handleClick}
      >
        <DownloadIcon />
      </button>
      {sheet === 'ios' ? (
        <IosInstallSheet appName={config.appName} onClose={() => setSheet(null)} />
      ) : null}
      {sheet === 'generic' ? (
        <GenericInstallSheet appName={config.appName} onClose={() => setSheet(null)} />
      ) : null}
    </>
  )
}
