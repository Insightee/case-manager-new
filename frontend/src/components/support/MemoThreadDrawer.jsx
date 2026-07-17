import './memo-thread-drawer.css'

/** Side drawer with capped memo body, scrollable timeline, and pinned reply footer. */
export function MemoThreadDrawer({
  open,
  onClose,
  memoCode,
  title = 'Memo Thread',
  loading = false,
  loadingLabel = 'Loading thread details…',
  memoSection,
  timelineSection,
  timelineLabel = 'Timeline',
  footer = null,
}) {
  if (!open) return null

  return (
    <div className="memo-thread-drawer" role="dialog" aria-label={title}>
      <div className="memo-thread-drawer__header">
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b' }}>{memoCode || 'Loading…'}</span>
          <h4 style={{ margin: '4px 0 0 0', fontSize: '1rem', fontWeight: 700, color: '#1e293b' }}>{title}</h4>
        </div>
        <button type="button" className="memo-thread-drawer__close" onClick={onClose} aria-label="Close memo thread">
          ×
        </button>
      </div>

      {loading ? (
        <div className="memo-thread-drawer__loading">{loadingLabel}</div>
      ) : (
        <div className="memo-thread-drawer__body">
          <div className="memo-thread-drawer__memo">{memoSection}</div>
          <div className="memo-thread-drawer__timeline">
            <p className="memo-thread-drawer__timeline-label">{timelineLabel}</p>
            {timelineSection}
          </div>
          {footer ? <div className="memo-thread-drawer__footer">{footer}</div> : null}
        </div>
      )}
    </div>
  )
}
