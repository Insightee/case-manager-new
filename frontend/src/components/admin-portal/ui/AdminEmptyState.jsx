export function AdminEmptyState({ title, description, hints, action }) {
  return (
    <div className="admin-empty admin-empty--guided">
      <p className="admin-empty__title">{title}</p>
      {description ? <p className="admin-empty__desc">{description}</p> : null}
      {hints?.length ? (
        <ul className="admin-empty__hints">
          {hints.map((h) => (
            <li key={h}>{h}</li>
          ))}
        </ul>
      ) : null}
      {action ? <div className="admin-empty__action">{action}</div> : null}
    </div>
  )
}
