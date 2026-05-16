/**
 * Stage / status pill (Observation, IEP Draft, Active, Completed, etc.)
 */
export function StatusBadge({ variant, children }) {
  return <span className={`ic-badge ic-badge--${variant}`}>{children}</span>
}
