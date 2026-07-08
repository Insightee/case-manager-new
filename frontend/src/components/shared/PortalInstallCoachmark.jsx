import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { usePortalInstall } from '../../context/usePortalInstall.js'
import { dismissInstallCoach, isInstallCoachDismissed, isMacDesktop } from '../../lib/portalPwa.js'

const COACH_DELAY_MS = 2500
const COACH_WIDTH = 248
const VIEWPORT_MARGIN = 12

const COACH_TITLE = 'Install for quick access'

function computeCoachPosition(anchorRect) {
  const anchorCenterX = anchorRect.left + anchorRect.width / 2
  const halfWidth = COACH_WIDTH / 2
  let left = anchorCenterX

  if (left - halfWidth < VIEWPORT_MARGIN) {
    left = VIEWPORT_MARGIN + halfWidth
  } else if (left + halfWidth > window.innerWidth - VIEWPORT_MARGIN) {
    left = window.innerWidth - VIEWPORT_MARGIN - halfWidth
  }

  return {
    top: anchorRect.bottom + 10,
    left,
    arrowLeft: anchorCenterX - left,
  }
}

export function PortalInstallCoachmark({ appName, visible, anchorRef, onActiveChange }) {
  const { portal } = usePortalInstall()
  const [dismissedSession, setDismissedSession] = useState(false)
  const dismissed = dismissedSession || isInstallCoachDismissed(portal)
  const [revealed, setRevealed] = useState(false)
  const [position, setPosition] = useState(null)

  const showCoach = visible && !dismissed && revealed

  useEffect(() => {
    if (!visible || dismissed) {
      setRevealed(false)
      return undefined
    }
    const timer = window.setTimeout(() => setRevealed(true), COACH_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [visible, dismissed])

  useEffect(() => {
    onActiveChange?.(showCoach)
  }, [showCoach, onActiveChange])

  useEffect(() => {
    if (!showCoach || !anchorRef?.current) {
      setPosition(null)
      return undefined
    }

    function updatePosition() {
      if (!anchorRef.current) return
      setPosition(computeCoachPosition(anchorRef.current.getBoundingClientRect()))
    }

    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [showCoach, anchorRef])

  if (!showCoach || !position) {
    return null
  }

  const installDestination = isMacDesktop() ? 'Dock' : 'desktop'

  function handleDismiss() {
    dismissInstallCoach(portal)
    setDismissedSession(true)
  }

  return createPortal(
    <div
      className="portal-install-coach"
      role="status"
      style={{
        top: position.top,
        left: position.left,
        width: COACH_WIDTH,
        ['--coach-arrow-offset']: `${position.arrowLeft}px`,
      }}
    >
      <div className="portal-install-coach__header">
        <p className="portal-install-coach__title">{COACH_TITLE}</p>
        <button
          type="button"
          className="portal-install-coach__dismiss"
          aria-label="Dismiss install hint"
          onClick={handleDismiss}
        >
          ×
        </button>
      </div>
      <p className="portal-install-coach__body">
        Click the download button to add <strong>{appName}</strong> to your {installDestination}.
      </p>
      <span className="portal-install-coach__arrow" aria-hidden />
    </div>,
    document.body,
  )
}
