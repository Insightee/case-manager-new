import { ClinicalPrimaryButton } from '../../clinical-ui/ClinicalPrimaryButton.jsx'
import { ClinicalSecondaryButton } from '../../clinical-ui/ClinicalSecondaryButton.jsx'
import { monthOptions } from '../../../lib/insightsConstants.js'

export function MonthlySnapshotGeneratorCard({
  month,
  onMonthChange,
  preview,
  previewLoading,
  snapshot,
  generating,
  onGenerate,
  onViewPrevious,
  onSave,
  onAddToStrategies,
  onSendReview,
  onRegenerate,
}) {
  const hasSnapshot = Boolean(snapshot?.ai_output_text || snapshot?.ai_output_json?.snapshot_summary)
  const summaryText = snapshot?.ai_output_text
    || snapshot?.ai_output_json?.snapshot_summary
    || null
  const monthOptionsList = monthOptions(6)

  return (
    <div className="insights-snapshot-card">
      <div className="insights-snapshot-card__head">
        <div className="insights-snapshot-card__head-main">
          <span className="insights-snapshot-card__icon" aria-hidden="true">💡</span>
          <h3 className="insights-snapshot-card__title">
            {hasSnapshot ? "Today's clinical focus" : 'Monthly clinical snapshot'}
          </h3>
        </div>
        <div className="insights-snapshot-card__head-actions">
          <label className="insights-month-label insights-month-label--inline">
            <span className="sr-only">Month</span>
            <select
              className="insights-month-select insights-month-select--inline"
              value={month}
              onChange={(e) => onMonthChange(e.target.value)}
            >
              {monthOptionsList.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </label>
          <ClinicalPrimaryButton
            disabled={generating || previewLoading}
            onClick={hasSnapshot ? onRegenerate : onGenerate}
          >
            {generating ? 'Generating…' : 'Generate insights'}
          </ClinicalPrimaryButton>
        </div>
      </div>

      {preview?.existing_snapshot_id && !hasSnapshot ? (
        <p className="insights-previous-note">
          Previous snapshot available for this month.{' '}
          <button type="button" className="clinical-text-action" onClick={onViewPrevious}>
            Open saved snapshot
          </button>
        </p>
      ) : null}

      {!hasSnapshot ? (
        <p className="insights-snapshot-card__empty">
          {previewLoading
            ? 'Loading preview…'
            : 'Generate a snapshot to condense this month\'s session logs, goals, and strategies into supervision-ready focus text.'}
        </p>
      ) : (
        <>
          {snapshot?.reused ? (
            <p className="insights-reused-note">Using saved snapshot. Source data has not changed.</p>
          ) : null}
          {snapshot?.provider_warning ? (
            <p className="insights-provider-warning">{snapshot.provider_warning}</p>
          ) : null}
          <div className="insights-focus-text">
            <p>{summaryText}</p>
          </div>
          <div className="insights-snapshot-actions">
            <ClinicalSecondaryButton onClick={onAddToStrategies}>Add to strategies</ClinicalSecondaryButton>
            <ClinicalSecondaryButton onClick={onSave}>Save snapshot</ClinicalSecondaryButton>
            <ClinicalSecondaryButton onClick={onSendReview}>Send to CM review</ClinicalSecondaryButton>
          </div>
        </>
      )}
    </div>
  )
}
