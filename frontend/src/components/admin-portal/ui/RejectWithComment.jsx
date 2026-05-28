/**
 * Two-step reject: "Reject…" expands a required comment field, then "Confirm reject".
 */
export function RejectWithComment({
  rejecting = false,
  comment = '',
  onCommentChange,
  onStartReject,
  onCancelReject,
  onConfirmReject,
  onApprove,
  processing = false,
  showApprove = true,
  approveLabel = 'Approve',
  placeholder = 'Reason for rejection (required)',
}) {
  if (rejecting) {
    return (
      <div className="reject-with-comment reject-with-comment--mobile" style={{ marginTop: 8 }}>
        <textarea
          className="admin-input"
          rows={3}
          value={comment}
          onChange={(e) => onCommentChange(e.target.value)}
          placeholder={placeholder}
          style={{ width: '100%', minHeight: 72, resize: 'vertical', marginBottom: 8 }}
          autoFocus
        />
        <div className="admin-btn-group">
          <button
            type="button"
            className="admin-btn admin-btn--danger admin-btn--sm"
            disabled={processing || !comment.trim()}
            onClick={onConfirmReject}
          >
            Confirm reject
          </button>
          <button
            type="button"
            className="admin-btn admin-btn--ghost admin-btn--sm"
            disabled={processing}
            onClick={onCancelReject}
          >
            Cancel
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-btn-group reject-with-comment reject-with-comment--mobile" style={{ marginTop: 8 }}>
      {showApprove && onApprove ? (
        <button
          type="button"
          className="admin-btn admin-btn--primary admin-btn--sm"
          disabled={processing}
          onClick={onApprove}
        >
          {approveLabel}
        </button>
      ) : null}
      <button
        type="button"
        className="admin-btn admin-btn--danger admin-btn--sm"
        disabled={processing}
        onClick={onStartReject}
      >
        Reject
      </button>
    </div>
  )
}
