/**
 * Summary strip metric card with colored icon tile.
 */
export function StatCard({ label, value, variant }) {
  return (
    <article className={`ic-stat ic-stat--${variant}`}>
      <span className="ic-stat__icon" aria-hidden />
      <div>
        <p className="ic-stat__label">{label}</p>
        <strong className="ic-stat__value">{value}</strong>
      </div>
    </article>
  )
}
