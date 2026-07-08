function BottomActionButtons({ selectedCount, disabled, onAddToMonthlyReport, onSubmitForIepReview, mobile = false }) {
  return (
    <>
      <button
        type="button"
        className="ci-btn ci-btn--primary"
        disabled={disabled}
        onClick={() => onAddToMonthlyReport?.()}
      >
        <span className="material-symbols-outlined" aria-hidden="true">
          add_to_photos
        </span>
        {mobile
          ? `Add selected to Monthly Report${selectedCount ? ` (${selectedCount})` : ''}`
          : `Add selected insights to Monthly Report${selectedCount ? ` (${selectedCount})` : ''}`}
      </button>
      {!mobile ? (
        <button
          type="button"
          className="ci-btn ci-btn--outline"
          disabled={disabled}
          onClick={() => onSubmitForIepReview?.()}
        >
          <span className="material-symbols-outlined" aria-hidden="true">
            assignment_turned_in
          </span>
          Submit selected items for IEP Review
        </button>
      ) : null}
    </>
  )
}

export function InsightsBottomActions({ selectedCount, onAddToMonthlyReport, onSubmitForIepReview, busy }) {
  const disabled = selectedCount === 0 || busy

  return (
    <>
      <div className="ci-bottom-actions">
        <BottomActionButtons
          selectedCount={selectedCount}
          disabled={disabled}
          onAddToMonthlyReport={onAddToMonthlyReport}
          onSubmitForIepReview={onSubmitForIepReview}
        />
        <p className="ci-bottom-actions__hint">Insights added to reports remain editable and require therapist review.</p>
      </div>
      <div className="ci-bottom-actions ci-bottom-actions--mobile">
        <BottomActionButtons
          selectedCount={selectedCount}
          disabled={disabled}
          onAddToMonthlyReport={onAddToMonthlyReport}
          onSubmitForIepReview={onSubmitForIepReview}
          mobile
        />
      </div>
    </>
  )
}
