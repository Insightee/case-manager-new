import { useAppVersionNotice } from '../../hooks/useAppVersionNotice.js'
import { getEmbeddedReleaseLabel } from '../../lib/appVersionUpdate.js'
import './app-release-label.css'

/**
 * Unobtrusive build label (iMMDD IST) — same in all portals (account menu / sidebar footer).
 * @param {{ variant?: 'menu' | 'footer', className?: string }} props
 */
export function AppReleaseLabel({ variant = 'footer', className = '' }) {
  const embedded = getEmbeddedReleaseLabel()
  const { remoteReleaseLabel, refreshRemote } = useAppVersionNotice()

  const showLatest =
    remoteReleaseLabel &&
    embedded !== 'dev' &&
    remoteReleaseLabel !== embedded &&
    remoteReleaseLabel

  return (
    <p
      className={`app-release-label app-release-label--${variant}${className ? ` ${className}` : ''}`}
      title="App build version (IST)"
    >
      <span className="app-release-label__tag">Build {embedded}</span>
      {showLatest ? (
        <button type="button" className="app-release-label__latest" onClick={() => void refreshRemote()}>
          Latest {remoteReleaseLabel}
        </button>
      ) : null}
    </p>
  )
}
