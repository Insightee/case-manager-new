export function AdminEmptyState({ title, description, action }) {
  return (
    <div className="admin-empty">
      <p className="admin-empty__title">{title}</p>
      {description ? <p className="admin-empty__desc">{description}</p> : null}
      {action}
    </div>
  )
}
