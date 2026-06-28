import { PortalComingSoon } from './PortalComingSoon.jsx'

/** Route-level gate — avoids conditional hooks inside page components. */
export function FeatureRoute({ enabled, variant, title, body, children }) {
  if (!enabled) {
    return <PortalComingSoon variant={variant} title={title} body={body} />
  }
  return children
}
