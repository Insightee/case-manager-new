import { StitchIcon } from '../observation/stitch/ObservationStitchBlocks.jsx'
import { IEP_DOMAIN_TABS } from '../../../lib/iepObservationAlign.js'

const SOURCE_LABELS = {
  observation: 'Observation report',
  session_log: 'Session logs',
  clinical_evidence_events: 'Session evidence',
  session_logs: 'Session logs',
  parent_inputs: 'Parent inputs',
}

function sourceLabel(ref) {
  if (!ref?.kind) return 'Source'
  return SOURCE_LABELS[ref.kind] || ref.kind.replace(/_/g, ' ')
}

export function IepInsightsRail({
  open,
  insights,
  clinicalInsights,
  aggregatedInputs,
  readOnly,
  generating,
  onGenerate,
  onPatchInsights,
  onImportTherapistInput,
  onImportParentInput,
}) {
  if (!open) return null

  const suggestions = insights?.suggestions || []
  const domainInsights = insights?.domain_insights || {}
  const aggregates = insights?.aggregated_inputs || aggregatedInputs || {}

  return (
    <section
      className="iep-insights-panel w-full mb-6 bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 clinical-shadow"
      aria-label="InsighteAI assistant"
    >
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-lg font-bold text-lush-purple flex items-center gap-2 m-0">
            <StitchIcon name="psychology" />
            InsighteAI Assistant
          </h3>
          <p className="text-sm text-on-surface-variant m-0 mt-1">
            Pointers from observation report, session logs, and IEP domains — generate on demand.
          </p>
        </div>
        {!readOnly ? (
          <button type="button" className="cr-btn cr-btn--forest shrink-0" disabled={generating} onClick={onGenerate}>
            {generating ? 'Generating…' : 'Generate insights'}
          </button>
        ) : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2 mb-4">
        <div className="cr-insight-card cr-insight-card--positive p-3">
          <p className="text-xs uppercase font-mono opacity-80 m-0 mb-1">Promising strategy</p>
          <textarea
            className="w-full bg-transparent border-none text-white text-sm resize-y min-h-[56px] p-0"
            disabled={readOnly}
            defaultValue={clinicalInsights?.promising_strategy || ''}
            onBlur={(e) => onPatchInsights?.({ promising_strategy: e.target.value })}
          />
        </div>
        <div className="cr-insight-card cr-insight-card--barrier p-3">
          <p className="text-xs uppercase font-mono text-error m-0 mb-1">Emerging barrier</p>
          <textarea
            className="w-full border-none text-sm resize-y min-h-[56px] p-0 bg-transparent"
            disabled={readOnly}
            defaultValue={clinicalInsights?.emerging_barrier || ''}
            onBlur={(e) => onPatchInsights?.({ emerging_barrier: e.target.value })}
          />
        </div>
      </div>

      {(aggregates.therapist_summary || aggregates.parent_summary) && !readOnly ? (
        <div className="flex flex-wrap gap-2 mb-4">
          {aggregates.therapist_summary ? (
            <button
              type="button"
              className="cr-btn text-xs"
              onClick={() => onImportTherapistInput?.(aggregates.therapist_summary)}
            >
              Import session notes → therapist input
            </button>
          ) : null}
          {aggregates.parent_summary ? (
            <button
              type="button"
              className="cr-btn text-xs"
              onClick={() => onImportParentInput?.(aggregates.parent_summary)}
            >
              Import family notes → parent input
            </button>
          ) : null}
        </div>
      ) : null}

      {IEP_DOMAIN_TABS.some((t) => (domainInsights[t.id] || []).length > 0) ? (
        <div className="mb-4">
          <p className="text-xs font-bold uppercase text-outline m-0 mb-2">By IEP domain</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {IEP_DOMAIN_TABS.map((tab) => {
              const rows = domainInsights[tab.id] || []
              if (!rows.length) return null
              return (
                <div key={tab.id} className="rounded-lg border border-outline-variant/30 bg-white p-3">
                  <p className="text-sm font-semibold m-0 mb-1">{tab.label}</p>
                  <ul className="m-0 p-0 list-none space-y-1">
                    {rows.map((s) => (
                      <li key={`${tab.id}-${s.type}-${s.text}`} className="text-xs text-on-surface-variant">
                        {s.text}
                      </li>
                    ))}
                  </ul>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}

      {suggestions.length > 0 ? (
        <ul className="space-y-2 m-0 p-0 list-none">
          {suggestions.map((s) => (
            <li
              key={`${s.type}-${s.target_goal_id || s.target_domain || s.text}`}
              className="text-sm p-3 rounded-lg border border-outline-variant/30 bg-white"
            >
              <p className="m-0 font-medium">{s.text}</p>
              <p className="text-xs text-on-surface-variant m-0 mt-1 capitalize">
                {(s.type || '').replace(/_/g, ' ')}
                {s.target_section ? ` · ${s.target_section.replace(/_/g, ' ')}` : ''}
                {(s.source_refs || []).length ? ` · ${sourceLabel(s.source_refs[0])}` : ''}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-on-surface-variant m-0">
          Generate insights when goals, observation context, or session logs are in place.
        </p>
      )}
    </section>
  )
}
