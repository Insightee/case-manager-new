import { serviceStyleFromCase } from '../../lib/serviceColors.js'

export function ServiceBadge({ service, productModule, caseRow, className = '' }) {
  const style = caseRow ? serviceStyleFromCase(caseRow) : serviceStyleFromCase({ service, productModule })
  return (
    <span
      className={`service-badge service-badge--${style.tone}${className ? ` ${className}` : ''}`}
      style={{
        '--service-bg': style.bg,
        '--service-text': style.text,
        '--service-border': style.border,
      }}
    >
      {style.label}
    </span>
  )
}
