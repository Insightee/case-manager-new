import { Link } from 'react-router-dom'

function initials(name) {
  if (!name) return '?'
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

/**
 * Left navigation sidebar for report workspace.
 * navItems: Array<{ id, label, icon?, to?, onClick? }>
 * activeItem: id of active nav item
 * primaryActionLabel + onPrimaryAction: optional large CTA button
 * footerItems: Array<{ id, label, icon?, to?, onClick? }>
 */
export function ClinicalSidebar({
  childName,
  caseCode,
  serviceType,
  avatarUrl,
  navItems = [],
  activeItem,
  primaryActionLabel,
  onPrimaryAction,
  footerItems = [],
}) {
  return (
    <aside className="clinical-sidebar">
      <div className="clinical-sidebar__identity">
        <div className="clinical-sidebar__avatar" aria-hidden="true">
          {avatarUrl
            ? <img src={avatarUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
            : initials(childName)}
        </div>
        {childName ? <p className="clinical-sidebar__name">{childName}</p> : null}
        {caseCode ? <p className="clinical-sidebar__sub">{caseCode}</p> : null}
        {serviceType ? <p className="clinical-sidebar__sub">{serviceType}</p> : null}
      </div>

      <ul className="clinical-sidebar__nav">
        {navItems.map((item) => {
          const cls = `clinical-sidebar__nav-item${activeItem === item.id ? ' is-active' : ''}`
          return (
            <li key={item.id}>
              {item.to ? (
                <Link to={item.to} className={cls}>
                  {item.icon ? <span aria-hidden="true">{item.icon}</span> : null}
                  {item.label}
                </Link>
              ) : (
                <button type="button" className={cls} onClick={item.onClick}>
                  {item.icon ? <span aria-hidden="true">{item.icon}</span> : null}
                  {item.label}
                </button>
              )}
            </li>
          )
        })}
      </ul>

      {primaryActionLabel && onPrimaryAction ? (
        <button type="button" className="clinical-sidebar__primary-btn" onClick={onPrimaryAction}>
          + {primaryActionLabel}
        </button>
      ) : null}

      {footerItems.length ? (
        <div className="clinical-sidebar__footer">
          {footerItems.map((item) => {
            const cls = 'clinical-sidebar__nav-item'
            return item.to ? (
              <Link key={item.id} to={item.to} className={cls}>
                {item.icon ? <span aria-hidden="true">{item.icon}</span> : null}
                {item.label}
              </Link>
            ) : (
              <button key={item.id} type="button" className={cls} onClick={item.onClick}>
                {item.icon ? <span aria-hidden="true">{item.icon}</span> : null}
                {item.label}
              </button>
            )
          })}
        </div>
      ) : null}
    </aside>
  )
}
