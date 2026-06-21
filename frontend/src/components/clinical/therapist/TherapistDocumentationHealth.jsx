import { DocumentationHealthCard } from '../quality/DocumentationHealthCard.jsx'
import { EvidenceCompletenessCard } from '../quality/EvidenceCompletenessCard.jsx'

export function TherapistDocumentationHealth({ caseId, summary }) {
  if (!summary) {
    return (
      <section className="ic-case-panel">
        <h3>Documentation health</h3>
        <p className="ic-case-panel__loading">Loading…</p>
      </section>
    )
  }
  return (
    <div className="cp-quality-grid cp-quality-grid--compact">
      <DocumentationHealthCard summary={summary} />
      <EvidenceCompletenessCard summary={summary} />
    </div>
  )
}
