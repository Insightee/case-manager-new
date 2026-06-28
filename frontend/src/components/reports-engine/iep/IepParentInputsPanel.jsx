/** Parent inputs shown in IEP builder review section (CM/therapist read-only list). */
export function IepParentInputsPanel({ inputs = [] }) {
  if (!inputs.length) return null
  return (
    <div className="mt-4 rounded-lg border border-secondary-container bg-secondary-container/30 p-4">
      <h3 className="text-xs font-bold uppercase font-mono text-outline m-0 mb-2">Family input</h3>
      <ul className="space-y-2 m-0 p-0 list-none">
        {inputs.map((item) => (
          <li key={item.id} className="text-sm bg-white rounded-lg p-3 border border-outline-variant/20">
            <p className="m-0">{item.text}</p>
            {item.submitted_at ? (
              <p className="text-xs text-on-surface-variant m-0 mt-1">
                {new Date(item.submitted_at).toLocaleString()}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  )
}
