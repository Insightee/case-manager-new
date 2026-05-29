import { Link } from 'react-router-dom'

export function AdminStatCard({ title, value, hint, tone = 'indigo', icon, to, onClick, active = false }) {
  const inner = (
    <>
      <div className="admin-stat__top">
        <span className="admin-stat__label">{title}</span>
        {icon ? <span className="admin-stat__icon" aria-hidden>{icon}</span> : null}
      </div>
      <span className="admin-stat__value">{value}</span>
      {hint ? <span className="admin-stat__hint">{hint}</span> : null}
    </>
  )

  const className = `admin-stat admin-stat--${tone}${active ? ' is-active' : ''}`

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
