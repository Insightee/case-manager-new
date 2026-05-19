import { Link } from 'react-router-dom'

export function AdminStatCard({ title, value, hint, tone = 'indigo', icon, to, onClick }) {
  const inner = (
    <>
      <div className="admin-stat__top">
        <p className="admin-stat__label">{title}</p>
        {icon ? <span className="admin-stat__icon" aria-hidden>{icon}</span> : null}
      </div>
      <p className="admin-stat__value">{value}</p>
      {hint ? <p className="admin-stat__hint">{hint}</p> : null}
    </>
  )

  const className = `admin-stat admin-stat--${tone}`

  if (to) {
    return (
      <Link to={to} className={`${className} admin-stat--link`}>
        {inner}
      </Link>
    )
  }

  if (onClick) {
    return (
      <button type="button" className={`${className} admin-stat--link`} onClick={onClick}>
        {inner}
      </button>
    )
  }

  return <article className={className}>{inner}</article>
}
