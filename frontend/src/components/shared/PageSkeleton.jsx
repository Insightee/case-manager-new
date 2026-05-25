export function PageSkeleton({ rows = 4, variant = 'list' }) {
  if (variant === 'grid') {
    return (
      <div className="page-skeleton page-skeleton--grid" aria-hidden>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="page-skeleton__card" />
        ))}
      </div>
    )
  }
  return (
    <div className="page-skeleton" aria-hidden>
      <div className="page-skeleton__bar page-skeleton__bar--title" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="page-skeleton__bar" />
      ))}
    </div>
  )
}
