import {
  clientPortalModuleRolloutMessage,
  shouldShowClientPortalRolloutNotice,
} from '../../lib/productFeatureFlags.js'
import './portal-module-rollout-notice.css'

export function PortalModuleRolloutNotice() {
  if (!shouldShowClientPortalRolloutNotice()) return null

  const message = clientPortalModuleRolloutMessage()

  return (
    <div className="portal-module-rollout-notice" role="status" aria-live="polite">
      <span className="portal-module-rollout-notice__icon material-symbols-outlined" aria-hidden="true">
        info
      </span>
      <p className="portal-module-rollout-notice__text">{message}</p>
    </div>
  )
}
