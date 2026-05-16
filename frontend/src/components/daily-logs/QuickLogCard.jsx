import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

function toggleInList(list, tag) {
  if (list.includes(tag)) return list.filter((t) => t !== tag)
  return [...list, tag]
}

export function QuickLogCard({
  cases,
  activityTags,
  lastSessionByCase,
  selectedCaseId,
  onCaseIdChange,
  onSubmitSuccess,
  formSeed,
  onFormSeedConsumed,
}) {
  const [duration, setDuration] = useState(45)
  const [activities, setActivities] = useState([])
  const [observations, setObservations] = useState('')
  const skipNextAutofill = useRef(false)

  const applyLastSession = useCallback(
    (caseId) => {
      const last = lastSessionByCase[caseId]
      if (last) {
        setDuration(last.durationMinutes ?? 45)
        setActivities(last.activities ?? [])
        setObservations(last.observations ?? '')
      } else {
        setDuration(45)
        setActivities([])
        setObservations('')
      }
    },
    [lastSessionByCase],
  )

  useEffect(() => {
    if (formSeed?.id) {
      queueMicrotask(() => {
        if (formSeed.durationMinutes != null) setDuration(formSeed.durationMinutes)
        if (Array.isArray(formSeed.activities)) setActivities(formSeed.activities)
        if (formSeed.observations != null) setObservations(formSeed.observations)
        skipNextAutofill.current = true
        onFormSeedConsumed?.()
      })
      return
    }
    if (skipNextAutofill.current) {
      skipNextAutofill.current = false
      return
    }
    applyLastSession(selectedCaseId)
  }, [selectedCaseId, applyLastSession, formSeed, onFormSeedConsumed])

  const caseLabel = useMemo(() => {
    const c = cases.find((x) => x.caseId === selectedCaseId)
    return c ? `${c.caseId} · ${c.child}` : 'Select a case'
  }, [cases, selectedCaseId])

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmitSuccess?.({
      caseId: selectedCaseId,
      durationMinutes: duration,
      activities,
      observations,
    })
  }

  return (
    <section
      id="quick-log-panel"
      className="rounded-2xl border border-[#E2E8F0] bg-white p-5 shadow-[0_4px_24px_rgba(79,70,229,0.07)] sm:p-6"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">Quick log</h3>
          <p className="mt-1 text-sm text-slate-500">
            Fast entry — autofill pulls your last session for the selected case.
          </p>
        </div>
        <span className="rounded-full bg-orange-100 px-3 py-1 text-xs font-bold uppercase tracking-wide text-orange-800">
          &lt; 1 min
        </span>
      </div>

      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        <div>
          <label htmlFor="quick-case" className="mb-2 block text-sm font-medium text-slate-700">
            Case
          </label>
          <select
            id="quick-case"
            value={selectedCaseId}
            onChange={(e) => onCaseIdChange(e.target.value)}
            className="w-full min-h-[48px] rounded-xl border border-[#E2E8F0] bg-slate-50/80 px-4 py-3 text-base font-medium text-slate-900 shadow-sm outline-none ring-indigo-500/0 transition focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-500/15"
          >
            {cases.map((c) => (
              <option key={c.caseId} value={c.caseId}>
                {c.caseId} — {c.child}
              </option>
            ))}
          </select>
          <p className="mt-1.5 text-xs text-slate-500">{caseLabel}</p>
        </div>

        <div>
          <label htmlFor="quick-duration" className="mb-2 block text-sm font-medium text-slate-700">
            Duration (minutes)
          </label>
          <input
            id="quick-duration"
            type="number"
            min={5}
            max={240}
            step={5}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            className="w-full min-h-[48px] rounded-xl border border-[#E2E8F0] bg-white px-4 py-3 text-lg font-semibold tabular-nums text-slate-900 outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
          />
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">Activities</p>
          <div className="flex flex-wrap gap-2">
            {activityTags.map((tag) => {
              const on = activities.includes(tag)
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => setActivities((a) => toggleInList(a, tag))}
                  className={`rounded-full px-3 py-2 text-sm font-medium transition-all ${
                    on
                      ? 'bg-indigo-600 text-white shadow-sm ring-2 ring-indigo-300'
                      : 'bg-slate-50 text-slate-700 ring-1 ring-[#E2E8F0] hover:bg-slate-100'
                  }`}
                >
                  {tag}
                </button>
              )
            })}
          </div>
        </div>

        <div>
          <label htmlFor="quick-obs" className="mb-2 block text-sm font-medium text-slate-700">
            Observations
          </label>
          <textarea
            id="quick-obs"
            rows={3}
            value={observations}
            onChange={(e) => setObservations(e.target.value)}
            placeholder="Brief session notes…"
            className="w-full resize-y rounded-xl border border-[#E2E8F0] bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-500/15"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <button
            type="submit"
            className="min-h-[48px] min-w-[160px] rounded-xl bg-indigo-600 px-6 text-base font-semibold text-white shadow-md transition hover:bg-indigo-700 hover:shadow-lg active:scale-[0.99]"
          >
            Submit log
          </button>
          <button
            type="button"
            className="text-sm font-semibold text-indigo-600 underline-offset-4 hover:underline"
            onClick={() => applyLastSession(selectedCaseId)}
          >
            Reset to last session
          </button>
        </div>
      </form>
    </section>
  )
}
