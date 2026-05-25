import { ErrorBanner } from './ErrorBanner.jsx'
import { PageSkeleton } from './PageSkeleton.jsx'

export function QueryState({
  isLoading,
  isError,
  error,
  onRetry,
  isEmpty,
  emptyMessage = 'Nothing here yet.',
  skeletonVariant = 'list',
  skeletonRows = 4,
  children,
}) {
  if (isLoading) {
    return <PageSkeleton rows={skeletonRows} variant={skeletonVariant} />
  }
  if (isError) {
    return (
      <div className="query-state query-state--error">
        <ErrorBanner message={error?.message || 'Something went wrong loading this page.'} />
        {onRetry ? (
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Try again
          </button>
        ) : null}
      </div>
    )
  }
  if (isEmpty) {
    return <p className="query-state__empty">{emptyMessage}</p>
  }
  return children
}
