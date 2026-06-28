import { TherapistCasePickerPanel } from '../cases/TherapistCasePickerPanel.jsx'

export function ChangeCaseSheet({
  open,
  cases,
  currentCaseId,
  onSelect,
  onClose,
  onViewAll,
  viewAllLabel = 'View all clients',
}) {
  if (!open) return null

  return (
    <div className="change-case-sheet" role="dialog" aria-modal="true" aria-labelledby="change-case-sheet-title">
      <button type="button" className="change-case-sheet__backdrop" aria-label="Close" onClick={onClose} />
      <div className="change-case-sheet__panel">
        {onViewAll ? (
          <button type="button" className="change-case-sheet__view-all" onClick={onViewAll}>
            {viewAllLabel}
          </button>
        ) : null}
        <TherapistCasePickerPanel
          title="Switch client"
          subtitle="Pending and recent clients appear first. Your current tab stays open after you switch."
          cases={cases.filter((c) => String(c.id) !== String(currentCaseId))}
          onSelect={onSelect}
          onCancel={onClose}
        />
      </div>
    </div>
  )
}
