import { Link } from 'react-router-dom'
import {
  MISSING_PACKAGE_COUNT_CODE,
  billingCalcErrorBannerText,
  parseBillingCalcApiError,
} from '../../lib/billingCalcErrors.js'

/**
 * @param {{ error: unknown, audience?: 'therapist'|'admin'|'parent', className?: string, tone?: 'warning'|'error' }} props
 */
export function BillingCalcErrorNotice({ error, audience = 'therapist', className = '', tone = 'warning' }) {
  if (!error) return null
  // Some callers still set plain-string errors (e.g. remove-session failures) — render them as-is.
  const parsed = typeof error === 'string' ? null : parseBillingCalcApiError(error)
  const message =
    typeof error === 'string'
      ? error
      : parsed
        ? billingCalcErrorBannerText(parsed, audience)
        : String(error?.message || '') || 'Something went wrong. Try again in a moment.'
  if (!message) return null

  const base =
    tone === 'error'
      ? 'rounded-lg bg-red-50 px-3 py-2 text-sm text-red-900'
      : 'rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950'

  const showAdminLinks = audience === 'admin' && parsed?.code === MISSING_PACKAGE_COUNT_CODE

  return (
    <div className={`${base} ${className}`.trim()} role="alert">
      <p className="m-0 leading-snug">{message}</p>
      {showAdminLinks ? (
        <p className="mb-0 mt-2 text-xs leading-snug opacity-90">
          <Link to="/admin/data-exceptions" className="font-semibold underline">
            Data exceptions
          </Link>
          {parsed.caseId ? (
            <>
              {' · '}
              <Link to={`/admin/cases/${parsed.caseId}`} className="font-semibold underline">
                Open case {parsed.caseCode || parsed.caseId}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  )
}
