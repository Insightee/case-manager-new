import { Link } from 'react-router-dom'
import { ClinicalStatusBadge } from './ClinicalStatusBadge.jsx'

function initials(name) {
  if (!name) return '?'
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}

export function ClinicalCaseHeader({
  childName,
  caseCode,
  serviceType,
  status,
  avatarUrl,
  onStatusClick,
  supportHref,
  supportLabel = 'Support',
  headerActions,
}) {
  return (
    <header className="clinical-case-header">
      <div className="clinical-case-header__row">
        <div className="clinical-case-header__avatar" aria-hidden="true">
          {avatarUrl
            ? <img src={avatarUrl} alt="" className="clinical-case-header__avatar-img" />
            : initials(childName)}
        </div>
        <div className="clinical-case-header__info">
          <div className="clinical-case-header__title-line">
            {childName ? <h1 className="clinical-case-header__name">{childName}</h1> : null}
            {caseCode ? <span className="clinical-case-header__code-pill">{caseCode}</span> : null}
          </div>
          {serviceType ? <p className="clinical-case-header__service">{serviceType}</p> : null}
        </div>
        <div className="clinical-case-header__toolbar">
          {status && onStatusClick ? (
            <button
              type="button"
              className="clinical-case-header__status-btn"
              onClick={onStatusClick}
              title="Request status change"
              aria-label={`Case status ${status}. Request change`}
            >
              <ClinicalStatusBadge status={status} />
            </button>
          ) : status ? (
            <ClinicalStatusBadge status={status} />
          ) : null}
          {supportHref ? (
            <Link to={supportHref} className="clinical-case-header__support-link">
              {supportLabel}
            </Link>
          ) : null}
          {headerActions ? <div className="clinical-case-header__extra">{headerActions}</div> : null}
        </div>
      </div>
    </header>
  )
}
