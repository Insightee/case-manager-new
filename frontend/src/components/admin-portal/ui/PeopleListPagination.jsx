import { buildPageNumbers } from '../../../lib/peopleDirectoryList.js'

export function PeopleListPagination({ page, totalPages, total, rangeStart, rangeEnd, onPageChange }) {
  if (total === 0) return null

  const pageItems = buildPageNumbers(page, totalPages)

  return (
    <div className="admin-people-pagination">
      <p className="admin-muted admin-people-pagination__summary">
        Showing {rangeStart}–{rangeEnd} of {total}
      </p>
      <nav className="admin-people-pagination__nav" aria-label="Directory pages">
        <button
          type="button"
          className="admin-btn admin-btn--sm admin-btn--ghost"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          Previous
        </button>
        {pageItems.map((item, idx) =>
          item === '…' ? (
            <span key={`ellipsis-${idx}`} className="admin-people-pagination__ellipsis" aria-hidden>
              …
            </span>
          ) : (
            <button
              key={item}
              type="button"
              className={`admin-btn admin-btn--sm ${item === page ? 'admin-btn--primary' : 'admin-btn--ghost'}`}
              aria-current={item === page ? 'page' : undefined}
              onClick={() => onPageChange(item)}
            >
              {item}
            </button>
          ),
        )}
        <button
          type="button"
          className="admin-btn admin-btn--sm admin-btn--ghost"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </button>
      </nav>
    </div>
  )
}
