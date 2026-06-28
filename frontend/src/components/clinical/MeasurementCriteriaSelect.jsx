import { MEASUREMENT_DIMENSIONS } from '../../lib/clinicalMeasurementCriteria.js'

export function MeasurementCriteriaSelect({ values = {}, onChange, readOnly = false, compact = false }) {
  return (
    <div className={`grid gap-3${compact ? '' : ' md:grid-cols-3'}`}>
      {MEASUREMENT_DIMENSIONS.map((dim) => (
        <label key={dim.key} className="block">
          <span className="text-xs font-bold uppercase text-outline font-mono">{dim.label}</span>
          <select
            className="mt-1 w-full min-h-[44px] rounded-xl border border-outline-variant/50 bg-surface-container-lowest px-3 text-sm"
            value={values[dim.key] || ''}
            disabled={readOnly}
            onChange={(e) => onChange?.({ ...values, [dim.key]: e.target.value })}
          >
            <option value="">Select…</option>
            {dim.options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      ))}
    </div>
  )
}
