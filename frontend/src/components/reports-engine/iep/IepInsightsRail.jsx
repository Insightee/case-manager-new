import { StitchIcon } from '../observation/stitch/ObservationStitchBlocks.jsx'

export function IepInsightsRail({
  open,
  insights,
  clinicalInsights,
  readOnly,
  generating,
  onGenerate,
  onPatchInsights,
}) {
  if (!open) return null

  const suggestions = insights?.suggestions || []

  return (
    <aside className="iep-insights-rail w-full lg:w-[340px] shrink-0 bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-5 clinical-shadow">
      <h3 className="text-lg font-bold text-lush-purple flex items-center gap-2 m-0 mb-4">
        <StitchIcon name="psychology" />
        InsighteAI
      </h3>
      <p className="text-sm text-on-surface-variant m-0 mb-4">
        Progress signals and draft suggestions — generate on demand.
      </p>

      <div className="grid gap-3 mb-4">
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

      {!readOnly ? (
        <button
          type="button"
          className="w-full cr-btn cr-btn--forest mb-4"
          disabled={generating}
          onClick={onGenerate}
        >
          {generating ? 'Generating…' : 'Generate insights'}
        </button>
      ) : null}

      {suggestions.length > 0 ? (
        <ul className="space-y-2 m-0 p-0 list-none">
          {suggestions.map((s) => (
            <li key={`${s.type}-${s.target_goal_id || s.text}`} className="text-sm p-3 rounded-lg border border-outline-variant/30 bg-white">
              <p className="m-0 font-medium">{s.text}</p>
              <p className="text-xs text-on-surface-variant m-0 mt-1 capitalize">{s.type?.replace(/_/g, ' ')}</p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-on-surface-variant m-0">No suggestions yet — generate when goals and observation context are in place.</p>
      )}
    </aside>
  )
}
