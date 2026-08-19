import { Link } from 'react-router-dom'

export function clinicalEngineUnavailableMessage(kind = 'Clinical') {
  return `${kind} reports are not enabled on this API yet. Deploy the latest backend with ENABLE_CLINICAL_REPORTS_ENGINE=true, or point frontend/.env.local at a local backend (see backend/README.md).`
}

export function normalizeClinicalApiError(err, kind = 'Clinical') {
  const msg = err?.message || ''
  if (err?.status === 404 || /not available in this environment/i.test(msg)) {
    return clinicalEngineUnavailableMessage(kind)
  }
  return msg || `Could not load ${kind.toLowerCase()} report`
}

export function ClinicalReportNotice({ tone = 'error', children, className = '' }) {
  const tones = {
    error: 'border-red-200 bg-red-50 text-red-900',
    warn: 'border-amber-200 bg-amber-50 text-amber-950',
    info: 'border-slate-200 bg-slate-50 text-slate-800',
  }
  return (
    <p
      className={`rounded-lg border px-4 py-3 text-sm leading-relaxed m-0 ${tones[tone] || tones.error} ${className}`.trim()}
      role={tone === 'error' ? 'alert' : 'status'}
    >
      {children}
    </p>
  )
}

export function ClinicalReportEmptyState({
  title,
  message,
  backHref,
  backLabel = 'Back to reports',
  onRetry,
  retryLabel = 'Try again',
}) {
  return (
    <div className="mx-auto max-w-lg rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      {title ? <h2 className="m-0 text-lg font-bold text-slate-900">{title}</h2> : null}
      {message ? (
        <ClinicalReportNotice tone="warn" className={title ? 'mt-3' : ''}>
          {message}
        </ClinicalReportNotice>
      ) : null}
      <div className="mt-4 flex flex-wrap gap-2">
        {backHref ? (
          <Link
            to={backHref}
            className="inline-flex min-h-[44px] items-center rounded-lg border border-slate-200 px-4 py-2 text-sm font-semibold text-slate-700 no-underline"
          >
            {backLabel}
          </Link>
        ) : null}
        {onRetry ? (
          <button
            type="button"
            className="inline-flex min-h-[44px] items-center rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
            onClick={onRetry}
          >
            {retryLabel}
          </button>
        ) : null}
      </div>
    </div>
  )
}
