import { createPortal } from 'react-dom'

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

export function PortalInstallSheets({ sheet, appName, onClose }) {
  if (!sheet || !appName) return null

  if (sheet === 'ios') {
    return (
      <InstallSheet appName={appName} onClose={onClose}>
        <ol>
          <li>Tap the Share button in Safari (square with an arrow).</li>
          <li>
            Scroll down and choose <strong>Add to Home Screen</strong>.
          </li>
          <li>
            Tap <strong>Add</strong> in the top corner.
          </li>
        </ol>
      </InstallSheet>
    )
  }

  if (sheet === 'mac') {
    return (
      <InstallSheet appName={appName} title={`Add ${appName} to your Dock`} onClose={onClose}>
        <ol>
          <li>
            In Safari, open the menu bar and choose <strong>File → Add to Dock…</strong>
          </li>
          <li>
            Or click <strong>Share</strong> in the toolbar, then choose <strong>Add to Dock</strong>.
          </li>
          <li>
            Confirm with <strong>Add</strong> — {appName} will appear in your Dock like an app.
          </li>
        </ol>
      </InstallSheet>
    )
  }

  return (
    <InstallSheet appName={appName} onClose={onClose}>
      <p className="portal-install-sheet__tip">
        After an app update, remove the old icon first if sign-in or pages act stuck — then add the shortcut again from the browser.
      </p>
      <ol>
        <li>Open your browser menu (three dots or lines).</li>
        <li>
          Choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.
        </li>
        <li>Confirm to add the {appName} shortcut.</li>
      </ol>
    </InstallSheet>
  )
}
