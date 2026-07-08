import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ServiceBadge } from '../shared/ServiceBadge.jsx'

function initials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

const STATUS_LABELS = {
  ACTIVE: 'Active',
  SUSPENDED: 'Suspended',
  CLOSED: 'Closed',
  PENDING_ALLOTMENT: 'Pending allotment',
  PENDING_REPLACEMENT: 'Pending replacement',
  DEACTIVATED: 'Deactivated',
}

const STATUS_REQUEST_OPTIONS = [
  { value: 'ACTIVE', label: 'Reactivate case' },
  { value: 'SUSPENDED', label: 'Suspend case' },
  { value: 'CLOSED', label: 'Close case' },
]

function formatStatusLabel(status) {
  if (!status) return '—'
  return STATUS_LABELS[status] || String(status).replace(/_/g, ' ')
}

function statusMenuOptions(currentStatus) {
  const current = String(currentStatus || '').toUpperCase()
  return STATUS_REQUEST_OPTIONS.filter((opt) => opt.value !== current)
}

function CaseStatusMenu({ status, statusPending, onStatusRequest, onStatusClick }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)
  const listId = useId()
  const canRequest = Boolean(onStatusRequest || onStatusClick)
  const pendingTarget = statusPending?.to_status || statusPending?.toStatus
  const options = statusMenuOptions(status)

  useEffect(() => {
    if (!open) return undefined
    function handlePointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false)
    }
    function handleKey(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', handlePointer)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('pointerdown', handlePointer)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  function pickOption(value) {
    setOpen(false)
    if (onStatusRequest) {
      onStatusRequest(value)
      return
    }
    onStatusClick?.()
  }

  if (!status) return null

  if (!canRequest) {
    return (
      <span className="cch-status-pill cch-status-pill--static">
        <span className="cch-status-pill__dot" aria-hidden="true" />
        {formatStatusLabel(status)}
      </span>
    )
  }

  return (
    <div className={`cch-status-menu${open ? ' is-open' : ''}`} ref={rootRef}>
      <button
        type="button"
        className="cch-status-menu__trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={listId}
        disabled={Boolean(statusPending)}
        title={statusPending ? 'Status change awaiting approval' : 'Request status change'}
      >
        <span className="cch-status-pill__dot" aria-hidden="true" />
        <span className="cch-status-menu__label">{formatStatusLabel(status)}</span>
        {statusPending ? (
          <span className="cch-status-menu__pending">Pending</span>
        ) : (
          <span className="material-symbols-outlined cch-status-menu__chevron" aria-hidden="true">
            expand_more
          </span>
        )}
      </button>
      {open && !statusPending ? (
        <ul id={listId} className="cch-status-menu__list" role="menu">
          {options.map((opt) => (
            <li key={opt.value} role="none">
              <button
                type="button"
                role="menuitem"
                className="cch-status-menu__item"
                onClick={() => pickOption(opt.value)}
              >
                {opt.label}
              </button>
            </li>
          ))}
          <li role="none" className="cch-status-menu__hint" aria-hidden="true">
            Sends a request for admin approval
          </li>
        </ul>
      ) : null}
      {statusPending && pendingTarget ? (
        <p className="cch-status-menu__pending-note cch-status-menu__pending-note--sr" role="status">
          Requested: {formatStatusLabel(pendingTarget)} — awaiting approval
        </p>
      ) : null}
    </div>
  )
}

export function ClinicalCaseHeader({
  childName,
  caseCode,
  serviceType,
  service,
  productModule,
  status,
  statusPending = null,
  avatarUrl,
  onStatusClick,
  onStatusRequest,
  onChangeCase,
  changeCaseLabel = 'Change case',
  supportHref,
  supportLabel = 'Support',
  headerActions,
}) {
  return (
    <header className="clinical-case-header">
      <div className="clinical-case-header__profile-row">
        <div className="clinical-case-header__identity">
          <div className="clinical-case-header__avatar" aria-hidden="true">
            {avatarUrl ? (
              <img src={avatarUrl} alt="" className="clinical-case-header__avatar-img" />
            ) : (
              initials(childName)
            )}
          </div>

          <div className="clinical-case-header__info">
            <div className="clinical-case-header__title-line">
              {childName ? <h1 className="clinical-case-header__name">{childName}</h1> : null}
              {caseCode ? <span className="clinical-case-header__code-pill">{caseCode}</span> : null}
            </div>

            <div className="clinical-case-header__meta-row">
              {service || productModule ? (
                <ServiceBadge
                  service={service || serviceType}
                  productModule={productModule}
                  className="clinical-case-header__service-badge"
                />
              ) : serviceType ? (
                <p className="clinical-case-header__service">{serviceType}</p>
              ) : null}

              <CaseStatusMenu
                status={status}
                statusPending={statusPending}
                onStatusRequest={onStatusRequest}
                onStatusClick={onStatusClick}
              />

              {supportHref ? (
                <Link to={supportHref} className="clinical-case-header__support-link">
                  {supportLabel}
                </Link>
              ) : null}

              {headerActions ? <div className="clinical-case-header__extra">{headerActions}</div> : null}
            </div>
          </div>
        </div>

        {onChangeCase ? (
          <button
            type="button"
            className="clinical-case-header__change-case"
            onClick={onChangeCase}
            aria-haspopup="dialog"
          >
            <span className="material-symbols-outlined" aria-hidden="true">
              swap_horiz
            </span>
            <span className="clinical-case-header__change-case-label">{changeCaseLabel}</span>
          </button>
        ) : null}
      </div>
    </header>
  )
}
