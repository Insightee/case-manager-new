/** Desktop table + mobile card list (CSS toggles visibility at 900px). */
export function AdminDataList({ desktop, mobile, className = '' }) {
  return (
    <div className={`admin-data-list ${className}`.trim()}>
      <div className="admin-data-list__desktop">{desktop}</div>
      <ul className="admin-data-list__mobile" aria-label="List">
        {mobile}
      </ul>
    </div>
  )
}
